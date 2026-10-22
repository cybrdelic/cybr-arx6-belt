#!/usr/bin/env python3
"""Build inspectable material-region contact proxies for the P5 CAD.

Ring sectors use overlapping circumscribed tangential boxes, so there are no
circumferential sampling gaps. Small over-coverage is recorded. Thread holes,
windows at joints between strips and nonstructural fasteners are not a fidelity
claim; native BREP checks remain the authority for fitted interfaces.
"""
from pathlib import Path
import json, math
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parent
S=json.loads((R/'spec.json').read_text())
rows=[]
def rz(a):
 a=math.radians(a);return np.array([[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1.]])
def align(axis):
 a=np.array(axis,float);a/=np.linalg.norm(a);v=np.cross([0,0,1],a);n=np.linalg.norm(v)
 if n<1e-10:return np.eye(3) if a[2]>0 else np.diag([1.,-1.,-1.])
 return Rotation.from_rotvec(v/n*math.acos(np.clip(a[2],-1,1))).as_matrix()
def box(name,body,c,h,Q=None,origin=(0,0,0),part=None,approx='CAD rectangular material region'):
 Q=np.eye(3) if Q is None else Q;c=np.array(origin)+Q@np.array(c);q=Rotation.from_matrix(Q).as_quat()
 rows.append({'name':'P5_'+name,'body':body,'type':'box','center_mm':c.tolist(),'half_size_mm':list(h),'quat_wxyz':[float(q[3]),*q[:3].tolist()],'native_part':part or name,'approximation':approx})
def cylinder(name,body,p0,p1,r,Q=None,origin=(0,0,0),part=None):
 Q=np.eye(3) if Q is None else Q
 rows.append({'name':'P5_'+name,'body':body,'type':'cylinder','fromto_mm':[(np.array(origin)+Q@np.array(p)).tolist() for p in (p0,p1)],'radius_mm':r,'native_part':part or name,'approximation':'Exact cylindrical envelope'})
def ring(name,body,ri,ro,z0,z1,Q=None,origin=(0,0,0),xy=(0,0),n=24,part=None):
 Q=np.eye(3) if Q is None else Q;d=math.pi/n
 inner=ri*math.cos(d);outer=ro;rad=(inner+outer)/2
 for k in range(n):
  a=360*k/n;v=rz(a);c=np.array([*xy,(z0+z1)/2])+v@np.array([rad,0,0])
  box(name+'_rim_'+str(k),body,c,[(outer-inner)/2,ro*math.sin(d),(z1-z0)/2],Q@v,np.array(origin)+Q@np.array([0,0,0]),part or name,'Overlapping circumscribed annular sector; max radial excess %.4f mm'%(ro*(1/math.cos(d)-1)))
  # box center was in parent canonical coordinates, so rotate center only by Q.
  rows[-1]['center_mm']=(np.array(origin)+Q@c).tolist()

def stage(j,parent,size,origin,axis,theta):
 large=size=='large';f=S['folded_transmission'][size];C=f['center_distance_mm'];front=f['gearhead_front_z_mm'];Lg=f['gearhead_length_mm'];Lm=f['motor_length_mm'];pr=f['pitch_mm']*f['pulley_teeth']/(2*math.pi);zc=f['pulley_center_z_mm'];w=f['belt_width_mm'];Q=align(axis)@rz(theta);Qa=align(axis)
 cylinder(j+'_motor',parent,[0,C,front+Lg],[0,C,front+Lg+Lm],20 if large else 11,Q,origin,j+'_motor')
 cylinder(j+'_gearhead',parent,[0,C,front],[0,C,front+Lg],21 if large else 11,Q,origin,j+'_gearhead')
 # Retained stationary casing material outside its real bearing and shaft bores.
 ring(j+'_bearing_housing',parent,21 if large else 14,27 if large else 18,-40 if large else -24,6 if large else 4,Qa,origin,part=size+'_bearing_housing')
 ring(j+'_rear_bearing_cover',parent,18 if large else 12,36 if large else 25,-44 if large else -28,-40 if large else -24,Qa,origin,part=size+'_rear_bearing_cover')
 ring(j+'_front_bearing_cover',parent,18 if large else 12,27 if large else 18,6 if large else 4,10 if large else 8,Qa,origin,part=size+'_front_bearing_cover')
 b=S['brakes'][size];case0=-88 if large else -63
 ring(j+'_brake_stator',parent,b['ID_mm']/2,b['OD_mm']/2,case0,case0+b['length_mm'],Qa,origin,part=size+'_brake_vendor_envelope')
 ring(j+'_brake_front_adapter',parent,22.2 if large else 8.5,54 if large else 27.5,-48 if large else -32,-44 if large else -28,Qa,origin,part=size+'_brake_front_adapter')
 ring(j+'_brake_back_adapter',parent,10.2 if large else 4.2,54 if large else 27.5,-104 if large else -74,-100 if large else -70,Qa,origin,part=j+'_stop_pin_backplate')
 # Carrier is a drilled capsule deck; annular regions leave shaft openings.
 rr=36 if large else 21;outR=56 if large else 29.5;outHole=16 if large else 8.5;inHole=14.2 if large else 7.7
 ring(j+'_carrier_output',parent,outHole,outR,front-4,front,Q,origin,part=size+'_folded_carrier_deck')
 ring(j+'_carrier_input',parent,inHole,rr,front-4,front,Q,origin,xy=(0,C),part=size+'_folded_carrier_deck')
 box(j+'_carrier_bridge',parent,[0,(outHole+C-inHole)/2,front-2],[rr,(C-inHole-outHole)/2,2],Q,origin,size+'_folded_carrier_deck','Conservative carrier web, excludes both pilot holes; fastener holes omitted')
 cover0=zc-w/2-(14.5 if large else 13.5);cover1=cover0+3;inner=pr+4.5;outer=inner+3;windowhalf=max(4,pr-6)
 ring(j+'_cover_output',parent,10.4 if large else 4.4,outer,cover0,cover1,Q,origin,part=size+'_folded_front_cover')
 ring(j+'_cover_input',parent,14.02 if large else 11.02,outer,cover0,cover1,Q,origin,xy=(0,C),part=size+'_folded_front_cover')
 for sign in (-1,1):
  box(j+'_cover_side_'+str(sign),parent,[sign*(outer+windowhalf)/2,C/2,(cover0+cover1)/2],[(outer-windowhalf)/2,C/2,1.5],Q,origin,size+'_folded_front_cover')
 # Full annuli are conservative at their inner-facing halves; the native shell
 # has a capsule cavity. This can cause false contacts, never silent gaps.
 for which,y in [('output',0),('input',C)]:
  ring(j+'_housing_end_'+which,parent,inner,outer,cover1,front-4,Q,origin,xy=(0,y),part=size+'_folded_housing_rails')
 for sign in (-1,1):
  for end,z in [('rear',cover1+2),('front',front-6)]:
   box(j+'_housing_side_'+str(sign)+'_'+end,parent,[sign*(inner+1.5),C/2,z],[1.5,C/2,2],Q,origin,size+'_folded_housing_rails')
 box(j+'_tension_block',parent,[0,C+rr-3,front+3.5],[6 if large else 4,4,3.5],Q,origin,size+'_folded_tension_block')
 cylinder(j+'_tension_screw',parent,[0,C+rr-13,front+3.5],[0,C+rr+8,front+3.5],3.5 if large else 2.7,Q,origin,size+'_folded_tension_screw')
 # Outboard input journal is enclosed; added bearing pocket protrusion matters.
 ring(j+'_input_bearing_pocket',parent,14.02 if large else 11.02,17 if large else 14,cover0-3.5,cover1+3,Q,origin,xy=(0,C),part=size+'_folded_front_cover')

C=S['folded_transmission']['large']['center_distance_mm'];theta=math.degrees(math.atan2(75,-math.sqrt(C*C-75*75)))
frames=[('J1','fixed','large',(0,60,0),(0,1,0),-90),('J2','turret','large',(0,144,-45),(0,0,1),theta),('J3','upper','large',(0,280,45),(0,0,-1),0),('J4','fore','small',(0,204,0),(0,1,0),0),('J5','roll','small',(0,0,-45),(0,0,1),90),('J6','bend','small',(0,169.6,0),(0,1,0),0)]
for x in frames:stage(*x)
# Revised counterbalance plates and short clevises, with real coordinates.
for name,body,c,h in [
 ('shoulder_fixed_plate','turret',[-20,89,54],[55,3,38]),
 ('shoulder_moving_plate','upper',[0,70,24.5],[29,14,2.5]),
 ('shoulder_moving_post','upper',[0,70,56],[8,5,33.5]),
 ('elbow_fixed_plate','upper',[-7,190,-25],[37,16,3]),
 ('elbow_fixed_post','upper',[-30,190,-54.5],[8,5,29.5]),
 ('elbow_moving_plate','fore',[0,35,-33],[29,35,3]),
 ('elbow_moving_lever','fore',[0,-22.5,-33],[12,22.5,3]),
 ('elbow_moving_post','fore',[0,-45,-57],[8,5,27])]:box(name,body,c,h)
for z in [55,65,79,89]:box('shoulder_fixed_cheek_'+str(z),'turret',[-65,100,z],[9,15,2])
cylinder('elbow_moving_root','fore',[0,0,-36],[0,0,-30],27)
# Base foot is a capsule minus the two actual through-bores. A conservative
# 4 mm strip decomposition never enlarges either hole; tiny screw holes omitted.
Q=align((0,1,0));step=4.;r=95.
for k,y0 in enumerate(np.arange(-r,r,step)):
 y1=min(r,y0+step);near=0 if y0<=0<=y1 else min(abs(y0),abs(y1));far=max(abs(y0),abs(y1));outer=math.sqrt(max(0,r*r-near*near));intervals=[[-outer,110+outer]]
 for xc,hr in [(0,55),(110,23)]:
  if far>=hr:continue
  dx=math.sqrt(hr*hr-far*far);lo,hi=xc-dx,xc+dx;new=[]
  for a,b in intervals:
   if hi<=a or lo>=b:new.append([a,b])
   else:
    if a<lo:new.append([a,lo])
    if hi<b:new.append([hi,b])
  intervals=new
 for n,(a,b) in enumerate(intervals):
  if b-a>1e-8:box('base_foot_%d_%d'%(k,n),'fixed',[(a+b)/2,(y0+y1)/2,6],[(b-a)/2,(y1-y0)/2,6],Q,part='bench_mount_plate',approx='Conservative 4 mm strip of actual capsule minus two circular bores')
ring('pedestal_main','fixed',27.025,45,20.2,64,Q,part='pedestal_sleeve')
ring('pedestal_base','fixed',36.2,80,12,20,Q,part='pedestal_sleeve')
for k,(x,z) in enumerate(S['bench_interface']['mount_bolt_centers_xz_mm']):
 cylinder('bench_washer_'+str(k),'fixed',[x,-47,z],[x,-40,z],14,part='bench_backing_washer')
 cylinder('bench_bolt_'+str(k),'fixed',[x,-53,z],[x,21,z],7,part='bench_mount_bolt')
T=json.loads((R/'folded-transmissions.json').read_text()) if (R/'folded-transmissions.json').exists() else []
config={'records':rows,'replace_names':['pedestal_collision',*[f'P2_base_mount_{i}' for i in range(4)]],
 'replace_prefixes':['package_','P2_fixed_clevis','P2_moving_clevis','P2_elbow_anchor_','P2_elbow_moving_anchor'],
 'joint_extra_armature_kg_m2':[r['extra_joint_armature_kg_m2'] for r in T] if T else [0]*6,
 'tabletop':{'thickness_mm':40,'top_y_mm':0,'extent_xz_mm':[1000,1000],'holes':[{'center_xz_mm':[0,0],'radius_mm':55},{'center_xz_mm':[110,0],'radius_mm':23}]},
 'scope':'External folded motor/reducer, output bearing/brake material, slotted carrier, windowed enclosure, revised counterbalance brackets, mounting foot and pedestal. Annuli use continuous overlapping conservative 24-sector boxes; no cavity-filling bearing or brake cylinders. Native BREP controls exact fitted interfaces. Flexible springs/belt contact, small fastener holes, internal shafts and vendor internals are outside proxy fidelity. No new body exclusions.',
 'approximation':'Conservative external material strips can report false contacts near curved or machined edges. Native BREP refinement is required before classifying an apparent overlap. Circular annulus sector maximum radial excess ro*(sec(pi/24)-1).',
 'source_generator':'generate_cad_p2.py','source_proxy_script':'build_p5_collision_proxies.py'}
(R/'p5_collision_proxies.json').write_text(json.dumps(config,indent=2)+'\n')
print(json.dumps({'records':len(rows),'armature_complete':bool(T),'joint_clocking_degrees':dict((j,a) for j,_,_,_,_,a in frames)}))
