#!/usr/bin/env python3
"""Compare compiled primitive/tape formulas with the captured native construction.

These are numerical equivalence checks at zero mechanism phase. Separate tests
in csg_symmetry.py exercise closed belt transport at nonzero phases as well.
"""
from pathlib import Path
import json,hashlib,re
import numpy as np
from check_csg import build,evaluate,polygon,box
from csg_symmetry import belt_nearest
from paths import P3

raw=json.loads((P3/'source/csg-recipe.json').read_text())
compiled=json.loads((P3/'source/compiled-csg.json').read_text())
points=np.array(compiled['points']);rng=np.random.default_rng(5107)

def primitive(rec,p):
 rows=np.array(rec['rows']);p=p@rows[:,:3].T+rows[:,3];a=rec['params'];kind=rec['type']
 if kind==0:return box(p,np.array(a))
 if kind==2:return np.linalg.norm(p,axis=1)-a[0]
 if kind==3:
  return evaluate(build({'op':'cone','args':a,'children':[]}),p)
 if kind==1:d=np.linalg.norm(p[:,:2],axis=1)-a[0];h=a[1]
 elif kind==5:
  phase,count=rec['extra'];angle=np.arctan2(p[:,1],p[:,0])-phase
  nearest=phase+2*np.pi*np.floor(angle*count/(2*np.pi)+.5)/count
  center=a[2]*np.column_stack([np.cos(nearest),np.sin(nearest)])
  d=np.linalg.norm(p[:,:2]-center,axis=1)-a[0];h=a[1]
 elif kind==6:
  c,pitch=rec['extra'];off=rec['detail'][0]
  d=np.array([belt_nearest(q,a[2],c,pitch,off,0.) for q in p[:,:2]])-a[0];h=a[1]
 elif kind in (4,7):
  if kind==7:
   start,pitch,count,_=rec['detail'];k=np.clip(np.floor((p[:,0]-start)/pitch+.5),0,count-1);p=p.copy();p[:,0]-=start+k*pitch
  d=polygon(p[:,:2],points[int(a[0]):int(a[0]+a[1])]);h=a[2]
 else:raise RuntimeError(kind)
 q=np.column_stack([d,abs(p[:,2])-h]);return np.linalg.norm(np.maximum(q,0),axis=1)+np.minimum(q.max(1),0)

def distance(obj,p):
 inv=np.linalg.inv(obj['matrix']);p=p@inv[:3,:3].T+inv[:3,3]
 s=compiled['shapes'][obj['shape']];stack=[]
 for op in compiled['instructions'][s['start']:s['start']+s['count']]:
  if op>0:stack.append(primitive(compiled['primitives'][op-1],p))
  else:
   b=stack.pop();a=stack.pop();stack.append(np.minimum(a,b) if op==-1 else np.maximum(a,-b if op==-2 else b))
 assert len(stack)==1
 return stack[0]

records=[];maximum=0.;total=0
for rec,obj in zip(raw,compiled['objects']):
 lo,hi=np.array(rec['bounds_mm']);pad=np.maximum((hi-lo)*.05,.2)
 p=rng.uniform(lo-pad,hi+pad,(256,3))
 exact=evaluate(build(rec['shape']),p);opt=distance(obj,p);err=float(np.max(abs(exact-opt)));maximum=max(maximum,err);total+=len(p)
 records.append({'name':rec['name'],'body':rec['body'],'comparisons':len(p),'maximum_abs_distance_difference_mm':err,'pass':err<1e-7})

# Test actual serialized GLSL polygon edge BVH, including crossing parity.
glsl=(P3/'source/geometry-constants.glsl').read_text()
def array(name,ty,width):
 text=re.search(r'const '+ty+r' '+name+r'\[\d+\]='+ty+r'\[\d+\]\((.*?)\n\);',glsl,re.S).group(1)
 rows=re.findall(ty+r'\(([^()]*)\)',text);return np.array([[float(v) for v in row.split(',')] for row in rows]).reshape(-1,width)
lo=array('POLY_BVH_LO','vec2',2);hi=array('POLY_BVH_HI','vec2',2);meta=array('POLY_BVH_META','ivec3',3).astype(int)
poly=array('CSG_POLY','vec2',2)
def bvh(p,first,end):
 d=1e100;inside=False;node=first
 while node<end:
  low,high=lo[node],hi[node];edge,previous,escape=meta[node];outside=np.maximum(np.maximum(low-p,p-high),0);bound=outside@outside
  cross=p[1]>=low[1] and p[1]<=high[1] and high[0]>p[0]
  if bound>=d and not cross:node=escape;continue
  if edge>=0:
   a,b=poly[previous],poly[edge];e=b-a;w=p-a;q=w-e*np.clip(w@e/max(e@e,1e-20),0,1);d=min(d,q@q)
   if (a[1]>p[1])!=(b[1]>p[1]):
    x=a[0]+(p[1]-a[1])*(b[0]-a[0])/(b[1]-a[1]);inside^=p[0]<x
  node+=1
 return np.sqrt(d)*(-1 if inside else 1)
seen=set();bvh_total=0;bvh_max=0.
for prim in compiled['primitives']:
 if prim['type'] not in (4,7):continue
 start,count,h=prim['params'];key=(int(start),int(count))
 if key in seen:continue
 seen.add(key);pp=poly[key[0]:key[0]+key[1]];first,end=map(int,prim['extra']);pad=max(float(np.ptp(pp,axis=0).max())*.2,.1)
 probes=np.r_[rng.uniform(pp.min(0)-pad,pp.max(0)+pad,(160,2)),pp]
 explicit=polygon(probes,pp);actual=np.array([bvh(p,first,end) for p in probes]);bvh_max=max(bvh_max,float(np.max(abs(explicit-actual))));bvh_total+=len(probes)

report={'raw_objects':len(raw),'compiled_objects':len(compiled['objects']),'matched_objects':len(records),'randomized_distance_comparisons':total,'maximum_abs_distance_difference_mm':maximum,'passed_objects':sum(r['pass'] for r in records),'polygon_edge_bvh_comparisons':bvh_total,'polygon_edge_bvh_max_abs_difference_mm':bvh_max,'captured_recipe_sha256':hashlib.sha256((P3/'source/csg-recipe.json').read_bytes()).hexdigest(),'compiled_csg_sha256':hashlib.sha256((P3/'source/compiled-csg.json').read_bytes()).hexdigest(),'constants_sha256':hashlib.sha256((P3/'source/geometry-constants.glsl').read_bytes()).hexdigest(),'runtime_sha256':hashlib.sha256((P3/'source/geometry-runtime.glsl').read_bytes()).hexdigest(),'scope':'Numerical comparisons of compiled exact periodic cylinder/rack/belt reductions and instruction tapes with original captured CSG; serialized polygon BVH distance and point-inside parity compared with explicit full edge scan. Not an exhaustive mathematical proof.','records':records}
(P3/'reports/optimized-csg-check.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2))
assert all(r['pass'] for r in records) and bvh_max<1e-7
