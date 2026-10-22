# ARX / 6 — P5 compact-drive prototype

This revision implements the compact mechanical redesign in native CAD, rebuilds the masses and coupled dynamics, and renders the resulting geometry in a new procedural inspection film. The original motor and reducer envelopes remain full size. The changes are physical placements and new transmission parts.

**Engineering status:** the nominal task is verified in the stated model. **21 of 24 ordinary validation scenarios pass; three adverse stop criteria remain failed.** Four deliberate failure controls produce their expected consequences. Read the adverse-case section below before using this design as a hardware starting point. The package is an engineering prototype, not a manufacturing or emergency-safe release.

## Open these files

| Deliverable | Purpose |
|---|---|
| `ARX-6-P5-Inspection-1080p.mp4` | 72-second, native 1920×1080, 24 fps inspection film with chapter markers and part callouts. |
| `ARX-6-P5.html` | Offline film player, individual-part inspection, recorded shader replay and live MuJoCo physics. |
| `ARX-6-P5-CAD.zip` | Named assembled STEP, individual native parts and subassemblies, specification, mass and mechanical evidence. |
| `ARX-6-P5-Source.zip` | Current engineering and shader source, bundled physics runtime, reports, diagnostic evidence and reproduction tools. |
| `ARX-6-P5-1080p.png` | Four-sample procedural still at the actual 2.5-second nominal state. |

Inside the CAD archive, open `integration/cad/ARX-6-P5-assembled-nominal-t2p5.step` for the complete robot. It contains 384 named items and 399 valid native solids, including both handed jaws and four springs at their posed anchor distances. The workbench, workpiece and receiving nests are separate scene elements and are not part of that robot STEP assembly.

The HTML starts with the film, without allocating a graphics context. Choose **Shader replay** or **Live physics** for interactive rendering. Under **Inspect components**, select an assembly or individual modeled rigid part, adjust the explosion slider, section housings, or rotate transmission components for inspection. Drag to orbit and scroll or pinch to zoom. Inspection offsets do not disassemble the physical simulation. Supplier motor/reducer envelopes and bearings do not reveal internal components that have not been modeled.

All 14 viewer behavior checks passed in desktop Chromium using software WebGL at 256×144. In that environment, initial shader startup took 522 seconds and rebuilding after a forced graphics reset took 301 seconds; every physical field was preserved. This is a demanding procedural renderer, with no real-time performance guarantee. The mobile check covers the layout and capped defaults in an emulated viewport; a physical Android GPU was not tested. Use the MP4 for playback that does not depend on the procedural renderer.

## Actual mechanical changes

Each of the six revolute joints uses a folded parallel-axis motor/reducer arrangement with a 1:1 toothed belt. The CAD includes the pulleys, finite belt teeth, keyed shafts, slotted carrier, tension block, input support bearing, enclosure and mounting hardware. The brake acts directly at the joint output. J3 folds back along the upper arm; J5 is clocked 90° to clear the neighboring wrist drive.

The shoulder springs move inward onto shorter attachment geometry. The elbow's raised anchor mast is replaced by a lower fixed attachment and a short forearm back lever. Spring force is calculated from those moving pin centers, stiffness, free length and initial tension. Native CAD volume, centroids and full inertia tensors propagate into the rebuilt dynamics, with an explicit flexible-spring mass allocation and additional drive armature.

| Measured quantity | Before | P5 | Change |
|---|---:|---:|---:|
| Large-drive rear projection | 305.1 mm | 152.5 mm | −50.0% |
| Small-drive rear projection | 207.6 mm | 109.5 mm | −47.3% |
| Complete reference depth | 700.2 mm | 395.0 mm | −43.6% |
| Complete reference width | 205.0 mm | 316.15 mm | +54.2% |

The overall dimensions compare the same q=0 construction reference, excluding the bench, payload, flexible cables and spring geometry. That reference is not an asserted allowed operating pose. Folding trades axial projection for transverse footprint and adds carrier/transmission mass; the design is not smaller in every direction.

The large stages use 36-tooth HTD 5M pulleys and 25 mm wide, 400 mm pitch-length belts on 110 mm centers. The small stages use 30-tooth HTD 3M pulleys and 15 mm wide, 225 mm pitch-length belts on 67.5 mm centers. These are explicit nominal tooth geometries, with catalog-based load screening rather than manufacturing-certified cutter profiles.

Native range review also corrected inherited link clashes. The physical J3 and J5 upper stops now engage at 1.85 and 1.63 rad, with software limits at 1.83 and 1.61 rad. The checked native gaps at the physical limits are 2.63686 mm and 1.00000 mm. The actual dowels and targets meet at those limits.

## Film contents

| Time | Chapter |
|---|---|
| 00:00–00:10 | Fresh physical pick-and-place cycle, two transfers |
| 00:10–00:16 | Complete assembly explosion |
| 00:16–00:21 | Base drive |
| 00:21–00:27 | Shoulder drive |
| 00:27–00:33 | Elbow drive |
| 00:33–00:37 | Shoulder counterbalance |
| 00:37–00:41 | Elbow counterbalance |
| 00:41–00:45 | Wrist roll |
| 00:45–00:49 | Wrist bend |
| 00:49–00:53 | Tool roll |
| 00:53–00:59 | Gripper racks, pinion, guides and pads |
| 00:59–01:03 | Independent payload and receiving nests |
| 01:03–01:07 | Links and load path |
| 01:07–01:12 | Reassembly |

The first chapter replays the fresh coupled physical solve. Later explosion, section and extra transmission rotation are labeled mechanism inspections. They explain the same parts' relationships; they are not simulations of loose components. Every video frame is separately evaluated by the procedural fragment shader. Typography is composited afterward. The per-frame raw shader hashes and camera/state records are included as evidence.

The renderer contains 385 rigid scene records plus four procedural springs. Geometry is evaluated from analytic primitives, Boolean construction and a sampled two-dimensional pinion boundary; no triangle mesh is used for rendering. Standard numeric buffers transport the same literal float32/int32 tables for desktop and browser performance. The downloadable GLSL retains the self-contained constant tables. These buffers are not geometry or material textures.

## Verified results and their scope

The final 10-second nominal run places the independent workpiece with approximately 0.2505 mm and 0.3351 mm destination error. Six transfers over 30 seconds have errors of 0.250, 0.335, 0.474, 0.555, 0.679 and 0.769 mm, all below the 1.5 mm criterion. The trend does not establish indefinitely drift-free cycling.

The payload is a free six-degree-of-freedom rigid body. Jaw contact and friction move it; there is no kinematic attachment, payload weld, imposed payload force or runtime pose assignment. Motor currents, voltage, speed, torque, gravity, friction, spring forces and the coupled mass matrix determine the arm motion.

Nominal timestep comparisons at 1200 and 4800 Hz differ from the 2400 Hz reference by at most 0.0213°/0.0108° in joint angle and 0.0948/0.0519 mm in workpiece position. There is no structural-proxy penetration above the 0.1 mm acceptance threshold along the nominal trajectory at any integration step. The contact logger ignores penetrations of 0.01 mm or less. Off-path combinations can still put the tool into the bench or fixtures; joint limits alone do not define a collision-free workspace.

J2's requested output torque is clipped for 0.11875 seconds of the nominal task to enforce the selected 12.798933 Nm belt service allowance. This is demand-limiting duration, not measured time at an exactly constant motor torque. The estimated belt-delivered peak, including upstream armature acceleration, is approximately 12.685 Nm. These results do not imply an unused shoulder torque reserve at every instant.

Mechanical evidence includes 52 native interface checks, eight physical-stop checks and 26 posed belt/key/spring-eye checks, all passing. The 385 rigid renderer records match the independent native-CAD surface probes: 70,392 probes, maximum absolute distance about 6.77×10⁻⁶ mm. This is sampled geometric agreement, not a proof of exhaustive BREP equivalence. The source also includes optimized-versus-original distance checks, transform checks, exact numeric-buffer accessor checks and browser behavior evidence.

## Three unresolved adverse stop criteria

| Scenario | Finding |
|---|---|
| Power loss at 3.2 s | J4 estimated transmitted belt torque reaches 3.184 Nm, above its 2.495 Nm service allowance, though below the 3.742 Nm raw catalog screen. |
| 10% weaker springs and doubled brake delay, power loss at 3.2 s | J2/J3/J5 reach 15.678/32.192/6.994 Nm. J3 and J5 exceed their raw 19.198/3.742 Nm catalog screens. |
| 10% weaker springs and doubled brake delay, power loss at 7.2 s | J4 misses the 0.5-second settling deadline and settles at roughly 0.567–0.575 seconds; maximum travel is 11.885°. |

In the failed descent event, power loss also removes gripper torque. The released puck hits the nest and the descending gripper, rapidly changing link velocity and loading the upstream rotor inertia through the belt. The large overload persists at 4800 Hz. The model has no belt breakage/tooth-skip state, so its later settling cannot establish hardware survival.

Isolated 70% and 40% reference-speed experiments did not reliably remove the required-margin failure and were rejected. A stationary-placement diagnostic passes; the evidence therefore does not claim that every possible retiming must fail. The delivered controller and acceptance criteria were not weakened to conceal these findings. The validation scripts intentionally return a nonzero status for the three unresolved ordinary failures.

Read `ARX-6-P5-Engineering/integration/reports/P5-fault-review.md` and its JSON companion for exact event timing, contact pairs, high-rate evidence and rejected experiments. Fail-safe payload retention, clearance and engineered impact compliance require a further hardware design and qualification.

## Reproduction and remaining hardware work

The source archive has sibling directories `ARX-6-P5-Engineering` and `ARX-6-P5-Shader`. Begin with `README-P5.md`, `integration/P5-DYNAMICS-README.md`, `integration/P5-mechanical-design.md` and `P5-SHADER-README.md`.

From the engineering directory, `bash integration/rebuild_p5.sh` regenerates the CAD, collision proxies, coupled model and evidence; `--physics-only` reuses the supplied native outputs. The native generator retains its historical filename `generate_cad_p2.py`, but its packaged contents implement P5. Baseline files are retained only where a current builder or dimensional comparison requires them. The renderer README lists capture, shader assembly, replay, film and offline-viewer build commands.

Supplier interfaces and true internal inertias, the additional input-bearing specification, the cover-to-rail screw pattern, belt installation pretension and locking, spring hooks and fatigue, structural stress, stop impact strength, brake switching/dynamic torque, thermal constants, wiring flex life and tolerances remain unqualified. The finite belt teeth and native STEP solids make the architecture concrete and reviewable; they do not substitute for those release details or physical commissioning.
