# ARX-6 P5 — compact joint engineering source

**Nominal operation is verified. Three adverse-case criteria remain failed: 21 of 24 ordinary scenarios pass, and all four deliberate failure controls produce their expected consequences.** This is a concrete engineering prototype with an incomplete emergency operating envelope. It is not a manufacturing or emergency-safety release.

The compact revision folds full-size motor/reducer envelopes back beside the links using 1:1 timing belts, retains output bearings and brakes, tucks the two counterbalance pairs, and corrects the physical elbow and wrist upper stops. The native CAD masses and inertia tensors feed the supplied MuJoCo model. The independent puck moves through actual jaw contact; it is not welded or assigned a trajectory.

## Start here

| File | Purpose |
|---|---|
| `integration/P5-mechanical-design.md` | Design changes, native fit checks, compact-envelope comparison and remaining supplier/manufacturing questions. |
| `integration/P5-DYNAMICS-README.md` | Coupled model, controller, geometry checks, fault scenarios and interpretation. |
| `integration/reports/P5-fault-review.md` | All three retained failures, contact mechanism, millisecond overload durations, catalog comparisons and rejected slowdown experiments. |
| `integration/P5-component-reference.json` | Purchased candidate identities and explicit qualification status. |
| `integration/cad/ARX-6-P5-assembled-nominal-t2p5.step` | Named native assembly at the actual 2.5 s simulated pose, including phased belts/shafts and springs at their current lengths. |
| `integration/results/nominal.json` | Final 10 s physical trajectory, current interface metadata, contact/electrical telemetry and body transforms. |
| `integration/reports/P5-dynamics-summary.json` | 28 scenarios, six consecutive placement errors, numerical sensitivity and explicit unresolved status. |

The 30 s simulation completes six transfers with placement errors from 0.250 to 0.769 mm, each within the configured 1.5 mm threshold. That result does not establish indefinite drift-free cycling. The nominal model records zero structural proxy penetration. Off-path joint combinations can still reach the table or fixture; joint limits alone are not a complete collision-safe workspace.

## Unresolved adverse cases

| Case | Retained failure |
|---|---|
| Power loss at 3.2 s during placement descent | J4 estimated transmitted belt load reaches 3.184 Nm, exceeding its 2.4948 Nm service allowance. |
| Same descent with 10% weaker springs and doubled brake delay | J2/J3/J5 reach 15.678/32.192/6.994 Nm. J3 and J5 exceed the corrected raw catalog screens for about 0.833/2.083 ms. The puck contacts its nest and the descending gripper; the overload persists at 4800 Hz. |
| Power loss at 7.2 s with weaker springs and doubled brake delay | J4 misses the 0.5 s settling deadline; sampled settling occurs at about 0.567–0.575 s after the fault. |

The delivered nominal cycle, brake assumptions, belt ratings and acceptance thresholds remain unchanged. Isolated 70% and 40% reference-rate tests still leave a descent service-allowance failure and were rejected. Fail-safe payload retention, fixture clearance and engineered impact compliance require a separate hardware design and qualification. The rigid transmission model has no tooth-skip or breakage state; simulated motion after overload does not prove hardware survival.

## Rebuild and inspect

Use Python 3.12 and the versions recorded in `integration/requirements-p5.txt` for native CAD. The final build used Python 3.12.14 and Node v24.19.0. The MuJoCo 3.16.0 JavaScript/WASM runtime and its license notices are bundled; a native Python MuJoCo installation is not required.

Run from this folder:

```bash
python3 -m pip install -r integration/requirements-p5.txt
bash integration/rebuild_p5.sh
```

The full entry point regenerates native parts, material proxies, native fit/stop checks, the coupled dynamics model, spring checks, all 28 simulations, clearance/range reports and the fully phased 2.5 s native assembly. It preserves a nonzero exit status for the three unresolved ordinary scenarios. Native assembly export still runs after those expected reported failures.

To reuse the supplied CAD and repeat only the model and physical simulations:

```bash
bash integration/rebuild_p5.sh --physics-only
```

To rerun one case without overwriting the authoritative results, use a separate output folder:

```bash
ARX_VALIDATION_OUT=/tmp/arx-p5-repeat node integration/validate_p5.mjs power_loss_3.2
```

The current source and results correspond to these frozen inputs:

- Nominal trace SHA256: `14b8dcd0e13c6baa7fd9236c23bf9712ad763afcad370f489c08f907a56e5a66`
- Model SHA256: `b5d8a969db3742f01afae169039358b18182e57605f3f39382b9dfb20ad68ac5`
- Controller SHA256: `e8fbe68be5a83f02f6e0b194c573b69bcf34f098de31358fd0e236ad4795107d`

Every scenario records the seven model/source hashes it used. Do not mix a changed CAD/model/controller with the supplied trace or report. Exact historical failed-case snapshots and high-rate event logs are preserved under `integration/diagnostics`; their role is evidence, not an alternative released design.

## Deliberately retained baseline inputs

P5 regeneration is standalone. `integration/P2-baseline.xml` supplies the preserved articulated/contact topology, and `integration/P2-baseline-parameters.json` supplies the retained electrical/controller data that the P5 builder updates. `integration/baseline-reference/` contains exactly the former mesh, mass and native-body-bounds records needed for comparison. `dynamics/interface.json` is a historical schema seed: the runtime resolves current object IDs, and the validator replaces initial state and provenance with the current P5 model. The final viewer must use the fresh `interface` embedded in `results/nominal.json`.

`integration/generate_cad_p2.py` retains its historical filename but contains the current P5 generator. The current source package omits the inherited P1/P2 viewers, old PDFs/drawings, old firmware and unrelated obsolete reports. `render/original/core.glsl` is retained as a helper dependency of the separate P5 shader renderer. The accompanying shader/video source is packaged separately by the release assembly.

Catalog envelopes, nominal fits, proxies and simulation results require physical supplier, tolerance, structural, thermal, fatigue, brake, belt and contact qualification before a manufactured machine can be released. The exact retained limitations are part of this deliverable.
