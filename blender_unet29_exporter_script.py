import bpy
import math
import os
import re
from mathutils import Vector
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

CAMERA_SETTINGS = {
    "render_resolution": 1536,   # square output
    "focal_length": 50.0,        # mm
    "sensor_width": 36.0,        # mm
    "sensor_height": 36.0,       # mm
    "clip_start": 0.01,
    "clip_end": 10000.0,
    "coverage_padding": 1.15,    # small margin to prevent edge clipping (1.0 = exact fit)
    "min_distance_multiplier": 1.5,
}

# 8 cameras: single ring at center height (turnaround)
# Smart framing: calculates optimal distance across all views to maximize mesh size
# while ensuring perfect turnaround without any clipping
CAMERA_GROUPS = {
    "turnaround": {"count": 8, "elevation_angle": 0},
}

# TexTools bake modes we want to run (keys must match TexTools' internal modes)
BAKING_MODES = {
    "position":   {"resolution": 512},
    "paint_base": {"resolution": 512},
    "base_color": {"resolution": 512},
    "wireframe":  {"resolution": 4096, "wireframe_size": 0.61},
}

# Folder relative to the .blend file - NEW STRUCTURE FOR UNET
OUTPUT_PATH = "//blender_outputs/blender_unet29_exporter_script/"

# ============================================================
# Small utils
# ============================================================

def ensure_dir(path):
    abspath = bpy.path.abspath(path)
    if not os.path.exists(abspath):
        os.makedirs(abspath)
    return abspath

def strip_numeric_suffix(name: str) -> str:
    """
    Blender autoincrement suffix, e.g., 'Cube.001' -> 'Cube'
    """
    return re.sub(r"\.\d{3}$", "", name)

def sanitize_filename(name: str) -> str:
    """
    Clean filename: only alphanumeric and underscores allowed.
    Replace any other character with underscore.
    """
    # Replace any non-alphanumeric character (except underscore) with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Remove any duplicate underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized

def generate_timestamp() -> str:
    """
    Generate a unique timestamp string for filename uniqueness.
    Format: YYYYMMDD_HHMMSS
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def to_set_name(obj: bpy.types.Object) -> str:
    """
    Reproduces TexTools' grouping base name as closely as possible for simple cases:
    - Parent name if the parent is selected, else object's name
    - Lowercased, numeric suffix removed
    """
    base = strip_numeric_suffix(obj.name)
    return base.lower()

# ============================================================
# Visibility management
# ============================================================

def hide_all_meshes_except(target_obj):
    """
    Hide all mesh objects except the target for rendering, return dict of original states
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
    Restore original visibility states
    """
    for obj, states in visibility_states.items():
        if obj and obj.name in bpy.data.objects:
            obj.hide_viewport = states['hide_viewport']
            obj.hide_render = states['hide_render']

# ============================================================
# Bounding box & camera placement
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

def optimal_distance(radius, focal_len, sensor_size, padding):
    """Calculate optimal camera distance based on radius."""
    if radius <= 0:
        return CAMERA_SETTINGS["min_distance_multiplier"]
    fov = 2.0 * math.atan((sensor_size * 0.5) / focal_len)
    dist = radius / math.sin(fov * 0.5)
    dist *= padding
    return max(dist, CAMERA_SETTINGS["min_distance_multiplier"] * radius)

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
    
    # Get all 8 corners of bounding box (already in world space from bounds calculation)
    # We need to recalculate them relative to the view center
    mw = bounds.get("matrix_world")
    bb = bounds.get("bound_box")
    
    # If we don't have these, use the dimensions
    # Project bounding box corners onto the view plane
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

def calculate_optimal_turnaround_distance(bounds, azimuth_angles):
    """
    Calculate the optimal distance that works for all camera angles in the turnaround.
    Returns the distance that ensures no clipping in any view while maximizing mesh size.
    """
    focal_len = CAMERA_SETTINGS["focal_length"]
    sensor_size = min(CAMERA_SETTINGS["sensor_width"], CAMERA_SETTINGS["sensor_height"])
    padding = CAMERA_SETTINGS["coverage_padding"]
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
    min_dist = CAMERA_SETTINGS["min_distance_multiplier"] * bounds["radius"]
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

def create_temp_camera(name, location, target):
    """
    Create temporary camera pointing at target.
    target: typically world origin (0,0,0)
    """
    cam_data = bpy.data.cameras.new(name=name)
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam_obj)

    cam = cam_obj.data
    cam.lens = CAMERA_SETTINGS["focal_length"]
    cam.sensor_width = CAMERA_SETTINGS["sensor_width"]
    cam.sensor_height = CAMERA_SETTINGS["sensor_height"]
    cam.clip_start = CAMERA_SETTINGS["clip_start"]
    cam.clip_end = CAMERA_SETTINGS["clip_end"]

    empty = bpy.data.objects.new(name + "_target", None)
    bpy.context.collection.objects.link(empty)
    empty.location = target

    con = cam_obj.constraints.new(type="TRACK_TO")
    con.target = empty
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'

    cam_obj.location = location
    return cam_obj, empty

def cleanup_temp(objects):
    for obj in objects:
        if obj and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

def render_from_camera(camera, filepath, res):
    scene = bpy.context.scene
    prev = {
        "camera": scene.camera,
        "resx": scene.render.resolution_x,
        "resy": scene.render.resolution_y,
        "filepath": scene.render.filepath,
        "engine": scene.render.engine,
        "film_transparent": scene.render.film_transparent,
        "world_bg": scene.world.node_tree.nodes["Background"].inputs[0].default_value[:] if scene.world and scene.world.use_nodes else None,
    }
    try:
        scene.camera = camera
        scene.render.resolution_x = res
        scene.render.resolution_y = res
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

def ensure_uv(obj):
    if not obj.data.uv_layers:
        sel_state = [o for o in bpy.context.selected_objects]
        active_prev = bpy.context.view_layer.objects.active

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')
        for o in sel_state:
            o.select_set(True)
        bpy.context.view_layer.objects.active = active_prev

# ============================================================
# TexTools interop
# ============================================================

def set_textools_mode(mode_key: str, resolution: int, wireframe_size: float = None):
    """Set TexTools bake mode and parameters"""
    bpy.context.scene.TT_bake_mode = f"{mode_key}.bip"
    tt = getattr(bpy.context.scene, "texToolsSettings", None)
    if tt:
        tt.size = (resolution, resolution)
        if mode_key == "wireframe" and wireframe_size is not None:
            tt.bake_wireframe_size = wireframe_size

def textools_organize_sets():
    """Build TexTools internal sets from current selection"""
    try:
        bpy.ops.uv.textools_bake_organize_names()
    except Exception as e:
        print(f"    Note: organize_names had issue: {e}")

def textools_bake():
    """Call TexTools bake operator"""
    bpy.ops.uv.textools_bake()

def find_baked_image(mesh_obj: bpy.types.Object, mode_key: str):
    """Find the baked texture image for a specific mesh and mode"""
    set_name = to_set_name(mesh_obj)
    exact = f"{set_name}_{mode_key}"
    
    img = bpy.data.images.get(exact)
    if img:
        return img
    
    # Try variants
    candidates = []
    for image in bpy.data.images:
        n = image.name.lower()
        if mode_key in n and (set_name in n or n == mode_key):
            candidates.append(image)
    
    if candidates:
        # Prefer highest resolution
        def _res_key(im):
            try:
                return (im.size[0] * im.size[1], im.size[0], im.size[1])
            except:
                return (0, 0, 0)
        candidates.sort(key=_res_key, reverse=True)
        return candidates[0]
    return None

def save_image(img: bpy.types.Image, out_dir: str, basename: str) -> str:
    path = os.path.join(out_dir, f"{basename}.png")
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    return path

def create_emission_material(image):
    """Create emission material for unlit bright rendering"""
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

# ============================================================
# Batch Baking
# ============================================================

def batch_bake_all_textures(selected_meshes):
    """
    Bake all textures for all meshes at once.
    TexTools will automatically process all meshes in the scene.
    Returns a dict mapping (mesh_obj, mode_key) -> image
    """
    print("\n" + "="*60)
    print("BATCH BAKING ALL TEXTURES")
    print("="*60)
    
    # Ensure all meshes have UVs first
    for obj in selected_meshes:
        ensure_uv(obj)
    
    # Make sure all meshes are selected for TexTools
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected_meshes:
        obj.select_set(True)
    if selected_meshes:
        bpy.context.view_layer.objects.active = selected_meshes[0]
    
    # Dictionary to store baked images
    baked_images = {}
    
    # Bake each mode ONCE for ALL meshes
    for mode_key, cfg in BAKING_MODES.items():
        print(f"\n  Batch baking mode: {mode_key}")
        res = cfg["resolution"]
        wireframe_size = cfg.get("wireframe_size", None)
        
        # Configure TexTools
        set_textools_mode(mode_key, res, wireframe_size)
        textools_organize_sets()
        
        print(f"    Baking all meshes for {mode_key}...")
        try:
            textools_bake()
            print(f"    ✓ Batch bake complete for {mode_key}")
            
            # Now find and save all the baked images
            for mesh_obj in selected_meshes:
                img = find_baked_image(mesh_obj, mode_key)
                if img:
                    baked_images[(mesh_obj, mode_key)] = img
                    print(f"      Found image for {mesh_obj.name}: {img.name}")
                else:
                    print(f"      ✗ Could not find image for {mesh_obj.name}")
                    
        except Exception as e:
            print(f"    Bake error for {mode_key}: {e}")
    
    print(f"\n  ✓ Batch baking complete. Found {len(baked_images)} images.")
    return baked_images

# ============================================================
# Rendering - MODIFIED FOR UNET DATASET FORMAT
# ============================================================

def render_all_views_unet(mesh_obj, bounds, position_dir, wireframe_dir, pointbase_dir, baked_images, timestamp):
    """
    Render from 8 camera positions in UNET format (turnaround):
    - position_dir: contains {mesh_name}_{timestamp}_view{XX}.png (position maps)
    - wireframe_dir: contains {mesh_name}_{timestamp}_view{XX}.png (wireframe targets)
    - pointbase_dir: contains {mesh_name}_{timestamp}_view{XX}.png (pointbase maps)
    
    View numbering: 00-07
    - All at center height (0° elevation)
    - Azimuth: 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°
    - Rotation center: world origin X,Y (0, 0) but mesh height Z
    - timestamp: unique identifier shared across all views of this mesh
    - Distance: optimized across all 8 views for maximum mesh size without clipping
    """
    # Target point: world origin XY, mesh center Z
    target_point = Vector((0, 0, bounds["center"].z))
    temp_objs = []
    
    # Ensure mesh is visible for rendering
    mesh_obj.hide_viewport = False
    mesh_obj.hide_render = False
    
    # Sanitize mesh name for filenames
    clean_name = sanitize_filename(mesh_obj.name)
    
    # Get baked textures
    position_img = baked_images.get((mesh_obj, "position"))
    wireframe_img = baked_images.get((mesh_obj, "wireframe"))
    pointbase_img = baked_images.get((mesh_obj, "paint_base"))
    
    if not position_img:
        print(f"    ✗ No position texture found for {mesh_obj.name}")
        return
    if not wireframe_img:
        print(f"    ✗ No wireframe texture found for {mesh_obj.name}")
        return
    if not pointbase_img:
        print(f"    ✗ No paint_base texture found for {mesh_obj.name}")
        return
    
    # Create materials once
    position_mat = create_emission_material(position_img)
    wireframe_mat = create_emission_material(wireframe_img)
    pointbase_mat = create_emission_material(pointbase_img)
    
    # Store original materials
    orig_mats = [m for m in mesh_obj.data.materials]
    
    # Calculate optimal distance for perfect turnaround (checks all 8 angles)
    azimuth_angles = [i * 45.0 for i in range(8)]  # 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°
    optimal_dist = calculate_optimal_turnaround_distance(bounds, azimuth_angles)
    print(f"    Optimal distance: {optimal_dist:.2f} (maximizes mesh size across all views)")
    
    # Render all 8 views using the same optimal distance
    elevation = 0  # All cameras at center height
    for view_idx in range(8):
        az = azimuth_angles[view_idx]
        loc = cam_position(bounds["center"], optimal_dist, az, elevation)
        
        cam, tgt = create_temp_camera(
            f"TT_Camera_view{view_idx:02d}", loc, target_point
        )
        temp_objs += [cam, tgt]
        
        # Render POSITION view
        mesh_obj.data.materials.clear()
        mesh_obj.data.materials.append(position_mat)
        outfile_pos = os.path.join(position_dir, f"{clean_name}_{timestamp}_view{view_idx:02d}.png")
        render_from_camera(cam, outfile_pos, CAMERA_SETTINGS["render_resolution"])
        
        # Render WIREFRAME view
        mesh_obj.data.materials.clear()
        mesh_obj.data.materials.append(wireframe_mat)
        outfile_wire = os.path.join(wireframe_dir, f"{clean_name}_{timestamp}_view{view_idx:02d}.png")
        render_from_camera(cam, outfile_wire, CAMERA_SETTINGS["render_resolution"])
        
        # Render POINTBASE view
        mesh_obj.data.materials.clear()
        mesh_obj.data.materials.append(pointbase_mat)
        outfile_pb = os.path.join(pointbase_dir, f"{clean_name}_{timestamp}_view{view_idx:02d}.png")
        render_from_camera(cam, outfile_pb, CAMERA_SETTINGS["render_resolution"])
    
    # Cleanup
    cleanup_temp(temp_objs)
    
    # Restore original materials
    mesh_obj.data.materials.clear()
    for m in orig_mats:
        if m:
            mesh_obj.data.materials.append(m)
    
    # Clean up temp materials
    if position_mat.name in bpy.data.materials:
        bpy.data.materials.remove(position_mat, do_unlink=True)
    if wireframe_mat.name in bpy.data.materials:
        bpy.data.materials.remove(wireframe_mat, do_unlink=True)
    if pointbase_mat.name in bpy.data.materials:
        bpy.data.materials.remove(pointbase_mat, do_unlink=True)

def process_mesh_unet(mesh_obj: bpy.types.Object, base_out: str, 
                      position_dir: str, wireframe_dir: str, pointbase_dir: str,
                      textures_dir: str, baked_images: dict):
    """Process a single mesh for UNET dataset"""
    print("\n" + "="*60)
    print(f"Processing mesh: {mesh_obj.name}")
    print("="*60)

    bounds = get_object_bounds(mesh_obj)
    
    # Generate unique timestamp for this mesh
    timestamp = generate_timestamp()
    
    # Sanitize mesh name for filenames
    clean_name = sanitize_filename(mesh_obj.name)
    
    # Save baked textures to textures directory (for reference/debugging)
    for mode_key in BAKING_MODES.keys():
        img = baked_images.get((mesh_obj, mode_key))
        if img:
            saved_path = save_image(img, textures_dir, f"{clean_name}_{timestamp}_{mode_key}")
            print(f"  ✓ Saved texture: {os.path.basename(saved_path)}")
    
    # Hide other objects for rendering
    visibility_states = hide_all_meshes_except(mesh_obj)
    
    try:
        print(f"  Rendering 8 views (timestamp: {timestamp})...")
        render_all_views_unet(mesh_obj, bounds, position_dir, wireframe_dir, pointbase_dir, baked_images, timestamp)
        print("  ✓ Views complete.")
    finally:
        # Restore visibility
        restore_visibility(visibility_states)

    print(f"\n✓ Completed: {mesh_obj.name}")
    print(f"  - Position views: {position_dir}/{clean_name}_{timestamp}_view*.png")
    print(f"  - Wireframe views: {wireframe_dir}/{clean_name}_{timestamp}_view*.png")
    print(f"  - Pointbase views: {pointbase_dir}/{clean_name}_{timestamp}_view*.png")

# ============================================================
# Main
# ============================================================

def main():
    if not hasattr(bpy.context.scene, "TT_bake_mode"):
        print("ERROR: TexTools not installed/enabled.")
        return

    selected = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not selected:
        print("No mesh objects selected.")
        return

    # Setup UNET directory structure
    base_out = ensure_dir(OUTPUT_PATH)
    position_dir = ensure_dir(os.path.join(base_out, "position"))
    wireframe_dir = ensure_dir(os.path.join(base_out, "wireframe"))
    pointbase_dir = ensure_dir(os.path.join(base_out, "pointbase"))
    textures_dir = ensure_dir(os.path.join(base_out, "textures"))
    
    print("\n" + "="*60)
    print("UNET DATASET GENERATION")
    print("="*60)
    print(f"Output structure:")
    print(f"  - Base: {base_out}")
    print(f"  - Position maps: {position_dir}")
    print(f"  - Wireframe targets: {wireframe_dir}")
    print(f"  - Pointbase maps: {pointbase_dir}")
    print(f"  - Textures (backup): {textures_dir}")
    print(f"Selected meshes: {len(selected)}")
    print(f"Camera setup: 8-view turnaround with smart framing")
    print("="*60)
    
    # Store initial state
    initial_selection = selected.copy()
    active_prev = bpy.context.view_layer.objects.active
    mode_prev = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    
    # Ensure object mode
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    try:
        # STEP 1: Batch bake ALL textures for ALL meshes at once
        baked_images = batch_bake_all_textures(selected)
        
        # STEP 2: Process each mesh for rendering and saving
        for idx, obj in enumerate(selected, 1):
            print(f"\n[{idx}/{len(selected)}] {obj.name}")
            process_mesh_unet(obj, base_out, position_dir, wireframe_dir, pointbase_dir,
                            textures_dir, baked_images)
            
    finally:
        # Restore initial selection
        bpy.ops.object.select_all(action='DESELECT')
        for o in initial_selection:
            if o and o.name in bpy.data.objects:
                o.select_set(True)
        if active_prev and active_prev.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = active_prev

    print("\n" + "="*60)
    print("DATASET GENERATION COMPLETE")
    print("="*60)
    print(f"\nTo train with this dataset:")
    print(f"  Single-view mode:")
    print(f"    python unet29.py --mode train \\")
    print(f"      --input-dir {position_dir} \\")
    print(f"      --target-dir {wireframe_dir} \\")
    print(f"      --use-pointbase")
    print(f"\n  Multi-view mode:")
    print(f"    python unet29.py --mode train \\")
    print(f"      --input-dir {position_dir} \\")
    print(f"      --target-dir {wireframe_dir} \\")
    print(f"      --use-pointbase \\")
    print(f"      --multiview")
    print("="*60)

if __name__ == "__main__":
    main()