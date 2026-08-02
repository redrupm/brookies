from simulation import DynamicSlotTradingEnv
from data_management import StockDataFeed
import numpy as np
from constants import *

from agent import Agent

NUM_EPISODES = 500
N = 1024
BATCH_SIZE = 128

feed = StockDataFeed(DATA_DIR + "master_feed.parquet")

env = DynamicSlotTradingEnv(data_feed=feed, initial_balance=10000.0)

agent = Agent(input_dim=250, n_actions=51, N=N, batch_size=BATCH_SIZE) # TODO: env.observation_space.shape?

best_score = -10000 # env.reward_range[0]??
score_history = []
best_final_portfolio = -100000000
final_portfolio_history = []
learn_iters = 0
n_steps = 0

for episode in range(NUM_EPISODES):
    done = False
    obs, _ = env.reset()
    score = 0

    while not done:
        action, prob, val = agent.choose_actions(obs)
        obs_, reward, done, truncated, info = env.step(action)
        n_steps += 1
        reward = reward * 100 # Gemini suggested
        score += reward
        agent.remember(obs, action, prob, val, reward, done)
        if n_steps % N == 0:
            agent.learn()
            learn_iters += 1
        obs = obs_
        if done:
            final_portfolio_history.append(info["portfolio_value"])
    score_history.append(score)
    avg_score = np.mean(score_history[-100:])
    avg_final_portfolio = np.mean(final_portfolio_history[-100:])

    if avg_score > best_score:
        best_score = avg_score
        agent.save_models()

    if avg_final_portfolio > best_final_portfolio:
        best_final_portfolio = avg_final_portfolio

    print('episode', episode, 'score %.3f' % score, 'avg score %.3f' % avg_score, 'portfolio %.3f' % final_portfolio_history[-1], 'avg final portfolio %.3f' % avg_final_portfolio,
          'time_steps', n_steps, 'learning_steps', learn_iters)
print([float(i) for i in score_history])
print([float(i) for i in final_portfolio_history])