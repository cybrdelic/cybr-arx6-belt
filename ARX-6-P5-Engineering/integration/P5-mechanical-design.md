# ARX-6 P5 — compact mechanical design record

**Status: executable engineering prototype with native CAD and tested nominal motion.** The six revolute arm axes and opposed rack gripper remain. The new design replaces the long inline motor/reducer/coupling stacks with real folded parallel-axis transmissions. Native motor and reducer envelope dimensions are retained; the geometry is not scaled for presentation. Supplier interfaces, fatigue, pretension, impact strength and production tolerances remain unqualified.

**Known unresolved hardware limitation: emergency payload/fixture impacts.** The frozen 10 second nominal motion passes its checks, but the final validation suite passes 21 of 24 ordinary scenarios. Two descent power-loss cases exceed the selected belt service allowance, and one combined weak-spring/delayed-brake case fails the settling criterion. These failures remain in the delivered evidence; the nominal drive torque limit does not bound an external impact transmitted through the belts.

| Scenario | Failed criterion in the frozen model | Implication |
| --- | --- | --- |
| Power loss at 3.2 s | J4 estimated belt torque 3.1842 N·m exceeds the 2.4948 N·m service allowance; raw catalog screen is 3.7422 N·m | The intended 1.5 load factor is not retained during this emergency event. |
| Weak springs and doubled brake delay, power loss at 3.2 s | J3 estimated belt torque 32.1921 N·m and J5 6.9939 N·m exceed their raw screens of 19.1984 and 3.7422 N·m | Potential transmission overload after payload/fixture contact remains unresolved. |
| Weak springs and doubled brake delay, power loss at 7.2 s | Residual joint speed 0.153292 rad/s exceeds the 0.002 rad/s settling criterion | This adverse stop does not meet the declared settling requirement. |

The torque reconstruction uses motor-generated output torque minus the upstream equivalent rotary inertia times angular acceleration in an ideal rigid transmission. It identifies a design limitation, rather than certifying tooth-impact strength. Source, thresholds, nominal timing, belt dimensions and brake ratings were kept unchanged after the investigation. See `reports/P5-dynamics-summary.json` and the final fault review for the scenario evidence. This CAD is not released for unattended physical operation.

## Actual geometry changes

Each joint now has an offset motor/reducer, two keyed toothed pulleys, a closed finite-tooth belt, a slotted carrier deck, a perimeter enclosure with inspection openings, a front cover, an additional outboard input bearing, an input shaft and explicit mounting hardware. The existing output bearing support and output-side brake remain. Joint-specific output shafts have independently clocked pulley key seats while retaining the brake key datum. These key seats were checked against the actual keys and pulley bores in native BREP.

The folded directions are chosen per joint. J3 folds back along the upper arm. J5 is clocked 90° to place its motor on the opposite side of the wrist space from the J4 drive. The shoulder and elbow counterbalance anchor brackets are moved inward; the former elbow mast beyond the elbow joint is removed. The CAD, body mass tensors, collision proxies and rendering geometry all come from the revised source.

| Joint | Clock about native positive shaft axis | Native axis in parent frame | Input centre offset before axis mapping, mm |
| --- | --- | --- | --- |
| J1 | -90.000000° | [0, 1, 0] | [110.0, 0.0, 0.0] |
| J2 | 137.014114° | [0, 0, 1] | [-75.0, -80.4674, 0.0] |
| J3 | 0.000000° | [0, 0, -1] | [-0.0, 110.0, 0.0] |
| J4 | 0.000000° | [0, 1, 0] | [-0.0, 67.5, 0.0] |
| J5 | 90.000000° | [0, 0, 1] | [-67.5, 0.0, 0.0] |
| J6 | 0.000000° | [0, 1, 0] | [-0.0, 67.5, 0.0] |

## Compactness and the real tradeoffs

Axial coordinates below are measured from each joint’s declared CAD origin along its positive native shaft axis. Negative values lie behind the joint. The comparison includes the actual drive assembly geometry, rather than only a visible motor cylinder.

| Drive family | P2 axial range, mm | P5 axial range, mm | Rear projection reduction | Total axial span reduction |
| --- | --- | --- | --- | --- |
| J1–J3 | −305.1 to +18.0 | −152.5 to +22.1 | 50.016% | 45.961% |
| J4–J6 | −207.6 to +16.0 | −109.5 to +17.6 | 47.254% | 43.157% |

At the elbow, the declared joint origin is upper-frame (0, 280, +45) mm and its native axis is −Z. The positive-Z outer limit therefore changes from +350.1 mm to +197.5 mm. This is an actual shape change. Folding increases transverse footprint, and the load-bearing carriers, belt components and extra support bearings add moving mass.

The complete native BREP bounds below use the same q=0 construction reference for both revisions. That reference is useful for dimension comparison; it is not an asserted allowed operating pose. It includes the canonical jaw and excludes flexible spring geometry, the bench, cables and payload.

| Revision | X min/max, mm | Y min/max, mm | Z min/max, mm | X×Y×Z span, mm |
| --- | --- | --- | --- | --- |
| P2 | -110.000 / 95.000 | -245.100 / 916.000 | -350.100 / 350.100 | 205.000 × 1161.100 × 700.200 |
| P5 | -111.148 / 205.000 | -92.500 / 916.000 | -197.500 / 197.500 | 316.148 × 1008.500 × 395.000 |

The resulting reference depth is 395.0 mm versus 700.2 mm. The width increases to 316.148 mm from 205.0 mm, largely because the J1 foot now supports the folded input train. No global “smaller in every direction” claim is made.

## Transmission dimensions and load screening

| Parameter | Large joints J1–J3 | Small joints J4–J6 |
| --- | --- | --- |
| Pulley tooth count / pitch | 36 teeth / 5 mm | 30 teeth / 3 mm |
| Belt width | 25 mm | 15 mm |
| Closed belt pitch length / teeth | 400 mm / 80 teeth | 225 mm / 75 teeth |
| Nominal centre distance | 110 mm | 67.5 mm |
| Transmission ratio | 1:1 | 1:1 |
| Carrier adjustment range | ±2 mm | ±2 mm |
| Retained motor envelope | Ø40 × 56.1 mm | Ø22 × 48.6 mm |
| Retained reducer envelope | Ø42 × 70 mm | Ø22 × 39 mm |
| Output brake static rating | 22 N·m | 2.2 N·m |
| Screened belt capacity | 19.1984 N·m | 3.7422 N·m |
| Controller allowance with 1.5 factor | 12.798933 N·m | 2.4948 N·m |

The equal-pulley belt length relation is L = 2C + Np. Thus 2×110 + 36×5 = 400 mm and 2×67.5 + 30×3 = 225 mm. Each belt contains the corresponding explicit tooth count. The odd half-count of the small belt is handled by the input pulley’s native tooth phase.

The load screen uses the [SDP/SI Technical Section](https://sdp-si.com/D820/PDFS/Technical-Section.pdf), Table 38 (PDF page 80) for the large belt and Table 37 (PDF page 78) for the small belt. The large screen is 7.1×3.38×0.80 = 19.1984 N·m. The small screen is 1.4×2.97×0.90 = 3.7422 N·m. These are catalog-based screening values at the lowest tabulated speed, not a certification of the custom nominal tooth geometry, installed pretension or service life. The separate 0.97 belt efficiency is an explicit engineering assumption.

The CAD tooth section is a rounded nominal approximation with deliberate clearance. It does not claim a manufacturing-certified HTD cutter profile. The single modeled adjustment screw and slotted mount still require a measured pretension and locking procedure. The cover geometry has real bearing pockets and mating rails, while its final cover-to-rail screw pattern remains a release detail. The output brake acts directly on the output shaft and does not rely on belt tension to hold the joint.

## Compact counterbalance

The springs are tension-only Hookean elements between the actual CAD pin centres. The force is zero below free eye length; above it, each spring uses F = F_initial + k(L − L_free). The applied generalized torque is calculated from the moving lever geometry, not imposed as a constant counterweight torque. The detailed energy-gradient check is in `reports/P5-spring-energy-check.json`.

| Parameter | Shoulder pair | Elbow pair |
| --- | --- | --- |
| Fixed anchor in its parent body, mm | turret: (−65, 104, +60) | upper: (−30, 190, −55) |
| Moving anchor in its child body, mm | upper: (0, 70, +60) | fore: (0, −45, −55) |
| Second spring anchor Z, mm | +84 | −79 |
| Wire / mean coil diameter, mm | 2.8 / 18 | 1.8 / 15 |
| Active turns | 30 | 22 |
| Free eye length, mm | 104 | 62 |
| Stiffness per spring, N/m | 3469.208962 | 1396.145455 |
| Initial tension per spring, N | 84.250233 | 30.577846 |
| Reference restoring torque | −11 N·m at q2=0.20 rad | −6 N·m at q3=1.50 rad |

The shoulder moving anchor is 70 mm from the joint instead of 100 mm, and its fixed attachment shifts inward from X=−100 mm to X=−65 mm. The elbow fixed anchor moves from upper-frame Y=350 mm to Y=190 mm, below the 280 mm elbow datum. A short forearm back lever places its moving anchor at Y=−45 mm. The native brackets attach through actual drilled tube interfaces and separate nut strips; the revised forearm lever is attached to the negative wall rather than floating at the joint.

Wire geometry and density contribute to mass, with half of each spring’s mass assigned at each attachment in the rigid-body model. This is a stated flexible-body approximation. Hook stress, initial-tension manufacture, winding details and fatigue life require spring-supplier review. Native helix geometry alone does not establish durability.

## Mounting and service access

J1 has an extended 12 mm thick capsule foot spanning X=−95 to +205 mm and Z=±95 mm. The 40 mm bench requires two separate through-bores: Ø110 mm at (X,Z)=(0,0), and Ø46 mm at (+110,0). The carrier sits below the tabletop; the bores are real geometric openings. Six nominal M8 through-bolts, nuts and individual Ø28 mm backing washers are modeled. Individual washers replace the earlier underside annular plate so the new folded carrier has space. Bench strength and fastener preload remain assembly qualifications.

## Native fit and stop verification

`reports/P5-mechanical-validation.json` records 52 native BREP interface checks. All passed with zero intersection above the 0.00001 mm³ reporting tolerance. All 127 top-level component/body STEP exports imported as valid shapes. The source also exports 375 exact placed STEP shapes under `cad/placed/`, indexed by `placed-native-parts.json`.

| Native check | Measured nominal clearance |
| --- | --- |
| Large belt to drive/driven pulleys | 0.1500 mm minimum |
| Small belt to driven pulley | 0.1200 mm minimum |
| Small belt to input pulley | 0.09848 mm minimum |
| Large/small belt to carrier | 1.5 / 3.5 mm |
| Large/small belt to enclosure rails | 2.2 / 3.0 mm |
| Output shaft flange to front bearing cover | 0.3000 mm at all six joints |
| J1 reducer to mounting foot bore | 2.0000 mm |

Keys, keyed shafts, pulley bores, input-bearing pockets, the two real bench openings and the J1 foot were also checked. Zero-distance fitted bearing shoulders are intentional contact faces; a zero minimum distance is not automatically a collision.

Native review exposed inherited broad-range link clashes, so the physical stop pins were moved before freezing this revision. J3 now stops at 1.85 rad and J5 at 1.63 rad; software soft maxima are 1.83 and 1.61 rad. At the new upper stops, the elbow tubes retain 2.636860 mm clearance and the wrist fork/cradle retain 1.000000 mm minimum clearance. Exact exported dowels and steel targets touch at each limit, remain separated one milliradian before it, and geometrically engage one milliradian beyond it. The eight tests in `reports/P5-corrected-joint-stop-check.json` all pass. They establish nominal stop geometry; they do not rate pin impact energy or bracket strength.

The collision model uses 2,095 explicit material-region primitives. Annular surfaces are covered by overlapping conservative sectors, preserving their bores and avoiding gaps between strips. No new whole-body exclusions are used. These proxies support the fresh dynamic trajectory tests; native BREP refines small clearances. The validated task path does not imply that every simultaneous joint-limit combination clears the bench and fixtures. Motion planning must consider those objects.

## Regenerated mass and inertia

| Body | P2 mass, kg | P5 mass, kg | Change, kg |
| --- | --- | --- | --- |
| fixed | 4.633618 | 5.517044 | +0.883426 |
| turret | 4.257395 | 4.685441 | +0.428046 |
| upper | 4.479617 | 4.912427 | +0.432810 |
| fore | 1.897943 | 2.240645 | +0.342703 |
| roll | 0.974561 | 1.120335 | +0.145774 |
| bend | 0.959504 | 1.105279 | +0.145774 |
| tool | 0.310468 | 0.345699 | +0.035231 |
| jaw | 0.026274 | 0.026274 | -0.000000 |

Custom-part volume, centroid and full inertia tensors come from native BREP and the declared material densities. Full-size motor, reducer and brake envelopes retain their catalog masses, with stated engineering allocation for the brake armature. Vendor internal mass distribution is not measured. Cables/encoders/fasteners retain explicit mass reserves. Input-pulley, input-shaft and key spin inertia plus translating-belt equivalent inertia are added separately at the 1:1 joint output speed, avoiding omission of the new transmission’s moving inertia.

Each body’s inertia tensor is positive definite. The placed component mass list is `bom-p5-placed-records.csv`; mechanism roles and exact native names are in `mechanism-parts.json`. These records let the inspection film remove and rotate actual modeled parts while keeping supplier motor/reducer internals and bearing rolling elements explicitly outside the modeled scope.

## Rebuild and evidence

Use the supplied P5 rebuild entrypoint, rather than the preserved historical P2 modification scripts. The current mechanical sequence is:

```sh
python integration/generate_cad_p2.py
python integration/build_p5_collision_proxies.py
python integration/validate_p5_mechanics.py
python integration/validate_p5_joint_stops.py
# Run the P5 model/controller tests, then export the saved pose:
python integration/export_p5_assembly.py --time 2.5
```

The standalone baseline reference files required for dimensional and mass comparison are under `integration/baseline-reference/`. The overall named assembly exporter uses the final nominal trace, phases input shafts and actual belt teeth with the six physical joint angles, creates the handed lower jaw correctly, and rebuilds all four springs at their saved anchor distances. It excludes cinematic inspection offsets. Its imported STEP validity, part count, body pose and trace hash are recorded in `reports/P5-overall-assembly.json`.

Frozen generator SHA256: `0c8474173cc5ec70164cae5050a9aa7decbf6e30f14cb7f67564e9fbdaad58f7`. Frozen specification SHA256: `606e09b482d4c5f838ee49daced4b574f8260450dd350735e95422c2d666a8ac`.

This package demonstrates a concrete compact architecture and its nominal tested motion. Supplier drawing approval, cover fastener release, belt pretension, structural stress, spring fatigue, thermal qualification, wiring flex life and physical commissioning remain the work needed to convert it into a production machine.
