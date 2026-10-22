// ARX / 6 Dynamics: forward transforms of the actual integrated SI state.
// This file contains NO prescribed joint animation and NO puck attachment.
// The host runs MuJoCo and supplies actual qpos. One scene unit = 0.20 m.
uniform vec3 u_joint012;
uniform vec3 u_joint345;
uniform vec2 u_jawsSI;
uniform vec3 u_puck_positionSI;
uniform vec4 u_puck_quaternionWXYZ;
uniform float u_cutaway;
uniform float u_explode;
uniform float u_camera_detail;

const float K_PI = 3.14159265358979323846;
const float K_TAU = 6.28318530717958647692;
const float K_METERS_PER_UNIT = 0.20;
const float K_UPPER_LENGTH = 1.40;
const float K_FORE_LENGTH = 1.30;
const float K_TOOL_LENGTH = 1.12;
const float K_PUCK_RADIUS = 0.095;
const float K_PUCK_HALF_HEIGHT = 0.070;
const float K_CYCLE_SECONDS = 10.0;
vec3 kShoulder, kElbow, kWrist, kTCP, kPuck;
vec3 kNestA, kNestB;
mat3 kBaseFrame, kUpperFrame, kForeFrame;
mat3 kRollFrame, kBendFrame, kToolFrame, kPuckFrame;
float kGrip, kGripLeft, kGripRight;
float kBaseAngle, kShoulderAngle, kElbowAngle;
float kRollAngle, kBendAngle, kToolAngle;

mat3 kRotY(float a) {
    float c=cos(a),s=sin(a);
    return mat3(vec3(c,0,-s),vec3(0,1,0),vec3(s,0,c));
}
mat3 kRotZ(float a) {
    float c=cos(a),s=sin(a);
    return mat3(vec3(c,s,0),vec3(-s,c,0),vec3(0,0,1));
}
mat3 kQuaternionFrame(vec4 wxyz) {
    vec4 q=wxyz/max(length(wxyz),1e-12);
    float w=q.x,x=q.y,y=q.z,z=q.w;
    return mat3(
        vec3(1.-2.*(y*y+z*z),2.*(x*y+w*z),2.*(x*z-w*y)),
        vec3(2.*(x*y-w*z),1.-2.*(x*x+z*z),2.*(y*z+w*x)),
        vec3(2.*(x*z+w*y),2.*(y*z-w*x),1.-2.*(x*x+y*y)));
}
void initKinematics(float time) {
    kBaseAngle=u_joint012.x;
    kShoulderAngle=u_joint012.y;
    kElbowAngle=u_joint012.z;
    kRollAngle=u_joint345.x;
    kBendAngle=u_joint345.y;
    kToolAngle=u_joint345.z;
    kBaseFrame=kRotY(-kBaseAngle);
    kShoulder=vec3(0,.72,0);
    kUpperFrame=kBaseFrame*kRotZ(-kShoulderAngle);
    kElbow=kShoulder+K_UPPER_LENGTH*kUpperFrame[1];
    kForeFrame=kUpperFrame*kRotZ(-kElbowAngle);
    kWrist=kElbow+K_FORE_LENGTH*kForeFrame[1];
    kRollFrame=kForeFrame*kRotY(kRollAngle);
    kBendFrame=kRollFrame*kRotZ(-kBendAngle);
    kToolFrame=kBendFrame*kRotY(kToolAngle);
    kTCP=kWrist+K_TOOL_LENGTH*kToolFrame[1];
    kGripLeft=u_jawsSI.x/K_METERS_PER_UNIT;
    kGripRight=u_jawsSI.y/K_METERS_PER_UNIT;
    kGrip=.5*(kGripLeft+kGripRight);
    kPuck=u_puck_positionSI/K_METERS_PER_UNIT;
    kPuckFrame=kQuaternionFrame(u_puck_quaternionWXYZ);
    kNestA=vec3(1.45,.070,-.62);
    kNestB=vec3(1.65,.070,.62);
}
