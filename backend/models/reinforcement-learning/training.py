from simulation import DynamicSlotTradingEnv
from data_management import StockDataFeed

from agent import Agent

feed = StockDataFeed("master_feed.parquet")

env = DynamicSlotTradingEnv(data_feed=feed, initial_balance=10000.0)

agent = Agent(5, 51) # TODO: pick actual values

done = False
obs, _ = env.reset()

while not done:
    action = agent.choose_action(obs) #env.action_space.sample()  # Replace with agent's action
    obs, reward, done, info = env.step(action)
    print(f"Step: {env.current_step}, Reward: {reward:.2f}, Portfolio Value: {env.portfolio_value:.2f}")