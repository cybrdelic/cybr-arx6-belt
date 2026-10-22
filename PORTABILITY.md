# Portable setup and bounded checks

Use Python 3.12 and Node.js 24. Create an environment with `python -m venv .venv`; activate `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` in Bash/Zsh. From the repository root:

```text
python -m pip install -r ARX-6-P5-Engineering/integration/requirements-p5.txt -r ARX-6-P5-Shader/requirements.txt
python tools/restore_geometry_cache.py
python tools/portable.py cad-smoke
python tools/portable.py physics-smoke
python tools/portable.py gl-smoke
python tools/portable.py viewer-build
```

The native CAD smoke builds and exports ten actual large/small bearing-support solids, including bores, bolt holes and keyed shafts. It refuses an existing CAD output directory; pass a fresh `--output` for another run. It is not a full-assembly manufacturing check. Physics smoke runs fresh nominal and power-loss scenarios to `.local/portable`, preserving archived traces. It requires nominal success and reproduces the known J4 belt overload. A successful regression check therefore does **not** mean the power-loss design passed its safety criterion. The validator itself still exits 1 on that overload; thresholds and model equations are unchanged.

For the complete workflow use `python ARX-6-P5-Engineering/integration/rebuild_p5.py --physics-only`, or omit `--physics-only` for full CAD regeneration. This is the cross-platform equivalent of `rebuild_p5.sh` with the same fresh-provenance gate and nonzero failures. Full CAD regeneration clears previous top-level STEP/STL exports in its working clone, as before. The full suite is substantially more expensive than the bounded smoke.

## Rendering backends

Native shader tools use [glcontext's platform backends](https://github.com/moderngl/glcontext): WGL on Windows, EGL then X11 on Linux, and native macOS GL where the shader's version is supported. `ARX_GL_BACKEND=native` or `egl` selects a backend explicitly. `gl-smoke` checks actual context creation and framebuffer rendering only; it does not compile the entire robot. The numeric-table film renderer requires OpenGL 4.3 SSBOs. macOS native OpenGL cannot run that backend; use the actual WebGL2 UBO viewer instead. No shader math is replaced or relabeled as equivalent film delivery.

Build and render the WebGL2 fallback on Windows, Linux or macOS:

```text
python tools/portable.py viewer-build
cd ARX-6-P5-Shader
npm ci --ignore-scripts
npx playwright install chromium
node tools/smoke_viewer.cjs
```

The smoke compiles the procedural robot, verifies GPU numeric-table byte readback and captures a fresh 256-pixel frame within a three-minute local budget (ten minutes on shared CI runners; ARX_VIEWER_TIMEOUT_MS can set a bounded budget up to fifteen minutes). The browser follows Playwright's platform defaults instead of a Linux-only executable. Set `ARX_CHROME` to an existing browser executable or `ARX_ANGLE` to an explicitly supported ANGLE backend if needed. The complete viewer tests remain `npm run check:functional` and are more expensive. Native driver capabilities and shader compilation resources can still limit execution; the smoke fails rather than replacing a failed render with a historical image.

Full films need FFmpeg and ffprobe on PATH. Caption fonts are discovered from Windows/macOS/Linux system fonts or `ARX_FONT_DIR`, with Pillow's built-in fallback; font appearance can differ across hosts. The original Linux film reports remain historical evidence.

The CI workflow runs fresh CAD and dynamics plus a real WebGL2 robot frame on Ubuntu, Windows and macOS. Defining this matrix does not mean the hosted runs have passed. This audit is for published baseline `aabdf8c57a4ee64f77b8a246ad9aca7b51d9cba2`; the compact-cartridge variant is separate and its mechanics must not be inferred from these results. No hardware qualification is claimed.

## Windows verification and remaining limits

The 2026-10-22 baseline audit built all ten smoke solids, reproduced nominal success and the exact documented power-loss overload, built the UTF-8 offline viewer, and rendered a native OpenGL framebuffer. Chrome's default ANGLE route exceeded the three-minute robot-shader budget on Intel UHD Graphics. With `ARX_ANGLE=gl`, the actual 256x144 robot frame and all 244,896 geometry-table bytes were verified and captured, but the original test then stalled during browser shutdown. The test now owns a BrowserServer and bounds teardown, terminating only that test's browser process tree when graceful shutdown stalls. Its launch/cleanup path is tested separately; the final complete browser command and Linux/macOS execution remain CI verification work. No additional full shader run was used to hide the timeout.

## Linux CI rendering backend

The initial Linux hosted Chromium headless backend lost its WebGL context on the first 16x16 probe after successful exact numeric-table readback. CI therefore selects the system Mesa OpenGL backend explicitly through ANGLE under Xvfb (`ARX_HEADLESS=0`, `ARX_ANGLE=gl`, `LIBGL_ALWAYS_SOFTWARE=true`). This is CPU software rendering, not a physical GPU claim. The same original shader, geometry tables and real-frame assertions remain required. The smoke records the actual browser renderer and uploads its generated frame/receipt; a failed backend is not replaced by film playback. Hosted validation of this follow-up is pending.

`ARX_HEADLESS=0` supports an existing display; the default remains headless. Linux automation can supply a virtual display using [Playwright's documented Xvfb route](https://playwright.dev/docs/ci#running-headed). Mesa's [software selection variable](https://docs.mesa3d.org/envvars.html) selects the available software renderer. This does not install or alter a user's graphics driver.
