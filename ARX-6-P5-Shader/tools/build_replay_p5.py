#!/usr/bin/env python3
"""Embed the fresh physical trace into a single procedural replay shader."""
from pathlib import Path
import hashlib,json,numpy as np
ROOT=Path(__file__).resolve().parents[1]
TRACE=ROOT.parent/'ARX-6-P5-Engineering/integration/results/nominal.json'
frames=np.asarray(json.loads(TRACE.read_text())['frames'],dtype=float)
states=frames[:,[1,2,3,4,5,6,13,14,15,16,17,18,19,20,21]]
states=np.c_[states,np.zeros(len(states))].reshape(len(states),4,4)
for i in range(1,len(states)):
 a=np.r_[states[i-1,2,3],states[i-1,3,:3]];b=np.r_[states[i,2,3],states[i,3,:3]]
 if np.dot(a,b)<0:states[i,2,3]*=-1;states[i,3,:3]*=-1
def scalar(v):
 s=format(float(np.float32(v)),'.9g');return s if any(x in s for x in '.e') else s+'.'
rows=['vec4('+','.join(map(scalar,v))+')' for v in states.reshape(-1,4)]
state='\n'.join(f'const vec4 ARX_STATE_{i}[{len(states)}]=vec4[]('+',\n'.join(rows[i::4])+');' for i in range(4))
rate=(len(frames)-1)/(frames[-1,0]-frames[0,0]);duration=frames[-1,0]
state+=f'''
void loadPhysicalReplay(float time) {{
 float z=mod(max(time,0.),{scalar(duration)})*{scalar(rate)};
 int a=clamp(int(floor(z)),0,{len(frames)-2}),b=a+1;float u=clamp(z-float(a),0.,1.);
 vec4 p=mix(ARX_STATE_0[a],ARX_STATE_0[b],u),q=mix(ARX_STATE_1[a],ARX_STATE_1[b],u),r=mix(ARX_STATE_2[a],ARX_STATE_2[b],u),s=mix(ARX_STATE_3[a],ARX_STATE_3[b],u);
 u_joint012=p.xyz;u_joint345=vec3(p.w,q.xy);u_jawsSI=q.zw;u_puck_positionSI=r.xyz;u_puck_quaternionWXYZ=normalize(vec4(r.w,s.xyz));
}}
'''
source=(ROOT/'ARX-6-P5-Live.glsl').read_text()
for typ,name in [('vec3','u_joint012'),('vec3','u_joint345'),('vec2','u_jawsSI'),('vec3','u_puck_positionSI'),('vec4','u_puck_quaternionWXYZ')]:source=source.replace(f'uniform {typ} {name};',f'{typ} {name};')
constants={'float':{'u_cutaway':'0.','u_explode':'0.','u_camera_detail':'0.','u_mechanism':'0.','u_camera_focal':'3.15','u_aperture':'0.','u_exposure':'.05'},'int':{'u_inspect':'0','u_part':'0','u_camera_override':'0','u_samples':'1','u_reflections':'0'},'vec3':{'u_camera_origin':'vec3(0)','u_camera_target':'vec3(0)'}}
for typ,entries in constants.items():
 for name,value in entries.items():source=source.replace(f'uniform {typ} {name};',f'const {typ} {name}={value};')
source=source.replace('void initKinematics(float time) {',state+'\nvoid initKinematics(float time) {\nloadPhysicalReplay(time);')
head=f'''// ARX-6 P5 — standalone procedural replay. No robot mesh or material texture.
// {len(frames)} fresh physical samples, including the independently simulated puck.
// This shader replays states; the offline HTML additionally runs live MuJoCo.
// Host declares: vec2 u_resolution; float u_time; int u_frame;
// vec2 u_drag; float u_scroll; out vec4 fragColor. GLSL 330 / GLSL ES 300.
// The replay resets at {duration:.6g} seconds. No continuous loop-state claim.
'''
out=ROOT/'ARX-6-P5-Replay.glsl';out.write_text(head+source)
(ROOT/'reports/replay-build.json').write_text(json.dumps({'revision':'P5','shader':out.name,'shader_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_shader_sha256':hashlib.sha256((ROOT/'ARX-6-P5-Live.glsl').read_bytes()).hexdigest(),'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'trajectory_sha256':hashlib.sha256(TRACE.read_bytes()).hexdigest(),'states':len(frames),'rate_Hz':rate,'cycle_seconds':duration,'position_quantization_max_m':float(np.max(np.abs(frames[:,15:18]-frames[:,15:18].astype(np.float32)))),'bytes':out.stat().st_size,'scope':'Recorded physical state replay. The independent physical solver is in the Engineering package and HTML viewer.'},indent=2))
print(out.name,out.stat().st_size)
