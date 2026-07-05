"""Render the Unitree Go1 standing in its home pose to an image (offscreen).

No window — just writes dog_render.png so we can look at the actual robot-dog
body in the sim before training a gait on it.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

import mujoco

MODEL = "mujoco_menagerie/unitree_go1/scene.xml"


def main() -> None:
    model = mujoco.MjModel.from_xml_path(MODEL)
    data = mujoco.MjData(model)
    if model.nkey > 0:
        mujoco.mj_resetDataKeyframe(model, data, model.key("home").id)
    mujoco.mj_forward(model, data)

    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    cam.lookat[:] = [0.0, 0.0, 0.26]
    cam.distance = 1.4
    cam.azimuth = 130
    cam.elevation = -20

    with mujoco.Renderer(model, height=480, width=640) as renderer:
        renderer.update_scene(data, cam)
        image: np.ndarray = renderer.render()

    Image.fromarray(image).save("dog_render.png")
    print("saved dog_render.png", image.shape)


if __name__ == "__main__":
    main()
