#!/usr/bin/env python3
"""Export a named, physically phased P5 assembly at a saved nominal state.

Uses the generator's exact placed BREP, not tessellated geometry. The input
shaft/pulley/key and each closed toothed belt are advanced by the actual joint
angle. Springs are regenerated at their current anchor distance. No inspection
explosion or demonstration rotation is applied.
"""
from pathlib import Path
import json,math,hashlib,argparse
import numpy as np
import cadquery as cq
from scipy.spatial.transform import Rotation
from OCP.gp import gp_Trsf
R=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--time',type=float,default=2.5);args=parser.parse_args()
S=json.loads((R/'spec.json').read_text());T=json.loads((R/'folded-transmissions.json').read_text());N=json.loads((R/'placed-native-parts.json').read_text())['records'];D=json.loads((R/'results/nominal.json').read_text())
i=min(range(len(D['frames'])),key=lambda i:abs(D['frames'][i][0]-args.time));f=D['frames'][i];poses=D['poses'][i];q=np.array(f[1:7]);sign=np.array([-1,-1,1,1,-1,1]);alphas=sign*q
cache={}
def read(p):
 p=Path(p)
 if str(p) not in cache:cache[str(p)]=cq.importers.importStep(str(p)).val()
 return cache[str(p)]
def cyl(r,z0,z1):return cq.Workplane('XY').workplane(offset=z0).circle(r).extrude(z1-z0)
def capsule(r,c,z0,z1):return cyl(r,z0,z1).union(cyl(r,z0,z1).translate((0,c,0))).union(cq.Workplane('XY').box(2*r,c,z1-z0).translate((0,c/2,(z0+z1)/2)))
def align(axis):
 z=np.array([0.,0.,1.]);a=np.array(axis,float);a/=np.linalg.norm(a);v=np.cross(z,a);n=np.linalg.norm(v)
 if n<1e-10:return np.eye(3) if a[2]>0 else np.diag([1.,-1.,-1.])
 return Rotation.from_rotvec(v/n*math.acos(np.clip(a[2],-1,1))).as_matrix()
def placed(sh,Q,p):
 mat=np.column_stack([Q,p]);tr=gp_Trsf();tr.SetValues(*mat.ravel().tolist());return sh.moved(cq.Location(tr))
def trans(sh,pos,axis):return placed(sh,align(axis),np.array(pos))
def path(s,r,c):
 h=math.pi*r
 if s<h:
  a=math.pi+s/r;return np.array([r*math.cos(a),r*math.sin(a)]),np.array([math.cos(a),math.sin(a)])
 s-=h
 if s<c:return np.array([r,s]),np.array([1.,0.])
 s-=c
 if s<h:
  a=s/r;return np.array([r*math.cos(a),c+r*math.sin(a)]),np.array([math.cos(a),math.sin(a)])
 s-=h;return np.array([-r,c-s]),np.array([-1.,0.])
def belt(t,alpha):
 large=int(t['joint'][1])<=3;d=S['folded_transmission']['large' if large else 'small'];c=d['center_distance_mm'];pr=t['pitch_radius_mm'];zc=d['pulley_center_z_mm'];w=d['belt_width_mm'];pitch=d['pitch_mm'];off=.60 if large else .35
 out=capsule(pr+(2.30 if large else 1.50),c,zc-w/2,zc+w/2).cut(capsule(pr-(.40 if large else .25),c,zc-w/2-1,zc+w/2+1))
 for k in range(d['belt_teeth']):
  p,n=path((k*pitch+pr*alpha)%d['belt_pitch_length_mm'],pr,c);p=p-off*n
  out=out.union(cyl(1.20 if large else .70,zc-w/2,zc+w/2).translate((p[0],p[1],0)))
 return trans(out.val().rotate((0,0,0),(0,0,1),t['clocking_degrees']),t['origin_mm'],t['axis'])
def spring(d,L,shoulder):
 lead=d['hook_span_total_mm']/2;length=L-2*lead;pitch=length/d['active_turns'];rr=d['mean_coil_diameter_mm']/2;wr=d['wire_diameter_mm']/2;er=3.6 if shoulder else 3.1
 helix=cq.Wire.makeHelix(pitch,length,rr);profile=cq.Plane(origin=(rr,0,0),xDir=(1,0,0),normal=(0,rr,pitch/(2*math.pi)))
 coil=cq.Workplane(profile).circle(wr).sweep(cq.Workplane(obj=helix),isFrenet=True).translate((0,0,lead))
 for ze in [0,L]:
  eye=cq.Workplane(obj=cq.Solid.makeTorus(er,wr)).rotate((0,0,0),(1,0,0),90).translate((0,0,ze));pa=np.array([er,0,ze]);pb=np.array([rr,0,lead if ze==0 else L-lead]);v=pb-pa
  tail=trans(cyl(wr,0,float(np.linalg.norm(v))).val(),pa,v)
  for pp in [pa,pb]:tail=tail.fuse(cq.Solid.makeSphere(wr).translate(tuple(pp)))
  coil=coil.union(eye).union(cq.Workplane(obj=tail))
 return coil.val()
materials={'aluminum':cq.Color(.66,.70,.75),'steel':cq.Color(.26,.29,.33),'rubber':cq.Color(.10,.11,.12),'polymer':cq.Color(.23,.27,.31)}
assembly=cq.Assembly(name='ARX_6_P5_nominal_t'+str(f[0]).replace('.','p'));parts=[];byjoint={t['joint']:t for t in T};beltcache={}
for rec in N:
 body=rec['body'];name=rec['name'];pbody='fixed_hardware' if body=='fixed' else 'jaw_left' if body=='jaw' else body;pose=poses[pbody];Q=np.array(pose['rotation_row_major']).reshape(3,3);p=np.array(pose['position_m'])*1000
 j=name.split('_')[0];t=byjoint.get(j);sh=read(R/rec['step_file'])
 if t and name==j+'_timing_belt':
  sh=belt(t,float(alphas[int(j[1])-1]));beltcache[j]=sh
 elif t and name in [j+'_drive_pulley',j+'_input_shaft',j+'_pulley_input_key']:
  c=np.array(t['origin_mm'])+align(t['axis'])@np.array(t['input_axis_local_offset_mm']);a=np.array(t['axis'],float)
  sh=sh.rotate(tuple(c),tuple(c+a),math.degrees(float(alphas[int(j[1])-1])))
 elif name.startswith('gripper_pinion_m0p3_z20'):
  angle=-((float(np.mean(f[13:15]))*1000+2)/3);sh=sh.rotate((0,201.5,0),(0,201.5,1),math.degrees(angle))
 world=placed(sh,Q,p);label=body+'__'+name;assembly.add(world,name=label,color=materials.get(rec['material'],materials['aluminum']));parts.append({'name':label,'body':body,'solids':len(world.Solids()),'volume_mm3':float(world.Volume())})
# The opposite jaw has its own lower rack and handed geometry, not a flipped
# forward axis or a duplicate upper rack.
pose=poses['jaw_right'];Q=np.array(pose['rotation_row_major']).reshape(3,3);p=np.array(pose['position_m'])*1000
left=[('left_carriage',read(R/'cad/left_jaw_carriage.step'),'aluminum'),('left_pad',read(R/'cad/finger_pad.step').mirror('YZ'),'rubber'),('lower_rack',read(R/'cad/gripper_rack_m0p3.step').mirror('YZ').translate((50*math.pi*.3/2-2,198.5,-3)),'steel')]
for z in [-10,10]:left.append(('left_bushing_'+str(z),trans(read(R/'cad/jaw_guide_bushing.step'),(-5.8,193,z),(1,0,0)),'polymer'))
for name,sh,mat in left:
 world=placed(sh.translate((0,-219.2,0)),Q,p);assembly.add(world,name=name,color=materials[mat]);parts.append({'name':name,'body':'jaw_right','solids':len(world.Solids()),'volume_mm3':float(world.Volume())})
springs=[]
for key,parent,child,offset in [('counterbalance','turret','upper',[0,144,0]),('elbow_counterbalance','upper','fore',[0,280,0])]:
 d=S[key];pa=poses[parent];pb=poses[child];Qa=np.array(pa['rotation_row_major']).reshape(3,3);Qb=np.array(pb['rotation_row_major']).reshape(3,3);oa=np.array(pa['position_m'])*1000;ob=np.array(pb['position_m'])*1000
 for ix,zval in enumerate([d['parent_anchor_m'][2]*1000,d['second_spring_z_m']*1000]):
  va=np.array(d['parent_anchor_m'])*1000;vb=np.array(d['child_anchor_m'])*1000;va[2]=vb[2]=zval;a=oa+Qa@(va+offset);b=ob+Qb@vb;z=b-a;L=float(np.linalg.norm(z));z/=L;up=-Qa[:,2];x=np.cross(up,z);x/=np.linalg.norm(x);y=np.cross(z,x);Qs=np.column_stack([x,y,z])
  if ix==0:coil=spring(d,L,key=='counterbalance')
  world=placed(coil,Qs,a);name=key+'_spring_'+str(ix+1);assembly.add(world,name=name,color=cq.Color(.45,.47,.51));springs.append({'name':name,'anchor_a_mm':a.tolist(),'anchor_b_mm':b.tolist(),'eye_distance_mm':L,'valid':world.isValid()});parts.append({'name':name,'body':'flexible_between_bodies','solids':len(world.Solids()),'volume_mm3':float(world.Volume())})
time_label=('{:.3f}'.format(f[0])).rstrip('0').rstrip('.').replace('.','p');file=R/'cad'/('ARX-6-P5-assembled-nominal-t'+time_label+'.step');assembly.save(str(file));out=cq.importers.importStep(str(file)).val();bb=out.BoundingBox()
meta={'file':str(file.relative_to(R)),'units':'mm','time_s':f[0],'joint_angles_rad':q.tolist(),'jaw_half_gaps_m':f[13:15],'input_drive_phase_about_native_axes_rad':alphas.tolist(),'trace_sha256':hashlib.sha256((R/'results/nominal.json').read_bytes()).hexdigest(),'model_xml_sha256':D['interface']['xml_sha256'],'generator_sha256':hashlib.sha256((R/'generate_cad_p2.py').read_bytes()).hexdigest(),'part_count':len(parts),'imported_solid_count':len(out.Solids()),'imported_valid':out.isValid(),'bounds_mm':{'min':[bb.xmin,bb.ymin,bb.zmin],'max':[bb.xmax,bb.ymax,bb.zmax]},'spring_anchors':springs,'parts':parts,'scope':'Robot only: exact named BREP parts at a saved physical nominal pose, actual belt-tooth and input-shaft phase, correct handed lower jaw, four rebuilt springs at actual eye distance. Workbench, payload, nest and flexible cable harness excluded. Supplier components remain declared outer envelopes.'}
(R/'reports'/'P5-overall-assembly.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps({k:v for k,v in meta.items() if k not in ['parts','spring_anchors']}))

if not meta["imported_valid"] or not all(x["valid"] for x in springs):
    raise SystemExit(1)
