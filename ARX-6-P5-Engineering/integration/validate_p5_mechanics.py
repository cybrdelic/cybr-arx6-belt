#!/usr/bin/env python3
"""Native BREP interface validation and traceable compact-envelope comparison."""
from pathlib import Path
import json, csv, math, hashlib
import numpy as np
import cadquery as cq
R=Path(__file__).resolve().parent;B=R/'baseline-reference';C=R/'cad';REPORT=R/'reports';REPORT.mkdir(exist_ok=True)
S=json.loads((R/'spec.json').read_text());T=json.loads((R/'folded-transmissions.json').read_text())
cache={}
def read(n):
 if n not in cache:cache[n]=cq.importers.importStep(str(C/(n+'.step'))).val()
 return cache[n]
def volume(a,b):return float(a.intersect(b).Volume())
def distance(a,b):return float(a.distance(b))
def cyl(r,z0,z1):return cq.Solid.makeCylinder(r,z1-z0,cq.Vector(0,0,z0))
def bbox(s):
 b=s.BoundingBox();return {'min_mm':[b.xmin,b.ymin,b.zmin],'max_mm':[b.xmax,b.ymax,b.zmax],'span_mm':[b.xlen,b.ylen,b.zlen]}
def transform(sh,origin,axis):
 z=np.array([0.,0.,1.]);a=np.array(axis,float);a/=np.linalg.norm(a);v=np.cross(z,a);an=math.degrees(math.acos(np.clip(z@a,-1,1)))
 if np.linalg.norm(v)>1e-10:sh=sh.rotate((0,0,0),tuple(v),an)
 elif a[2]<0:sh=sh.rotate((0,0,0),(1,0,0),180)
 return sh.translate(tuple(origin))
checks=[]
def check(name,a,b,allowed=1e-5):
 v=volume(a,b);d=distance(a,b);checks.append({'name':name,'intersection_volume_mm3':v,'minimum_distance_mm':d,'pass':v<=allowed,'volume_tolerance_mm3':allowed});return checks[-1]
for size in ['large','small']:
 f=S['folded_transmission'][size];large=size=='large';cent=f['center_distance_mm'];belt=read(size+'_folded_timing_belt')
 for other,shift in [('driven_pulley',False),('drive_pulley',True),('carrier_deck',False),('front_cover',False),('housing_rails',False)]:
  a=read(size+'_folded_'+other);a=a.translate((0,cent,0)) if shift else a
  check(size+'_belt_vs_'+other,belt,a)
 z=f['pulley_center_z_mm'];w=f['belt_width_mm'];key=cq.Workplane('XY').box(4 if large else 2,4 if large else 2,w+3).translate((5.8 if large else 3.3,0,z)).val()
 check(size+'_input_key_vs_keyed_shaft',key,read(size+'_folded_input_shaft'))
 check(size+'_input_key_vs_pulley',key,read(size+'_folded_drive_pulley'))
 check(size+'_input_shaft_vs_pulley',read(size+'_folded_input_shaft'),read(size+'_folded_drive_pulley'))
 check(size+'_input_bearing_vs_cover',read(size+'_folded_input_support_bearing').translate((0,cent,0)),read(size+'_folded_front_cover'))
for t in T:
 j=t['joint'];size='large' if int(j[1])<4 else 'small';large=size=='large';f=S['folded_transmission'][size];theta=t['clocking_degrees'];z=f['pulley_center_z_mm'];w=f['belt_width_mm']
 shaft=read(j+'_clocked_output_shaft');key=cq.Workplane('XY').box(6 if large else 2,6 if large else 2,w+3).translate((9.5 if large else 3.8,0,z)).val().rotate((0,0,0),(0,0,1),theta)
 pulley=read(size+'_folded_driven_pulley').rotate((0,0,0),(0,0,1),theta)
 check(j+'_output_key_vs_clocked_shaft',key,shaft)
 check(j+'_output_key_vs_clocked_pulley',key,pulley)
 check(j+'_shaft_vs_pulley',shaft,pulley)
 check(j+'_shaft_flange_vs_front_cover',shaft,read(size+'_front_bearing_cover'))
# Exact table service cutouts and true J1 base interface, in body/world millimetres.
bench=cq.Workplane('XZ').box(1000,1000,40).translate((0,-20,0)).val()
for x,r in [(0,55),(110,23)]:bench=bench.cut(cq.Solid.makeCylinder(r,60,cq.Vector(x,-50,0),cq.Vector(0,1,0)))
t=T[0];f=S['folded_transmission']['large'];theta=t['clocking_degrees'];origin=t['origin_mm'];axis=t['axis'];cent=f['center_distance_mm']
base=transform(read('bench_mount_plate'),(0,0,0),(0,1,0))
for part in ['carrier_deck','housing_rails','front_cover']:
 sh=transform(read('large_folded_'+part).rotate((0,0,0),(0,0,1),theta),origin,axis)
 check('J1_'+part+'_vs_table_with_two_real_bores',sh,bench)
 check('J1_'+part+'_vs_base_foot',sh,base)
for part,z0,z1,r in [('gearhead',-104,-34,21),('motor',-34,22.1,20)]:
 sh=transform(cyl(r,z0,z1).translate((0,cent,0)).rotate((0,0,0),(0,0,1),theta),origin,axis)
 check('J1_'+part+'_vs_table_with_two_real_bores',sh,bench)
 check('J1_'+part+'_vs_base_foot',sh,base)
# Every exported native STEP is readable and its constituent solids valid.
files=[]
for p in sorted(C.glob('*.step')):
 sh=read(p.stem);solids=sh.Solids();files.append({'file':p.name,'solids':len(solids),'valid':bool(sh.isValid()) and all(s.isValid() for s in solids),'bounds':bbox(sh),'volume_mm3':float(sh.Volume())})
# Mesh bounds are direct tessellations of generated BREP. World frame at q=0
# is a reference construction pose, not an asserted allowed operating pose.
world_offsets={'fixed':[0,0,0],'turret':[0,0,0],'upper':[0,144,0],'fore':[0,424,0],'roll':[0,684,0],'bend':[0,684,0],'tool':[0,684,0],'jaw':[0,903.2,0]}
parents={'J1':'fixed','J2':'turret','J3':'upper','J4':'fore','J5':'roll','J6':'bend'}
def bounds(v):
 v=np.array(v);lo=v.min(0);hi=v.max(0);return {'min_mm':lo.tolist(),'max_mm':hi.tolist(),'span_mm':(hi-lo).tolist()}
def groupmesh(path,baseline=False):
 mm=json.loads(path.read_text())['meshes'];groups={j:[] for j in parents};allv=[];bodyv={};joint=None;idx=0
 for m in mm:
  n=m['name'];body=m['body'];verts=np.array(m['vertices_mm'])
  if not len(verts):continue
  bodyv.setdefault(body,[]).append(verts);wv=verts+world_offsets[body];allv.append(wv)
  if baseline:
   if '_bearing_housing_' in n:idx+=1;joint='J'+str(idx)
   if n.startswith('bench_mount_plate'):joint=None
  else:joint=m.get('mechanism')
  if joint in groups:
   v=wv-np.array(world_offsets[parents[joint]]);groups[joint].append(v)
 return mm,{j:np.concatenate(v) for j,v in groups.items() if v},bounds(np.concatenate(allv)),{b:bounds(np.concatenate(v)) for b,v in bodyv.items()}
oldmesh,oldgroups,oldbounds,oldbody=groupmesh(B/'geometry-meshes.json',True)
mesh,newgroups,newbounds,newbody=groupmesh(R/'geometry-meshes.json')
comp=[]
for t in T:
 j=t['joint'];ax=np.array(t['axis']);org=np.array(t['origin_mm']);o=oldgroups[j];n=newgroups[j];oa=(o-org)@ax;na=(n-org)@ax
 comp.append({'joint':j,'parent_frame':parents[j],'joint_origin_mm':org.tolist(),'axis':ax.tolist(),'baseline_body_local_bounds':bounds(o),'P5_body_local_bounds':bounds(n),'baseline_axial_range_from_origin_mm':[float(oa.min()),float(oa.max())],'P5_axial_range_from_origin_mm':[float(na.min()),float(na.max())],'rear_projection_reduction_percent':100*(1-abs(float(na.min()/oa.min()))),'overall_axial_span_reduction_percent':100*(1-float(np.ptp(na)/np.ptp(oa)))})
props=json.loads((R/'mass_properties.json').read_text());oldprops=json.loads((B/'mass_properties.json').read_text());mass=[]
for b,p in props.items():mass.append({'body':b,'P2_mass_kg':oldprops[b]['mass_kg'],'P5_mass_kg':p['mass_kg'],'difference_kg':p['mass_kg']-oldprops[b]['mass_kg'],'minimum_inertia_eigenvalue_kg_m2':float(np.linalg.eigvalsh(p['inertia_tensor_kg_m2']).min())})
with (R/'bom-p5-placed-records.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['body','name','mass_kg','provenance'])
 for b,p in props.items():
  for c in p['components']:w.writerow([b,c['name'],c['mass_kg'],c['provenance']])
roles=[]
for m in mesh:
 n=m['name'];role='structural part'
 if 'motor' in n:role='catalog motor envelope'
 elif 'gearhead' in n:role='catalog reducer envelope'
 elif 'pulley' in n:role='keyed toothed transmission'
 elif 'shaft' in n or 'key' in n:role='rotating torque path'
 elif 'bearing' in n:role='bearing support envelope'
 elif 'brake' in n:role='output-side brake'
 elif 'cover' in n or 'housing_rails' in n:role='removable enclosure and support'
 elif 'screw' in n or 'bolt' in n or 'nut' in n or 'washer' in n:role='assembly hardware'
 elif 'spring' in n or 'clevis' in n:role='counterbalance attachment'
 elif 'rack' in n or 'pinion' in n or 'jaw' in n or 'pad' in n:role='gripper transmission or contact'
 roles.append({'name':n,'body':m['body'],'mechanism':m.get('mechanism','structure_or_counterbalance'),'role':role,'material':m['material'],'native_mesh_vertices':len(m['vertices_mm'])})
(R/'mechanism-parts.json').write_text(json.dumps({'rigid_placements':roles,'spring_count':4,'scope':'Vendor motor/reducer/brake internals and bearing rolling elements are not modeled. Film inspection may move actual modeled parts only.'},indent=2)+'\n')
report={'revision':'P5','generator_sha256':hashlib.sha256((R/'generate_cad_p2.py').read_bytes()).hexdigest(),'spec_sha256':hashlib.sha256((R/'spec.json').read_bytes()).hexdigest(),'native_interface_checks':checks,'native_checks_pass':all(x['pass'] for x in checks),'step_files':files,'step_file_count':len(files),'all_step_solids_valid':all(x['valid'] for x in files),'rigid_placement_count':len(mesh),'body_masses':mass,'joint_envelope_comparison':comp,'zero_reference_assembly_bounds':{'P2':oldbounds,'P5':newbounds,'note':'q=0 construction reference, includes canonical one jaw; comparison excludes procedural springs, flexible cables, bench and payload. This is not the demonstrated task pose.'},'body_local_bounds':{'P2':oldbody,'P5':newbody},'limitations':['Native fit checks are nominal geometry checks, not tolerance-stack approval or manufacturing release.','Catalog motor/reducer/brake geometry remains a full-size outer envelope with catalog mass; vendor internals and true inertia distribution are unverified.','Belt tooth section is an explicit rounded nominal approximation; cutter geometry, pretension, alignment and endurance require supplier qualification.','Continuous-proxy task-path collision evidence is separate; no claim that all combinations of hard joint limits are collision-free.','Flexible spring and cable collision, fastener preload, structural stress and thermal life are not qualified.']}
# Overall assembly extents use native STEP body bounds, avoiding tessellation undershoot.
old_native=json.loads((B/'native-body-bounds.json').read_text())
new_native={body:next(x['bounds'] for x in files if x['file']==body+'_subassembly.step') for body in world_offsets}
def aggregate_body_bounds(bb):
    lo=[];hi=[]
    for body,b in bb.items():
        off=np.array(world_offsets[body]);lo.append(np.array(b['min_mm'])+off);hi.append(np.array(b['max_mm'])+off)
    low=np.min(lo,axis=0);high=np.max(hi,axis=0)
    return {'min_mm':low.tolist(),'max_mm':high.tolist(),'span_mm':(high-low).tolist()}
report['tessellation_reference_assembly_bounds']=report['zero_reference_assembly_bounds']
report['zero_reference_assembly_bounds']={'P2':aggregate_body_bounds(old_native),'P5':aggregate_body_bounds(new_native),'note':'Native STEP BREP body bounds in q=0 construction reference, includes canonical one jaw; excludes procedural springs, flexible cables, bench and payload. Not an asserted operating pose.'}
report['native_body_local_bounds']={'P2':old_native,'P5':new_native}
(REPORT/'P5-mechanical-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'native_interface_checks':len(checks),'passed':report['native_checks_pass'],'step_files':len(files),'all_step_valid':report['all_step_solids_valid'],'rigid_placements':len(mesh),'joint_rear_projection_reduction_percent':{r['joint']:r['rear_projection_reduction_percent'] for r in comp},'failed_checks':[r for r in checks if not r['pass']]}))

if not report["native_checks_pass"] or not report["all_step_solids_valid"]:
    raise SystemExit(1)
