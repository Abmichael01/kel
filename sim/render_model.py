"""Render any MuJoCo model in its home pose to an image (offscreen, no window).

    python render_model.py kel_quad.xml quad.png
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("MUJOCO_GL", "egl")

import numpy as np
from PIL import Image

import mujoco

model_path = sys.argv[1] if len(sys.argv) > 1 else "kel_quad.xml"
out_path = sys.argv[2] if len(sys.argv) > 2 else "render.png"


def main() -> None:
    model = mujoco.MjModel.from_xml_path(model_path)
    data = mujoco.MjData(model)
    if model.nkey > 0:
        mujoco.mj_resetDataKeyframe(model, data, 0)  # the 'home' keyframe
    # let it settle onto its feet for a moment so the stance is real, not floating
    for _ in range(200):
        mujoco.mj_step(model, data)

    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)  # auto-frames whatever the model's size is
    cam.azimuth = 130
    cam.elevation = -20

    with mujoco.Renderer(model, height=480, width=640) as renderer:
        renderer.update_scene(data, cam)
        image: np.ndarray = renderer.render()

    Image.fromarray(image).save(out_path)
    print(f"saved {out_path} {image.shape}; torso height after settling: {data.qpos[2]:.3f} m")


if __name__ == "__main__":
    main()
