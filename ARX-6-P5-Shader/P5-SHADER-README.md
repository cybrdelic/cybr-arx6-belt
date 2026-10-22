# ARX-6 P5 — procedural CAD renderer and inspection film

This package renders the revised P5 robot from its native CAD construction using one fragment program. The deliverables are an independently rendered 72-second inspection film, a portable shader with embedded physical replay, and an offline viewer with film, recorded replay, component inspection, and live MuJoCo modes. The engineering source, native STEP parts, mass properties, controller, and physical validation are in the adjacent `ARX-6-P5-Engineering` directory.

The renderer carries **385 rigid records and four moving springs: 389 components**. It retains the six folded belt transmissions, shaft keys, bearings, brakes, stop hardware, mounting hardware, covers, gripper, both counterbalances, workpiece, and receiving nests. The reference bench and studio floor are additional presentation fixtures.

## Deliverables and entry points

| File | Purpose |
|---|---|
| `ARX-6-P5-Inspection-1080p.mp4` | Native 1920 × 1080, 24 fps inspection film; 72 seconds and 1,728 independently rendered frames. Its first chapter follows the physical solve; later chapters are labeled inspection views. |
| `ARX-6-P5.html` | Self-contained viewer. Film opens without creating a WebGL context. Replay and inspection use the procedural shader; live mode runs the included physical model and controller. |
| `ARX-6-P5-Live.glsl` | Portable fragment source with external physical-state and inspection uniforms. All geometry tables remain literal constants. |
| `ARX-6-P5-Replay.glsl` | Portable fragment source containing the recorded physical states. This replays the solve; it does not solve dynamics inside the fragment shader. |
| `reports/inspection-parts.json` | Complete rigid and spring inventory, semantic groups, object IDs, local bounds, inspection axes, and per-part explosion offsets. |
| `reports/film-build.json` and `film/*-frame-audit.json` | Final encoding provenance and the state, camera, inspection controls, and raw shader-image hash for every frame. |
| `../ARX-6-P5-Engineering/integration/P5-DYNAMICS-README.md` | Physical model, controller, collision/contact assumptions, and engineering validation. |

Generated film, replay, and viewer reports identify their source hashes. A report from an earlier revision or a preliminary build is not evidence for a later output. The release source selection excludes inherited P3/P4 viewers, images, obsolete physical files, and earlier browser reports; the P5 build and test reports identify the delivered outputs.

## CAD construction to fragment geometry

`tools/capture_csg.py` replays the geometric part of `integration/generate_cad_p2.py` through a semantic AST interpreter. Although the native generator retains its historical filename, the captured file is the P5 engineering revision. Its modeled boxes, cylinders, cones, spheres, polygon extrusions, rigid transforms, unions, cuts, and intersections become a constructive-solid recipe. Unsupported operations fail explicitly. The capture is not based on a source-line whitelist, and it records the actual generator and specification hashes.

Native STEP export and mass-property evaluation remain engineering operations. The capture omits those operations and substitutes analytical spring generation for the marked dynamic spring blocks. It adds the independently moving mirrored jaw and the workpiece/nest records needed by the physical scene. No native mesh is imported into the render pipeline.

`tools/refine_pinion.py` preserves the native gripper pinion's 0.06 mm root blend by sampling its **two-dimensional native STEP section** at 0.00015 mm deflection. The resulting 1,000-vertex outline remains a procedural extrusion with its original socket cuts. This small contour approximation is disclosed; it is not a triangle-mesh surface or a sampled 3D distance field.

`tools/build_csg_shader.py` deduplicates shapes and primitives, writes a compact postfix Boolean tape, and builds threaded bounding-volume hierarchies. The frozen P5 scene has:

| Compiled quantity | Count |
|---|---:|
| Rigid records | 385 |
| Distinct constructive shapes | 129 |
| Analytic primitives | 612 |
| Boolean tape instructions | 1,301 |
| Polygon vertices, including the pinion section | 1,028 |
| Object BVH nodes | 760 |
| Maximum Boolean stack depth | 3 |

The compiler recognizes exact repeated constructions. An equally spaced ring of identical cylindrical cutters uses the nearest periodic member. An evenly spaced finite rack tooth row uses its nearest valid member. A toothed belt uses candidates on its four pitch-path segments. These reductions retain the original repeated solids; they do not remove teeth or round away details. The polygon edge BVH preserves both nearest-edge distance and inside/outside crossing parity.

The fragment runtime intersects simple boxes, cylinders, and spheres analytically. Other constructive shapes use bounded distance-based ray traversal with finite convergence tolerances. Surface normals use finite differences. Bounding boxes only prune work; they never appear as substitute mechanical surfaces or shadow occluders. Direct shadow rays have a finite light-distance limit and stop at the first actual solid hit. Ambient occlusion uses three short, capped distance queries. These numerical render tolerances and the pinion contour sampling mean that “CAD-derived” should not be read as a formal, bit-exact BREP equivalence claim.

Lighting uses three finite rectangular emitters, an anisotropic GGX response, a complete 5 × 5 quadrature for each emitter, and procedural manufactured finishes. Its low-frequency ambient and floor-bounce terms are deliberately approximate indirect lighting. There are no image-based material textures, environment maps, sampled geometry textures, scene vertex buffers, or scene triangle meshes. A fullscreen triangle invokes the fragment evaluator; an image attachment stores its output.

The P5 assembler also rejects an area light when a conservative bound establishes that its **entire rectangle contributes zero** because of the receiver or emitter facing direction. A numerical guard retains near-horizon cases. Every retained light keeps its full quadrature and shadow budget. Compared with the saved reference, this change produced identical linear float RGB and encoded pixels in three 1920 × 1080 frames: physical operation, an exploded shoulder drive, and a sectioned gripper. Alternating warm draws on the tested shared CPU gave median speedups of 1.086×, 1.174×, and 1.155×. These are measured examples, not a hardware-independent performance promise; see `reports/exact-light-cull-check.json`. A separate local-ray reassociation candidate was rejected after a few grazing pixels changed at full resolution.

`tools/assemble_p5.py` combines the engineering core, kinematics, immutable geometry tables, geometry runtime, P5 lighting, and camera. Display finishes affect appearance only. CAD substrate data and engineering mass properties are not changed by a display finish.

## Portable constants and desktop numeric-buffer transport

The published live and replay GLSL retain their literal arrays, suitable for a desktop GLSL 330 or WebGL 2 / GLSL ES 300 host. The host supplies the version declaration, standard resolution/time/camera interaction declarations, and fragment output; the included viewer and EGL renderer provide these wrappers.

For offline desktop film rendering, `tools/shader_tables.py` optionally moves eligible **numeric literal arrays** into one read-only OpenGL 4.3 `std430` shader-storage buffer. The fragment geometry evaluator and indexing expressions stay the same. This avoids the very large constant-index selector code that some software drivers generate.

The packer accepts only the listed scalar/vector types and recognized geometry/finish table prefixes. It strips constructors, rejects nonliteral expressions or incorrect element counts, converts the same literals to little-endian float32 or int32, and applies `std430` alignment. Scalar elements occupy 4 bytes, two-component elements 8 bytes, and three- or four-component vector elements 16 bytes. Three-component vectors include an unused padding word. The complete block is padded to a 16-byte boundary.

The current assembled scene produces **36 tables in 244,864 bytes**, including 12 bytes of final block padding. `egl_render.py` reflects the linked program's block size and every active table's offset and array stride, failing if these disagree with the upload. Reports include per-table value hashes and the complete packed-buffer hash. The buffer contains the original mathematical parameters and instructions; it contains no tessellated scene geometry or texture samples. Browser rendering uses the standard uniform-buffer transport described below; the downloadable shaders retain the constant-array path.

Float32 conversion and layout checks establish what data was transported. Driver-level image comparisons are a separate check and should be identified by their tested frames, shader hashes, and error metrics. They do not establish identical results on all GPU drivers.

### WebGL 2 uniform-buffer transport

`tools/webgl_tables.py` addresses the same compiler-selector problem in WebGL 2, which does not provide the desktop SSBO interface. It encodes the exact float32/int32 literal **bit patterns** in `uvec4` arrays inside standard `std140` uniform blocks. Four scalar values or two two-component values share a word vector; a three-component value uses three lanes and a padding lane; a four-component value occupies one word vector. Each table starts on a 16-byte boundary. Float accessors use `uintBitsToFloat`; integer accessors preserve the signed 32-bit value. Array reads become typed getter calls, including nested reads, and selected arrays' `.length()` expressions become their original constant element counts.

The viewer chooses the first variant supported by its reported maximum block size and fragment-block count. All variants contain the same mathematical geometry and finishes:

| Maximum block size | Blocks | Transported tables | Tables retained as literals | Uploaded bytes |
|---:|---:|---:|---:|---:|
| 64 KiB | 4 | 36 | 0 | 244,896 |
| 32 KiB | 8 | 36 | 0 | 244,896 |
| 16 KiB | 12 | 26 | 10 | 196,608 |

The 16 KiB variant keeps the remaining object/transform/finish arrays as their original constants to fit within 12 blocks. A table may cross a block boundary; the getter dispatches by its global 16-byte word address. No array element is discarded. The slightly different byte total from desktop `std430` follows from per-table alignment in this packed representation.

At startup the viewer checks every active block's reflected size and reads back the uploaded bytes for comparison. Its diagnostics identify the selected shader and data hashes, active buffers, retained literal tables, and readback result. If no listed variant is supported, the original constant source remains available as a fallback. The entire table data is embedded in the offline HTML; no network fetch supplies scene geometry.

An independent accessor probe checked **55,342 scalar values in each variant, 166,026 in total**, along with every array length, signed conversion, vector lane, and block crossing. All output scalar bit patterns matched with zero error; see `reports/webgl-table-accessors.json`. That probe executes the generated `std140` accessors on desktop OpenGL. Actual WebGL startup/readback and browser-versus-native images are separate checks in `viewer-tests-p5.json` and `webgl-transport-parity.json`.

## Inventory and inspection controls

The inventory starts with the **375 rigid placements** emitted by the native CAD generator. The independently moving mirrored jaw contributes five additional records; the puck and four nest records contribute five more. Four dynamic spring records bring the scene-component total to 389. The studio table, legs, and lower floor are outside this inventory.

| `u_inspect` | Assembly | Rigid records | Springs |
|---:|---|---:|---:|
| 0 | Complete robot and scene | 385 | 4 |
| 1 | Base drive | 72 | 0 |
| 2 | Shoulder drive | 53 | 0 |
| 3 | Elbow drive | 53 | 0 |
| 4 | Wrist roll drive | 52 | 0 |
| 5 | Wrist bend drive | 55 | 0 |
| 6 | Tool roll drive | 53 | 0 |
| 7 | Rack-and-pinion gripper | 20 | 0 |
| 8 | Shoulder counterbalance | 7 | 2 |
| 9 | Elbow counterbalance | 8 | 2 |
| 10 | Workpiece and nests | 5 | 0 |
| 11 | Link structure | 7 | 0 |

Group 11 contains the upper and forearm link tubes, root ears, nut strips, and forearm clamp shims. Wrist forks are grouped with their associated drive assemblies.

| Uniform | Meaning |
|---|---|
| `u_inspect` | Zero selects the full scene; 1–11 selects the corresponding semantic assembly. |
| `u_part` | Zero retains all parts in the selected assembly. A positive value selects `object_id + 1` from the metadata and hides the dynamic springs. |
| `u_explode` | Zero is assembled; one applies the full deterministic offset recorded for each part. Intermediate values interpolate the display displacement. Small hardware and all four springs have their own offsets. |
| `u_mechanism` | Additional demonstration angle, in radians, for an isolated transmission. This is separate from the physical joint phase. |
| `u_cutaway` | Progressively sections designated modeled housings and guards. Custom housing sections remove positive local X; the gripper bridge section removes positive local Z. |
| `u_camera_override`, `u_camera_origin`, `u_camera_target`, `u_camera_focal` | Explicit camera interface used by the film director and inspection viewer. Camera coordinates are render-world units. |

Exploded parts remain the same solids. The runtime applies each part's displacement before tracing its true geometry. Bounds account for the full demonstration rotation and explosion range so inspection does not clip rotating keys, stop targets, or hardware.

Sections are intersections of genuine modeled solids with display planes. Vendor motor, gearhead, brake, and bearing envelopes retain only the geometry actually modeled in the native source. The renderer does not invent supplier gear trains, bearing rolling elements, windings, friction details, or other undisclosed internals. Visible interfaces and modeled hardware explain the load path without making such an internals claim.

The reference 40 mm tabletop has two real round service bores: Ø110 mm at X = 0, Z = 0 and Ø46 mm at X = 110 mm, Z = 0. These are subtracted solids, including for shadows; there is no connecting slot. The native base foot and its individual underside washers and fasteners surround this mounting interface.

## Physical pose, belt phase, and springs

The physics interface uses SI units, Y up, and WXYZ quaternions. CAD construction uses millimetres. The shader's render world uses **one unit = 200 mm**. The six joint inputs, two independent jaw gaps, and independent workpiece pose come from the physical trace or live solver. The puck is never attached to the tool by a render-only weld.

The body rotation convention is:

| Body | Rotation relative to the preceding frame |
|---|---|
| Turret | `Ry(-q1)` |
| Upper arm | `Rz(-q2)` |
| Forearm | `Rz(-q3)` |
| Wrist roll | `Ry(q4)` |
| Wrist bend | `Rz(-q5)` |
| Tool roll | `Ry(q6)` |

The shoulder origin is `[0, 144, 0]` mm. Upper and forearm lengths are 280 and 260 mm. The two jaw origins use the actual half gaps, with opposite local-X signs and a tool-local Y datum of 219.2 mm. Workpiece quaternions are normalized before use. `check_fk.py` compares these equations with the independent recorded MuJoCo body transforms.

All six folded transmissions are 1:1 at the belt stage. J1–J3 use 36-tooth, 5 mm pitch, 25 mm wide pulleys and a 110 mm center distance. J4–J6 use 30-tooth, 3 mm pitch, 15 mm wide pulleys and a 67.5 mm center distance. The motor and reducer keep their full native envelopes. The belt-loop tooth counts are 80 and 75 respectively.

Around each captured positive shaft axis, the physical input phase is:

```text
J1: -q1     J2: -q2     J3: +q3
J4: +q4     J5: -q5     J6: +q6
```

The input pulley, input shaft, and input key belong to the parent body, so the shader rotates those records about their actual input-axis center by this phase. The output pulley and output hardware already belong to the rotating child frame; physical joint rotation is not applied to them twice. The stationary motor and reducer envelopes do not rotate with the input shaft.

For tooth index `k`, pitch `p`, pitch radius `r`, belt length `N*p`, and phase `alpha`, the closed-path station is:

```text
s = (k*p + r*alpha) mod (N*p)
N*p = 2*center_distance + 2*pi*r
```

Each tooth follows that exact closed pitch path, with its native radial offset from the path. The backing loop is stationary as a geometric shape. In a drive inspection, `u_mechanism` adds the demonstration phase to the belt teeth and appropriate rotating hardware. Nominal physical operation sets that extra phase to zero while retaining the real joint-driven phase. This is a geometric kinematic visualization; tooth forces, belt compliance, and slip are handled only to the extent described by the engineering model.

The gripper pinion follows the recorded jaw travel through its 3 mm pitch radius. Its local forward angle is `-(1000*mean(jaw_half_gaps_m) + 2)/3` radians; the 2 mm term is the modeled rack datum. The opposed jaw translations remain independent physical inputs.

Both shoulder springs and both elbow springs rebuild their axes and lengths from the actual parent and child anchor positions. Coil radius, wire radius, active turns, straight leads, and eye dimensions come from the shared specification. The helix pitch changes with anchor separation; the eyes and tail geometry remain analytic. An exploded spring receives a separate display translation without changing those physical anchor calculations. This is a geometric spring depiction, not a finite-element solution of wire stress or local coil contact.

## Film states and physical interpretation

The film has 14 chapters: operation, complete disassembly, six drive close-ups, two counterbalance close-ups, gripper, workpiece/nests, link structure, and reassembly. Every frame uses its own state and camera evaluation. Typography and callout lines are composited after the procedural render; the per-frame audit records the raw rendered RGB hash before these overlays.

The first 10 seconds show the nominal physical trace. Joint angles, jaw motion, and workpiece pose are interpolated from the recorded 120 Hz samples; quaternion interpolation uses a consistent hemisphere and normalization. The trace is produced by the engineering controller and MuJoCo integration, not by an animated end-effector path inside the shader.

Subsequent chapters are explicitly marked **INSPECTION VIEW**. Whole-assembly disassembly and reassembly freeze a physical pose while the camera and display offsets move. Drive chapters section selected housings, separate parts, and add slow transmission rotation. Counterbalance chapters keep the other arm coordinates fixed while following the relevant recorded joint coordinate. The gripper chapter holds the arm pose and shows recorded jaw travel through a sectioned bridge; the workpiece is inspected separately. These isolated demonstrations are not a new physical simulation of a dismantled robot, a released brake, or floating hardware.

The portable replay resets after its recorded 10-second interval. It makes no claim of a dynamically seamless loop. Live mode in the HTML uses the P5 physical model and controller, whereas replay mode uses the stored states. Inspection controls affect the rendered presentation and do not modify the physical solver's assembled model.

## Reproduce the outputs

Keep `ARX-6-P5-Shader` and `ARX-6-P5-Engineering` adjacent. Run the following commands from the shader directory. Geometry tools also accept `ARX_P5_SHADER_ROOT` and `ARX_P5_ENGINEERING_ROOT`; the P5 assembly, film, and viewer tools use the sibling layout directly.

The recorded Python environment includes NumPy 2.3.5, Pillow 12.3.0, CadQuery 2.7.0, and cadquery-ocp 7.8.1.1.post1. Native geometry generation additionally needs the engineering package's dependencies. Desktop film rendering needs EGL, an OpenGL implementation supporting GLSL 430 and SSBOs, and `ffmpeg`. The browser checks use Node Playwright 1.62.1 and a Chromium executable; Python Playwright is not used. The existing source package includes the offline MuJoCo viewer assets.

First finish the engineering regeneration and physical validation described in its README. The CAD generator, specification, STEP outputs, mass properties, collision model, controller inputs, and `integration/results/nominal.json` must describe the same revision. The film director checks the trace's model/controller/mass/collision provenance before it will render.

To regenerate and validate the shader geometry:

```bash
python tools/capture_csg.py
python tools/refine_pinion.py
python tools/build_csg_shader.py
python tools/check_csg.py
python tools/check_optimized_csg.py
python tools/check_fk.py
python tools/assemble_p5.py
python tools/build_replay_p5.py
```

Do not recapture alone and then assemble: `refine_pinion.py` must run after capture and before compilation to retain the native root blend. The geometry compiler also runs the periodic-cylinder and moving-belt equivalence checks. It verifies the current generator and specification hashes.

Render representative chapter previews, then the final film and joined output:

```bash
python tools/film_p5.py --preview --chapter 0 --chapter 3 --chapter 10
python tools/film_p5.py --width 1920 --height 1080 --fps 24 --samples 1 --shadows 1 --quality 1
python tools/film_p5.py --join --width 1920 --height 1080 --fps 24 --samples 1 --shadows 1 --quality 1
python tools/verify_film_p5.py
python tools/build_viewer_p5.py
```

Chapter indices are zero-based. `--chapter` may be repeated to render selected chapters. The default film settings are the values shown above; each emitter still uses all 25 BRDF quadrature points. More camera or shadow samples increase cost without changing mechanical geometry. Preview images and chapter files are placed in `film/`. Full chapters are resumable only when their recorded source/settings hashes and expected frame counts agree. Joining checks the shader, trace, inspection metadata, director, renderer, table packer, resolution, frame rate, and sampling/quality settings.

Run `verify_film_p5.py` only after all 14 chapters are complete. It recomputes every chapter MP4 hash, verifies source/settings and numeric-table provenance, checks every frame audit against the current director, measures raw-image hash uniqueness per chapter and overall, and confirms all 11 inspection groups plus both paired-spring chapters. `ffprobe` counts the actual encoded frames and verifies native resolution, rate, and duration; a present joined MP4 is also fully decoded with `ffmpeg`. The expected final film is 1,728 frames at 24 fps over 72 seconds. The verifier writes `reports/film-verification-p5.json` and a labeled `reports/film-contact-sheet-p5.jpg` made strictly from each final chapter's actual middle-frame JPEG, never from preview images. A complete delivery requires `final_film_verified: true`; if the joined MP4 is absent, a successful chapter-only result is explicitly marked as awaiting the join.

Build the viewer after joining the final film so the HTML embeds that final MP4 and its metadata. The viewer builder can also make a preliminary film-free inspection page; that preliminary output should not be delivered as the completed film viewer.

Run the P5 behavioral browser check with a known Chromium executable:

```bash
ARX_CHROME=/absolute/path/to/chromium node tools/test_viewer_p5.cjs
python tools/check_webgl_transport.py
```

The browser test verifies film metadata, fresh shader startup, numeric-buffer byte readback, assembly/part inspection, replay seeking, live solver advancement, context-loss recovery, controlled stop response, and capped mobile-view defaults. It also saves a shader/state/image snapshot used by `check_webgl_transport.py` to compare the WebGL result with the desktop evaluator. `--functional-only` deliberately omits the embedded-film metadata check and is useful during development. It is not the full delivery test. Software WebGL can spend substantial time compiling its first tiny draw; subsequent tiled draws retain a shorter timeout. A desktop emulated mobile viewport is not a test on a physical phone GPU.

The recorded desktop Chromium software-WebGL run passed **14/14 behavioral checks** with **256 × 144** shader frames in `--functional-only` mode. Initial startup took **522.032 seconds**; rebuilding the graphics resources after context restoration took **301.109 seconds**. All 47 physical-state fields remained exactly unchanged through restoration and the resource rebuild, and the live normal-stop check passed. The mobile check covered only emulated viewport defaults: a 320-pixel long edge, one sample, and no initial WebGL allocation. A physical Android GPU was not tested. These results establish functionality at the tested settings and do not establish real-time rendering performance.

Use the explicitly named P5 commands above for this revision. Historical renderer rebuild and browser-test tools are not part of this release.

For the supplied completed release, the separate final-media and cross-artifact checks are:

```bash
node tools/test_media_p5.cjs
python tools/verify_delivery_p5.py
```

The media check compares the final HTML against `reports/viewer-media-baseline-p5.json`, captured from the page used for the functional browser test. It permits only the embedded film/metadata, native poster, and corrected MP4 download label to change. It rejects any WebGL context request, checks the embedded video against the final MP4 bytes, and loads its media metadata without repeating the expensive shader compilation. A changed executable module or physics asset requires a new functional test before a new baseline is captured; the baseline must not be replaced merely to make a failed identity check pass.

The delivery checker is an identity check for this particular frozen release. It checks the film, viewer, replay, native assembly, physical inputs and evidence together. Its `passed` field concerns artifact consistency; it explicitly retains the engineering result of **21/24 ordinary scenarios passing, with three unresolved adverse cases**. A newly modified design needs its own physical validation and output provenance rather than the old release hashes.

## Validation evidence and limits

| Report | What it establishes |
|---|---|
| `csg-capture.json` | Actual CAD-generator and specification hashes; semantic capture scope and explicitly excluded native/dynamic operations. |
| `shader-geometry.json` | Compiled object, primitive, tape, polygon, and BVH counts with captured-recipe provenance. |
| `pinion-contour.json` | Native STEP hash, section plane, 0.00015 mm sampling deflection, and retained root-blend contour. |
| `geometry-surface-check.json` | All 385 rigid records matched; 70,392 native-surface probes passed a 0.001 mm tolerance. Maximum absolute sampled distance was 0.000006768 mm. |
| `optimized-csg-check.json` | All 385 records passed 98,560 raw-versus-compiled distance comparisons; maximum difference about 1.20 × 10⁻¹² mm. An additional 2,308 polygon-BVH checks reached about 1.78 × 10⁻¹⁵ mm maximum difference. |
| `csg-symmetry.json` | 18,000 periodic-cylinder comparisons and 7,000 belt-path comparisons, including moving phases; maximum differences about 2.55 × 10⁻¹⁴ and 7.11 × 10⁻¹⁵ mm. |
| `forward-transforms.json` | Nine body transforms across every recorded frame compared with MuJoCo's stored poses. For the final Freeze 2 trace, 10,809 comparisons passed; maximum position error was 3.26 × 10⁻¹⁶ m and rotation-entry error 2.11 × 10⁻¹⁵. |
| `assembly-p5.json`, `replay-build.json`, `viewer-build.json` | Current output hashes and the exact geometry/trace/physics artifacts used by each build. |
| `exact-light-cull-check.json` | Reference-versus-accepted-shader image comparisons and alternating draw timings at 640 × 360 and 1920 × 1080; unchanged geometry and sampling budgets. |
| `p5-renderer-review.json` | Independent review of numeric-table packing, film state/camera/callout conventions, resolved corrections, and remaining limited reproducibility caveats. |
| `webgl-table-accessors.json` | All 166,026 scalar accessor results across the three uniform-block variants, their lengths, signed conversions, lanes, and cross-block addressing matched exactly in the desktop accessor probe. |
| `webgl-transport-parity.json` | Browser uniform-buffer rendering compared with desktop numeric-buffer rendering at the recorded test state; inspect its error metrics, shader hash, and pass result. |
| `film-build.json`, chapter JSON, and frame audits | Encoded film dimensions, rate, frame count, source and numeric-buffer hashes, per-frame state/camera controls, and rendered-image hashes. |
| `film-verification-p5.json` | Recomputed chapter/joined MP4 hashes, current-source and numeric-table checks, decoded frame counts, raw-audit uniqueness, camera/state consistency, all-group and spring coverage, full joined-film decode, and contact-sheet source hashes. |
| `viewer-tests-p5.json` | Actual browser behavior for the HTML hash in that report; inspect its `passed` result and scope. |
| `viewer-media-baseline-p5.json`, `viewer-media-tests-p5.json` | Final embedded video and poster checks, film-first behavior without a graphics context, and executable/physical identity relative to the functional-test page. |
| `delivery-consistency-p5.json` | Consistent identities across the completed deliverables while retaining the three unresolved engineering fault criteria. |

The geometry checks sample native STEP-derived surface data; they are not an exhaustive proof of equality over every BREP point. Optimization checks are numerical equivalence tests. Transform checks evaluate the shader equations in double precision and exclude GPU float32 roundoff. Engineering safety margins, actuator limits, brake timing, contacts, and fault scenarios belong to the separate physical validation and are not established by a successful rendered image.

Frozen geometry provenance for this revision:

```text
CAD generator SHA256:
0c8474173cc5ec70164cae5050a9aa7decbf6e30f14cb7f67564e9fbdaad58f7
Specification SHA256:
606e09b482d4c5f838ee49daced4b574f8260450dd350735e95422c2d666a8ac
Captured recipe SHA256:
3d26522dd8a764ca067cf444500530dfc63f22c5d6dbee8d1e9e22edbbfd454b
Compiled constructive scene SHA256:
ca91a0664d1d3193bac02906d8142723a638908917549c4baf01f02596a8c73a
```

The generated reports remain the authoritative record of a particular rebuild, especially if controller-only revisions produce a later physical trace without changing this frozen geometry.
