#!/usr/bin/env python3
"""Build the compact P5 dynamics model from the regenerated mechanical outputs.

Uses the previously verified P2 contact topology, replacing every explicitly
revised collision proxy and every moving CAD mass tensor. This build refuses to
run without the P5 collision record; it never reuses a P2 trajectory as P5 data.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

R = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt(values) -> str:
    return " ".join(f"{float(x):.13g}" for x in values)


def main() -> None:
    spec = json.loads((R / "spec.json").read_text())
    props = json.loads((R / "mass_properties.json").read_text())
    proxy_path = R / "p5_collision_proxies.json"
    if not proxy_path.exists():
        raise RuntimeError("The compact CAD collision record is not ready")
    pdata = json.loads(proxy_path.read_text())
    records = pdata if isinstance(pdata, list) else pdata["records"]
    config = {} if isinstance(pdata, list) else pdata
    root = ET.fromstring((R / "P2-baseline.xml").read_text())
    root.set("model", "ARX6_P5_compact_belt_drives")
    bodies = {b.get("name"): b for b in root.findall(".//body")}
    checks = []

    for name in ("turret", "upper", "fore", "roll", "bend", "tool"):
        p = props[name]
        tensor = np.asarray(p["inertia_tensor_kg_m2"], float)
        eigenvalues = np.linalg.eigvalsh(tensor)
        if min(eigenvalues) <= 0 or eigenvalues[-1] > sum(eigenvalues[:2]) + 1e-10:
            raise RuntimeError(f"Nonphysical CAD inertia tensor for {name}")
        inertial = bodies[name].find("inertial")
        inertial.set("pos", fmt(p["com_m"]))
        inertial.set("mass", f"{p['mass_kg']:.15g}")
        inertial.set("fullinertia", fmt(p["fullinertia_mujoco_kg_m2"]))
        for key in ("diaginertia", "quat"):
            inertial.attrib.pop(key, None)
        checks.append({"name": name + " CAD inertia positive and realizable", "passed": True,
                       "mass_kg": p["mass_kg"], "eigenvalues_kg_m2": eigenvalues.tolist()})

    # Preserve separately derived jaw inertias where supplied. The original
    # opposition constraint and independent workpiece remain unchanged.
    for name in ("jaw_left", "jaw_right"):
        if name in props:
            p = props[name]
            inertial = bodies[name].find("inertial")
            inertial.set("mass", f"{p['mass_kg']:.15g}")
            inertial.set("pos", fmt(p["com_m"]))
            inertial.set("fullinertia", fmt(p["fullinertia_mujoco_kg_m2"]))

    for index in range(6):
        joint = root.find(f".//joint[@name='j{index + 1}']")
        joint.set("range", fmt(spec["joint_hard_limits_rad"][index]))

    # A proxy record describes material outside the real component's holes;
    # large cavity-filling hulls must not be used for rotating shaft interfaces.
    prefixes = config.get("replace_prefixes", ["package_", "P2_fixed_clevis", "P2_moving_clevis",
        "P2_elbow_anchor_", "P2_elbow_moving_anchor"])
    exact = set(config.get("replace_names", []))
    removed = []
    for container in [root.find("worldbody"), *bodies.values()]:
        for geom in list(container.findall("geom")):
            name = geom.get("name", "")
            if name in exact or any(name.startswith(p) for p in prefixes):
                removed.append(name)
                container.remove(geom)

    added = []
    for row in records:
        name = row["name"]
        body = row.get("body", row.get("parent_body"))
        container = bodies["fixed_hardware"] if body == "fixed" else bodies.get(body)
        if body in ("world", "worldbody"):
            container = root.find("worldbody")
        if container is None:
            raise ValueError(f"Unknown body {body!r} for collision record {name!r}")
        kind = row["type"]
        attrs = {"name": name, "type": kind, "rgba": ".42 .46 .49 1"}
        if kind == "box":
            attrs["pos"] = fmt(np.asarray(row["center_mm"]) * .001)
            attrs["size"] = fmt(np.asarray(row["half_size_mm"]) * .001)
            if "quat_wxyz" in row:
                attrs["quat"] = fmt(row["quat_wxyz"])
        elif kind in ("cylinder", "capsule"):
            attrs["fromto"] = fmt(np.asarray(row["fromto_mm"]).ravel() * .001)
            attrs["size"] = fmt([row["radius_mm"] * .001])
        elif kind == "sphere":
            attrs["pos"] = fmt(np.asarray(row["center_mm"]) * .001)
            attrs["size"] = fmt([row["radius_mm"] * .001])
        else:
            raise ValueError(f"Unsupported collision primitive {kind}")
        ET.SubElement(container, "geom", **attrs)
        added.append(name)

    # The folded J1 drive passes through a real second bench opening. An
    # infinite tabletop would incorrectly fill both holes. Tile the material
    # around the two round openings with 1 mm strips whose aperture lies inside
    # the true circle, so this proxy never removes extra bench material.
    tabletop = config.get("tabletop", {
        "thickness_mm": 40., "top_y_mm": 0., "extent_xz_mm": [1000., 1000.],
        "holes": [{"center_xz_mm": [0., 0.], "radius_mm": 55.},
                  {"center_xz_mm": [110., 0.], "radius_mm": 23.}]})
    world = root.find("worldbody")
    old_floor = world.find("geom[@name='floor']")
    if old_floor is not None:
        world.remove(old_floor)
    hx, hz = tabletop["extent_xz_mm"]
    top, thick = tabletop["top_y_mm"], tabletop["thickness_mm"]
    holes = sorted(tabletop["holes"], key=lambda h: h["center_xz_mm"][0])
    tiles = []

    def table_box(x0, x1, z0, z1):
        if x1 - x0 < 1e-8 or z1 - z0 < 1e-8:
            return
        name = "floor" if not tiles else f"P5_table_material_{len(tiles):03d}"
        center = [(x0 + x1) / 2, top - thick / 2, (z0 + z1) / 2]
        half = [(x1 - x0) / 2, thick / 2, (z1 - z0) / 2]
        ET.SubElement(world, "geom", name=name, type="box", pos=fmt(np.array(center) * .001),
                      size=fmt(np.array(half) * .001), rgba=".16 .17 .18 1")
        tiles.append({"name": name, "center_mm": center, "half_size_mm": half})

    left = -hx
    for hole in holes:
        cx, cz = hole["center_xz_mm"]
        radius = hole["radius_mm"]
        if cx - radius < left - 1e-8:
            raise ValueError("Table tiling requires separated circular openings")
        table_box(left, cx - radius, -hz, hz)
        edges = np.linspace(cx - radius, cx + radius, int(np.ceil(2 * radius)) + 1)
        for x0, x1 in zip(edges[:-1], edges[1:]):
            x = max(abs(x0 - cx), abs(x1 - cx))
            opening_half_z = float(np.sqrt(max(0., radius * radius - x * x)))
            table_box(x0, x1, -hz, cz - opening_half_z)
            table_box(x0, x1, cz + opening_half_z, hz)
        left = cx + radius
    table_box(left, hx, -hz, hz)
    tabletop["collision_approximation"] = "At most 1 mm wide strips; aperture lies within each native circular opening, conservatively retaining bench material."
    tabletop["collision_tile_count"] = len(tiles)

    # Explicit narrow contact exclusions require their geometric rationale in
    # the emitted CAD record. No automatic adjacent-body exclusion is added.
    contact = root.find("contact")
    if contact is None:
        contact = ET.SubElement(root, "contact")
    inherited_exclusions_removed = []
    for item in list(contact.findall("exclude")):
        if {item.get("body1"), item.get("body2")} == {"fixed_hardware", "turret"}:
            inherited_exclusions_removed.append(dict(item.attrib))
            contact.remove(item)
    exclusions = config.get("body_exclusions", [])
    for row in exclusions:
        if not row.get("reason"):
            raise ValueError("A contact exclusion requires its geometric rationale")
        ET.SubElement(contact, "exclude", body1=row["body1"], body2=row["body2"])

    p = json.loads((R / "P2-baseline-parameters.json").read_text())
    p["integration"] = spec
    p["model_revision"] = "P5"
    p["status"] = "Compact folded-belt engineering prototype with regenerated CAD inertias and collision proxies"
    p["bodies"] = {name: {key: value[key] for key in ("mass_kg", "com_m", "fullinertia_mujoco_kg_m2")}
                   for name, value in props.items()}
    p["cad_mass_properties_sha256"] = sha(R / "mass_properties.json")
    p["collision_proxy_sha256"] = sha(proxy_path)
    p["mechanical_source_sha256"] = {name: sha(R / name) for name in (
        "generate_cad_p2.py", "spec.json", "mass_properties.json", "p5_collision_proxies.json",
        "packaging_envelopes.json", "geometry-meshes.json", "folded-transmissions.json")}
    p["collision_packages"] = json.loads((R / "packaging_envelopes.json").read_text())
    p["collision_boxes"] = records
    p["tabletop_fixture"] = tabletop
    p["geometry_revision_note"] = "P5 uses six folded 1:1 belt stages, full original motor/reducer envelopes, revised counterbalances, real two-bore bench fixture, CAD-derived moving tensors and corrected J3/J5 upper stops. Retained linkage geometry: " + p["geometry_revision_note"]
    p["controller"]["ki_Nm_rad_s"][1:3] = [80., 60.]
    transmission = spec.get("folded_transmission", {})
    efficiencies = transmission.get("efficiency_screening", .97)
    if isinstance(efficiencies, (float, int)):
        efficiencies = [efficiencies] * 6
    p["motors"]["gear_efficiency"] = [e * b for e, b in zip(p["motors"]["gear_efficiency"], efficiencies)]
    extra_armature = config.get("joint_extra_armature_kg_m2", transmission.get("joint_extra_armature_kg_m2", [0.] * 6))
    if len(extra_armature) != 6 or min(extra_armature) < 0:
        raise ValueError("Six nonnegative transmission inertia additions are required")
    for index, additional in enumerate(extra_armature):
        joint = root.find(f".//joint[@name='j{index + 1}']")
        joint.set("armature", f"{float(joint.get('armature', '0')) + additional:.15g}")
    p["motors"]["extra_transmission_inertia_kg_m2"] = extra_armature
    # Manufacturer handbook base ratings, width and length corrections recorded
    # by the mechanical/source review. These are screening limits, not a claim
    # that tension, tooth contact or fatigue has been experimentally qualified.
    belt_ratings = [19.1984] * 3 + [3.7422] * 3
    service_factor = 1.5
    p["motors"]["belt_screen_capacity_Nm"] = belt_ratings
    p["motors"]["belt_service_factor"] = service_factor
    p["motors"]["belt_allowable_output_torque_Nm"] = [v / service_factor for v in belt_ratings]
    p["belt_rating_screen"] = {
        "source": "https://sdp-si.com/D820/PDFS/Technical-Section.pdf",
        "large": {"profile": "5M", "teeth": 36, "width_mm": 25, "length_mm": 400,
                  "center_distance_mm": 110, "base_torque_Nm": 7.1,
                  "width_factor": 3.38, "length_factor": .8, "table": "38, printed T-78"},
        "small": {"profile": "3M", "teeth": 30, "width_mm": 15, "length_mm": 225,
                  "center_distance_mm": 67.5, "base_torque_Nm": 1.4,
                  "width_factor": 2.97, "length_factor": .9, "table": "37, printed T-76"},
        "service_factor": service_factor,
        "implementation": "Torque demand limited by both gearhead and corrected belt capacity/service factor. Actual electromechanical torque is checked independently; no artificial output-position locking.",
        "limitations": "No compliant tooth or belt-slip simulation. Rating application, belt tension, supplier geometry, shafts and fatigue remain physical qualification items. Direct-output brakes do not transmit their holding torque through this belt stage."
    }
    p["assumptions"]["inertia"] = "P5 native CAD mass and full tensors; supplier motor/reducer/brake envelope masses retained; explicit cable/fastener allowances and spring allocation. Both revised belt paths and relocated drive components included."
    p["assumptions"]["gear_efficiency"] += " P5 adds a stated 0.97 belt-stage efficiency screening assumption; actual belt losses, tension and tooth loading require measurement."
    p["assumptions"]["collision"] = config.get("scope", "Revised explicit compact component proxies; preserved independent puck and jaw contact. Flexible belt, spring and cable contact are not simulated.")
    p["assumptions"]["rotating_inertia"] += " Added input pulley, input shaft, keys and translating-belt equivalent inertias identified by the P5 CAD record. The diagonal armature model does not resolve individual spinning-body gyroscopic coupling."

    # Detect any accidental object welding or actuation before writing.
    puck = bodies["puck"]
    if puck.find("freejoint") is None and puck.find("joint[@type='free']") is None:
        raise RuntimeError("The workpiece must remain a free body")
    equality = root.find("equality")
    if equality is not None:
        for item in equality:
            if item.tag == "weld" and "puck" in item.attrib.values():
                raise RuntimeError("A workpiece attachment is not allowed")
    checks.append({"name": "independent workpiece free-body topology preserved", "passed": True})
    ET.indent(root)
    xml = ET.tostring(root, encoding="unicode") + "\n"
    (R / "ARX-6-P5.xml").write_text(xml)
    (R / "parameters.json").write_text(json.dumps(p, indent=2) + "\n")
    report = {"revision": "P5", "xml_sha256": sha(R / "ARX-6-P5.xml"),
              "cad_mass_properties_sha256": p["cad_mass_properties_sha256"],
              "collision_proxy_sha256": p["collision_proxy_sha256"],
              "rigid_body_mass_kg": {k: v["mass_kg"] for k, v in props.items()},
              "removed_collision_proxies": removed, "new_collision_proxies": added,
              "body_exclusions": exclusions, "additional_armature_kg_m2": extra_armature,
              "removed_inherited_exclusions": inherited_exclusions_removed,
              "tabletop_fixture": tabletop,
              "gearbox_and_belt_efficiency": p["motors"]["gear_efficiency"], "checks": checks,
              "scope": p["assumptions"]["collision"],
              "brakes": "Unchanged finite-capacity friction constraints with delayed torque buildup; no position locks"}
    (R / "reports" / "P5-model-provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"model": "P5", "moving_mass_kg": sum(props[x]["mass_kg"] for x in ("turret", "upper", "fore", "roll", "bend", "tool")),
                      "collision_geoms": len(root.findall('.//geom')), "new_proxies": len(added)}))


if __name__ == "__main__":
    main()
