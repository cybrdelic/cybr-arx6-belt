"""Cross-platform equivalent of rebuild_p5.sh; known model failures stay nonzero."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / 'integration'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--physics-only', action='store_true')
    args = parser.parse_args()
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required on PATH')
    def run(name, *extra, check=True):
        executable = node if name.endswith('.mjs') else sys.executable
        return subprocess.run([executable, str(INTEGRATION/name), *extra], cwd=ROOT,
                              env=dict(os.environ,PYTHONUTF8='1'),check=check).returncode
    if not args.physics_only:
        for name in ['generate_cad_p2.py', 'build_p5_collision_proxies.py', 'validate_p5_mechanics.py', 'validate_p5_joint_stops.py']:
            run(name)
    run('build_p5_model.py')
    run('check_p5_springs.mjs')
    nominal = INTEGRATION/'results/nominal.json'
    before = nominal.stat().st_mtime_ns if nominal.exists() else -1
    status = run('validate_p5.mjs', check=False)
    fresh = False
    if nominal.exists() and nominal.stat().st_mtime_ns != before:
        metrics = json.loads(nominal.read_text(encoding='utf-8'))['metrics']
        names = {'xml_sha256':'ARX-6-P5.xml','controller_sha256':'controller.mjs','safety_sha256':'safety.mjs',
                 'parameters_sha256':'parameters.json','geometry_sha256':'geometry-meshes.json',
                 'collision_proxies_sha256':'p5_collision_proxies.json','cad_mass_properties_sha256':'mass_properties.json'}
        expected = {key:hashlib.sha256((INTEGRATION/name).read_bytes()).hexdigest() for key,name in names.items()}
        fresh = metrics.get('name')=='nominal' and metrics.get('duration_s',0)>=9.99 and metrics.get('provenance')==expected
    if not fresh:
        print('No fresh matching nominal trace; posed assembly export is skipped.', file=sys.stderr)
        status = 1
    for name in ['check_p5_clearance.mjs','review_p5_ranges.mjs','analyze_p5_results.py']:
        if run(name, check=False): status = 1
    if not args.physics_only and fresh:
        if run('export_p5_assembly.py', '--time', '2.5', check=False):
            status = 1
        elif run('validate_p5_posed_interfaces.py', check=False):
            status = 1
        if run('write_p5_mechanical_report.py', check=False): status = 1
    return status

if __name__ == '__main__':
    raise SystemExit(main())
