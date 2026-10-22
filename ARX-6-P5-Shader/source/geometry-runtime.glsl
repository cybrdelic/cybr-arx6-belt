// P3 procedural engineering renderer. All distances in millimetres inside
// the constructive-solid evaluator. World/render units are 200 mm.
#ifndef P3_QUALITY
#define P3_QUALITY 1
#endif
uniform int u_inspect;
uniform int u_part;
uniform float u_mechanism;
struct Hit {float t;float id;vec3 n;vec3 local;vec3 tangent;float part;};
mat3 bodyFrame[10]; vec3 bodyOrigin[10];
mat3 springFrame[4]; vec3 springOrigin[4]; vec4 springSpec[4];

float sdBox(vec3 p,vec3 b){vec3 q=abs(p)-b;return length(max(q,0.))+min(max(q.x,max(q.y,q.z)),0.);}
float sdCylinder(vec3 p,float r,float h){vec2 q=vec2(length(p.xy)-r,abs(p.z)-h);return length(max(q,0.))+min(max(q.x,q.y),0.);}
float sdCapsule(vec3 p,vec3 a,vec3 b,float r){vec3 ab=b-a;return length(p-a-ab*clamp(dot(p-a,ab)/dot(ab,ab),0.,1.))-r;}
float sdCone(vec3 p,float r0,float r1,float h){
 vec2 q=vec2(length(p.xy),p.z),k1=vec2(r1,h),k2=vec2(r1-r0,2.*h);
 vec2 ca=vec2(q.x-min(q.x,q.y<0.?r0:r1),abs(q.y)-h);
 vec2 cb=q-k1+k2*clamp(dot(k1-q,k2)/dot(k2,k2),0.,1.);
 float s=cb.x<0.&&ca.y<0.?-1.:1.;return s*sqrt(min(dot(ca,ca),dot(cb,cb)));
}
float sdPolygon(vec2 p,int start,int count){
 vec2 a=CSG_POLY[start+count-1];float d=1e20;bool inside=false;
 for(int j=0;j<count;j++){
  vec2 b=CSG_POLY[start+j],e=b-a,w=p-a;
  float l=max(dot(e,e),1e-20);vec2 q=w-e*clamp(dot(w,e)/l,0.,1.);d=min(d,dot(q,q));
  if((a.y>p.y)!=(b.y>p.y)){
   float x=a.x+(p.y-a.y)*(b.x-a.x)/(b.y-a.y);if(p.x<x)inside=!inside;
  }
  a=b;
 }
 return sqrt(d)*(inside?-1.:1.);
}
float sdPolygonBVH(vec2 p,int first,int end){
 float distanceSquared=1e20;bool inside=false;int node=first;
 while(node<end){
  vec2 lo=POLY_BVH_LO[node],hi=POLY_BVH_HI[node];ivec3 meta=POLY_BVH_META[node];
  vec2 outside=max(max(lo-p,p-hi),vec2(0));float bound=dot(outside,outside);
  bool canCross=p.y>=lo.y&&p.y<=hi.y&&hi.x>p.x;
  if(bound>=distanceSquared&&!canCross){node=meta.z;continue;}
  if(meta.x>=0){
   vec2 a=CSG_POLY[meta.y],b=CSG_POLY[meta.x],e=b-a,w=p-a;
   vec2 q=w-e*clamp(dot(w,e)/max(dot(e,e),1e-20),0.,1.);distanceSquared=min(distanceSquared,dot(q,q));
   if((a.y>p.y)!=(b.y>p.y)){float x=a.x+(p.y-a.y)*(b.x-a.x)/(b.y-a.y);if(p.x<x)inside=!inside;}
  }
  node++;
 }
 return sqrt(distanceSquared)*(inside?-1.:1.);
}
vec2 beltToothCenter(float s,float radius,float centers,float inward){
 float h=PI*radius,r=radius-inward;
 if(s<h){float a=PI+s/radius;return r*vec2(cos(a),sin(a));}
 s-=h;if(s<centers)return vec2(r,s);
 s-=centers;if(s<h){float a=s/radius;return vec2(r*cos(a),centers+r*sin(a));}
 s-=h;return vec2(-r,centers-s);
}
float beltTeethDistance(int index,vec3 p,float beltPhase){
 vec4 a=CSG_P[index];vec2 extra=CSG_EXTRA[index];vec4 detail=CSG_DETAIL[index];
 float pr=a.w,c=extra.x,pitch=extra.y,off=detail.x,h=PI*pr;
 float shift=beltPhase*pr;float phase=mod(shift,pitch);
 float lowAngle=dot(p.xy,p.xy)<1e-20?PI:(p.y<=0.?TAU-atan(-p.y,p.x):(p.x<0.?PI:TAU));
 float topAngle=dot(p.xy-vec2(0,c),p.xy-vec2(0,c))<1e-20?0.:(p.y>=c?atan(p.y-c,p.x):(p.x<0.?PI:0.));
 float projection[4]=float[4](pr*(lowAngle-PI),h+clamp(p.y,0.,c),h+c+pr*topAngle,2.*h+2.*c-clamp(p.y,0.,c));
 float starts[4]=float[4](0.,h,h+c,2.*h+c),ends[4]=float[4](h,h+c,2.*h+c,2.*h+2.*c);
 float nearest=1e20;
 for(int j=0;j<4;j++){
  float first=ceil((starts[j]-phase)/pitch-1e-6),last=floor((ends[j]-phase)/pitch+1e-6);
  float k=clamp(floor((projection[j]-phase)/pitch+.5),first,last);
  vec2 q=p.xy-beltToothCenter(phase+k*pitch,pr,c,off);nearest=min(nearest,dot(q,q));
 }
 vec2 d=vec2(sqrt(nearest)-a.y,abs(p.z)-a.z);return length(max(d,0.))+min(max(d.x,d.y),0.);
}
float primitiveDistance(int index,vec3 p,float beltPhase){
 vec4 v=vec4(p,1.);p=vec3(dot(CSG_R0[index],v),dot(CSG_R1[index],v),dot(CSG_R2[index],v));
 vec4 a=CSG_P[index];int type=int(a.x+.5);
 if(type==0)return sdBox(p,a.yzw);
 if(type==1)return sdCylinder(p,a.y,a.z);
 if(type==2)return length(p)-a.y;
 if(type==3)return sdCone(p,a.y,a.z,a.w);
 if(type==6)return beltTeethDistance(index,p,beltPhase);
 if(type==5){
  if(dot(p.xy,p.xy)<1e-20)return sdCylinder(vec3(-a.w,0.,p.z),a.y,a.z);
  vec2 extra=CSG_EXTRA[index];float angle=atan(p.y,p.x)-extra.x;
  float closest=extra.x+TAU*floor(angle*extra.y/TAU+.5)/extra.y;
  return sdCylinder(p-vec3(a.w*cos(closest),a.w*sin(closest),0.),a.y,a.z);
 }
 if(type==7){vec4 repeat=CSG_DETAIL[index];float k=clamp(floor((p.x-repeat.x)/repeat.y+.5),0.,repeat.z-1.);p.x-=repeat.x+k*repeat.y;}
 vec2 span=CSG_EXTRA[index];vec2 d=vec2(sdPolygonBVH(p.xy,int(span.x+.5),int(span.y+.5)),abs(p.z)-a.w);
 return length(max(d,0.))+min(max(d.x,d.y),0.);
}
float shapeDistance(int shape,vec3 p,float beltPhase){
 ivec2 span=CSG_SHAPE[shape];float stack[CSG_STACK];int top=0;
 // Data-dependent tape bounds deliberately prevent compile-time expansion of
 // hundreds of separate CAD expressions into every shadow/normal invocation.
 for(int i=span.x;i<span.x+span.y;i++){
  int op=CSG_CODE[i];
  if(op>0){stack[top]=primitiveDistance(op-1,p,beltPhase);top++;}
  else{float b=stack[top-1],a=stack[top-2];top--;stack[top-1]=op==-1?min(a,b):op==-2?max(a,-b):max(a,b);}
 }
 return stack[0];
}
bool inspectNode(int node){return u_inspect==0||(BVH_GROUP_MASK[node]&(1<<u_inspect))!=0;}
bool inspectSpring(int id){return u_part==0&&(u_inspect==0||u_inspect==(id<2?8:9));}
vec3 nodeLow(int node){return u_explode<=0.?BVH_LO[node]:BVH_LO[node]+BVH_ELO[node]*clamp(u_explode,0.,1.);}
vec3 nodeHigh(int node){return u_explode<=0.?BVH_HI[node]:BVH_HI[node]+BVH_EHI[node]*clamp(u_explode,0.,1.);}
vec3 inspectionRotate(vec3 v,vec3 axis,float angle){float c=cos(angle),s=sin(angle);return v*c+cross(axis,v)*s+axis*dot(axis,v)*(1.-c);}
float jointPhysicalPhase(int group){
 if(group==1)return -u_joint012.x;if(group==2)return -u_joint012.y;if(group==3)return u_joint012.z;
 if(group==4)return u_joint345.x;if(group==5)return -u_joint345.y;if(group==6)return u_joint345.z;return 0.;
}
float inspectionAngle(int id){
 float physical=CSG_INPUT_PHASE[id]!=0?jointPhysicalPhase(CSG_INSPECT[id].x):0.;
 return physical+(u_inspect>0?u_mechanism*CSG_DEMO_AXIS[id].w:0.);
}
mat3 objectInverse(int id){return transpose(mat3(CSG_O0[id].xyz,CSG_O1[id].xyz,CSG_O2[id].xyz));}
vec3 objectPoint(int id,vec3 p){
 if(u_explode>0.)p-=CSG_EXPLODE[id]*clamp(u_explode,0.,1.);
 float inspectAngle=inspectionAngle(id);
 if(abs(inspectAngle)>.000001)p=CSG_DEMO_CENTER[id]+inspectionRotate(p-CSG_DEMO_CENTER[id],CSG_DEMO_AXIS[id].xyz,-inspectAngle);
 vec4 q=vec4(p,1.);vec3 v=vec3(dot(CSG_O0[id],q),dot(CSG_O1[id],q),dot(CSG_O2[id],q));
 if(CSG_OBJECT[id].w!=0){float a=(.5*(u_jawsSI.x+u_jawsSI.y)*1000.+2.)/3.;v=kRotZ(a)*v;}
 return v;
}
float objectDistance(int id,vec3 p){
 vec3 q=objectPoint(id,p);float phase=jointPhysicalPhase(CSG_INSPECT[id].x)+(u_inspect>0&&u_inspect<=6?u_mechanism:0.);float d=shapeDistance(CSG_OBJECT[id].x,q,phase);
 if(u_inspect>0&&u_cutaway>0.&&CSG_INSPECT[id].y!=0){vec4 planes=CSG_CUT_PLANE[CSG_OBJECT[id].x];bool cutZ=CSG_INSPECT[id].y==2;vec2 cut=cutZ?planes.zw:planes.xy;float coord=cutZ?q.z:q.x;d=max(d,coord-mix(cut.x+.01,cut.y,clamp(u_cutaway,0.,1.)));}
 return d;
}
vec2 boxInterval(vec3 ro,vec3 rd,vec3 lo,vec3 hi){
 vec3 inv=(2.*step(vec3(0),rd)-1.)/max(abs(rd),vec3(1e-10));
 vec3 a=(lo-ro)*inv,b=(hi-ro)*inv,mn=min(a,b),mx=max(a,b);
 return vec2(max(mn.x,max(mn.y,mn.z)),min(mx.x,min(mx.y,mx.z)));
}
float boxDistance(vec3 p,vec3 lo,vec3 hi){return sdBox(p-(lo+hi)*.5,(hi-lo)*.5);}
vec3 objectDirection(int id,vec3 direction){
 float a=inspectionAngle(id);
 if(abs(a)>.000001)direction=inspectionRotate(direction,CSG_DEMO_AXIS[id].xyz,-a);
 vec3 d=objectInverse(id)*direction;
 if(CSG_OBJECT[id].w!=0){float angle=(.5*(u_jawsSI.x+u_jawsSI.y)*1000.+2.)/3.;d=kRotZ(angle)*d;}
 return d;
}
int analyticObjectHit(int id,vec3 origin,vec3 direction,float limit,out float result){
 ivec2 span=CSG_SHAPE[CSG_OBJECT[id].x];
 if(span.y!=1||(u_inspect>0&&u_cutaway>0.&&CSG_INSPECT[id].y!=0))return 0;
 int primitive=CSG_CODE[span.x]-1;vec4 param=CSG_P[primitive];int type=int(param.x+.5);
 if(type>2)return 0;
 vec4 local=vec4(objectPoint(id,origin),1.);vec3 ld=objectDirection(id,direction);
 vec3 ro=vec3(dot(CSG_R0[primitive],local),dot(CSG_R1[primitive],local),dot(CSG_R2[primitive],local));
 vec3 rd=vec3(dot(CSG_R0[primitive].xyz,ld),dot(CSG_R1[primitive].xyz,ld),dot(CSG_R2[primitive].xyz,ld));
 vec2 interval=vec2(-1e20,1e20);
 if(type==0)interval=boxInterval(ro,rd,-param.yzw,param.yzw);
 else if(type==1){
  float A=dot(rd.xy,rd.xy),B=dot(ro.xy,rd.xy),C=dot(ro.xy,ro.xy)-param.y*param.y;
  if(A<1e-14){if(C>0.)return -1;}
  else{float disc=B*B-A*C;if(disc<0.)return -1;float root=sqrt(disc);interval=vec2(-B-root,-B+root)/A;}
  if(abs(rd.z)<1e-12){if(abs(ro.z)>param.z)return -1;}
  else{vec2 ends=(vec2(-param.z,param.z)-ro.z)/rd.z;interval=vec2(max(interval.x,min(ends.x,ends.y)),min(interval.y,max(ends.x,ends.y)));}
 }else{
  float A=dot(rd,rd),B=dot(ro,rd),C=dot(ro,ro)-param.y*param.y,disc=B*B-A*C;
  if(disc<0.)return -1;float root=sqrt(disc);interval=vec2(-B-root,-B+root)/A;
 }
 if(interval.x>interval.y||interval.y<.01||interval.x>limit)return -1;
 result=max(interval.x,.01);return result<=limit?1:-1;
}

void setupSpring(int i,vec3 a,vec3 b,vec3 up,float radius,float wire,float turns,float lead){
 vec3 z=normalize(b-a),x=normalize(cross(up,z)),y=cross(z,x);
 springFrame[i]=mat3(x,y,z);springOrigin[i]=a;springSpec[i]=vec4(radius,wire,length(b-a),lead);
}
void initScene(){
 bodyFrame[0]=mat3(1);bodyOrigin[0]=vec3(0);
 bodyFrame[1]=kBaseFrame;bodyOrigin[1]=vec3(0);
 bodyFrame[2]=kUpperFrame;bodyOrigin[2]=kShoulder*200.;
 bodyFrame[3]=kForeFrame;bodyOrigin[3]=kElbow*200.;
 bodyFrame[4]=kRollFrame;bodyOrigin[4]=kWrist*200.;
 bodyFrame[5]=kBendFrame;bodyOrigin[5]=kWrist*200.;
 bodyFrame[6]=kToolFrame;bodyOrigin[6]=kWrist*200.;
 bodyFrame[7]=kToolFrame;bodyOrigin[7]=kWrist*200.+kToolFrame*vec3(u_jawsSI.x*1000.,219.2,0);
 bodyFrame[8]=kToolFrame;bodyOrigin[8]=kWrist*200.+kToolFrame*vec3(-u_jawsSI.y*1000.,219.2,0);
 bodyFrame[9]=kPuckFrame;bodyOrigin[9]=kPuck*200.;
 for(int j=0;j<4;j++){
  if(!inspectSpring(j))continue;
  ivec2 ids=SPRING_BODY[j];vec4 detail=SPRING_DETAIL[j];
  vec3 a=bodyOrigin[ids.x]+bodyFrame[ids.x]*SPRING_ANCHOR_A[j];
  vec3 b=bodyOrigin[ids.y]+bodyFrame[ids.y]*SPRING_ANCHOR_B[j];
  setupSpring(j,a,b,-bodyFrame[ids.x][2],detail.x,detail.y,detail.z,detail.w);
  springOrigin[j]+=bodyFrame[ids.x]*vec3((j%2==0?-36.:36.),0.,j<2?36.:-36.)*clamp(u_explode,0.,1.);
 }

}
float springDistance(int id,vec3 p){
 vec4 s=springSpec[id];float radius=s.x,wire=s.y,L=s.z,lead=s.w,turns=SPRING_DETAIL[id].z;
 float rise=(L-2.*lead)/(TAU*turns);
 float theta=atan(p.y,p.x);theta+=TAU*round(((p.z-lead)/rise-theta)/TAU);
 theta=clamp(theta,0.,TAU*turns);
 for(int i=0;i<3;i++){
  float c=cos(theta),sn=sin(theta);
  float g=radius*(p.x*sn-p.y*c)+rise*(lead+rise*theta-p.z);
  float H=radius*(p.x*c+p.y*sn)+rise*rise;
  theta=clamp(theta-clamp(g/max(H,.001),-.8,.8),0.,TAU*turns);
 }
 vec3 c=vec3(radius*cos(theta),radius*sin(theta),lead+rise*theta);
 float d=length(p-c)-wire;vec2 hook=SPRING_HOOK[id];
 for(int j=0;j<2;j++){
  float z=j==0?0.:L;
  vec3 q=p-vec3(0,0,z);
  d=min(d,length(vec2(length(q.xz)-hook.x,q.y))-hook.y);
  d=min(d,sdCapsule(p,vec3(hook.x,0,z),vec3(radius,0,j==0?lead:L-lead),hook.y));
 }
 return d;
}
void traceObject(int id,int body,vec3 ro,vec3 rd,vec2 range,inout Hit hit){
 float t=max(range.x,0.01),end=min(range.y,hit.t*200.);if(t>end)return;
 bool found=false;float epsilon=.012;
 float analyticT;int analytic=analyticObjectHit(id,ro,rd,end,analyticT);
 if(analytic<0)return;
 found=analytic>0;if(found)t=analyticT;
 for(int k=0;k<96;k++){
  if(found)break;
  if(t>end)break;float d=objectDistance(id,ro+rd*t);epsilon=max(.008,pixelFootprint*t*.022);
  if(d<epsilon){found=true;break;}t+=max(d*.86,.005);
 }
 if(!found||t>=hit.t*200.)return;
 vec3 p=ro+rd*t;float e=max(.012,epsilon*.7);vec2 k=vec2(1,-1);
 vec3 n=normalize(k.xyy*objectDistance(id,p+k.xyy*e)+k.yyx*objectDistance(id,p+k.yyx*e)+k.yxy*objectDistance(id,p+k.yxy*e)+k.xxx*objectDistance(id,p+k.xxx*e));
 vec3 q=objectPoint(id,p);vec3 animatedN=inspectionRotate(n,CSG_DEMO_AXIS[id].xyz,-inspectionAngle(id));vec3 localN=objectInverse(id)*animatedN;
 vec3 tangent=abs(localN.z)>.60?normalize(vec3(-q.y,q.x,.0001)):vec3(0,0,1);
 mat3 world=bodyFrame[body]*transpose(objectInverse(id));
 if(CSG_OBJECT[id].w!=0){float a=-(.5*(u_jawsSI.x+u_jawsSI.y)*1000.+2.)/3.;world=world*kRotZ(a);}
 hit.t=t/200.;hit.id=float(CSG_OBJECT[id].y);hit.part=1000.+float(id);hit.n=bodyFrame[body]*n;hit.local=q/200.;hit.tangent=normalize(bodyFrame[body]*inspectionRotate(transpose(bodyFrame[body])*(world*tangent),CSG_DEMO_AXIS[id].xyz,inspectionAngle(id)));
}
void traceBody(int b,vec3 ro,vec3 rd,inout Hit hit){
 if(BVH_BODY[b].x==BVH_BODY[b].y||!inspectNode(BVH_BODY[b].x))return;
 if(u_part>0&&CSG_OBJECT[u_part-1].z!=b)return;
 mat3 inv=transpose(bodyFrame[b]);vec3 lr=inv*(ro*200.-bodyOrigin[b]),ld=inv*rd;
 if(u_part>0){int id=u_part-1,node=CSG_LEAF[id];if(!inspectNode(node))return;vec2 rr=boxInterval(lr,ld,nodeLow(node),nodeHigh(node));if(rr.x<=rr.y&&rr.y>0.)traceObject(id,b,lr,ld,rr,hit);return;}
 ivec2 range=BVH_BODY[b];int ni=range.x;
 while(ni<range.y){
  ivec2 node=BVH_META[ni];if(!inspectNode(ni)){ni=node.y;continue;}vec2 rr=boxInterval(lr,ld,nodeLow(ni),nodeHigh(ni));
  if(rr.x>rr.y||rr.y<0.||rr.x>hit.t*200.){ni=node.y;continue;}
  if(node.x>=0)traceObject(node.x,b,lr,ld,rr,hit);
  ni++;
 }
}
void traceSpring(int id,vec3 ro,vec3 rd,inout Hit hit){
 mat3 inv=transpose(springFrame[id]);vec3 r=inv*(ro*200.-springOrigin[id]),d=inv*rd;vec4 s=springSpec[id];
 vec2 box=boxInterval(r,d,vec3(-s.x-s.y,-s.x-s.y,-5.),vec3(s.x+s.y,s.x+s.y,s.z+5.));
 float t=max(box.x,.01),end=min(box.y,hit.t*200.);bool found=false;
 for(int i=0;i<128;i++){
  if(t>end)break;float x=springDistance(id,r+d*t);if(x<max(.008,pixelFootprint*t*.022)){found=true;break;}t+=max(.004,x*.65);
 }
 if(!found||t>=hit.t*200.)return;
 vec3 p=r+d*t;vec2 k=vec2(1,-1);float e=.015;
 vec3 n=normalize(k.xyy*springDistance(id,p+k.xyy*e)+k.yyx*springDistance(id,p+k.yyx*e)+k.yxy*springDistance(id,p+k.yxy*e)+k.xxx*springDistance(id,p+k.xxx*e));
 hit.t=t/200.;hit.id=4.;hit.part=2000.+float(id);hit.n=springFrame[id]*n;hit.local=p/200.;hit.tangent=springFrame[id]*vec3(0,0,1);
}
float benchDistance(vec3 p){
 // Real P5 mount interface: 950 x 700 x 40 mm table with separate
 // circular service bores: diameter110 atX0 and diameter46 atX110mm.
 float slab=sdBox(p-vec3(.625,-.1025,0),vec3(2.375,.1,1.75));
 slab=max(slab,-sdCylinder(p.xzy,.275,2.));
 slab=max(slab,-sdCylinder((p-vec3(.55,0,0)).xzy,.115,2.));
 // The support legs and dark lower studio floor are presentation fixtures.
 vec3 q=p-vec3(.625,-1.15,0);q.x=abs(q.x)-2.15;q.z=abs(q.z)-1.52;
 return min(slab,sdBox(q,vec3(.075,1.0475,.075)));
}
void traceBench(vec3 ro,vec3 rd,inout Hit hit){
 if(rd.y<-.00001){float t=(-2.3-ro.y)/rd.y;if(t>0.&&t<hit.t){hit.t=t;hit.id=7.;hit.n=vec3(0,1,0);hit.local=ro+rd*t;hit.tangent=vec3(1,0,0);hit.part=100.;}}
 vec2 box=boxInterval(ro,rd,vec3(-1.75,-2.3,-1.75),vec3(3.,0.,1.75));float t=max(box.x,.001),end=min(box.y,hit.t);bool found=false;
 for(int i=0;i<80;i++){if(t>end)break;float d=benchDistance(ro+rd*t);if(d<.0001){found=true;break;}t+=max(.00005,.9*d);}
 if(found&&t<hit.t){vec3 p=ro+rd*t;vec2 k=vec2(1,-1);float e=.0001;hit.n=normalize(k.xyy*benchDistance(p+k.xyy*e)+k.yyx*benchDistance(p+k.yyx*e)+k.yxy*benchDistance(p+k.yxy*e)+k.xxx*benchDistance(p+k.xxx*e));hit.t=t;hit.id=7.;hit.local=p;hit.tangent=vec3(1,0,0);hit.part=100.;}
}
Hit traceScene(vec3 ro,vec3 rd){
 Hit hit;hit.t=100.;hit.id=0.;hit.n=vec3(0,1,0);hit.local=vec3(0);hit.tangent=vec3(1,0,0);hit.part=0.;
 if(u_inspect==0&&u_part==0)traceBench(ro,rd,hit);
 for(int b=0;b<10;b++)traceBody(b,ro,rd,hit);
 for(int j=0;j<4;j++)if(inspectSpring(j))traceSpring(j,ro,rd,hit);
 return hit;
}
float visibilityMapClamped(vec3 point,float maximum){
 float result=u_inspect==0&&u_part==0?min(benchDistance(point)*200.,maximum*200.):maximum*200.;
 for(int b=0;b<10;b++){
  if(BVH_BODY[b].x==BVH_BODY[b].y||!inspectNode(BVH_BODY[b].x))continue;
  if(u_part>0&&CSG_OBJECT[u_part-1].z!=b)continue;
  vec3 p=transpose(bodyFrame[b])*(point*200.-bodyOrigin[b]);ivec2 rr=BVH_BODY[b];int ni=rr.x;
  if(u_part>0){int id=u_part-1;result=min(result,objectDistance(id,p));continue;}
  while(ni<rr.y){
   ivec2 n=BVH_META[ni];if(!inspectNode(ni)){ni=n.y;continue;}float box=boxDistance(p,nodeLow(ni),nodeHigh(ni));
   if(box>=result){ni=n.y;continue;}
   if(n.x>=0){
    // Bounds prune traversal only. Visibility/occlusion must use the solid,
    // not the box: a conservative stepping bound is not a shadow distance.
    float d=objectDistance(n.x,p);result=min(result,d);
   }
   ni++;
  }
 }
 for(int j=0;j<4;j++){
  if(!inspectSpring(j))continue;
  vec3 p=transpose(springFrame[j])*(point*200.-springOrigin[j]);vec4 s=springSpec[j];
  float bound=sdCylinder(p-vec3(0,0,s.z*.5),s.x+s.y,s.z*.5+4.);
  if(bound<result)result=min(result,springDistance(j,p));
 }
 return result/200.;
}
float visibilityMap(vec3 point){return visibilityMapClamped(point,100.);}
bool occludeObject(int id,vec3 ro,vec3 rd,vec2 range,float maximum){
 float t=max(range.x,.02),end=min(range.y,maximum);if(t>end)return false;
 float analyticT;int analytic=analyticObjectHit(id,ro,rd,end,analyticT);if(analytic!=0)return analytic>0;
 for(int i=0;i<96;i++){
  if(t>end)return false;float d=objectDistance(id,ro+rd*t);
  if(d<.012)return true;t+=max(d*.88,.006);
 }
 return false;
}
bool occludeBody(int b,vec3 ro,vec3 rd,float maximum){
 if(BVH_BODY[b].x==BVH_BODY[b].y||!inspectNode(BVH_BODY[b].x))return false;
 if(u_part>0&&CSG_OBJECT[u_part-1].z!=b)return false;
 mat3 inv=transpose(bodyFrame[b]);vec3 lr=inv*(ro*200.-bodyOrigin[b]),ld=inv*rd;
 if(u_part>0){int id=u_part-1,node=CSG_LEAF[id];if(!inspectNode(node))return false;vec2 rr=boxInterval(lr,ld,nodeLow(node),nodeHigh(node));return rr.x<=rr.y&&rr.y>0.&&occludeObject(id,lr,ld,rr,maximum);}
 ivec2 span=BVH_BODY[b];int ni=span.x;
 while(ni<span.y){
  ivec2 node=BVH_META[ni];
  if(!inspectNode(ni)){ni=node.y;continue;}
  vec2 rr=boxInterval(lr,ld,nodeLow(ni),nodeHigh(ni));
  if(rr.x>rr.y||rr.y<.02||rr.x>maximum){ni=node.y;continue;}
  if(node.x>=0&&occludeObject(node.x,lr,ld,rr,maximum))return true;
  ni++;
 }
 return false;
}
bool occludeSpring(int id,vec3 ro,vec3 rd,float maximum){
 mat3 inv=transpose(springFrame[id]);vec3 r=inv*(ro*200.-springOrigin[id]),d=inv*rd;vec4 s=springSpec[id];
 vec2 range=boxInterval(r,d,vec3(-s.x-s.y,-s.x-s.y,-5.),vec3(s.x+s.y,s.x+s.y,s.z+5.));
 float t=max(range.x,.02),end=min(range.y,maximum);
 for(int i=0;i<80;i++){
  if(t>end)return false;float v=springDistance(id,r+d*t);if(v<.012)return true;t+=max(.006,v*.72);
 }
 return false;
}
float softShadow(vec3 p,vec3 light){
#if P3_QUALITY==0
 return 1.;
#else
 vec3 delta=light-p;float lengthToLight=length(delta);vec3 direction=delta/lengthToLight;
 float maximum=(lengthToLight-.001)*200.;
 for(int b=0;b<10;b++)if(occludeBody(b,p,direction,maximum))return .035;
 for(int j=0;j<4;j++)if(inspectSpring(j)&&occludeSpring(j,p,direction,maximum))return .035;
 // The studio bench uses its actual procedural solid when it lies on the ray.
 if(u_inspect==0&&u_part==0){Hit h;h.t=lengthToLight;traceBench(p,direction,h);if(h.t<lengthToLight-.001)return .035;}
 return 1.;
#endif
}
float ambientOcclusion(vec3 p,vec3 n){
#if P3_QUALITY==0
 return 1.;
#else
 float occ=0.,w=1.;
 for(int i=0;i<3;i++){float h=.006+.018*float(i);occ+=max(0.,h-visibilityMapClamped(p+n*h,h))*w;w*=.5;}
 return clamp(1.-12.*occ,.22,1.);
#endif
}
void applyMarkings(inout Hit h){} // CAD solids remain unchanged; no fake labels.
