from simulation import DynamicSlotTradingEnv
from data_management import StockDataFeed
import numpy as np

from agent import Agent

BASE_DIR = "backend\\models\\reinforcement-learning"
NUM_EPISODES = 500
FIGURE_FILE = BASE_DIR + "\\output\\plots\\plot.png"
N = 20

feed = StockDataFeed(BASE_DIR + "\\data\\master_feed.parquet")

env = DynamicSlotTradingEnv(data_feed=feed, initial_balance=10000.0)

agent = Agent(input_dim=250, n_actions=51, N=N) # TODO: env.observation_space.shape?

best_score = -10000 # env.reward_range[0]??
score_history = []
learn_iters = 0
n_steps = 0

for episode in range(NUM_EPISODES):
    done = False
    obs, _ = env.reset()
    score = 0

    while not done:
        action, prob, val = agent.choose_actions(obs) #env.action_space.sample()  # Replace with agent's action
        obs_, reward, done, truncated, info = env.step(action)
        n_steps += 1
        score += reward
        agent.remember(obs, action, prob, val, reward, done)
        if n_steps % N == 0:
            agent.learn()
            learn_iters += 1
        obs = obs_
        # print(f"Step: {env.current_step}, Reward: {reward:.2f}, Portfolio Value: {env.portfolio_value:.2f}")
    score_history.append(score)
    avg_score = np.mean(score_history[-100:])

    if avg_score > best_score:
        best_score = avg_score
        agent.save_models()

    print('episode', episode, 'score %.1f' % score, 'avg score %.1f' % avg_score,
          'time_steps', n_steps, 'learning_steps', learn_iters)
    
    #print(f"Episode {episode + 1} Complete. Final Portfolio: ${info['portfolio_value']:.2f}\n")