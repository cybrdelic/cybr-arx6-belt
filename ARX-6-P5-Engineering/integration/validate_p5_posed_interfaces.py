#!/usr/bin/env python3
"""Check actual moving transmission phases and pin/eye fits in the posed STEP."""
from pathlib import Path
import json,hashlib
import numpy as np
import cadquery as cq
R=Path(__file__).resolve().parent;meta=json.loads((R/'reports/P5-overall-assembly.json').read_text());file=R/meta['file'];sh=cq.importers.importStep(str(file)).val();children=list(sh);parts=meta['parts']
if len(children)!=len(parts):raise RuntimeError('STEP direct child count does not match named assembly index')
maxvol=max(abs(c.Volume()-p['volume_mm3']) for c,p in zip(children,parts))
if maxvol>1e-4:raise RuntimeError('STEP child sequence does not match named native volume index')
byname={p['name']:c for p,c in zip(parts,children)};checks=[]
def find(suffix):
 matches=[s for n,s in byname.items() if n.endswith('__'+suffix)]
 if len(matches)!=1:raise RuntimeError('Ambiguous placed name '+suffix)
 return matches[0]
def check(name,a,b):
 v=float(a.intersect(b).Volume());d=float(a.distance(b));checks.append({'name':name,'intersection_volume_mm3':v,'minimum_distance_mm':d,'pass':v<1e-5})
for i in range(1,7):
 j='J'+str(i);belt=find(j+'_timing_belt')
 check(j+'_phased_belt_vs_input_pulley',belt,find(j+'_drive_pulley'))
 check(j+'_phased_belt_vs_output_pulley',belt,find(j+'_driven_pulley'))
 check(j+'_phased_input_key_vs_shaft',find(j+'_pulley_input_key'),find(j+'_input_shaft'))
pins=[(n,s,np.array(s.Center().toTuple())) for n,s in byname.items() if 'spring_eye_pin' in n]
for spring in meta['spring_anchors']:
 for side in ['a','b']:
  anchor=np.array(spring['anchor_'+side+'_mm']);name,pin,c=min(pins,key=lambda r:np.linalg.norm(r[2]-anchor));err=float(np.linalg.norm(c-anchor))
  if err>1e-5:raise RuntimeError('Spring pin does not meet recorded eye centre')
  check(spring['name']+'_eye_'+side+'_vs_'+name,byname[spring['name']],pin)
report={'overall_step_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'time_s':meta['time_s'],'trace_sha256':meta['trace_sha256'],'model_xml_sha256':meta['model_xml_sha256'],'part_count':len(parts),'maximum_child_volume_index_error_mm3':maxvol,'checks':checks,'all_pass':all(x['pass'] for x in checks),'scope':'Exact native BREP at the saved2.5s state: six moving belt tooth phases, six input keys/shafts and eight spring eye/pin fits. Does not qualify elastic belt engagement, pretension, bearing preload, spring fatigue or the global configuration space.'}
(R/'reports/P5-posed-interface-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));raise SystemExit(0 if report['all_pass'] else 1)
