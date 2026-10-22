from paths import P2 as SOURCE_P2, P3 as OUTPUT_P3
#!/usr/bin/env python3
"""Compile the captured CAD construction to an immutable GLSL CSG instruction set.

Instruction tape and analytic primitives are constants in the fragment shader.
No mesh buffers, sampled SDF textures, model textures or environment maps exist.
Threaded per-body BVHs bound the analytic solids without changing their shapes.
"""
from pathlib import Path
import hashlib,json,math,sys
import numpy as np
from inspection_metadata import setup as inspection_setup, report as inspection_report
from csg_symmetry import optimize as optimize_csg, STATS as SYMMETRY_STATS, verify as verify_symmetry, specialize_belt, verify_belts, specialize_rack
from capture_csg import Node,bounds,ROOT,OUT

def fromplain(d):return Node(d['op'],tuple(d['args']),tuple(fromplain(x) for x in d['children']))
def num(x):
    x=float(x)
    if abs(x)<5e-10:x=0.
    s=format(x,'.10g');return s if any(c in s for c in '.e') else s+'.'
def vec(v,ty='vec4'):return ty+'('+','.join(num(x) for x in v)+')'
def ivec(v,ty='ivec4'):return ty+'('+','.join(str(int(x)) for x in v)+')'
def array(ty,name,values):return f'const {ty} {name}[{len(values)}]={ty}[{len(values)}](\n'+',\n'.join(values)+'\n);\n'

bodies=['fixed','turret','upper','fore','roll','bend','tool','jaw_left','jaw_right','puck']
prims=[];primdict={};points=[];polydict={};instructions=[];shapes=[];shapedict={};objects=[]

def leaf(n,T):
    key=json.dumps([n.plain(),np.round(T,9).tolist()],separators=(',',':'))
    if key in primdict:return primdict[key]
    typ={'box':0,'cylinder':1,'sphere':2,'cone':3,'polygon':4,'radial_cylinders':5,'belt_teeth':6,'linear_polygon':7}[n.op]
    args=list(n.args)
    if n.op in ('polygon','linear_polygon'):
        poly=args[0];pk=json.dumps(poly)
        if pk not in polydict:polydict[pk]=(len(points),len(poly));points.extend(poly)
        st,ln=polydict[pk];params=[st,ln,args[1]]
    else:params=args
    params=(params+[0,0,0])[:3]
    inv=np.linalg.inv(T)
    extra=[args[3],args[4]] if n.op in ('radial_cylinders','belt_teeth') else [0.,0.]
    detail=[args[5],args[6],0.,0.] if n.op=='belt_teeth' else [args[2],args[3],args[4],0.] if n.op=='linear_polygon' else [0.,0.,0.,0.]
    idx=len(prims);primdict[key]=idx;prims.append({'type':typ,'params':params,'extra':extra,'detail':detail,'rows':inv[:3].tolist()});return idx

def postfix(n,T,code):
    if n.op=='transform':postfix(n.children[0],T@np.array(n.args).reshape(4,4),code)
    elif n.op in ['union','cut','intersection']:
        postfix(n.children[0],T,code);postfix(n.children[1],T,code);code.append({'union':-1,'cut':-2,'intersection':-3}[n.op])
    else:code.append(leaf(n,T)+1)

def material(o):
    name=o['name'];m=o['material']
    if name=='workpiece':return 6
    if m in ('rubber','polymer'):return 5
    if name.endswith('_motor') or name.endswith('_brake_stator'):return 2
    if 'link_tube' in name:return 1  # display-only satin ceramic/powder finish
    if name.startswith('nest_'):return 2 if name.endswith('_base') else 4
    if 'gripper_motor' in name:return 2
    return 3 if m=='aluminum' else 4

raw=json.loads((OUT/'csg-recipe.json').read_text())
capture_report=json.loads((OUT.parent/'reports/csg-capture.json').read_text())
if hashlib.sha256((ROOT/'generate_cad_p2.py').read_bytes()).hexdigest()!=capture_report['generator_sha256']:raise RuntimeError('CAD source changed after capture; regenerate recipe')
if (OUT/'captured-spec.json').read_bytes()!=(ROOT/'spec.json').read_bytes():raise RuntimeError('CAD specification changed after capture; regenerate recipe')
spec=json.loads((ROOT/'spec.json').read_text())
for rec in raw:
    n=fromplain(rec['shape'])
    if rec['name'].endswith('_timing_belt'):
        size='large' if int(rec['inspection_group'])<=3 else 'small'
        n=specialize_belt(n,spec['folded_transmission'][size],size)
    if rec['name'] in ('upper_rack','left_lower_rack'):n=specialize_rack(n)
    n=optimize_csg(n);T=np.eye(4)
    while n.op=='transform':T=T@np.array(n.args).reshape(4,4);n=n.children[0]
    key=json.dumps(n.plain(),separators=(',',':'))
    if key not in shapedict:
        code=[];postfix(n,np.eye(4),code);idx=len(shapes);shapedict[key]=idx
        lo,hi=bounds(n);shapes.append({'start':len(instructions),'count':len(code),'lo':lo.tolist(),'hi':hi.tolist()});instructions.extend(code)
    si=shapedict[key];lo,hi=np.array(rec['bounds_mm'])
    objects.append({'name':rec['name'],'body':bodies.index(rec['body']),'shape':si,'matrix':T.tolist(),'bounds':[lo.tolist(),hi.tolist()],'material':material(rec),'pinion':int('gripper_pinion' in rec['name'])})

# Exact 2-D edge BVHs avoid visiting every point of the fine gear contour.
poly_nodes=[];poly_ranges={}
def poly_hierarchy(edge_ids,edge_bounds):
    idx=len(poly_nodes);lo=np.min([edge_bounds[i][0] for i in edge_ids],axis=0);hi=np.max([edge_bounds[i][1] for i in edge_ids],axis=0)
    node={'lo':lo.tolist(),'hi':hi.tolist(),'edge':-1,'escape':-1,'previous':-1};poly_nodes.append(node)
    if len(edge_ids)==1:
        i=edge_ids[0];node['edge']=i;node['previous']=edge_bounds[i][2]
    else:
        centers=np.array([(edge_bounds[i][0]+edge_bounds[i][1])*.5 for i in edge_ids]);axis=int(np.argmax(np.ptp(centers,axis=0)));edge_ids=sorted(edge_ids,key=lambda i:float(np.mean([edge_bounds[i][0][axis],edge_bounds[i][1][axis]])));mid=len(edge_ids)//2
        poly_hierarchy(edge_ids[:mid],edge_bounds);poly_hierarchy(edge_ids[mid:],edge_bounds)
    node['escape']=len(poly_nodes)
for start,count in polydict.values():
    edge_bounds={}
    for j in range(count):
        i=start+j;previous=start+(j-1)%count;a=np.array(points[previous]);b=np.array(points[i]);edge_bounds[i]=[np.minimum(a,b),np.maximum(a,b),previous]
    first=len(poly_nodes);poly_hierarchy(list(edge_bounds),edge_bounds);poly_ranges[start]=[first,len(poly_nodes)]
for primitive in prims:
    if primitive['type'] in (4,7):primitive['extra']=poly_ranges[int(primitive['params'][0])]
inspection_groups=inspection_setup(objects,raw,bodies)

# Bound all rigid parts, not the frozen-reference coils. Threaded BVH traversal
# has no per-ray stack and no recursion; escape indices skip entire subtrees.
nodes=[];ranges=[]

def hierarchy(ids):
    idx=len(nodes);lo=np.min([objects[i]['demo_bounds'][0] for i in ids],axis=0)-.06;hi=np.max([objects[i]['demo_bounds'][1] for i in ids],axis=0)+.06
    elo=np.min([objects[i]['explode_offset_mm'] for i in ids],axis=0);ehi=np.max([objects[i]['explode_offset_mm'] for i in ids],axis=0)
    mask=0
    for i in ids:mask|=1<<objects[i]['inspection_group']
    node={'lo':lo.tolist(),'hi':hi.tolist(),'object':-1,'escape':-1,'explode_lo':elo.tolist(),'explode_hi':ehi.tolist(),'group_mask':mask};nodes.append(node)
    if len(ids)==1:node['object']=ids[0]
    else:
        centers=np.array([np.mean(objects[i]['bounds'],axis=0) for i in ids]);axis=int(np.argmax(np.ptp(centers,axis=0)));ids=sorted(ids,key=lambda i:np.mean(objects[i]['bounds'],axis=0)[axis]);mid=len(ids)//2
        hierarchy(ids[:mid]);hierarchy(ids[mid:])
    node['escape']=len(nodes);return idx

for b in range(len(bodies)):
    start=len(nodes);ids=[i for i,o in enumerate(objects) if o['body']==b]
    if ids:hierarchy(ids)
    ranges.append([start,len(nodes)])
maxstack=0
for s in shapes:
    top=0
    for i in instructions[s['start']:s['start']+s['count']]:top+=1 if i>0 else -1;maxstack=max(maxstack,top)
    assert top==1

out='''// GENERATED FROM THE P5 CAD CONSTRUCTION. Dimensions are millimetres.
// Analytic boxes, capped cylinders, spheres, conical frusta and polygon extrusions.
// Exact periodic reductions, boolean operations and rigid placements are retained.
// There are no triangles, geometry texture samples or external model inputs.
'''
out+=array('vec4','CSG_P',[vec([p['type']]+p['params']) for p in prims])
out+=array('vec2','CSG_EXTRA',[vec(p['extra'],'vec2') for p in prims])
out+=array('vec4','CSG_DETAIL',[vec(p['detail'],'vec4') for p in prims])
for r in range(3):out+=array('vec4','CSG_R'+str(r),[vec(p['rows'][r]) for p in prims])
out+=array('vec2','CSG_POLY',[vec(p,'vec2') for p in points])
out+=array('vec2','POLY_BVH_LO',[vec(n['lo'],'vec2') for n in poly_nodes])
out+=array('vec2','POLY_BVH_HI',[vec(n['hi'],'vec2') for n in poly_nodes])
out+=array('ivec3','POLY_BVH_META',[ivec([n['edge'],n['previous'],n['escape']],'ivec3') for n in poly_nodes])
out+=array('int','CSG_CODE',[str(x) for x in instructions])
out+=array('ivec2','CSG_SHAPE',[ivec([s['start'],s['count']],'ivec2') for s in shapes])
out+=array('ivec4','CSG_OBJECT',[ivec([o['shape'],o['material'],o['body'],o['pinion']]) for o in objects])
out+=array('ivec2','CSG_INSPECT',[ivec([o['inspection_group'],o['cutaway']],'ivec2') for o in objects])
out+=array('int','CSG_INPUT_PHASE',[str(o['input_joint_phase']) for o in objects])
out+=array('vec3','CSG_EXPLODE',[vec(o['explode_offset_mm'],'vec3') for o in objects])
out+=array('vec4','CSG_DEMO_AXIS',[vec(o['demo_axis']+[o['demo_ratio']]) for o in objects])
out+=array('vec3','CSG_DEMO_CENTER',[vec(o['demo_center_mm'],'vec3') for o in objects])
out+=array('vec4','CSG_CUT_PLANE',[vec([s['hi'][0],.5*(s['lo'][0]+s['hi'][0]),s['hi'][2],.5*(s['lo'][2]+s['hi'][2])],'vec4') for s in shapes])
for r in range(3):out+=array('vec4','CSG_O'+str(r),[vec(np.linalg.inv(o['matrix'])[r]) for o in objects])
out+=array('vec3','BVH_LO',[vec(n['lo'],'vec3') for n in nodes])
out+=array('vec3','BVH_HI',[vec(n['hi'],'vec3') for n in nodes])
out+=array('ivec2','BVH_META',[ivec([n['object'],n['escape']],'ivec2') for n in nodes])
out+=array('ivec2','BVH_BODY',[ivec(r,'ivec2') for r in ranges])
leaf_map={n['object']:i for i,n in enumerate(nodes) if n['object']>=0}
out+=array('int','CSG_LEAF',[str(leaf_map[i]) for i in range(len(objects))])
out+=array('vec3','BVH_ELO',[vec(n['explode_lo'],'vec3') for n in nodes])
out+=array('vec3','BVH_EHI',[vec(n['explode_hi'],'vec3') for n in nodes])
out+=array('int','BVH_GROUP_MASK',[str(n['group_mask']) for n in nodes])
spec=json.loads((ROOT/'spec.json').read_text())
sa=[];sb=[];sd=[];sbody=[]
for key,parent,child,joint_offset in [('counterbalance',1,2,[0,144,0]),('elbow_counterbalance',2,3,[0,280,0])]:
    sp=spec[key]
    for j in range(2):
        a=np.array(sp['parent_anchor_m'],float)*1000+np.array(joint_offset)
        b=np.array(sp['child_anchor_m'],float)*1000
        if j:a[2]=b[2]=sp['second_spring_z_m']*1000
        sa.append(a);sb.append(b);sbody.append([parent,child]);sd.append([sp['mean_coil_diameter_mm']/2,sp['wire_diameter_mm']/2,sp['active_turns'],sp.get('hook_span_total_mm',18.)/2])
out+=array('vec3','SPRING_ANCHOR_A',[vec(v,'vec3') for v in sa])
out+=array('vec3','SPRING_ANCHOR_B',[vec(v,'vec3') for v in sb])
out+=array('vec4','SPRING_DETAIL',[vec(v) for v in sd])
# Native shoulder eyes are R3.6 with1.4wire; elbow eyes R3.1 with coil wire.
out+=array('vec2','SPRING_HOOK',[vec([3.6,1.4] if i<2 else [3.1,sd[i][1]],'vec2') for i in range(4)])
out+=array('ivec2','SPRING_BODY',[ivec(v,'ivec2') for v in sbody])
out+='\n#define CSG_STACK '+str(maxstack+1)+'\n'

(OUT/'geometry-constants.glsl').write_text(out)
report={'generator_sha256':capture_report['generator_sha256'],'spec_sha256':hashlib.sha256((ROOT/'spec.json').read_bytes()).hexdigest(),'objects':len(objects),'unique_constructive_shapes':len(shapes),'analytic_primitives':len(prims),'boolean_tape_instructions':len(instructions),'polygon_vertices':len(points),'threaded_bvh_nodes':len(nodes),'maximum_boolean_stack':maxstack,'constants_source_bytes':len(out.encode()),'input_csg_sha256':hashlib.sha256((OUT/'csg-recipe.json').read_bytes()).hexdigest()}
(OUT.parent/'reports/shader-geometry.json').write_text(json.dumps(report,indent=2));(OUT/'compiled-csg.json').write_text(json.dumps({'primitives':prims,'points':points,'instructions':instructions,'shapes':shapes,'objects':objects,'nodes':nodes,'ranges':ranges,'bodies':bodies},separators=(',',':')))
(OUT.parent/'reports/csg-symmetry.json').write_text(json.dumps({**SYMMETRY_STATS,**verify_symmetry(),**verify_belts(spec['folded_transmission'])},indent=2))
inspection=inspection_report(objects,bodies,inspection_groups)
inspection['generator_sha256']=capture_report['generator_sha256'];inspection['spec_sha256']=hashlib.sha256((ROOT/'spec.json').read_bytes()).hexdigest()
inspection['dynamic_parts']=[{'id':j,'name':('shoulder' if j<2 else 'elbow')+'_extension_spring_'+str(j%2+1),'group':8 if j<2 else 9,'parent_body':bodies[sbody[j][0]],'child_body':bodies[sbody[j][1]],'parent_anchor_mm':sa[j].tolist(),'child_anchor_mm':sb[j].tolist(),'coil_radius_mm':sd[j][0],'wire_radius_mm':sd[j][1],'active_turns':sd[j][2],'straight_lead_mm':sd[j][3],'eye_major_radius_mm':3.6 if j<2 else 3.1,'eye_wire_radius_mm':1.4 if j<2 else sd[j][1],'explode_offset_parent_mm':[-36. if j%2==0 else 36.,0.,36. if j<2 else -36.],'motion':'Coil pitch follows actual parent and child anchor locations; exploded translation is display-only.'} for j in range(4)]
inspection['inventory_totals']={'rigid_parts':len(objects),'dynamic_springs':4,'total_components':len(objects)+4}
(OUT.parent/'reports/inspection-parts.json').write_text(json.dumps(inspection,indent=2))
print(json.dumps(report,indent=2))
