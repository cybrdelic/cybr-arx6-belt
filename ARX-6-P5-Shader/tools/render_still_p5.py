#!/usr/bin/env python3
"""Render the delivery poster from the same verified P5 geometry and motion."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from PIL import Image
from film_p5 import Director,uniforms,ROOT
from egl_render import EGLRenderer,aces

shader=ROOT/'ARX-6-P5-Live.glsl'
director=Director();state=director.state(0,2.5);start=time.monotonic()
renderer=EGLRenderer(1920,1080,shader.read_text(),'#define AA 1\n#define P3_QUALITY 1\n#define P5_SHADOW_SAMPLES 4\n#define CAPTURE 1\n',geometry_buffers=True)
acc=np.zeros((1080,1920,3),np.float32)
for sample in range(4):
    uniforms(renderer,state,sample)
    acc+=renderer.draw()
    print('Completed poster sample',sample+1,flush=True)
pixels=np.uint8(np.clip(aces(acc/4)*255+.5,0,255))
output=ROOT/'ARX-6-P5-1080p.png';Image.fromarray(pixels).save(output)
report={'revision':'P5','file':output.name,'width':1920,'height':1080,'camera_samples':4,'shadow_samples_per_light':4,'physical_time_s':2.5,'shader_sha256':hashlib.sha256(shader.read_bytes()).hexdigest(),'trajectory_sha256':hashlib.sha256(director.trajectory_path.read_bytes()).hexdigest(),'file_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'numeric_table_transport':renderer.table_info,'seconds':time.monotonic()-start}
(ROOT/'reports/still-p5.json').write_text(json.dumps(report,indent=2))
renderer.close();print(json.dumps({k:v for k,v in report.items() if k!='numeric_table_transport'}))
