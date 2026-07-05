"""Train the cardboard quad to walk with PPO, then save the policy.

    python train_quad.py            # 800k steps (default)
    python train_quad.py 400000     # quicker, rougher
"""

from __future__ import annotations

import sys

from stable_baselines3 import PPO

from kel_quad_env import KelQuadEnv

POLICY_PATH = "quad_walk"


def main() -> None:
    timesteps = int(sys.argv[1]) if len(sys.argv) > 1 else 800_000
    env = KelQuadEnv()
    model = PPO("MlpPolicy", env, verbose=1, device="cpu")
    print(f"Teaching the cardboard quad to walk for {timesteps:,} steps...")
    model.learn(total_timesteps=timesteps)
    model.save(POLICY_PATH)
    print(f"Done. Saved {POLICY_PATH}.zip")


if __name__ == "__main__":
    main()
