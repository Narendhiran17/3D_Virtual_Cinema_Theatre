"""Photorealistic Production Build for 3D Cinema Theatre Auditorium
Targeting absolute photographic realism using Cycles OptiX GPU Path Tracing,
PBR procedural textures, detailed ergonomic seating, volumetric projector beam,
and CinemaScope 2.39:1 film projection.
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
FILM_STILL_PATH = OUTPUT_DIR / "cinema_screen_film_still.png"


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


def create_box(name: str, location, scale, collection: bpy.types.Collection, material=None,
               bevel_width=0.0, bevel_segments=2, rotation_euler=(0, 0, 0)):
    """Helper to create a scaled box mesh with bevel and smooth shading."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = tuple(scale)
    obj.rotation_euler = tuple(rotation_euler)

    if bevel_width > 0:
        mod = obj.modifiers.new(name="Bevel", type="BEVEL")
        mod.width = bevel_width
        mod.segments = bevel_segments
        mod.limit_method = "ANGLE"

    for poly in obj.data.polygons:
        poly.use_smooth = True

    if material:
        obj.data.materials.append(material)

    if obj.name not in collection.objects:
        collection.objects.link(obj)
    for col in list(obj.users_collection):
        if col != collection:
            col.objects.unlink(obj)

    return obj


def create_cylinder(name: str, location, radius, depth, collection: bpy.types.Collection, material=None,
                    rotation_euler=(0, 0, 0)):
    """Helper to create a cylinder mesh with smooth shading."""
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, vertices=24, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = tuple(rotation_euler)

    for poly in obj.data.polygons:
        poly.use_smooth = True

    if material:
        obj.data.materials.append(material)

    if obj.name not in collection.objects:
        collection.objects.link(obj)
    for col in list(obj.users_collection):
        if col != collection:
            col.objects.unlink(obj)

    return obj


def create_helper_empty(name: str, location, collection: bpy.types.Collection, display_size=0.3):
    """Create a non-rendering transformation helper empty object."""
    empty = bpy.data.objects.new(name, None)
    empty.location = tuple(location)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = display_size
    collection.objects.link(empty)
    return empty


# ==============================================================================
# ADVANCED PROCEDURAL PBR MATERIAL GENERATORS
# ==============================================================================

def create_cinema_carpet_material(name="Mat_Cinema_Carpet") -> bpy.types.Material:
    """Create a rich, commercial patterned cinema carpet with woven loop-pile bump."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_out.location = (800, 0)

    node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    node_bsdf.location = (500, 0)
    node_bsdf.inputs["Roughness"].default_value = 0.94
    for spec_name in ["Specular IOR Level", "Specular"]:
        if spec_name in node_bsdf.inputs:
            node_bsdf.inputs[spec_name].default_value = 0.15
            break

    # Texture Coordinates & Mapping
    node_coord = nodes.new(type="ShaderNodeTexCoord")
    node_coord.location = (-600, 0)

    node_mapping = nodes.new(type="ShaderNodeMapping")
    node_mapping.location = (-400, 0)
    node_mapping.inputs["Scale"].default_value = (8.0, 8.0, 8.0)
    links.new(node_coord.outputs["Object"], node_mapping.inputs["Vector"])

    # Voronoi Pattern for Geometric Cinema Carpet Motifs
    node_voro = nodes.new(type="ShaderNodeTexVoronoi")
    node_voro.location = (-150, 100)
    node_voro.inputs["Scale"].default_value = 4.5
    links.new(node_mapping.outputs["Vector"], node_voro.inputs["Vector"])

    # Fine Noise for Woven Fiber Flecks
    node_noise = nodes.new(type="ShaderNodeTexNoise")
    node_noise.location = (-150, -150)
    node_noise.inputs["Scale"].default_value = 120.0
    node_noise.inputs["Detail"].default_value = 4.0
    links.new(node_mapping.outputs["Vector"], node_noise.inputs["Vector"])

    # Color Ramp for Carpet Palette: Dark Charcoal + Wine Red Flecks
    node_ramp = nodes.new(type="ShaderNodeValToRGB")
    node_ramp.location = (150, 100)
    node_ramp.color_ramp.elements[0].position = 0.35
    node_ramp.color_ramp.elements[0].color = (0.022, 0.022, 0.026, 1.0)  # Dark charcoal
    node_ramp.color_ramp.elements[1].position = 0.70
    node_ramp.color_ramp.elements[1].color = (0.075, 0.022, 0.035, 1.0)  # Wine red fleck
    links.new(node_voro.outputs["Distance"], node_ramp.inputs["Fac"])
    links.new(node_ramp.outputs["Color"], node_bsdf.inputs["Base Color"])

    # Bump node for tactile pile texture
    node_bump = nodes.new(type="ShaderNodeBump")
    node_bump.location = (200, -150)
    node_bump.inputs["Strength"].default_value = 0.25
    node_bump.inputs["Distance"].default_value = 0.005
    links.new(node_noise.outputs["Fac"], node_bump.inputs["Height"])
    links.new(node_bump.outputs["Normal"], node_bsdf.inputs["Normal"])

    links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    return mat


def create_velvet_seat_material(name="Mat_Seat_Burgundy", base_rgb=(0.42, 0.028, 0.055)) -> bpy.types.Material:
    """Create authentic cinema velvet upholstery with edge sheen and micro-fabric texture."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_out.location = (600, 0)

    node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    node_bsdf.location = (300, 0)
    node_bsdf.inputs["Base Color"].default_value = tuple(base_rgb) + (1.0,)
    node_bsdf.inputs["Roughness"].default_value = 0.65

    # Sheen for velvet plush edge glow
    for s_name in ["Sheen Weight", "Sheen"]:
        if s_name in node_bsdf.inputs:
            node_bsdf.inputs[s_name].default_value = 1.0
            break
    if "Sheen Roughness" in node_bsdf.inputs:
        node_bsdf.inputs["Sheen Roughness"].default_value = 0.25
    if "Sheen Tint" in node_bsdf.inputs:
        node_bsdf.inputs["Sheen Tint"].default_value = (0.75, 0.12, 0.22, 1.0)

    # Micro-fabric noise bump
    node_coord = nodes.new(type="ShaderNodeTexCoord")
    node_coord.location = (-400, -100)

    node_noise = nodes.new(type="ShaderNodeTexNoise")
    node_noise.location = (-200, -100)
    node_noise.inputs["Scale"].default_value = 180.0
    node_noise.inputs["Detail"].default_value = 6.0
    links.new(node_coord.outputs["Object"], node_noise.inputs["Vector"])

    node_bump = nodes.new(type="ShaderNodeBump")
    node_bump.location = (50, -100)
    node_bump.inputs["Strength"].default_value = 0.10
    node_bump.inputs["Distance"].default_value = 0.002
    links.new(node_noise.outputs["Fac"], node_bump.inputs["Height"])
    links.new(node_bump.outputs["Normal"], node_bsdf.inputs["Normal"])

    links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    return mat


def create_leather_vip_material(name="Mat_Seat_VIP") -> bpy.types.Material:
    """Create luxury perforated dark midnight navy leather for Row G VIP recliners."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_out.location = (600, 0)

    node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    node_bsdf.location = (300, 0)
    node_bsdf.inputs["Base Color"].default_value = (0.015, 0.035, 0.09, 1.0)
    node_bsdf.inputs["Roughness"].default_value = 0.36
    for spec in ["Specular IOR Level", "Specular"]:
        if spec in node_bsdf.inputs:
            node_bsdf.inputs[spec].default_value = 0.55
            break
    for coat in ["Coat Weight", "Clearcoat"]:
        if coat in node_bsdf.inputs:
            node_bsdf.inputs[coat].default_value = 0.25
            break

    # Leather pore bump
    node_coord = nodes.new(type="ShaderNodeTexCoord")
    node_coord.location = (-400, -100)
    node_voro = nodes.new(type="ShaderNodeTexVoronoi")
    node_voro.location = (-200, -100)
    node_voro.inputs["Scale"].default_value = 220.0
    links.new(node_coord.outputs["Object"], node_voro.inputs["Vector"])

    node_bump = nodes.new(type="ShaderNodeBump")
    node_bump.location = (50, -100)
    node_bump.inputs["Strength"].default_value = 0.12
    node_bump.inputs["Distance"].default_value = 0.002
    links.new(node_voro.outputs["Distance"], node_bump.inputs["Height"])
    links.new(node_bump.outputs["Normal"], node_bsdf.inputs["Normal"])

    links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    return mat


def create_acoustic_panel_material(name="Mat_Acoustic_Panel") -> bpy.types.Material:
    """Create fabric-wrapped acoustic wall panel material with subtle weave."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_out.location = (600, 0)

    node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    node_bsdf.location = (300, 0)
    node_bsdf.inputs["Base Color"].default_value = (0.025, 0.045, 0.09, 1.0)
    node_bsdf.inputs["Roughness"].default_value = 0.82

    node_coord = nodes.new(type="ShaderNodeTexCoord")
    node_coord.location = (-400, -100)
    node_noise = nodes.new(type="ShaderNodeTexNoise")
    node_noise.location = (-200, -100)
    node_noise.inputs["Scale"].default_value = 140.0
    node_noise.inputs["Detail"].default_value = 4.0
    links.new(node_coord.outputs["Object"], node_noise.inputs["Vector"])

    node_bump = nodes.new(type="ShaderNodeBump")
    node_bump.location = (50, -100)
    node_bump.inputs["Strength"].default_value = 0.15
    node_bump.inputs["Distance"].default_value = 0.003
    links.new(node_noise.outputs["Fac"], node_bump.inputs["Height"])
    links.new(node_bump.outputs["Normal"], node_bsdf.inputs["Normal"])

    links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    return mat


def create_projected_screen_material(name="Mat_Cinema_Screen", image_path: Path = None) -> bpy.types.Material:
    """Create realistic CinemaScope projection screen material displaying the movie image with HDR emission."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_out = nodes.new(type="ShaderNodeOutputMaterial")
    node_out.location = (700, 0)

    node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    node_bsdf.location = (400, 0)
    node_bsdf.inputs["Roughness"].default_value = 0.35

    if image_path and image_path.exists():
        # Load film still texture
        img = bpy.data.images.load(str(image_path), check_existing=True)
        node_tex = nodes.new(type="ShaderNodeTexImage")
        node_tex.location = (0, 0)
        node_tex.image = img

        # Map to Base Color
        links.new(node_tex.outputs["Color"], node_bsdf.inputs["Base Color"])

        # Map to Emission with HDR boost so it physically illuminates the auditorium in Cycles!
        for em_name in ["Emission Color", "Emission"]:
            if em_name in node_bsdf.inputs:
                links.new(node_tex.outputs["Color"], node_bsdf.inputs[em_name])
                break
        if "Emission Strength" in node_bsdf.inputs:
            node_bsdf.inputs["Emission Strength"].default_value = 3.2
    else:
        node_bsdf.inputs["Base Color"].default_value = (0.92, 0.92, 0.95, 1.0)
        if "Emission Strength" in node_bsdf.inputs:
            node_bsdf.inputs["Emission Strength"].default_value = 1.0

    links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    return mat


def build_cinema_photoreal():
    print("=" * 75)
    print(" BUILDING PHOTOREALISTIC 3D CINEMA AUDITORIUM (CYCLES OPTIX PATH TRACER)")
    print("=" * 75)

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
    mat_carpet = create_cinema_carpet_material("Mat_Cinema_Carpet")
    mat_seat_burgundy = create_velvet_seat_material("Mat_Seat_Burgundy", (0.42, 0.028, 0.055))
    mat_seat_accessible = create_velvet_seat_material("Mat_Seat_Accessible", (0.36, 0.035, 0.075))
    mat_seat_vip = create_leather_vip_material("Mat_Seat_VIP")
    mat_panel = create_acoustic_panel_material("Mat_Acoustic_Panel")
    mat_screen = create_projected_screen_material("Mat_Cinema_Screen", FILM_STILL_PATH)

    # Standard Principled materials
    mat_wall = bpy.data.materials.new("Mat_Acoustic_Wall")
    mat_wall.use_nodes = True
    mat_wall.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.045, 0.045, 0.052, 1.0)
    mat_wall.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.88

    mat_ceiling = bpy.data.materials.new("Mat_Ceiling_Baffle")
    mat_ceiling.use_nodes = True
    mat_ceiling.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.018, 0.018, 0.022, 1.0)
    mat_ceiling.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.90

    mat_masking = bpy.data.materials.new("Mat_Screen_Masking")
    mat_masking.use_nodes = True
    mat_masking.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.008, 0.008, 0.008, 1.0)
    mat_masking.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.98

    mat_polymer = bpy.data.materials.new("Mat_Seat_Polymer")
    mat_polymer.use_nodes = True
    mat_polymer.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.025, 0.025, 0.028, 1.0)
    mat_polymer.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.42

    mat_trim_brass = bpy.data.materials.new("Mat_Trim_Brass")
    mat_trim_brass.use_nodes = True
    mat_trim_brass.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.72, 0.58, 0.28, 1.0)
    mat_trim_brass.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.90
    mat_trim_brass.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.25

    mat_step_led = bpy.data.materials.new("Mat_Step_LED")
    mat_step_led.use_nodes = True
    bsdf_led = mat_step_led.node_tree.nodes["Principled BSDF"]
    bsdf_led.inputs["Base Color"].default_value = (1.0, 0.74, 0.28, 1.0)
    for em in ["Emission Color", "Emission"]:
        if em in bsdf_led.inputs:
            bsdf_led.inputs[em].default_value = (1.0, 0.74, 0.28, 1.0)
            break
    if "Emission Strength" in bsdf_led.inputs:
        bsdf_led.inputs["Emission Strength"].default_value = 8.0

    mat_aisle_badge = bpy.data.materials.new("Mat_Aisle_Row_Badge")
    mat_aisle_badge.use_nodes = True
    bsdf_badge = mat_aisle_badge.node_tree.nodes["Principled BSDF"]
    bsdf_badge.inputs["Base Color"].default_value = (1.0, 0.85, 0.45, 1.0)
    for em in ["Emission Color", "Emission"]:
        if em in bsdf_badge.inputs:
            bsdf_badge.inputs[em].default_value = (1.0, 0.85, 0.45, 1.0)
            break
    if "Emission Strength" in bsdf_badge.inputs:
        bsdf_badge.inputs["Emission Strength"].default_value = 6.0

    mat_exit_sign = bpy.data.materials.new("Mat_Exit_Sign")
    mat_exit_sign.use_nodes = True
    bsdf_exit = mat_exit_sign.node_tree.nodes["Principled BSDF"]
    bsdf_exit.inputs["Base Color"].default_value = (0.1, 0.90, 0.30, 1.0)
    for em in ["Emission Color", "Emission"]:
        if em in bsdf_exit.inputs:
            bsdf_exit.inputs[em].default_value = (0.1, 0.90, 0.30, 1.0)
            break
    if "Emission Strength" in bsdf_exit.inputs:
        bsdf_exit.inputs["Emission Strength"].default_value = 6.0

    mat_handrail = bpy.data.materials.new("Mat_Handrail_Metal")
    mat_handrail.use_nodes = True
    mat_handrail.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.22, 0.22, 0.24, 1.0)
    mat_handrail.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.95
    mat_handrail.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.18

    # 3. Build ARCHITECTURE (Shell, Walls, Ceiling, Tiers)
    print("[1/6] Building Auditorium Architecture Shell...")
    aud_width = 16.0
    aud_length = 22.0  # from Y = -3.0 to Y = 19.0
    aud_height = 7.5

    # Main Base Floor
    create_box("AUD_FLOOR", [0.0, 7.5, -0.05], [aud_width, 25.0, 0.1], arch_col, mat_carpet)

    # Left & Right Perimeter Walls
    create_box("AUD_WALL_LEFT", [-aud_width / 2.0 - 0.1, 7.5, aud_height / 2.0], [0.2, 25.0, aud_height], arch_col, mat_wall)
    create_box("AUD_WALL_RIGHT", [aud_width / 2.0 + 0.1, 7.5, aud_height / 2.0], [0.2, 25.0, aud_height], arch_col, mat_wall)

    # Rear & Front Walls
    create_box("AUD_WALL_REAR", [0.0, 19.1, aud_height / 2.0], [aud_width + 0.4, 0.2, aud_height], arch_col, mat_wall)
    create_box("AUD_WALL_SCREEN", [0.0, -3.1, aud_height / 2.0], [aud_width + 0.4, 0.2, aud_height], arch_col, mat_masking)

    # Ceiling Suspended Acoustic Baffles
    create_box("AUD_CEILING", [0.0, 7.5, aud_height + 0.05], [aud_width, 25.0, 0.1], arch_col, mat_ceiling)
    for b_y in range(-1, 19, 2):
        create_box(f"AUD_CEILING_BAFFLE_{b_y}", [0.0, float(b_y), aud_height - 0.15],
                   [aud_width - 1.0, 0.25, 0.28], arch_col, mat_ceiling)

    # 12 Acoustic Wall Panels with Anodized Bronze Trim
    for p_idx in range(6):
        y_pos = 1.0 + p_idx * 3.0
        # Left wall panel
        create_box(f"AUD_ACOUSTIC_PANEL_L_{p_idx+1:02d}", [-aud_width / 2.0 + 0.08, y_pos, 3.8],
                   [0.12, 2.2, 4.8], arch_col, mat_panel, bevel_width=0.03)
        # Left wall trim frame
        create_box(f"AUD_PANEL_TRIM_L_{p_idx+1:02d}", [-aud_width / 2.0 + 0.06, y_pos, 3.8],
                   [0.14, 2.30, 4.90], arch_col, mat_trim_brass, bevel_width=0.01)

        # Right wall panel
        create_box(f"AUD_ACOUSTIC_PANEL_R_{p_idx+1:02d}", [aud_width / 2.0 - 0.08, y_pos, 3.8],
                   [0.12, 2.2, 4.8], arch_col, mat_panel, bevel_width=0.03)
        # Right wall trim frame
        create_box(f"AUD_PANEL_TRIM_R_{p_idx+1:02d}", [aud_width / 2.0 - 0.06, y_pos, 3.8],
                   [0.14, 2.30, 4.90], arch_col, mat_trim_brass, bevel_width=0.01)

    # Tiered Stadium Risers (Rows A to G)
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
        create_box(t_name, [0.0, y_center, z_height / 2.0], [aud_width - 1.2, 1.20, z_height],
                   tier_col, mat_carpet, bevel_width=0.01)

    # Rear Concourse Platform
    create_box("AUD_REAR_CONCOURSE", [0.0, 14.5, 2.66 / 2.0], [aud_width - 1.2, 5.4, 2.66], arch_col, mat_carpet)

    # 4. Build SCREEN_AND_STAGE
    print("[2/6] Building Screen, Frame, Stage, and Sound System...")
    # Front Stage with beveled edges and carpet finish
    create_box("STAGE_MAIN", [0.0, -1.0, 0.225], [15.0, 2.8, 0.45], screen_col, mat_carpet, bevel_width=0.03)
    # Stage Apron fascia plate (dark trim)
    create_box("STAGE_FASCIA", [0.0, 0.42, 0.225], [15.0, 0.04, 0.45], screen_col, mat_polymer)

    # CinemaScope 2.39:1 Screen Surface
    screen_w = 13.5
    screen_h = 5.65
    screen_z = 3.95
    screen_y = -2.3

    # Screen Surface Mesh (unwrapped quad texture mapping facing audience)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, screen_y, screen_z),
                                     rotation=(math.radians(-90), 0, 0))
    scr_obj = bpy.context.active_object
    scr_obj.name = "SCREEN_MAIN"
    scr_obj.scale = (-screen_w, -screen_h, 1.0)
    scr_obj.data.materials.append(mat_screen)
    if scr_obj.name not in screen_col.objects:
        screen_col.objects.link(scr_obj)
    for c in list(scr_obj.users_collection):
        if c != screen_col:
            c.objects.unlink(scr_obj)

    # 4-Sided Plush Velvet Masking Frame Border
    border_w = 0.35
    frame_d = 0.12
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
    # Stepped Aisle Blocks & Nose LED Strips
    for row_lbl, y_center, z_height in rows_data:
        y_front = y_center - 0.58
        # Step LED strips with realistic downward-facing nose lip
        create_box(f"STEP_NOSE_{row_lbl}_L", [-2.6, y_front, z_height + 0.01], [1.02, 0.05, 0.03], aisles_col, mat_polymer)
        create_box(f"STEP_LED_{row_lbl}_L", [-2.6, y_front - 0.02, z_height - 0.005], [0.98, 0.02, 0.015], aisles_col, mat_step_led)

        create_box(f"STEP_NOSE_{row_lbl}_R", [2.6, y_front, z_height + 0.01], [1.02, 0.05, 0.03], aisles_col, mat_polymer)
        create_box(f"STEP_LED_{row_lbl}_R", [2.6, y_front - 0.02, z_height - 0.005], [0.98, 0.02, 0.015], aisles_col, mat_step_led)

    # Handrails: Cylindrical steel tube railings with vertical mounting stanchions
    # Safety Barrier Rail in front of Row A
    create_cylinder("BARRIER_TOP_ROW_A", [0.0, 3.35, 0.90], 0.025, aud_width - 3.2, aisles_col, mat_handrail,
                    rotation_euler=(0, math.radians(90), 0))
    for post_x in [-5.0, -2.5, 0.0, 2.5, 5.0]:
        create_cylinder(f"BARRIER_POST_{post_x}", [post_x, 3.35, 0.45], 0.02, 0.90, aisles_col, mat_handrail)

    # Wall Handrails along circulation ramps
    create_cylinder("HANDRAIL_L_TUBE", [-aud_width / 2.0 + 0.25, 7.8, 1.8], 0.025, 9.5, aisles_col, mat_handrail,
                    rotation_euler=(math.radians(90), 0, 0))
    create_cylinder("HANDRAIL_R_TUBE", [aud_width / 2.0 - 0.25, 7.8, 1.8], 0.025, 9.5, aisles_col, mat_handrail,
                    rotation_euler=(math.radians(90), 0, 0))

    # Rear Exit Doors with Push Bars and illuminated EXIT signs
    for door_x, d_lbl in [(-5.5, "L"), (5.5, "R")]:
        create_box(f"DOOR_REAR_{d_lbl}", [door_x, 18.95, 2.66 + 1.2], [1.4, 0.08, 2.4], aisles_col, mat_wall)
        create_box(f"DOOR_FRAME_{d_lbl}", [door_x, 18.92, 2.66 + 1.2], [1.5, 0.04, 2.5], aisles_col, mat_polymer)
        create_cylinder(f"DOOR_PUSHBAR_{d_lbl}", [door_x, 18.88, 2.66 + 1.05], 0.018, 1.1, aisles_col, mat_handrail,
                        rotation_euler=(0, math.radians(90), 0))
        create_box(f"EXIT_SIGN_{d_lbl}", [door_x, 18.90, 2.66 + 2.6], [0.8, 0.04, 0.3], signage_col, mat_exit_sign)

    # 6. Build Master Cinema SEAT Model and Seating Grid (Rows A to G, 105 Seats Total)
    print("[4/6] Building Realistic Cinema Seating with Ergonomic Contours & Aisle Badges...")

    seat_x_coords = [
        -5.6, -5.0, -4.4, -3.8,  # Left Bank: Seats 1-4
        -1.8, -1.2, -0.6, 0.0, 0.6, 1.2, 1.8,  # Center Bank: Seats 5-11
        3.8, 4.4, 5.0, 5.6   # Right Bank: Seats 12-15
    ]

    metadata_seats = []

    for row_lbl, y_center, z_base in rows_data:
        row_col = get_or_create_collection(f"ROW_{row_lbl}", seating_col)
        is_vip_row = (row_lbl == "G")

        for seat_num, x_pos in enumerate(seat_x_coords, start=1):
            seat_id = f"{row_lbl}-{seat_num:03d}"
            obj_name = f"SEAT_{row_lbl}_{seat_num:03d}"

            # Accessible seats: Row A seats 1-2, Row D seats 1-2
            is_accessible = (row_lbl in ("A", "D") and seat_num in (1, 2))
            is_companion = (row_lbl in ("A", "D") and seat_num == 3)
            seat_type = "ACCESSIBLE" if is_accessible else ("VIP_RECLINER" if is_vip_row else "STANDARD")
            seat_mat = mat_seat_accessible if is_accessible else (mat_seat_vip if is_vip_row else mat_seat_burgundy)

            seat_z = z_base

            # Ergonomic Dimensions
            cushion_w = 0.65 if is_vip_row else 0.52
            cushion_d = 0.52 if is_vip_row else 0.46
            cushion_h = 0.16 if is_vip_row else 0.13
            back_tilt = math.radians(8.0)

            # Master Root Empty at floor level with identity scale
            seat_root = bpy.data.objects.new(obj_name, None)
            seat_root.location = (x_pos, y_center, seat_z)
            seat_root.empty_display_type = "PLAIN_AXES"
            seat_root.empty_display_size = 0.25
            row_col.objects.link(seat_root)

            sub_objects = []

            # A. Dual Tubular Steel Pedestal Stanchions & Floor Anchors
            stanch_l = create_cylinder(f"{obj_name}_Stanch_L", [x_pos - 0.14, y_center, seat_z + 0.18],
                                       0.025, 0.36, row_col, mat_polymer)
            stanch_r = create_cylinder(f"{obj_name}_Stanch_R", [x_pos + 0.14, y_center, seat_z + 0.18],
                                       0.025, 0.36, row_col, mat_polymer)
            plate = create_box(f"{obj_name}_Plate", [x_pos, y_center, seat_z + 0.02],
                               [0.36, 0.32, 0.04], row_col, mat_polymer, bevel_width=0.005)
            sub_objects.extend([stanch_l, stanch_r, plate])

            # B. Contoured Under-Seat Molded Polymer Tray
            tray = create_box(f"{obj_name}_Tray", [x_pos, y_center - 0.04, seat_z + 0.32],
                              [cushion_w - 0.02, cushion_d - 0.02, 0.05], row_col, mat_polymer, bevel_width=0.01)
            sub_objects.append(tray)

            # C. Sculpted Plush Seat Pan Cushion with Waterfall Front
            cushion = create_box(f"{obj_name}_Cushion", [x_pos, y_center - 0.04, seat_z + 0.40],
                                 [cushion_w, cushion_d, cushion_h], row_col, seat_mat,
                                 bevel_width=0.035, bevel_segments=3)
            sub_objects.append(cushion)

            # D. High Ergonomic Backrest with Lumbar Contour
            back_z = seat_z + 0.72
            back_y = y_center + 0.16
            backrest = create_box(f"{obj_name}_Backrest", [x_pos, back_y, back_z],
                                  [cushion_w, 0.14, 0.54], row_col, seat_mat,
                                  bevel_width=0.03, bevel_segments=3, rotation_euler=(-back_tilt, 0, 0))
            sub_objects.append(backrest)

            # E. Protective Textured Polymer Rear Back Shell
            back_shell = create_box(f"{obj_name}_BackShell", [x_pos, back_y + 0.065, back_z],
                                    [cushion_w, 0.035, 0.54], row_col, mat_polymer,
                                    bevel_width=0.015, rotation_euler=(-back_tilt, 0, 0))
            sub_objects.append(back_shell)

            # F. Contoured Headrest Pillow
            head_z = seat_z + 1.05
            head_y = y_center + 0.21
            headrest = create_box(f"{obj_name}_Headrest", [x_pos, head_y, head_z],
                                  [cushion_w - 0.08, 0.12, 0.18], row_col, seat_mat,
                                  bevel_width=0.025, bevel_segments=2, rotation_euler=(-back_tilt, 0, 0))
            sub_objects.append(headrest)

            # G. Armrests with Integrated Recessed Cup Holders
            arm_offset_x = (cushion_w / 2.0) + 0.045
            arm_w = 0.09 if is_vip_row else 0.08
            for side_idx, arm_x in [(-1, x_pos - arm_offset_x), (1, x_pos + arm_offset_x)]:
                s_tag = "L" if side_idx == -1 else "R"
                arm_body = create_box(f"{obj_name}_Arm_{s_tag}", [arm_x, y_center - 0.02, seat_z + 0.54],
                                      [arm_w, 0.44, 0.10], row_col, mat_polymer, bevel_width=0.015)
                # Recessed Cup Holder Ring on front of armrest
                cupholder = create_cylinder(f"{obj_name}_Cup_{s_tag}", [arm_x, y_center - 0.16, seat_z + 0.57],
                                            0.035, 0.045, row_col, mat_trim_brass)
                sub_objects.extend([arm_body, cupholder])

            # H. Illuminated Aisle End Panel with Row Badge on Aisle-Facing Seats
            # Left aisle is between X=-3.8 and X=-1.8 (seats 4 and 5)
            # Right aisle is between X=1.8 and X=3.8 (seats 11 and 12)
            is_aisle_facing_left = (seat_num == 4)
            is_aisle_facing_right = (seat_num == 12)
            if is_aisle_facing_left or is_aisle_facing_right:
                panel_x = x_pos + (0.34 if is_aisle_facing_left else -0.34)
                aisle_panel = create_box(f"{obj_name}_AislePanel", [panel_x, y_center + 0.05, seat_z + 0.50],
                                         [0.03, 0.48, 0.56], row_col, mat_polymer, bevel_width=0.01)
                # Glowing warm row letter badge
                badge = create_cylinder(f"{obj_name}_RowBadge", [panel_x + (0.016 if is_aisle_facing_left else -0.016), y_center - 0.08, seat_z + 0.62],
                                        0.055, 0.015, row_col, mat_aisle_badge, rotation_euler=(0, math.radians(90), 0))
                sub_objects.extend([aisle_panel, badge])

            # Parent all components preserving world coordinates
            for sub in sub_objects:
                sub.parent = seat_root
                sub.matrix_parent_inverse = seat_root.matrix_world.inverted()

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

    print(f" -> Generated {len(metadata_seats)} verified photorealistic seats with ergonomic contours.")

    # 7. Build INTERACTION_HELPERS & Anchors as Blender Empties
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
        ("HELPER_PROJECTOR_BOOTH", [0.0, 18.8, 6.2]),
    ]
    for h_name, h_loc in helpers:
        create_helper_empty(h_name, h_loc, helpers_col)

    # 8. Setup LIGHTING & ATMOSPHERIC PROJECTOR BEAM
    # A. Projector Booth Glass Window in Rear Wall
    create_box("PROJECTOR_BOOTH_FRAME", [0.0, 18.92, 6.2], [0.80, 0.06, 0.50], lighting_col, mat_polymer, bevel_width=0.01)
    create_box("PROJECTOR_LENS_PORT", [0.0, 18.88, 6.2], [0.60, 0.02, 0.35], lighting_col, mat_step_led)

    # B. Volumetric Cinematic Projector Beam Light (Cuts through atmosphere)
    proj_light = bpy.data.lights.new(name="LIGHT_PROJECTOR_BEAM", type="SPOT")
    proj_light.energy = 4200.0
    proj_light.color = (0.90, 0.94, 1.0)
    proj_light.spot_size = math.radians(48.0)
    proj_light.spot_blend = 0.25
    proj_light.shadow_soft_size = 0.05
    obj_proj = bpy.data.objects.new(name="LIGHT_PROJECTOR_BEAM", object_data=proj_light)
    obj_proj.location = (0.0, 18.8, 6.2)
    dir_proj = mathutils.Vector((0.0, screen_y, screen_z)) - mathutils.Vector((0.0, 18.8, 6.2))
    obj_proj.rotation_euler = dir_proj.to_track_quat('-Z', 'Y').to_euler()
    lighting_col.objects.link(obj_proj)

    # C. Recessed Ceiling Downlights (Dimmed warm golden cove lighting)
    for c_y in [4.0, 7.5, 11.0, 15.0]:
        for c_x in [-5.0, 0.0, 5.0]:
            c_light = bpy.data.lights.new(name=f"LIGHT_DOWNLIGHT_{c_x}_{c_y}", type="POINT")
            c_light.energy = 220.0
            c_light.shadow_soft_size = 0.35
            c_light.color = (1.0, 0.92, 0.82)
            obj_c = bpy.data.objects.new(name=f"LIGHT_DOWNLIGHT_{c_x}_{c_y}", object_data=c_light)
            obj_c.location = (c_x, c_y, aud_height - 0.25)
            lighting_col.objects.link(obj_c)

    # D. Architectural Wall Grazing Sconces on Acoustic Panels
    for s_idx in range(4):
        s_y = 3.5 + s_idx * 3.5
        for s_x in [-aud_width / 2.0 + 0.16, aud_width / 2.0 - 0.16]:
            create_box(f"SCONCE_CHASSIS_{s_x:.1f}_{s_y:.1f}", [s_x, s_y, 4.0], [0.12, 0.22, 0.48],
                       lighting_col, mat_trim_brass, bevel_width=0.01)

            w_down = bpy.data.lights.new(name=f"LIGHT_SCONCE_DOWN_{s_x:.1f}_{s_y:.1f}", type="SPOT")
            w_down.energy = 110.0
            w_down.color = (1.0, 0.84, 0.55)
            w_down.spot_size = math.radians(65)
            w_down.spot_blend = 0.4
            obj_w_down = bpy.data.objects.new(name=w_down.name, object_data=w_down)
            obj_w_down.location = (s_x + (0.08 if s_x < 0 else -0.08), s_y, 3.8)
            obj_w_down.rotation_euler = (0, 0, 0)
            lighting_col.objects.link(obj_w_down)

            w_up = bpy.data.lights.new(name=f"LIGHT_SCONCE_UP_{s_x:.1f}_{s_y:.1f}", type="SPOT")
            w_up.energy = 90.0
            w_up.color = (1.0, 0.84, 0.55)
            w_up.spot_size = math.radians(60)
            w_up.spot_blend = 0.4
            obj_w_up = bpy.data.objects.new(name=w_up.name, object_data=w_up)
            obj_w_up.location = (s_x + (0.08 if s_x < 0 else -0.08), s_y, 4.2)
            obj_w_up.rotation_euler = (math.radians(180), 0, 0)
            lighting_col.objects.link(obj_w_up)

    # 9. Setup Multi-Camera System with Physical Depth of Field
    print("[6/6] Configuring Multi-Camera System with Photographic Depth of Field...")

    # Camera 1: Overview (High rear angle looking down auditorium toward screen)
    cam_overview_data = bpy.data.cameras.new("CAM_OVERVIEW")
    cam_overview_data.lens = 24.0
    cam_overview_data.clip_start = 0.1
    cam_overview_data.clip_end = 150.0
    cam_overview_data.dof.use_dof = True
    cam_overview_data.dof.focus_distance = 11.0
    cam_overview_data.dof.aperture_fstop = 8.0
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
    cam_stage_data.dof.use_dof = True
    cam_stage_data.dof.focus_distance = 9.5
    cam_stage_data.dof.aperture_fstop = 5.6
    cam_stage_obj = bpy.data.objects.new("CAM_SCREEN_FACING", cam_stage_data)
    cam_stage_obj.location = (0.0, -1.8, 1.2)
    target_stage = mathutils.Vector((0.0, 7.5, 2.4))
    cam_stage_obj.rotation_euler = (target_stage - cam_stage_obj.location).to_track_quat('-Z', 'Y').to_euler()
    cameras_col.objects.link(cam_stage_obj)

    # Camera 3: Seat Preview (Row D, Seat 8 - prime center sweet-spot seat)
    prime_seat = [s for s in metadata_seats if s["seat_id"] == "D-008"][0]
    cam_seat_data = bpy.data.cameras.new("CAM_SEAT_PREVIEW_D08")
    cam_seat_data.lens = 20.0  # Ultra-wide 20mm cinema viewer perspective
    cam_seat_data.clip_start = 0.1
    cam_seat_data.clip_end = 150.0
    cam_seat_data.dof.use_dof = True
    cam_seat_data.dof.focus_distance = 9.9  # Exact distance to screen center
    cam_seat_data.dof.aperture_fstop = 4.0  # Soft photographic defocus on Row C in foreground!
    cam_seat_obj = bpy.data.objects.new("CAM_SEAT_PREVIEW_D08", cam_seat_data)
    cam_seat_obj.location = tuple(prime_seat["eye_point"])
    target_screen_view = mathutils.Vector((0.0, screen_y, screen_z - 0.45))
    cam_seat_obj.rotation_euler = (target_screen_view - cam_seat_obj.location).to_track_quat('-Z', 'Y').to_euler()
    cameras_col.objects.link(cam_seat_obj)

    # 10. Save Master .blend File
    blend_path = OUTPUT_DIR / "cinema_theatre_auditorium.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f" -> Master Blender project saved: {blend_path}")

    # 11. Export Optimized Web-Ready GLB
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
    print(f" -> GLB exported successfully: {glb_size:,} bytes ({glb_size / 1024 / 1024:.2f} MB)")

    # 12. Save Normalized Seat & Layout Metadata JSON
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
            "film_still_texture": "cinema_screen_film_still.png",
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
        "version": "1.1.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "author": "Antigravity AI 3D Technical Artist",
        "license": "Multi-Cinema Platform Production License",
        "units": "meters",
        "blender_version": bpy.app.version_string,
        "files": {
            "blend_source": "cinema_theatre_auditorium.blend",
            "web_glb": "cinema_theatre_auditorium.glb",
            "layout_metadata": "cinema_layout_metadata.json",
            "film_still": "cinema_screen_film_still.png",
        },
        "file_sizes_bytes": {
            "blend": blend_path.stat().st_size,
            "glb": glb_size,
            "metadata": metadata_path.stat().st_size,
            "film_still": FILM_STILL_PATH.stat().st_size,
        },
        "sha256": {
            "glb": hashlib.sha256(glb_path.read_bytes()).hexdigest(),
        },
    }
    manifest_path = OUTPUT_DIR / "cinema_asset_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f" -> Asset manifest written: {manifest_path}")

    # 14. High-Fidelity Path Tracing Render Setup with Cycles OptiX
    print("\n" + "-" * 60)
    print(" CONFIGURING CYCLES OPTIX GPU PATH TRACER FOR PHOTOREALISM")
    print("-" * 60)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "GPU"

    # Configure OptiX GPU acceleration
    cycles_prefs = bpy.context.preferences.addons["cycles"].preferences
    cycles_prefs.compute_device_type = "OPTIX"
    cycles_prefs.get_devices()
    for d in cycles_prefs.devices:
        if d.type == "OPTIX":
            d.use = True
            print(f" -> Enabled OptiX device: {d.name}")
        else:
            d.use = False

    # Path tracing quality settings
    scene.cycles.samples = 256
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPTIX"
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 4

    # Color Management: AgX with High Contrast for cinematic film grade
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - High Contrast"

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
        print(f" -> Path-tracing {fname} from {cam_obj.name} with Cycles OptiX (256 samples)...")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        t_elapsed = time.time() - t0
        print(f"    Saved: {r_path} ({r_path.stat().st_size:,} bytes) in {t_elapsed:.1f}s")

    print("\n" + "=" * 75)
    print(" PHOTOREALISTIC CINEMA BUILD & CYCLES RENDERS COMPLETED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    build_cinema_photoreal()
