"""Watch the walker in a MuJoCo window — the trained policy, or random flailing.

    python watch.py           # watch the trained policy walk (needs ant_walk.zip)
    python watch.py random    # watch an untrained random policy (before training)

Needs a display (your desktop), so run it on your own machine, not a headless box.
"""

from __future__ import annotations

import sys

import gymnasium as gym

POLICY_PATH = "ant_walk"


def main() -> None:
    random = len(sys.argv) > 1 and sys.argv[1] == "random"
    env = gym.make("Ant-v5", render_mode="human")

    model = None
    if not random:
        from stable_baselines3 import PPO

        model = PPO.load(POLICY_PATH)

    observation, _ = env.reset()
    while True:
        if model is None:
            action = env.action_space.sample()
        else:
            action, _ = model.predict(observation, deterministic=True)
        observation, _reward, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            observation, _ = env.reset()


if __name__ == "__main__":
    main()
