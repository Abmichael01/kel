"""A Gymnasium environment that teaches the cardboard quad to walk forward.

Reward = go forward + stay upright - thrash the servos. The action is the 8 servo
targets (normalized to [-1, 1]); the SG-90 force limits live in the model, so a
learned gait is one the real cardboard build could actually do.
"""

from __future__ import annotations

import os

import numpy as np
from gymnasium import utils
from gymnasium.envs.mujoco import MujocoEnv
from gymnasium.spaces import Box

_XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kel_quad.xml")

# joint order: fl_hip, fl_knee, fr_hip, fr_knee, bl_hip, bl_knee, br_hip, br_knee
_LOW = np.array([-0.9, -0.3, -0.9, -0.3, -0.9, -0.3, -0.9, -0.3])
_HIGH = np.array([0.9, 1.6, 0.9, 1.6, 0.9, 1.6, 0.9, 1.6])


class KelQuadEnv(MujocoEnv, utils.EzPickle):
    metadata = {"render_modes": ["human", "rgb_array", "depth_array"], "render_fps": 40}

    def __init__(self, **kwargs):
        observation_space = Box(low=-np.inf, high=np.inf, shape=(27,), dtype=np.float64)
        MujocoEnv.__init__(self, _XML, 5, observation_space=observation_space, **kwargs)
        utils.EzPickle.__init__(self, **kwargs)
        # symmetric actions are kinder to PPO; we scale them to the real joint ranges
        self.action_space = Box(low=-1.0, high=1.0, shape=(8,), dtype=np.float32)

    def _scale(self, action):
        action = np.clip(action, -1.0, 1.0)
        return _LOW + (action + 1.0) * 0.5 * (_HIGH - _LOW)

    def _get_obs(self):
        q = self.data.qpos
        v = self.data.qvel
        return np.concatenate(
            [[q[2]], q[3:7], v[0:3], v[3:6], q[7:], v[6:]]
        ).astype(np.float64)

    def _up_z(self) -> float:
        # z-component of the torso's up axis: 1 = level, < 0 = flipped over
        _w, x, y, _z = self.data.qpos[3:7]
        return 1.0 - 2.0 * (x * x + y * y)

    def step(self, action):
        x_before = self.data.qpos[0]
        self.do_simulation(self._scale(action), self.frame_skip)
        x_after = self.data.qpos[0]

        forward = (x_after - x_before) / self.dt
        height = float(self.data.qpos[2])
        healthy = (0.04 < height < 0.20) and self._up_z() > 0.4

        # Forward speed is the ONLY real payoff now, so it can't game a survival bonus by
        # standing still. The tiny +0.02 keeps it from diving to end the episode; the ctrl
        # cost discourages thrashing/sliding. Standing still now scores ~0; walking scores big.
        reward = 3.0 * forward + 0.02 - 0.001 * float(np.square(action).sum())
        terminated = not healthy
        return self._get_obs(), reward, terminated, False, {"x": float(x_after)}

    def reset_model(self):
        # start from the crouched 'home' stance with a small random nudge
        qpos = self.model.key_qpos[0] + self.np_random.uniform(-0.01, 0.01, self.model.nq)
        qvel = self.np_random.uniform(-0.01, 0.01, self.model.nv)
        self.set_state(qpos, qvel)
        self.data.ctrl[:] = self.model.key_ctrl[0]
        return self._get_obs()
