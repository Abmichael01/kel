# Teaching Kel to walk — simulation-first plan

## Goal

Train a quadruped walking controller in a physics simulator, then (later) let
Gemini drive it with high-level commands. Start entirely in sim — no hardware.

## The two-layer brain (the key architecture)

Walking and thinking are separate controllers at different speeds:

- **Locomotion policy (reflex)** — a small neural net trained by reinforcement
  learning. Runs at high frequency (50–500 Hz), reads joint angles + balance
  state, outputs leg motions. Knows *how* to walk, not where or why.
- **Gemini (cognition)** — decides *what* to do and calls high-level tools:
  `walk_forward(distance)`, `turn(direction)`, `stop`. Never touches joints.

Gemini controls walking the same way it already calls `look`/`move`/`see_screen`.
The policy is trained first and stands alone; the Gemini tool layer is a thin
command interface added later.

## Approach

Reinforcement learning in **MuJoCo** (free, open-source). No dataset needed — the
policy learns from a reward (move forward, stay upright, don't thrash) over
millions of fast simulated steps. Optional later: motion-capture imitation for
more natural gait.

- **Simulator:** MuJoCo via `gymnasium[mujoco]`.
- **RL algorithm:** PPO (via stable-baselines3 to start; RSL-RL later if we go GPU/Isaac).
- **First milestone:** MuJoCo's built-in **Ant** (a ready-made 4-legged, 2-joint-per-leg
  creature) learns to walk — a fast "it moves!" win, no custom body modeling.

## Body variants to compare (all cheap to try in sim)

Same reward, different morphology; compare which learns the fastest, steadiest gait:

1. **Peg legs, hip only** — 1 joint/leg (4 DoF). Crude shuffle; simplest.
2. **Hip + knee** — 2 joints/leg (8 DoF). Real walking; the SpotMicro/Bittle sweet
   spot. **Recommended primary.**
3. **Hip-sideways + hip + knee** — 3 joints/leg (12 DoF). Turning + stability.
4. **Biped** — 2 legs, for contrast (hard to balance).
5. **Wheel-leg hybrid** — wheels + simple legs; experimental.

## Where it lives

A separate `sim/` project (heavy RL/MuJoCo deps), isolated from the clean `kel`
package so the robot brain stays lean. The trained policy exports as a small file
the `kel` app can later load behind the `walk_*` tools.

## Roadmap

1. Stand up MuJoCo; train Ant → watch it walk. (Milestone: a learned gait.)
2. Define the variant morphologies; train + compare.
3. Pick the best; harden the policy (rough ground, pushes) for robustness.
4. Add the Gemini `walk_forward`/`turn`/`stop` tool layer in sim.
5. (Much later, optional) sim-to-real onto a small quadruped — the hard part.

## Honest constraints

- Training needs real compute/time; watching it render needs a display (the
  owner's machine, not a headless server).
- Sim-to-real on hobby servos is the hardest stage and is deliberately last.
- This is a separate ambition from the wheeled "drives around" body; that remains
  the pragmatic real robot.

## Out of scope (for now)

Bipedal hardware, GPU/Isaac Lab scaling, imitation-learning gaits, real actuators.
