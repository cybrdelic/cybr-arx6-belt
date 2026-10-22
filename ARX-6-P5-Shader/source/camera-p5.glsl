// P5 film and interactive camera. Rendering uses the current physical state.
uniform int u_camera_override;
uniform vec3 u_camera_origin;
uniform vec3 u_camera_target;
uniform float u_camera_focal;
uniform float u_aperture;
uniform int u_samples;
uniform float u_exposure;

vec3 aces(vec3 x) { return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.); }
float radicalInverse(int n,int base) {
    float inv=1./float(base),weight=inv,value=0.;
    for(int i=0;i<12;i++) {
        if(n==0) break;
        value+=float(n%base)*weight; n/=base; weight*=inv;
    }
    return value;
}

vec3 renderCamera(vec2 frag,vec2 jitter,int sampleIndex) {
    vec2 screen=(2.*(frag+jitter)-u_resolution)/u_resolution.y;
    float azimuth=.67+u_drag.x/max(u_resolution.x,1.)*3.;
    float elevation=clamp(.28+u_drag.y/max(u_resolution.y,1.)*1.6,-.2,1.30);
    float distance=clamp(6.4*exp(-u_scroll*.11),.5,18.);
    vec3 target=vec3(.68,1.25,0.);
    vec3 ro=target+distance*vec3(sin(azimuth)*cos(elevation),sin(elevation),cos(azimuth)*cos(elevation));
    float focal=3.15*min(1.,u_resolution.x/(u_resolution.y*1.35));
    if(u_camera_override!=0) {
        ro=u_camera_origin; target=u_camera_target;
        distance=length(ro-target); focal=max(.5,u_camera_focal);
    }
    vec3 forward=normalize(target-ro);
    vec3 right=normalize(cross(forward,vec3(0,1,0)));
    vec3 up=cross(right,forward);
    pixelFootprint=2./(u_resolution.y*focal);
    vec3 rd=normalize(forward*focal+screen.x*right+screen.y*up);
    if(u_aperture>0.) {
        float angle=TAU*radicalInverse(sampleIndex+1,5);
        float radius=u_aperture*sqrt(radicalInverse(sampleIndex+1,7));
        vec3 focus=ro+rd*(distance/max(.1,dot(rd,forward)));
        ro+=radius*(cos(angle)*right+sin(angle)*up);
        rd=normalize(focus-ro);
    }
    Hit h=traceScene(ro,rd);
    vec3 color;
    if(h.id<.5) color=studioBackground(rd);
    else {
        applyMarkings(h);
#ifdef DEBUG_NORMAL
        color=.5+.5*h.n;
#else
        color=shadeSurface(h,ro+rd*h.t,rd);
#endif
    }
    return max(color,vec3(0))*exp2(u_exposure)*max(.85,1.-.018*dot(screen,screen));
}

void main() {
    sceneTime=max(u_time,0.);
    initKinematics(sceneTime);
    initScene();
#ifdef CAPTURE
    int index=u_frame;
    robotLightPhase=index%4;
    vec2 jitter=vec2(radicalInverse(index+1,2),radicalInverse(index+1,3))-.5;
    fragColor=vec4(renderCamera(gl_FragCoord.xy,jitter,index),1);
#else
    int samples=u_samples>1?4:1;
    vec3 color=vec3(0);
    for(int k=0;k<4;k++) {
        if(k>=samples) break;
        robotLightPhase=k;
        vec2 jitter=samples==1?vec2(0):vec2(radicalInverse(k+1,2),radicalInverse(k+1,3))-.5;
        color+=renderCamera(gl_FragCoord.xy,jitter,k);
    }
    color/=float(samples);
    fragColor=vec4(pow(aces(color),vec3(1./2.2)),1);
#endif
}
