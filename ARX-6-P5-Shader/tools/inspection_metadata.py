"""Deterministic engineering-inspection grouping and displacement metadata.

Offsets are visual disassembly transforms, never changes to the physical model.
Rotation is restricted to modeled rotating hardware; vendor envelopes stay fixed.
"""
from __future__ import annotations
import math,re
import numpy as np

GROUP_NAMES={1:'Base drive',2:'Shoulder drive',3:'Elbow drive',4:'Wrist roll drive',5:'Wrist bend drive',6:'Tool roll drive',7:'Rack and pinion gripper',8:'Shoulder counterbalance',9:'Elbow counterbalance',10:'Workpiece and nests',11:'Link structure'}

def classify(rec):
    name=rec['name'].lower();body=rec['body']
    if 'inspection_group' in rec:return int(rec['inspection_group'])
    match=re.match(r'j([1-6])_',name)
    if match:return int(match.group(1))
    if name.startswith('nest_') or body=='puck':return 10
    if 'shoulder_spring' in name:return 8
    if 'elbow_' in name and any(x in name for x in ('spring','anchor','counterbalance')):return 9
    if 'spring_eye_pin' in name:
        cy=float(np.mean(np.asarray(rec['bounds_mm']),axis=0)[1])
        return 8 if body=='turret' or body=='upper' and cy<160 else 9
    if body.startswith('jaw') or any(x in name for x in ('gripper','guide_rod','pinion','finger_pad')):return 7
    if any(x in name for x in ('link_tube','root_ear','nut_strip','clamp_side_shim')):return 11
    return {'fixed':1,'turret':2,'upper':3,'fore':4,'roll':5,'bend':6,'tool':7}[body]

def fallback_axis(rec):
    body=rec['body'];name=rec['name']
    return np.array([0.,1.,0.]) if body in ('fixed','fore','bend') else np.array([0.,0.,1.])

def setup(objects,raw,bodies):
    groups={g:[] for g in GROUP_NAMES}
    for i,(obj,rec) in enumerate(zip(objects,raw)):
        group=classify(rec);groups[group].append(i)
        axis=np.array(rec.get('joint_axis',fallback_axis(rec)),float);axis/=max(np.linalg.norm(axis),1e-9)
        center=np.array(rec.get('joint_center_mm',np.mean(obj['bounds'],axis=0)),float)
        name=obj['name'].lower()
        demo=any(x in name for x in ('output_shaft','input_shaft','shaft_key','keyed_hub','armature','inner_race_spacer','installed_retainer','selective_inner_race_shim','pulley','rotor_shaft','integral_stop_target'))
        demo=demo and not any(x in name for x in ('guard','mount','plate','bearing_housing')) and group<=6
        # A separate input-pulley center may be supplied by the mechanical generator.
        if 'pulley' in name or 'gearhead_output_shaft' in name:
            # A folded drive's input axis is offset from the joint output.
            # Each symmetric pulley is rotated about its own modeled center.
            center=np.mean(obj['bounds'],axis=0)
        if 'demo_axis' in rec:axis=np.array(rec['demo_axis'],float)
        if 'demo_center_mm' in rec:center=np.array(rec['demo_center_mm'],float)
        obj.update(input_joint_phase=int(any(token in name for token in ('_drive_pulley','_input_shaft','_pulley_input_key')) and group<=6),inspection_group=group,demo_axis=axis.tolist(),demo_center_mm=center.tolist(),demo_ratio=float(rec.get('demo_ratio',1. if demo else 0.)),cutaway=2 if 'gripper_bridge' in name else int(any(x in name for x in ('belt_guard','belt_cover','front_cover','housing_rails','bearing_housing','coupling_cage'))))
    for group,ids in groups.items():
        if not ids:continue
        order=sorted(ids,key=lambda i:(float(np.mean(objects[i]['bounds'],axis=0)@np.array(objects[i]['demo_axis'])),objects[i]['name']))
        for rank,i in enumerate(order):
            obj=objects[i];name=obj['name'].lower();a=np.array(obj['demo_axis']);c=np.mean(obj['bounds'],axis=0);origin=np.array(obj['demo_center_mm']);radial=c-origin-a*np.dot(c-origin,a)
            if np.linalg.norm(radial)<1e-5:
                ref=np.array([1.,0.,0.]) if abs(a[0])<.8 else np.array([0.,1.,0.]);radial=np.cross(a,ref)
            radial/=np.linalg.norm(radial)
            side=np.cross(a,radial)
            axial=(rank-(len(order)-1)*.5)*9.
            offset=a*axial
            if any(x in name for x in ('strut','spacer_','stop_pin','sensor','key','shim','retainer','pin_')):
                angle=(rank*.61803398875%1.)*2*math.pi
                offset+=35.*(math.cos(angle)*radial+math.sin(angle)*side)
            elif any(x in name for x in ('motor','gearhead')):offset+=radial*32.
            elif any(x in name for x in ('guard','cover')):offset+=radial*24.
            elif group in (7,8,9,11):offset+=radial*(25.+(rank%3)*10.)
            if group==10:offset=np.zeros(3)
            obj['explode_offset_mm']=np.round(offset,6).tolist()
            # Conservative bounds for any inspection-only axial rotation.
            lo,hi=np.array(obj['bounds'])
            if obj['demo_ratio']:
                corners=np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])
                origin=np.array(obj['demo_center_mm']);q=corners-origin;t=q@a;radius=np.max(np.linalg.norm(q-t[:,None]*a,axis=1))
                extent=radius*np.sqrt(np.maximum(0,1-a*a))
                axiallo=np.minimum(a*t.min(),a*t.max());axialhi=np.maximum(a*t.min(),a*t.max())
                obj['demo_bounds']=[(origin+axiallo-extent).tolist(),(origin+axialhi+extent).tolist()]
            else:obj['demo_bounds']=obj['bounds']
    return groups

def report(objects,bodies,groups):
    result={'units':'millimetres in each body local frame','inspection_kind':'Visual disassembly and kinematic mechanism demonstration. Exploded offsets and inspection rotations are not simulated mechanical configurations.','uniforms':{'u_part':'0=all parts in selected group; positive integer selects object_id+1 and hides dynamic springs','u_inspect':'0=all, positive integer selects listed group','u_explode':'0 assembled, 1 fully exploded','u_mechanism':'Inspection-only hardware rotation in radians; 0 disables extra rotation','u_cutaway':'0 whole, 1 sections genuine housing/guard solids on positive local-X; gripper bridge sections positive local-Z'},'groups':[],'parts':[]}
    for group,ids in groups.items():
        if not ids:continue
        bounds={}
        for i in ids:
            o=objects[i];b=bodies[o['body']];lo,hi=np.array(o['demo_bounds']);e=np.array(o['explode_offset_mm']);pair=np.array([np.minimum(lo,lo+e),np.maximum(hi,hi+e)])
            if b not in bounds:bounds[b]=pair
            else:bounds[b]=np.array([np.minimum(bounds[b][0],pair[0]),np.maximum(bounds[b][1],pair[1])])
        result['groups'].append({'id':group,'name':GROUP_NAMES[group],'parts':ids,'body_bounds_mm':{k:v.tolist() for k,v in bounds.items()}})
    for i,o in enumerate(objects):
        result['parts'].append({'id':i,'name':o['name'],'body':bodies[o['body']],'group':o['inspection_group'],'bounds_mm':o['bounds'],'explode_offset_mm':o['explode_offset_mm'],'demo_axis':o['demo_axis'],'demo_center_mm':o['demo_center_mm'],'demo_ratio':o['demo_ratio'],'physical_input_rotation':bool(o['input_joint_phase']),'cutaway':bool(o['cutaway']),'cutaway_axis':'Z' if o['cutaway']==2 else 'X' if o['cutaway']==1 else None})
    return result
