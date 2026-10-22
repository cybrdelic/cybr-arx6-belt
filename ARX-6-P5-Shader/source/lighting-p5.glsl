// ARX / 6 — procedural manufactured finishes and finite studio emitters.
// Interface: Hit {t,id,n,local,tangent,part}; sceneTime, pixelFootprint;
// noise2/noise3; ambientOcclusion(p,n); softShadow(p,lightPosition).
// CAPTURE samples cycle robotLightPhase = u_frame % 4. A balanced 4, 8, ...
// sample capture covers the full 10 x 10 rectangular quadrature. The single
// camera sample live preview instead uses a complete 5 x 5 quadrature.

int robotLightPhase = 0;
const float RL_PI = 3.14159265358979323846;
const float RL_TAU = 6.28318530717958647692;

float rlSq(float x) { return x*x; }
float rlSat(float x) { return clamp(x,0.0,1.0); }

struct RobotLight {
    vec3 position;
    vec3 u;
    vec3 v;
    vec2 halfSize;
    vec3 radiance;
};

RobotLight robotLight(int index) {
    vec3 p;
    vec2 halfSize;
    vec3 radiance;
    if(index==0) {
        // Large overhead/front-left diffuser: long continuous highlight
        // gradients across the enamel shells and milled joint shoulders.
        p=vec3(-2.7,5.5,4.5);
        halfSize=vec2(2.6,1.65);
        radiance=vec3(5.8,5.6,5.25);
    } else if(index==1) {
        // Broad low front-left diffuser reveals the machined joint faces.
        // Its lower radiance preserves metal colour instead of clipping it.
        p=vec3(4.3,2.6,2.4);
        halfSize=vec2(1.1,2.0);
        radiance=vec3(3.0,3.15,3.4);
    } else {
        // Rear strip separates the narrow cables and wrist from the studio.
        p=vec3(-1.8,4.6,-3.2);
        halfSize=vec2(1.15,2.0);
        radiance=vec3(5.8,6.0,6.3);
    }
    vec3 lightTarget=vec3(.65,1.15,0.);
    if(u_camera_override!=0&&u_inspect>0) {
        vec3 view=normalize(u_camera_origin-u_camera_target);
        vec3 right=normalize(cross(vec3(0,1,0),view));
        vec3 up=cross(view,right);
        float scale=clamp(length(u_camera_origin-u_camera_target)*.60,.7,4.);
        vec3 offset=index==0?vec3(-1.35,1.75,2.30):index==1?vec3(1.8,.45,1.65):vec3(-.75,1.65,-1.6);
        lightTarget=u_camera_target;
        p=lightTarget+scale*(right*offset.x+up*offset.y+view*offset.z);
        halfSize*=scale*.65;
    }
    vec3 normal=normalize(lightTarget-p);
    vec3 u=normalize(cross(vec3(0.0,1.0,0.0),normal));
    vec3 v=cross(normal,u);
    return RobotLight(p,u,v,halfSize,radiance);
}

// The background remains quiet so the material response, rather than a
// painted background gradient, establishes the robot's shape.
vec3 studioBackground(vec3 direction) {
    float upward=smoothstep(-.22,.92,direction.y);
    vec3 c=mix(vec3(.0115,.0130,.0160),
               vec3(.0370,.0420,.0500),upward);
    float blackFlag=pow(max(dot(direction,
        normalize(vec3(-.90,.08,.43))),0.0),7.0);
    return c*(1.0-.76*blackFlag);
}

// Smooth, finite diffusion cloth. Both direct illumination and visible
// reflections use this exact radiance profile.
vec3 robotEmitterRadiance(RobotLight light,vec2 uv) {
    vec2 q=uv/light.halfSize;
    vec2 d=abs(q)-vec2(.90);
    float roundedOutline=length(max(d,0.0))+min(max(d.x,d.y),0.0)-.10;
    float edge=1.0-smoothstep(-.055,0.0,roundedOutline);
    float cloth=.63+.37*exp(-1.45*dot(q,q));
    return light.radiance*(edge*cloth);
}

// Analytic emitter reflections for rays that miss geometry. Opaque surfaces
// use the GGX area integral below, so shadeSurface never adds these sources
// a second time as an environment-specular term.
vec3 studioEnv(vec3 origin,vec3 direction,float roughness) {
    vec3 c=studioBackground(direction);
    for(int i=0;i<3;i++) {
        RobotLight light=robotLight(i);
        vec3 normal=cross(light.u,light.v);
        float denominator=dot(direction,normal);
        if(denominator < -.00001) {
            float distance=dot(light.position-origin,normal)/denominator;
            if(distance>0.0) {
                vec3 point=origin+direction*distance-light.position;
                vec2 uv=vec2(dot(point,light.u),dot(point,light.v));
                float blur=max(.001,distance*roughness*roughness*.80);
                vec2 expanded=light.halfSize+vec2(blur);
                vec2 filteredUV=uv*light.halfSize/expanded;
                float energy=light.halfSize.x*light.halfSize.y/
                             (expanded.x*expanded.y);
                c+=robotEmitterRadiance(light,filteredUV)*energy;
            }
        }
    }
    return c;
}

struct RobotMaterial {
    vec3 base;
    vec3 f0;
    float roughness;
    float metal;
    float anisotropy;
    vec3 normal;
    vec3 tangent;
    vec3 emission;
};

vec3 robotTangent(vec3 n,vec3 authoredTangent) {
    vec3 tangent=authoredTangent-n*dot(n,authoredTangent);
    if(dot(tangent,tangent)<.000001)
        tangent=abs(n.y)<.85?cross(n,vec3(0,1,0)):cross(n,vec3(1,0,0));
    return normalize(tangent);
}

// All fine surface variation is anchored to the hit's moving part frame.
// There are no world-space noise layers that would slide across the links.
const int P5_FINISH[385]=int[385](4,4,4,4,4,4,4,4,4,3,4,4,4,4,2,4,4,4,6,4,4,3,2,2,4,4,4,4,4,4,2,2,3,3,3,3,4,5,6,4,4,6,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,3,4,4,4,4,2,4,4,4,6,4,4,3,2,2,4,4,4,4,4,4,2,2,3,3,3,3,4,5,6,4,4,6,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,3,4,4,4,4,2,4,4,4,6,4,4,3,2,2,4,4,4,4,4,4,2,2,3,3,3,3,4,5,6,4,4,6,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,3,4,4,4,4,2,4,4,4,6,4,4,3,2,2,4,4,4,2,2,3,3,3,3,4,5,6,4,4,6,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,3,4,4,4,4,2,4,4,4,6,4,4,3,2,2,4,4,4,2,2,3,3,3,3,4,5,6,4,4,6,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,3,4,4,4,4,2,4,4,4,6,4,4,3,2,2,4,4,4,2,2,3,3,3,3,4,5,6,4,4,6,4,4,4,4,4,4,4,4,4,4,4,4,3,1,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,1,1,1,4,1,1,4,3,3,4,1,4,4,4,1,4,3,2,4,4,4,4,3,5,5,5,4,2,2,2,5,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,3,5,4,5,5,6,2,4,2,4);
RobotMaterial robotMaterial(Hit hit,vec3 position) {
    float finishID=hit.id;
    if(hit.part>=1000.&&hit.part<float(1000+P5_FINISH.length())) finishID=float(P5_FINISH[int(hit.part)-1000]);

    vec3 n=hit.n;
    vec3 t=robotTangent(n,hit.tangent);
    vec3 b=cross(n,t);
    vec3 q=hit.local;
    float footprint=max(pixelFootprint*hit.t,.0001);
    float fineAttenuation=exp(-2.0*rlSq(footprint*130.0));
    float fine=(noise3(q*130.0)-.5)*fineAttenuation;
    float finish=noise3(q*7.0+vec3(4.2,19.7,6.1))-.5;
    RobotMaterial m=RobotMaterial(vec3(.52,.505,.475),vec3(.043),
        .295,0.0,0.0,n,t,vec3(0));

    if(finishID<1.5) {
        // Warm off-white powder enamel. Very slight orange peel is confined
        // to the sheen; the housing is not covered with arbitrary grime.
        m.base=vec3(.56,.555,.535)*(1.0+.012*finish);
        m.f0=vec3(.044);
        m.roughness=.25+.012*finish+.016*fine;
        float peelA=(noise2(q.xy*180.0+vec2(3.1,8.7))-.5)*fineAttenuation;
        float peelB=(noise2(q.yz*180.0+vec2(7.3,1.9))-.5)*fineAttenuation;
        m.normal=normalize(n+.007*(t*peelA+b*peelB));
    } else if(finishID<2.5) {
        // Satin anodized gearbox covers. The dielectric oxide response
        // keeps this black material readable without making it chrome.
        m.base=vec3(.038,.043,.050)*(1.0+.08*finish);
        m.f0=vec3(.047,.049,.052);
        m.roughness=.27+.022*finish+.016*fine;
        m.anisotropy=.12;
    } else if(finishID<3.5) {
        // Clean bead-milled/turned aluminium; brushed tangent supplied by
        // geometry. Filtering attenuates subpixel tool-feed normal slopes.
        m.base=vec3(.50,.53,.56);
        m.f0=vec3(.66,.69,.72);
        m.metal=1.0;
        m.roughness=.26+.020*finish+.016*fine;
        m.anisotropy=.42;
        float toolCoordinate=q.y;
        if(hit.part==13.0 || hit.part==32.0 || hit.part==44.0) {
            vec2 center=hit.part==13.0?vec2(0.0,.72):vec2(0.0);
            toolCoordinate=length(q.xy-center);
        }
        float feed=sin(toolCoordinate*RL_TAU*145.0+.14*sin(q.x*17.0));
        float filteredFeed=feed*exp(-.22*rlSq(RL_TAU*145.0*footprint));
        m.normal=normalize(n+b*(.009*filteredFeed));
    } else if(finishID<4.5) {
        // Steel socket screws and polished bearing seats. A wide enough
        // lobe keeps the fasteners stable at video pixel footprints.
        m.base=vec3(.30,.32,.34);
        m.f0=vec3(.56,.59,.62);
        m.metal=1.0;
        m.roughness=.235+.030*finish+.015*fine;
        m.anisotropy=.28;
    } else if(finishID<5.5) {
        // Matte elastomer boots, cable jackets and finger contact pads.
        m.base=vec3(.006,.008,.011)*(1.0+.08*finish);
        m.f0=vec3(.032);
        m.roughness=.52+.025*finish+.022*fine;
    } else if(finishID<6.5) {
        // Restrained copper-orange metal accent rings. Colour comes from
        // spectral reflectance, with the same physical highlights as metal.
        m.base=vec3(.38,.19,.07);
        m.f0=vec3(.69,.40,.18);
        m.metal=1.0;
        m.roughness=.285+.027*finish+.015*fine;
        m.anisotropy=.44;
    } else if(finishID<7.5) {
        // A dense graphite work surface: a fine finish, not gravel/noise.
        float broad=noise2(position.xz*1.1)-.5;
        m.base=(position.y< -2.?vec3(.010,.012,.015):vec3(.024,.029,.036))*(1.0+.035*broad);
        m.f0=vec3(.037);
        m.roughness=.47+.012*fine;
        m.anisotropy=.08;
    } else if(finishID<8.5) {
        // The handled calibration puck has a slightly brighter cut finish
        // than the arm's aluminium. Its highlight makes the transfer legible.
        m.base=vec3(.53,.55,.58);
        m.f0=vec3(.71,.735,.76);
        m.metal=1.0;
        m.roughness=.235+.030*finish+.020*fine;
        m.anisotropy=.49;
        float feed=sin(length(q.xz)*RL_TAU*155.0);
        m.normal=normalize(n+b*(.008*feed*
            exp(-.22*rlSq(RL_TAU*155.0*footprint))));
    } else if(finishID<9.5) {
        // A small status emitter. No screen-space glow or painted halo.
        m.base=vec3(.015,.11,.075);
        m.f0=vec3(.045);
        m.roughness=.22;
        m.emission=vec3(.13,1.65,.73);
    } else {
        // Recessed engraving and dark screw-socket interiors.
        m.base=vec3(.003,.004,.005);
        m.f0=vec3(.025);
        m.roughness=.57;
    }
    m.roughness=clamp(m.roughness,.20,.62);
    m.tangent=robotTangent(m.normal,m.tangent);
    return m;
}

vec3 robotFresnel(vec3 f0,float cosine) {
    float grazing=pow(1.0-rlSat(cosine),5.0);
    return f0+(vec3(1)-f0)*grazing;
}

vec2 robotGaussNode(int index) {
    int k=index/2;
    if(k==0) return vec2(-.9061798459,.2369268851);
    if(k==1) return vec2(-.5384693101,.4786286705);
    if(k==2) return vec2(0.,.5688888889);
    if(k==3) return vec2(.5384693101,.4786286705);
    return vec2(.9061798459,.2369268851);
}
float robotLambda(vec3 direction,vec3 n,vec3 tangent,vec3 bitangent,vec2 alpha) {
    float cosine=max(abs(dot(direction,n)),.0001);
    float slopes=rlSq(alpha.x*dot(direction,tangent))+
                 rlSq(alpha.y*dot(direction,bitangent));
    return .5*(sqrt(1.0+slopes/(cosine*cosine))-1.0);
}

vec3 robotBRDF(RobotMaterial m,vec3 n,vec3 tangent,vec3 bitangent,
               vec2 alpha,vec3 V,vec3 L,float lambdaV) {
    float NoV=max(dot(n,V),.0001);
    float NoL=dot(n,L);
    if(NoL<=0.0) return vec3(0);
    vec3 H=normalize(V+L);
    float slope=rlSq(dot(H,tangent)/alpha.x)+
                rlSq(dot(H,bitangent)/alpha.y)+rlSq(dot(H,n));
    float D=1.0/(RL_PI*alpha.x*alpha.y*slope*slope);
    float G=1.0/(1.0+lambdaV+robotLambda(L,n,tangent,bitangent,alpha));
    vec3 F=robotFresnel(m.f0,dot(V,H));
    vec3 specular=F*(D*G/max(4.0*NoV*NoL,.00001));
    vec3 diffuse=m.base*((1.0-m.metal)/RL_PI)*(vec3(1)-F);
    return diffuse+specular;
}

vec3 shadeSurface(Hit hit,vec3 position,vec3 rayDirection) {
    RobotMaterial m=robotMaterial(hit,position);
    vec3 n=dot(m.normal,rayDirection)>0.0?-m.normal:m.normal;
    vec3 V=-rayDirection;
    float NoV=max(dot(n,V),.0001);
    vec3 tangent=robotTangent(n,m.tangent);
    vec3 bitangent=cross(n,tangent);
    float aspect=sqrt(max(.15,1.0-.86*m.anisotropy));
    vec2 alpha=max(vec2(.027),m.roughness*m.roughness*
                   vec2(aspect,1.0/aspect));
    float lambdaV=robotLambda(V,n,tangent,bitangent,alpha);
    float bias=max(.00018,pixelFootprint*hit.t*.055);
    float ao=ambientOcclusion(position+n*bias,n);
    vec3 F=robotFresnel(m.f0,NoV);

    // Low-frequency studio irradiance and a very weak floor bounce. These
    // are explicitly approximate indirect terms, not a full GI solution.
    vec3 ambient=mix(vec3(.050,.056,.067),vec3(.10,.113,.137),
                     .5+.5*n.y);
    vec3 c=m.base*(1.0-m.metal)*(vec3(1)-F)*ambient*ao;
    vec3 R=reflect(rayDirection,n);
    c+=studioBackground(R)*F*mix(ao,1.0,pow(1.0-NoV,3.0));
    c+=m.emission;

    for(int i=0;i<3;i++) {
        RobotLight light=robotLight(i);
        vec3 lightNormal=cross(light.u,light.v);
        // Conservative rectangle bounds: these lights contribute exactly
        // zero when every emitter sample is below either facing hemisphere.
        vec3 emitterDelta=light.position-position;
        float receiverUpper=dot(n,emitterDelta)+abs(dot(n,light.u))*light.halfSize.x+abs(dot(n,light.v))*light.halfSize.y;
        float emitterUpper=-dot(lightNormal,emitterDelta)+abs(dot(lightNormal,light.u))*light.halfSize.x+abs(dot(lightNormal,light.v))*light.halfSize.y;
        float facingGuard=1e-5*(1.+length(emitterDelta)+light.halfSize.x+light.halfSize.y);
        if(receiverUpper < -facingGuard || emitterUpper < -facingGuard) continue;
        float visibility=0.;
#ifndef P5_SHADOW_SAMPLES
#define P5_SHADOW_SAMPLES 2
#endif
        for(int si=0;si<P5_SHADOW_SAMPLES;si++) {
            vec2 sv=si==0?vec2(-.38,.31):si==1?vec2(.38,-.31):si==2?vec2(.36,.37):vec2(-.36,-.37);
            if(P5_SHADOW_SAMPLES==1) sv=vec2(0.);
            vec3 sp=light.position+light.u*sv.x*light.halfSize.x+light.v*sv.y*light.halfSize.y;
            visibility+=softShadow(position+n*max(bias,.00035),sp);
        }
        visibility/=float(P5_SHADOW_SAMPLES);
        float weight=1.;
        vec3 integral=vec3(0);
        for(int y=0;y<5;y++) {
            vec2 gy=robotGaussNode(2*y);
            for(int x=0;x<5;x++) {
                vec2 gx=robotGaussNode(2*x);
                vec2 uv=vec2(gx.x,gy.x)*light.halfSize;
                vec3 delta=light.position+light.u*uv.x+light.v*uv.y-position;
                float distanceSquared=dot(delta,delta);
                vec3 L=delta*inversesqrt(distanceSquared);
                float cosEmitter=max(-dot(lightNormal,L),0.0);
                float NoL=max(dot(n,L),0.0);
                float measure=weight*gx.y*gy.y*light.halfSize.x*
                    light.halfSize.y*cosEmitter*NoL/distanceSquared;
                integral+=robotEmitterRadiance(light,uv)*measure*
                    robotBRDF(m,n,tangent,bitangent,alpha,V,L,lambdaV);
            }
        }
        c+=integral*visibility;
    }
    return max(c,vec3(0));
}
