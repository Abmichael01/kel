"""Record the trained cardboard quad walking: a GIF to watch + a frame-strip PNG.

    python record_quad.py

Saves quad_walk.gif (play it) and quad_walk_strip.png (6 stills across the run),
and prints how far it actually travelled forward.
"""

from __future__ import annotations

import os

os.environ.setdefault("MUJOCO_GL", "egl")

import numpy as np
from PIL import Image
from stable_baselines3 import PPO

import mujoco
from kel_quad_env import KelQuadEnv

STEPS = 400


def main() -> None:
    env = KelQuadEnv()
    model = PPO.load("quad_walk")
    obs, _ = env.reset(seed=2)

    renderer = mujoco.Renderer(env.model, height=360, width=480)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(env.model, cam)
    cam.azimuth, cam.elevation, cam.distance = 120, -12, 0.8

    frames = []
    survived = 0
    for _ in range(STEPS):
        action, _ = model.predict(obs, deterministic=True)
        obs, _reward, terminated, _trunc, _info = env.step(action)
        cam.lookat[:] = env.data.qpos[:3]  # keep the bot centred so we see the gait
        renderer.update_scene(env.data, cam)
        frames.append(renderer.render().copy())
        survived += 1
        if terminated:
            break

    distance = float(env.data.qpos[0])

    gif = [Image.fromarray(f) for f in frames]
    gif[0].save(
        "quad_walk.gif", save_all=True, append_images=gif[1::2], duration=50, loop=0
    )
    idx = np.linspace(0, len(frames) - 1, 6).astype(int)
    Image.fromarray(np.concatenate([frames[i] for i in idx], axis=1)).save("quad_walk_strip.png")

    print(f"forward distance: {distance:.2f} m over {survived} steps ({survived * env.dt:.1f}s)")
    print("saved quad_walk.gif and quad_walk_strip.png")


if __name__ == "__main__":
    main()
