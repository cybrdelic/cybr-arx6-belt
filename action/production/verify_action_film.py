#!/usr/bin/env python3
"""Independent verification of the P5 continuous action film.

This program performs no shader rendering and changes no model, trace or film.
It checks the actual joined decoder output against the three source segments,
compares per-frame render states against the saved continuous dynamics, and
extracts a small contact sheet from the final encoded video for visual review.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('ARX_ACTION_SOURCE_ROOT',
                            str(BASE / 'source' / 'ARX-6-P5-Source'))).resolve()
ENGINEERING = SOURCE / 'ARX-6-P5-Engineering' / 'integration'
SHADER = SOURCE / 'ARX-6-P5-Shader'
REPORTS = BASE / 'reports'
WIDTH, HEIGHT, FPS, DURATION, FRAME_COUNT = 1920, 1080, 24, 30, 720
HEX256 = re.compile(r'^[0-9a-f]{64}$')
ACCEPTED = {
    'shader': '1af43fd29a719fca74317e9f2bf63b47707e46117a994f2b477517c3df1908f5',
    'trace_10s': '14b8dcd0e13c6baa7fd9236c23bf9712ad763afcad370f489c08f907a56e5a66',
    'trace_30s': 'b7a2358597ee4735affc3a9baff7bffcdc3644cd0bca8dc52eb0d25d0dd5e2b7',
    'original_video': '2a657d5dc7fdd89b05054aae1a0c5212af07f4699de5127a945fcb5adecda084',
    'original_report': '911544f39e838d504ef6a1b7a0c0e574eb0f1ac60bc9624394258f76f18f8338',
    'original_audit': 'c677f5196ad4d5c2965cc455105b66f3c0c2c6962f92eb249420ae3c54643dae',
    'original_director': '222f6f8e9e5dfc335fd2312fa5dfd57dd1b061d4f101e25668b5b82ba39b2923',
    'renderer': 'bbc289ca2c5661f63a43c3efeef5b3165a1704cba874082f53895f6562b4885b',
    'table_packer': '2a1ca8becd51c12d84a0fc9b57b1af5707d2635b43bbe03f089891ebd41ba88c',
    'action_director': '957b9e36957716c8509c63bd0af34ff23a3253f846591db3f4afaefec66555ad',
    'inspection': 'a556c371e7671c1cc3e006dc95cce1d801798f7920a8cfc499e45eb647521304',
}
PROVENANCE = {
    'xml_sha256': 'ARX-6-P5.xml',
    'controller_sha256': 'controller.mjs',
    'safety_sha256': 'safety.mjs',
    'parameters_sha256': 'parameters.json',
    'geometry_sha256': 'geometry-meshes.json',
    'collision_proxies_sha256': 'p5_collision_proxies.json',
    'cad_mass_properties_sha256': 'mass_properties.json',
}
RENDER_INDICES = [1, 2, 3, 4, 5, 6, 13, 14, 15, 16, 17, 18, 19, 20, 21]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


class Findings:
    def __init__(self):
        self.checks = []

    def check(self, name, condition, detail=None):
        item = {'name': name, 'passed': bool(condition)}
        if detail is not None:
            item['detail'] = detail
        self.checks.append(item)
        return bool(condition)

    @property
    def passed(self):
        return bool(self.checks) and all(row['passed'] for row in self.checks)


def independent_state(frames, physical_time):
    """Interpolate the recorded rows independently of the renderer module."""
    position = int(np.searchsorted(frames[:, 0], physical_time, side='right'))
    position = max(1, min(position, len(frames) - 1))
    left, right = frames[position - 1], frames[position]
    alpha = max(0., min(1., (physical_time - left[0]) / (right[0] - left[0])))
    state = left + alpha * (right - left)
    quaternion_left, quaternion_right = left[18:22], right[18:22].copy()
    if np.dot(quaternion_left, quaternion_right) < 0.:
        quaternion_right *= -1.
    quaternion = quaternion_left + alpha * (quaternion_right - quaternion_left)
    state[18:22] = quaternion / np.linalg.norm(quaternion)
    return state


def verify_sources(findings):
    paths = {
        'shader': SHADER / 'ARX-6-P5-Live.glsl',
        'trace_10s': ENGINEERING / 'results/nominal.json',
        'trace_30s': ENGINEERING / 'results/nominal_30s.json',
        'original_video': SHADER / 'film/01-operation.mp4',
        'original_report': SHADER / 'film/01-operation.json',
        'original_audit': SHADER / 'film/01-operation-frame-audit.json',
        'original_director': SHADER / 'tools/film_p5.py',
        'renderer': SHADER / 'tools/egl_render.py',
        'table_packer': SHADER / 'tools/shader_tables.py',
        'action_director': BASE / 'production/action_film.py',
        'inspection': SHADER / 'reports/inspection-parts.json',
    }
    hashes = {key: digest(path) for key, path in paths.items()}
    findings.check('All accepted source and original operation hashes match',
                   hashes == ACCEPTED, hashes)
    trace = read_json(paths['trace_30s'])
    short = read_json(paths['trace_10s'])
    frames = np.asarray(trace['frames'], dtype=np.float64)
    short_frames = np.asarray(short['frames'], dtype=np.float64)
    findings.check('The continuous trace has 3601 finite states with 47 fields',
                   frames.shape == (3601, 47) and np.isfinite(frames).all())
    findings.check('The saved physical timeline is continuous at 120 Hz through 30 seconds',
                   frames[0, 0] == 0. and abs(frames[-1, 0] - 30) < 1e-9
                   and np.max(np.abs(np.diff(frames[:, 0]) - 1 / 120)) < 1e-10)
    findings.check('All first-10-second state fields exactly match the accepted original',
                   short_frames.shape == (1201, 47)
                   and np.array_equal(frames[:1201], short_frames))
    actual = {key: digest(ENGINEERING / relative) for key, relative in PROVENANCE.items()}
    findings.check('All seven physical input hashes match the continuous solve',
                   actual == trace['metrics']['provenance'], actual)
    repeated = []
    for offset in (1200, 2400):
        count = int(np.sum(np.all(frames[offset:offset + 1200, 1:]
                                 == frames[:1200, 1:], axis=1)))
        repeated.append({'cycle_start_seconds': offset / 120,
                         'exact_repeated_state_rows': count})
    findings.check('Later cycles contain freshly integrated state rather than repeated rows',
                   all(item['exact_repeated_state_rows'] == 0 for item in repeated), repeated)
    return {'paths': paths, 'hashes': hashes, 'trace': trace, 'frames': frames,
            'physical_hashes': actual, 'original_report': read_json(paths['original_report']),
            'original_audit': read_json(paths['original_audit'])}


def probe_video(path, frames, seconds, findings, label):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-show_chapters',
         '-of', 'json', str(path)], check=True, text=True, capture_output=True)
    data = json.loads(result.stdout)
    streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
    if len(streams) != 1:
        raise ValueError(f'{label}: expected exactly one video stream')
    video = streams[0]
    rate, nominal = Fraction(video['avg_frame_rate']), Fraction(video['r_frame_rate'])
    duration = float(video.get('duration', data['format']['duration']))
    container_duration = float(data['format']['duration'])
    header_frames = int(video.get('nb_frames', 0))
    findings.check(f'{label}: native 1920×1080, 24 fps, expected duration and frame count',
                   video['width'] == WIDTH and video['height'] == HEIGHT
                   and rate == FPS and nominal == FPS and header_frames == frames
                   and abs(duration - seconds) < .001
                   and abs(container_duration - seconds) < .001)
    return {'width': video['width'], 'height': video['height'], 'fps': str(rate),
            'nominal_fps': str(nominal), 'frames_declared': header_frames,
            'duration_seconds': duration, 'container_duration_seconds': container_duration,
            'codec': video['codec_name'], 'pixel_format': video['pix_fmt'],
            'chapters': data.get('chapters', [])}


def decode_hashes(path, expected_frames, findings, label):
    """Decode every frame and retain actual planar YUV SHA256 hashes."""
    started = time.monotonic()
    command = ['ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-err_detect', 'explode',
               '-threads', '2', '-i', str(path), '-map', '0:v:0', '-an',
               '-vsync', '0', '-f', 'framemd5', '-hash', 'sha256', '-']
    result = subprocess.run(command, capture_output=True, text=True)
    records, timebase = [], None
    for line in result.stdout.splitlines():
        if line.startswith('#tb 0:'):
            timebase = Fraction(line.split(':', 1)[1].strip())
        elif line and not line.startswith('#'):
            values = [v.strip() for v in line.split(',')]
            if len(values) != 6:
                raise ValueError(f'{label}: unexpected decoder hash record')
            records.append({'stream': int(values[0]), 'dts': int(values[1]),
                            'pts': int(values[2]), 'duration': int(values[3]),
                            'bytes': int(values[4]), 'sha256': values[5]})
    findings.check(f'{label}: complete error-free decode of every video frame',
                   result.returncode == 0 and not result.stderr.strip()
                   and len(records) == expected_frames
                   and all(HEX256.fullmatch(row['sha256']) for row in records),
                   {'exit_code': result.returncode, 'decoded_frames': len(records),
                    'errors': result.stderr.strip()[:2000]})
    timing_good = timebase is not None and all(
        Fraction(row['pts']) * timebase == Fraction(i, FPS)
        and Fraction(row['duration']) * timebase == Fraction(1, FPS)
        for i, row in enumerate(records))
    findings.check(f'{label}: decoded presentation timestamps advance without gaps or resets',
                   timing_good, {'timebase': str(timebase)})
    return {'decoded_frames': len(records), 'decode_seconds': time.monotonic() - started,
            'timebase': str(timebase), 'records': records,
            'frame_hashes_sha256': json_digest([r['sha256'] for r in records])}


def make_contact_sheet(video, destination):
    samples = [12, 48, 87, 252, 288, 327, 492, 528, 567]
    labels = ['Approach / grip', 'Carry', 'Release'] * 3
    expression = '+'.join(f'eq(n,{i})' for i in samples)
    with tempfile.TemporaryDirectory(prefix='arx-action-contact-') as temporary:
        pattern = Path(temporary) / 'frame-%02d.png'
        command = ['ffmpeg', '-hide_banner', '-v', 'error', '-xerror', '-threads', '2',
                   '-i', str(video), '-vf', f"select='{expression}'", '-vsync', '0',
                   '-frames:v', str(len(samples)), str(pattern)]
        subprocess.run(command, check=True, capture_output=True)
        tile_w, tile_h, gap, margin, title_h, label_h = 512, 288, 12, 20, 78, 42
        sheet = Image.new('RGB', (margin * 2 + 3 * tile_w + 2 * gap,
                                 title_h + 3 * (tile_h + label_h) + 2 * gap + margin),
                          '#10171c')
        draw = ImageDraw.Draw(sheet)
        font_dir = Path('/usr/share/fonts/truetype/dejavu')
        def font(size, bold=False):
            try:
                return ImageFont.truetype(str(font_dir / ('DejaVuSans-Bold.ttf' if bold
                                                         else 'DejaVuSans.ttf')), size)
            except OSError:
                return ImageFont.load_default()
        draw.text((margin, 14), 'ARX / 6 · P5 — Continuous action film',
                  font=font(26, True), fill='#eee6d5')
        draw.text((margin, 48), 'Actual decoded final frames · 30 seconds · 1920 × 1080 · 24 fps',
                  font=font(17), fill='#adbdc8')
        items = []
        for i, frame in enumerate(samples):
            image_path = Path(temporary) / f'frame-{i + 1:02d}.png'
            with Image.open(image_path) as image:
                image.load()
                if image.size != (WIDTH, HEIGHT):
                    raise ValueError('Contact extraction did not retain native frame size')
                pixel_hash = hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()
                thumbnail = ImageOps.contain(image.convert('RGB'), (tile_w, tile_h),
                                            Image.Resampling.LANCZOS)
            x = margin + (i % 3) * (tile_w + gap)
            y = title_h + (i // 3) * (tile_h + label_h + gap)
            sheet.paste(thumbnail, (x, y))
            draw.rectangle((x, y + tile_h, x + tile_w, y + tile_h + label_h), fill='#1b272e')
            draw.text((x + 10, y + tile_h + 10), f'{frame / FPS:05.2f}s  {labels[i]}',
                      font=font(19), fill='#e1ceb2')
            items.append({'frame': frame, 'time_seconds': frame / FPS,
                          'decoded_rgb_sha256': pixel_hash})
        destination.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(destination, quality=94, subsampling=0)
    return {'file': str(destination), 'sha256': digest(destination),
            'size': list(sheet.size), 'samples': items,
            'source': 'Decoded directly from the final joined MP4, without shader rerendering.'}


# The action-director metadata adapter is defined below. It deliberately keeps
# physical interpolation, decoding, ordering and original-source checks above
# independent of the renderer implementation.


def load_director():
    path = BASE / 'production/action_film.py'
    spec = importlib.util.spec_from_file_location('arx_verified_action_director', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module.ActionDirector()


def check_metadata(record, expected, findings, label):
    keys = ['revision', 'width', 'height', 'fps', 'duration_seconds', 'frames',
            'camera_samples', 'shadow_samples', 'quality', 'exposure', 'playback_speed',
            'shader_sha256', 'trajectory_sha256', 'short_trajectory_sha256',
            'short_trajectory_prefix_exact', 'physical_sources', 'director_sha256',
            'renderer_sha256', 'table_packer_sha256', 'inspection_director_sha256',
            'inspection_sha256', 'shots']
    differences = [key for key in keys if record.get(key) != expected.get(key)]
    findings.check(f'{label}: source hashes, settings and shot plan match the frozen director',
                   not differences, {'mismatched_fields': differences})


def check_numeric_transport(record, expected, findings, label):
    actual = record.get('numeric_table_transport', {})
    keys = ['tables', 'table_count', 'bytes', 'tail_padding_bytes', 'sha256']
    layout = actual.get('driver_layout_checks', [])
    findings.check(f'{label}: exact geometry table bytes and driver layout match the frozen shader',
                   all(actual.get(k) == expected.get(k) for k in keys)
                   and actual.get('driver_block_bytes') == expected['bytes']
                   and bool(layout)
                   and all(item.get('passed') for item in layout if item.get('active')))


def check_audit(entries, shot, director, frames, findings):
    start = shot * 240
    maximum_state_error = maximum_render_error = maximum_camera_error = 0.
    maximum_time_error = 0.
    malformed = []
    camera_records = []
    hashes = []
    for local, entry in enumerate(entries):
        index, t = start + local, (start + local) / FPS
        if entry.get('global_frame') != index:
            malformed.append(f'frame {index}: nonsequential global index')
        if shot and entry.get('shot_frame') != local:
            malformed.append(f'frame {index}: nonsequential shot index')
        if not shot and entry.get('frame') != local:
            malformed.append(f'frame {index}: original index differs')
        actual_time = float(entry.get('physical_time_s', math.nan))
        if not math.isfinite(actual_time):
            malformed.append(f'frame {index}: missing/nonfinite physical time')
        else:
            maximum_time_error = max(maximum_time_error, abs(actual_time - t))
        expected_state = independent_state(frames, t)
        if shot:
            actual_state = np.asarray(entry.get('state_47', []), dtype=float)
            if actual_state.shape != (47,) or not np.isfinite(actual_state).all():
                malformed.append(f'frame {index}: missing/nonfinite full physical state')
            else:
                delta = np.abs(expected_state - actual_state)
                maximum_state_error = max(maximum_state_error, float(delta.max()))
                maximum_render_error = max(maximum_render_error,
                                           float(delta[RENDER_INDICES].max()))
        if any(entry.get(k) != 0 for k in ['group', 'explode', 'cutaway', 'mechanism_rad']):
            malformed.append(f'frame {index}: visual inspection controls are active')
        raw_hash = entry.get('raw_shader_rgb8_sha256', '')
        if not isinstance(raw_hash, str) or not HEX256.fullmatch(raw_hash):
            malformed.append(f'frame {index}: invalid raw image hash')
        hashes.append(raw_hash)
        intended = director.state(shot, t)
        current_camera = {}
        for key, expected in [('camera_origin', intended['origin']),
                              ('camera_target', intended['target'])]:
            actual = np.asarray(entry.get(key, []), dtype=float)
            if actual.shape != (3,) or not np.isfinite(actual).all():
                malformed.append(f'frame {index}: invalid {key}')
            else:
                maximum_camera_error = max(maximum_camera_error,
                                           float(np.abs(actual - expected).max()))
                current_camera[key] = actual.tolist()
        # The original 0–10s audit did not store focal. Its accepted source hash
        # binds that uniform; every newly rendered frame explicitly records it.
        focal = float(entry.get('camera_focal', intended['focal'] if shot == 0 else math.nan))
        if not math.isfinite(focal) or focal <= 0:
            malformed.append(f'frame {index}: invalid focal value')
        else:
            maximum_camera_error = max(maximum_camera_error, abs(focal - intended['focal']))
            current_camera['camera_focal'] = focal
        camera_records.append(current_camera)
    good = len(entries) == 240 and not malformed and maximum_time_error < 1e-10
    good = good and maximum_state_error < 5e-12 and maximum_camera_error < 1e-9
    findings.check(f'Shot {shot}: every audit frame matches absolute time, physical state and camera',
                   good, {'frame_count': len(entries), 'maximum_time_error_seconds': maximum_time_error,
                          'maximum_full_state_error': maximum_state_error,
                          'maximum_render_state_error': maximum_render_error,
                          'maximum_camera_error': maximum_camera_error,
                          'errors': malformed[:20]})
    return {'frames': len(entries), 'raw_hashes': hashes,
            'unique_raw_shader_frames': len(set(hashes)),
            'camera_records_sha256': json_digest(camera_records),
            'maximum_full_state_error': maximum_state_error,
            'maximum_render_state_error': maximum_render_error,
            'maximum_camera_error': maximum_camera_error,
            'maximum_time_error_seconds': maximum_time_error}


def verify_final(sources, module, director, findings):
    from shader_tables import convert
    expected = director.metadata()
    build_path = REPORTS / 'action-build.json'
    audit_path = REPORTS / 'action-frame-audit.json'
    build, all_entries = read_json(build_path), read_json(audit_path)
    final_path = BASE / 'ARX-6-P5-In-Action-1080p.mp4'
    final_hash = digest(final_path)
    check_metadata(build, expected, findings, 'Final film')
    findings.check('Joined file and combined audit match the final build identities',
                   build.get('file') == final_path.name and build.get('sha256') == final_hash
                   and build.get('bytes') == final_path.stat().st_size
                   and build.get('audit_sha256') == digest(audit_path))
    findings.check('All 720 physical frame times advance from 0 to 29.958333 seconds without resets',
                   isinstance(all_entries, list) and len(all_entries) == FRAME_COUNT
                   and all(entry.get('global_frame') == i
                           and abs(entry.get('physical_time_s', -999) - i / FPS) < 1e-10
                           for i, entry in enumerate(all_entries)))
    _, _, table_info = convert((SHADER / 'ARX-6-P5-Live.glsl').read_text())
    original = sources['original_report']
    original_keys = {
        'width': WIDTH, 'height': HEIGHT, 'fps': FPS, 'frames': 240,
        'camera_samples': 1, 'shadow_samples': 1, 'quality': 1,
        'shader_sha256': ACCEPTED['shader'], 'trajectory_sha256': ACCEPTED['trace_10s'],
        'director_sha256': ACCEPTED['original_director'], 'renderer_sha256': ACCEPTED['renderer'],
        'table_packer_sha256': ACCEPTED['table_packer'], 'inspection_sha256': ACCEPTED['inspection'],
        'output_sha256': ACCEPTED['original_video'],
    }
    findings.check('Reused operation report binds the accepted helpers, shader, trace and settings',
                   all(original.get(k) == v for k, v in original_keys.items()))
    check_numeric_transport(original, table_info, findings, 'Original operation chapter')
    segments = []
    expected_combined = []
    expected_sources = []
    decoded_concatenation = []
    raw_concatenation = []
    for shot in range(3):
        if shot == 0:
            movie = sources['paths']['original_video']
            report_path = sources['paths']['original_report']
            sidecar_audit_path = sources['paths']['original_audit']
            sidecar = original
            entries = [{'global_frame': i, **item, 'source': 'original operation chapter'}
                       for i, item in enumerate(sources['original_audit'])]
        else:
            entry = module.SHOTS[shot]
            movie = BASE / 'render' / (entry['id'] + '.mp4')
            report_path = movie.with_suffix('.json')
            sidecar_audit_path = movie.with_name(entry['id'] + '-frame-audit.json')
            sidecar, entries = read_json(report_path), read_json(sidecar_audit_path)
            check_metadata(sidecar, expected, findings, f'Shot {shot}')
            findings.check(f'Shot {shot}: correct ten-second range and byte identities',
                           sidecar.get('shot') == shot and sidecar.get('start_s') == shot * 10
                           and sidecar.get('end_s') == (shot + 1) * 10
                           and sidecar.get('shot_frames') == 240
                           and sidecar.get('output_sha256') == digest(movie)
                           and sidecar.get('bytes') == movie.stat().st_size
                           and sidecar.get('audit_sha256') == digest(sidecar_audit_path))
            check_numeric_transport(sidecar, table_info, findings, f'Shot {shot}')
            fit = director.camera_audit(shot)
            stored_fit = sidecar.get('camera_fit', {})
            findings.check(f'Shot {shot}: sampled camera fit remains within the stated frame limits',
                           fit['passed'] and stored_fit.get('passed')
                           and all(abs(float(stored_fit.get(k, -999)) - float(fit[k])) < 1e-9
                                   for k in ['maximum_abs_ndc_x', 'maximum_abs_ndc_y', 'minimum_depth']))
        expected_combined.extend(entries)
        expected_sources.append({'shot': shot, 'reused': shot == 0, 'file_sha256': digest(movie),
                                 'source_report_sha256': digest(report_path),
                                 'source_audit_sha256': digest(sidecar_audit_path)})
        audit = check_audit(entries, shot, director, sources['frames'], findings)
        raw_concatenation.extend(audit.pop('raw_hashes'))
        findings.check(f'Shot {shot}: sidecar unique raw-frame count agrees with actual audit',
                       sidecar.get('unique_raw_shader_frames') == audit['unique_raw_shader_frames'])
        media = probe_video(movie, 240, 10, findings, f'Shot {shot}')
        decoded = decode_hashes(movie, 240, findings, f'Shot {shot}')
        decoded_concatenation.extend(row['sha256'] for row in decoded.pop('records'))
        segments.append({'shot': shot, 'file': str(movie), 'sha256': digest(movie),
                         'report_sha256': digest(report_path), 'audit_sha256': digest(sidecar_audit_path),
                         'audit': audit, 'media': media, 'decode': decoded})
    findings.check('The final combined audit is the exact ordered concatenation of source audits',
                   all_entries == expected_combined)
    findings.check('The final shot-source identities match the three verified segments in order',
                   build.get('shot_sources') == expected_sources)
    counter = Counter(raw_concatenation)
    findings.check('Final raw-frame unique count agrees with the complete audit',
                   build.get('unique_raw_shader_frames') == len(counter))
    repeated_blocks = [(i, j) for i in range(3) for j in range(i + 1, 3)
                       if raw_concatenation[i * 240:(i + 1) * 240]
                       == raw_concatenation[j * 240:(j + 1) * 240]]
    findings.check('No ten-second raw-image block is replayed as another segment',
                   not repeated_blocks, repeated_blocks)
    media = probe_video(final_path, FRAME_COUNT, DURATION, findings, 'Joined action film')
    chapters = media['chapters']
    findings.check('Joined chapter tags cover the three intended shots in order',
                   len(chapters) == 3 and all(
                       abs(float(chapter['start_time']) - i * 10) < 1e-8
                       and abs(float(chapter['end_time']) - (i + 1) * 10) < 1e-8
                       and chapter.get('tags', {}).get('title') == module.SHOTS[i]['title']
                       for i, chapter in enumerate(chapters)))
    decoded = decode_hashes(final_path, FRAME_COUNT, findings, 'Joined action film')
    joined_hashes = [row['sha256'] for row in decoded.pop('records')]
    findings.check('Every decoded joined frame equals its corresponding source-segment frame',
                   joined_hashes == decoded_concatenation)
    contact = make_contact_sheet(final_path, REPORTS / 'action-contact-sheet.jpg')
    findings.check('All nine requested samples were decoded from the actual final film',
                   len(contact['samples']) == 9)
    return {'file': str(final_path), 'sha256': final_hash, 'bytes': final_path.stat().st_size,
            'build_report_sha256': digest(build_path), 'combined_audit_sha256': digest(audit_path),
            'media': media, 'decode': decoded, 'segments': segments, 'contact_sheet': contact,
            'raw_frame_statistics': {
                'frames': len(raw_concatenation), 'unique': len(counter),
                'duplicate_frames': len(raw_concatenation) - len(counter),
                'largest_identical_frame_group': max(counter.values(), default=0),
                'repeated_ten_second_blocks': repeated_blocks,
                'policy': 'Identical stationary RGB8 frames are counted, not automatically failed. A repeated whole ten-second block fails.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true',
                        help='Check frozen sources and director state mapping without requiring completed video')
    args = parser.parse_args()
    findings = Findings()
    report = {'revision': 'P5', 'checked_utc': datetime.now(timezone.utc).isoformat(),
              'verifier_sha256': digest(Path(__file__)), 'passed': False,
              'final_film_verified': False, 'expected': {'width': WIDTH, 'height': HEIGHT,
              'fps': FPS, 'seconds': DURATION, 'frames': FRAME_COUNT},
              'scope': 'Computational verification of a nominal action film. The three existing adverse stop failures remain unresolved.'}
    error = None
    try:
        sources = verify_sources(findings)
        module, director = load_director()
        report['source_hashes'] = sources['hashes']
        report['physical_input_hashes'] = sources['physical_hashes']
        if args.preflight:
            errors = []
            for shot, t in [(0, 0.), (0, 9.958333333333334), (1, 10.), (1, 15.5),
                            (1, 19.958333333333332), (2, 20.), (2, 25.5), (2, 29.958333333333332)]:
                actual = np.asarray(director.state(shot, t)['state'])
                errors.append(float(np.abs(actual - independent_state(sources['frames'], t)).max()))
            findings.check('Director state mapping agrees with independent interpolation across all three shots',
                           max(errors) < 5e-12, {'maximum_error': max(errors)})
        else:
            report.update(verify_final(sources, module, director, findings))
            report['final_film_verified'] = findings.passed
        report['passed'] = findings.passed
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        findings.check('Verification completed without an exception', False, error)
    report['checks'] = findings.checks
    report['error'] = error
    report['failed_checks'] = [x['name'] for x in findings.checks if not x['passed']]
    path = REPORTS / ('action-verification-preflight.json' if args.preflight else 'action-film-verification.json')
    write_json(path, report)
    print(json.dumps({'report': str(path), 'passed': report['passed'],
                      'final_film_verified': report['final_film_verified'],
                      'checks': len(findings.checks), 'failed_checks': report['failed_checks'],
                      'error': error}, indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
