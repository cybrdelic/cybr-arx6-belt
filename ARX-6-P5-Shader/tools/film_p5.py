#!/usr/bin/env python3
"""Render the P5 inspection film directly from the procedural fragment shader.

Every output frame is evaluated at its own camera/state. The first chapter is
the fresh physical solve. Disassembly and isolated mechanism rotation are
explicitly marked as visual inspection, not a simulation of loose components.
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, math, os, subprocess, sys, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from egl_render import EGLRenderer, physical_state, apply, aces

ROOT=Path(__file__).resolve().parents[1]
ENG=ROOT.parent/'ARX-6-P5-Engineering'
FILM=ROOT/'film'

CHAPTERS=[
 dict(id='01-operation',duration=10,group=0,title='ARX / 6',subtitle='Compact drives. Independent payload. Fresh physical solve.',note='RECORDED DYNAMICS · TWO TRANSFERS'),
 dict(id='02-disassembly',duration=6,group=0,title='Every assembly, revealed',subtitle='The same CAD parts separate along service and inspection directions.',note='VISUAL DISASSEMBLY · ALL RIGID PARTS'),
 dict(id='03-base',duration=5,group=1,title='01 / Base rotation',subtitle='Folded motor and reducer → toothed belt → output shaft.',note='DIRECT OUTPUT BRAKE · ADJUSTABLE BELT CARRIER'),
 dict(id='04-shoulder',duration=6,group=2,title='02 / Shoulder drive',subtitle='The full-size drive folds beside the joint instead of projecting outward.',note='5M BELT · 36T PULLEYS · 25 MM WIDTH'),
 dict(id='05-elbow',duration=6,group=3,title='03 / Elbow drive',subtitle='The belt transfers reducer torque; the brake acts directly on the output.',note='REMOVABLE COVER · SUPPORTED INPUT SHAFT'),
 dict(id='06-shoulder-balance',duration=4,group=8,title='Shoulder counterbalance',subtitle='Paired extension springs support the arm through its changing lever arm.',note='ACTUAL MOVING ANCHORS · RECORDED JOINT MOTION'),
 dict(id='07-elbow-balance',duration=4,group=9,title='Elbow counterbalance',subtitle='The fixed anchor moves below the elbow; the raised mast is removed.',note='COMPACT TAIL ARM · PAIRED SPRINGS'),
 dict(id='08-wrist-roll',duration=4,group=4,title='04 / Wrist roll',subtitle='A smaller folded transmission turns the wrist about the forearm axis.',note='3M BELT · 30T PULLEYS · 15 MM WIDTH'),
 dict(id='09-wrist-bend',duration=4,group=5,title='05 / Wrist bend',subtitle='The fork, bearings and output brake support the bend axis.',note='ISOLATED MECHANISM · SECTIONED HOUSINGS'),
 dict(id='10-tool-roll',duration=4,group=6,title='06 / Tool roll',subtitle='The final folded stage rotates the tool without the former axial stack.',note='FULL MOTOR ENVELOPE · SHORTER AXIAL PACKAGE'),
 dict(id='11-gripper',duration=6,group=7,title='Rack-and-pinion gripper',subtitle='One pinion moves opposed racks; guided jaws transmit force through the pads.',note='MECHANISM INSPECTION · RECORDED JAW POSITIONS'),
 dict(id='12-fixtures',duration=4,group=10,title='Payload and receiving nests',subtitle='The puck remains a free rigid body. Friction and contact determine its motion.',note='NO KINEMATIC ATTACHMENT · NO HIDDEN PAYLOAD WELD'),
 dict(id='13-structure',duration=4,group=11,title='Links and load path',subtitle='Rigid links carry joint reactions between the bearings and tool.',note='CAD-DERIVED SOLIDS · INDIVIDUAL FASTENERS RETAINED'),
 dict(id='14-reassembly',duration=5,group=0,title='ARX / 6 · P5',subtitle='Compact engineered prototype. CAD, dynamics and renderer share one revision.',note='REASSEMBLY · SOURCE AND VALIDATION INCLUDED'),
]

def smooth(x):
 x=float(np.clip(x,0,1));return x*x*(3-2*x)
def ry(a):
 c,s=math.cos(a),math.sin(a);return np.array([[c,0,s],[0,1,0],[-s,0,c]])
def rz(a):
 c,s=math.cos(a),math.sin(a);return np.array([[c,-s,0],[s,c,0],[0,0,1]])
def quat(q):
 w,x,y,z=np.asarray(q)/np.linalg.norm(q)
 return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def transforms(s):
 q=s[1:7];base=ry(-q[0]);shoulder=np.array([0.,144.,0.]);upper=base@rz(-q[1]);elbow=shoulder+upper@np.array([0.,280.,0.]);fore=upper@rz(-q[2]);wrist=elbow+fore@np.array([0.,260.,0.]);roll=fore@ry(q[3]);bend=roll@rz(-q[4]);tool=bend@ry(q[5]);zero=np.zeros(3)
 return {'fixed':(np.eye(3),zero),'turret':(base,zero),'upper':(upper,shoulder),'fore':(fore,elbow),'roll':(roll,wrist),'bend':(bend,wrist),'tool':(tool,wrist),'jaw_left':(tool,wrist+tool@np.array([s[13]*1000,219.2,0])),'jaw_right':(tool,wrist+tool@np.array([-s[14]*1000,219.2,0])),'puck':(quat(s[18:22]),s[15:18]*1000)}

class Director:
 def __init__(self):
  self.trajectory_path=ENG/'integration/results/nominal.json'
  self.trace=json.loads(self.trajectory_path.read_text())
  expected={'xml_sha256':'ARX-6-P5.xml','controller_sha256':'controller.mjs','safety_sha256':'safety.mjs','parameters_sha256':'parameters.json','geometry_sha256':'geometry-meshes.json','collision_proxies_sha256':'p5_collision_proxies.json','cad_mass_properties_sha256':'mass_properties.json'}
  provenance=self.trace.get('metrics',{}).get('provenance',{})
  for key,filename in expected.items():
   actual=hashlib.sha256((ENG/'integration'/filename).read_bytes()).hexdigest()
   if provenance.get(key)!=actual:raise RuntimeError('The film requires a fresh physical trace: '+filename+' differs')
  capture=json.loads((ROOT/'reports/csg-capture.json').read_text())
  if capture['generator_sha256']!=hashlib.sha256((ENG/'integration/generate_cad_p2.py').read_bytes()).hexdigest():raise RuntimeError('Stale captured CAD geometry')
  self.frames=np.asarray(self.trace['frames'])
  self.meta=json.loads((ROOT/'reports/inspection-parts.json').read_text())
  self.parts=self.meta['parts']
  self.fit_points={}
  self.timing=[];t=0
  for c in CHAPTERS:
   self.timing.append(dict(c,start=t,end=t+c['duration']));t+=c['duration']
  self.duration=t
 def points(self,s,group,explode):
  ts=transforms(s);points=[]
  for p in self.parts:
   if group and p['group']!=group:continue
   if not group and p['body']=='fixed' and any(x in p['name'].lower() for x in ('floor','ground','worktop','table')):continue
   R,o=ts[p['body']];lo,hi=np.asarray(p['bounds_mm']);off=np.asarray(p['explode_offset_mm'])*explode
   points.extend([R@(np.array(v)+off)+o for v in itertools.product(*zip(lo,hi))])
  if not points:raise ValueError('No geometry for inspection '+str(group))
  return np.asarray(points)/200
 def bounds(self,s,group,explode):
  pts=self.points(s,group,explode);return pts.min(0),pts.max(0)
 def inspection_state(self,time,group):
  s=physical_state(self.frames,time)
  if group in (7,8,9):
   reference=physical_state(self.frames,2.5)
   moving=s[2] if group==8 else s[3] if group==9 else None
   s[1:7]=reference[1:7]
   if group==8:s[2]=moving
   if group==9:s[3]=moving
  return s
 def state(self,index,local):
  c=CHAPTERS[index];dur=c['duration'];p=np.clip(local/dur,0,1);g=c['group'];ex=0.;cut=0.;mech=0.
  pt=2.5
  if index==0:pt=min(local,9.999)
  elif index==1:ex=.70*smooth((p-.08)/.68)
  elif index==13:ex=.70*(1-smooth((p-.1)/.72));pt=2.5
  elif g in (8,9):pt=1.6+3.2*p
  elif g==7:pt=.45+2.8*p;ex=.22*smooth((p-.58)/.27);cut=smooth((p-.08)/.22)
  elif g==10:pt=.1+8.9*p
  elif g==11:ex=.32+.16*math.sin(p*math.pi)
  else:
   ex=.10+.35*smooth((p-.12)/.64)
   cut=smooth((p-.12)/.25)
   mech=p*math.tau*.55
  s=self.inspection_state(pt,g)
  # Stable bounding envelope across each camera move prevents camera breathing.
  fit_ex=.70 if index in (1,13) else .45 if 1<=g<=6 else .25 if g==7 else .48 if g==11 else 0.
  fit_s=physical_state(self.frames,2.5)
  points=self.fit_points.get(index)
  if points is None:
   points=self.points(fit_s,g,fit_ex)
   if index==0:
    points=np.concatenate([self.points(physical_state(self.frames,t),0,0) for t in np.linspace(0,9.99,16)])
   if g in (7,8,9,10):
    times=np.linspace(1.6,4.8,12) if g in (8,9) else np.linspace(.1,9.8,12)
    points=np.concatenate([self.points(self.inspection_state(t,g),g,fit_ex) for t in times])
   self.fit_points[index]=points
  lo,hi=points.min(0),points.max(0)
  target=(lo+hi)/2
  az=.70+.30*(p-.5);el=.22
  direction=np.array([math.sin(az)*math.cos(el),math.sin(el),math.cos(az)*math.cos(el)])
  ts=transforms(fit_s)
  if 1<=g<=6:
   # View from the belt-cover side of each joint; a shallow orbit reveals depth.
   p0=next(x for x in self.parts if x['group']==g)
   R,_=ts[p0['body']];axis=R@np.asarray(p0['demo_axis']);axis=axis/max(np.linalg.norm(axis),1e-9)
   tangent=np.cross(axis,np.array([0.,1.,0.]))
   if np.linalg.norm(tangent)<.2:tangent=np.array([1.,0.,0.])
   tangent/=np.linalg.norm(tangent)
   direction=-axis+.42*tangent+.25*np.array([0.,1.,0.])+(.20*(p-.5))*np.cross(tangent,axis)
   direction/=np.linalg.norm(direction)
  if g in (8,9):direction=np.array([.82,.22,1. if g==8 else -1.]);direction/=np.linalg.norm(direction)
  if g==7:direction=ts['tool'][0]@np.array([.28,.08,1.]);direction/=np.linalg.norm(direction)
  if g==10:direction=np.array([.35,.95,1.]);direction/=np.linalg.norm(direction)
  if g==11:direction=np.array([.75,.25,1.]);direction/=np.linalg.norm(direction)
  if g:direction=ry(.20*(p-.5))@direction
  forward=-direction;right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
  target+=up*.02*(hi[1]-lo[1])
  relative=points-target
  x,y,z=relative@right,relative@up,relative@direction
  focal=3.3;distance=max(np.max(z+focal*np.abs(y)/.72),np.max(z+focal*np.abs(x)/(16/9*.84)))+.08
  distance=max(distance,.60)
  origin=target+direction*distance
  callouts=[];phase=min(2,int(p*3))
  if 1<=g<=6:
   j='J'+str(g)
   final={1:[('_bearing_0','BEARINGS','Support the output'),('_output_shaft','OUTPUT SHAFT','Joint torque path')],2:[('_brake_stator','OUTPUT BRAKE','Holds the joint'),('_pulley_output_key','SHAFT KEY','Locks pulley to shaft')],3:[('_input_support_bearing','INPUT BEARING','Supports the extension'),('_front_cover','SERVICE COVER','Closes the carrier')],4:[('_index_sensor','INDEX SENSOR','Reference position'),('_stop_pin_0','STOP PIN','Physical travel limit')],5:[('_integral_stop_target','STOP TARGET','Meets the fixed pin'),('_brake_strut_0','BRAKE SUPPORT','Carries housing reaction')],6:[('_pulley_output_key','PULLEY KEY','Transfers joint torque'),('DIN471','RETAINER','Locates the shaft')]}
   pairs=[[('_motor','MOTOR','Produces shaft torque'),('_gearhead','GEARHEAD','Reduces speed')],[('_timing_belt','TOOTHED BELT','Transfers torque 1:1'),('_tension_block','TENSION BLOCK','Sets center distance')],final[g]][phase]
   for token,title,note in pairs:
    item=next((v for v in self.parts if v['group']==g and (v['name']==j+token or token=='DIN471' and token in v['name'])),None)
    if item:callouts.append((item,title,note))
  elif g==7:
   pairs=[[('gripper_motor','MOTOR','Turns the pinion'),('gripper_pinion','PINION','Drives opposed racks')],[('upper_rack','RACK','Converts rotary motion'),('guide_rod_10','GUIDE RODS','Constrain jaw travel')],[('finger_pad','CONTACT PADS','Transmit grip force'),('gripper_cable_clamp_cap','CABLE CLAMP','Provides strain relief')]][phase]
   for token,title,note in pairs:
    item=next((v for v in self.parts if v['group']==g and token in v['name']),None)
    if item:callouts.append((item,title,note))
  visible=[];frames=transforms(s)
  for item,title,note in callouts:
   center=np.mean(item['bounds_mm'],axis=0)
   angle=mech*item.get('demo_ratio',0.)
   if abs(angle)>1e-9:
    axis=np.asarray(item['demo_axis']);v=center-np.asarray(item['demo_center_mm'])
    center=np.asarray(item['demo_center_mm'])+v*math.cos(angle)+np.cross(axis,v)*math.sin(angle)+axis*np.dot(axis,v)*(1-math.cos(angle))
   center+=np.asarray(item['explode_offset_mm'])*ex
   R,o=frames[item['body']];visible.append({'title':title,'note':note,'point':(R@center+o)/200})
  return dict(state=s,physical_time=pt,group=g,explode=ex,cutaway=cut,mechanism=mech,origin=origin,target=target,focal=focal,chapter=c,phase=float(p),callouts=visible)

def uniforms(r,d,frame):
 apply(r,d['state'])
 for n,v in [('u_time',d['physical_time']),('u_frame',frame),('u_samples',1),('u_exposure',.38),('u_inspect',d['group']),('u_explode',d['explode']),('u_cutaway',d['cutaway']),('u_mechanism',d['mechanism']),('u_camera_override',1),('u_camera_origin',d['origin']),('u_camera_target',d['target']),('u_camera_focal',d['focal']),('u_aperture',0.)]:r.uniform(n,v)

def caption(pixels,d,total_time,total_duration):
 im=Image.fromarray(pixels,'RGB');w,h=im.size;scale=w/1920
 overlay=Image.new('RGBA',im.size);dr=ImageDraw.Draw(overlay)
 regular='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf';mono='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
 ft=ImageFont.truetype(bold,max(12,round(40*scale)));fs=ImageFont.truetype(regular,max(9,round(22*scale)));fn=ImageFont.truetype(mono,max(8,round(16*scale)))
 for y in range(round(170*scale)):
  alpha=round(190*(1-y/max(1,170*scale))**1.4);dr.line((0,y,w,y),fill=(9,12,15,alpha))
 for y in range(round(135*scale)):
  alpha=round(180*(1-y/max(1,135*scale))**1.4);dr.line((0,h-1-y,w,h-1-y),fill=(9,12,15,alpha))
 x=round(70*scale);c=d['chapter']
 dr.text((x,round(45*scale)),c['title'],font=ft,fill=(236,238,236,255))
 dr.text((x,round(100*scale)),c['subtitle'],font=fs,fill=(181,191,195,255))
 forward=d['target']-d['origin'];forward/=np.linalg.norm(forward);right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
 for i,entry in enumerate(d.get('callouts',[])):
  relative=entry['point']-d['origin'];depth=np.dot(relative,forward)
  if depth<=0:continue
  px=w/2+d['focal']*np.dot(relative,right)/depth*h/2;py=h/2-d['focal']*np.dot(relative,up)/depth*h/2
  if not 0<px<w or not 0<py<h:continue
  lx=round(72*scale) if i==0 else w-round(440*scale);ly=round(h*(.48 if i==0 else .70));lw=round(365*scale);lh=round(78*scale)
  alpha=round(220*smooth(d['phase']*12));ink=(183,162,127,alpha)
  anchor=(lx+lw,ly+lh/2) if i==0 else (lx,ly+lh/2)
  dr.line([(px,py),(anchor[0]+(18*scale if i==0 else -18*scale),anchor[1]),anchor],fill=ink,width=max(1,round(scale)))
  radius=max(1,round(3*scale));dr.ellipse((px-radius,py-radius,px+radius,py+radius),fill=ink)
  dr.rounded_rectangle((lx,ly,lx+lw,ly+lh),radius=round(5*scale),fill=(17,22,26,round(alpha*.86)))
  dr.text((lx+round(15*scale),ly+round(10*scale)),entry['title'],font=fn,fill=(205,190,160,alpha))
  dr.text((lx+round(15*scale),ly+round(37*scale)),entry['note'],font=fs,fill=(198,207,212,alpha))
 dr.text((x,h-round(78*scale)),c['note'],font=fn,fill=(194,176,143,255))
 tag='PHYSICAL STATE' if c['group']==0 and c['id'].startswith('01') else 'INSPECTION VIEW'
 text=f'{tag}   /   {total_time:05.1f} s';box=dr.textbbox((0,0),text,font=fn)
 dr.text((w-x-(box[2]-box[0]),h-round(78*scale)),text,font=fn,fill=(154,168,177,255))
 dr.rectangle((x,h-round(35*scale),w-x,h-round(32*scale)),fill=(69,78,83,255))
 dr.rectangle((x,h-round(35*scale),x+(w-2*x)*total_time/total_duration,h-round(32*scale)),fill=(188,161,114,255))
 return np.asarray(Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB'))

def hashfile(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def metadata(director,fps,width,height,shader):
 return {'revision':'P5','width':width,'height':height,'fps':fps,'duration_seconds':director.duration,'chapters':director.timing,'shader_sha256':hashfile(shader),'trajectory_sha256':hashfile(director.trajectory_path),'inspection_sha256':hashfile(ROOT/'reports/inspection-parts.json'),'director_sha256':hashfile(Path(__file__)),'renderer_sha256':hashfile(ROOT/'tools/egl_render.py'),'table_packer_sha256':hashfile(ROOT/'tools/shader_tables.py'),'method':'One full-screen fragment program; native procedural CAD-derived CSG at every frame; shader output plus typography; physical replay distinguished from visual mechanism inspection.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--width',type=int,default=1920);p.add_argument('--height',type=int,default=1080);p.add_argument('--fps',type=int,default=24);p.add_argument('--samples',type=int,default=1);p.add_argument('--shadows',type=int,default=1);p.add_argument('--quality',type=int,default=1);p.add_argument('--chapter',type=int,action='append');p.add_argument('--preview',action='store_true');p.add_argument('--join',action='store_true');p.add_argument('--no-caption',action='store_true');a=p.parse_args()
 FILM.mkdir(exist_ok=True);director=Director();shader=ROOT/'ARX-6-P5-Live.glsl';meta=metadata(director,a.fps,a.width,a.height,shader);meta.update(camera_samples=a.samples,shadow_samples=a.shadows,quality=a.quality)
 if a.join:
  chunks=[FILM/(c['id']+'.mp4') for c in CHAPTERS]
  for c,path in zip(CHAPTERS,chunks):
   rep=json.loads(path.with_suffix('.json').read_text())
   for key in ['shader_sha256','trajectory_sha256','inspection_sha256','director_sha256','renderer_sha256','table_packer_sha256','width','height','fps','camera_samples','shadow_samples','quality']:
    if rep[key]!=meta[key]:raise ValueError(f'Stale/mismatched {path.name}: {key}')
   if rep['frames']!=c['duration']*a.fps:raise ValueError('Incomplete '+path.name)
  meta['numeric_table_transport']=rep['numeric_table_transport']
  listing=FILM/'concat.txt';listing.write_text('\n'.join("file '"+str(x)+"'" for x in chunks)+'\n')
  ffmeta=FILM/'chapters.ffmeta';ffmeta.write_text(';FFMETADATA1\ntitle=ARX-6 P5 — Compact Drive Inspection\nartist=Procedural CAD renderer\n'+''.join(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(c['start']*1000)}\nEND={int(c['end']*1000)}\ntitle={c['title']}\n" for c in director.timing))
  dest=ROOT/'ARX-6-P5-Inspection-1080p.mp4'
  subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-i',str(ffmeta),'-map_metadata','1','-map_chapters','1','-c','copy','-movflags','+faststart',str(dest)],check=True)
  meta.update(file=dest.name,bytes=dest.stat().st_size,sha256=hashfile(dest),frames=director.duration*a.fps)
  (ROOT/'reports/film-build.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta));return
 defs=f'#define AA 1\n#define P3_QUALITY {a.quality}\n#define P5_SHADOW_SAMPLES {a.shadows}\n#define CAPTURE 1\n'
 r=EGLRenderer(a.width,a.height,shader.read_text(),defs,geometry_buffers=True);meta['numeric_table_transport']=r.table_info;print(json.dumps({'renderer':r.info,'compile_seconds':r.compile_seconds,'source':meta['shader_sha256'],'numeric_tables':r.table_info['table_count'],'table_bytes':r.table_info['bytes']}),flush=True)
 indexes=a.chapter if a.chapter else range(len(CHAPTERS))
 for ci in indexes:
  c=CHAPTERS[ci];start=director.timing[ci]['start'];frames=1 if a.preview else c['duration']*a.fps
  dest=FILM/(c['id']+('-preview.png' if a.preview else '.mp4'));report=dest.with_suffix('.json');begin=time.monotonic()
  if not a.preview and report.exists() and dest.exists():
   prev=json.loads(report.read_text())
   if all(prev.get(k)==meta.get(k) for k in ['shader_sha256','trajectory_sha256','inspection_sha256','director_sha256','renderer_sha256','table_packer_sha256','width','height','fps','camera_samples','shadow_samples','quality']) and prev.get('frames')==frames:
    print('skip verified chapter',c['id'],flush=True);continue
  enc=None
  if not a.preview:
   enc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{a.width}x{a.height}','-r',str(a.fps),'-i','-','-an','-c:v','libx264','-threads','2','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],stdin=subprocess.PIPE)
  first_hash=None;last_hash=None;render_hashes=set();audit=[]
  try:
   for fi in range(frames):
    local=c['duration']*.55 if a.preview else fi/a.fps
    d=director.state(ci,local);acc=np.zeros((a.height,a.width,3),np.float32)
    for si in range(a.samples):
     uniforms(r,d,si);acc+=r.draw()
    pix=np.uint8(np.clip(aces(acc/a.samples)*255+.5,0,255))
    rawhash=hashlib.sha256(pix.tobytes()).hexdigest()
    if fi==0:first_hash=rawhash
    last_hash=rawhash
    render_hashes.add(rawhash)
    audit.append({'frame':fi,'film_time_s':start+local,'physical_time_s':d['physical_time'],'group':d['group'],'explode':d['explode'],'cutaway':d['cutaway'],'mechanism_rad':d['mechanism'],'camera_origin':d['origin'].tolist(),'camera_target':d['target'].tolist(),'raw_shader_rgb8_sha256':rawhash})
    if not a.no_caption:pix=caption(pix,d,start+local,director.duration)
    if a.preview:Image.fromarray(pix).save(dest)
    else:
     enc.stdin.write(pix.tobytes())
     if fi in (0,frames//2,frames-1):Image.fromarray(pix).save(FILM/(c['id']+f'-frame-{fi:04d}.jpg'),quality=94)
    if fi%max(1,a.fps)==0 or fi==frames-1:print(json.dumps({'chapter':c['id'],'frame':fi+1,'frames':frames,'elapsed_s':round(time.monotonic()-begin,2)}),flush=True)
   if enc:
    enc.stdin.close()
    if enc.wait()!=0:raise RuntimeError('ffmpeg failed '+c['id'])
   (FILM/(c['id']+('-preview' if a.preview else '')+'-frame-audit.json')).write_text(json.dumps(audit,separators=(',',':')))
   report.write_text(json.dumps({**meta,'chapter':ci,'frames':frames,'unique_raw_shader_frames':len(render_hashes),'seconds':time.monotonic()-begin,'first_render_sha256':first_hash,'last_render_sha256':last_hash,'output_sha256':hashfile(dest),'bytes':dest.stat().st_size},indent=2))
  finally:
   if enc and enc.poll() is None:enc.kill();enc.wait()
 r.close()

if __name__=='__main__':main()
