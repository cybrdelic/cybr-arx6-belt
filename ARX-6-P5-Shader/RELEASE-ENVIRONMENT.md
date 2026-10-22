# P5 source release: environment and dependency notes

Keep `ARX-6-P5-Engineering` and `ARX-6-P5-Shader` as adjacent directories. The build tools resolve their inputs from their own location and that sibling layout. The original workspace path is not required. Absolute paths retained inside historical reports are provenance records, not build inputs.

## Recorded software environment

| Dependency | Version or requirement |
|---|---|
| Python | 3.12.14 in the recorded build |
| NumPy | 2.3.5 |
| Pillow | 12.3.0 |
| CadQuery | 2.7.0 |
| cadquery-ocp | 7.8.1.1.post1 |
| Node.js | 24.19.0 in the recorded build |
| Node Playwright | 1.62.1, pinned in `package.json` |
| Native render interface | EGL and OpenGL 4.3 / GLSL 430 with shader storage buffers |
| Media utilities | `ffmpeg` with libx264 and `ffprobe`, available on `PATH` |
| Browser | Chromium executable supplied through `ARX_CHROME` |

The pinned Python packages are in this directory's `requirements.txt` and the engineering directory's `integration/requirements-p5.txt`. Install them into a local virtual environment. Python Playwright is not used. The packaged MuJoCo JavaScript and WebAssembly runtime is already present in both the engineering runtime folder and the shader's embedded runtime asset; their bytes are checked by the package dependency audit. The corresponding MuJoCo license and third-party notices are included.

Browser checks require the Node dependency and a compatible local Chromium installation:

```bash
npm install
npx playwright install chromium
node -p "require('playwright').chromium.executablePath()"
```

Set `ARX_CHROME` to the executable path printed by the last command when running the checks. This explicit override avoids the test tool's original local-cache fallback. Do not copy that fallback directory from the original workspace. Browser test tools use `ARX_PYTHON` and `ARX_FFPROBE` when specified; otherwise they use `python3` and `ffprobe` from `PATH`.

The recorded renderer used a Linux EGL/Mesa environment. A working GPU driver or a suitable software OpenGL implementation is an external system dependency. The browser scripts preserve the tested ANGLE/EGL launch configuration and software-renderer settings. A different driver or operating system may need environment setup; the archived image-parity result describes the recorded implementation, not every graphics driver.

The film compositor loads these DejaVu fonts from the Linux system:

```text
/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf
```

Install the host's DejaVu font package at these locations before rendering. Fonts and browser binaries are not copied into the source archive. They are system dependencies, not private workspace files.

## Rebuilding and verifying

Follow `../ARX-6-P5-Engineering/README-P5.md` for native CAD, model generation and physical validation. Then follow `P5-SHADER-README.md` for capture, native surface checks, shader assembly, replay generation, rendering and viewer construction. The source includes `source/player-base.html`, both base and P5 lighting files, and the engineering `render/original/core.glsl` dependency. The retained base template and core are build inputs; old P3/P4 deliverables and obsolete rebuild commands are excluded.

`reports/source-dependency-path-fix.json` records the two minimal input-path corrections from the obsolete model alias to `ARX-6-P5.xml`. All four consumed nest records were identical. That source-only correction did not change the captured geometry or rerun any physical or rendered output. `tools/paths.py` retains its historical `P2`/`P3` import names and legacy environment overrides for compatibility while its defaults use the current sibling directories.

The final delivery uses two complementary browser reports. `viewer-tests-p5.json` covers shader startup, replay, inspection, live physics, recovery and capped mobile-view defaults. `viewer-media-baseline-p5.json` records that page's executable and non-media assets before the final film embedding. `viewer-media-tests-p5.json` verifies the final MP4, poster, film-first startup and exact identity of the retained executable/non-media inputs. The final check requires the baseline HTML hash to match the functional report. Do not overwrite the baseline after changing executable inputs and present it as earlier evidence.

For a new rebuild, a functional baseline can be captured and tested before film embedding, followed by the final media-only check, or the complete functional test can be rerun against the completed viewer. Review the explicit test commands and their scope in the shader README and source. The delivery consistency verifier checks the archived release's exact accepted hashes; it is an identity check for this release and is expected to reject an intentionally changed design.

The source archive includes all 14 final chapter MP4 files, sidecar build records, per-frame audits and actual middle-frame JPEGs. It includes the joined film, final viewer, native hero image and film contact sheet. `film/concat.txt` is excluded because it is a temporary absolute-path join list; the director regenerates it from the current location. Preview images, caches, benchmark files and browser UI screenshots are excluded. The three `transport-*.png` files are direct framebuffer comparison images, not browser screenshots.

## Engineering status retained by this release

This is an engineering prototype. The ordinary physical validation result is **21/24 passing**, with three unresolved adverse stop criteria: `power_loss_3.2`, `weak_spring_double_delay_3.2`, and `weak_spring_double_delay_7.2`. The final nominal trace, CAD, model and controller remain frozen. The source package retains the failed-case evidence, high-rate checks and rejected retiming experiments. A successful package or media audit does not change that engineering status or establish emergency-safe hardware. See the root delivery README and the engineering fault review for the exact limitations.
