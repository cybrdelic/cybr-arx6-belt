#!/usr/bin/env python3
"""Check consistency of the completed P5 deliverables without rerunning physics.

This checks artifact identity, provenance and the recorded verification scope.
It deliberately does not change or turn green the three failed dynamics cases.
Keep the Shader and Engineering directories adjacent when reproducing it.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import base64
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ENG = ROOT.parent / 'ARX-6-P5-Engineering' / 'integration'
REPORTS = ROOT / 'reports'

EXPECTED = {
    'generate_cad_p2.py': '0c8474173cc5ec70164cae5050a9aa7decbf6e30f14cb7f67564e9fbdaad58f7',
    'spec.json': '606e09b482d4c5f838ee49daced4b574f8260450dd350735e95422c2d666a8ac',
    'geometry-meshes.json': '838768d0473b4ba2ed25be1e1b0d5c34c3ac643dce99e140bb415d99f2103208',
    'mass_properties.json': '98f98c0a6dd1b39dac65f967fb0ebe682beb003aa29052f2924337fb07f8e024',
    'ARX-6-P5.xml': 'b5d8a969db3742f01afae169039358b18182e57605f3f39382b9dfb20ad68ac5',
    'controller.mjs': 'e8fbe68be5a83f02f6e0b194c573b69bcf34f098de31358fd0e236ad4795107d',
    'parameters.json': '7127b02dc62029a39f58b5e69e97aa932867d560282f98e5aa62b05f0d558c70',
    'safety.mjs': 'a71184c3b9e296ddc367218396027b621371d1e5ef17aec32dbcd3e5e9a41a63',
    'p5_collision_proxies.json': 'f351530da734766721dfd95582d764552d0f92f291a62ad07080dcbd888b528f',
    'results/nominal.json': '14b8dcd0e13c6baa7fd9236c23bf9712ad763afcad370f489c08f907a56e5a66',
}
SHADER_SHA = '1af43fd29a719fca74317e9f2bf63b47707e46117a994f2b477517c3df1908f5'
FAILED_CASES = ['power_loss_3.2', 'weak_spring_double_delay_3.2',
                'weak_spring_double_delay_7.2']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    checks = []
    def check(name, condition, detail=None):
        checks.append({'name': name, 'passed': bool(condition), 'detail': detail})
    report = {
        'revision': 'P5', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Completed deliverable identity and evidence consistency; not a new physical qualification.',
        'checks': checks, 'passed': False,
    }
    try:
        actual = {name: sha(ENG / name) for name in EXPECTED}
        check('All ten frozen physical inputs match', actual == EXPECTED, actual)
        live = ROOT / 'ARX-6-P5-Live.glsl'
        check('Final procedural shader matches the accepted source', sha(live) == SHADER_SHA)
        trace = read(ENG / 'results/nominal.json')
        summary = read(ENG / 'reports/P5-dynamics-summary.json')
        check('The same fresh nominal trace has 1201 samples and 10 seconds',
              len(trace['frames']) == 1201 and abs(trace['frames'][-1][0] - 10) < 1e-8 and
              summary['nominal_trace_sha256'] == EXPECTED['results/nominal.json'])
        check('Three adverse failures remain explicitly unresolved',
              summary['ordinary_scenario_count'] == 24 and summary['ordinary_scenario_passes'] == 21 and
              summary['all_ordinary_scenarios_pass'] is False and
              summary['unresolved_ordinary_cases'] == FAILED_CASES, FAILED_CASES)
        check('All four deliberate failure controls retain their expected outcomes',
              summary['negative_control_outcomes_pass'] and len(summary['negative_control_outcomes']) == 4)
        report['engineering_acceptance'] = {
            'ordinary_scenarios_passed': 21, 'ordinary_scenarios_total': 24,
            'all_ordinary_scenarios_pass': False, 'unresolved_ordinary_cases': FAILED_CASES,
            'status': summary['overall_status'],
        }
        mechanical = read(ENG / 'reports/P5-mechanical-validation.json')
        stops = read(ENG / 'reports/P5-corrected-joint-stop-check.json')
        posed = read(ENG / 'reports/P5-posed-interface-check.json')
        assembly = read(ENG / 'reports/P5-overall-assembly.json')
        check('52 native interface, 8 stop and 26 posed checks pass',
              len(mechanical['native_interface_checks']) == 52 and mechanical['native_checks_pass'] and
              len(stops['checks']) == 8 and stops['all_pass'] and len(posed['checks']) == 26 and posed['all_pass'])
        native_step = ENG / 'cad/ARX-6-P5-assembled-nominal-t2p5.step'
        check('Native overall STEP is the verified posed assembly',
              sha(native_step) == posed['overall_step_sha256'] and assembly['part_count'] == 384 and
              assembly['imported_solid_count'] == 399 and assembly['imported_valid'] and
              posed['trace_sha256'] == EXPECTED['results/nominal.json'])
        capture = read(REPORTS / 'csg-capture.json')
        geometry = read(REPORTS / 'geometry-surface-check.json')
        check('Rendered geometry derives from the frozen CAD and specification',
              capture['generator_sha256'] == EXPECTED['generate_cad_p2.py'] and
              capture['spec_sha256'] == EXPECTED['spec.json'] and
              geometry['matched'] == geometry['passed_objects'] == 385 and
              geometry['surface_probes'] == 70392 and geometry['max_distance_mm'] < .001)
        replay = read(REPORTS / 'replay-build.json')
        check('Portable replay embeds the final shader and physical trace',
              replay['shader_sha256'] == sha(ROOT / 'ARX-6-P5-Replay.glsl') and
              replay['source_shader_sha256'] == SHADER_SHA and replay['trajectory_sha256'] == EXPECTED['results/nominal.json'] and
              replay['builder_sha256'] == sha(ROOT / 'tools/build_replay_p5.py') and replay['states'] == 1201)
        still = read(REPORTS / 'still-p5.json')
        check('Native 1080p still matches final source and four-sample settings',
              still['file_sha256'] == sha(ROOT / 'ARX-6-P5-1080p.png') and still['shader_sha256'] == SHADER_SHA and
              still['trajectory_sha256'] == EXPECTED['results/nominal.json'] and
              still['camera_samples'] == 4 and still['shadow_samples_per_light'] == 4)
        film = read(REPORTS / 'film-build.json')
        film_check = read(REPORTS / 'film-verification-p5.json')
        check('Joined film has current provenance and complete independent verification',
              film['sha256'] == sha(ROOT / 'ARX-6-P5-Inspection-1080p.mp4') and
              film['shader_sha256'] == SHADER_SHA and film['trajectory_sha256'] == EXPECTED['results/nominal.json'] and
              film_check['passed'] and film_check['final_film_verified'] and
              film_check['joined']['sha256'] == film['sha256'] and
              film_check['totals']['unique_raw_shader_frames'] == 1728)
        html_path = ROOT / 'ARX-6-P5.html'
        html = html_path.read_text()
        assets = json.loads(re.search(r'<script type="application/json" id="assets">([\s\S]*?)</script>', html)[1])
        controller = (ENG / 'controller.mjs').read_text()
        controller = re.sub(r"^import \{[^\n]+\} from './safety.mjs';\n", '', controller)
        check('Offline viewer embeds the final actual model, controller, trace and shader',
              assets['xml'] == (ENG / 'ARX-6-P5.xml').read_text() and
              assets['p'] == read(ENG / 'parameters.json') and
              assets['controllerJS'] == (ENG / 'safety.mjs').read_text() + '\n' + controller and
              assets['frames'] == [f[:22] for f in trace['frames']] and assets['api'] == trace['interface'] and
              assets['shader'] == live.read_text() and assets['inspection'] == read(REPORTS / 'inspection-parts.json'))
        browser = read(REPORTS / 'viewer-tests-p5.json')
        media = read(REPORTS / 'viewer-media-tests-p5.json')
        check('Browser functional checks pass for the verified source baseline',
              browser['passed'] and all(c['passed'] for c in browser['checks']) and
              browser['literal_shader_sha256'] == SHADER_SHA)
        check('Final embedded media and unchanged executable sources pass',
              media['passed'] and media['source_identity_preserved'] and
              media['html_sha256'] == sha(html_path) and media['baseline_html_sha256'] == browser['html_sha256'])
        parity = read(REPORTS / 'webgl-transport-parity.json')
        check('Browser and native renderer agree at the captured physical state',
              parity['passed'] and parity['shader_sha256'] == SHADER_SHA,
              {k: parity[k] for k in ['width', 'height', 'mean_absolute_RGB8_error', 'maximum_RGB8_error']})
        capture_path = REPORTS / 'browser-parity-frame.json'
        captured = read(capture_path)
        pixels = captured['pixels']
        raw = np.frombuffer(base64.b64decode(pixels['rgbaBottomUp']), np.uint8)
        raw = raw.reshape(pixels['height'], pixels['width'], 4)[::-1, :, :3]
        browser_image = np.asarray(Image.open(REPORTS / 'transport-browser.png').convert('RGB'))
        native_image = np.asarray(Image.open(REPORTS / 'transport-native.png').convert('RGB'))
        difference = np.abs(native_image.astype(np.int16) - raw.astype(np.int16))
        check('Current browser capture retains the actual compared framebuffer evidence',
              np.array_equal(raw, browser_image) and
              int(difference.max()) == parity['maximum_RGB8_error'] and
              abs(float(difference.mean()) - parity['mean_absolute_RGB8_error']) < 1e-12 and
              captured['diagnostics']['shaderSHA'] == SHADER_SHA and
              sha(REPORTS / 'browser-parity-shader.glsl') == SHADER_SHA,
              {'browser_capture_sha256': sha(capture_path),
               'browser_image_sha256': sha(REPORTS / 'transport-browser.png'),
               'native_image_sha256': sha(REPORTS / 'transport-native.png')})
        report['deliverables'] = {
            p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in
            [live, ROOT / 'ARX-6-P5-Replay.glsl', ROOT / 'ARX-6-P5-1080p.png',
             ROOT / 'ARX-6-P5-Inspection-1080p.mp4', html_path]
        }
        report['passed'] = all(c['passed'] for c in checks)
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    destination = REPORTS / 'delivery-consistency-p5.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'checks': len(checks),
                      'failed_checks': [c['name'] for c in checks if not c['passed']],
                      'error': report.get('error'), 'report': str(destination),
                      'engineering_ordinary_acceptance': '21/24; three unresolved'}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
