"""Train a 4-legged walker (MuJoCo's Ant) to walk, with PPO, then save the policy.

This is milestone 1: watch an AI learn to walk from a plain reward (move forward,
stay upright) — no dataset, no hardware. Ant is a ready-made quadruped with two
joints per leg, the same shape we recommend for Kel's first legged body.

Run it (on a machine where you can spare ~an hour of CPU):

    cd sim
    uv venv && source .venv/bin/activate
    uv pip install -r requirements.txt
    python train.py

Then watch the result with:  python watch.py
"""

from __future__ import annotations

import sys

import gymnasium as gym
from stable_baselines3 import PPO

DEFAULT_TIMESTEPS = 1_000_000  # ~an hour on CPU; the gait emerges well before the end
POLICY_PATH = "ant_walk"


def main() -> None:
    # Optional: `python train.py 400000` for a quicker, rougher first gait.
    timesteps = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TIMESTEPS
    env = gym.make("Ant-v5")
    model = PPO("MlpPolicy", env, verbose=1, device="cpu")
    print(f"Training for {timesteps:,} steps — watch 'ep_rew_mean' climb as it learns to move.")
    model.learn(total_timesteps=timesteps)
    model.save(POLICY_PATH)
    print(f"\nDone. Saved the walking policy to {POLICY_PATH}.zip — now run: python watch.py")


if __name__ == "__main__":
    main()
