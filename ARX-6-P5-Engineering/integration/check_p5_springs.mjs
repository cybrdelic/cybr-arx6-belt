/* Verify that the actual revised anchor geometry supplies a conservative force law. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {springState} from './safety.mjs';

const R=path.dirname(fileURLToPath(import.meta.url));
const specText=fs.readFileSync(path.join(R,'spec.json'),'utf8'),spec=JSON.parse(specText);
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const rows=[];
for(const index of [1,2]){
  const s=index===1?spec.counterbalance:spec.elbow_counterbalance;
  const limits=spec.joint_hard_limits_rad[index],step=1e-6;
  const samples=[];
  for(let k=0;k<=120;k++){
    const q=limits[0]+(limits[1]-limits[0])*k/120;
    const state=springState(q,spec,1,index);
    const gradient=(springState(q+step,spec,1,index).potential_energy_J-springState(q-step,spec,1,index).potential_energy_J)/(2*step);
    samples.push({q_rad:q,...state,energy_torque_residual_Nm:state.torque_Nm+gradient});
  }
  const maxResidual=Math.max(...samples.map(x=>Math.abs(x.energy_torque_residual_Nm)));
  const reference=springState(s.reference_q_rad,spec,1,index);
  const forcePeak=Math.max(...samples.map(x=>x.force_each_N));
  // Wahl correction for a helical extension-spring body under axial load.
  // Eye/hook bending stress is not determined by this spring-body calculation.
  const C=s.mean_coil_diameter_mm/s.wire_diameter_mm;
  const kw=(4*C-1)/(4*C-4)+.615/C;
  const maxWireShearMPa=kw*8*forcePeak*s.mean_coil_diameter_mm/(Math.PI*s.wire_diameter_mm**3);
  const calibrationError=Math.abs(Math.abs(reference.torque_Nm)-s.reference_total_torque_Nm);
  rows.push({joint:index+1,anchors:{parent_m:s.parent_anchor_m,child_m:s.child_anchor_m},
    max_potential_gradient_residual_Nm:maxResidual,passes_conservative_force_check:maxResidual<1e-5,
    reference_torque_Nm:reference.torque_Nm,reference_target_magnitude_Nm:s.reference_total_torque_Nm,
    reference_calibration_error_Nm:calibrationError,passes_reference_calibration:calibrationError<1e-6,
    force_peak_each_N:forcePeak,min_length_m:Math.min(...samples.map(x=>x.length_m)),max_length_m:Math.max(...samples.map(x=>x.length_m)),
    max_coil_body_shear_MPa:maxWireShearMPa,spring_index:C,
    qualification:'Calculated wire-body stress only; no assumed yield/fatigue acceptance, hook strength or supplier material qualification.',samples});
}
const report={revision:'P5',date_utc:new Date().toISOString(),spec_sha256:sha(specText),safety_sha256:sha(fs.readFileSync(path.join(R,'safety.mjs'),'utf8')),method:'Independent central derivative of tension-spring potential energy across the actual joint travel. The controller applies minus its gradient.',joints:rows,all_pass:rows.every(x=>x.passes_conservative_force_check&&x.passes_reference_calibration)};
fs.writeFileSync(path.join(R,'reports','P5-spring-energy-check.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({all_pass:report.all_pass,joints:rows.map(({samples,...row})=>row)},null,2));
if(!report.all_pass)process.exitCode=1;
