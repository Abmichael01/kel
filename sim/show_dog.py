"""Stand the real Unitree Go1 robot dog up in the MuJoCo viewer.

This is just to SEE the actual robot-dog body (not the generic Ant) in the sim.
It holds the model's 'home' standing pose with its position servos, so it stands
like the reference photo instead of collapsing under gravity. Training a walking
gait on this body is the next step.

    python show_dog.py       # needs a display
"""

from __future__ import annotations

import time

import mujoco
import mujoco.viewer

MODEL = "mujoco_menagerie/unitree_go1/scene.xml"


def main() -> None:
    model = mujoco.MjModel.from_xml_path(MODEL)
    data = mujoco.MjData(model)

    # Reset to the 'home' standing keyframe and hold that pose with the servos.
    home_ctrl = None
    if model.nkey > 0:
        home = model.key("home").id
        mujoco.mj_resetDataKeyframe(model, data, home)
        home_ctrl = model.key_ctrl[home].copy()

    with mujoco.viewer.launch_passive(model, data) as viewer:
        # Frame the dog instead of staring at empty floor.
        viewer.cam.lookat[:] = [0.0, 0.0, 0.28]
        viewer.cam.distance = 1.6
        viewer.cam.azimuth = 120
        viewer.cam.elevation = -15
        while viewer.is_running():
            if home_ctrl is not None:
                data.ctrl[:] = home_ctrl  # servos keep it standing
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(0.002)


if __name__ == "__main__":
    main()
