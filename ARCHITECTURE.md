# Source architecture

This repository contains a specific historical arm implementation. It is not a generic preset library or a new CYBR GEO implementation.

## Reusable causal chain

1. `ARX-6-P5-Engineering/integration/spec.json` owns dimensional/mechanical inputs and screens. `P5-component-reference.json` records component identities and qualification status.
2. `generate_cad_p2.py` constructs native solids, assigns material density, places real parts and computes body mass properties. Its historical name does not indicate an old delivered model.
3. `build_p5_collision_proxies.py` creates material-region collision primitives from the current design, preserving bores. Native BREP checks and conservative proxies have different roles.
4. `build_p5_model.py` combines current CAD mass tensors, collision data, hard limits and retained topology. It rejects nonphysical inertia tensors rather than accepting arbitrary display geometry as a physical body.
5. `controller.mjs` and `safety.mjs` integrate causal actuation, thermal/electrical accounting, springs, delayed brakes and explicit faults through MuJoCo. Current limits and geometric limits are not substitutes for an external-impact load model.
6. `validate_p5.mjs`, native Python checks and the reports carry both success and failure. A nominal animation cannot turn failed adverse cases into passes.
7. Shader capture/compilation uses the actual generator/CSG, body transformations and physical traces. Inspection offsets are presentation-only.

## Data records

- `spec.json`: design configuration, mechanical interfaces, dimensions and acceptance limits.
- `cad_parts.json`, `placed-native-parts.json`, `mechanism-parts.json`: native identity, body ownership and mechanism/assembly roles.
- `mass_properties.json`: body masses, centers and full inertias.
- `p5_collision_proxies.json`: current collision records, explicit replacement names/prefixes and placement transforms.
- `parameters.json`: assembled physical/electrical/control parameters with provenance.
- `ARX-6-P5.xml`: articulated model, contacts, equality constraints and actuators.
- `results/*.json`: recorded states, contact/actuation telemetry, metrics and provenance.
- `ARX-6-P5-Shader/source/csg-recipe.json`, `compiled-csg.json`: captured and compiled constructive representation, not a substitute physical model.

## Features that must remain distinct

CAD validity, nominal interface clearance, tolerance stackups, controller limits, collision checks, torque screens and actual hardware qualification are different assertions. Preserve the scope and evidence behind each. This source does not contain a general tolerance propagation engine, manufacturing process planner, certified supplier assembly, flexible-body stress solver or safety-rated control stack.

For a unified downstream geometry framework, adapt these representations and checks into one shared system, keeping this arm as an example. Do not copy the cinematic motion into an unrelated preset and call it validated mechanics.
