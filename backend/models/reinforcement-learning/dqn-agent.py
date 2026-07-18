import torch
from torch import nn
import numpy as np

from tensordict import TensorDict
from torchrl.data import TensorDictReplayBuffer, LazyMemmapStorage

class AgentNN(nn.Module):
    def __init__(self, input_size, n_actions, freeze=False):
        super().__init__()

        self.network = nn.Sequential(
            nn.Flatten(), # TODO: Needed?
            nn.Linear(input_size, 512),
            nn.ReLU(),
            nn.Linear(512, n_actions)
        )

        if freeze:
            self._freeze()

        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.to(self.device)


    def _freeze(self):
        for p in self.network.parameters():
            p.requires_grad = False

    def forward(self, x):
        return self.network(x)
    

class Agent:
    def __init__(self, input_dims, num_actions):
        self.num_actions = num_actions
        self.learn_step_counter = 0

        # Hyperparameters
        self.lr = 0.00025
        self.gamma = 0.9
        self.epsilon = 1.0
        self.eps_decay = 0.99999975
        self.eps_min = 0.1
        self.batch_size = 32
        self.sync_network_rate = 10_000

        # Networks
        self.online_network = AgentNN(input_dims, num_actions)
        self.target_network = AgentNN(input_dims, num_actions, freeze=True)

        # Optimizer and loss
        self.optimizer = torch.optim.Adam(self.online_network.parameters(), lr=self.lr)
        self.loss = torch.nn.MSELoss()

        # Replay buffer
        replay_buffer_capacity = 100_000
        storage = LazyMemmapStorage(replay_buffer_capacity)
        self.replay_bufffer = TensorDictReplayBuffer(storage=storage)


    def choose_actions(self, observation):
        if np.random.random() < self.epsilon:
            return np.random.uniform(-5.0, 5.0, size=(self.num_actions,))
        observation = torch.tensor(np.array(observation), dtype=torch.float32) \
                            .unsqueeze(0) \
                            .to(self.online_network.device)
        return self.online_network(observation).squeeze().detach().cpu().numpy()

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon * self.eps_decay, self.eps_min)
    
    def store_in_memory(self, state, action, reward, next_state, done):
        self.replay_bufffer.add(TensorDict({
            "state": torch.tensor(np.array(state), dtype=torch.float32),
            "action": torch.tensor(action),
            "reward": torch.tensor(reward),
            "next_state": torch.tensor(np.array(next_state), dtype=torch.float32),
            "done": torch.tensor(done)
        }, batch_size=[]))

    def sync_networks(self):
        if self.learn_step_counter % self.sync_network_rate == 0 and self.learn_step_counter > 0:
            self.target_network.load_state_dict(self.online_network.state_dict())

    def learn(self):
        if len(self.replay_buffer) < self.batch_size:
            return
        
        self.sync_networks()

        self.optimizer.zero_grad()

        samples = self.replay_bufffer.sample(self.batch_size).to(self.online_network.device)

        keys = ("state", "action", "reward", "next_state", "done")

        states, actions, rewards, next_states, dones = [samples[key] for key in keys]

        predicted_q_values = self.online_network(states)
        predicted_q_values = predicted_q_values[np.arange(self.batch_size), actions.squeeze()]

        target_q_values = self.target_network(next_states).max(dim=1)[0]
        target_q_values = rewards + self.gamma * target_q_values * (1 - dones.float())

        loss = self.loss(predicted_q_values, target_q_values)
        loss.backward()
        self.optimizer.step()
        
        self.learn_step_counter += 1
        self.decay_epsilon()