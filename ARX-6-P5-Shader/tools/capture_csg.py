#!/usr/bin/env python3
"""Replay ARX-6's CAD construction into a texture-free constructive-solid recipe.

This is NOT a triangle-to-distance conversion. Each modeled box, cylinder,
annulus, polygon extrusion and boolean operation is retained as a constructive
solid. Per-body placements come from the same generator as the STEP assembly.
Native CAD and all physics inputs are left untouched.
"""
from __future__ import annotations
from paths import P2 as SOURCE_P2, P3 as OUTPUT_P3
import ast, copy, hashlib, json, math, types
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

ROOT=(SOURCE_P2/'integration')
OUT=(OUTPUT_P3/'source')

@dataclass
class Node:
    op: str
    args: tuple=()
    children: tuple=()
    def plain(self):
        return {'op':self.op,'args':self.args,'children':[x.plain() for x in self.children]}


def trans(n,T):
    T=np.asarray(T,dtype=float)
    if n.op=='transform':T=T@np.asarray(n.args).reshape(4,4);n=n.children[0]
    if np.max(abs(T-np.eye(4)))<1e-10:return n
    return Node('transform',tuple(np.round(T.ravel(),12)),(n,))

class W:
    def __init__(self,plane='XY',obj=None,node=None,offset=0,profiles=()):
        self.plane=plane;self.offset=offset;self.profiles=profiles
        self.node=node if node is not None else (obj.node if isinstance(obj,W) else obj)
    def _new(self,**kw):
        d=dict(plane=self.plane,node=self.node,offset=self.offset,profiles=self.profiles);d.update(kw);return W(**d)
    def workplane(self,offset=0):return self._new(offset=self.offset+offset)
    def circle(self,r):return self._new(profiles=self.profiles+(('circle',r),))
    def rect(self,w,h):return self._new(profiles=self.profiles+(('rect',w,h),))
    def polyline(self,p):return self._new(profiles=self.profiles+(('poly',tuple(tuple(float(x) for x in q) for q in p)),))
    def close(self):return self
    def box(self,x,y,z):return self._new(node=Node('box',(x/2,y/2,z/2)),profiles=())
    def sphere(self,r):return self._new(node=Node('sphere',(r,)),profiles=())
    def extrude(self,h,both=False):
        z0=self.offset-(h if both else 0);z1=self.offset+h
        nodes=[]
        for p in self.profiles:
            if p[0]=='circle':n=Node('cylinder',(float(p[1]),(z1-z0)/2))
            elif p[0]=='rect':n=Node('box',(p[1]/2,p[2]/2,(z1-z0)/2))
            else:n=Node('polygon',(p[1],(z1-z0)/2))
            T=np.eye(4);T[2,3]=(z0+z1)/2;n=trans(n,T)
            # CadQuery XZ has xDir=+X and normal=-Y.
            if self.plane=='XZ':
                R=np.eye(4);R[:3,:3]=[[1,0,0],[0,0,-1],[0,1,0]];n=trans(n,R)
            elif self.plane=='YZ':
                R=np.eye(4);R[:3,:3]=[[0,0,1],[1,0,0],[0,1,0]];n=trans(n,R)
            elif self.plane!='XY':raise ValueError('Unsupported workplane '+str(self.plane))
            nodes.append(n)
        if not nodes:raise ValueError('Empty extrusion')
        n=nodes[0]
        for a in nodes[1:]:n=Node('cut',children=(n,a))
        return self._new(node=n,profiles=())
    def cut(self,b):return self._new(node=Node('cut',children=(self.node,nodeof(b))))
    def union(self,b):return self._new(node=Node('union',children=(self.node,nodeof(b))))
    def intersect(self,b):return self._new(node=Node('intersection',children=(self.node,nodeof(b))))
    def translate(self,v):
        T=np.eye(4);T[:3,3]=v;return self._new(node=trans(self.node,T))
    def rotate(self,a,b,deg):
        a=np.array(a,float);v=np.array(b,float)-a;v/=np.linalg.norm(v);theta=math.radians(deg);c=math.cos(theta);s=math.sin(theta)
        x,y,z=v;K=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
        R=c*np.eye(3)+(1-c)*np.outer(v,v)+s*K;T=np.eye(4);T[:3,:3]=R;T[:3,3]=a-R@a
        return self._new(node=trans(self.node,T))
    def mirror(self,plane='XY'):
        T=np.eye(4);T[{'XY':2,'XZ':1,'YZ':0}[plane],{'XY':2,'XZ':1,'YZ':0}[plane]]=-1
        return self._new(node=trans(self.node,T))
    def val(self):return self
    def newObject(self,o):return self
    def fillet(self,r):return self  # Only spur_gear root blend; replaced by sampled CAD contour below.
    def isValid(self):return True
    def Volume(self):return 1.

def nodeof(x):return x.node if isinstance(x,W) else x

class Assembly:
    def __init__(self,name=''):self.name=name;self.items=[]
    def add(self,s,name='',**kwargs):self.items.append((name,s));return self
    def save(self,*a,**k):return self
class Solid:
    @staticmethod
    def makeCone(r0,r1,h,point=(0,0,0)):
        return W(node=Node('cone',(float(r0),float(r1),float(h)/2))).translate(np.array(point)+[0,0,h/2])
class Exports:
    @staticmethod
    def export(*a,**k):pass


def bounds(n):
    if n.op=='transform':
        lo,hi=bounds(n.children[0]);T=np.asarray(n.args).reshape(4,4)
        v=np.array([[x,y,z,1] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]])@T.T
        return v[:,:3].min(0),v[:,:3].max(0)
    if n.op in ('union','cut','intersection'):
        l,h=bounds(n.children[0]);l2,h2=bounds(n.children[1])
        if n.op=='union':return np.minimum(l,l2),np.maximum(h,h2)
        if n.op=='intersection':return np.maximum(l,l2),np.minimum(h,h2)
        return l,h
    if n.op=='box':a=np.array(n.args)
    elif n.op=='sphere':a=np.repeat(n.args[0],3)
    elif n.op=='cylinder':r,h=n.args;a=np.array([r,r,h])
    elif n.op=='cone':a=np.array([max(n.args[:2]),max(n.args[:2]),n.args[2]])
    elif n.op=='radial_cylinders':a=np.array([n.args[0]+n.args[2],n.args[0]+n.args[2],n.args[1]])
    elif n.op=='belt_teeth':
        r,h,pr,c,pitch,off,count=n.args;rad=pr-off+r
        return np.array([-rad,-rad,-h]),np.array([rad,c+rad,h])
    elif n.op in ('polygon','linear_polygon'):
        p=np.array(n.args[0]);lo=np.r_[p.min(0),-n.args[1]];hi=np.r_[p.max(0),n.args[1]]
        if n.op=='linear_polygon':lo[0]+=n.args[2];hi[0]+=n.args[2]+n.args[3]*(n.args[4]-1)
        return lo,hi
    else:raise ValueError(n.op)
    return -a,a


def capture():
    source=(ROOT/'generate_cad_p2.py').read_text()
    generator_hash=hashlib.sha256(source.encode()).hexdigest()
    tree=ast.parse(source)
    ctx={'__file__':str(OUT/'capture-work/generate_cad_p2.py'),'cq':types.SimpleNamespace(Workplane=W,Solid=Solid,Vector=lambda *x:tuple(x),Assembly=Assembly,Color=lambda *x:tuple(x),exporters=Exports),'np':np}
    (OUT/'capture-work').mkdir(parents=True,exist_ok=True)
    (OUT/'capture-work/spec.json').write_bytes((ROOT/'spec.json').read_bytes())
    placed=[]; active={}; skipped=[]
    native_meta=json.loads((ROOT/'cad_parts.json').read_text()) if (ROOT/'cad_parts.json').exists() else {}
    def addpart(name,s,material='aluminum',note='Custom nominal prototype geometry'):
        ctx['PARTS'][name]=s
        ctx['META'][name]={**native_meta.get(name,{}),'material':material,'status':note,'mass_kg':native_meta.get(name,{}).get('mass_kg',0.)}
        return s
    def place(body,label,s,material='aluminum',mass=None,note='CAD density'):
        rec={'body':body,'name':label,'material':material,'shape':s.node,'source_status':note}
        if active:
            rec['inspection_group']=int(active['label'][1:])
            rec['joint_axis']=np.asarray(active['axis'],dtype=float).tolist()
            center=np.array(active['origin'],float)
            if body==active['child']: center-=np.array(active.get('child_offset',(0,0,0)),float)
            rec['joint_center_mm']=center.tolist()
        placed.append(rec)
        ctx.get('MESHES',[]).append(rec)
        ctx['BODIES'].setdefault(body,[]).append({'name':label})
    # Mass calculations inside placement functions are deliberately excluded:
    # native CadQuery computes the physical inertia separately. Only geometric
    # operations from this symbolic execution become shader input.
    ctx.update(addpart=addpart,place=place,inertia_shape=lambda s,rho:(1.,np.zeros(3),np.eye(3)))
    skip_dynamic=False
    for n in tree.body:
        # The construction phase ends before CAD mass aggregation and output.
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('props','reserve') for t in n.targets):break
        if isinstance(n,ast.Import) and any(a.name=='cadquery' for a in n.names):continue
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ['addpart','place','inertia_shape']:continue
        code=ast.get_source_segment(source,n) or ''
        if 'cq.Wire.makeHelix' in code:
            skip_dynamic=True
        if skip_dynamic:
            skipped.append({'line':n.lineno,'reason':'Dynamic spring is emitted analytically from the shared spring specification.'})
            if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='addpart':
                call=n.value
                if call.args and isinstance(call.args[0],ast.Constant) and 'extension_spring' in str(call.args[0].value):
                    name=call.args[0].value
                    ctx['META'][name]={**native_meta.get(name,{}),'material':'steel','mass_kg':native_meta.get(name,{}).get('mass_kg',0.)}
                    skip_dynamic=False
            continue
        if isinstance(n,ast.FunctionDef) and n.name=='spur_gear':
            # The native root-filleted outline is inserted by refine_pinion.py.
            n.body=[x for x in n.body if not any(isinstance(y,ast.Attribute) and y.attr in ('Edges','Vertices','Center','fillet') for y in ast.walk(x)) and not (isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='root_edges' for t in x.targets)) and not (isinstance(x,ast.If) and 'root_edges' in ast.unparse(x.test))]
        if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='drive':
            vals=[eval(compile(ast.Expression(x),'<capture-arg>','eval'),ctx) for x in n.value.args]
            kws={k.arg:eval(compile(ast.Expression(k.value),'<capture-arg>','eval'),ctx) for k in n.value.keywords}
            import inspect
            active=inspect.signature(ctx['drive']).bind(*vals,**kws).arguments
        try:
            exec(compile(ast.fix_missing_locations(ast.Module(body=[n],type_ignores=[])),str(ROOT/'generate_cad_p2.py'),'exec'),ctx)
        except Exception as exc:
            raise RuntimeError(f'Unsupported CAD capture operation at generator line {n.lineno}: {code[:220]}') from exc
        finally:
            active={}
    if skip_dynamic:raise RuntimeError('Unterminated dynamic spring construction in CAD generator')
    transmissions={r['joint']:r for r in ctx.get('TRANSMISSIONS',[])}
    for o in placed:
        joint='J'+str(o.get('inspection_group',0))
        if joint not in transmissions:continue
        rec=transmissions[joint];axis=np.array(rec['axis'],float);axis/=np.linalg.norm(axis)
        z=np.array([0.,0.,1.]);cross=np.cross(z,axis);theta=math.acos(np.clip(z@axis,-1.,1.))
        if np.linalg.norm(cross)<1e-10:Q=np.eye(3) if axis[2]>0 else np.diag([1.,-1.,-1.])
        else:
            cross/=np.linalg.norm(cross);x,y,z0=cross;K=np.array([[0,-z0,y],[z0,0,-x],[-y,x,0]])
            Q=np.eye(3)+math.sin(theta)*K+(1.-math.cos(theta))*(K@K)
        if any(token in o['name'] for token in ('_drive_pulley','_input_shaft','_pulley_input_key')):
            o['demo_center_mm']=(np.array(rec['origin_mm'])+Q@np.array(rec['input_axis_local_offset_mm'])).tolist()
            o['demo_axis']=axis.tolist();o['demo_ratio']=1.
        elif any(token in o['name'] for token in ('_driven_pulley','_pulley_output_key')):
            o['demo_center_mm']=np.asarray(rec['child_origin_mm'],dtype=float).tolist();o['demo_axis']=axis.tolist();o['demo_ratio']=1.
    for name,s in ctx['leftjaw'].items:
        placed.append({'body':'jaw_right','name':'left_'+name,'material':'rubber' if 'pad' in name else 'steel' if 'rack' in name else 'polymer' if 'bushing' in name else 'aluminum','shape':s.translate((0,-219.2,0)).node,'inspection_group':7})
    for o in placed:
        if o['body']=='jaw':o['body']='jaw_left'
    import xml.etree.ElementTree as ET
    par=json.loads((ROOT/'parameters.json').read_text());p=par['puck']
    piece=W('XZ').circle(p['outer_radius_m']*1000).circle(p['bore_radius_m']*1000).extrude(p['height_m']*500,both=True)
    placed.append({'body':'puck','name':'workpiece','material':'brass','shape':piece.node,'inspection_group':10})
    xml=ET.fromstring((ROOT/'ARX-6-P5.xml').read_text())
    for name in ['nest_A_base','nest_A_seat','nest_B_base','nest_B_seat']:
        g=xml.find('.//geom[@name="'+name+'"]');sz=[float(x)*1000 for x in g.get('size').split()];pos=[float(x)*1000 for x in g.get('pos').split()]
        shape=W('XZ').circle(sz[0]).extrude(sz[1],both=True).translate(pos)
        placed.append({'body':'fixed','name':name,'material':'steel','shape':shape.node,'inspection_group':10})
    report={'generator_sha256':generator_hash,'spec_sha256':hashlib.sha256((ROOT/'spec.json').read_bytes()).hexdigest(),'placed_objects':len(placed),'unique_parts':len(ctx['PARTS']),'bodies':{},'scope':'Analytic CAD construction replay. Per-instance rigid geometry is captured; dynamic spring geometry comes from the same design specification. No triangle meshes are renderer inputs.','capture_mapping':'Semantic AST construction interpreter; explicit unsupported-operation failure; no source-line-number whitelist.','excluded_operations':skipped}
    payload=[]
    for o in placed:
        report['bodies'][o['body']]=report['bodies'].get(o['body'],0)+1
        l,h=bounds(o['shape']);payload.append({**o,'shape':o['shape'].plain(),'bounds_mm':[l.tolist(),h.tolist()]})
    (OUT/'csg-recipe.json').write_text(json.dumps(payload,separators=(',',':')))
    (OUT.parent/'reports/csg-capture.json').write_text(json.dumps(report,indent=2))
    (OUT/'captured-spec.json').write_bytes((ROOT/'spec.json').read_bytes())
    print(json.dumps({k:v for k,v in report.items() if k!='excluded_operations'},indent=2))
    return placed,ctx
if __name__=='__main__':capture()
