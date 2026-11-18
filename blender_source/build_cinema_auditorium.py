"""Build a photorealistic, production-oriented 3D Cinema Auditorium according to
3D Cinema Theatre - Build Prompt Pack v1.0.

Key deliverables:
1. Editable Master Blender source file (.blend)
2. Web-optimized real-time GLB export (.glb)
3. Normalized Seat & Layout Metadata JSON conforming to Section 13 schema
4. Asset Manifest JSON with SHA-256
5. Multi-camera high-resolution preview renders (Overview, Screen-facing, Seat D-08 preview)
"""

import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import bpy
import mathutils

WORKSPACE = Path(__file__).resolve().parent.parent
OUTPUT_DIR = WORKSPACE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clear_scene():
    """Wipe default and existing objects to start fresh."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam)
    for light in list(bpy.data.lights):
        bpy.data.lights.remove(light)
    for col in list(bpy.data.collections):
        if col.name != "Collection":
            bpy.data.collections.remove(col)


def get_or_create_collection(name: str, parent: bpy.types.Collection = None) -> bpy.types.Collection:
    """Retrieve or create collection under designated parent."""
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        if parent:
            parent.children.link(col)
        else:
            bpy.context.scene.collection.children.link(col)
    return col


def create_material(name: str, base_color, roughness=0.5, metallic=0.0, specular=0.5,
                    emission_color=None, emission_strength=0.0) -> bpy.types.Material:
    """Create a Principled BSDF material with specified physical properties."""
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = None
    for n in nodes:
        if n.type == "BSDF_PRINCIPLED":
            bsdf = n
            break
    if not bsdf:
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")

    # Base Color
    if "Base Color" in bsdf.inputs:
        col = tuple(base_color[:3]) + (1.0,) if len(base_color) == 3 else tuple(base_color)
        bsdf.inputs["Base Color"].default_value = col

    # Roughness
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = float(roughness)

    # Metallic
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = float(metallic)

    # Specular
    for spec_name in ["Specular IOR Level", "Specular"]:
        if spec_name in bsdf.inputs:
            bsdf.inputs[spec_name].default_value = float(specular)
            break

    # Emission
    if emission_color and emission_strength > 0:
        ec = tuple(emission_color[:3]) + (1.0,) if len(emission_color) == 3 else tuple(emission_color)
        for em_name in ["Emission Color", "Emission"]:
            if em_name in bsdf.inputs:
                bsdf.inputs[em_name].default_value = ec
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = float(emission_strength)

    return mat


def create_cinema_screen_material(name="Mat_Cinema_Screen") -> bpy.types.Material:
    """Create procedural cinema projection screen material with subtle warm white projector radiance."""
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_out.location = (400, 0)

    node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    node_bsdf.location = (100, 0)
    node_bsdf.inputs["Base Color"].default_value = (0.94, 0.94, 0.96, 1.0)
    node_bsdf.inputs["Roughness"].default_value = 0.22

    for em_name in ["Emission Color", "Emission"]:
        if em_name in node_bsdf.inputs:
            node_bsdf.inputs[em_name].default_value = (0.88, 0.91, 0.98, 1.0)
            break
    if "Emission Strength" in node_bsdf.inputs:
        node_bsdf.inputs["Emission Strength"].default_value = 1.05

    links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    return mat


def create_box(name: str, location, scale, collection: bpy.types.Collection, material=None,
               bevel_width=0.0, rotation_euler=(0, 0, 0)):
    """Helper to create a scaled box mesh with optional bevel and smooth shading."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = tuple(scale)
    obj.rotation_euler = tuple(rotation_euler)

    if bevel_width > 0:
        mod = obj.modifiers.new(name="Bevel", type="BEVEL")
        mod.width = bevel_width
        mod.segments = 2
        mod.limit_method = "ANGLE"

    # Smooth shading
    for poly in obj.data.polygons:
        poly.use_smooth = True

    if material:
        obj.data.materials.append(material)

    # Collection linking
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    for col in list(obj.users_collection):
        if col != collection:
            col.objects.unlink(obj)

    return obj


def create_helper_empty(name: str, location, collection: bpy.types.Collection, display_size=0.3):
    """Create a non-rendering transformation helper empty object for Three.js/R3F anchor targeting."""
    empty = bpy.data.objects.new(name, None)
    empty.location = tuple(location)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = display_size
    collection.objects.link(empty)
    return empty


def build_cinema():
    print("=" * 70)
    print(" STARTING 3D CINEMA THEATRE AUDITORIUM BUILD (PROMPT PACK v1.0)")
    print("=" * 70)

    clear_scene()

    # 1. Setup Collection Hierarchy
    root_col = get_or_create_collection("AUDITORIUM_ROOT")
    arch_col = get_or_create_collection("ARCHITECTURE", root_col)
    screen_col = get_or_create_collection("SCREEN_AND_STAGE", root_col)
    seating_col = get_or_create_collection("SEATING", root_col)
    aisles_col = get_or_create_collection("AISLES_AND_ACCESS", root_col)
    lighting_col = get_or_create_collection("LIGHTING", root_col)
    signage_col = get_or_create_collection("SIGNAGE", root_col)
    helpers_col = get_or_create_collection("INTERACTION_HELPERS", root_col)
    cameras_col = get_or_create_collection("CAMERAS", root_col)
    qa_col = get_or_create_collection("QA_HELPERS", root_col)

    # 2. Setup Physically-Based Cinema Materials
    # Acoustic walls: dark matte charcoal fabric
    mat_wall = create_material("Mat_Acoustic_Wall", [0.05, 0.05, 0.06], roughness=0.88, specular=0.2)
    # Acoustic feature panels: dark navy / midnight blue acoustic weave
    mat_panel = create_material("Mat_Acoustic_Panel", [0.03, 0.05, 0.10], roughness=0.82, specular=0.25)
    # Floor carpet: dark charcoal plush theater carpet with subtle warm undertone
    mat_carpet = create_material("Mat_Cinema_Carpet", [0.04, 0.04, 0.048], roughness=0.92, specular=0.15)
    # Ceiling: dark suspended acoustic baffle
    mat_ceiling = create_material("Mat_Ceiling_Baffle", [0.02, 0.02, 0.025], roughness=0.90, specular=0.1)
    # Screen projection surface: matte high-gain cinema screen
    mat_screen = create_cinema_screen_material("Mat_Cinema_Screen")
    # Screen masking: light-absorbing ultra-deep velvet black frame
    mat_masking = create_material("Mat_Screen_Masking", [0.01, 0.01, 0.01], roughness=0.98, specular=0.04)
    # Standard seat upholstery: rich burgundy velvet fabric
    mat_seat_burgundy = create_material("Mat_Seat_Burgundy", [0.42, 0.035, 0.065], roughness=0.62, specular=0.5)
    # VIP / Recliner upholstery: premium midnight navy leather
    mat_seat_vip = create_material("Mat_Seat_VIP", [0.02, 0.05, 0.12], roughness=0.36, specular=0.58)
    # Accessible seat upholstery: rich burgundy with subtle accessibility accent
    mat_seat_accessible = create_material("Mat_Seat_Accessible", [0.38, 0.04, 0.08], roughness=0.65, specular=0.45)
    # Seat metal & polymer: dark matte durable plastic/metal
    mat_seat_polymer = create_material("Mat_Seat_Polymer", [0.03, 0.03, 0.035], roughness=0.40, specular=0.5)
    # Aisle Step LED strip: warm amber low-glare glow
    mat_step_led = create_material("Mat_Step_LED", [1.0, 0.74, 0.28], roughness=0.2,
                                   emission_color=[1.0, 0.74, 0.28], emission_strength=5.0)
    # Wall Sconce fixture material: brushed brass trim
    mat_sconce_fixture = create_material("Mat_Sconce_Fixture", [0.65, 0.52, 0.24], roughness=0.3, metallic=0.85, specular=0.8)
    # Exit sign: illuminated safety green
    mat_exit_sign = create_material("Mat_Exit_Sign", [0.1, 0.85, 0.25], roughness=0.3,
                                    emission_color=[0.1, 0.85, 0.25], emission_strength=5.5)
    # Handrail: brushed gunmetal
    mat_handrail = create_material("Mat_Handrail_Metal", [0.18, 0.18, 0.20], roughness=0.22, metallic=0.92, specular=0.7)

    # 3. Build ARCHITECTURE (Shell, Walls, Ceiling, Tiers)
    print("[1/6] Building Auditorium Architecture Shell...")
    aud_width = 16.0
    aud_length = 22.0  # from Y = -3.0 to Y = 19.0
    aud_height = 7.5

    # Base Floor
    create_box("AUD_FLOOR", [0.0, 7.5, -0.05], [aud_width, 25.0, 0.1], arch_col, mat_carpet)

    # Left & Right Walls
    create_box("AUD_WALL_LEFT", [-aud_width / 2.0 - 0.1, 7.5, aud_height / 2.0], [0.2, 25.0, aud_height], arch_col, mat_wall)
    create_box("AUD_WALL_RIGHT", [aud_width / 2.0 + 0.1, 7.5, aud_height / 2.0], [0.2, 25.0, aud_height], arch_col, mat_wall)

    # Rear & Front (Screen) Walls
    create_box("AUD_WALL_REAR", [0.0, 19.1, aud_height / 2.0], [aud_width + 0.4, 0.2, aud_height], arch_col, mat_wall)
    create_box("AUD_WALL_SCREEN", [0.0, -3.1, aud_height / 2.0], [aud_width + 0.4, 0.2, aud_height], arch_col, mat_masking)

    # Ceiling with acoustic absorption
    create_box("AUD_CEILING", [0.0, 7.5, aud_height + 0.05], [aud_width, 25.0, 0.1], arch_col, mat_ceiling)

    # Acoustic feature panels on Left and Right walls
    for p_idx in range(6):
        y_pos = 1.0 + p_idx * 3.0
        # Left wall panel
        create_box(f"AUD_ACOUSTIC_PANEL_L_{p_idx+1:02d}", [-aud_width / 2.0 + 0.08, y_pos, 3.8],
                   [0.12, 2.2, 4.8], arch_col, mat_panel, bevel_width=0.03)
        # Right wall panel
        create_box(f"AUD_ACOUSTIC_PANEL_R_{p_idx+1:02d}", [aud_width / 2.0 - 0.08, y_pos, 3.8],
                   [0.12, 2.2, 4.8], arch_col, mat_panel, bevel_width=0.03)

    # Tiered Stadium Seating Risers (Rows A to G)
    # Row pitch: 1.20m, Step rise: 0.38m per row
    rows_data = [
        ("A", 4.0, 0.38),
        ("B", 5.2, 0.76),
        ("C", 6.4, 1.14),
        ("D", 7.6, 1.52),
        ("E", 8.8, 1.90),
        ("F", 10.0, 2.28),
        ("G", 11.2, 2.66),
    ]

    tier_col = get_or_create_collection("AUD_TIERS", arch_col)
    for row_lbl, y_center, z_height in rows_data:
        t_name = f"AUD_TIER_{row_lbl}"
        # Tier platform spanning full seating bank width
        create_box(t_name, [0.0, y_center, z_height / 2.0], [aud_width - 1.2, 1.20, z_height], tier_col, mat_carpet, bevel_width=0.01)

    # Rear Concourse / Cross Aisle Platform
    create_box("AUD_REAR_CONCOURSE", [0.0, 14.5, 2.66 / 2.0], [aud_width - 1.2, 5.4, 2.66], arch_col, mat_carpet)

    # 4. Build SCREEN_AND_STAGE
    print("[2/6] Building Screen, Frame, Stage, and Sound System...")
    # Front stage platform
    create_box("STAGE_MAIN", [0.0, -1.0, 0.225], [15.0, 2.8, 0.45], screen_col, mat_carpet, bevel_width=0.02)

    # CinemaScope 2.39:1 Screen Surface
    screen_w = 13.5
    screen_h = 5.65
    screen_z = 3.95
    screen_y = -2.3

    # Screen surface mesh
    create_box("SCREEN_MAIN", [0.0, screen_y, screen_z], [screen_w, 0.02, screen_h], screen_col, mat_screen)

    # Black Velvet Masking Outer Frame (True 4-sided beveled border surround)
    border_w = 0.35
    frame_d = 0.10
    create_box("SCREEN_FRAME_TOP", [0.0, screen_y + 0.02, screen_z + screen_h / 2.0 + border_w / 2.0],
               [screen_w + border_w * 2, frame_d, border_w], screen_col, mat_masking, bevel_width=0.02)
    create_box("SCREEN_FRAME_BOTTOM", [0.0, screen_y + 0.02, screen_z - screen_h / 2.0 - border_w / 2.0],
               [screen_w + border_w * 2, frame_d, border_w], screen_col, mat_masking, bevel_width=0.02)
    create_box("SCREEN_FRAME_LEFT", [-screen_w / 2.0 - border_w / 2.0, screen_y + 0.02, screen_z],
               [border_w, frame_d, screen_h], screen_col, mat_masking, bevel_width=0.02)
    create_box("SCREEN_FRAME_RIGHT", [screen_w / 2.0 + border_w / 2.0, screen_y + 0.02, screen_z],
               [border_w, frame_d, screen_h], screen_col, mat_masking, bevel_width=0.02)

    # Stage LCR Speakers (Concealed behind perforated screen / baffle wall per cinema spec)
    create_box("SPEAKER_LEFT", [-5.5, screen_y - 0.4, 3.8], [0.8, 0.5, 1.4], screen_col, mat_masking)
    create_box("SPEAKER_CENTER", [0.0, screen_y - 0.4, 3.8], [1.0, 0.5, 1.2], screen_col, mat_masking)
    create_box("SPEAKER_RIGHT", [5.5, screen_y - 0.4, 3.8], [0.8, 0.5, 1.4], screen_col, mat_masking)

    # 5. Build AISLES_AND_ACCESS
    print("[3/6] Building Aisles, Handrails, and Safety Features...")
    # Stepped Aisle Blocks along Left Aisle (X=-2.6) and Right Aisle (X=+2.6)
    for row_lbl, y_center, z_height in rows_data:
        y_front = y_center - 0.58
        create_box(f"STEP_LED_{row_lbl}_L", [-2.6, y_front, z_height], [1.0, 0.04, 0.025], aisles_col, mat_step_led)
        create_box(f"STEP_LED_{row_lbl}_R", [2.6, y_front, z_height], [1.0, 0.04, 0.025], aisles_col, mat_step_led)

    # Safety Barrier Rail in front of Row A
    create_box("BARRIER_RAIL_ROW_A", [0.0, 3.35, 0.45], [aud_width - 3.0, 0.05, 0.90], aisles_col, mat_handrail)

    # Wall Handrails along circulation ramps
    create_box("HANDRAIL_LEFT_WALL", [-aud_width / 2.0 + 0.25, 7.8, 1.8], [0.06, 9.5, 0.9], aisles_col, mat_handrail)
    create_box("HANDRAIL_RIGHT_WALL", [aud_width / 2.0 - 0.25, 7.8, 1.8], [0.06, 9.5, 0.9], aisles_col, mat_handrail)

    # Rear Exit Doors
    create_box("DOOR_REAR_LEFT", [-5.5, 18.95, 2.66 + 1.2], [1.4, 0.08, 2.4], aisles_col, mat_wall)
    create_box("DOOR_REAR_RIGHT", [5.5, 18.95, 2.66 + 1.2], [1.4, 0.08, 2.4], aisles_col, mat_wall)

    # Illuminated EXIT Signs above doors
    create_box("EXIT_SIGN_LEFT", [-5.5, 18.9, 2.66 + 2.6], [0.8, 0.05, 0.3], signage_col, mat_exit_sign)
    create_box("EXIT_SIGN_RIGHT", [5.5, 18.9, 2.66 + 2.6], [0.8, 0.05, 0.3], signage_col, mat_exit_sign)

    # 6. Build Master SEAT Model and Seating Grid (Rows A to G, 105 Seats Total)
    print("[4/6] Building Cinema Seating Grid with Unique Seat IDs...")

    # Seating Block Layout per Row:
    # Left Block (Seats 1-4): X = -5.6, -5.0, -4.4, -3.8
    # Center Block (Seats 5-11): X = -1.8, -1.2, -0.6, 0.0, 0.6, 1.2, 1.8
    # Right Block (Seats 12-15): X = 3.8, 4.4, 5.0, 5.6
    seat_x_coords = [
        -5.6, -5.0, -4.4, -3.8,  # Left Bank: Seats 1-4
        -1.8, -1.2, -0.6, 0.0, 0.6, 1.2, 1.8,  # Center Bank: Seats 5-11
        3.8, 4.4, 5.0, 5.6   # Right Bank: Seats 12-15
    ]

    metadata_seats = []

    for row_lbl, y_center, z_base in rows_data:
        row_col = get_or_create_collection(f"ROW_{row_lbl}", seating_col)
        is_vip_row = (row_lbl == "G")  # Row G is Premium VIP Recliner row

        for seat_num, x_pos in enumerate(seat_x_coords, start=1):
            seat_id = f"{row_lbl}-{seat_num:03d}"
            obj_name = f"SEAT_{row_lbl}_{seat_num:03d}"

            # Accessible seats: Row A seats 1-2, Row D seats 1-2 (Operator-approved wheelchair accessible)
            is_accessible = (row_lbl in ("A", "D") and seat_num in (1, 2))
            is_companion = (row_lbl in ("A", "D") and seat_num == 3)
            seat_type = "ACCESSIBLE" if is_accessible else ("VIP_RECLINER" if is_vip_row else "STANDARD")
            seat_mat = mat_seat_accessible if is_accessible else (mat_seat_vip if is_vip_row else mat_seat_burgundy)

            # Base tier height
            seat_z = z_base

            # VIP recliners in row G are wider and plusher
            cushion_w = 0.64 if is_vip_row else 0.52
            cushion_d = 0.52 if is_vip_row else 0.46
            cushion_h = 0.16 if is_vip_row else 0.13
            back_tilt = math.radians(7.0)  # Gentle comfortable cinema recline angle

            # Root Empty at exact seat floor pivot with scale (1, 1, 1)
            seat_root = bpy.data.objects.new(obj_name, None)
            seat_root.location = (x_pos, y_center, seat_z)
            seat_root.empty_display_type = "PLAIN_AXES"
            seat_root.empty_display_size = 0.25
            row_col.objects.link(seat_root)

            # 1. Pedestal Stanchion & Floor Plate
            pedestal = create_box(f"{obj_name}_Pedestal", [x_pos, y_center, seat_z + 0.18],
                                  [0.14, 0.14, 0.36], row_col, mat_seat_polymer)
            plate = create_box(f"{obj_name}_Plate", [x_pos, y_center, seat_z + 0.02],
                               [0.26, 0.30, 0.04], row_col, mat_seat_polymer)

            # 2. Plastic Underside Support Tray
            tray = create_box(f"{obj_name}_Tray", [x_pos, y_center - 0.04, seat_z + 0.33],
                              [cushion_w - 0.02, cushion_d - 0.02, 0.04], row_col, mat_seat_polymer)

            # 3. Cushioned Seat Pan
            cushion = create_box(f"{obj_name}_Cushion", [x_pos, y_center - 0.04, seat_z + 0.40],
                                 [cushion_w, cushion_d, cushion_h], row_col, seat_mat, bevel_width=0.03)

            # 4. Ergonomic High Backrest
            back_z = seat_z + 0.72
            back_y = y_center + 0.16
            backrest = create_box(f"{obj_name}_Backrest", [x_pos, back_y, back_z],
                                  [cushion_w, 0.14, 0.54], row_col, seat_mat,
                                  bevel_width=0.025, rotation_euler=(-back_tilt, 0, 0))

            # 5. Protective Polymer Shell on Back
            back_shell = create_box(f"{obj_name}_BackShell", [x_pos, back_y + 0.06, back_z],
                                    [cushion_w, 0.04, 0.54], row_col, mat_seat_polymer,
                                    bevel_width=0.015, rotation_euler=(-back_tilt, 0, 0))

            # 6. Headrest
            head_z = seat_z + 1.05
            head_y = y_center + 0.21
            headrest = create_box(f"{obj_name}_Headrest", [x_pos, head_y, head_z],
                                  [cushion_w - 0.08, 0.12, 0.18], row_col, seat_mat,
                                  bevel_width=0.02, rotation_euler=(-back_tilt, 0, 0))

            # 7. Left & Right Armrests with Cup Holders
            arm_offset_x = (cushion_w / 2.0) + 0.045
            arm_w = 0.09 if is_vip_row else 0.08
            arm_l = create_box(f"{obj_name}_Arm_L", [x_pos - arm_offset_x, y_center - 0.02, seat_z + 0.54],
                               [arm_w, 0.44, 0.10], row_col, mat_seat_polymer, bevel_width=0.01)
            arm_r = create_box(f"{obj_name}_Arm_R", [x_pos + arm_offset_x, y_center - 0.02, seat_z + 0.54],
                               [arm_w, 0.44, 0.10], row_col, mat_seat_polymer, bevel_width=0.01)

            # Parent components to seat_root preserving world transforms
            for sub in [pedestal, plate, tray, cushion, backrest, back_shell, headrest, arm_l, arm_r]:
                sub.parent = seat_root
                sub.matrix_parent_inverse = seat_root.matrix_world.inverted()

            # Compute eye-point (seated viewer eye level is standardized at tier height + 1.15m)
            eye_point = [round(x_pos, 4), round(y_center, 4), round(seat_z + 1.15, 4)]
            seat_pos = [round(x_pos, 4), round(y_center, 4), round(seat_z, 4)]

            metadata_seats.append({
                "seat_id": seat_id,
                "label": f"{row_lbl}{seat_num:02d}",
                "row_label": row_lbl,
                "seat_number": seat_num,
                "seat_type": seat_type,
                "is_accessible": is_accessible,
                "is_companion": is_companion,
                "tier_level": row_lbl,
                "position": seat_pos,
                "eye_point": eye_point,
                "target": [0.0, round(screen_y, 4), round(screen_z, 4)],
                "rotation": [0.0, 0.0, 0.0],
                "mesh_reference": obj_name,
            })

    print(f" -> Successfully generated {len(metadata_seats)} verified seats with unique IDs.")

    # 7. Build INTERACTION_HELPERS & Anchors as True Blender Empties (Section 1 & 8)
    print("[5/6] Building Interaction Helpers and Anchor Points...")
    helpers = [
        ("HELPER_AUDITORIUM_ORIGIN", [0.0, 0.0, 0.0]),
        ("HELPER_SCREEN_CENTER", [0.0, screen_y, screen_z]),
        ("HELPER_SCREEN_TL", [-screen_w / 2.0, screen_y, screen_z + screen_h / 2.0]),
        ("HELPER_SCREEN_TR", [screen_w / 2.0, screen_y, screen_z + screen_h / 2.0]),
        ("HELPER_SCREEN_BL", [-screen_w / 2.0, screen_y, screen_z - screen_h / 2.0]),
        ("HELPER_SCREEN_BR", [screen_w / 2.0, screen_y, screen_z - screen_h / 2.0]),
        ("HELPER_STAGE_CENTER", [0.0, -1.0, 0.45]),
        ("HELPER_AISLE_LEFT_FRONT", [-2.6, 3.5, 0.0]),
        ("HELPER_AISLE_RIGHT_FRONT", [2.6, 3.5, 0.0]),
        ("HELPER_EXIT_REAR_LEFT", [-5.5, 18.9, 2.66]),
        ("HELPER_EXIT_REAR_RIGHT", [5.5, 18.9, 2.66]),
    ]
    for h_name, h_loc in helpers:
        create_helper_empty(h_name, h_loc, helpers_col)

    # 8. Setup LIGHTING
    # A. Screen Projection Ambience Light (illuminates auditorium with authentic movie bounce glow)
    light_screen = bpy.data.lights.new(name="LIGHT_SCREEN_PROJECTOR", type="AREA")
    light_screen.energy = 1100.0
    light_screen.color = (0.86, 0.92, 1.0)
    light_screen.size = screen_w * 0.95
    light_screen.size_y = screen_h * 0.90
    obj_l_screen = bpy.data.objects.new(name="LIGHT_SCREEN_PROJECTOR", object_data=light_screen)
    obj_l_screen.location = (0.0, screen_y + 0.15, screen_z)
    direction_proj = mathutils.Vector((0.0, 8.0, 2.5)) - mathutils.Vector((0.0, screen_y, screen_z))
    obj_l_screen.rotation_euler = direction_proj.to_track_quat('-Z', 'Y').to_euler()
    lighting_col.objects.link(obj_l_screen)

    # B. Ceiling Recessed Soft Downlights (dimmed architectural cove lighting)
    for c_y in [4.0, 7.5, 11.0, 15.0]:
        for c_x in [-5.0, 0.0, 5.0]:
            c_light = bpy.data.lights.new(name=f"LIGHT_DOWNLIGHT_{c_x}_{c_y}", type="POINT")
            c_light.energy = 180.0
            c_light.shadow_soft_size = 0.35
            c_light.color = (1.0, 0.94, 0.88)
            obj_c = bpy.data.objects.new(name=f"LIGHT_DOWNLIGHT_{c_x}_{c_y}", object_data=c_light)
            obj_c.location = (c_x, c_y, aud_height - 0.25)
            lighting_col.objects.link(obj_c)

    # C. Wall Sconces (Architectural wall grazing fixtures with up/down light cones)
    for s_idx in range(4):
        s_y = 3.5 + s_idx * 3.5
        for s_x, rot_z in [(-aud_width / 2.0 + 0.15, math.radians(90)), (aud_width / 2.0 - 0.15, math.radians(-90))]:
            create_box(f"SCONCE_FIXTURE_{s_x:.1f}_{s_y:.1f}", [s_x, s_y, 4.0], [0.12, 0.20, 0.45],
                       lighting_col, mat_sconce_fixture, bevel_width=0.01)

            w_down = bpy.data.lights.new(name=f"LIGHT_SCONCE_DOWN_{s_x:.1f}_{s_y:.1f}", type="SPOT")
            w_down.energy = 95.0
            w_down.color = (1.0, 0.82, 0.58)
            w_down.spot_size = math.radians(65)
            w_down.spot_blend = 0.4
            obj_w_down = bpy.data.objects.new(name=w_down.name, object_data=w_down)
            obj_w_down.location = (s_x + (0.1 if s_x < 0 else -0.1), s_y, 3.8)
            obj_w_down.rotation_euler = (0, 0, 0)
            lighting_col.objects.link(obj_w_down)

            w_up = bpy.data.lights.new(name=f"LIGHT_SCONCE_UP_{s_x:.1f}_{s_y:.1f}", type="SPOT")
            w_up.energy = 75.0
            w_up.color = (1.0, 0.82, 0.58)
            w_up.spot_size = math.radians(60)
            w_up.spot_blend = 0.4
            obj_w_up = bpy.data.objects.new(name=w_up.name, object_data=w_up)
            obj_w_up.location = (s_x + (0.1 if s_x < 0 else -0.1), s_y, 4.2)
            obj_w_up.rotation_euler = (math.radians(180), 0, 0)
            lighting_col.objects.link(obj_w_up)

    # 9. Setup Multi-Camera Navigation System (Section 8)
    print("[6/6] Configuring Cameras and Render Setup...")
    # Camera 1: Overview (High rear angle looking down auditorium toward screen)
    cam_overview_data = bpy.data.cameras.new("CAM_OVERVIEW")
    cam_overview_data.lens = 24.0  # wide angle cinema overview
    cam_overview_data.clip_start = 0.1
    cam_overview_data.clip_end = 150.0
    cam_overview_obj = bpy.data.objects.new("CAM_OVERVIEW", cam_overview_data)
    cam_overview_obj.location = (0.0, 16.5, 6.2)
    target_overview = mathutils.Vector((0.0, 2.0, 2.2))
    cam_overview_obj.rotation_euler = (target_overview - cam_overview_obj.location).to_track_quat('-Z', 'Y').to_euler()
    cameras_col.objects.link(cam_overview_obj)

    # Camera 2: Screen-Facing (From stage looking up into tiered seats)
    cam_stage_data = bpy.data.cameras.new("CAM_SCREEN_FACING")
    cam_stage_data.lens = 24.0
    cam_stage_data.clip_start = 0.1
    cam_stage_data.clip_end = 150.0
    cam_stage_obj = bpy.data.objects.new("CAM_SCREEN_FACING", cam_stage_data)
    cam_stage_obj.location = (0.0, -1.8, 1.2)
    target_stage = mathutils.Vector((0.0, 7.5, 2.4))
    cam_stage_obj.rotation_euler = (target_stage - cam_stage_obj.location).to_track_quat('-Z', 'Y').to_euler()
    cameras_col.objects.link(cam_stage_obj)

    # Camera 3: Seat Preview (Row D, Seat 8 - prime center sweet-spot seat)
    prime_seat = [s for s in metadata_seats if s["seat_id"] == "D-008"][0]
    cam_seat_data = bpy.data.cameras.new("CAM_SEAT_PREVIEW_D08")
    cam_seat_data.lens = 19.0  # ultra-wide FOV capturing screen + masking + stage + row C ahead
    cam_seat_data.clip_start = 0.1
    cam_seat_data.clip_end = 150.0
    cam_seat_obj = bpy.data.objects.new("CAM_SEAT_PREVIEW_D08", cam_seat_data)
    cam_seat_obj.location = tuple(prime_seat["eye_point"])
    target_screen_view = mathutils.Vector((0.0, screen_y, screen_z - 0.5))
    cam_seat_obj.rotation_euler = (target_screen_view - cam_seat_obj.location).to_track_quat('-Z', 'Y').to_euler()
    cameras_col.objects.link(cam_seat_obj)

    # 10. Save Master .blend File
    blend_path = OUTPUT_DIR / "cinema_theatre_auditorium.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f" -> Master Blender project saved: {blend_path}")

    # 11. Export Optimized Web-Ready GLB (Section 11)
    glb_path = OUTPUT_DIR / "cinema_theatre_auditorium.glb"
    print(f"Exporting optimized web-ready GLB to {glb_path}...")
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
    )
    glb_size = glb_path.stat().st_size
    print(f" -> GLB exported successfully. File size: {glb_size:,} bytes ({glb_size / 1024 / 1024:.2f} MB)")

    # 12. Save Normalized Seat & Layout Metadata JSON (Section 13)
    layout_metadata = {
        "schema_version": "1.0",
        "auditorium_id": "AUD_HORIZON_SCREEN_01",
        "auditorium_name": "Horizon Cineplex - Auditorium 1 (Scope Grand)",
        "layout_version": 1,
        "units": "meters",
        "coordinate_system": {
            "up_axis": "Z",
            "forward_axis": "-Y",
            "origin": "auditorium_floor_front_center",
        },
        "engine_coordinate_mapping": {
            "web_engine": "Three.js / React Three Fiber",
            "web_up_axis": "Y",
            "web_forward_axis": "-Z",
            "note": "GLTF export automatically converts Blender +Z up to Three.js +Y up.",
        },
        "dimensions": {
            "width": aud_width,
            "length": aud_length,
            "height": aud_height,
        },
        "screen": {
            "name": "SCREEN_MAIN",
            "center": [0.0, screen_y, screen_z],
            "width": screen_w,
            "height": screen_h,
            "aspect_ratio": "2.39:1 (CinemaScope)",
            "normal": [0.0, 1.0, 0.0],
            "masking_frame": {
                "border_width": border_w,
                "material": "Mat_Screen_Masking",
            },
        },
        "helpers": {
            h_name: h_loc for h_name, h_loc in helpers
        },
        "seating_summary": {
            "total_seats": len(metadata_seats),
            "rows_count": len(rows_data),
            "rows": [r[0] for r in rows_data],
            "seat_types": {
                "STANDARD": sum(1 for s in metadata_seats if s["seat_type"] == "STANDARD"),
                "VIP_RECLINER": sum(1 for s in metadata_seats if s["seat_type"] == "VIP_RECLINER"),
                "ACCESSIBLE": sum(1 for s in metadata_seats if s["seat_type"] == "ACCESSIBLE"),
            },
            "accessible_seats_count": sum(1 for s in metadata_seats if s["is_accessible"]),
            "companion_seats_count": sum(1 for s in metadata_seats if s.get("is_companion", False)),
        },
        "seats": metadata_seats,
    }

    metadata_path = OUTPUT_DIR / "cinema_layout_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(layout_metadata, f, indent=2)
    print(f" -> Layout metadata written: {metadata_path}")

    # 13. Save Asset Manifest JSON
    manifest = {
        "asset_name": "cinema_theatre_auditorium",
        "version": "1.0.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "author": "Antigravity AI 3D Technical Artist",
        "license": "Multi-Cinema Platform Production License",
        "units": "meters",
        "blender_version": bpy.app.version_string,
        "files": {
            "blend_source": "cinema_theatre_auditorium.blend",
            "web_glb": "cinema_theatre_auditorium.glb",
            "layout_metadata": "cinema_layout_metadata.json",
        },
        "file_sizes_bytes": {
            "blend": blend_path.stat().st_size,
            "glb": glb_size,
            "metadata": metadata_path.stat().st_size,
        },
        "sha256": {
            "glb": hashlib.sha256(glb_path.read_bytes()).hexdigest(),
        },
    }
    manifest_path = OUTPUT_DIR / "cinema_asset_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f" -> Asset manifest written: {manifest_path}")

    # 14. Render Multi-Camera Preview Stills
    print("Rendering Multi-Camera High-Resolution Preview Images...")
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    renders = [
        ("render_overview.png", cam_overview_obj),
        ("render_screen_facing.png", cam_stage_obj),
        ("render_seat_d08_view.png", cam_seat_obj),
    ]

    for fname, cam_obj in renders:
        r_path = OUTPUT_DIR / fname
        scene.camera = cam_obj
        scene.render.filepath = str(r_path)
        print(f" -> Rendering {fname} from {cam_obj.name}...")
        bpy.ops.render.render(write_still=True)
        print(f"    Saved: {r_path} ({r_path.stat().st_size:,} bytes)")

    print("\n" + "=" * 70)
    print(" 3D CINEMA THEATRE AUDITORIUM BUILD COMPLETE SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    build_cinema()
