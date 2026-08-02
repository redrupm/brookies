import os
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

class PPOMemory:
    def __init__(self, batch_size):
        self.states = []
        self.probs = []
        self.vals = []
        self.actions = []
        self.rewards = []
        self.dones = []

        self.batch_size = batch_size

    def generate_batches(self):
        n_states = len(self.states)
        batch_start = np.arange(0, n_states, self.batch_size)
        indices = np.arange(n_states, dtype=np.int64)
        np.random.shuffle(indices)
        batches = [indices[i : i + self.batch_size] for i in batch_start]
        
        return (np.array(self.states),
                np.array(self.actions),
                np.array(self.probs),
                np.array(self.vals),
                np.array(self.rewards),
                np.array(self.dones),
                batches
        )
    
    def store_memory(self, state, action, probs, vals, reward, done):
        self.states.append(state)
        self.actions.append(action)
        self.probs.append(probs)
        self.vals.append(vals)
        self.rewards.append(reward)
        self.dones.append(done)

    def clear_memory(self):
        self.states = []
        self.probs = []
        self.vals = []
        self.actions = []
        self.rewards = []
        self.dones = []

class ActorNetwork(nn.Module):
    def __init__(self, n_actions, input_dim, alpha,
                fc1_dims=256, fc2_dims=246,
                chkpt_dir='backend\\models\\reinforcement-learning\\models'):
        super(ActorNetwork, self).__init__()

        self.checkpoint_file = os.path.join(chkpt_dir, 'actor_torch_ppo')

        self.embedding = nn.Linear(5, 64)
        
        self.attention = nn.TransformerEncoderLayer(
            d_model=64, 
            nhead=4, 
            dim_feedforward=128, 
            batch_first=True
        )
        
        # Output the final logit for the stock based on its contextualized data
        self.logit_head = nn.Linear(64, 1)

        # Standalone learnable logit for the "Cash" position
        self.cash_logit = nn.Parameter(torch.zeros(1))

        self.action_std = nn.Parameter(torch.full((n_actions,), -1.5))

        self.optimizer = optim.Adam(self.parameters(), lr=alpha)
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        self.to(self.device)

    def forward(self, state):
        # state shape: [batch_size, 50, 5]
        
        x = self.embedding(state)    # shape: [batch_size, 50, 64]
        x = self.attention(x)        # shape: [batch_size, 50, 64] (Now context-aware!)
        
        stock_logits = self.logit_head(x).squeeze(-1) # shape: [batch_size, 50]
        
        batch_size = state.shape[0]
        cash_logits = self.cash_logit.expand(batch_size, 1)
        
        action_mean = torch.cat([cash_logits, stock_logits], dim=-1)
        
        action_var = self.action_std.exp().expand_as(action_mean)
        dist = Normal(action_mean, action_var)

        return dist
    
    def save_checkpoint(self):
        torch.save(self.state_dict(), self.checkpoint_file)

    def load_checkpoint(self):
        self.load_state_dict(torch.load(self.checkpoint_file))


class CriticNetwork(nn.Module):
    def __init__(self, input_dim, alpha,
                fc1_dims=256, fc2_dims=246,
                chkpt_dir='backend\\models\\reinforcement-learning\\models'):
        super(CriticNetwork, self).__init__()

        self.checkpoint_file = os.path.join(chkpt_dir, 'critic_torch_ppo')

        self.embedding = nn.Linear(5, 64)
        
        self.attention = nn.TransformerEncoderLayer(
            d_model=64, 
            nhead=4, 
            dim_feedforward=128, 
            batch_first=True
        )
        
        # After understanding the whole market, it boils it down to 1 dollar value estimate
        self.value_head = nn.Sequential(
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )

        self.optimizer = optim.Adam(self.parameters(), lr=alpha)
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        self.to(self.device)

    def forward(self, state):
        # state shape: [batch_size, 50, 5]
        x = self.embedding(state)
        x = self.attention(x)
        
        # Mean Pooling: Average the context of all 50 stocks into a single global market view
        global_context = x.mean(dim=1) # shape: [batch_size, 64]
        
        value = self.value_head(global_context)
        return value
    
    def save_checkpoint(self):
        torch.save(self.state_dict(), self.checkpoint_file)

    def load_checkpoint(self):
        self.load_state_dict(torch.load(self.checkpoint_file))


class Agent:
    def __init__(self, input_dim, n_actions, gamma=0.99, alpha=0.0003, gae_lambda=0.95,
                 policy_clip=0.2, batch_size=64, N=2048, n_epochs=10):
        # N= horizon. The number of steps before update?
        # TODO: N is never used?
        self.gamma = gamma
        self.policy_clip = policy_clip
        self.n_epochs = n_epochs
        self.gae_lambda = gae_lambda

        self.actor = ActorNetwork(n_actions, input_dim, alpha)
        self.critic = CriticNetwork(input_dim, alpha)
        self.memory = PPOMemory(batch_size)

    def remember(self, state, action, probs, vals, reward, done):
        self.memory.store_memory(state, action, probs, vals, reward, done)

    def save_models(self):
        print('... saving models ...')
        self.actor.save_checkpoint()
        self.critic.save_checkpoint()
    
    def load_models(self):
        print('... loading models ...')
        self.actor.load_checkpoint()
        self.critic.load_checkpoint()

    def choose_actions(self, observation, explore=True):
        state = torch.tensor([observation], dtype=torch.float).to(self.actor.device)

        dist = self.actor(state)
        value = self.critic(state)
        
        if explore:
            # Stochastic: Pick a random point under the bell curve
            action = dist.sample()
        else:
            # Deterministic: Take the exact center of the bell curve (the network's raw prediction)
            action = dist.mean 

        probs = torch.squeeze(dist.log_prob(action).sum(dim=-1)).item()
        action = torch.squeeze(action).detach().cpu().numpy()
        value = torch.squeeze(value).item()

        return action, probs, value
    
    def learn(self):
        for _ in range(self.n_epochs):
            state_arr, action_arr, old_probs_arr, vals_arr,\
            reward_arr, dones_arr, batches = self.memory.generate_batches()

            values = vals_arr
            advantage = np.zeros(len(reward_arr), dtype=np.float32)
             
            for t in range(len(reward_arr) - 1):
                discount = 1
                advantage_at_timestep = 0
                for k in range(t, len(reward_arr) - 1):
                    delta_t = reward_arr[k] + self.gamma * values[k + 1] * (1 - int(dones_arr[k])) - values[k]
                    advantage_at_timestep += discount * delta_t
                    discount *= self.gamma * self.gae_lambda
                advantage[t] = advantage_at_timestep
            advantage = torch.tensor(advantage).to(self.actor.device)

            values = torch.tensor(values).to(self.actor.device)
            # TODO: something about vals array is inefficient?
            for batch in batches:
                states = torch.tensor(state_arr[batch], dtype=torch.float).to(self.actor.device)
                old_probs = torch.tensor(old_probs_arr[batch]).to(self.actor.device)
                actions = torch.tensor(action_arr[batch]).to(self.actor.device)

                dist = self.actor(states)
                critc_value = self.critic(states)

                critic_value = torch.squeeze(critc_value)

                new_probs = dist.log_prob(actions).sum(dim=-1)
                prob_ratio = (new_probs - old_probs).exp()
                weighted_probs = advantage[batch] * prob_ratio
                weighted_clipped_probs = torch.clamp(prob_ratio, 1 - self.policy_clip,
                                                     1 + self.policy_clip) * advantage[batch]
                actor_loss = -torch.min(weighted_probs, weighted_clipped_probs).mean()

                returns = advantage[batch] + values[batch]
                critic_loss = (returns - critic_value)**2
                critic_loss = critic_loss.mean()

                total_loss = actor_loss + 0.5*critic_loss
                self.actor.optimizer.zero_grad()
                self.critic.optimizer.zero_grad()
                total_loss.backward()
                self.actor.optimizer.step()
                self.critic.optimizer.step()
        self.memory.clear_memory()
