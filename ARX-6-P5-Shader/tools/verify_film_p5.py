#!/usr/bin/env python3
"""Verify completed P5 film outputs and assemble their actual middle frames.

Run after all 14 chapter renders finish. No rendering, encoding, shader edits,
or repair is performed. A missing joined MP4 permits chapter-only inspection,
but final_film_verified stays false until the joined output is checked.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont, ImageOps

from film_p5 import CHAPTERS, Director, metadata
from shader_tables import convert

ROOT = Path(__file__).resolve().parents[1]
FILM = ROOT / 'film'
JOINED = ROOT / 'ARX-6-P5-Inspection-1080p.mp4'
WIDTH, HEIGHT, FPS, TOTAL_SECONDS, TOTAL_FRAMES = 1920, 1080, 24, 72, 1728
SETTINGS = {'width': WIDTH, 'height': HEIGHT, 'fps': FPS,
            'camera_samples': 1, 'shadow_samples': 1, 'quality': 1}
SOURCE_KEYS = ['revision', 'shader_sha256', 'trajectory_sha256',
               'inspection_sha256', 'director_sha256', 'renderer_sha256',
               'table_packer_sha256', 'duration_seconds', 'chapters']
HEX256 = re.compile(r'[0-9a-f]{64}')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def relative(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def probe(path, expected_frames, expected_seconds):
    command = ['ffprobe', '-v', 'error', '-threads', '2', '-count_frames',
               '-show_streams', '-show_format', '-show_chapters',
               '-of', 'json', str(path)]
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    data = json.loads(result.stdout)
    videos = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
    if len(videos) != 1:
        raise ValueError(f'{path.name}: expected one video stream, got {len(videos)}')
    video = videos[0]
    count = int(video['nb_read_frames'])
    average = Fraction(video['avg_frame_rate'])
    nominal = Fraction(video['r_frame_rate'])
    duration = float(video.get('duration', data['format']['duration']))
    container_duration = float(data['format']['duration'])
    errors = []
    for condition, message in [
        (video.get('width') == WIDTH and video.get('height') == HEIGHT,
         f'frame size is {video.get("width")}x{video.get("height")}'),
        (average == FPS and nominal == FPS,
         f'frame rates are avg={average}, nominal={nominal}'),
        (count == expected_frames, f'ffprobe counted {count} frames'),
        (abs(duration - expected_seconds) <= .001,
         f'video duration is {duration} seconds'),
        (abs(container_duration - expected_seconds) <= .001,
         f'container duration is {container_duration} seconds'),
    ]:
        if not condition:
            errors.append(f'{path.name}: {message}')
    declared = video.get('nb_frames')
    if declared not in (None, 'N/A') and int(declared) != expected_frames:
        errors.append(f'{path.name}: header declares {declared} frames')
    return {'width': video['width'], 'height': video['height'],
            'fps': str(average), 'nominal_fps': str(nominal),
            'counted_frames': count, 'duration_seconds': duration,
            'container_duration_seconds': container_duration,
            'codec': video.get('codec_name'), 'pixel_format': video.get('pix_fmt'),
            'chapters': data.get('chapters', []), 'errors': errors}


def audit_frames(path, chapter_index, chapter, director, chapter_report):
    entries = read_json(path)
    expected_count = chapter['duration'] * FPS
    errors, hashes = [], []
    scalar_error = camera_error = 0.
    groups = set()
    if not isinstance(entries, list):
        raise ValueError(f'{path.name}: audit is not a list')
    if len(entries) != expected_count:
        errors.append(f'{path.name}: {len(entries)} entries, expected {expected_count}')
    controls = {k: [] for k in ('explode', 'cutaway', 'mechanism_rad', 'physical_time_s')}
    start = director.timing[chapter_index]['start']
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f'{path.name}: frame {index} is not an object')
            continue
        if entry.get('frame') != index:
            errors.append(f'{path.name}: nonsequential frame index at {index}')
        h = entry.get('raw_shader_rgb8_sha256', '')
        if not isinstance(h, str) or HEX256.fullmatch(h) is None:
            errors.append(f'{path.name}: invalid raw shader hash at frame {index}')
        else:
            hashes.append(h)
        actual_group = entry.get('group')
        if actual_group != chapter['group']:
            errors.append(f'{path.name}: wrong inspection group at frame {index}')
        if isinstance(actual_group, int):
            groups.add(actual_group)
        expected = director.state(chapter_index, index / FPS)
        scalars = {'film_time_s': start + index / FPS,
                   'physical_time_s': expected['physical_time'],
                   'explode': expected['explode'], 'cutaway': expected['cutaway'],
                   'mechanism_rad': expected['mechanism']}
        for key, value in scalars.items():
            actual = float(entry.get(key, math.nan))
            if not math.isfinite(actual):
                errors.append(f'{path.name}: nonfinite/missing {key} at frame {index}')
            else:
                scalar_error = max(scalar_error, abs(actual - float(value)))
                if key in controls:
                    controls[key].append(actual)
        for key, value in [('camera_origin', expected['origin']),
                           ('camera_target', expected['target'])]:
            actual = entry.get(key)
            if not isinstance(actual, list) or len(actual) != 3:
                errors.append(f'{path.name}: missing {key} vector at frame {index}')
                continue
            for a, b in zip(actual, value):
                a = float(a)
                if not math.isfinite(a):
                    errors.append(f'{path.name}: nonfinite camera at frame {index}')
                else:
                    camera_error = max(camera_error, abs(a - float(b)))
    unique = len(set(hashes))
    if unique != expected_count:
        errors.append(f'{path.name}: {unique} unique raw images, expected {expected_count}')
    if chapter_report.get('unique_raw_shader_frames') != unique:
        errors.append(f'{path.name}: unique-image count differs from chapter report')
    if not hashes or chapter_report.get('first_render_sha256') != hashes[0]:
        errors.append(f'{path.name}: first raw image hash differs from chapter report')
    if not hashes or chapter_report.get('last_render_sha256') != hashes[-1]:
        errors.append(f'{path.name}: last raw image hash differs from chapter report')
    if scalar_error > 1e-8 or camera_error > 1e-7:
        errors.append(f'{path.name}: audited state/camera differs from current director')
    return ({'file': relative(path), 'sha256': digest(path), 'frames': len(entries),
             'unique_raw_shader_frames': unique, 'duplicate_raw_frames': len(hashes) - unique,
             'groups': sorted(groups), 'maximum_scalar_error': scalar_error,
             'maximum_camera_coordinate_error': camera_error,
             'control_ranges': {key: [min(values), max(values)] if values else None
                                for key, values in controls.items()}, 'errors': errors}, hashes)


def check_provenance(record, expected, table_info, name):
    errors = []
    for key in SOURCE_KEYS + list(SETTINGS):
        if record.get(key) != expected[key]:
            errors.append(f'{name}: stale/mismatched {key}')
    numeric = record.get('numeric_table_transport', {})
    for key in ('sha256', 'bytes', 'table_count', 'tail_padding_bytes', 'tables'):
        if numeric.get(key) != table_info[key]:
            errors.append(f'{name}: numeric-table {key} differs from current literal tables')
    if numeric.get('driver_block_bytes') != table_info['bytes']:
        errors.append(f'{name}: missing or mismatched reflected numeric-block size')
    layout = numeric.get('driver_layout_checks', [])
    if not layout or any(x.get('active') and not x.get('passed') for x in layout):
        errors.append(f'{name}: missing or failing driver numeric-table layout checks')
    return errors


def middle_image(chapter, frames):
    index = frames // 2
    path = FILM / f'{chapter["id"]}-frame-{index:04d}.jpg'
    with Image.open(path) as image:
        image.load()
        if image.format != 'JPEG' or image.size != (WIDTH, HEIGHT):
            raise ValueError(f'{path.name}: expected an actual 1920x1080 final JPEG')
    return {'file': relative(path), 'frame': index, 'local_time_s': index / FPS,
            'sha256': digest(path), 'width': WIDTH, 'height': HEIGHT}


def contact_sheet(rows, destination):
    columns, thumb_w, thumb_h = 3, 640, 360
    gap, margin, header, label = 16, 24, 84, 64
    count_rows = math.ceil(len(rows) / columns)
    width = margin * 2 + columns * thumb_w + (columns - 1) * gap
    height = header + count_rows * (thumb_h + label) + (count_rows - 1) * gap + margin
    sheet = Image.new('RGB', (width, height), '#11181d')
    draw = ImageDraw.Draw(sheet)
    font_root = Path('/usr/share/fonts/truetype/dejavu')
    def font(size, bold=False):
        try:
            return ImageFont.truetype(str(font_root / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), size)
        except OSError:
            return ImageFont.load_default()
    draw.text((margin, 18), 'ARX / 6 · P5 — Final film contact sheet', fill='#eee6d5', font=font(28, True))
    draw.text((margin, 55), '14 actual chapter middle frames · 1920 × 1080 originals · 24 fps · 72 seconds', fill='#aebcc6', font=font(17))
    for i, row in enumerate(rows):
        column, line = i % columns, i // columns
        x, y = margin + column * (thumb_w + gap), header + line * (thumb_h + label + gap)
        source = ROOT / row['middle_frame']['file']
        with Image.open(source) as image:
            tile = ImageOps.contain(image.convert('RGB'), (thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(tile, (x + (thumb_w - tile.width) // 2, y))
        draw.rectangle((x, y + thumb_h, x + thumb_w, y + thumb_h + label), fill='#1c272e')
        title = f'{i + 1:02d}  {row["title"]}'
        draw.text((x + 12, y + thumb_h + 8), title, fill='#e3ceb0', font=font(21, True))
        mode = 'PHYSICAL OPERATION' if i == 0 else 'INSPECTION'
        note = f'{mode} · group {row["group"]} · frame {row["middle_frame"]["frame"]} · film {row["middle_frame"]["film_time_s"]:.2f}s'
        draw.text((x + 12, y + thumb_h + 38), note, fill='#b8c6cf', font=font(16))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.tmp')
    options = {'format': 'PNG'} if destination.suffix.lower() == '.png' else {'format': 'JPEG', 'quality': 94, 'subsampling': 0}
    sheet.save(temporary, **options)
    temporary.replace(destination)
    return {'file': relative(destination), 'sha256': digest(destination),
            'width': width, 'height': height, 'chapters': len(rows),
            'sources': [row['middle_frame']['file'] for row in rows],
            'source_kind': 'Final actual middle-frame JPEGs; no preview images used.'}


def decode_joined(path):
    command = ['ffmpeg', '-hide_banner', '-v', 'error', '-xerror',
               '-err_detect', 'explode', '-threads', '2', '-i', str(path),
               '-map', '0:v:0', '-an', '-progress', 'pipe:1', '-nostats',
               '-f', 'null', '-']
    start = time.monotonic()
    result = subprocess.run(command, text=True, capture_output=True)
    frame_counts = [int(line.split('=', 1)[1]) for line in result.stdout.splitlines()
                    if line.startswith('frame=')]
    frames = frame_counts[-1] if frame_counts else 0
    return {'exit_code': result.returncode, 'decoded_frames': frames,
            'seconds': round(time.monotonic() - start, 3),
            'passed': result.returncode == 0 and frames == TOTAL_FRAMES and not result.stderr.strip(),
            'errors': result.stderr.strip()[:4000]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'reports/film-verification-p5.json')
    parser.add_argument('--contact-sheet', type=Path, default=ROOT / 'reports/film-contact-sheet-p5.jpg')
    args = parser.parse_args()
    started = time.monotonic()
    report = {'revision': 'P5', 'checked_utc': datetime.now(timezone.utc).isoformat(),
              'verifier_sha256': digest(Path(__file__)), 'passed': False,
              'final_film_verified': False, 'expected': {**SETTINGS, 'chapters': 14,
               'frames': TOTAL_FRAMES, 'duration_seconds': TOTAL_SECONDS},
              'chapters': [], 'joined': {'present': JOINED.is_file()}, 'errors': [],
              'scope': 'Current-source provenance, completed MP4 hashes and decoded metadata, per-frame audit/state consistency and image-hash uniqueness, semantic group/spring coverage, and final middle-frame contact sheet. Raw shader hashes precede captions/encoding and cannot be reconstructed from lossy MP4/JPEG images; group coverage does not prove every part is unoccluded in one frame.'}
    errors = report['errors']
    missing = []
    for chapter in CHAPTERS:
        frames = chapter['duration'] * FPS
        for path in [FILM / (chapter['id'] + '.mp4'), FILM / (chapter['id'] + '.json'),
                     FILM / (chapter['id'] + '-frame-audit.json'),
                     FILM / f'{chapter["id"]}-frame-{frames // 2:04d}.jpg']:
            if not path.is_file():
                missing.append(relative(path))
    if missing:
        report.update(status='incomplete_chapters', missing=missing)
        errors.append('All 14 completed chapter files, reports, audits, and final middle JPEGs are required. No media checks or contact-sheet generation were attempted.')
        write_json(args.report, report)
        print(json.dumps({'passed': False, 'status': report['status'], 'missing_files': len(missing), 'report': str(args.report)}))
        return 2
    try:
        for tool in ('ffprobe', 'ffmpeg'):
            if shutil.which(tool) is None:
                raise RuntimeError(f'{tool} is required')
        if len(CHAPTERS) != 14 or sum(c['duration'] for c in CHAPTERS) != TOTAL_SECONDS:
            raise ValueError('The current director does not define the expected 14 chapters / 72 seconds')
        director = Director()  # Also checks current engineering/trace provenance.
        expected = metadata(director, FPS, WIDTH, HEIGHT, ROOT / 'ARX-6-P5-Live.glsl')
        expected.update(SETTINGS)
        _, _, table_info = convert((ROOT / 'ARX-6-P5-Live.glsl').read_text())
        report['current_source_hashes'] = {key: expected[key] for key in SOURCE_KEYS if key.endswith('sha256')}
        report['numeric_table_sha256'] = table_info['sha256']
        all_hashes, locations = [], defaultdict(list)
        groups = set()
        for ci, chapter in enumerate(CHAPTERS):
            chapter_errors = []
            path = FILM / (chapter['id'] + '.mp4')
            sidecar = path.with_suffix('.json')
            record = read_json(sidecar)
            frames = chapter['duration'] * FPS
            chapter_errors.extend(check_provenance(record, expected, table_info, sidecar.name))
            actual_hash = digest(path)
            if actual_hash != record.get('output_sha256'):
                chapter_errors.append(f'{path.name}: MP4 SHA256 differs from completed chapter report')
            if path.stat().st_size != record.get('bytes'):
                chapter_errors.append(f'{path.name}: MP4 byte size differs from report')
            if record.get('chapter') != ci or record.get('frames') != frames:
                chapter_errors.append(f'{sidecar.name}: wrong chapter index or frame count')
            media = probe(path, frames, chapter['duration'])
            chapter_errors.extend(media.pop('errors'))
            media.pop('chapters')
            audit, hashes = audit_frames(FILM / (chapter['id'] + '-frame-audit.json'), ci, chapter, director, record)
            chapter_errors.extend(audit.pop('errors'))
            for fi, h in enumerate(hashes):
                locations[h].append(f'{chapter["id"]}:{fi}')
            all_hashes.extend(hashes)
            groups.update(audit['groups'])
            middle = middle_image(chapter, frames)
            middle['film_time_s'] = director.timing[ci]['start'] + middle['local_time_s']
            row = {'id': chapter['id'], 'title': chapter['title'], 'group': chapter['group'],
                   'file': relative(path), 'sha256': actual_hash, 'bytes': path.stat().st_size,
                   'report_sha256': digest(sidecar), 'media': media, 'audit': audit,
                   'middle_frame': middle, 'passed': not chapter_errors, 'errors': chapter_errors[:30]}
            report['chapters'].append(row)
            errors.extend(chapter_errors)
            print(json.dumps({'chapter': chapter['id'], 'passed': row['passed'],
                              'frames': media['counted_frames'], 'unique_raw_frames': audit['unique_raw_shader_frames']}), flush=True)
        counts = Counter(all_hashes)
        duplicate_groups = [where for where in locations.values() if len(where) > 1]
        counted_frames = sum(c['media']['counted_frames'] for c in report['chapters'])
        report['totals'] = {'chapters': len(report['chapters']), 'ffprobe_frames': counted_frames,
                            'chapter_duration_seconds': sum(c['media']['duration_seconds'] for c in report['chapters']),
                            'audit_frames': len(all_hashes), 'unique_raw_shader_frames': len(counts),
                            'duplicate_raw_frames': len(all_hashes) - len(counts),
                            'duplicate_locations': duplicate_groups[:20]}
        if counted_frames != TOTAL_FRAMES or len(all_hashes) != TOTAL_FRAMES or len(counts) != TOTAL_FRAMES:
            errors.append('Overall frame/audit/unique-image counts are not all 1728')
        wanted_groups = set(range(1, 12))
        if not wanted_groups.issubset(groups):
            errors.append(f'Missing semantic groups: {sorted(wanted_groups - groups)}')
        springs = director.meta.get('dynamic_parts', [])
        spring_coverage = []
        for group, chapter_id in [(8, '06-shoulder-balance'), (9, '07-elbow-balance')]:
            names = [s['name'] for s in springs if s.get('group') == group]
            chapter = next((c for c in report['chapters'] if c['id'] == chapter_id), None)
            good = len(names) == 2 and chapter is not None and chapter['audit']['groups'] == [group]
            if good:
                a, b = chapter['audit']['control_ranges']['physical_time_s']
                good = b > a
            spring_coverage.append({'group': group, 'chapter': chapter_id, 'springs': names, 'passed': good})
            if not good:
                errors.append(f'Incomplete paired-spring inspection coverage for group {group}')
        inventory = director.meta.get('inventory_totals', {})
        if inventory != {'rigid_parts': 385, 'dynamic_springs': 4, 'total_components': 389}:
            errors.append('Inspection inventory is not the expected 385 rigid parts plus four springs')
        report['coverage'] = {'groups_present': sorted(groups), 'required_groups': sorted(wanted_groups),
                              'inventory': inventory, 'spring_chapters': spring_coverage}
        if not errors:
            report['contact_sheet'] = contact_sheet(report['chapters'], args.contact_sheet)
        if JOINED.is_file():
            build_path = ROOT / 'reports/film-build.json'
            build = read_json(build_path)
            errors.extend(check_provenance(build, expected, table_info, build_path.name))
            joined_hash = digest(JOINED)
            if build.get('sha256') != joined_hash or build.get('bytes') != JOINED.stat().st_size:
                errors.append('Joined MP4 hash/size differs from film-build.json')
            if build.get('file') != JOINED.name or build.get('frames') != TOTAL_FRAMES:
                errors.append('Joined film report has wrong filename or frame count')
            joined_media = probe(JOINED, TOTAL_FRAMES, TOTAL_SECONDS)
            errors.extend(joined_media.pop('errors'))
            chapter_tags = joined_media.pop('chapters')
            if len(chapter_tags) != 14:
                errors.append(f'Joined MP4 has {len(chapter_tags)} chapter tags, expected 14')
            for i, tag in enumerate(chapter_tags[:14]):
                timing = director.timing[i]
                if (abs(float(tag['start_time']) - timing['start']) > .001 or
                        abs(float(tag['end_time']) - timing['end']) > .001 or
                        tag.get('tags', {}).get('title') != timing['title']):
                    errors.append(f'Joined MP4 chapter tag {i + 1} differs from current director')
            print(json.dumps({'action': 'decode_complete_joined_film', 'file': JOINED.name}), flush=True)
            decoded = decode_joined(JOINED)
            if not decoded['passed']:
                errors.append('Full joined MP4 decode failed or did not yield 1728 frames')
            report['joined'] = {'present': True, 'file': JOINED.name, 'sha256': joined_hash,
                                'bytes': JOINED.stat().st_size, 'report_sha256': digest(build_path),
                                'media': joined_media, 'chapter_tags': len(chapter_tags),
                                'full_decode': decoded}
        report['passed'] = not errors
        report['final_film_verified'] = not errors and JOINED.is_file()
        report['status'] = 'verified' if report['final_film_verified'] else 'chapters_verified_join_pending' if not errors else 'failed'
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError,
            RuntimeError, subprocess.SubprocessError) as exc:
        detail = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            detail += '\n' + (exc.stderr or '')[:4000]
        errors.append(detail)
        report['status'] = 'failed'
    report['seconds'] = round(time.monotonic() - started, 3)
    report['error_count'] = len(errors)
    if len(errors) > 50:
        report['errors'] = errors[:50] + [f'{len(errors) - 50} additional failures omitted.']
    write_json(args.report, report)
    print(json.dumps({'passed': report['passed'], 'final_film_verified': report['final_film_verified'],
                      'status': report['status'], 'errors': report['error_count'],
                      'report': str(args.report),
                      'contact_sheet': report.get('contact_sheet', {}).get('file')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
