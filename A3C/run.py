import gym
import agent
import model
import os
import tensorflow as tf
import numpy as np
import click
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from time import time, sleep
from tqdm import tqdm
from queue import Queue


@click.command()
@click.option('--env_name', type=str, default='CartPole-v1')
@click.option('--num_workers', type=int, default=1)
@click.option('--max_episodes', type=int, default=100)
@click.option('--learning_rate', type=float, default=10e-4)
@click.option('--network_update_frequency', type=int, default=50)
@click.option('--entropy_coefficient', type=float, default=0.01)
@click.option('--norm_clip_value', type=float, default=None)
@click.option('--num_checkpoints', type=int, default=10)
@click.option('--model_directory', type=click.Path(), default="")
@click.option('--test_model', type=bool, default=True)
@click.option('--test_episodes', type=int, default=100)
@click.option('--render_testing', type=bool, default=False)
@click.option('--random_seed', type=int, default=None)
@click.option('--save', type=bool, default=True)
def run_training(
        env_name,
        num_workers,
        max_episodes,
        learning_rate,
        network_update_frequency,
        entropy_coefficient,
        norm_clip_value,
        num_checkpoints,
        model_directory,
        test_model,
        test_episodes,
        render_testing,
        random_seed,
        save):
    env = gym.make(env_name)
    state_space = env.observation_space.shape[0]
    action_space = env.action_space.n

    if random_seed is not None:
        tf.random.set_seed(random_seed)
        np.random.seed(random_seed)

    global_network = model.A3CNetwork(
        state_space=state_space,
        action_space=action_space,
        entropy_coefficient=entropy_coefficient
    )

    if not model_directory:
        model_directory = os.path.join(
            "./experiment/",
            f"{env_name}_{datetime.now()}"
        )
    if save:
        os.makedirs(model_directory, exist_ok=True)

    reward_queue = Queue()
    optimizer = tf.optimizers.Adam(learning_rate=learning_rate)
    workers = [
        agent.Worker(
            worker_index,
            global_network,
            env_name,
            random_seed,
            max_episodes,
            optimizer,
            network_update_frequency,
            entropy_coefficient, 
            norm_clip_value,
            num_checkpoints,
            reward_queue,
            model_directory,
            save
        ) for worker_index in range(num_workers)
    ]
    start_time = time()
    for worker in workers:
        print(f"Starting Worker: {worker.name}")
        worker.start()

    moving_average_rewards = []
    while True:
        reward = reward_queue.get()
        if reward is not None:
            moving_average_rewards.append(reward)
        else:
            break

    for worker in workers:
        worker.join()

    end_time = time()
    time_taken = end_time - start_time

    if save:
        write_summary(model_directory,
                      num_workers,
                      max_episodes,
                      learning_rate,
                      network_update_frequency,
                      entropy_coefficient,
                      norm_clip_value,
                      time_taken,
                      random_seed,
                      global_network,
                      filename="summary.txt")
        plt.plot(moving_average_rewards)
        plt.ylabel('Moving average reward')
        plt.xlabel('Episode')
        plt.savefig(os.path.join(model_directory, 'Moving_Average.png'))

        if test_model:
            test_dir = os.path.join(model_directory, "test")
            os.makedirs(test_dir)
            print("Running tests with checkpoint policies...")
            for checkpoint in tqdm(range(num_checkpoints + 1)):
                if checkpoint == num_checkpoints:
                    checkpoint = "best"

                model_file_path = os.path.join(
                    model_directory,
                    f"checkpoint_{checkpoint}.h5"
                )
                if not os.path.exists(model_file_path):
                    break

                test_file_path = os.path.join(
                    test_dir,
                    f"test_checkpoint_{checkpoint}.txt"
                )

                run_testing(
                    env_name,
                    test_episodes,
                    model_file_path,
                    test_file_path,
                    render_testing
                )


def run_testing(
        env_name,
        max_episodes,
        model_file,
        test_file_name,
        render):

    env = gym.make(env_name)
    state_space = env.observation_space.shape[0]
    action_space = env.action_space.n
    global_network = model.A3CNetwork(
        state_space=state_space,
        action_space=action_space
    )

    global_network.load_weights(
        model_file
    )

    worker = agent.TestWorker(
        global_network,
        env_name,
        max_episodes,
        test_file_name,
        render=render
    )
    worker.start()
    worker.join()


def write_summary(
        model_directory,
        num_workers,
        max_episodes,
        learning_rate,
        network_update_frequency,
        entropy_coefficient,
        norm_clip_value,
        time_taken,
        random_seed,
        global_network,
        filename="summary.txt"):
    filepath = os.path.join(model_directory, filename)
    with open(filepath, "w+") as fp:
        fp.write("Number of Workers:".ljust(35) + f"{num_workers}\n")
        fp.write("Training Episodes:".ljust(35) + f"{max_episodes}\n")
        fp.write("Learning Rate:".ljust(35) + f"{learning_rate}\n")
        fp.write("Network Update Frequency:".ljust(35) + f"{network_update_frequency}\n")
        fp.write("Entropy Coefficient:".ljust(35) + f"{entropy_coefficient}\n")
        fp.write("Norm Clip Value:".ljust(35) + f"{norm_clip_value}\n")
        fp.write("Time Taken:".ljust(35) + f"{time_taken}\n")
        fp.write("Formatted Time:".ljust(35) + f"{timedelta(seconds=time_taken)}\n")
        fp.write("Random Seed:".ljust(35) + f"{random_seed}\n")
        fp.write("Network Architecture:\n")
        global_network.summary(print_fn=lambda summ: fp.write(summ + "\n"))


if __name__ == "__main__":
    run_training()


