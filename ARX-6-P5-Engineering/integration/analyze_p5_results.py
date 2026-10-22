#!/usr/bin/env python3
"""Reduce real P5 trajectories into explicit, auditable physical-model evidence."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parent


def load(name):
    return json.loads((R / "results" / (name + ".json")).read_text())


def filehash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nearest(frames, time):
    return min(frames, key=lambda f: abs(f[0] - time))


def main():
    nominal = load("nominal")
    p = json.loads((R / "parameters.json").read_text())
    if p.get("model_revision") != "P5":
        raise RuntimeError("Only fresh P5 results may be summarized")
    wanted = {"xml_sha256": filehash(R / "ARX-6-P5.xml"),
              "controller_sha256": filehash(R / "controller.mjs"),
              "safety_sha256": filehash(R / "safety.mjs"),
              "parameters_sha256": filehash(R / "parameters.json"),
              "geometry_sha256": filehash(R / "geometry-meshes.json"),
              "collision_proxies_sha256": filehash(R / "p5_collision_proxies.json"),
              "cad_mass_properties_sha256": filehash(R / "mass_properties.json")}
    scenarios = []
    for path in sorted((R / "results").glob("*-metrics.json")):
        m = json.loads(path.read_text())
        if all(m.get("provenance", {}).get(k) == v for k, v in wanted.items()):
            scenarios.append(m)
    if nominal["metrics"]["provenance"] != wanted:
        raise RuntimeError("Nominal trace does not correspond to the current P5 model")
    required = {"nominal", "nominal_30s", "dt1200", "dt4800", "weak_spring", "no_counterbalance",
                "normal_stop", "watchdog", "estop", "invalid_feedback", "power_loss_no_brakes",
                "friction_loss", "weak_grip", "brake_torque_40pct"}
    required.update(f"power_loss_{t:.1f}" for t in [.6, 1.2, 1.9, 2.2, 2.6, 3.2, 6.2, 7.2])
    required.update(f"weak_spring_double_delay_{t:.1f}" for t in [1.2, 1.9, 2.2, 2.6, 3.2, 7.2])
    missing = required - {m["name"] for m in scenarios}
    if missing:
        raise RuntimeError("The current P5 model still needs scenarios: " + ", ".join(sorted(missing)))
    deliberate = {"no_counterbalance", "power_loss_no_brakes", "friction_loss", "weak_grip"}
    regular = [m for m in scenarios if m["name"] not in deliberate]
    controls = [m for m in scenarios if m["name"] in deliberate]
    by_name = {m["name"]: m for m in scenarios}
    control_checks = []
    for name in ("friction_loss", "weak_grip"):
        error = by_name[name]["placement_B_error_m"]
        control_checks.append({"name": name + " independently simulated payload fails the transfer",
                               "passed": error > .010, "placement_B_error_mm": error * 1000,
                               "minimum_visible_failure_mm": 10.})
    no_spring = by_name["no_counterbalance"]
    control_checks.append({"name": "removing both springs materially increases drive burden or loses placement",
                           "passed": no_spring["placement_B_error_m"] > .010 or
                           no_spring["rms_current_A"][1] > 1.25 * nominal["metrics"]["rms_current_A"][1],
                           "placement_B_error_mm": no_spring["placement_B_error_m"] * 1000,
                           "shoulder_rms_current_ratio": no_spring["rms_current_A"][1] / nominal["metrics"]["rms_current_A"][1]})
    braked_travel = max(by_name["estop"]["max_fault_travel_deg"])
    unbraked_travel = max(by_name["power_loss_no_brakes"]["max_fault_travel_deg"])
    control_checks.append({"name": "power removal without brakes causes substantially larger free motion",
                           "passed": unbraked_travel > max(5., 3 * braked_travel),
                           "unbraked_maximum_travel_deg": unbraked_travel,
                           "braked_emergency_maximum_travel_deg": braked_travel,
                           "comparison": "Both failures begin at 2.0 s of the same nominal motion; unbraked travel bounds are intentionally unenforced."})

    differences = []
    base = np.asarray(nominal["frames"])
    for name in ("dt1200", "dt4800"):
        other = np.asarray(load(name)["frames"])
        if len(base) != len(other) or np.max(abs(base[:, 0] - other[:, 0])) > 1e-8:
            raise RuntimeError("Time-step comparison must use matching physical timestamps")
        differences.append({"case": name,
                            "max_joint_difference_deg": float(np.max(abs(base[:, 1:7] - other[:, 1:7])) * 180 / np.pi),
                            "max_payload_position_difference_mm": float(np.max(np.linalg.norm(base[:, 15:18] - other[:, 15:18], axis=1)) * 1000),
                            "final_payload_difference_mm": float(np.linalg.norm(base[-1, 15:18] - other[-1, 15:18]) * 1000),
                            "interpretation": "Numerical sensitivity of a contact simulation; a small placement error does not prove exact path identity."})

    transfers = []
    long_trace = load("nominal_30s")
    for index in range(6):
        time = 4.9 + 5 * index
        destination = "B" if index % 2 == 0 else "A"
        f = nearest(long_trace["frames"], time)
        error = np.linalg.norm(np.array(f[15:18]) - p["workpiece_targets_m"][destination]) * 1000
        transfers.append({"transfer": index + 1, "sample_time_s": f[0], "destination": destination,
                          "placement_error_mm": float(error), "within_1p5_mm": bool(error < 1.5)})

    spring_report = json.loads((R / "reports" / "P5-spring-energy-check.json").read_text()) if (R / "reports" / "P5-spring-energy-check.json").exists() else None
    if not spring_report or spring_report.get("spec_sha256") != filehash(R / "spec.json") or spring_report.get("safety_sha256") != wanted["safety_sha256"]:
        raise RuntimeError("Spring report must be regenerated for the current specification and force law")
    failed_regular = [m for m in regular if not m["all_checks_pass"]]
    fault_review_path = R / "reports" / "P5-fault-review.json"
    fault_review = json.loads(fault_review_path.read_text()) if fault_review_path.exists() else None
    if fault_review and fault_review.get("frozen_model_provenance") != wanted:
        raise RuntimeError("Fault review does not correspond to the current frozen model")
    report = {"revision": "P5", "date_utc": datetime.now(timezone.utc).isoformat(), "provenance": wanted,
              "nominal_trace_sha256": filehash(R / "results" / "nominal.json"),
              "overall_status": "Nominal operation verified; adverse-case envelope incomplete" if failed_regular else "All configured ordinary scenarios pass",
              "all_ordinary_scenarios_pass": not failed_regular,
              "unresolved_ordinary_cases": [m["name"] for m in failed_regular],
              "fault_review_file": "P5-fault-review.json" if fault_review else None,
              "fault_review_conclusion": fault_review.get("conclusion") if fault_review else None,
              "ordinary_scenarios": [{"name": m["name"], "passes": m["all_checks_pass"],
                                       "failed_checks": [c for c in m["checks"] if not c["passed"]]} for m in regular],
              "ordinary_scenario_count": len(regular), "ordinary_scenario_passes": sum(m["all_checks_pass"] for m in regular),
              "controls_and_sensitivities": [{"name": m["name"], "ordinary_checks_pass": m["all_checks_pass"],
                                             "placement_B_error_mm": m["placement_B_error_m"] * 1000,
                                             "maximum_fault_joint_travel_deg": max(m["max_fault_travel_deg"]),
                                             "failed_checks": [c for c in m["checks"] if not c["passed"]]} for m in controls],
              "negative_control_outcomes": control_checks,
              "negative_control_outcomes_pass": all(c["passed"] for c in control_checks),
              "six_transfers": transfers,
              "all_six_transfers_within_1p5_mm": all(x["within_1p5_mm"] for x in transfers),
              "timestep_sensitivity": differences,
              "nominal_rms_current_A": nominal["metrics"]["rms_current_A"],
              "continuous_current_ratings_A": p["motors"]["continuous_current_A"],
              "nominal_peak_motor_current_A": nominal["metrics"]["peak_current_A"],
              "nominal_peak_output_torque_Nm": nominal["metrics"]["peak_output_torque_Nm"],
              "nominal_peak_estimated_belt_transmitted_torque_Nm": nominal["metrics"]["peak_estimated_belt_transmitted_torque_Nm"],
              "belt_corrected_screen_capacity_Nm": p["motors"]["belt_screen_capacity_Nm"],
              "belt_service_allowance_Nm": p["motors"]["belt_allowable_output_torque_Nm"],
              "nominal_belt_capacity_to_peak_load_ratio": [rating / max(motor, delivered) for rating, motor, delivered in zip(p["motors"]["belt_screen_capacity_Nm"], nominal["metrics"]["peak_output_torque_Nm"], nominal["metrics"]["peak_estimated_belt_transmitted_torque_Nm"])],
              "belt_load_ratio_basis": "Corrected catalog capacity divided by the larger of motor-generated peak and upstream-inertia-adjusted transmitted peak for each joint; required ratio 1.5.",
              "nominal_peak_pulley_speed_rpm": [speed / ratio * 60 / (2 * np.pi) for speed, ratio in zip(nominal["metrics"]["peak_motor_speed_rad_s"], p["motors"]["gear_ratio"])],
              "nominal_voltage_saturation_s": nominal["metrics"]["voltage_saturation_s"],
              "nominal_max_structural_proxy_penetration_mm": nominal["metrics"]["max_unintended_proxy_penetration_m"] * 1000,
              "nominal_trajectory_samples": len(nominal["frames"]),
              "spring_energy_gradient_check": spring_report,
              "scope": "Engineering prototype: nominal operation and revised CAD are computationally verified, but three configured adverse cases remain failed. Power loss disables gripper torque and can allow the puck to contact its nest and the descending gripper; two such cases exceed the belt service screen, and a combined weak-spring/delayed-brake case misses the 0.5 s settling requirement. Fail-safe payload retention and engineered impact compliance require a separate hardware design and qualification. Contact friction, belt compliance/tension, supplier interfaces, fatigue, tolerances, electrical safety and physical accuracy require hardware qualification. Inspection animation is not a replacement for this solver."}
    (R / "reports" / "P5-dynamics-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"ordinary_scenarios": len(regular), "passed": sum(m["all_checks_pass"] for m in regular),
                      "six_placement_errors_mm": [x["placement_error_mm"] for x in transfers],
                      "negative_controls_pass": all(c["passed"] for c in control_checks),
                      "timestep_sensitivity": differences}, indent=2))
    if not all(c["passed"] for c in control_checks):
        raise RuntimeError("At least one deliberate physical failure control did not produce its expected consequence")
    if not all(x["within_1p5_mm"] for x in transfers):
        raise RuntimeError("At least one of the six consecutive placements exceeds 1.5 mm")
    if not all(m["all_checks_pass"] for m in regular):
        raise RuntimeError("Ordinary scenarios failed: " + ", ".join(m["name"] for m in regular if not m["all_checks_pass"]))


if __name__ == "__main__":
    main()
