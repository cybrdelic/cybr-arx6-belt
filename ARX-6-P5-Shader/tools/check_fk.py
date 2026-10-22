from paths import P2 as SOURCE_P2, P3 as OUTPUT_P3
from pathlib import Path
import json,numpy as np,math,hashlib
P=OUTPUT_P3;R=SOURCE_P2
p=R/'integration/results/nominal.json';t=json.loads(p.read_text())
def ry(a):
 c,s=math.cos(a),math.sin(a);return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def rz(a):
 c,s=math.cos(a),math.sin(a);return np.array([[c,-s,0],[s,c,0],[0,0,1]])
def quat(w,x,y,z):
 q=np.array([w,x,y,z]);w,x,y,z=q/np.linalg.norm(q)
 return np.array([[1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y)],[2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x)],[2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)]])
maxp,maxr=0,0;count=0;bybody={}
for f,poses in zip(t['frames'],t['poses']):
 q=f[1:7];B=ry(-q[0]);U=B@rz(-q[1]);F=U@rz(-q[2]);Rr=F@ry(q[3]);Be=Rr@rz(-q[4]);T=Be@ry(q[5]);S=np.array([0,.144,0]);E=S+U[:,1]*.28;W=E+F[:,1]*.26
 frames={'turret':(np.zeros(3),B),'upper':(S,U),'fore':(E,F),'roll':(W,Rr),'bend':(W,Be),'tool':(W,T),'jaw_left':(W+T@np.array([f[13],.2192,0]),T),'jaw_right':(W+T@np.array([-f[14],.2192,0]),T),'puck':(np.array(f[15:18]),quat(*f[18:22]))}
 for name,(o,r) in frames.items():
  ref=poses[name];ep=float(np.linalg.norm(o-np.array(ref['position_m'])));er=float(np.max(np.abs(r-np.array(ref['rotation_row_major']).reshape(3,3))));maxp=max(ep,maxp);maxr=max(er,maxr);count+=1
  a=bybody.setdefault(name,{'max_position_error_m':0,'max_rotation_entry_error':0});a['max_position_error_m']=max(ep,a['max_position_error_m']);a['max_rotation_entry_error']=max(er,a['max_rotation_entry_error'])
report={'comparisons':count,'times':len(t['frames']),'max_position_error_m':maxp,'max_rotation_entry_error':maxr,'passed':maxp<1e-10 and maxr<1e-10,'by_body':bybody,'scope':'Double-precision implementation of the GLSL transform equations compared with the independent stored MuJoCo body transforms; excludes GPU float roundoff.','trajectory_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(P/'reports/forward-transforms.json').write_text(json.dumps(report,indent=2));print(report)
