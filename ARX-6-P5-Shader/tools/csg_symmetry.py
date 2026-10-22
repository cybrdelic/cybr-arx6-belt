"""Exact algebraic reduction of complete regular rings of cylindrical cutters.

All cutter solids remain mathematically identical. Evaluating the nearest member
of an equally spaced circular set replaces evaluating every member separately.
No surface tessellation or approximation is introduced.
"""
from __future__ import annotations
import math
import numpy as np
from capture_csg import Node

STATS={'radial_sets':0,'individual_cylinders':0}

def cylinder(n):
    t=np.eye(4)
    while n.op=='transform':t=t@np.array(n.args).reshape(4,4);n=n.children[0]
    if n.op!='cylinder':return None
    if np.max(abs(t[:3,2]-np.array([0.,0.,1.])))>1e-8:return None
    return float(n.args[0]),float(n.args[1]),t[:3,3]

def optimize(n):
    if n.op!='cut':return Node(n.op,n.args,tuple(optimize(c) for c in n.children))
    cutters=[];base=n
    while base.op=='cut':cutters.append(base.children[1]);base=base.children[0]
    groups={}
    for i,c in enumerate(cutters):
        v=cylinder(c)
        if v is None:continue
        r,h,center=v;rad=math.hypot(center[0],center[1])
        key=tuple(round(x,7) for x in (r,h,center[2],rad))
        groups.setdefault(key,[]).append((i,center))
    used=set();replacements=[]
    for (r,h,z,rad),items in groups.items():
        count=len(items)
        if count<4 or rad<1e-6:continue
        angles=np.sort(np.mod([math.atan2(c[1],c[0]) for _,c in items],2*math.pi))
        gaps=np.diff(np.r_[angles,angles[0]+2*math.pi])
        if np.max(abs(gaps-2*math.pi/count))>1e-7:continue
        r,h,center=cylinder(cutters[items[0][0]])
        z=float(center[2]);rad=float(np.linalg.norm(center[:2]))
        primitive=Node('radial_cylinders',(r,h,rad,float(angles[0]),count))
        if abs(z)>1e-12:
            t=np.eye(4);t[2,3]=z;primitive=Node('transform',tuple(t.ravel()),(primitive,))
        used.update(i for i,_ in items);replacements.append(primitive)
        STATS['radial_sets']+=1;STATS['individual_cylinders']+=count
    result=optimize(base)
    for c in [c for i,c in enumerate(cutters) if i not in used]+replacements:
        result=Node('cut',children=(result,optimize(c)))
    return result

def verify():
    rng=np.random.default_rng(6165);worst=0.
    for count,rad,r,h,phase in [(36,28.0478897565,1.35,14.5,0.),(30,13.9739448783,.82,9.5,math.pi/30),(4,24,1.65,25,math.pi/4)]:
        p=rng.uniform([-45,-45,-35],[45,45,35],(6000,3))
        all_angles=phase+np.arange(count)*2*math.pi/count
        centers=rad*np.column_stack([np.cos(all_angles),np.sin(all_angles)])
        explicit=np.min(np.linalg.norm(p[:,None,:2]-centers[None,:,:],axis=2),axis=1)-r
        angle=np.arctan2(p[:,1],p[:,0])-phase
        closest=phase+np.floor(angle*count/(2*math.pi)+.5)*2*math.pi/count
        analytic=np.linalg.norm(p[:,:2]-rad*np.column_stack([np.cos(closest),np.sin(closest)]),axis=1)-r
        worst=max(worst,float(np.max(abs(explicit-analytic))))
    assert worst<1e-10,worst
    return {'randomized_comparisons':18000,'maximum_abs_distance_difference_mm':worst,'preserves':'Exact union of equally spaced identical cylindrical cutters; no decimation.'}


def belt_point(s,pr,c,off):
    h=math.pi*pr
    if s<h:
        a=math.pi+s/pr;return np.array([(pr-off)*math.cos(a),(pr-off)*math.sin(a)])
    s-=h
    if s<c:return np.array([pr-off,s])
    s-=c
    if s<h:
        a=s/pr;return np.array([(pr-off)*math.cos(a),c+(pr-off)*math.sin(a)])
    s-=h;return np.array([-pr+off,c-s])

def specialize_belt(n,f,size):
    """Preserve every native belt tooth, with an exact closed-path expression."""
    if n.op=='transform':return Node(n.op,n.args,(specialize_belt(n.children[0],f,size),))
    parts=[]
    def flatten(q):
        if q.op=='union':
            flatten(q.children[0]);flatten(q.children[1])
        else:parts.append(q)
    flatten(n)
    cylinders=[(i,cylinder(q)) for i,q in enumerate(parts)]
    cylinders=[(i,v) for i,v in cylinders if v is not None]
    count=int(f['belt_teeth']);assert len(cylinders)==count,(size,len(cylinders),count)
    pitch=float(f['pitch_mm']);pr=pitch*f['pulley_teeth']/(2*math.pi);c=float(f['center_distance_mm']);off=.60 if size=='large' else .35
    toothr=1.20 if size=='large' else .70;half=float(f['belt_width_mm'])/2;z=float(f['pulley_center_z_mm'])
    actual=np.array([v[2][:2] for _,v in cylinders]);expected=np.array([belt_point(k*pitch,pr,c,off) for k in range(count)])
    err=np.max(np.min(np.linalg.norm(actual[:,None,:]-expected[None,:,:],axis=2),axis=1));assert err<1e-8,err
    assert abs(count*pitch-2*c-2*math.pi*pr)<1e-8
    for _,(r,h,p) in cylinders:assert max(abs(r-toothr),abs(h-half),abs(p[2]-z))<1e-8
    teeth=Node('belt_teeth',(toothr,half,pr,c,pitch,off,count))
    t=np.eye(4);t[2,3]=z;teeth=Node('transform',tuple(t.ravel()),(teeth,))
    removed={i for i,_ in cylinders};retained=[q for i,q in enumerate(parts) if i not in removed]
    result=retained[0]
    for q in retained[1:]+[teeth]:result=Node('union',children=(result,q))
    STATS['closed_belts']=STATS.get('closed_belts',0)+1
    STATS['individual_belt_teeth']=STATS.get('individual_belt_teeth',0)+count
    return result

def belt_nearest(p,pr,c,pitch,off,shift):
    h=math.pi*pr;phase=shift%pitch;rad=pr-off
    if p[1]<=0:ang=2*math.pi-math.atan2(-p[1],p[0])
    else:ang=math.pi if p[0]<0 else 2*math.pi
    low=pr*(ang-math.pi)
    if p[1]>=c:ang=math.atan2(p[1]-c,p[0])
    else:ang=math.pi if p[0]<0 else 0.
    top=h+c+pr*ang
    projections=[low,h+min(c,max(0.,p[1])),top,2*h+c+c-min(c,max(0.,p[1]))]
    starts=[0,h,h+c,2*h+c];ends=[h,h+c,2*h+c,2*h+2*c]
    nearest=1e100
    for s,a,b in zip(projections,starts,ends):
        first=math.ceil((a-phase)/pitch-1e-12);last=math.floor((b-phase)/pitch+1e-12)
        k=min(last,max(first,math.floor((s-phase)/pitch+.5)))
        q=belt_point((phase+k*pitch)%(2*h+2*c),pr,c,off)
        nearest=min(nearest,float(np.linalg.norm(p-q)))
    return nearest

def verify_belts(spec):
    rng=np.random.default_rng(527);worst=0.;comparisons=0
    for size in ['large','small']:
        f=spec[size];pitch=f['pitch_mm'];pr=pitch*f['pulley_teeth']/(2*math.pi);c=f['center_distance_mm'];off=.60 if size=='large' else .35;count=f['belt_teeth'];period=count*pitch
        for shift in [0.,.17*pitch,.49*pitch,.93*pitch,-1.7*pitch]:
            centers=np.array([belt_point((k*pitch+shift)%period,pr,c,off) for k in range(count)])
            for p in rng.uniform([-pr*2,-pr*2],[pr*2,c+pr*2],(700,2)):
                exact=np.min(np.linalg.norm(centers-p,axis=1));optimized=belt_nearest(p,pr,c,pitch,off,shift)
                worst=max(worst,abs(exact-optimized));comparisons+=1
    assert worst<1e-8,worst
    return {'closed_belt_distance_comparisons':comparisons,'closed_belt_max_abs_difference_mm':worst,'belt_animation':'Inspection tooth transport along exact closed pitch path; static phase reproduces CAD; backing remains fixed.'}


def specialize_rack(n):
    """Exact nearest member of a finite regularly translated symmetric tooth row."""
    if n.op=='transform':return Node(n.op,n.args,(specialize_rack(n.children[0]),))
    parts=[]
    def flatten(q):
        if q.op=='union':flatten(q.children[0]);flatten(q.children[1])
        else:parts.append(q)
    flatten(n);polygons=[]
    for i,q in enumerate(parts):
        t=np.eye(4)
        while q.op=='transform':t=t@np.array(q.args).reshape(4,4);q=q.children[0]
        if q.op!='polygon' or len(q.args[0])!=4 or np.max(abs(t[:3,:3]-np.eye(3)))>1e-8:continue
        pts=np.array(q.args[0]);center=.5*(pts[:,0].min()+pts[:,0].max());pts[:,0]-=center
        polygons.append((i,pts,float(q.args[1]),center,t[:3,3]))
    assert len(polygons)==50,len(polygons)
    pts,h=polygons[0][1:3];z=polygons[0][4]
    for _,p,hh,x,t in polygons:assert max(np.max(abs(p-pts)),abs(hh-h),np.max(abs(t-z)))<1e-8
    assert np.max(abs(pts[:,0]+pts[::-1,0]))<1e-8
    centers=np.sort([p[3] for p in polygons]);step=float(np.mean(np.diff(centers)));assert np.max(abs(np.diff(centers)-step))<1e-8
    tooth=Node('linear_polygon',(tuple(map(tuple,pts.tolist())),h,float(centers[0]),step,len(polygons)))
    t=np.eye(4);t[:3,3]=z;tooth=Node('transform',tuple(t.ravel()),(tooth,))
    removed={p[0] for p in polygons};rest=[q for i,q in enumerate(parts) if i not in removed];result=rest[0]
    for q in rest[1:]+[tooth]:result=Node('union',children=(result,q))
    STATS['linear_tooth_rows']=STATS.get('linear_tooth_rows',0)+1;STATS['individual_rack_teeth']=STATS.get('individual_rack_teeth',0)+len(polygons)
    return result
