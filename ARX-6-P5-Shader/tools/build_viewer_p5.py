#!/usr/bin/env python3
"""Build the offline P5 film, CAD inspection and fresh live-physics viewer."""
from pathlib import Path
import base64, hashlib, json, re
from PIL import Image
from webgl_tables import build as build_webgl_tables

ROOT=Path(__file__).resolve().parents[1]
ENG=ROOT.parent/'ARX-6-P5-Engineering'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(text,old,new):
 if old not in text:raise RuntimeError('Missing template hook: '+old[:90])
 return text.replace(old,new)

def build():
 A=json.loads((ROOT/'assets/mujoco-runtime.json').read_text())
 A['xml']=(ENG/'integration/ARX-6-P5.xml').read_text()
 A['p']=json.loads((ENG/'integration/parameters.json').read_text())
 trace=json.loads((ENG/'integration/results/nominal.json').read_text())
 A['api']=trace['interface'];A['frames']=[f[:22] for f in trace['frames']]
 controller=(ENG/'integration/controller.mjs').read_text()
 controller=re.sub(r"^import \{[^\n]+\} from './safety.mjs';\n",'',controller)
 A['controllerJS']=(ENG/'integration/safety.mjs').read_text()+'\n'+controller
 A['physicsSHA']={p.name:sha(p) for p in [ENG/'integration/ARX-6-P5.xml',ENG/'integration/parameters.json',ENG/'integration/controller.mjs',ENG/'integration/safety.mjs',ENG/'integration/mass_properties.json',ENG/'integration/p5_collision_proxies.json']}
 A['shader']=(ROOT/'ARX-6-P5-Live.glsl').read_text();A['shaderSHA']=hashlib.sha256(A['shader'].encode()).hexdigest()
 A['webglNumeric']=build_webgl_tables(A['shader'])
 A['inspection']=json.loads((ROOT/'reports/inspection-parts.json').read_text())
 film=ROOT/'ARX-6-P5-Inspection-1080p.mp4'
 A['film']=base64.b64encode(film.read_bytes()).decode() if film.exists() else ''
 A['filmMetadata']=json.loads((ROOT/'reports/film-build.json').read_text()) if film.exists() else {'duration_seconds':72}
 poster=ROOT/'ARX-6-P5-1080p.png'
 if not poster.exists():poster=ROOT/'film/01-operation-preview.png'
 im=Image.open(poster);im.thumbnail((1920,1080));(ROOT/'assets').mkdir(exist_ok=True);im.save(ROOT/'assets/poster.jpg',quality=94)
 poster64='data:image/jpeg;base64,'+base64.b64encode((ROOT/'assets/poster.jpg').read_bytes()).decode()
 h=(ROOT/'source/player-base.html').read_text().replace('P4','P5')
 h=h.replace('Save MP5','Save MP4')
 h=replace(h,'Recorded nominal physics · 10 seconds · The film does not use WebGL.','72 seconds · Physical operation, exploded assemblies and mechanism inspection.')
 h=replace(h,'<details id="detail" hidden>','''<details id="inspection" hidden><summary>Inspect components</summary><label>Assembly<select id="assembly"><option value="0">Complete robot</option></select></label><label>Individual part<select id="part"><option value="0">All parts in assembly</option></select></label><label>Explode<input id="explode" type="range" min="0" max="1" step=".01" value="0"></label><label><input id="cut" type="checkbox"> Section modeled housings</label><label><input id="mechanism" type="checkbox"> Rotate transmission for inspection</label><p id="partnote">The physical model stays assembled. These controls separate the rendered parts for inspection.</p></details><details id="detail" hidden>''')
 h=replace(h,'</style>','''#inspection{position:fixed;left:22px;top:112px;width:280px;padding:12px 14px;background:#182026ed;border:1px solid #46546055;border-radius:8px;color:#b8c5ce;font-size:11px}#inspection summary{cursor:pointer;font-size:12px}#inspection label{display:block;margin-top:12px}#inspection select{display:block;width:100%;margin-top:5px;padding:7px;font-size:10px}#inspection input[type=range]{display:block;width:100%;margin-top:7px;accent-color:#c5ae84}#inspection p{font-size:10px;line-height:1.6;color:#8e9da7}@media(max-width:700px){#inspection{left:14px;top:126px;width:min(260px,86vw)}#detail{display:none}}\n</style>''')
 h=replace(h,"$('reflections').onchange=",'''for(const g of A.inspection.groups){const o=document.createElement('option');o.value=g.id;o.textContent=g.name;$('assembly').append(o);}
function populateParts(){
 const selected=Number($('assembly').value);$('part').replaceChildren(new Option('All parts in assembly','0'));
 for(const p of A.inspection.parts)if(!selected||p.group===selected)$('part').append(new Option(p.name,String(p.id+1)));
}
populateParts();
$('assembly').onchange=()=>{populateParts();drag=[0,0];zoom=0;dirty=true;queueLoop();};
$('part').onchange=()=>{drag=[0,0];zoom=0;dirty=true;queueLoop();const p=A.inspection.parts.find(p=>p.id+1===Number($('part').value));$('partnote').textContent=p?p.name+' · '+p.body+' body · Exact CAD-derived part. Vendor envelopes do not expose unmodeled internal components.':'The physical model stays assembled. These controls separate the rendered parts for inspection.';};
for(const id of ['explode','cut','mechanism'])$(id).oninput=()=>{dirty=true;queueLoop();};
$('reflections').onchange=''' )
 h=replace(h,"$('downloadFilm').onclick=", "$('filmnote').textContent=A.filmMetadata.duration_seconds+' seconds · Physical operation, exploded assemblies and mechanism inspection.';\n$('downloadFilm').onclick=")
 h=h.replace('ARX-6-P5-1080p.mp4','ARX-6-P5-Inspection-1080p.mp4')
 h=replace(h,"$('detail').hidden=true;","$('detail').hidden=true;$('inspection').hidden=true;")
 h=replace(h,"$('detail').hidden=false;","$('detail').hidden=false;$('inspection').hidden=false;")
 h=replace(h,'#define P3_QUALITY 1\\n','#define P3_QUALITY 1\\n#define P5_SHADOW_SAMPLES 1\\n')
 h=replace(h,"'u_camera_detail','u_cutaway','u_explode','u_samples'","'u_camera_detail','u_cutaway','u_explode','u_inspect','u_part','u_mechanism','u_camera_override','u_camera_origin','u_camera_target','u_camera_focal','u_aperture','u_samples'")
 h=replace(h,"gl.uniform1f(U.u_camera_detail,0);gl.uniform1f(U.u_cutaway,0);gl.uniform1f(U.u_explode,0);",'''gl.uniform1f(U.u_camera_detail,0);gl.uniform1f(U.u_cutaway,$('cut').checked?1:0);gl.uniform1f(U.u_explode,Number($('explode').value));
 gl.uniform1i(U.u_inspect,Number($('assembly').value));gl.uniform1i(U.u_part,Number($('part').value));gl.uniform1f(U.u_mechanism,$('mechanism').checked?t*.65:0);gl.uniform1f(U.u_aperture,0);
 const camera=inspectionCamera(frame,Number($('assembly').value),Number($('part').value),Number($('explode').value),w/h);
 gl.uniform1i(U.u_camera_override,camera?1:0);if(camera){gl.uniform3fv(U.u_camera_origin,camera.origin);gl.uniform3fv(U.u_camera_target,camera.target);gl.uniform1f(U.u_camera_focal,camera.focal);}
''')
 camera_js='''
function inspectionCamera(s,group,part,explode,aspect){
 if(!group&&!part&&explode<.001)return null;
 const add=(a,b)=>a.map((v,i)=>v+b[i]),scale=(a,k)=>a.map(v=>v*k),dot=(a,b)=>a.reduce((v,x,i)=>v+x*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],unit=a=>scale(a,1/Math.hypot(...a));
 const mv=(m,v)=>[dot(m.slice(0,3),v),dot(m.slice(3,6),v),dot(m.slice(6,9),v)];
 const mm=(a,b)=>Array.from({length:9},(_,i)=>{const r=Math.floor(i/3),c=i%3;return a[3*r]*b[c]+a[3*r+1]*b[c+3]+a[3*r+2]*b[c+6];});
 const ry=a=>{const c=Math.cos(a),s=Math.sin(a);return[c,0,s,0,1,0,-s,0,c]},rz=a=>{const c=Math.cos(a),s=Math.sin(a);return[c,-s,0,s,c,0,0,0,1]};
 const eye=[1,0,0,0,1,0,0,0,1],zero=[0,0,0],base=ry(-s[1]),sh=[0,144,0],upper=mm(base,rz(-s[2])),el=add(sh,mv(upper,[0,280,0])),fore=mm(upper,rz(-s[3])),wr=add(el,mv(fore,[0,260,0])),roll=mm(fore,ry(s[4])),bend=mm(roll,rz(-s[5])),tool=mm(bend,ry(s[6]));
 const [qw,qx,qy,qz]=s.slice(18,22),puckR=[1-2*(qy*qy+qz*qz),2*(qx*qy-qz*qw),2*(qx*qz+qy*qw),2*(qx*qy+qz*qw),1-2*(qx*qx+qz*qz),2*(qy*qz-qx*qw),2*(qx*qz-qy*qw),2*(qy*qz+qx*qw),1-2*(qx*qx+qy*qy)];
 const tr={fixed:[eye,zero],turret:[base,zero],upper:[upper,sh],fore:[fore,el],roll:[roll,wr],bend:[bend,wr],tool:[tool,wr],jaw_left:[tool,add(wr,mv(tool,[s[13]*1000,219.2,0]))],jaw_right:[tool,add(wr,mv(tool,[-s[14]*1000,219.2,0]))],puck:[puckR,scale(s.slice(15,18),1000)]};
 const pts=[];for(const p of A.inspection.parts){if(group&&p.group!==group||part&&p.id+1!==part)continue;const [R,o]=tr[p.body],b=p.bounds_mm,off=scale(p.explode_offset_mm,explode);for(let i=0;i<8;i++){const v=[b[i&1?1:0][0],b[i&2?1:0][1],b[i&4?1:0][2]];pts.push(scale(add(mv(R,add(v,off)),o),1/200));}}
 if(!pts.length)return null;const lo=[0,1,2].map(i=>Math.min(...pts.map(p=>p[i]))),hi=[0,1,2].map(i=>Math.max(...pts.map(p=>p[i]))),target=scale(add(lo,hi),.5);
 const az=.70+drag[0]*3,elv=Math.max(-.6,Math.min(1.3,.25+drag[1]*1.6)),dir=[Math.sin(az)*Math.cos(elv),Math.sin(elv),Math.cos(az)*Math.cos(elv)],right=unit(cross(scale(dir,-1),[0,1,0])),up=cross(right,scale(dir,-1));
 let hx=0,hy=0,depth=0;for(const p of pts){const d=add(p,scale(target,-1));hx=Math.max(hx,Math.abs(dot(d,right)));hy=Math.max(hy,Math.abs(dot(d,up)));depth=Math.max(depth,dot(d,dir));}
 const focal=3.3,dist=Math.max(.35,Math.max(hy*focal/.72,hx*focal/(aspect*.78))+depth+.1)*Math.exp(-zoom*.11);return{origin:add(target,scale(dir,dist)),target,focal};
}
'''
 h=replace(h,'function pixelSize(){',camera_js+'\nfunction pixelSize(){')
 numeric_js='''
let selectedNumericTables=null,numericTableBuffers=[],numericTableReadbackVerified=false;
function selectNumericShader(){
 const blockSize=gl.getParameter(gl.MAX_UNIFORM_BLOCK_SIZE),blockCount=gl.getParameter(gl.MAX_FRAGMENT_UNIFORM_BLOCKS);
 selectedNumericTables=A.webglNumeric.variants.find(v=>v.maximum_block_bytes<=blockSize&&v.block_count<=blockCount)||null;
 return selectedNumericTables?selectedNumericTables.source:A.shader;
}
function uploadNumericTables(){
 numericTableBuffers=[];numericTableReadbackVerified=false;
 if(!selectedNumericTables)return;
 for(const block of selectedNumericTables.blocks){
  const index=gl.getUniformBlockIndex(program,block.name);if(index===gl.INVALID_INDEX)continue;
  const bytes=bytes64(block.base64),required=gl.getActiveUniformBlockParameter(program,index,gl.UNIFORM_BLOCK_DATA_SIZE);
  if(required!==bytes.byteLength)throw Error('Numeric table layout differs: '+block.name+' '+required+' / '+bytes.byteLength);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.UNIFORM_BUFFER,buffer);gl.bufferData(gl.UNIFORM_BUFFER,bytes,gl.STATIC_DRAW);gl.uniformBlockBinding(program,index,block.binding);gl.bindBufferBase(gl.UNIFORM_BUFFER,block.binding,buffer);
  const copy=new Uint8Array(bytes.length);gl.getBufferSubData(gl.UNIFORM_BUFFER,0,copy);for(let i=0;i<bytes.length;i++)if(copy[i]!==bytes[i])throw Error('Numeric table upload differs: '+block.name);
  numericTableBuffers.push(buffer);
 }
 numericTableReadbackVerified=true;
}
'''
 h=replace(h,'async function compile(){',numeric_js+'\nasync function compile(){')
 h=replace(h,"'+A.shader;","'+selectNumericShader();")
 h=replace(h,'program=p;gl.useProgram(program);buildCount++;','program=p;gl.useProgram(program);uploadNumericTables();buildCount++;')
 h=replace(h,'sceneTriangles:0,sceneTextures:0,','sceneTriangles:0,sceneTextures:0,numericTables:selectedNumericTables?{blocks:numericTableBuffers.length,bytes:selectedNumericTables.table_bytes,literalTablesRemaining:selectedNumericTables.literal_tables_remaining,shaderSHA:selectedNumericTables.shader_sha256,dataSHA:selectedNumericTables.data_sha256,readbackVerified:numericTableReadbackVerified}:null,')
 h=h.replace('The unchanged P2 MuJoCo model and controller','The P5 model with rebuilt CAD mass properties and folded-drive parameters')
 h=h.replace('MuJoCo integrates the original P2 mechanics.','MuJoCo integrates the revised P5 mechanics.')
 h=h.replace('260 placed rigid-part records and four springs.',str(len(A['inspection']['parts']))+' placed rigid-part records and four springs.')
 h=h.replace('Rigid-part records: 260','Rigid-part records: '+str(len(A['inspection']['parts'])))
 h=h.replace('FILM · Recorded nominal physics · No WebGL rendering','FILM · Physical cycle + mechanism inspection · No WebGL rendering')
 h=h.replace('The static render is available.','The recorded film is available.')
 h=h.replace('performance.now()-start>60000','performance.now()-start>300000')
 # Software drivers can defer native compilation until the tiny probe draw.
 # Ordinary tile submissions retain their shorter deadline and loss handling.
 h=replace(h,'async function gpuWait(serial){','async function gpuWait(serial,timeoutMs=15000){')
 h=replace(h,'performance.now()-started>15000','performance.now()-started>timeoutMs')
 h=replace(h,'await gpuWait(serial);abortIfChanged(serial);renderReady=true;','await gpuWait(serial,300000);abortIfChanged(serial);renderReady=true;')
 h=h.replace('<p><label><input id="reflections" type="checkbox"> Secondary reflections (experimental)</label></p>','<input id="reflections" type="checkbox" hidden>')
 h=replace(h,'window.ARX={ready:true,','''window.ARX={ready:true,
 readPixels:()=>{if(!gl||!fbo)throw Error('No completed shader frame');gl.bindFramebuffer(gl.FRAMEBUFFER,fbo);const p=new Uint8Array(width*height*4);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,p);let text='';for(const v of p)text+=String.fromCharCode(v);return{width,height,rgbaBottomUp:btoa(text)};},
 inspect:async(group=0,part=0,explode=0,cut=false)=>{$('assembly').value=String(group);populateParts();$('part').value=String(part);$('explode').value=String(explode);$('cut').checked=cut;drag=[0,0];zoom=0;dirty=true;await draw();},''')
 (ROOT/'source/player-p5.html').write_text(h)
 h=h.replace('__POSTER__',poster64).replace('__ASSETS__',json.dumps(A,separators=(',',':')).replace('</','<\\/'))
 (ROOT/'ARX-6-P5.html').write_text(h)
 report={'revision':'P5','shader_sha256':A['shaderSHA'],'physics_sha256':A['physicsSHA'],'film_embedded':bool(A['film']),'poster_sha256':sha(poster),'html_bytes':len(h.encode()),'trajectory_sha256':sha(ENG/'integration/results/nominal.json'),'recorded_states':len(A['frames']),'rigid_records':len(A['inspection']['parts']),'inspection_groups':len(A['inspection']['groups']),'offline':True,'numeric_table_transport':{'method':A['webglNumeric']['method'],'variants':[{k:v for k,v in item.items() if k not in ('source','blocks','tables')} for item in A['webglNumeric']['variants']]}}
 (ROOT/'reports/viewer-build.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':build()
