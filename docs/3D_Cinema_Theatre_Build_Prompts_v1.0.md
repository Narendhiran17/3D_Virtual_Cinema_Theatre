# 3D Cinema Theatre --- Build Prompt Pack v1.0

**Purpose:** Build photorealistic, production-oriented cinema
auditoriums and the 3D assets required for interactive seat selection in
the Multi-Cinema Platform.

**Architecture alignment:** Architecture Baseline v1.0. This document
covers 3D creation and asset delivery only. It does not change the
platform architecture or implement booking/payment logic.

## How to use

1.  Use the Master Prompt to create the overall auditorium.
2.  Use the focused prompts below to build or refine individual
    components.
3.  Supply real floor plans, measurements, seat schedules and reference
    photos wherever possible.
4.  Validate the Blender scene, exported GLB, seat metadata and actual
    web viewer.
5.  Obtain cinema-operator approval before marking a real auditorium
    production-ready.

**Critical rule:** Never invent real seat counts, row labels, seat IDs,
aisle locations, accessible spaces or dimensions. Use clearly labelled
placeholders where source information is missing. A realistic-looking
model is not necessarily an accurate auditorium.

------------------------------------------------------------------------

## 1. Master prompt --- complete auditorium

Copy the prompt below into your 3D AI assistant or Blender MCP agent.

``` text
Act as a senior architectural visualization artist, Blender technical artist,
cinema auditorium designer and real-time 3D environment engineer.

Build a photorealistic, production-oriented 3D movie theatre auditorium for an
interactive cinema seat-selection application.

PURPOSE
A customer must be able to understand the auditorium, identify the screen,
rows, aisles and seats, orbit and zoom around the space, focus on a seat, and
preview the approximate view from that seat.

SOURCE OF TRUTH
Use supplied measurements, floor plans, reference photos, approved seat
schedule and layout metadata. Do not fabricate real-world dimensions or seat
positions. If information is missing, use clearly labelled placeholders and
list every assumption in the build report.

BUILD THESE COMPONENTS
1. Auditorium shell: floor, side/rear walls, ceiling, acoustic panels and columns.
2. Screen area: screen surface, frame, masking and supplied speaker positions.
3. Seating: seat models, row groupings, seat anchors and stable seat mapping.
4. Circulation: aisles, steps, ramps, handrails, entrances and exits.
5. Safety/accessibility: signs, emergency lights and operator-confirmed
   accessible spaces and companion seats.
6. Lighting: aisle, step, wall and ceiling lights; controlled screen illumination.
7. Decoration: approved wall finishes, trims, acoustic treatment and signage.
8. Helpers: screen centre/corners, auditorium origin, seat anchors and cameras.

VISUAL TARGET
Create a premium contemporary cinema with believable proportions, physically
plausible materials, dark low-reflectance finishes, comfortable upholstered
seats, subtle warm aisle lighting and a readable screen. Do not add decoration
that hides seats or interferes with interaction.

BLENDER ORGANIZATION
Create collections:
AUDITORIUM_ROOT
  ARCHITECTURE
  SCREEN_AND_STAGE
  SEATING
  AISLES_AND_ACCESS
  LIGHTING
  SIGNAGE
  INTERACTION_HELPERS
  CAMERAS
  QA_HELPERS

Use clear names such as AUD_FLOOR, AUD_WALL_LEFT, SCREEN_MAIN, ROW_A,
SEAT_A_001, AISLE_LEFT, CAM_OVERVIEW and HELPER_SCREEN_CENTER.

REAL-TIME REQUIREMENTS
- Target a Three.js / React Three Fiber web viewer.
- Use real-world scale and document the unit and coordinate conventions.
- Apply transforms before export; use clean topology and sensible polygon counts.
- Reuse materials and geometry. Instance repeated seats where practical.
- Keep static architecture separate from interactive seat geometry.
- Every bookable seat must map to a permanent seat_id.
- Never use Blender object indices or GLB export order as seat identity.
- Keep screen references, seat anchors and camera targets explicit.
- Avoid duplicate meshes, unused geometry and unnecessarily heavy textures.

SEAT METADATA
For each seat provide seat_id, row_label, seat_number, seat_type, position,
rotation, layout_version and a visual mesh/instance reference. Include
accessibility attributes only when supplied and verified.

The 3D model does not own booking state. The application controls:
AVAILABLE, SELECTED_LOCAL, HELD_BY_CURRENT_SESSION, HELD_BY_OTHER,
CONFIRMED, BLOCKED and ACCESSIBLE_AVAILABLE.

CAMERAS
Create overview, orbit, screen-centred and seat-focus/seat-view camera helpers.
Aim seat-view cameras toward the screen reference point. Mark views as
approximate if screen, eye-height or obstruction measurements are unavailable.

DELIVERABLES
1. Editable Blender .blend source.
2. Optimized .glb export.
3. Separate seat/layout metadata JSON.
4. Asset manifest with version, units and coordinate convention.
5. Preview renders: overview, screen-facing, rear-to-screen and seat detail.
6. Build report: assumptions, missing inputs, validation and limitations.

VALIDATION
Verify dimensions, row count, seat count, row labels, unique seat IDs, seat
anchor alignment, aisles, exits, accessible positions, transforms, normals,
materials and GLB export. Test loading, seat picking, highlighting, camera
navigation and performance in the target web viewer on desktop and mobile.

Do not build backend booking, payment or seat-lock logic. Return the created
files and a concise validation report.
```

## 2. Auditorium shell prompt

``` text
Build the architectural shell of the supplied cinema auditorium in Blender.
Treat the supplied floor plan and dimensions as authoritative.

Create floor, side walls, rear wall, ceiling, acoustic panels, columns, screen
wall, entrance/exit openings, aisle openings and any supplied ramps or stairs.
Use real-world scale and document the origin.

Keep all shell geometry in the ARCHITECTURE collection. Do not create seats yet.

Add helpers for auditorium origin, floor plane, screen centre/corners, front
row boundary, rear wall boundary, aisle centre lines and entrance/exit points.

Do not guess missing dimensions. Mark unknowns as placeholders and list them
in the report. Deliver the .blend source and a dimension/assumption report.
```

## 3. Screen and stage prompt

``` text
Build the cinema screen and front presentation area from supplied specifications.
Include screen surface, frame, masking, front-wall treatment and speaker
positions. Add a stage/platform only if it exists in the reference design.

Create explicit helpers:
SCREEN_CENTER, SCREEN_TOP_LEFT, SCREEN_TOP_RIGHT,
SCREEN_BOTTOM_LEFT, SCREEN_BOTTOM_RIGHT.

The screen must be a stable reference for seat-view cameras. Keep screen
geometry separate from the auditorium shell. Do not add copyrighted posters,
film artwork or logos unless supplied and licensed.
```

## 4. Cinema seat model prompt

``` text
Create a realistic cinema seat asset designed for repeated use in a large
auditorium and interactive seat selection.

Include upholstered backrest and cushion, seat base/support, armrests, seams
and realistic metal/polymer details. Add a cup holder only if it exists in
the reference seat.

Create a high-quality master asset and an optimized real-time variant if
needed. Apply transforms and set the origin consistently at the floor contact
point. Create variants only when required by the approved seat schedule:
standard, recliner, premium, accessible companion or operator-defined types.

Keep availability, booking state, price and seat identity out of the mesh
materials. The application will control seat-state appearance.

Deliver .blend, optimized .glb, dimensions, pivot definition and material list.
```

## 5. Seating rows and seat-ID mapping prompt

``` text
Place seats using the approved auditorium layout and seat schedule. Preserve
exact row labels, seat numbers, seat spacing, row spacing, rotations, aisle
gaps, offsets and seat types. Do not add or remove seats to improve symmetry.

Every seat must have a stable seat_id, row_label, seat_number, seat_type,
world position, world rotation, layout_version and visual mesh/instance
reference.

If IDs are not supplied, propose deterministic IDs using an agreed convention
and return the mapping for operator approval before production use.

Generate a JSON mapping. Check for duplicate IDs, missing seats, unexpected
seats and seat-anchor alignment. Instancing is allowed only if every instance
can still be mapped reliably to its seat_id. Never depend on object indices
or export order for identity.
```

## 6. Aisles, safety and accessibility prompt

``` text
Build only the circulation and safety elements shown in the approved plan:
aisles, steps, handrails, ramps, entrance/exit doors, aisle lighting, step
lighting, exit signs and wheelchair spaces.

Follow supplied drawings and requirements confirmed by the cinema operator
and relevant authorities. Do not claim legal, fire-safety or accessibility
compliance based only on the 3D model.

Keep these elements separate for review. Create helpers for entrance points,
exit points, aisle boundaries and operator-confirmed accessible positions.
Report missing or conflicting source information.
```

## 7. Materials and lighting prompt

``` text
Create a coherent physically based material and lighting setup for a premium
cinema auditorium. Use suitable acoustic fabric, carpet/floor finish, wall
panels, upholstered seat fabric, metal/polymer components and screen material.

Create subtle aisle and step lighting, restrained wall lighting and controlled
screen illumination. The auditorium should feel dark while seat geometry
remains readable in the interactive viewer.

Provide two targets: a photorealistic approval/marketing render and a performant
real-time web version. Avoid excessive transparent layers, costly real-time
lights, heavy shader graphs and unnecessary texture resolution.

Deliver a material inventory and state which effects are baked, real-time or
omitted in the web version.
```

## 8. Seat-view camera prompt

``` text
Create camera helpers and navigation targets for overview, orbit, pan, zoom,
seat focus, approximate first-person seat view and reset-to-overview.

For each seat, create an eye-position helper using the approved eye-height
rule and aim toward SCREEN_CENTER. Keep helpers separate from visible geometry
and export the data required by the web viewer.

Do not claim accurate sightlines, obstruction analysis or viewing-quality
scores unless screen dimensions, eye height, floor slope and obstruction
geometry have been measured and a calculation method is documented.
```

## 9. Custom real-cinema reconstruction prompt

``` text
Reconstruct this real cinema from the supplied photos, measurements, floor
plans and seat schedule.

Before modelling, produce a reference analysis:
- identify each reference view and likely camera position;
- list known dimensions and dimensions measurable from drawings;
- list unknown dimensions and conflicting references;
- identify missing seat schedule or accessibility information.

Ask for clarification rather than silently guessing. Then model the verified
auditorium, matching seat count, row labels, seat numbers, aisles, screen,
entrances, exits, ramps and approved accessible spaces.

Use clearly labelled placeholders for unresolved areas. Return a discrepancy
list for cinema-operator approval. Do not mark the reconstruction production-
ready until the geometry and seat schedule are approved.
```

## 10. Reusable auditorium template prompt

``` text
Create a reusable parametric cinema auditorium template in Blender.

Expose editable parameters for auditorium width/length/height, screen size and
position, row count, seats per row, seat spacing, row spacing, row curvature,
aisle positions/widths, floor slope, seat type and entrance/exit positions.

Generate geometry and seat metadata from the same approved parameter set.
Changing dimensions must regenerate the layout while preserving stable IDs
for seats that remain logically the same.

Keep this as a generic template. Do not represent it as a real cinema until
the operator approves the geometry and seat schedule.
```

## 11. Optimization and GLB export prompt

``` text
Prepare the approved auditorium for a browser-based Three.js viewer.

1. Apply transforms and verify scale.
2. Remove hidden, duplicate and unused geometry.
3. Reuse materials and mesh data.
4. Instance repeated seats where possible without losing seat-ID mapping.
5. Create LOD variants if profiling shows they are needed.
6. Optimize textures; use KTX2 where supported by the app pipeline.
7. Use Meshopt or Draco only after testing target-viewer compatibility.
8. Separate static architecture from interactive seat geometry.
9. Export GLB and validate the exported file, not only the Blender scene.
10. Test load, picking, highlighting, camera controls and GPU-resource cleanup.

Deliver .blend, .glb, seat/layout JSON, asset manifest, export settings,
before/after file sizes and validation report. Do not sacrifice seat identity,
geometry correctness or picking accuracy for file-size reduction.
```

## 12. Seat-state appearance prompt for the application developer

``` text
Implement application-controlled visual states for each seat:

AVAILABLE: neutral and selectable.
SELECTED_LOCAL: selected locally; not yet reserved.
HELD_BY_CURRENT_SESSION: temporary hold confirmed by backend.
HELD_BY_OTHER: unavailable to this customer.
CONFIRMED: booked and unavailable.
BLOCKED: disabled by cinema operator.
ACCESSIBLE_AVAILABLE: accessible seat available, with a distinction that is
not colour-only.

Use accessible contrast and do not communicate state by colour alone. Provide
labels/tooltips and a linked 2D seat map. Correctly apply backend updates after
WebSocket events, reconnects and failed hold attempts.

A local click is not a successful reservation. The backend remains authoritative.
Do not encode dynamic seat status into the exported GLB.
```

## 13. Layout metadata example

Illustrative schema only. Replace all example values with approved
cinema data.

``` json
{
  "schema_version": "1.0",
  "auditorium_id": "APPROVED_AUDITORIUM_ID",
  "layout_version": 1,
  "units": "meters",
  "coordinate_system": {
    "up_axis": "Y",
    "forward_axis": "-Z",
    "origin": "auditorium_floor_reference"
  },
  "screen": {
    "center": [0.0, 4.0, -12.0],
    "width": 12.0,
    "height": 5.0
  },
  "seats": [
    {
      "seat_id": "A-001",
      "row_label": "A",
      "seat_number": 1,
      "seat_type": "STANDARD",
      "position": [-3.0, 0.0, -8.0],
      "rotation": [0.0, 0.0, 0.0],
      "mesh_reference": "SEAT_INSTANCE_GROUP_01"
    }
  ]
}
```

The numbers and seat ID above are examples, not real auditorium
measurements. Choose the production coordinate convention once and keep
it consistent across Blender, GLB, metadata and the web viewer.

## 14. Final acceptance checklist

### Geometry and appearance

-   [ ] Dimensions match approved references.
-   [ ] Screen, shell, seating, aisles and circulation are present.
-   [ ] Seat model and materials match approved references.
-   [ ] Lighting is readable in both render and real-time modes.
-   [ ] No unapproved invented features remain.

### Seat data

-   [ ] Every bookable physical seat appears exactly once.
-   [ ] Every seat has a unique stable seat_id.
-   [ ] Row labels, seat numbers and types match the approved schedule.
-   [ ] Seat anchors align with visible geometry.
-   [ ] Accessibility data is verified, not inferred.

### Runtime

-   [ ] GLB loads in the target web viewer.
-   [ ] Seat picking maps to the correct seat_id.
-   [ ] Seat highlighting and state updates work.
-   [ ] Camera controls work on desktop and touch devices.
-   [ ] 2D fallback remains available.

### Delivery

-   [ ] Editable .blend source.
-   [ ] Optimized .glb.
-   [ ] Seat/layout metadata JSON.
-   [ ] Asset manifest and version.
-   [ ] Preview renders.
-   [ ] Validation and assumptions report.
-   [ ] Cinema-operator approval recorded.

**Definition of done:** A model is not production-ready merely because
it looks realistic. Geometry, seat schedule, stable IDs, metadata,
export and application picking must all pass review.
