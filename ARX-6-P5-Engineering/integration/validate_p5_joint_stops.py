#!/usr/bin/env python3
"""Check revised link clearance and physical stop-pin engagement in native BREP."""
from pathlib import Path
import json,math
import numpy as np
import cadquery as cq
from scipy.spatial.transform import Rotation
from OCP.gp import gp_Trsf
R=Path(__file__).resolve().parent;C=R/'cad';S=json.loads((R/'spec.json').read_text());T=json.loads((R/'folded-transmissions.json').read_text())
def read(n):return cq.importers.importStep(str(C/(n+'.step'))).val()
def align(axis):
 a=np.array(axis,float);a/=np.linalg.norm(a);v=np.cross([0,0,1],a);n=np.linalg.norm(v)
 if n<1e-10:return np.eye(3) if a[2]>0 else np.diag([1.,-1.,-1.])
 return Rotation.from_rotvec(v/n*math.acos(np.clip(a[2],-1,1))).as_matrix()
checks=[]
for joint,parent,child,shift in [('J3','upper_link_tube','fore_link_tube',(0,280,0)),('J5','wrist_roll_fork','wrist_bend_cradle',(0,0,0))]:
 idx=int(joint[1])-1;q=S['joint_hard_limits_rad'][idx][1];a=read(parent);b=read(child).rotate((0,0,0),(0,0,1),-math.degrees(q)).translate(shift);v=float(a.intersect(b).Volume());d=float(a.distance(b));checks.append({'joint':joint,'check':'native link clearance at corrected upper hard stop','angle_rad':q,'intersection_volume_mm3':v,'minimum_distance_mm':d,'pass':v<1e-5 and d>.5})
 t=T[idx];sgn=[-1,-1,1,1,-1,1][idx];pin_index=1 if sgn>0 else 0
 pin=read('placed/'+t['parent']+'__'+joint+'_stop_pin_'+str(pin_index));Q=align(t['axis']);mat=np.eye(4);mat[:3,:3]=Q.T;mat[:3,3]=-Q.T@np.array(t['origin_mm']);tr=gp_Trsf();tr.SetValues(*mat[:3,:].ravel().tolist());pin=pin.moved(cq.Location(tr));cam=read(joint+'_clocked_stop_target')
 for delta,label in [(-.001,'one milliradian before stop'),(0,'at stop'),(.001,'one milliradian beyond stop')]:
  target=cam.rotate((0,0,0),(0,0,1),math.degrees(sgn*(q+delta)));v=float(pin.intersect(target).Volume());d=float(pin.distance(target));ok=(v<1e-5 and d>0) if delta<0 else (v<1e-5 and d<1e-4) if delta==0 else v>1e-5
  checks.append({'joint':joint,'check':'physical pin engagement '+label,'angle_rad':q+delta,'intersection_volume_mm3':v,'minimum_distance_mm':d,'pass':ok})
report={'checks':checks,'all_pass':all(x['pass'] for x in checks),'hard_limits_rad':S['joint_hard_limits_rad'],'soft_limits_rad':S['joint_soft_limits_rad'],'scope':'Nominal native geometry at corrected upper stops, including actual exported stop dowels and clocked steel target. Pin impact strength, bracket stress and stopping energy are not qualified. Other coupled configurations still require collision-aware planning.'}
(R/'reports'/'P5-corrected-joint-stop-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));raise SystemExit(0 if report['all_pass'] else 1)
