# P5 adverse-case review

**Status: 21 of 24 ordinary scenarios pass. Three adverse-case criteria remain failed.** The 10 s nominal pick-and-place cycle, 30 s repeat, both nominal timestep comparisons and all four deliberate failure controls have the expected outcomes. The supplied geometry and nominal motion are retained as an engineering prototype; this is not an emergency-safe hardware release.

## Frozen design and decision

Retain the exact frozen 10 s nominal design as an engineering prototype. 21 of 24 configured ordinary scenarios pass; all four deliberate failure controls produce their expected consequences. Two moving-descent power-loss cases fail the belt service allowance, including a combined weak-spring/doubled-delay case that exceeds the raw catalog screen. A third weak-spring/doubled-delay case stops after the specified settling deadline. The original controller, brakes, acceptance thresholds, geometry and nominal trace remain unchanged. Fail-safe payload retention, fixture clearance and engineered impact compliance require a separate hardware design and qualification; this model does not establish emergency-safe operation.

Nominal trace SHA256: `14b8dcd0e13c6baa7fd9236c23bf9712ad763afcad370f489c08f907a56e5a66`. Model SHA256: `b5d8a969db3742f01afae169039358b18182e57605f3f39382b9dfb20ad68ac5`. The exact frozen controller and parameter hashes are recorded in the companion JSON. The rejected experiments did not modify these files.

## Belt-load failures

The screening estimate is `T_belt = T_motor_output − J_upstream × angular_acceleration`. An output-side brake does not transmit its entire holding rating through the belt, but the belt still accelerates or decelerates the upstream motor/reducer/pulley inertia. The check includes that load.

| Fault case | Joint | Estimated peak, Nm | Allowance at SF 1.5, Nm | Corrected raw catalog screen, Nm | Capacity / peak |
|---|---|---:|---:|---:|---:|
| power_loss_3.2 | J4 | 3.184 | 2.495 | 3.7422 | 1.175 |
| weak_spring_double_delay_3.2 | J2 | 15.678 | 12.799 | 19.1984 | 1.225 |
| weak_spring_double_delay_3.2 | J3 | 32.192 | 12.799 | 19.1984 | 0.596 |
| weak_spring_double_delay_3.2 | J5 | 6.994 | 2.495 | 3.7422 | 0.535 |

The 3.2 s ordinary power-loss case exceeds the J4 service allowance while remaining below the raw catalog screen. Its initial high-rate diagnostic, using exact `1/2400 s` rather than the XML's rounded timestep, records one 0.417 ms exceedance at about 3.292 s and a 3.408 Nm peak. The frozen suite's authoritative peak is 3.184 Nm. This difference is retained rather than hidden.

For the combined 10% weaker spring / doubled brake delay case, the exact XML-timestep repeat reproduces the frozen peaks exactly. All three listed peaks occur at **3.267917 s**, about 67.9 ms after power loss. J2 exceeds its service allowance for **0.417 ms**; J3 for **1.250 ms**, including **0.833 ms above the raw catalog screen**; J5 for **2.500 ms**, including **2.083 ms above the raw catalog screen**. These durations are integration-step measurements. The handbook does not provide permission to dismiss them as harmless impulse overloads.

At 4800 Hz, the same combined fault still exceeds raw capacity: J3 reaches **26.814 Nm** and J5 **8.402 Nm**. Their time above the raw screen remains about **0.833 ms** and **2.083 ms**. The precise peak is contact/timestep sensitive; the failure persists. The solver has no belt breakage or tooth-skip state, so later simulated settling must not be read as evidence that physical hardware survives an overload.

## Physical event in the model

Power loss removes electrical torque from the arm and the gripper. The puck remains a free body, so it can fall toward the placement nest while the arm continues descending during brake engagement. In the failed case it contacts the nest and then the descending gripper front-wall and motor-clamp material proxies. That contact rapidly changes link velocity and loads upstream rotor inertia through the belt.

No link-to-link structural penetration is recorded in these two fault cases. That result excludes the independent puck and therefore does not imply the absence of a payload/fixture/gripper impact. The companion JSON records the exact contact pairs, penetration and native solver contact forces at the weak-case peak. These are model contact forces, not calibrated hardware impact measurements.

The existing brake model retains the original finite delays and ramps, 60%-of-holding dynamic torque assumption, and full static holding rating. It switches between dynamic and holding capacity at 0.01 rad/s. A smoother transition or lower dynamic torque was considered, but no brake-law adjustment was adopted: the resolved contact event and half-timestep repeat establish a physical load path that cannot be dismissed as a switching artifact.

## Settling failure

With 10% weaker springs and doubled brake delay, power loss at **7.2 s** leaves J4 moving at **0.1533 rad/s** in the window that begins 0.5 s after the fault. The criterion is **0.002 rad/s**. J4 travels **11.885°** before settling. The saved trace last exceeds the threshold at **7.7667 s** and is below it by **7.7750 s**, so the sampled settling time is approximately **0.567–0.575 s**. The arm eventually stops; the configured deadline is still missed. No deadline or velocity threshold was relaxed.

## Rejected slowdown appendix

The fault trigger was moved to the same trajectory phase when testing slower references. A 70% global reference rate places the original 3.2 s fault at 4.5714 s, and a 40% rate places it at 8.0 s. These tests change only isolated in-memory controller variants; they do not replace the delivered source or trace.

At 70% speed, nominal power loss at the placement phase and the original late-settling phase pass the assessed criteria, but the combined weak/delayed descent still overloads J3, J4 and J5. At 40% speed, the cycle would last 25 s and the combined descent still reaches **3.593 Nm at J4** for **0.833 ms above service allowance**, although it remains below raw capacity. Both slowdowns were rejected because neither resolves the stated criteria. No broad phase-coverage acceptance is claimed for them.

A separate combined weak/delayed fault during stationary placement at 3.6 s passes the assessed belt and settling criteria. This bounds the conclusion: the current moving-descent trajectory and two tested slowdowns fail; the data do not prove collision unavoidable for every possible retiming or stationary placement pose.

## Controls and qualification scope

The deliberate failure controls remain effective. Reducing friction produces **78.159 mm** placement error; weakening the grip produces **251.205 mm**; removing both counterbalances produces **204.441 mm** and a software-limit trip. Removing power without brakes produces **30.307°** maximum joint travel, compared with **6.834°** for the corresponding braked emergency case. Lower RMS current after the no-spring safety trip is not interpreted as reduced drive burden. The severe no-spring case also exceeds the rigid transmission's load screen, so its post-overload motion has the same breakage-model limitation.

Fail-safe payload retention, adequate fixture/gripper clearance and engineered impact compliance or energy absorption need a separate hardware design and qualification. A larger belt alone would not establish payload safety. No unverified belt-width multiplier, higher brake torque or allowable impact rating was introduced. Supplier brake switching/dynamic torque, belt pretension and compliance, contact friction, spring hooks, tolerances and physical impact loads remain qualification inputs.

The manufacturer source is [SDP/SI, Timing Belts Technical Section](https://sdp-si.com/D820/PDFS/Technical-Section.pdf), Table 38 on printed T-78 for the large belt and Table 37 on printed T-76 for the small belt. The supplied `belt-selection-source.json` records the exact width and length factors. These are catalog selection screens, not certified reversal/impact capacity for this assembly.

## Reproduction and retained evidence

`validate_p5.mjs` and `analyze_p5_results.py` deliberately return a nonzero status while these three ordinary failures remain. The original complete failed suite is preserved under `diagnostics/freeze2-original-brake`. Integration-step event logs and rejected controller variants are under `diagnostics/brake-events`. `P5-fault-review.json` gives hashes, load comparisons, source metadata and exact reproduction commands. The nominal source hashes remain unchanged.
