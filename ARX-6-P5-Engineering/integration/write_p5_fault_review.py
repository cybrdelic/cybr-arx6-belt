#!/usr/bin/env python3
"""Assemble the retained failed-case evidence without changing physical inputs."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parent
D = R / "diagnostics" / "brake-events"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    model_files = {"xml_sha256": "ARX-6-P5.xml", "controller_sha256": "controller.mjs",
                   "safety_sha256": "safety.mjs", "parameters_sha256": "parameters.json",
                   "geometry_sha256": "geometry-meshes.json", "collision_proxies_sha256": "p5_collision_proxies.json",
                   "cad_mass_properties_sha256": "mass_properties.json"}
    provenance = {key: sha(R / name) for key, name in model_files.items()}
    p = read(R / "parameters.json")
    names = ["power_loss_3.2", "weak_spring_double_delay_3.2", "weak_spring_double_delay_7.2"]
    metrics = {name: read(R / "results" / (name + "-metrics.json")) for name in names}
    for m in metrics.values():
        if m["provenance"] != provenance:
            raise RuntimeError("Fault evidence is stale: " + m["name"])
    nominal_sha = sha(R / "results" / "nominal.json")
    original = R / "diagnostics" / "freeze2-original-brake"
    for name in ["results/nominal.json", "ARX-6-P5.xml", "controller.mjs", "parameters.json", "safety.mjs"]:
        if sha(R / name) != sha(original / name):
            raise RuntimeError("Frozen physical source or nominal trace changed: " + name)

    exact_path = D / "weak_spring_double_delay_3.2-baseline-rate1-2400-summary.json"
    refined_path = D / "weak_spring_double_delay_3.2-baseline-rate1-4800-summary.json"
    exact, refined = read(exact_path), read(refined_path)
    if exact["peak_estimated_belt_torque_Nm"] != metrics["weak_spring_double_delay_3.2"]["peak_estimated_belt_transmitted_torque_Nm"]:
        raise RuntimeError("High-rate diagnosis must exactly reproduce the frozen weak/delayed fault")
    raw = p["motors"]["belt_screen_capacity_Nm"]
    allowance = p["motors"]["belt_allowable_output_torque_Nm"]
    load_rows = []
    for name in names[:2]:
        for joint, peak in enumerate(metrics[name]["peak_estimated_belt_transmitted_torque_Nm"]):
            if peak <= allowance[joint]:
                continue
            row = {"case": name, "joint": f"J{joint + 1}", "peak_estimated_torque_Nm": peak,
                   "service_allowance_Nm": allowance[joint], "corrected_catalog_capacity_Nm": raw[joint],
                   "catalog_capacity_to_peak_ratio": raw[joint] / peak,
                   "exceeds_service_allowance": True, "exceeds_catalog_screen": peak > raw[joint]}
            if name == "weak_spring_double_delay_3.2":
                row.update({"peak_time_s": exact["peak_events"][joint]["time_s"],
                            "total_time_over_allowance_ms": exact["above_allowance_total_s"][joint] * 1000,
                            "total_time_over_catalog_screen_ms": exact["above_raw_capacity_total_s"][joint] * 1000,
                            "events_over_allowance": exact["above_allowance_events"][joint]})
            else:
                repeat = read(D / "power_loss_3.2-baseline-2400-summary.json")
                row["separate_diagnostic_repeat"] = {"timestep_s": 1 / 2400,
                    "note": "Original XML timestep is 0.000416666666667 s. This initial diagnostic used exact 1/2400 s; the contact peak changes modestly. The frozen suite peak above remains authoritative.",
                    "peak_torque_Nm": repeat["peak_estimated_belt_torque_Nm"][joint],
                    "peak_time_s": repeat["peak_events"][joint]["time_s"],
                    "time_over_allowance_ms": repeat["above_allowance_total_s"][joint] * 1000,
                    "time_over_catalog_screen_ms": repeat["above_raw_capacity_total_s"][joint] * 1000}
            load_rows.append(row)

    late = read(R / "results" / "weak_spring_double_delay_7.2.json")
    above = [f for f in late["frames"] if f[0] >= 7.2 and max(abs(x) for x in f[7:13]) > .002]
    last_time = max(f[0] for f in above)
    next_frame = next(f for f in late["frames"] if f[0] > last_time)
    settling = {"case": names[2], "required_maximum_speed_rad_s": .002,
                "required_settled_after_fault_s": .5,
                "measured_maximum_speed_after_deadline_rad_s": metrics[names[2]]["max_speed_after_fault_plus_0p5s_rad_s"],
                "joint_with_residual_motion": "J4",
                "last_saved_state_exceeding_threshold_s": last_time,
                "next_saved_state_all_joints_below_threshold_s": next_frame[0],
                "approximate_time_to_settle_s": [last_time - 7.2, next_frame[0] - 7.2],
                "maximum_J4_fault_travel_deg": metrics[names[2]]["max_fault_travel_deg"][3],
                "final_joint_speed_rad_s": late["frames"][-1][7:13],
                "interpretation": "The brake eventually stops the arm, but the unchanged 0.5 s acceptance deadline is missed. No settling tolerance was relaxed."}

    appendix_paths = [
        "power_loss_3.2-baseline-rate0.7-2400-summary.json",
        "weak_spring_double_delay_3.2-baseline-rate0.7-2400-summary.json",
        "weak_spring_double_delay_7.2-baseline-rate0.7-2400-summary.json",
        "weak_spring_double_delay_3.2-baseline-rate0.4-2400-summary.json",
        "stationary_placement_power_loss-baseline-rate1-2400-summary.json",
    ]
    appendix = []
    for name in appendix_paths:
        d = read(D / name)
        appendix.append({"file": "diagnostics/brake-events/" + name,
                         "sha256": sha(D / name), "case": d["case"], "reference_rate": d["reference_rate"],
                         "cycle_duration_if_adopted_s": 10 / d["reference_rate"],
                         "physical_fault_time_s": d["physical_fault_time_s"],
                         "peak_estimated_belt_torque_Nm": d["peak_estimated_belt_torque_Nm"],
                         "time_over_allowance_ms": [x * 1000 for x in d["above_allowance_total_s"]],
                         "time_over_catalog_screen_ms": [x * 1000 for x in d["above_raw_capacity_total_s"]],
                         "max_speed_after_fault_plus_half_second_rad_s": max(d["max_speed_after_fault_plus_half_second_rad_s"]),
                         "adopted": False})
    summary = read(R / "reports" / "P5-dynamics-summary.json")
    conclusion = (
        "Retain the exact frozen 10 s nominal design as an engineering prototype. "
        "21 of 24 configured ordinary scenarios pass; all four deliberate failure controls produce their expected consequences. "
        "Two moving-descent power-loss cases fail the belt service allowance, including a combined weak-spring/doubled-delay case that exceeds the raw catalog screen. "
        "A third weak-spring/doubled-delay case stops after the specified settling deadline. "
        "The original controller, brakes, acceptance thresholds, geometry and nominal trace remain unchanged. "
        "Fail-safe payload retention, fixture clearance and engineered impact compliance require a separate hardware design and qualification; this model does not establish emergency-safe operation."
    )
    report = {"revision": "P5", "date_utc": datetime.now(timezone.utc).isoformat(),
              "status": "Nominal operation verified; three adverse-case criteria remain failed",
              "frozen_model_provenance": provenance, "nominal_trace_sha256": nominal_sha,
              "ordinary_scenarios_passed": 21, "ordinary_scenario_count": 24,
              "negative_controls_pass": summary["negative_control_outcomes_pass"],
              "conclusion": conclusion,
              "failed_scenarios": [{"name": m["name"], "failed_checks": [c for c in m["checks"] if not c["passed"]]} for m in metrics.values()],
              "belt_load_comparison": load_rows, "settling_failure": settling,
              "load_estimation": {"formula": "T_belt_est = T_motor_output - J_upstream_equivalent * (qvel_after - qvel_before) / dt",
                    "meaning": "The belt carries upstream rotor inertia during a stop even though the full output-brake holding torque does not flow through the belt.",
                    "limits": "Rigid lumped transmission, compliant numerical contact, and finite brake delay/ramp assumptions. No explicit belt tooth elasticity, skip, breakage or calibrated impact impulse rating. Millisecond overload duration is not permission to exceed the catalog screen. Post-overload simulated motion is not a prediction that real hardware remains intact."},
              "cause": {"sequence": ["Power loss removes arm and gripper electrical torque.",
                   "The independent puck drops toward the placement nest while finite brake engagement allows further arm descent.",
                   "The puck contacts the nest and the descending gripper front wall/motor-clamp proxies.",
                   "Contact force changes link velocity rapidly and loads the belt through upstream drive inertia."],
                   "exact_weak_case_event_time_s": exact["peak_events"][2]["time_s"],
                   "exact_weak_case_contact_records": exact["peak_events"][2]["contacts"],
                   "no_structural_link_overlap": metrics[names[1]]["max_unintended_proxy_penetration_m"] == 0,
                   "structural_check_scope": "The structural-link check excludes the independent puck. Zero link overlap does not imply no puck/fixture/gripper impact.",
                   "brake_model": p["integration"]["brakes"],
                   "brake_switching_note": "The existing speed-based dynamic/holding transition is abrupt at 0.01 rad/s. It is not the sole cause: the overload coincides with resolved puck/fixture/gripper contact and persists at half the timestep. No smoother or weaker brake law was adopted."},
              "timestep_refinement": {"original_exact_summary": str(exact_path.relative_to(R)),
                  "original_summary_sha256": sha(exact_path), "refined_summary": str(refined_path.relative_to(R)),
                  "refined_summary_sha256": sha(refined_path), "refined_timestep_s": refined["dt_s"],
                  "refined_peaks_Nm": refined["peak_estimated_belt_torque_Nm"],
                  "refined_time_above_catalog_screen_ms": [x * 1000 for x in refined["above_raw_capacity_total_s"]],
                  "interpretation": "The numerical impact peak is timestep sensitive; both resolutions flag raw-capacity exceedance at J3 and J5. This establishes the model limitation, not a precise hardware impact load."},
              "diagnostic_appendix": appendix,
              "rejected_slowdown_decision": "70% and 40% reference-rate candidates were tested only in isolated in-memory controller variants with fault times moved to the same trajectory phase. The 40% candidate would make a 25 s cycle yet still exceeds J4 service allowance. Neither candidate was adopted, and neither received an all-phase acceptance claim.",
              "stationary_diagnostic_scope": "A separate power loss during stationary placement at 3.6 s, with weaker springs and doubled brake delay, passes the assessed belt/settling criteria. It completed before a stop request arrived. Thus the evidence does not prove impact unavoidable for every placement pose or every possible retiming.",
              "negative_control_outcomes": summary["negative_control_outcomes"],
              "catalog_source": read(R / "reports" / "belt-selection-source.json"),
              "retained_failed_suite": "diagnostics/freeze2-original-brake",
              "reproduction": ["node integration/validate_p5.mjs", "python3 integration/analyze_p5_results.py",
                  "node integration/diagnose_p5_brakes.mjs weak_spring_double_delay_3.2",
                  "ARX_BRAKE_DIAG_HZ=4800 node integration/diagnose_p5_brakes.mjs weak_spring_double_delay_3.2",
                  "ARX_BRAKE_DIAG_REFERENCE_RATE=0.7 node integration/diagnose_p5_brakes.mjs weak_spring_double_delay_3.2",
                  "ARX_BRAKE_DIAG_REFERENCE_RATE=0.4 node integration/diagnose_p5_brakes.mjs weak_spring_double_delay_3.2",
                  "python3 integration/write_p5_fault_review.py"],
              "expected_validation_exit_status": "Nonzero: the three ordinary failures remain unresolved. Do not reclassify them as deliberate negative controls."}
    (R / "reports" / "P5-fault-review.json").write_text(json.dumps(report, indent=2) + "\n")
    table = "\n".join(f"| {x['case']} | {x['joint']} | {x['peak_estimated_torque_Nm']:.3f} | {x['service_allowance_Nm']:.3f} | {x['corrected_catalog_capacity_Nm']:.4f} | {x['catalog_capacity_to_peak_ratio']:.3f} |" for x in load_rows)
    doc = f"""# P5 adverse-case review

**Status: 21 of 24 ordinary scenarios pass. Three adverse-case criteria remain failed.** The 10 s nominal pick-and-place cycle, 30 s repeat, both nominal timestep comparisons and all four deliberate failure controls have the expected outcomes. The supplied geometry and nominal motion are retained as an engineering prototype; this is not an emergency-safe hardware release.

## Frozen design and decision

{conclusion}

Nominal trace SHA256: `{nominal_sha}`. Model SHA256: `{provenance['xml_sha256']}`. The exact frozen controller and parameter hashes are recorded in the companion JSON. The rejected experiments did not modify these files.

## Belt-load failures

The screening estimate is `T_belt = T_motor_output − J_upstream × angular_acceleration`. An output-side brake does not transmit its entire holding rating through the belt, but the belt still accelerates or decelerates the upstream motor/reducer/pulley inertia. The check includes that load.

| Fault case | Joint | Estimated peak, Nm | Allowance at SF 1.5, Nm | Corrected raw catalog screen, Nm | Capacity / peak |
|---|---|---:|---:|---:|---:|
{table}

The 3.2 s ordinary power-loss case exceeds the J4 service allowance while remaining below the raw catalog screen. Its initial high-rate diagnostic, using exact `1/2400 s` rather than the XML's rounded timestep, records one 0.417 ms exceedance at about 3.292 s and a 3.408 Nm peak. The frozen suite's authoritative peak is 3.184 Nm. This difference is retained rather than hidden.

For the combined 10% weaker spring / doubled brake delay case, the exact XML-timestep repeat reproduces the frozen peaks exactly. All three listed peaks occur at **3.267917 s**, about 67.9 ms after power loss. J2 exceeds its service allowance for **0.417 ms**; J3 for **1.250 ms**, including **0.833 ms above the raw catalog screen**; J5 for **2.500 ms**, including **2.083 ms above the raw catalog screen**. These durations are integration-step measurements. The handbook does not provide permission to dismiss them as harmless impulse overloads.

At 4800 Hz, the same combined fault still exceeds raw capacity: J3 reaches **26.814 Nm** and J5 **8.402 Nm**. Their time above the raw screen remains about **0.833 ms** and **2.083 ms**. The precise peak is contact/timestep sensitive; the failure persists. The solver has no belt breakage or tooth-skip state, so later simulated settling must not be read as evidence that physical hardware survives an overload.

## Physical event in the model

Power loss removes electrical torque from the arm and the gripper. The puck remains a free body, so it can fall toward the placement nest while the arm continues descending during brake engagement. In the failed case it contacts the nest and then the descending gripper front-wall and motor-clamp material proxies. That contact rapidly changes link velocity and loads upstream rotor inertia through the belt.

No link-to-link structural penetration is recorded in these two fault cases. That result excludes the independent puck and therefore does not imply the absence of a payload/fixture/gripper impact. The companion JSON records the exact contact pairs, penetration and native solver contact forces at the weak-case peak. These are model contact forces, not calibrated hardware impact measurements.

The existing brake model retains the original finite delays and ramps, 60%-of-holding dynamic torque assumption, and full static holding rating. It switches between dynamic and holding capacity at 0.01 rad/s. A smoother transition or lower dynamic torque was considered, but no brake-law adjustment was adopted: the resolved contact event and half-timestep repeat establish a physical load path that cannot be dismissed as a switching artifact.

## Settling failure

With 10% weaker springs and doubled brake delay, power loss at **7.2 s** leaves J4 moving at **0.1533 rad/s** in the window that begins 0.5 s after the fault. The criterion is **0.002 rad/s**. J4 travels **11.885°** before settling. The saved trace last exceeds the threshold at **7.7667 s** and is below it by **7.7750 s**, so the sampled settling time is approximately **0.567–0.575 s**. The arm eventually stops; the configured deadline is still missed. No deadline or velocity threshold was relaxed.

## Rejected slowdown appendix

The fault trigger was moved to the same trajectory phase when testing slower references. A 70% global reference rate places the original 3.2 s fault at 4.5714 s, and a 40% rate places it at 8.0 s. These tests change only isolated in-memory controller variants; they do not replace the delivered source or trace.

At 70% speed, nominal power loss at the placement phase and the original late-settling phase pass the assessed criteria, but the combined weak/delayed descent still overloads J3, J4 and J5. At 40% speed, the cycle would last 25 s and the combined descent still reaches **3.593 Nm at J4** for **0.833 ms above service allowance**, although it remains below raw capacity. Both slowdowns were rejected because neither resolves the stated criteria. No broad phase-coverage acceptance is claimed for them.

A separate combined weak/delayed fault during stationary placement at 3.6 s passes the assessed belt and settling criteria. This bounds the conclusion: the current moving-descent trajectory and two tested slowdowns fail; the data do not prove collision unavoidable for every possible retiming or stationary placement pose.

## Controls and qualification scope

The deliberate failure controls remain effective. Reducing friction produces **78.159 mm** placement error; weakening the grip produces **251.205 mm**; removing both counterbalances produces **204.441 mm** and a software-limit trip. Removing power without brakes produces **30.307°** maximum joint travel, compared with **6.834°** for the corresponding braked emergency case. Lower RMS current after the no-spring safety trip is not interpreted as reduced drive burden. The severe no-spring case also exceeds the rigid transmission's load screen, so its post-overload motion has the same breakage-model limitation.

Fail-safe payload retention, adequate fixture/gripper clearance and engineered impact compliance or energy absorption need a separate hardware design and qualification. A larger belt alone would not establish payload safety. No unverified belt-width multiplier, higher brake torque or allowable impact rating was introduced. Supplier brake switching/dynamic torque, belt pretension and compliance, contact friction, spring hooks, tolerances and physical impact loads remain qualification inputs.

The manufacturer source is [SDP/SI, Timing Belts Technical Section](https://sdp-si.com/D820/PDFS/Technical-Section.pdf), Table 38 on printed T-78 for the large belt and Table 37 on printed T-76 for the small belt. The supplied `belt-selection-source.json` records the exact width and length factors. These are catalog selection screens, not certified reversal/impact capacity for this assembly.

## Reproduction and retained evidence

`validate_p5.mjs` and `analyze_p5_results.py` deliberately return a nonzero status while these three ordinary failures remain. The original complete failed suite is preserved under `diagnostics/freeze2-original-brake`. Integration-step event logs and rejected controller variants are under `diagnostics/brake-events`. `P5-fault-review.json` gives hashes, load comparisons, source metadata and exact reproduction commands. The nominal source hashes remain unchanged.
"""
    (R / "reports" / "P5-fault-review.md").write_text(doc)
    print(json.dumps({"report": "reports/P5-fault-review.json", "status": report["status"],
                      "nominal_trace_sha256": nominal_sha, "preserved_inputs": True}, indent=2))


if __name__ == "__main__":
    main()
