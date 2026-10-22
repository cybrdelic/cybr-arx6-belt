from paths import P2 as SOURCE_P2, P3 as OUTPUT_P3
#!/usr/bin/env python3
"""Surface-probe comparison against P2's independently exported BREP meshes."""
import sys,json,hashlib,re
from pathlib import Path
import numpy as np
import cadquery as cq
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).parent))
from capture_csg import Node,bounds,ROOT,OUT

def build(d):return Node(d['op'],tuple(d['args']),tuple(build(c) for c in d['children']))
def box(p,b):
 q=abs(p)-b;return np.linalg.norm(np.maximum(q,0),axis=1)+np.minimum(np.max(q,axis=1),0)
def polygon(p,pts):
 pts=np.array(pts);a=pts[-1];d=np.full(len(p),np.inf);inside=np.zeros(len(p),bool)
 for b in pts:
  e=b-a;w=p-a;q=w-np.clip(w@e/max(np.dot(e,e),1e-24),0,1)[:,None]*e;d=np.minimum(d,np.sum(q*q,axis=1))
  crossing=(a[1]>p[:,1])!=(b[1]>p[:,1])
  if abs(b[1]-a[1])>1e-15:inside^=crossing&(p[:,0]<a[0]+(p[:,1]-a[1])*(b[0]-a[0])/(b[1]-a[1]))
  a=b
 return np.sqrt(d)*np.where(inside,-1,1)
def evaluate(n,p):
 if n.op=='transform':
  inv=np.linalg.inv(np.array(n.args).reshape(4,4));return evaluate(n.children[0],p@inv[:3,:3].T+inv[:3,3])
 if n.op in ['union','intersection','cut']:
  a,b=(evaluate(c,p) for c in n.children);return np.minimum(a,b) if n.op=='union' else np.maximum(a,-b if n.op=='cut' else b)
 if n.op=='box':return box(p,np.array(n.args))
 if n.op=='sphere':return np.linalg.norm(p,axis=1)-n.args[0]
 if n.op in ['cylinder','polygon']:
  d=polygon(p[:,:2],n.args[0]) if n.op=='polygon' else np.linalg.norm(p[:,:2],axis=1)-n.args[0]
  q=np.column_stack([d,abs(p[:,2])-n.args[1]]);return np.linalg.norm(np.maximum(q,0),axis=1)+np.minimum(q.max(1),0)
 if n.op=='cone':
  r0,r1,h=n.args;q=np.column_stack([np.linalg.norm(p[:,:2],axis=1),p[:,2]]);k1=np.array([r1,h]);k2=np.array([r1-r0,2*h]);ca=np.column_stack([q[:,0]-np.minimum(q[:,0],np.where(q[:,1]<0,r0,r1)),abs(q[:,1])-h]);cb=q-k1+np.clip((k1-q)@k2/(k2@k2),0,1)[:,None]*k2
  return np.where((cb[:,0]<0)&(ca[:,1]<0),-1,1)*np.sqrt(np.minimum(np.sum(ca*ca,1),np.sum(cb*cb,1)))
 raise RuntimeError(n.op)

def main():
 source_sha=hashlib.sha256((ROOT/'generate_cad_p2.py').read_bytes()).hexdigest()
 capture_report=json.loads((OUT.parent/'reports/csg-capture.json').read_text())
 if source_sha!=capture_report['generator_sha256']:raise RuntimeError('Native generator changed after CSG capture; recapture before comparison')
 if (OUT/'captured-spec.json').read_bytes()!=(ROOT/'spec.json').read_bytes():raise RuntimeError('Engineering specification changed after CSG capture')
 native=json.loads((ROOT/'geometry-meshes.json').read_text())['meshes']
 for m in native:
  if m['body']=='jaw':m['body']='jaw_left'
 def append(shape,body,name,material,offset=(0,0,0)):
  shape=shape.translate(tuple(offset));verts,_=shape.tessellate(.08,.12)
  native.append({'body':body,'name':name,'material':material,'vertices_mm':[v.toTuple() for v in verts]})
 jaw=cq.Assembly.load(str(ROOT/'cad/left_jaw_subassembly.step'))
 for name,node in jaw.objects.items():
  if node.obj is None:continue
  shape=node.obj.val() if isinstance(node.obj,cq.Workplane) else node.obj
  append(shape.moved(node.loc),'jaw_right','left_'+name,'steel',(0,-219.2,0))
 par=json.loads((ROOT/'parameters.json').read_text());puck=par['puck']
 piece=cq.Workplane('XZ').circle(puck['outer_radius_m']*1000).circle(puck['bore_radius_m']*1000).extrude(puck['height_m']*500,both=True)
 append(piece.val(),'puck','workpiece','brass')
 xml=ET.fromstring((ROOT/'ARX-6-P5.xml').read_text())
 for name in ['nest_A_base','nest_A_seat','nest_B_base','nest_B_seat']:
  g=xml.find('.//geom[@name="'+name+'"]');sz=[float(x)*1000 for x in g.get('size').split()];pos=[float(x)*1000 for x in g.get('pos').split()]
  shape=cq.Workplane('XZ').circle(sz[0]).extrude(sz[1],both=True).translate(tuple(pos))
  append(shape.val(),'fixed',name,'steel')
 captured=json.loads((OUT/'csg-recipe.json').read_text());used=set();records=[];rng=np.random.default_rng(6159)
 if len(native)!=len(captured):raise RuntimeError(f'Native/captured part counts differ: {len(native)} vs {len(captured)}')
 for m in native:
  vv=np.array(m['vertices_mm']);bb=np.array([vv.min(0),vv.max(0)])
  candidates=[i for i,x in enumerate(captured) if i not in used and x['body']==m['body']]
  exact=[i for i in candidates if captured[i]['name']==m['name']]
  i=exact[0] if exact else min(candidates,key=lambda i:np.max(abs(np.array(captured[i]['bounds_mm'])-bb)))
  used.add(i);c=captured[i];p=vv[rng.choice(len(vv),min(192,len(vv)),replace=False)];dist=evaluate(build(c['shape']),p)
  mx=float(abs(dist).max());allowed=.001
  records.append({'body':m['body'],'native_name':m['name'],'shader_name':c['name'],'probes':len(p),'max_abs_distance_mm':mx,'rms_distance_mm':float(np.sqrt(np.mean(dist*dist))),'tolerance_mm':allowed,'pass':mx<=allowed})
 report={'native_objects':len(native),'shader_objects':len(captured),'matched':len(used),'surface_probes':sum(x['probes'] for x in records),'passed_objects':sum(x['pass'] for x in records),'max_distance_mm':max(x['max_abs_distance_mm'] for x in records),'scope':'Surface samples from native STEP tessellation; not an exhaustive BREP equivalence proof. The pinion outline includes the native 0.06 mm root blend sampled at 0.00015 mm deflection.','records':records}
 report['spec_sha256']=hashlib.sha256((ROOT/'spec.json').read_bytes()).hexdigest();report['native_geometry_sha256']=hashlib.sha256((ROOT/'geometry-meshes.json').read_bytes()).hexdigest();report['captured_recipe_sha256']=hashlib.sha256((OUT/'csg-recipe.json').read_bytes()).hexdigest();report['generator_sha256']=hashlib.sha256((ROOT/'generate_cad_p2.py').read_bytes()).hexdigest()
 path=OUT.parent/'reports/geometry-surface-check.json';path.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2));print('Failures',[x for x in records if not x['pass']]);assert all(x['pass'] for x in records),'Native surface probe failure'
if __name__=='__main__':main()
