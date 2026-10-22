from paths import P2 as SOURCE_P2, P3 as OUTPUT_P3
#!/usr/bin/env python3
"""Retain the existing 0.06 mm CAD root blend in the procedural 2-D contour.
Only a 2-D section contour is encoded; no triangle mesh is imported or rendered.
"""
from pathlib import Path
import cadquery as cq,json,hashlib
R=(SOURCE_P2/'integration');O=OUTPUT_P3
p=R/'cad/gripper_pinion_m0p3_z20.step';gear=cq.importers.importStep(str(p));outer=max(gear.section(0).wires().vals(),key=lambda w:w.Length());v,_=outer.sample(.00015);points=[[x.x,x.y] for x in v]
data=json.loads((O/'source/csg-recipe.json').read_text());count=0

def visit(n):
 global count
 if n['op']=='polygon' and len(n['args'][0])>300:
  n['args'][0]=points;count+=1
 for c in n['children']:visit(c)
for o in data:visit(o['shape'])
(O/'source/csg-recipe.json').write_text(json.dumps(data,separators=(',',':')))
r={'source_step_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'section_z_mm':0,'sampling_deflection_mm':.00015,'outline_vertices':len(points),'replaced_profiles':count,'source_root_fillet_mm':.06,'geometry':'2-D boundary of native gear section, procedural extrusion and socket cuts preserved'}
(O/'reports/pinion-contour.json').write_text(json.dumps(r,indent=2));print(r)
