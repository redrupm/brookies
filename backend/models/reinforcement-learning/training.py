from simulation import DynamicSlotTradingEnv
from data_management import StockDataFeed

feed = StockDataFeed("master_feed.parquet")

env = DynamicSlotTradingEnv(data_feed=feed, initial_balance=10000.0)

done = False
obs, _ = env.reset()

while not done:
    action = env.action_space.sample()  # Replace with agent's action
    obs, reward, done, info = env.step(action)
    print(f"Step: {env.current_step}, Reward: {reward:.2f}, Portfolio Value: {env.portfolio_value:.2f}")