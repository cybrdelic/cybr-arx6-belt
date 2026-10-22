#!/usr/bin/env python3
"""A continuous, real-time P5 action film from the verified 30-second solve.

The first ten seconds reuse the original operation chapter, whose complete
physical-state prefix is proven equal. Later shots evaluate the same frozen
procedural shader at successive states of the 30-second trace. No pose loop,
explosion, section, or additional mechanism rotation is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ACTION = HERE.parent
SOURCE = Path(os.environ.get("ARX_ACTION_SOURCE_ROOT", str(ACTION / "source/ARX-6-P5-Source"))).resolve()
SHADER_ROOT = SOURCE / "ARX-6-P5-Shader"
ENGINEERING = SOURCE / "ARX-6-P5-Engineering"
OUTPUT = ACTION / "render"
os.environ.setdefault("MESA_SHADER_CACHE_DIR", str(ACTION / ".mesa-action-cache"))
sys.path.insert(0, str(SHADER_ROOT / "tools"))
from portable_fonts import load_font
from egl_render import EGLRenderer, physical_state, apply, aces
from film_p5 import Director as InspectionDirector

LIVE_SHA256 = "1af43fd29a719fca74317e9f2bf63b47707e46117a994f2b477517c3df1908f5"
TRACE_SHA256 = "b7a2358597ee4735affc3a9baff7bffcdc3644cd0bca8dc52eb0d25d0dd5e2b7"
WIDTH, HEIGHT, FPS, DURATION = 1920, 1080, 24, 30
SHOTS = [
    {"index": 0, "start": 0, "end": 10, "id": "01-whole-arm", "title": "Whole arm — transfers 1 and 2", "reused": True},
    {"index": 1, "start": 10, "end": 20, "id": "02-elevated", "title": "Elevated view — transfers 3 and 4", "azimuth": [0.96, 1.10], "elevation": 0.40, "reused": False},
    {"index": 2, "start": 20, "end": 30, "id": "03-front", "title": "Front view — transfers 5 and 6", "azimuth": [0.19, 0.34], "elevation": 0.30, "reused": False},
]


def hashfile(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonfile(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def smooth(value: float) -> float:
    value = float(np.clip(value, 0, 1))
    return value * value * (3 - 2 * value)


def direction(azimuth: float, elevation: float) -> np.ndarray:
    return np.array([math.sin(azimuth) * math.cos(elevation), math.sin(elevation), math.cos(azimuth) * math.cos(elevation)])


def basis(eye_direction: np.ndarray):
    forward = -eye_direction
    right = np.cross(forward, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return right, up, eye_direction


class ActionDirector:
    def __init__(self):
        self.shader_path = SHADER_ROOT / "ARX-6-P5-Live.glsl"
        self.trajectory_path = ENGINEERING / "integration/results/nominal_30s.json"
        self.short_trajectory_path = ENGINEERING / "integration/results/nominal.json"
        if hashfile(self.shader_path) != LIVE_SHA256:
            raise RuntimeError("The accepted P5 shader has changed")
        if hashfile(self.trajectory_path) != TRACE_SHA256:
            raise RuntimeError("The verified thirty-second trajectory has changed")
        self.trace = json.loads(self.trajectory_path.read_text())
        self.frames = np.asarray(self.trace["frames"], dtype=np.float64)
        short = np.asarray(json.loads(self.short_trajectory_path.read_text())["frames"], dtype=np.float64)
        if self.frames.shape != (3601, 47) or short.shape != (1201, 47):
            raise RuntimeError("Unexpected exported physical state shape")
        if not np.array_equal(self.frames[:len(short)], short):
            raise RuntimeError("Original ten-second footage does not match the longer solve")
        if not np.isfinite(self.frames).all() or not np.all(np.diff(self.frames[:, 0]) > 0):
            raise RuntimeError("Trajectory must contain finite states in strictly increasing time")
        if abs(self.frames[0, 0]) > 1e-12 or abs(self.frames[-1, 0] - 30) > 1e-8:
            raise RuntimeError("The continuous trajectory does not cover 0–30 seconds")
        if not self.trace["metrics"].get("all_checks_pass"):
            raise RuntimeError("The nominal thirty-second simulation failed its checks")
        expected = {
            "xml_sha256": "ARX-6-P5.xml", "controller_sha256": "controller.mjs",
            "safety_sha256": "safety.mjs", "parameters_sha256": "parameters.json",
            "geometry_sha256": "geometry-meshes.json", "collision_proxies_sha256": "p5_collision_proxies.json",
            "cad_mass_properties_sha256": "mass_properties.json",
        }
        provenance = self.trace["metrics"]["provenance"]
        self.physical_sources = {}
        for key, filename in expected.items():
            current = hashfile(ENGINEERING / "integration" / filename)
            if current != provenance.get(key):
                raise RuntimeError("Trace no longer matches " + filename)
            self.physical_sources[filename] = current
        self.inspection = InspectionDirector()
        self.envelopes = {}
        self.cameras = {}

    def physical(self, t: float) -> np.ndarray:
        if not 0 <= t <= DURATION:
            raise ValueError("Physical time must stay within the uninterrupted thirty-second trace")
        return physical_state(self.frames, t)

    def prepare_camera(self, shot: int):
        if shot in self.cameras:
            return self.cameras[shot]
        entry = SHOTS[shot]
        if entry["reused"]:
            raise ValueError("Shot zero retains the verified original camera")
        points = np.concatenate([
            self.inspection.points(self.physical(t), 0, 0.0)
            for t in np.linspace(entry["start"], entry["end"], 41)
        ])
        target = (points.min(axis=0) + points.max(axis=0)) * 0.5
        focal = 3.3
        # Fit one fixed distance against all sampled poses and the entire orbit.
        # The camera does not breathe in response to the moving arm.
        distance = 0.6
        for az in np.linspace(*entry["azimuth"], 17):
            eye = direction(float(az), entry["elevation"])
            right, up, back = basis(eye)
            relative = points - target
            x, y, z = relative @ right, relative @ up, relative @ back
            distance = max(distance, float(np.max(z + focal * np.abs(y) / 0.80)), float(np.max(z + focal * np.abs(x) / ((16 / 9) * 0.86))))
        distance += 0.10
        result = {"target": target, "distance": distance, "focal": focal}
        self.envelopes[shot] = points
        self.cameras[shot] = result
        return result

    def state(self, shot: int, t: float) -> dict:
        entry = SHOTS[shot]
        if not entry["start"] <= t <= entry["end"]:
            raise ValueError("Time is outside this shot")
        if shot == 0:
            result = self.inspection.state(0, min(t, 9.999))
            result["state"] = self.physical(t)
            result["physical_time"] = t
            return result
        camera = self.prepare_camera(shot)
        phase = smooth((t - entry["start"]) / (entry["end"] - entry["start"]))
        az0, az1 = entry["azimuth"]
        eye = direction(az0 + (az1 - az0) * phase, entry["elevation"])
        return {
            "state": self.physical(t), "physical_time": t,
            "group": 0, "explode": 0.0, "cutaway": 0.0, "mechanism": 0.0,
            "origin": camera["target"] + eye * camera["distance"],
            "target": camera["target"].copy(), "focal": camera["focal"],
        }

    def camera_audit(self, shot: int) -> dict:
        extrema = {"maximum_abs_ndc_x": 0.0, "maximum_abs_ndc_y": 0.0, "minimum_depth": float("inf")}
        entry = SHOTS[shot]
        for t in np.linspace(entry["start"], entry["end"], 81):
            view = self.state(shot, float(t))
            points = self.inspection.points(view["state"], 0, 0.0)
            back = view["origin"] - view["target"]
            back /= np.linalg.norm(back)
            right, up, _ = basis(back)
            relative = points - view["origin"]
            depth = relative @ -back
            ndc_x = view["focal"] * (relative @ right) / depth / (16 / 9)
            ndc_y = view["focal"] * (relative @ up) / depth
            extrema["maximum_abs_ndc_x"] = max(extrema["maximum_abs_ndc_x"], float(np.max(np.abs(ndc_x))))
            extrema["maximum_abs_ndc_y"] = max(extrema["maximum_abs_ndc_y"], float(np.max(np.abs(ndc_y))))
            extrema["minimum_depth"] = min(extrema["minimum_depth"], float(np.min(depth)))
        return {"shot": shot, "sampled_times": 81, **extrema, "passed": extrema["minimum_depth"] > 0 and extrema["maximum_abs_ndc_x"] < 0.90 and extrema["maximum_abs_ndc_y"] < 0.85}

    def metadata(self, width=WIDTH, height=HEIGHT):
        return {
            "revision": "P5", "purpose": "Continuous arm action",
            "width": width, "height": height, "fps": FPS,
            "duration_seconds": DURATION, "frames": DURATION * FPS,
            "camera_samples": 1, "shadow_samples": 1, "quality": 1,
            "exposure": 0.38, "playback_speed": 1.0,
            "shader_sha256": hashfile(self.shader_path),
            "trajectory_sha256": hashfile(self.trajectory_path),
            "short_trajectory_sha256": hashfile(self.short_trajectory_path),
            "short_trajectory_prefix_exact": True,
            "physical_sources": self.physical_sources,
            "director_sha256": hashfile(Path(__file__)),
            "renderer_sha256": hashfile(SHADER_ROOT / "tools/egl_render.py"),
            "table_packer_sha256": hashfile(SHADER_ROOT / "tools/shader_tables.py"),
            "inspection_director_sha256": hashfile(SHADER_ROOT / "tools/film_p5.py"),
            "inspection_sha256": hashfile(SHADER_ROOT / "reports/inspection-parts.json"),
            "shots": SHOTS,
            "method": "Frozen CAD-derived procedural fragment shader evaluated at recorded physical states. Original matching first ten seconds reused; seconds ten through thirty newly rendered. Physical time advances continuously at normal speed; no frame loop or pose reset.",
            "engineering_status": "Nominal action passes. Broader ordinary scenario suite remains 21/24 with three unresolved adverse stop criteria.",
        }


def set_uniforms(renderer, view):
    apply(renderer, view["state"])
    for key, value in [
        ("u_time", float(view["physical_time"])), ("u_frame", 0), ("u_samples", 1),
        ("u_exposure", 0.38), ("u_inspect", 0), ("u_part", 0),
        ("u_explode", 0.0), ("u_cutaway", 0.0), ("u_mechanism", 0.0),
        ("u_camera_override", 1), ("u_camera_origin", view["origin"]),
        ("u_camera_target", view["target"]), ("u_camera_focal", view["focal"]),
        ("u_aperture", 0.0),
    ]:
        renderer.uniform(key, value)


def phase_caption(t: float):
    transfer = min(6, int(t // 5) + 1)
    phase_time = t - (transfer - 1) * 5
    for until, label in [(0.65, "Approach"), (1.0, "Grip"), (1.65, "Lift"), (2.75, "Carry"), (3.4, "Lower"), (3.75, "Release"), (4.45, "Retract"), (5.01, "Settle")]:
        if phase_time < until:
            break
    route = "A → B" if transfer % 2 else "B → A"
    return f"TRANSFER {transfer:02d} / 06   ·   {route}   ·   {label.upper()}"


def caption(pixels: np.ndarray, t: float):
    im = Image.fromarray(pixels, "RGB")
    width, height = im.size
    scale = width / 1920
    over = Image.new("RGBA", im.size)
    draw = ImageDraw.Draw(over)
    title = load_font(max(12, round(34 * scale)), bold=True)
    mono = load_font(max(8, round(17 * scale)), mono=True)
    for row in range(round(126 * scale)):
        opacity = round(170 * (1 - row / max(1, 126 * scale)) ** 1.8)
        draw.line((0, row, width, row), fill=(9, 12, 15, opacity))
    for row in range(round(92 * scale)):
        opacity = round(170 * (1 - row / max(1, 92 * scale)) ** 1.8)
        draw.line((0, height - 1 - row, width, height - 1 - row), fill=(9, 12, 15, opacity))
    x = round(58 * scale)
    draw.text((x, round(36 * scale)), "ARX / 6 · In action", font=title, fill=(234, 237, 236, 255))
    draw.text((x, round(84 * scale)), phase_caption(t), font=mono, fill=(190, 183, 164, 255))
    bottom = height - round(48 * scale)
    draw.text((x, bottom), "RECORDED PHYSICS · 1× SPEED", font=mono, fill=(167, 178, 185, 255))
    right_text = f"{t:05.2f} / 30.00 s"
    box = draw.textbbox((0, 0), right_text, font=mono)
    draw.text((width - x - (box[2] - box[0]), bottom), right_text, font=mono, fill=(167, 178, 185, 255))
    return np.asarray(Image.alpha_composite(im.convert("RGBA"), over).convert("RGB"))


def render_shot(director: ActionDirector, renderer: EGLRenderer, shot: int, preview: bool, times: list[float] | None):
    entry = SHOTS[shot]
    if entry["reused"]:
        raise ValueError("Shot 0 is retained from the already rendered operation chapter")
    metadata = director.metadata(renderer.w, renderer.h)
    metadata["numeric_table_transport"] = renderer.table_info
    fit = director.camera_audit(shot)
    if not fit["passed"]:
        raise RuntimeError("Camera fit failed: " + json.dumps(fit))
    metadata["camera_fit"] = fit
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if preview:
        for t in times or [entry["start"] + 2.5, entry["start"] + 3.5, entry["start"] + 7.5]:
            view = director.state(shot, t)
            set_uniforms(renderer, view)
            raw = np.uint8(np.clip(aces(renderer.draw()) * 255 + 0.5, 0, 255))
            path = OUTPUT / f"{entry['id']}-preview-{t:05.2f}.png"
            Image.fromarray(caption(raw, t)).save(path)
            jsonfile(path.with_suffix(".json"), {**metadata, "physical_time_s": t, "camera_origin": view["origin"].tolist(), "camera_target": view["target"].tolist(), "raw_shader_rgb8_sha256": hashlib.sha256(raw.tobytes()).hexdigest(), "output_sha256": hashfile(path)})
            print(json.dumps({"preview": str(path), "physical_time_s": t}), flush=True)
        return
    if (renderer.w, renderer.h) != (WIDTH, HEIGHT):
        raise ValueError("Final shots must be native 1920×1080")
    dest = OUTPUT / (entry["id"] + ".mp4")
    sidecar = dest.with_suffix(".json")
    audit_path = OUTPUT / (entry["id"] + "-frame-audit.json")
    frame_count = int((entry["end"] - entry["start"]) * FPS)
    identity_keys = ["width", "height", "fps", "camera_samples", "shadow_samples", "quality", "exposure", "shader_sha256", "trajectory_sha256", "director_sha256", "renderer_sha256", "table_packer_sha256", "inspection_director_sha256", "inspection_sha256"]
    if dest.exists() and sidecar.exists() and audit_path.exists():
        previous = json.loads(sidecar.read_text())
        if all(previous.get(k) == metadata.get(k) for k in identity_keys) and previous.get("shot_frames") == frame_count and previous.get("output_sha256") == hashfile(dest) and previous.get("audit_sha256") == hashfile(audit_path):
            print(json.dumps({"skip_verified_shot": shot, "file": str(dest)}), flush=True)
            return
    temporary = OUTPUT / (entry["id"] + ".partial.mp4")
    encoder = subprocess.Popen([
        "ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-", "-an",
        "-c:v", "libx264", "-threads", "2", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary),
    ], stdin=subprocess.PIPE)
    audit = []
    started = time.monotonic()
    try:
        for local_frame in range(frame_count):
            global_frame = int(entry["start"] * FPS) + local_frame
            t = global_frame / FPS
            view = director.state(shot, t)
            set_uniforms(renderer, view)
            raw = np.uint8(np.clip(aces(renderer.draw()) * 255 + 0.5, 0, 255))
            raw_hash = hashlib.sha256(raw.tobytes()).hexdigest()
            state = np.asarray(view["state"], dtype=np.float64)
            audit.append({
                "global_frame": global_frame, "shot_frame": local_frame,
                "physical_time_s": t, "state_47": state.tolist(),
                "group": 0, "explode": 0.0, "cutaway": 0.0, "mechanism_rad": 0.0,
                "camera_origin": view["origin"].tolist(), "camera_target": view["target"].tolist(), "camera_focal": view["focal"],
                "raw_shader_rgb8_sha256": raw_hash,
            })
            pixels = caption(raw, t)
            encoder.stdin.write(pixels.tobytes())
            if local_frame in (0, 60, 84, 120, 180, 204, frame_count - 1):
                Image.fromarray(pixels).save(OUTPUT / f"{entry['id']}-frame-{local_frame:04d}.jpg", quality=94)
            if local_frame % FPS == 0 or local_frame == frame_count - 1:
                print(json.dumps({"shot": shot, "frame": local_frame + 1, "frames": frame_count, "physical_time_s": t, "elapsed_s": round(time.monotonic() - started, 2)}), flush=True)
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise RuntimeError("Video encoding failed")
        temporary.replace(dest)
        jsonfile(audit_path, audit)
        jsonfile(sidecar, {**metadata, "shot": shot, "start_s": entry["start"], "end_s": entry["end"], "shot_frames": frame_count, "unique_raw_shader_frames": len({x["raw_shader_rgb8_sha256"] for x in audit}), "elapsed_s": time.monotonic() - started, "output_sha256": hashfile(dest), "audit_sha256": hashfile(audit_path), "bytes": dest.stat().st_size})
    finally:
        if encoder.poll() is None:
            encoder.kill()
            encoder.wait()


def join(director: ActionDirector):
    metadata = director.metadata()
    first = SHADER_ROOT / "film/01-operation.mp4"
    first_report = json.loads(first.with_suffix(".json").read_text())
    first_audit_path = SHADER_ROOT / "film/01-operation-frame-audit.json"
    first_audit = json.loads(first_audit_path.read_text())
    required = {"width": WIDTH, "height": HEIGHT, "fps": FPS, "frames": 240, "camera_samples": 1, "shadow_samples": 1, "quality": 1, "shader_sha256": LIVE_SHA256, "trajectory_sha256": hashfile(director.short_trajectory_path)}
    for k, value in required.items():
        if first_report.get(k) != value:
            raise RuntimeError("Reused opening chapter mismatch: " + k)
    if hashfile(first) != first_report.get("output_sha256") or len(first_audit) != 240:
        raise RuntimeError("Reused opening chapter bytes/audit mismatch")
    for i, frame in enumerate(first_audit):
        if abs(frame["physical_time_s"] - i / FPS) > 1e-10 or any(abs(frame.get(k, 0)) > 1e-10 for k in ("group", "explode", "cutaway", "mechanism_rad")):
            raise RuntimeError("Opening chapter is not continuous physical action")
    parts = [first]
    audits = [{"global_frame": i, **entry, "source": "original operation chapter"} for i, entry in enumerate(first_audit)]
    reports = [{"shot": 0, "reused": True, "file_sha256": hashfile(first), "source_report_sha256": hashfile(first.with_suffix(".json")), "source_audit_sha256": hashfile(first_audit_path)}]
    for shot in (1, 2):
        entry = SHOTS[shot]
        path = OUTPUT / (entry["id"] + ".mp4")
        report_path = path.with_suffix(".json")
        audit_path = OUTPUT / (entry["id"] + "-frame-audit.json")
        report = json.loads(report_path.read_text())
        for key in ["width", "height", "fps", "camera_samples", "shadow_samples", "quality", "shader_sha256", "trajectory_sha256", "director_sha256", "renderer_sha256", "table_packer_sha256", "inspection_director_sha256", "inspection_sha256"]:
            if report.get(key) != metadata[key]:
                raise RuntimeError(f"Stale shot {shot}: {key}")
        if report["shot_frames"] != 240 or hashfile(path) != report["output_sha256"] or hashfile(audit_path) != report["audit_sha256"]:
            raise RuntimeError("Shot bytes or audit changed")
        parts.append(path)
        audits.extend(json.loads(audit_path.read_text()))
        reports.append({"shot": shot, "reused": False, "file_sha256": hashfile(path), "source_report_sha256": hashfile(report_path), "source_audit_sha256": hashfile(audit_path)})
    if len(audits) != 720 or any(x["global_frame"] != i or abs(x["physical_time_s"] - i / FPS) > 1e-10 for i, x in enumerate(audits)):
        raise RuntimeError("The final audit does not prove continuous thirty-second physical time")
    OUTPUT.mkdir(exist_ok=True)
    listing = OUTPUT / "action-concat.txt"
    listing.write_text("\n".join("file '" + str(p) + "'" for p in parts) + "\n")
    ffmeta = OUTPUT / "action-chapters.ffmeta"
    ffmeta.write_text(";FFMETADATA1\ntitle=ARX-6 P5 — In Action\nartist=Procedural CAD renderer\n" + "".join(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={s['start'] * 1000}\nEND={s['end'] * 1000}\ntitle={s['title']}\n" for s in SHOTS))
    destination = ACTION / "ARX-6-P5-In-Action-1080p.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(ffmeta), "-map_metadata", "1", "-map_chapters", "1", "-c", "copy", "-movflags", "+faststart", str(destination)], check=True)
    final_audit = ACTION / "reports/action-frame-audit.json"
    jsonfile(final_audit, audits)
    report = {**metadata, "file": destination.name, "bytes": destination.stat().st_size, "sha256": hashfile(destination), "shot_sources": reports, "unique_raw_shader_frames": len({a["raw_shader_rgb8_sha256"] for a in audits}), "audit_sha256": hashfile(final_audit)}
    jsonfile(ACTION / "reports/action-build.json", report)
    print(json.dumps({"file": str(destination), "sha256": report["sha256"], "bytes": report["bytes"], "frames": 720, "duration_seconds": 30}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot", type=int, choices=[1, 2], action="append")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--time", type=float, action="append")
    parser.add_argument("--width", type=int, default=WIDTH)
    parser.add_argument("--height", type=int, default=HEIGHT)
    parser.add_argument("--join", action="store_true")
    parser.add_argument("--audit-cameras", action="store_true")
    args = parser.parse_args()
    director = ActionDirector()
    if args.join:
        join(director)
        return
    if args.audit_cameras:
        result = [director.camera_audit(shot) for shot in args.shot or (1, 2)]
        jsonfile(ACTION / "reports/action-camera-audit.json", result)
        print(json.dumps(result), flush=True)
        if not all(r["passed"] for r in result):
            raise SystemExit(1)
        return
    defines = "#define AA 1\n#define P3_QUALITY 1\n#define P5_SHADOW_SAMPLES 1\n#define CAPTURE 1\n"
    renderer = EGLRenderer(args.width, args.height, director.shader_path.read_text(), defines, geometry_buffers=True)
    print(json.dumps({"renderer": renderer.info, "compile_seconds": renderer.compile_seconds, "table_count": renderer.table_info["table_count"], "table_bytes": renderer.table_info["bytes"]}), flush=True)
    try:
        for shot in args.shot or (1, 2):
            render_shot(director, renderer, shot, args.preview, args.time)
    finally:
        renderer.close()


if __name__ == "__main__":
    main()
