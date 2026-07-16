# Reliable grasp pipeline

## Status vs code (2026-07-15)

| Piece | Path | Reality |
|---|---|---|
| Perception input | Hailo COCO `yolov8n` only | Boxes for cup/bottle/etc. **No** grasp/seg/custom HEF yet — do not plan M3 on masks we do not have |
| Grasp FSM | `playground/autonomy/grasp_fsm.py` | Stub: ACQUIRE → PRE_GRASP hold → VERIFY; **no motion**; `max_steps` cap |
| RobotIO arm | `playground/autonomy/robot_io.py` | Live only applies `arm_pose=="neutral"` → `(0,6,18)` cam-up; no gripper yet |
| Manual poses | `playground/micro_move.py` | `cam_up` `(0,6,18)`; `reach` `(0,14,5)` pitch −90; grip open **2000** / close **1200** @ servo 1 |
| End-to-end sketch | `playground/blanket_fetch.py` | Open-loop: yaw nudge → sonar approach stop **180 mm** / timeout **8 s** → reach → close → lift → reverse; **not** a verified grasp FSM |
| Stock IK | `kinematics.arm_move_ik.ArmIK.setPitchRangeMoving` | Coords **cm**; returns **`False`** if unreachable |
| Stock gripper | `Board.pwm_servo_set_position(duration, [[1, pulse]])` | Pulse µs; provisional playground open/close |
| Action groups | `common.action_group_control.ActionGroupController.runAction` | Scripted recoveries only — not closed-loop vision grasp |

SSOT: [CURRENT_STATE.md](CURRENT_STATE.md). Chassis must be **stopped** before `PRE_GRASP`. Approach + pickup of COCO-visible soft objects first; custom HEF later.

## Interface notes (arm / gripper)

| Call | Units | Notes |
|---|---|---|
| `ArmIK.setPitchRangeMoving((x,y,z), alpha, alpha1, alpha2, movetime_ms)` | cm, degrees, ms | Origin ≈ pan centre projected to floor (stock IK comments). Check return ≠ `False`. Wait `movetime/1000 + settle` (settle start **0.1–0.2 s**) |
| `board.pwm_servo_set_position(duration_s, [[servo_id, pulse]])` | s, µs | Gripper = **servo 1**. One bounded close per attempt |
| Proven poses (this robot, provisional) | — | Stow/view: `(0,6,18)` @0°; floor reach: `(0,14,5)` @−90°. Re-measure before cataloguing |
| Grip pulses | — | Open **2000**, close **1200** (playground). Re-validate per object family; never tight-loop close |

No confirmed grip-force telemetry in stock SDK. Closed pulse ≠ pickup proof.

## State machine

```text
DETECT -> CONFIRM -> APPROACH -> ALIGN -> PRE_GRASP -> REACH
  -> CLOSE -> VERIFY -> LIFT -> RETREAT -> CARRY
                   \-> RECOVER -> SEARCH / FAULT
```

| State | Entry evidence | Action | Timeout | Success | Failure |
|---|---|---|---|---|---|
| Detect | ≥1 detection | log label, box, `t_mono` | — | never move on 1 frame | — |
| Confirm | 3–5 consistent obs | bearing + floor-plane estimate | 2 s | confidence/age/cov pass | → SEARCH |
| Approach | outside handoff | leased crawl ≤25 mm/s, sonar-gated | 8 s (blanket) | re-detect each lease | lost target / sonar hard-stop → stop |
| Align | in handoff band | tiny yaw/lateral ticks | 3 s / ≤6 ticks | centre + range OK | → RECOVER |
| Pre-grasp | chassis vel 0 ≥0.5 s | open gripper; ready pose | 2 s | IK OK | IK `False` → FAULT safe pose |
| Reach | calibrated target | pre-grasp then contact pose via IK | movetime+settle | IK OK both | stale target / IK fail → safe pose |
| Close | target still present | **one** `pwm_servo` close | 0.7–1.0 s | command completed | never retry unboundedly |
| Verify | gripper closed | ≥2 cues (see below) | 1.5 s | pass → Lift | fail → RECOVER (open only if safe) |
| Lift / retreat | verified | carry pose; reverse short clearance; stop | 3 s | clear + stopped | stop; report |
| Recover / Fault | any hard fail | known recovery pose; stop | 2 s | operator reset | sticky FAULT |

## Calibration before closed-loop grasping

1. **Pose table** (`playground/autonomy/poses.py` — to add): name, `(x,y,z)`, pitch, movetime, settle, version. Seed from `micro_move` after re-confirm on hardware.
2. **Grip endpoints:** 10 open/close cycles unloaded; record pulses that fully open/close without stall noise.
3. **Camera→arm:** fiducial or known block on floor; predict contact vs actual at ≥3 positions; record error cm.
4. **Target catalog:** class, max mass, grip width, floor vs table, success metric (e.g. 4/5 lifts).

## Verification strategy (pickup proof)

Require **≥2 independent cues** when possible:

1. Target leaves expected floor ROI after close+lift.
2. Target appears in carry-camera ROI.
3. Scene change under small vertical lift.
4. Optional: servo/board feedback **only if** verified available (do not invent).
5. Human confirm on first N trials.

If cues fail: recovery pose → stop → bounded reverse **only if** sonar clear → SEARCH. **Never** loop `grip_close`.

## Sequenced experiments

| ID | Experiment | Setup | Procedure | Pass metric | Fail / stop |
|---|---|---|---|---|---|
| **G0** | FSM dry-run | fake `RobotIO`, recorded obs | every transition: timeout, lost target, IK `False`, step-cap | all paths end STOP/FAULT; no UART | any path without terminal stop |
| **G1** | Pose replay | chassis stopped, clear envelope | `cam_up` → `reach` → `cam_up`; log IK returns | 5/5 IK true; finally cam-up | collision / IK false ignored |
| **G2** | Grip cycles | no object | 10× open 2000 / close 1200, ≥0.5 s gaps | 10/10 complete; no tight loop | continuous PWM spam |
| **G3** | Reach geometry | soft foam block marked | manual place in reach zone; command contact pose | end-effector within ~2 cm visual | force against floor; skip |
| **G4** | Cam–arm error | known object @ 3 spots | predict vs touch | mean error ≤2 cm or document bias | proceed closed-loop without numbers |
| **G5** | Supervised pickup ×5 | one soft safe object | full FSM live, operator kill switch | ≥3/5 verified lifts; each failure classified | unbounded retry; chassis moves in PRE_GRASP+ |
| **G6** | Handoff from roam | after nav N6 | roam stops → grasp owns arm | 0 chassis cmd during arm phase | dual owners / contested UART |

Order: G0 → G1 → G2 → G3 → G4 → G5 → G6.

## Safety envelope

- Chassis: `stop_all()` and confirm before PRE_GRASP; roam must not renew drive leases during grasp.
- Arm: only named poses + IK check; wait movetime + settle; no streaming joint spam.
- Gripper: one close per attempt; open only on safe recover paths.
- Timeouts on every state; `GraspFSM.max_steps` hard cap retained.
- Soft objects first; no glass/cables/pets.

## Decision criteria

| Decision | Choose A | Choose B |
|---|---|---|
| Open-loop blanket vs FSM | bring-up / demo only | any reliability goal → FSM + verify |
| Action-group recovery | scripted stow after FAULT | fine alignment — use IK poses |
| Close pulse | 1200 works for soft foam | object slips → try slightly tighter **once**, then catalog; never hunt in loop |
| Verify strictness | early trials: 1 cue + human | unattended: ≥2 automatic cues |
| Approach stop distance | carpet / slow → **180–220 mm** | hard floors / short brake → may tighten after N2 nav data |

## Success metrics (grasp MVP)

- G5: ≥3/5 supervised pickups of one soft object with logged state traces.
- Zero chassis motion commands between PRE_GRASP and LIFT complete.
- Zero unbounded gripper close loops in code paths (lint/review + test).
- Every failure ends in stop + recovery pose within 2 s.

## Build next

1. Add `poses.py` (versioned table + `is_reachable()` wrapping ArmIK).
2. Expand `grasp_fsm.py` states to match table; keep pure; inject clock/obs.
3. Extend `RobotIO`: `grip_open/close`, `move_pose(name)`, always `stop_all` on exit.
4. `dry_run` CLI prints plan (poses + timings) with `live=False`.
5. Five supervised trials (G5) on one **COCO-visible** soft object before second class or custom HEF.
6. Seg / custom grasp HEF only after box approach + G4 cal are green.
