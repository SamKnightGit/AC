import tensorflow as tf
import numpy as np
from tensorflow.keras import layers, initializers
from collections import deque


class A2CNetwork(tf.keras.Model):
    def __init__(self, state_space, action_space, value_weight=0.5, entropy_coefficient=0.01, clip_range=0.2):
        super(A2CNetwork, self).__init__()
        self.state_space = state_space
        self.action_space = action_space
        self.value_weight = value_weight
        self.entropy_coefficient = entropy_coefficient
        self.clip_range = clip_range

        # self.dense_shared_1 = layers.Dense(100, activation='relu')
        self.dense_value_hidden = layers.Dense(100, activation='relu', input_dim=self.state_space,
                                               kernel_initializer=initializers.glorot_uniform)
        self.dense_critic_hidden = layers.Dense(100, activation='relu', input_dim=self.state_space,
                                                kernel_initializer=initializers.glorot_uniform)
        self.policy = layers.Dense(self.action_space, activation=tf.nn.softmax,
                                   kernel_initializer=initializers.glorot_uniform)
        self.value = layers.Dense(1, kernel_initializer=initializers.glorot_uniform)
        # Initialize network weights with random input
        self(tf.convert_to_tensor(np.random.random((1, self.state_space)), dtype=tf.float32))

    def call(self, inputs):
        policy_output = self.dense_critic_hidden(inputs)
        policy = self.policy(policy_output)

        value_output = self.dense_value_hidden(inputs)
        value = self.value(value_output)

        return policy, value

    def get_loss(self, done, new_state, history, discount_factor=0.99):
        if done:
            estimated_reward = 0
        else:
            _, estimated_reward = self(tf.convert_to_tensor(new_state[None, :], dtype=tf.float32))

        all_discounted_rewards = deque()
        for reward in history.rewards[::-1]:
            discounted_reward = estimated_reward * discount_factor
            discounted_reward += reward
            all_discounted_rewards.appendleft(discounted_reward)

        action_one_hot = tf.one_hot(history.actions, self.action_space, 1.0, 0.0)

        policy, values = self(tf.convert_to_tensor(np.vstack(history.states), dtype=tf.float32))

        advantage = tf.convert_to_tensor(np.array(all_discounted_rewards)[:, None], dtype=tf.float32) - values

        value_loss_unclipped = tf.square(advantage)
        value_loss_clipped = tf.square(
            history.values + tf.clip_by_value(values - history.values, -self.clip_range, self.clip_range)
        )

        value_loss = tf.reduce_mean(tf.maximum(value_loss_clipped, value_loss_unclipped))

        log_policy = tf.math.log(tf.clip_by_value(policy, 0.000001, 0.999999))
        log_policy_given_action = tf.reduce_sum(tf.multiply(log_policy, action_one_hot))

        log_old_policy = tf.math.log(tf.clip_by_value(history.policy, 0.000001, 0.999999))
        log_old_policy_given_action = tf.reduce_sum(tf.multiply(log_old_policy, action_one_hot))

        policy_ratio = tf.exp(log_policy_given_action - log_old_policy_given_action)

        policy_loss_unclipped = -advantage * policy_ratio
        policy_loss_clipped = -advantage * tf.clip_by_value(policy_ratio, 1.0 - self.clip_range, 1.0 + self.clip_range)
        policy_loss = tf.reduce_mean(tf.maximum(policy_loss_unclipped, policy_loss_clipped))

        entropy = tf.reduce_sum(tf.multiply(policy, -log_policy))

        total_loss = policy_loss + self.value_weight * value_loss - entropy * self.entropy_coefficient
        return total_loss
