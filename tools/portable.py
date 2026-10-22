"""Portable, bounded entry points. Physics criteria are never weakened."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
ENG=ROOT/'ARX-6-P5-Engineering'
SHADER=ROOT/'ARX-6-P5-Shader'

def call(args,cwd=ROOT,env=None,check=True):
    print('+',subprocess.list2cmdline([str(x) for x in args]),flush=True)
    environment = dict(os.environ if env is None else env, PYTHONUTF8='1')
    return subprocess.run([str(x) for x in args],cwd=cwd,env=environment,check=check).returncode

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['cad-smoke','physics-smoke','viewer-build','gl-smoke'])
    p.add_argument('--output',type=Path,default=ROOT/'.local/portable')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if a.action=='cad-smoke':
        cad=out/'cad'
        if cad.exists():
            raise SystemExit('Refusing to reuse CAD output; choose a fresh --output directory')
        env=dict(os.environ,ARX_CAD_OUTPUT=str(cad))
        call([sys.executable,'integration/generate_cad_p2.py','--smoke'],ENG,env)
    elif a.action=='physics-smoke':
        node=shutil.which('node')
        if not node:raise SystemExit('Node.js is required')
        call([sys.executable,ROOT/'tools/restore_geometry_cache.py'])
        env=dict(os.environ,ARX_VALIDATION_OUT=str(out))
        call([node,'integration/check_p5_springs.mjs'],ENG,env)
        call([node,'integration/validate_p5.mjs','nominal'],ENG,env)
        status=call([node,'integration/validate_p5.mjs','power_loss_3.2'],ENG,env,False)
        metrics=json.loads((out/'results/power_loss_3.2.json').read_text(encoding='utf-8'))['metrics']
        failures=[x for x in metrics['checks'] if not x['passed']]
        expected='estimated belt torque including rotor deceleration within service allowance'
        assert status==1 and [x['name'] for x in failures]==[expected], failures
        report={'nominal_passed':True,'known_power_loss_failure_reproduced':True,'failures':failures,
                'scope':'Execution regression, not a safety pass. Power-loss overload remains a design failure.'}
        (out/'smoke-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
    elif a.action=='viewer-build':
        call([sys.executable,'tools/build_viewer_p5.py'],SHADER)
    else:
        sys.path.insert(0,str(SHADER/'tools'))
        from egl_render import EGLRenderer
        source='void main(){fragColor=vec4(gl_FragCoord.xy/u_resolution,0.5,1.0);}'
        renderer=EGLRenderer(32,24,source)
        try:
            frame=renderer.draw()
            assert frame.shape==(24,32,3) and float(frame.max())>0
            print(json.dumps({'backend':renderer.backend,'GL':renderer.info,'scope':'GL context and framebuffer probe; not the complete robot shader'}))
        finally:renderer.close()
if __name__=='__main__':main()
