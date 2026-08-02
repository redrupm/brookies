import gymnasium as gym
from gymnasium import spaces
import numpy as np

class DynamicSlotTradingEnv(gym.Env):
    """
    A custom Gymnasium environment using a Dynamic Slotting buffer.
    Action Space: 51 continuous logits (Cash + 50 Asset Slots).
    Observation Space: 50 active slots x N features.
    """
    
    def __init__(self, data_feed, initial_balance=10000.0, transaction_fee_bps=5):
        super().__init__()
        
        # Configuration
        self.max_slots = 50
        self.num_features = 5 # e.g., Norm_Price, Score, Confidence, Direction, Pct_Owned
        self.initial_balance = initial_balance
        self.transaction_fee = transaction_fee_bps / 10000.0
        
        self.data_feed = data_feed 
        
        # Action Space: 51 continuous values (Logits). The env applies Softmax.
        self.action_space = spaces.Box(
            low=-10.0, 
            high=10.0, 
            shape=(self.max_slots + 1,), 
            dtype=np.float32
        )
        
        # Observation Space: 50 slots, each with 'num_features'
        self.observation_space = spaces.Box(
            low=-np.inf, 
            high=np.inf, 
            shape=(self.max_slots, self.num_features), 
            dtype=np.float32
        )
        
        # Internal State
        self.current_step = 0
        self.cash = self.initial_balance
        self.portfolio_value = self.initial_balance
        
        # Tracks the actual stock tickers currently mapped to the 50 slots
        self.active_tickers = [] 
        # Tracks the number of shares owned for each ticker in the slots
        self.holdings = np.zeros(self.max_slots, dtype=np.float32)
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        self.current_step = 0
        self.cash = self.initial_balance
        self.portfolio_value = self.initial_balance
        self.holdings = np.zeros(self.max_slots, dtype=np.float32)
        
        obs = self._build_observation()
        
        return obs, {}



    def step(self, action):
        # 1. Apply Softmax to convert raw logits to target portfolio percentages
        exp_actions = np.exp(action - np.max(action)) # Subtract max for numerical stability
        target_weights = exp_actions / np.sum(exp_actions)
        
        target_cash_weight = target_weights[0]
        target_stock_weights = target_weights[1:]
        
        # 2. Get current prices for the actively mapped slots
        current_prices = self._get_current_prices(self.active_tickers)
        
        # Calculate current market value before trades
        stock_value = np.sum(self.holdings * current_prices)
        current_market_value = self.cash + stock_value # FIX: Renamed from self.portfolio_value
        
        # 3. Calculate target dollar allocations
        target_cash_dollars = current_market_value * target_cash_weight # FIX
        target_stock_dollars = current_market_value * target_stock_weights # FIX
        
        # 4. Execute Trades & Apply Friction
        # We calculate the difference between target dollars and current dollars for each slot
        current_stock_dollars = self.holdings * current_prices
        dollar_trades = target_stock_dollars - current_stock_dollars
        
        transaction_costs = 0.0
        
        for i in range(self.max_slots):
            if dollar_trades[i] != 0 and current_prices[i] > 0:
                # Basic spread/fee friction (You can implement the Square-Root law here later)
                cost = abs(dollar_trades[i]) * self.transaction_fee
                transaction_costs += cost
                
                # Update holdings
                self.holdings[i] = target_stock_dollars[i] / current_prices[i]
        
        # Update cash after trades and penalties
        self.cash = target_cash_dollars - transaction_costs
        
        # Recalculate true portfolio value post-friction
        new_portfolio_value = self.cash + np.sum(self.holdings * current_prices)
        
        # 5. Calculate Reward (Log Return)
        # FIX: Now correctly compares today's post-trade value against YESTERDAY'S value
        reward = np.log(new_portfolio_value / self.portfolio_value)
        self.portfolio_value = new_portfolio_value
        
        # 6. Advance Time
        self.current_step += 1
        done = self.current_step >= self.data_feed.max_steps
        
        # 7. Rebuild the Dynamic Slot Buffer for the next step
        obs = self._build_observation()
        
        info = {
            "portfolio_value": self.portfolio_value,
            "cash": self.cash,
            "transaction_costs": transaction_costs
        }
        
        return obs, reward, done, False, info


    def _build_observation(self):
        """
        Constructs the [50, N] observation matrix using Priority Slotting.
        Priority 1: Stocks currently owned.
        Priority 2: Top screener ideas for the current day.
        """
        obs = np.zeros((self.max_slots, self.num_features), dtype=np.float32)
        next_active_tickers = []
        next_holdings = np.zeros(self.max_slots, dtype=np.float32)
        
        slot_index = 0
        
        # -- PRIORITY 1: Map currently held positions --
        for i, ticker in enumerate(self.active_tickers):
            if self.holdings[i] > 0: # Agent owns shares
                next_active_tickers.append(ticker)
                next_holdings[slot_index] = self.holdings[i]
                
                # Fetch features from data pipeline
                features = self.data_feed.get_features(ticker, self.current_step)
                
                # Append the "Percent Owned" feature to the state
                pct_owned = (self.holdings[i] * features['price']) / self.portfolio_value
                obs[slot_index] = [
                    features['norm_price'], 
                    features['score'], 
                    features['confidence'], 
                    features['direction'], 
                    pct_owned
                ]
                slot_index += 1
                
        # -- PRIORITY 2: Fill remaining slots with new screener ideas --
        # Pull the day's top sorted stocks, excluding ones we already hold
        screener_candidates = self.data_feed.get_top_screener_stocks(self.current_step)
        
        for ticker in screener_candidates:
            if slot_index >= self.max_slots:
                break # Buffer is full
                
            if ticker not in next_active_tickers:
                next_active_tickers.append(ticker)
                
                features = self.data_feed.get_features(ticker, self.current_step)
                obs[slot_index] = [
                    features['norm_price'], 
                    features['score'], 
                    features['confidence'], 
                    features['direction'], 
                    0.0 # Percent owned is 0
                ]
                slot_index += 1
                
        # Update internal tracking arrays
        self.active_tickers = next_active_tickers
        self.holdings = next_holdings
        
        return obs
        
    def _get_current_prices(self, tickers):
        # Helper to extract an array of current prices for the active slots
        return np.array([self.data_feed.get_price(t, self.current_step) for t in tickers], dtype=np.float32)