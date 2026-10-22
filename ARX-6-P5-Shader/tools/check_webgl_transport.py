#!/usr/bin/env python3
"""Compare WebGL uniform-buffer output to the native literal-table evaluator."""
import base64,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from egl_render import EGLRenderer,apply

root=Path(__file__).resolve().parents[1];reports=root/'reports'
frame=json.loads((reports/'browser-parity-frame.json').read_text())
shader=reports/'browser-parity-shader.glsl'
sha=hashlib.sha256(shader.read_bytes()).hexdigest()
assert sha==frame['diagnostics']['shaderSHA']
width=frame['pixels']['width'];height=frame['pixels']['height']
browser=np.frombuffer(base64.b64decode(frame['pixels']['rgbaBottomUp']),np.uint8).reshape(height,width,4)[::-1,:,:3].copy()
renderer=EGLRenderer(width,height,shader.read_text(),'#define AA 1\n#define P3_QUALITY 1\n#define P5_SHADOW_SAMPLES 1\n',geometry_buffers=True)
apply(renderer,np.asarray(frame['state']))
for name,value in [('u_time',float(frame['state'][0])),('u_frame',0),('u_samples',1),('u_exposure',0.),('u_inspect',0),('u_part',0),('u_camera_override',0),('u_cutaway',0.),('u_explode',0.),('u_mechanism',0.),('u_aperture',0.),('u_drag',[0,0]),('u_scroll',0.)]:renderer.uniform(name,value)
native=np.uint8(np.clip(renderer.draw()*255+.5,0,255))
diff=np.abs(native.astype(np.int16)-browser.astype(np.int16));pixel=np.max(diff,axis=2)
report={'shader_sha256':sha,'width':width,'height':height,'physical_time_s':frame['state'][0],'native_transport':renderer.table_info,'browser_transport':frame['diagnostics']['numericTables'],'mean_absolute_RGB8_error':float(diff.mean()),'rms_RGB8_error':float(np.sqrt(np.mean(diff.astype(float)**2))),'maximum_RGB8_error':int(diff.max()),'different_pixels':int(np.count_nonzero(pixel)),'pixels_over_4_codes':int(np.count_nonzero(pixel>4)),'pixel_count':width*height,'scope':'Cross-driver image comparison of the exact same numerical tables and procedural fragment program: WebGL2 uint-bit uniform buffers versus OpenGL read-only std430 tables. Rendering arithmetic may differ at edges.'}
report['passed']=report['mean_absolute_RGB8_error']<.5 and report['pixels_over_4_codes']/(width*height)<.002
Image.fromarray(native).save(reports/'transport-native.png');Image.fromarray(browser).save(reports/'transport-browser.png');Image.fromarray(np.minimum(diff*12,255).astype(np.uint8)).save(reports/'transport-difference-amplified.png')
(reports/'webgl-transport-parity.json').write_text(json.dumps(report,indent=2));renderer.close()
print(json.dumps({k:v for k,v in report.items() if k not in ('native_transport','browser_transport')},indent=2))
if not report['passed']:raise SystemExit('The native/browser image comparison needs review')
