/* Quantify previously detected off-path primitive interference. These angles
 * are for native CAD refinement, not automatic permission to move a stop. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import load from '../runtime/node_modules/@mujoco/mujoco/mujoco.js';
const R=path.dirname(fileURLToPath(import.meta.url)),xml=fs.readFileSync(path.join(R,'ARX-6-P5.xml'),'utf8');
const spec=JSON.parse(fs.readFileSync(path.join(R,'spec.json'),'utf8'));
const mj=await load();mj.FS.writeFile('/range-review.xml',xml);
const m=mj.MjModel.mj_loadXML('/range-review.xml'),d=new mj.MjData(m),segment=new mj.DoubleBuffer(6);
mj.mj_resetDataKeyframe(m,d,0);const home=Array.from(d.qpos.slice(0,6));
const sets=[
  {joint:3,interval:[1.8,2.1],pairs:[['structure_upper_tube','structure_fore_tube'],['structure_upper_mount_standoff_20','structure_fore_root_tab'],['structure_upper_mount_standoff_20','structure_fore_tube']]},
  {joint:5,interval:[1.5,1.75],pairs:[['structure_bend_support_rail_28.5','structure_roll_fork_bridge']]}
];
const results=[];
for(const group of sets){
  const ids=group.pairs.map(pair=>pair.map(name=>mj.mj_name2id(m,5,name)));
  function probe(q){d.qpos.set(home,0);d.qpos[group.joint-1]=q;mj.mj_kinematics(m,d);return Math.min(...ids.map(([a,b])=>mj.mj_geomDistance(m,d,a,b,.1,segment)));}
  function angleForGap(gap){let [lo,hi]=group.interval;if(probe(lo)<gap||probe(hi)>gap)return null;
    for(let n=0;n<50;n++){const mid=(lo+hi)/2;if(probe(mid)>=gap)lo=mid;else hi=mid;}return (lo+hi)/2;}
  results.push({joint:group.joint,tested_pairs:group.pairs,other_joint_positions_rad:home,
    first_zero_clearance_angle_rad:angleForGap(0),angle_at_1mm_clearance_rad:angleForGap(.001),
    angle_at_2mm_clearance_rad:angleForGap(.002),retired_upper_hard_limit_rad:group.interval[1],
    retired_hard_limit_signed_clearance_mm:probe(group.interval[1])*1000,
    current_upper_hard_limit_rad:spec.joint_hard_limits_rad[group.joint-1][1],
    current_hard_limit_signed_clearance_mm:probe(spec.joint_hard_limits_rad[group.joint-1][1])*1000});
}
const report={revision:'P5',date_utc:new Date().toISOString(),model_sha256:crypto.createHash('sha256').update(xml).digest('hex'),results,
  scope:'Rigid primitive distances for the named structural pairs, including the retired ranges to document the correction. Angles beyond the current stop are diagnostic poses only. Native BREP refinement is reported separately; this does not certify all joint combinations or tolerance stacks.'};
fs.writeFileSync(path.join(R,'reports/P5-joint-range-review.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));segment.delete();d.delete();m.delete();
