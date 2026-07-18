from simulation import DynamicSlotTradingEnv
from data_management import StockDataFeed

from agent import Agent

feed = StockDataFeed("backend\\models\\reinforcement-learning\\data\\master_feed.parquet")

env = DynamicSlotTradingEnv(data_feed=feed, initial_balance=10000.0)

agent = Agent(250, 51)

NUM_EPISODES = 500

for episode in range(NUM_EPISODES):
    done = False
    obs, _ = env.reset()

    while not done:
        action = agent.choose_actions(obs) #env.action_space.sample()  # Replace with agent's action
        obs, reward, done, truncated, info = env.step(action)
        # print(f"Step: {env.current_step}, Reward: {reward:.2f}, Portfolio Value: {env.portfolio_value:.2f}")
    print(f"Episode {episode + 1} Complete. Final Portfolio: ${info['portfolio_value']:.2f}\n")