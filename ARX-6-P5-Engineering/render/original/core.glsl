// ARX / 6 — an entirely procedural six-axis robotic arm.
// FragCoord single Main fragment pass. No textures, meshes or image inputs.
// CAPTURE emits linear light for external multisample film integration.
#ifndef AA
#define AA 2
#endif
#define PI 3.141592653589793
#define TAU 6.283185307179586
float sceneTime;
float pixelFootprint;
float hash12(vec2 p) {
    vec3 p3=fract(vec3(p.xyx)*.1031);
    p3+=dot(p3,p3.yzx+33.33);
    return fract((p3.x+p3.y)*p3.z);
}
vec2 hash22(vec2 p) { return vec2(hash12(p),hash12(p+vec2(87.13,23.71))); }
float noise2(vec2 p) {
    vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(hash12(i),hash12(i+vec2(1,0)),f.x),mix(hash12(i+vec2(0,1)),hash12(i+vec2(1,1)),f.x),f.y);
}
float noise3(vec3 p) {
    vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    vec2 q=i.xy+vec2(37,17)*i.z;
    float a=mix(mix(hash12(q),hash12(q+vec2(1,0)),f.x),mix(hash12(q+vec2(0,1)),hash12(q+vec2(1,1)),f.x),f.y);
    q+=vec2(37,17);
    float b=mix(mix(hash12(q),hash12(q+vec2(1,0)),f.x),mix(hash12(q+vec2(0,1)),hash12(q+vec2(1,1)),f.x),f.y);
    return mix(a,b,f.z);
}
