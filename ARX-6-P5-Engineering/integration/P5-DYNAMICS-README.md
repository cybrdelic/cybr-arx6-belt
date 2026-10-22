# P5 compact arm: reproducible dynamics

**Current result: the nominal task passes; 21 of 24 ordinary scenarios pass, and three adverse-case criteria remain failed.** All four deliberate failure controls produce their expected consequences. This package is an engineering prototype with an incomplete emergency operating envelope. `reports/P5-fault-review.md` and its JSON companion explain the retained failures and rejected slowdown experiments.

| Unresolved ordinary case | Finding |
|---|---|
| Power loss at 3.2 s during placement descent | J4 estimated belt load reaches 3.184 Nm, above the 2.4948 Nm service allowance but below the 3.7422 Nm corrected raw catalog screen. |
| The same phase with 10% weaker springs and doubled brake delay | J2/J3/J5 reach 15.678/32.192/6.994 Nm. J3 and J5 exceed their raw catalog screens for about 0.833/2.083 ms. Puck/nest/gripper impact causes the load pulse; it persists at half the timestep. |
| Power loss at 7.2 s with weaker springs and doubled brake delay | J4 misses the required 0.5 s settling deadline; sampled settling occurs about 0.567–0.575 s after the fault. |

The original 10 s nominal motion, controller, physical parameters and CAD remain frozen. A 70% reference-rate candidate and a 40% candidate still fail the delayed-descent service allowance, so neither was adopted. No brake torque, belt rating or acceptance threshold was adjusted to erase these failures. Fail-safe payload retention, fixture clearance and engineered impact compliance need a separate hardware design and qualification.

Use `bash integration/rebuild_p5.sh` from the package root to rebuild the compact CAD, material collision proxies, coupled model and verification results. The native CAD generator retains its historical filename `generate_cad_p2.py`; its current contents implement P5. `bash integration/rebuild_p5.sh --physics-only` reuses the supplied native CAD outputs and repeats the model and physics checks.

The validation and summary commands intentionally return a nonzero status while the three ordinary failures remain. They are not reclassified as deliberate negative controls.

The Node runtime uses the bundled MuJoCo 3.16.0 WASM files under `runtime/node_modules/@mujoco/mujoco`. Native CAD generation and review use Python, CadQuery and NumPy. The supplied package contains the small baseline reference set required for comparison; a sibling checkout is unnecessary.

## Source of the motion

`build_p5_model.py` constructs `ARX-6-P5.xml` from the preserved contact topology and new CAD output. Every moving link receives its regenerated mass, center of mass and full inertia tensor. The full motor, reducer, bearing and output-brake envelopes remain present. Input pulley, input shaft, keys and belt motion add the equivalent joint armature reported by the mechanical generator. The added belt stage uses a stated 0.97 efficiency assumption.

The controller advances the arm through motor current dynamics, voltage saturation, back EMF, gearbox and belt losses, gravity, coupled body inertia, friction, spring forces and native contact. The reference trajectory is a torque-controller target. The workpiece remains a separate six-degree-of-freedom body, with no actuator, attachment, external force command or pose assignment after initialization. The opposed jaws are linked to one pinion through their existing synchronization and tendon model; their contacts supply the forces that move the workpiece.

Shoulder and elbow counterbalances use the actual revised anchors, tension-only force law, stiffness, free length and calibrated initial tension from `spec.json`. The spring check independently compares generalized force with the derivative of potential energy. Reported wire-body stresses do not establish hook strength or material fatigue life.

The belt screening capacities and 1.5 service factor are recorded in `parameters.json` and the source report. The controller limits requested transmitted torque to the lower of the gearhead and belt allowances. Actual torque still follows the electrical dynamics and is checked independently. A second load estimate subtracts the upstream armature acceleration from motor torque, so power-loss tests include the belt torque that decelerates rotating drive inertia. The logs include the duration of demand limiting. The brakes act directly on the outputs, and therefore their full holding torque does not pass through the belt. Belt tooth compliance, skip, tension and wear are outside this rigid transmission model.

## Geometry and range checks

The P5 contact model includes the compact motor and reducer envelopes, material strips around bearing and brake cavities, carrier plates, windowed housings, spring brackets and mounting hardware. The inherited base-to-turret contact exclusion has been removed. The table is finite material around two real circular service openings; narrow strips conservatively retain material inside the native circular boundaries. Flexible spring, belt and cable collision is outside this proxy model.

Native CAD review identified elbow-tube and wrist-fork interference beyond the original upper travel limits. The current physical stop geometry, source limits and dynamics ranges are revised together. `P5-joint-range-review.json` preserves the original contact thresholds and reports clearance at the corrected stops; the native BREP review provides the corresponding material-intersection evidence.

`check_p5_clearance.mjs` directly evaluates distances between represented parts, including excluded contact pairs. It checks the actual simulated task, isolated joint sweeps and deterministic coupled poses. The isolated and coupled pose sweeps are geometric diagnostics, not dynamically executed trajectories. A rectangular list of joint limits is not a complete workspace collision constraint: some off-path combinations can put the tool into the table or mounting fixture. The fixed task trajectory has its own every-step contact check, and the geometric report retains all off-path intersections with names and exact joint coordinates.

## Evidence files

| File | Meaning |
|---|---|
| `results/nominal.json` | Fresh 10-second integrated motion, 120 Hz samples, contact forces, current, torque, temperature, body transforms and current interface metadata. |
| `results/nominal_30s.json` | Six consecutive transfers through the same contact simulation. |
| `results/*-metrics.json` | Per-scenario measurements, explicit checks, events and hashes of the exact model inputs. |
| `reports/P5-dynamics-summary.json` | All 24 ordinary scenarios, four deliberate failure controls, six placement errors, step-size comparisons and drive margins. |
| `reports/P5-fault-review.json` and `.md` | Explicit unresolved fault criteria, high-rate contact/load diagnosis, catalog comparisons, rejected slowdown candidates and remaining hardware scope. |
| `reports/P5-clearance-sweep.json` | Task-path and off-path rigid-proxy distances with exact problematic configurations. |
| `reports/P5-joint-range-review.json` | Revised elbow and wrist stop clearance and the retired interference thresholds. |
| `reports/P5-spring-energy-check.json` | Force/potential consistency, reference torque calibration and calculated spring body stress. |
| `reports/P5-model-provenance.json` | Applied CAD tensors, changed contact geometry, finite table, armature and build checks. |
| `reports/P5-mechanical-validation.json` | Native component-interface checks, validity, mass changes and compact-envelope comparison. |

The 28-case dynamics suite covers the nominal cycle, 30-second repeat, 1200/2400/4800 Hz integration, 10% weaker springs, normal stop, watchdog, emergency stop, invalid feedback, eight power-loss times, six combined weak-spring/doubled-brake-delay cases and reduced dynamic brake torque. Four deliberate controls remove both springs, remove power without brakes, reduce contact friction or severely weaken the gripper. Their expected physical consequences are checked separately from ordinary operating success.

The harness inspects structural contacts at every integration step, records current/voltage/torque/speed limits, verifies zero imposed workpiece force, and records actual finite brake travel and dissipated work. An emergency disables the gripper drive too; payload retention is therefore not promised by the brake-settling result. A normal controlled stop is checked separately with grip power retained.

The structural-link collision check excludes the independent puck. Zero structural penetration therefore does not mean there was no payload/fixture/gripper impact. The adverse-case review records those contact pairs explicitly. This rigid transmission model has no belt breakage or tooth-skip state; simulated motion after an overload is not evidence that physical hardware survives it.

The summary rejects mixed or stale input hashes. If the CAD, collision proxies, controller or parameters change, the model and all scenario results must be regenerated. The viewer should use the `interface` embedded in the fresh nominal trace, together with the matching XML, parameters, controller and safety module.

## Interpretation

These are reproducible computational checks of the stated mechanical and electrical model. The inspection film uses the generated geometry and integrated motion, while exploded mechanism demonstrations show part relationships. Neither the film nor solver output is manufacturing qualification. Contact friction, vendor internal inertia, spring hooks, belt pretension and fatigue, bearing/shaft fits, stop impact strength, brake switching and dynamic torque, thermal constants and tolerances require measured hardware evidence before release.
