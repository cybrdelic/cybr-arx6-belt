/* Reproducible coupled-body simulations, not injected/synthetic trajectories. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import load from '../runtime/node_modules/@mujoco/mujoco/mujoco.js';
import {ArmSimulation} from './controller.mjs';
const R=path.dirname(fileURLToPath(import.meta.url));
const O=process.env.ARX_VALIDATION_OUT ? path.resolve(process.env.ARX_VALIDATION_OUT) : R;
fs.mkdirSync(path.join(O,'results'),{recursive:true});fs.mkdirSync(path.join(O,'reports'),{recursive:true});
const read=n=>fs.readFileSync(path.join(R,n),'utf8');
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
const xml=read('ARX-6-P5.xml'),p=JSON.parse(read('parameters.json')),api=JSON.parse(read('../dynamics/interface.json'));
const inputNames=['ARX-6-P5.xml','parameters.json','controller.mjs','safety.mjs','geometry-meshes.json','p5_collision_proxies.json','mass_properties.json'];
const inputHashes=Object.fromEntries(inputNames.map(n=>[n,sha(read(n))]));
function assertStableInputs(){for(const n of inputNames)if(sha(read(n))!==inputHashes[n])throw new Error('P5 input changed during integration: '+n);}
const mj=await load();
const simHz=2400, sampleHz=120;
const only=process.argv[2]||null;
if(p.model_revision!=='P5')throw new Error('P5 regenerated parameters are required');
const cases=[
 {name:'nominal',seconds:10,options:{}},
 {name:'nominal_30s',seconds:30,options:{}},
 {name:'dt1200',seconds:10,options:{},dt:1/1200},
 {name:'dt4800',seconds:10,options:{},dt:1/4800},
 {name:'weak_spring',seconds:10,options:{springScale:.9}},
 {name:'no_counterbalance',seconds:10,options:{springScale:0}},
 {name:'normal_stop',seconds:4,options:{normalStopTime:2}},
 {name:'watchdog',seconds:4,options:{heartbeatUntil:1.9}},
 {name:'estop',seconds:4,options:{estopTime:2}},
 {name:'invalid_feedback',seconds:4,options:{invalidFeedbackTime:2}},
 {name:'power_loss_no_brakes',seconds:3,options:{motorOffTime:2,brakes:false,enforceLimits:false}},
 {name:'friction_loss',seconds:5,options:{frictionChangeTime:2,frictionAfterScale:.01}},
 {name:'weak_grip',seconds:5,options:{gripScale:.025}},
 ...[.6,1.2,1.9,2.2,2.6,3.2,6.2,7.2].map(t=>({name:`power_loss_${t.toFixed(1)}`,seconds:t+1.2,options:{motorOffTime:t}})),
 ...[1.2,1.9,2.2,2.6,3.2,7.2].map(t=>({name:`weak_spring_double_delay_${t.toFixed(1)}`,seconds:t+1.2,options:{motorOffTime:t,springScale:.9,brakeDelayScale:2}})),
 {name:'brake_torque_40pct',seconds:3.4,options:{motorOffTime:2.2,springScale:.9,brakeDelayScale:2,brakeScale:2/3}},
];
const outputs=[];
for(const c of cases){
 if(only&&c.name!==only)continue;
 const start=performance.now(),s=new ArmSimulation(mj,xml,p,api,c.options);
 if(c.dt)s.model.opt.timestep=c.dt;
 const dt=s.model.opt.timestep,total=Math.round(c.seconds/dt),stride=Math.round(1/(sampleHz*dt));
 // Refresh all interface provenance and initial conditions. Only the schema is
 // inherited from the baseline; old XML hashes or initial currents must never
 // be presented as metadata for this regenerated model.
 s.api={...s.api,model_revision:'P5',mujoco_version:mj.mj_versionString(),
   nq:s.model.nq,nv:s.model.nv,nu:s.model.nu,timestep_seconds:dt,
   initial_qpos:Array.from(s.data.qpos),initial_qvel:Array.from(s.data.qvel),
   initial_motor_current_A:Array.from(s.current),xml_sha256:sha(xml),
   initialization:'mj_resetDataKeyframe(model,data,0); mj_forward(model,data); initial current=(bias minus shoulder/elbow spring torque)/(gear ratio*Kt), clipped to current limits; other controller states zero; motor temperature25C.',
   provenance:{model_xml_sha256:sha(xml),controller_parameters_file_sha256:sha(read('parameters.json')),
     controller_sha256:sha(read('controller.mjs')),safety_sha256:sha(read('safety.mjs')),
     cad_mass_properties_sha256:sha(read('mass_properties.json')),collision_proxies_sha256:sha(read('p5_collision_proxies.json')),mujoco_version:mj.mj_versionString()}};
 s.api.joints=Object.fromEntries(['j1','j2','j3','j4','j5','j6','jaw_left','jaw_right','puck_free'].map(name=>{
   const id=mj.mj_name2id(s.model,3,name);return [name,{id,qpos_adr:s.model.jnt_qposadr[id],dof_adr:s.model.jnt_dofadr[id]}];
 }));
 const frames=[],telemetry=[],poses=[],checks=[];
 let faultQ=null,faultTCP=null,faultPuck=null,faultTime=null,maxDrift=new Array(6).fill(0),maxTCPDrift=0,maxPuckDrop=0,maxSettledSpeed=0;
 let minLimitMargin=Infinity,maxTrackingError=0,maxPenetration=0,maxUnintendedPenetration=0,unintendedPairs={},unintendedPairTimes={},normalHoldPuckRange=[],maxGripCurrent=0,gripOverContinuous=0,maxPuckAppliedForce=0;
 let maxSpringForce=0,minSpringTorque=Infinity,maxSpringTorque=-Infinity,maxElbowSpringForce=0,minElbowSpringTorque=Infinity,maxElbowSpringTorque=-Infinity;
 const maxBrakeCap=new Array(6).fill(0),maxBrakeTorque=new Array(6).fill(0);
 const maxEstimatedBeltTorque=new Array(6).fill(0);
 const jointsAtMaxDrift=new Array(6).fill(0);
 const geomNames=Array.from({length:s.model.ngeom},(_,i)=>mj.mj_id2name(s.model,5,i));
 function inspectContacts(){
   const cs=s.data.contact;
   try{for(let k=0;k<cs.size();k++){const cc=cs.get(k);try{
      const pen=Math.max(0,-cc.dist);maxPenetration=Math.max(maxPenetration,pen);
      const involvesPuck=cc.geom1===s.api.geom_ids.puck||cc.geom2===s.api.geom_ids.puck;
      if(pen>1e-5&&!involvesPuck){
        const pair=[geomNames[cc.geom1],geomNames[cc.geom2]].sort().join(' / ');
        if(pen>(unintendedPairs[pair]||0)){
          unintendedPairs[pair]=pen;unintendedPairTimes[pair]=Math.max(0,(s.steps-1)*dt);
        }
        maxUnintendedPenetration=Math.max(maxUnintendedPenetration,pen);
      }
   }finally{cc.delete();}}}finally{cs.delete();}
 }
 function capture(){
   // Kinematics only refreshes body/geometry transforms; no forces or generalized
   // coordinates are imposed, including on the independently simulated puck.
   mj.mj_kinematics(s.model,s.data);
   const f=s.frame(),tt=s.telemetry();frames.push(f);telemetry.push(tt);
   if(c.name==='nominal'||c.name==='estop'||c.name==='normal_stop')poses.push(s.transforms());
   if(s.steps>0)maxTrackingError=Math.max(maxTrackingError,...s.desiredQ.map((q,i)=>Math.abs(q-s.data.qpos[i])));
   for(let i=0;i<6;i++)minLimitMargin=Math.min(minLimitMargin,s.data.qpos[i]-p.integration.joint_hard_limits_rad[i][0],p.integration.joint_hard_limits_rad[i][1]-s.data.qpos[i]);
   if(faultQ){
     const d=s.data;
     for(let i=0;i<6;i++){const delta=Math.abs(d.qpos[i]-faultQ[i]);if(delta>maxDrift[i]){maxDrift[i]=delta;jointsAtMaxDrift[i]=f[0];}}
     maxTCPDrift=Math.max(maxTCPDrift,Math.hypot(...f.slice(44,47).map((x,i)=>x-faultTCP[i])));
     maxPuckDrop=Math.max(maxPuckDrop,faultPuck[1]-d.qpos[9]);
     if(f[0]>faultTime+.5)maxSettledSpeed=Math.max(maxSettledSpeed,...Array.from(d.qvel.slice(0,6),Math.abs));
   }
   if(c.name==='normal_stop'&&f[0]>2.6)normalHoldPuckRange.push(f.slice(15,18));
 }
 capture();inspectContacts();
 for(let n=0;n<total;n++){
   const before=Array.from(s.data.qpos.slice(0,6));const preTCP=Array.from(s.data.site_xpos.slice(s.api.tcp_site_id*3,s.api.tcp_site_id*3+3)),prePuck=Array.from(s.data.qpos.slice(8,11));
   s.step();
   inspectContacts();
   for(let i=0;i<6;i++)minLimitMargin=Math.min(minLimitMargin,s.data.qpos[i]-p.integration.joint_hard_limits_rad[i][0],p.integration.joint_hard_limits_rad[i][1]-s.data.qpos[i]);
   maxPuckAppliedForce=Math.max(maxPuckAppliedForce,...Array.from(s.data.qfrc_applied.slice(8,14),Math.abs),...Array.from(s.data.xfrc_applied.slice(s.api.body_ids.puck*6,s.api.body_ids.puck*6+6),Math.abs));
   if(s.safety.faultTime!=null&&faultQ===null){faultTime=s.safety.faultTime;faultQ=before;faultTCP=preTCP;faultPuck=prePuck;}
   maxGripCurrent=Math.max(maxGripCurrent,Math.abs(s.gripperCurrent));
   if(Math.abs(s.gripperCurrent)>p.gripper.continuous_current_A+1e-6)gripOverContinuous+=dt;
   maxSpringForce=Math.max(maxSpringForce,s.spring.force_each_N);minSpringTorque=Math.min(minSpringTorque,s.spring.torque_Nm);maxSpringTorque=Math.max(maxSpringTorque,s.spring.torque_Nm);
   maxElbowSpringForce=Math.max(maxElbowSpringForce,s.elbowSpring.force_each_N);minElbowSpringTorque=Math.min(minElbowSpringTorque,s.elbowSpring.torque_Nm);maxElbowSpringTorque=Math.max(maxElbowSpringTorque,s.elbowSpring.torque_Nm);
   for(let i=0;i<6;i++){
     maxBrakeCap[i]=Math.max(maxBrakeCap[i],s.brakeCapacity[i]);maxBrakeTorque[i]=Math.max(maxBrakeTorque[i],Math.abs(s.brakeTorque[i]));
     // The belt can transmit a decelerating rotor's torque even with electrical
     // power removed. Subtract the upstream armature acceleration from motor
     // torque to estimate delivery to the links in this rigid lumped model.
     const acceleration=(s.data.qvel[i]-s.preStepVelocity[i])/dt;
     const transmitted=s.torque[i]-s.model.dof_armature[i]*acceleration;
     maxEstimatedBeltTorque[i]=Math.max(maxEstimatedBeltTorque[i],Math.abs(transmitted));
   }
   if((n+1)%stride===0||n+1===total)capture();
 }
 const elapsed=s.steps*dt,mon=s.monitor,finite=frames.every(f=>f.every(Number.isFinite));
 const rms=Array.from(mon.rmsIntegral,x=>Math.sqrt(x/elapsed));
 const nearest=t=>frames.reduce((a,b)=>Math.abs(b[0]-t)<Math.abs(a[0]-t)?b:a);
 const targetError=(t,target)=>Math.hypot(...nearest(t).slice(15,18).map((x,i)=>x-p.workpiece_targets_m[target][i]));
 const checksPush=(name,passed,detail)=>checks.push({name,passed:Boolean(passed),detail});
 checksPush('all integrated states finite',finite,'All 47 exported fields, every saved state.');
 checksPush('hard travel bounds respected',minLimitMargin>=-1e-4,`Minimum margin ${minLimitMargin} rad; dynamic contact joints not clamped.`);
 checksPush('no structural proxy penetration over 0.1 mm',maxUnintendedPenetration<1e-4,`Every integration step inspected. Worst ${maxUnintendedPenetration} m; flexible spring/cable and literal pin impact excluded.`);
 checksPush('no imposed force on independent free workpiece',maxPuckAppliedForce===0,{max_imposed_generalized_or_body_force:maxPuckAppliedForce,workpiece_qpos_count:7,workpiece_velocity_dofs:6,attachment:'No workpiece weld, actuator, or post-reset pose command.'});
 checksPush('motor-generated output torque within belt service allowance',Array.from(mon.maxTorque).every((x,i)=>x<=p.motors.belt_allowable_output_torque_Nm[i]+1e-5),{peak_output_torque_Nm:Array.from(mon.maxTorque),allowance_Nm:p.motors.belt_allowable_output_torque_Nm,service_factor:p.motors.belt_service_factor});
 checksPush('estimated belt torque including rotor deceleration within service allowance',maxEstimatedBeltTorque.every((x,i)=>x<=p.motors.belt_allowable_output_torque_Nm[i]+1e-5),{peak_estimated_transmitted_torque_Nm:maxEstimatedBeltTorque,allowance_Nm:p.motors.belt_allowable_output_torque_Nm,method:'Motor-generated output torque minus equivalent upstream armature times actual angular acceleration. Ideal rigid lumped transmission; no tooth impact or compliance.'});
 checksPush('configured arm peak current ceilings',Array.from(mon.maxCurrent).every((x,i)=>x<=p.motors.peak_current_A[i]+1e-5),'Electrical model incl. back-EMF and voltage saturation.');
 checksPush('configured gripper peak current ceiling',maxGripCurrent<=.35+1e-6,`${maxGripCurrent} A; ideal hardware-chopping approximation.`);
 checksPush('belt pulley speed within handbook low-speed screen',Array.from(mon.maxSpeed).every((x,i)=>x/p.motors.gear_ratio[i]*60/(2*Math.PI)<=200),Array.from(mon.maxSpeed,(x,i)=>x/p.motors.gear_ratio[i]*60/(2*Math.PI)));
 checksPush('motor input speed ratings',Array.from(mon.maxSpeed).every((x,i)=>x<=p.motors.gear_max_input_speed_rad_s[i]),'Actual motor speed includes gear ratio.');
 checksPush('voltage ceilings',Array.from(mon.maxVoltage).every((x,i)=>x<=p.motors.bus_voltage_V[i]*p.motors.max_pwm_duty[i]+1e-6),'Actual applied voltage, not unclipped demand.');
 const isNominal=['nominal','nominal_30s','dt1200','dt4800','weak_spring','no_counterbalance'].includes(c.name);
 if(isNominal){
   checksPush('completed without safety trip',s.safety.mode==='RUN',s.safety.reason||'RUN');
   checksPush('arm RMS currents below continuous ratings',rms.every((x,i)=>x<=p.motors.continuous_current_A[i]),rms);
   checksPush('placement at B within 1.5 mm',targetError(4.9,'B')<.0015,targetError(4.9,'B'));
   checksPush('return to A within 1.5 mm',targetError(c.seconds-.1,'A')<.0015,targetError(c.seconds-.1,'A'));
 }
 if(faultQ&&c.options.brakes!==false){
   checksPush('all drives disabled after emergency',s.current.every(x=>Math.abs(x)<1e-12)&&s.gripperCurrent===0,'Including the gripper; carried payload is not guaranteed retained.');
   checksPush('all joints settle below 0.002 rad/s',maxSettledSpeed<.002,maxSettledSpeed);
   checksPush('model brake work below catalog event-energy ceiling',Array.from(s.brakeEnergy).every((x,i)=>x<p.integration.brakes[i<3?'large':'small'].max_single_stop_energy_J),'Catalog energy limit is not a dynamic torque guarantee or safety certification.');
 }
 if(c.name==='normal_stop'){
   const ranges=[0,1,2].map(i=>Math.max(...normalHoldPuckRange.map(x=>x[i]))-Math.min(...normalHoldPuckRange.map(x=>x[i])));
   checksPush('normal stop retains grip power',s.safety.mode==='HOLD'&&Math.abs(s.gripperCurrent)>.01,'Separate from emergency stop and command watchdog.');
   checksPush('held payload drift below 1 mm',Math.hypot(...ranges)<.001,ranges);
 }
 const metrics={name:c.name,duration_s:elapsed,dt_s:dt,solver:'MuJoCo 3.16.0 WASM; implicitfast; Newton',options:c.options,mode:s.safety.mode,events:s.safety.events,checks,all_checks_pass:checks.every(x=>x.passed),
   rms_current_A:rms,peak_current_A:Array.from(mon.maxCurrent),peak_output_torque_Nm:Array.from(mon.maxTorque),peak_estimated_belt_transmitted_torque_Nm:maxEstimatedBeltTorque,peak_motor_speed_rad_s:Array.from(mon.maxSpeed),peak_voltage_V:Array.from(mon.maxVoltage),over_continuous_current_s:Array.from(mon.overContinuousSeconds),over_continuous_gear_torque_s:Array.from(mon.overGearContinuousSeconds),voltage_saturation_s:Array.from(mon.voltageSaturationSeconds),belt_demand_limit_s:Array.from(mon.beltDemandLimitSeconds),gear_demand_limit_s:Array.from(mon.gearDemandLimitSeconds),final_temperature_C:Array.from(s.temperature),gripper_rms_current_A:Math.sqrt(s.gripperI2Integral/elapsed),peak_gripper_current_A:maxGripCurrent,gripper_over_continuous_s:gripOverContinuous,gripper_final_temperature_C:s.gripperTemperature,
   max_tracking_error_rad:maxTrackingError,min_hard_limit_margin_rad:minLimitMargin,max_penetration_m:maxPenetration,max_unintended_proxy_penetration_m:maxUnintendedPenetration,unintended_proxy_pairs:unintendedPairs,unintended_proxy_pair_worst_time_s:unintendedPairTimes,spring_force_max_each_N:maxSpringForce,spring_torque_range_Nm:[minSpringTorque,maxSpringTorque],elbow_spring_force_max_each_N:maxElbowSpringForce,elbow_spring_torque_range_Nm:[minElbowSpringTorque,maxElbowSpringTorque],maximum_imposed_workpiece_force:maxPuckAppliedForce,fault_time_s:faultTime,max_fault_travel_deg:maxDrift.map(x=>x*180/Math.PI),max_fault_travel_at_s:jointsAtMaxDrift,max_fault_tcp_travel_m:maxTCPDrift,max_fault_puck_drop_m:maxPuckDrop,max_speed_after_fault_plus_0p5s_rad_s:maxSettledSpeed,brake_energy_J:Array.from(s.brakeEnergy),brake_max_capacity_Nm:maxBrakeCap,brake_max_actual_torque_Nm:maxBrakeTorque,placement_B_error_m:targetError(Math.min(4.9,c.seconds),'B'),return_A_error_m:targetError(c.seconds-.1,'A'),
   provenance:{xml_sha256:sha(xml),controller_sha256:sha(read('controller.mjs')),safety_sha256:sha(read('safety.mjs')),parameters_sha256:sha(read('parameters.json')),geometry_sha256:sha(read('geometry-meshes.json')),collision_proxies_sha256:sha(read('p5_collision_proxies.json')),cad_mass_properties_sha256:sha(read('mass_properties.json'))},wall_time_s:(performance.now()-start)/1000};
 assertStableInputs();
 const report={metrics,interface:s.api,frames,telemetry};if(poses.length)report.poses=poses;
 fs.writeFileSync(path.join(O,'results',c.name+'.json'),JSON.stringify(report));
 fs.writeFileSync(path.join(O,'results',c.name+'-metrics.json'),JSON.stringify(metrics,null,2)+'\n');
 outputs.push(metrics);console.log(JSON.stringify({name:c.name,pass:metrics.all_checks_pass,failed:checks.filter(x=>!x.passed),rms,drift:metrics.max_fault_travel_deg,settled:maxSettledSpeed,ms:Math.round(performance.now()-start)}));
 s.destroy();
}
fs.writeFileSync(path.join(O,'reports',only?'validation-'+only+'.json':'validation-summary.json'),JSON.stringify({date:new Date().toISOString(),revision:'P5 compact folded drives',engine:'MuJoCo 3.16.0 bundled WASM',scenarios:outputs,summary:{scenarios:outputs.length,passed:outputs.filter(x=>x.all_checks_pass).length,checks:outputs.reduce((n,x)=>n+x.checks.length,0),failed_checks:outputs.reduce((n,x)=>n+x.checks.filter(y=>!y.passed).length,0)},qualification:'Executable model verification only. Brake dynamic torque, switching, flexible components, thermal constants, friction, fixture strength and supplier interfaces require physical qualification.'},null,2)+'\n');

// Expected negative controls must fail; no new failure is silently accepted.
const deliberateControls=new Set(['no_counterbalance','power_loss_no_brakes','friction_loss','weak_grip']);
if(outputs.some(x=>!deliberateControls.has(x.name)&&!x.all_checks_pass))process.exitCode=1;
