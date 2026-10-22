#!/usr/bin/env bash
set -euo pipefail
arx_p5_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$arx_p5_root"
if [[ "${1:-}" != "" && "${1:-}" != "--physics-only" ]]; then
  echo "Usage: bash integration/rebuild_p5.sh [--physics-only]" >&2
  exit 2
fi
if [[ "${1:-}" != "--physics-only" ]]; then
  python3 integration/generate_cad_p2.py
  python3 integration/build_p5_collision_proxies.py
  python3 integration/validate_p5_mechanics.py
  python3 integration/validate_p5_joint_stops.py
fi
python3 integration/build_p5_model.py
node integration/check_p5_springs.mjs
arx_p5_validation_status=0
arx_p5_nominal_before="$(python3 - <<'PY'
from pathlib import Path
p=Path('integration/results/nominal.json')
print(p.stat().st_mtime_ns if p.exists() else -1)
PY
)"
node integration/validate_p5.mjs || arx_p5_validation_status=$?
arx_p5_nominal_fresh=0
if python3 - "$arx_p5_nominal_before" <<'PY'
from pathlib import Path
import hashlib,json,sys
r=Path('integration');p=r/'results/nominal.json'
if not p.exists() or p.stat().st_mtime_ns == int(sys.argv[1]):
    raise SystemExit('No fresh nominal trace was written; posed assembly export will be skipped.')
d=json.loads(p.read_text());m=d['metrics']
names={'xml_sha256':'ARX-6-P5.xml','controller_sha256':'controller.mjs','safety_sha256':'safety.mjs','parameters_sha256':'parameters.json','geometry_sha256':'geometry-meshes.json','collision_proxies_sha256':'p5_collision_proxies.json','cad_mass_properties_sha256':'mass_properties.json'}
expected={k:hashlib.sha256((r/v).read_bytes()).hexdigest() for k,v in names.items()}
if m.get('name')!='nominal' or m.get('duration_s',0)<9.99 or m.get('provenance')!=expected:
    raise SystemExit('Fresh nominal trace does not match this rebuilt model; posed assembly export will be skipped.')
PY
then
  arx_p5_nominal_fresh=1
else
  arx_p5_validation_status=1
fi
node integration/check_p5_clearance.mjs || arx_p5_validation_status=1
node integration/review_p5_ranges.mjs || arx_p5_validation_status=1
python3 integration/analyze_p5_results.py || arx_p5_validation_status=1
if [[ "${1:-}" != "--physics-only" && "$arx_p5_nominal_fresh" == 1 ]]; then
  # The native generator clears prior top-level STEP outputs. Recreate the
  # fully phased named assembly from this freshly simulated nominal trace.
  if python3 integration/export_p5_assembly.py --time 2.5; then
    python3 integration/validate_p5_posed_interfaces.py || arx_p5_validation_status=1
  else
    arx_p5_validation_status=1
  fi
  python3 integration/write_p5_mechanical_report.py || arx_p5_validation_status=1
fi
exit "$arx_p5_validation_status"
