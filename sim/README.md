# Kel walking — simulation

Teaching Kel to walk, simulation-first. See the plan in
`../docs/superpowers/specs/2026-07-05-walking-in-sim-design.md`.

This trains a **locomotion policy** (the fast "reflex" brain that keeps her
upright and moving) with reinforcement learning in MuJoCo. Later, Gemini drives
it with high-level `walk_forward` / `turn` / `stop` tools — Gemini never moves the
joints itself.

Kept as a separate project so its heavy RL deps don't touch the lean `kel` package.

## Setup

```bash
cd sim
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

## Milestone 1 — watch an AI learn to walk

```bash
python watch.py random   # first, see it flail with no training (needs a display)
python train.py          # ~an hour on CPU; ep_rew_mean climbs as it learns
python watch.py          # now watch the trained policy walk
```

`Ant-v5` is a ready-made quadruped (4 legs, 2 joints each) — the same shape we
recommend for Kel's first legged body. Once it walks, we branch into the body
variants (peg legs, 3-joint legs, the wheel-leg hybrid) and compare them.
