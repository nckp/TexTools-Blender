"""
Rendering Engine - Multi-view camera rendering
===============================================

This module handles camera placement and rendering, preserving all the
camera logic from the original script with smart framing optimization.
"""

import bpy
import math
import os
from mathutils import Vector


# ============================================================
# Camera Calculations (Preserved from original script)
# ============================================================

def get_object_bounds(obj):
    """Get object bounding box information in world space."""
    mw = obj.matrix_world
    corners = [mw @ Vector(c) for c in obj.bound_box]
    center = sum(corners, Vector()) / 8.0
    minv = Vector((min(v.x for v in corners),
                   min(v.y for v in corners),
                   min(v.z for v in corners)))
    maxv = Vector((max(v.x for v in corners),
                   max(v.y for v in corners),
                   max(v.z for v in corners)))
    dims = maxv - minv
    radius = max((v - center).length for v in corners)
    return {
        "center": center,
        "dimensions": dims,
        "radius": radius,
        "bound_box": obj.bound_box,
        "matrix_world": mw
    }


def calculate_max_extent_from_angle(bounds, azim_deg, elev_deg):
    """
    Calculate the maximum extent (effective radius) of the bounding box
    when viewed from a specific angle.
    """
    center = bounds["center"]

    # Create rotation matrix for this viewing angle
    az = math.radians(azim_deg)
    el = math.radians(elev_deg)

    # Calculate view direction (from camera to target)
    view_dir = Vector((
        -math.cos(el) * math.cos(az),
        -math.cos(el) * math.sin(az),
        -math.sin(el)
    )).normalized()

    # Calculate right and up vectors for this view
    world_up = Vector((0, 0, 1))
    if abs(view_dir.z) > 0.99:  # Nearly vertical
        world_up = Vector((0, 1, 0))

    right = view_dir.cross(world_up).normalized()
    up = right.cross(view_dir).normalized()

    # Get all 8 corners of bounding box
    corners_world = [
        center + Vector((
            dx * bounds["dimensions"].x / 2,
            dy * bounds["dimensions"].y / 2,
            dz * bounds["dimensions"].z / 2
        ))
        for dx in [-1, 1]
        for dy in [-1, 1]
        for dz in [-1, 1]
    ]

    # Project each corner onto the camera's right and up axes
    max_extent = 0
    for corner in corners_world:
        # Vector from center to corner
        offset = corner - center

        # Project onto right and up axes (these give us 2D screen space coords)
        x_proj = abs(offset.dot(right))
        y_proj = abs(offset.dot(up))

        # Maximum extent in either direction
        extent = max(x_proj, y_proj)
        max_extent = max(max_extent, extent)

    return max_extent


def calculate_optimal_turnaround_distance(bounds, azimuth_angles, focal_len, sensor_size, padding, min_dist_mult):
    """
    Calculate the optimal distance that works for all camera angles in the turnaround.
    Returns the distance that ensures no clipping in any view while maximizing mesh size.
    """
    elevation = 0  # All turnaround cameras at same elevation

    max_required_distance = 0

    # Check each angle in the turnaround
    for azim in azimuth_angles:
        # Calculate the effective radius (max extent) for this viewing angle
        extent = calculate_max_extent_from_angle(bounds, azim, elevation)

        # Calculate required distance for this extent
        fov = 2.0 * math.atan((sensor_size * 0.5) / focal_len)
        dist = extent / math.sin(fov * 0.5)
        dist *= padding

        max_required_distance = max(max_required_distance, dist)

    # Ensure minimum distance
    min_dist = min_dist_mult * bounds["radius"]
    return max(max_required_distance, min_dist)


def cam_position(center, distance, azim_deg, elev_deg):
    """
    Calculate camera position using pre-calculated distance.
    - X, Y: always uses world origin (0, 0) for rotation center
    - Z: uses mesh's calculated center height
    - distance: pre-calculated optimal distance
    """
    az = math.radians(azim_deg)
    el = math.radians(elev_deg)

    # Use world origin for XY, mesh center for Z
    target_point = Vector((0, 0, center.z))
    x = target_point.x + distance * math.cos(el) * math.cos(az)
    y = target_point.y + distance * math.cos(el) * math.sin(az)
    z = target_point.z + distance * math.sin(el)
    return Vector((x, y, z))


def create_temp_camera(name, location, target, settings):
    """
    Create temporary camera pointing at target.

    Args:
        name: Camera name
        location: Camera location
        target: Target point to look at
        settings: UNetExporterSettings

    Returns:
        Tuple of (camera_object, target_empty)
    """
    cam_data = bpy.data.cameras.new(name=name)
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam_obj)

    cam = cam_obj.data
    cam.lens = settings.focal_length
    cam.sensor_width = 36.0
    cam.sensor_height = 36.0
    cam.clip_start = 0.01
    cam.clip_end = 10000.0

    empty = bpy.data.objects.new(name + "_target", None)
    bpy.context.collection.objects.link(empty)
    empty.location = target

    con = cam_obj.constraints.new(type="TRACK_TO")
    con.target = empty
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'

    cam_obj.location = location
    return cam_obj, empty


def cleanup_temp_objects(objects):
    """Remove temporary objects from the scene"""
    for obj in objects:
        if obj and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)


# ============================================================
# Visibility Management
# ============================================================

def hide_all_meshes_except(target_obj):
    """
    Hide all mesh objects except the target for rendering.

    Args:
        target_obj: Object to keep visible

    Returns:
        Dict of original visibility states
    """
    visibility_states = {}
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj != target_obj:
            visibility_states[obj] = {
                'hide_viewport': obj.hide_viewport,
                'hide_render': obj.hide_render
            }
            obj.hide_viewport = True
            obj.hide_render = True
    return visibility_states


def restore_visibility(visibility_states):
    """
    Restore original visibility states.

    Args:
        visibility_states: Dict of original states from hide_all_meshes_except
    """
    for obj, states in visibility_states.items():
        if obj and obj.name in bpy.data.objects:
            obj.hide_viewport = states['hide_viewport']
            obj.hide_render = states['hide_render']


# ============================================================
# Material & Rendering
# ============================================================

def create_emission_material(image):
    """
    Create emission material for unlit bright rendering.

    Args:
        image: Image texture to use

    Returns:
        Created material
    """
    mat_name = f"Preview_Emission_{image.name}"
    if mat_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[mat_name], do_unlink=True)

    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (300, 0)

    emission_node = nodes.new("ShaderNodeEmission")
    emission_node.location = (0, 0)
    emission_node.inputs['Strength'].default_value = 1.0

    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.location = (-300, 0)
    tex_node.image = image

    links.new(tex_node.outputs["Color"], emission_node.inputs["Color"])
    links.new(emission_node.outputs["Emission"], output_node.inputs["Surface"])

    return mat


def render_from_camera(camera, filepath, resolution):
    """
    Render from a specific camera.

    Args:
        camera: Camera object
        filepath: Output file path
        resolution: Render resolution (square)
    """
    scene = bpy.context.scene

    # Store previous settings
    prev = {
        "camera": scene.camera,
        "resx": scene.render.resolution_x,
        "resy": scene.render.resolution_y,
        "filepath": scene.render.filepath,
        "engine": scene.render.engine,
        "film_transparent": scene.render.film_transparent,
        "world_bg": None
    }

    # Store world background
    if scene.world and scene.world.use_nodes:
        bg_node = scene.world.node_tree.nodes.get("Background")
        if bg_node:
            prev["world_bg"] = tuple(bg_node.inputs[0].default_value)

    try:
        scene.camera = camera
        scene.render.resolution_x = resolution
        scene.render.resolution_y = resolution
        scene.render.filepath = filepath
        scene.render.image_settings.file_format = "PNG"

        # Use EEVEE for faster unlit rendering
        scene.render.engine = 'BLENDER_EEVEE_NEXT'

        # Set pure black background
        scene.render.film_transparent = False
        if scene.world:
            if not scene.world.use_nodes:
                scene.world.use_nodes = True
            bg_node = scene.world.node_tree.nodes.get("Background")
            if bg_node:
                bg_node.inputs[0].default_value = (0, 0, 0, 1)  # Pure black

        bpy.ops.render.render(write_still=True)

    finally:
        # Restore settings
        scene.camera = prev["camera"]
        scene.render.resolution_x = prev["resx"]
        scene.render.resolution_y = prev["resy"]
        scene.render.filepath = prev["filepath"]
        scene.render.engine = prev["engine"]
        scene.render.film_transparent = prev["film_transparent"]

        # Restore world background
        if prev["world_bg"] and scene.world and scene.world.use_nodes:
            bg_node = scene.world.node_tree.nodes.get("Background")
            if bg_node:
                bg_node.inputs[0].default_value = prev["world_bg"]


# ============================================================
# Multi-View Rendering
# ============================================================

def render_multiview_turnaround(obj, baked_images, output_dirs, settings, mesh_id):
    """
    Render multi-view turnaround for a mesh object.

    Args:
        obj: Mesh object to render
        baked_images: Dict of baked images {mode_name: image}
        output_dirs: Dict of output directories {mode_name: path}
        settings: UNetExporterSettings
        mesh_id: Unique identifier for this mesh (timestamp or hash)

    Returns:
        Number of views rendered
    """
    # Get bounds and calculate optimal distance
    bounds = get_object_bounds(obj)
    target_point = Vector((0, 0, bounds["center"].z))

    # Generate azimuth angles for turnaround
    camera_count = settings.camera_count
    azimuth_angles = [i * (360.0 / camera_count) for i in range(camera_count)]

    # Calculate optimal distance that works for all views
    optimal_dist = calculate_optimal_turnaround_distance(
        bounds,
        azimuth_angles,
        focal_len=settings.focal_length,
        sensor_size=36.0,
        padding=settings.coverage_padding,
        min_dist_mult=1.5
    )

    print(f"    Optimal distance: {optimal_dist:.2f} (maximizes mesh size across all views)")

    # Ensure mesh is visible
    obj.hide_viewport = False
    obj.hide_render = False

    # Hide other meshes
    visibility_states = hide_all_meshes_except(obj)

    # Store original materials
    orig_mats = [slot.material for slot in obj.material_slots]

    # Temporary objects to clean up
    temp_objs = []

    try:
        # For each bake mode, create emission material
        emission_materials = {}
        for mode_name, image in baked_images.items():
            if image:
                emission_materials[mode_name] = create_emission_material(image)

        # Render all views
        elevation = 0  # All cameras at center height
        for view_idx in range(camera_count):
            az = azimuth_angles[view_idx]
            loc = cam_position(bounds["center"], optimal_dist, az, elevation)

            # Create camera
            cam, tgt = create_temp_camera(
                f"TempCam_view{view_idx:02d}",
                loc,
                target_point,
                settings
            )
            temp_objs += [cam, tgt]

            # Render each mode
            for mode_name, image in baked_images.items():
                if mode_name not in emission_materials:
                    continue

                # Apply emission material
                obj.data.materials.clear()
                obj.data.materials.append(emission_materials[mode_name])

                # Render
                output_path = os.path.join(
                    output_dirs[mode_name],
                    f"{obj.name}_{mesh_id}_view{view_idx:02d}.png"
                )
                render_from_camera(cam, output_path, settings.render_resolution)

    finally:
        # Cleanup temp objects
        cleanup_temp_objects(temp_objs)

        # Restore materials
        obj.data.materials.clear()
        for mat in orig_mats:
            if mat:
                obj.data.materials.append(mat)

        # Clean up temp emission materials
        for mat in emission_materials.values():
            if mat.name in bpy.data.materials:
                bpy.data.materials.remove(mat, do_unlink=True)

        # Restore visibility
        restore_visibility(visibility_states)

    return camera_count


def save_baked_textures(baked_images, output_dir, mesh_name, mesh_id):
    """
    Save all baked textures to disk.

    Args:
        baked_images: Dict of baked images {mode_name: image}
        output_dir: Output directory path
        mesh_name: Mesh object name
        mesh_id: Unique identifier

    Returns:
        Dict of saved file paths
    """
    saved_paths = {}

    for mode_name, image in baked_images.items():
        if not image:
            continue

        filename = f"{mesh_name}_{mesh_id}_{mode_name}.png"
        filepath = os.path.join(output_dir, filename)

        image.filepath_raw = filepath
        image.file_format = 'PNG'
        image.save()

        saved_paths[mode_name] = filepath

    return saved_paths
