"""Watch the cardboard quad move in a live MuJoCo window (camera follows it).

    python watch_quad.py           # the trained policy (needs quad_walk.zip)
    python watch_quad.py random    # the untrained random brain

Needs a display, so run it on your own desktop.
"""

from __future__ import annotations

import sys
import time

import mujoco
import mujoco.viewer

from kel_quad_env import KelQuadEnv


def main() -> None:
    use_random = len(sys.argv) > 1 and sys.argv[1] == "random"
    env = KelQuadEnv()

    model = None
    if not use_random:
        from stable_baselines3 import PPO

        model = PPO.load("quad_walk")

    obs, _ = env.reset(seed=2)
    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        viewer.cam.azimuth, viewer.cam.elevation, viewer.cam.distance = 120, -12, 0.9
        while viewer.is_running():
            if model is None:
                action = env.action_space.sample()
            else:
                action, _ = model.predict(obs, deterministic=True)
            obs, _r, terminated, truncated, _i = env.step(action)
            viewer.cam.lookat[:] = env.data.qpos[:3]  # keep the bot centred as it moves
            viewer.sync()
            time.sleep(0.01)
            if terminated or truncated:
                obs, _ = env.reset(seed=1)


if __name__ == "__main__":
    main()
