# ARX / 6 — P5 in action

This companion film shows the compact P5 arm executing six physical pick-and-place transfers over **30 continuous seconds**, at **1920 × 1080 and 24 frames per second**. The camera changes at 10 and 20 seconds. Simulation time continues through those changes at normal speed.

The robot stays assembled. The film does not use exploded views, section cuts, extra mechanism rotation, or image generation. All six joints, both jaws and the independent payload follow the recorded coupled simulation. The phase labels describe the controller's scheduled task phases.

## What the three shots contain

| Physical time | View | Transfers |
|---|---|---|
| 0–10 s | Original whole-arm operation view | 1 and 2 |
| 10–20 s | Newly rendered elevated view | 3 and 4 |
| 20–30 s | Newly rendered front view | 5 and 6 |

The first shot deliberately reuses the original operation chapter. Every one of its **1,201 recorded states, with all 47 fields**, exactly matches the first ten seconds of the longer solve. The following twenty seconds use their actual later states; the renderer does not repeat the first ten seconds or reset the payload. All six destination errors in this nominal run are below the 1.5 mm criterion: approximately **0.250, 0.335, 0.474, 0.555, 0.679 and 0.769 mm**. This finite run does not establish indefinitely drift-free cycling.

## Files and evidence

The separate deliverable is `ARX-6-P5-In-Action-1080p.mp4`. This small source companion intentionally excludes videos, the full baseline package, temporary previews, browser screenshots and render caches.

- `production/action_film.py` drives the two new shots, preserves complete frame audits and joins all three shots.
- `production/verify_action_film.py` independently checks source identity, all new render states and camera records, absolute physical time and video decoding. It compares every decoded joined frame with the corresponding source-segment frame.
- `reports/action-trace-verification.json` records source provenance, exact opening-state equality and all six placement results.
- `reports/action-camera-audit.json` records sampled framing checks.
- `reports/action-build.json`, `reports/action-frame-audit.json` and the two `render/*-frame-audit.json` files retain final source, camera and raw-frame evidence.
- `reports/action-film-verification.json` is the completed-video result. Both `passed` and `final_film_verified` must be true. The earlier preflight report intentionally has `final_film_verified: false` because it does not inspect a completed video.
- `reports/action-contact-sheet.jpg` contains nine frames decoded from the completed MP4.
- `manifest.json` lists the size and SHA256 of every packaged content file. It does not include itself.

## Baseline dependency and layout

Obtain the previously delivered **`ARX-6-P5-Source.zip`**, whose SHA256 is:

```text
df51911e3701191a5f1aee62b0111ad3c7a03f131d5c88eda6b3077f4546b510
```

Extract this action companion, then extract that baseline ZIP into its `source` directory. The resulting paths must include:

```text
ARX-6-P5-Action/production/action_film.py
ARX-6-P5-Action/production/verify_action_film.py
ARX-6-P5-Action/source/ARX-6-P5-Source/ARX-6-P5-Engineering/
ARX-6-P5-Action/source/ARX-6-P5-Source/ARX-6-P5-Shader/
```

Alternatively, set `ARX_ACTION_SOURCE_ROOT` to the extracted `ARX-6-P5-Source` directory containing those two sibling directories. Both the director and verifier honor this override. Keep the baseline inputs unchanged; the tools check their accepted hashes.

## Reproduce the film

The supplied workflow uses Python with NumPy and Pillow, system EGL with OpenGL 4.3 shader-storage-buffer support, FFmpeg with `libx264`, `ffprobe`, and the DejaVu fonts at `/usr/share/fonts/truetype/dejavu`. It does not need CadQuery to render the already supplied geometry. The baseline package's environment notes describe the full engineering build dependencies. The current headless renderer was tested through Mesa software rendering; performance varies by system.

Run these commands from the extracted action-companion directory:

```bash
python3 production/verify_action_film.py --preflight
python3 production/action_film.py --audit-cameras
python3 production/action_film.py --shot 1 --shot 2
python3 production/action_film.py --join
python3 production/verify_action_film.py
```

The first rendering command creates both new ten-second shots in one graphics process. A completed shot is reused only when its source/settings identity and video/audit hashes still match. An interrupted partial shot is rendered again. Joining reuses the baseline's original `film/01-operation.mp4` and does not re-encode the three shots.

Each new frame uses one camera sample, one shadow sample per light and the accepted full lighting-quality setting, with exposure 0.38. Rendering starts at physical time 10 seconds and proceeds through 29.958333 seconds. Driver differences can affect pixels; the evidence checks each output against its own recorded rendering and encoding, rather than promising identical pixels on every GPU.

After full verification succeeds, rebuild this small source archive with:

```bash
python3 production/package_action_source.py --build
```

The packager refuses to build while final media or evidence are missing, while verification is failed, or when the verified video or source files have changed. It then checks every archived content hash, size and ZIP CRC.

## Engineering scope remains unchanged

This is a nominal simulation demonstration of an engineering prototype. The broader P5 suite still has **21 of 24 ordinary scenarios passing**, with these three adverse stop failures retained:

| Scenario | Remaining failure |
|---|---|
| Power loss at 3.2 s | J4 transmitted belt torque exceeds its selected service allowance. |
| Weaker springs and doubled brake delay, power loss at 3.2 s | Impact loads at J3 and J5 exceed their raw catalog torque screens. |
| Weaker springs and doubled brake delay, power loss at 7.2 s | J4 misses the 0.5-second settling deadline. |

Making the nominal action film does not resolve these cases or qualify the design for manufacturing or emergency-safe hardware use. The complete mechanical limitations and fault evidence remain in the baseline P5 source package.
