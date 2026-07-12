# Agent guide — tiny_pi_car

## Goal

Learn and evolve the MasterPi stack **in place**:

1. Read and run stock code under `MasterPi/` first.
2. Add small, safe experiments under `playground/`.
3. Promote working ideas by replacing stock paths piece by piece.

## Do

- Prefer editing `playground/` for new behavior.
- When changing motion or grippers: low speed, explicit stop, short timeouts.
- Keep commits small and focused.
- Document non-obvious hardware discoveries in `docs/`.

## Don't

- Don't rewrite all of `MasterPi/` in one pass.
- Don't leave motors running in background jobs.
- Don't commit secrets, large media dumps, or virtualenvs.

## Key stock entry points

- `MasterPi/MasterPi.py` — main daemon (camera, RPC, MJPEG, “games” modes)
- `MasterPi/masterpi_pc_software/Arm.py` — desktop arm / action-group UI
- `MasterPi/masterpi_sdk/` — board + mecanum + kinematics packages
- `MasterPi/board_demo/` — low-level hardware demos
- `MasterPi/mecanum_control/` — chassis demos
