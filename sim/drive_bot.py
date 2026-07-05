"""Drive wheeled Kel around a little and look around, then record it.

No learning needed - the wheels just take speed commands and the head takes angle
commands. This is exactly how Kel/Gemini would drive her in real life.

    python drive_bot.py   # writes bot_drive.gif + bot_drive_strip.png
"""

from __future__ import annotations

import os

os.environ.setdefault("MUJOCO_GL", "egl")

import numpy as np
from PIL import Image

import mujoco

MODEL = "kel_bot.xml"


def main() -> None:
    model = mujoco.MjModel.from_xml_path(MODEL)
    data = mujoco.MjData(model)
    lw = model.actuator("left_wheel").id
    rw = model.actuator("right_wheel").id
    pan = model.actuator("head_pan").id
    tilt = model.actuator("head_tilt").id

    # a little tour: (steps, left_wheel_speed, right_wheel_speed)
    routine = [
        (150, 16, 16),    # drive forward
        (90, 15, 5),      # curve to the right
        (150, 16, 16),    # forward
        (110, -11, 11),   # spin left in place
        (150, 16, 16),    # forward again
        (70, 0, 0),       # stop and just look around
    ]
    commands = [(left, right) for steps, left, right in routine for _ in range(steps)]

    renderer = mujoco.Renderer(model, height=480, width=640)
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.distance, cam.azimuth, cam.elevation = 0.7, 140, -22

    frames = []
    prev = data.qpos[:2].copy()
    path = 0.0
    for i, (left, right) in enumerate(commands):
        data.ctrl[lw] = left
        data.ctrl[rw] = right
        data.ctrl[pan] = 0.8 * np.sin(i * 0.04)  # sweep the head left/right
        data.ctrl[tilt] = 0.2 * np.sin(i * 0.025)  # gentle up/down
        mujoco.mj_step(model, data)
        path += float(np.linalg.norm(data.qpos[:2] - prev))
        prev = data.qpos[:2].copy()
        if i % 2 == 0:
            cam.lookat[:] = data.body("chassis").xpos  # keep her in frame as she drives
            renderer.update_scene(data, cam)
            frames.append(renderer.render().copy())

    gif = [Image.fromarray(f) for f in frames]
    gif[0].save("bot_drive.gif", save_all=True, append_images=gif[1:], duration=40, loop=0)
    idx = np.linspace(0, len(frames) - 1, 6).astype(int)
    Image.fromarray(np.concatenate([frames[i] for i in idx], axis=1)).save("bot_drive_strip.png")
    print(f"drove {path:.2f} m of ground; saved bot_drive.gif + bot_drive_strip.png")


if __name__ == "__main__":
    main()
