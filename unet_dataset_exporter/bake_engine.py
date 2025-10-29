"""
Baking Engine - Core texture baking functionality
==================================================

This module implements all texture baking modes without any dependency on TexTools.
Each bake mode creates the necessary shader nodes procedurally and performs Cycles baking.
"""

import bpy
import numpy as np
from mathutils import Vector


# ============================================================
# Material Creation Helpers
# ============================================================

def create_bake_material(name, setup_nodes_func):
    """
    Create a material for baking with a custom node setup function.

    Args:
        name: Material name
        setup_nodes_func: Function that sets up the shader nodes

    Returns:
        Created material
    """
    # Remove existing material if present
    if name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[name], do_unlink=True)

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True

    # Clear default nodes
    mat.node_tree.nodes.clear()

    # Setup custom nodes
    setup_nodes_func(mat.node_tree)

    return mat


def create_bake_image(name, width, height, color=(0, 0, 0, 1), is_float=True):
    """
    Create an image for baking.

    Args:
        name: Image name
        width: Image width
        height: Image height
        color: Background color (RGBA)
        is_float: Use 32-bit float format

    Returns:
        Created image
    """
    # Remove existing image if present
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name], do_unlink=True)

    img = bpy.data.images.new(
        name=name,
        width=width,
        height=height,
        alpha=True,
        float_buffer=is_float
    )

    # Set background color
    img.pixels = [pv for _ in range(width * height) for pv in color]
    img.colorspace_settings.name = 'Non-Color'  # Linear color space for data maps

    return img


def assign_bake_image_to_material(mat, image):
    """
    Add an image texture node to the material and make it active for baking.

    Args:
        mat: Material to modify
        image: Image to assign
    """
    tree = mat.node_tree

    # Create or get the bake image node
    if "BakeTarget" in tree.nodes:
        node = tree.nodes["BakeTarget"]
    else:
        node = tree.nodes.new("ShaderNodeTexImage")
        node.name = "BakeTarget"
        node.label = "Bake Target"

    node.image = image
    node.select = True
    tree.nodes.active = node


def apply_material_to_object(obj, mat):
    """
    Apply a material to an object, replacing all existing materials.

    Args:
        obj: Object to modify
        mat: Material to apply

    Returns:
        List of original materials (for restoration)
    """
    # Store original materials
    orig_mats = [slot.material for slot in obj.material_slots]

    # Clear and assign new material
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    return orig_mats


def restore_materials(obj, materials):
    """
    Restore original materials to an object.

    Args:
        obj: Object to modify
        materials: List of materials to restore
    """
    obj.data.materials.clear()
    for mat in materials:
        obj.data.materials.append(mat)


# ============================================================
# Shader Node Setups for Each Bake Mode
# ============================================================

def setup_position_nodes(tree):
    """
    Create nodes for world-space position baking.
    Encodes world XYZ position as RGB color.
    """
    # Geometry node for position
    geo_node = tree.nodes.new("ShaderNodeNewGeometry")
    geo_node.location = (-400, 0)

    # Emission shader (to output the position directly)
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (-200, 0)

    # Material output
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (0, 0)

    # Connect: Geometry.Position -> Emission.Color -> Output
    tree.links.new(geo_node.outputs['Position'], emission.inputs['Color'])
    tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])


def setup_wireframe_nodes(tree, thickness=0.01):
    """
    Create nodes for wireframe baking.

    Args:
        thickness: Wireframe line thickness
    """
    # Wireframe node
    wireframe = tree.nodes.new("ShaderNodeWireframe")
    wireframe.location = (-400, 0)
    wireframe.use_pixel_size = False
    wireframe.inputs['Size'].default_value = thickness

    # Color ramp to make lines solid
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 0)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)  # Black background
    ramp.color_ramp.elements[1].position = 0.01
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)  # White lines

    # Emission shader
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (0, 0)

    # Material output
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (200, 0)

    # Connect
    tree.links.new(wireframe.outputs['Fac'], ramp.inputs['Fac'])
    tree.links.new(ramp.outputs['Color'], emission.inputs['Color'])
    tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])


def setup_paint_base_nodes(tree):
    """
    Create nodes for paint base baking.
    This creates a gradient from Z-axis for base painting reference.
    """
    # Geometry node
    geo = tree.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-600, 0)

    # Separate XYZ to get Z coordinate
    separate = tree.nodes.new("ShaderNodeSeparateXYZ")
    separate.location = (-400, 0)

    # Map Range to normalize Z to 0-1 range
    map_range = tree.nodes.new("ShaderNodeMapRange")
    map_range.location = (-200, 0)
    map_range.inputs['From Min'].default_value = -10.0
    map_range.inputs['From Max'].default_value = 10.0
    map_range.inputs['To Min'].default_value = 0.0
    map_range.inputs['To Max'].default_value = 1.0

    # Color ramp for gradient
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (0, 0)
    ramp.color_ramp.elements[0].color = (0.1, 0.1, 0.2, 1)
    ramp.color_ramp.elements[1].color = (0.9, 0.9, 1.0, 1)

    # Emission
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (200, 0)

    # Output
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)

    # Connect
    tree.links.new(geo.outputs['Position'], separate.inputs['Vector'])
    tree.links.new(separate.outputs['Z'], map_range.inputs['Value'])
    tree.links.new(map_range.outputs['Result'], ramp.inputs['Fac'])
    tree.links.new(ramp.outputs['Color'], emission.inputs['Color'])
    tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])


def setup_normal_object_nodes(tree):
    """
    Create nodes for object-space normal baking.
    This is a standard Cycles bake, so we just need a simple output setup.
    """
    # For normal baking, Cycles handles the actual normal calculation
    # We just need a basic BSDF setup
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)

    tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])


def setup_base_color_nodes(tree):
    """
    Create nodes for base color baking.
    This extracts the base color from existing materials.
    """
    # For base color, we use the material's base color input
    # This is also a standard Cycles bake
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)

    tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])


def setup_ao_nodes(tree):
    """
    Create nodes for ambient occlusion baking.
    Standard Cycles AO bake.
    """
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)

    tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])


def setup_thickness_nodes(tree, distance=1.0):
    """
    Create nodes for thickness baking.
    Uses AO with inverted normals to calculate thickness.

    Args:
        distance: Maximum distance for thickness calculation
    """
    # Geometry for normal
    geo = tree.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-600, 0)

    # Vector math to invert normal
    vec_math = tree.nodes.new("ShaderNodeVectorMath")
    vec_math.location = (-400, 0)
    vec_math.operation = 'SCALE'
    vec_math.inputs[3].default_value = -1.0  # Scale by -1 to invert

    # AO node
    ao = tree.nodes.new("ShaderNodeAmbientOcclusion")
    ao.location = (-200, 0)
    ao.inputs['Distance'].default_value = distance
    ao.samples = 16

    # Emission
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (0, 0)

    # Output
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (200, 0)

    # Connect
    tree.links.new(geo.outputs['Normal'], vec_math.inputs[0])
    tree.links.new(vec_math.outputs['Vector'], ao.inputs['Normal'])
    tree.links.new(ao.outputs['Color'], emission.inputs['Color'])
    tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])


def setup_curvature_nodes(tree):
    """
    Create nodes for curvature baking.
    We'll bake normals first, then post-process for curvature.
    """
    # Curvature requires post-processing, so we just set up for normal bake
    setup_normal_object_nodes(tree)


# ============================================================
# Baking Functions
# ============================================================

def ensure_uv_map(obj):
    """
    Ensure the object has a UV map. Create one with smart unwrap if missing.

    Args:
        obj: Mesh object
    """
    if not obj.data.uv_layers:
        # Store context
        prev_active = bpy.context.view_layer.objects.active
        prev_mode = obj.mode if hasattr(obj, 'mode') else 'OBJECT'
        prev_selection = [o for o in bpy.context.selected_objects]

        # Setup for unwrap
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Unwrap
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Restore context
        bpy.ops.object.select_all(action='DESELECT')
        for o in prev_selection:
            if o.name in bpy.data.objects:
                o.select_set(True)
        if prev_active and prev_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = prev_active


def bake_cycles(obj, bake_type='EMIT', samples=1, margin=16, use_clear=True):
    """
    Execute Cycles baking operation.

    Args:
        obj: Object to bake
        bake_type: Cycles bake type
        samples: Number of samples
        margin: Pixel margin
        use_clear: Clear image before baking
    """
    # Store settings
    prev_engine = bpy.context.scene.render.engine
    prev_samples = bpy.context.scene.cycles.samples

    # Setup for baking
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = samples

    # Select object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Bake
    bpy.ops.object.bake(
        type=bake_type,
        use_clear=use_clear,
        margin=margin,
        use_selected_to_active=False,
    )

    # Restore settings
    bpy.context.scene.render.engine = prev_engine
    bpy.context.scene.cycles.samples = prev_samples


def bake_with_material(obj, mat_name, image_name, resolution, setup_func, bake_type='EMIT', samples=1, bg_color=(0,0,0,1)):
    """
    Generic baking function with custom material.

    Args:
        obj: Object to bake
        mat_name: Name for the material
        image_name: Name for the baked image
        resolution: Image resolution
        setup_func: Function to setup shader nodes
        bake_type: Cycles bake type
        samples: Render samples
        bg_color: Background color

    Returns:
        Baked image
    """
    # Ensure UV map
    ensure_uv_map(obj)

    # Create material and image
    mat = create_bake_material(mat_name, setup_func)
    img = create_bake_image(image_name, resolution, resolution, bg_color)

    # Assign bake target
    assign_bake_image_to_material(mat, img)

    # Apply material to object
    orig_mats = apply_material_to_object(obj, mat)

    try:
        # Bake
        bake_cycles(obj, bake_type=bake_type, samples=samples)
    finally:
        # Restore materials
        restore_materials(obj, orig_mats)
        # Clean up temp material
        if mat.name in bpy.data.materials:
            bpy.data.materials.remove(mat, do_unlink=True)

    return img


# ============================================================
# Public API - Individual Bake Functions
# ============================================================

def bake_position_map(obj, resolution=512):
    """Bake world-space position map"""
    return bake_with_material(
        obj,
        mat_name="TempMat_Position",
        image_name=f"{obj.name}_position",
        resolution=resolution,
        setup_func=setup_position_nodes,
        bake_type='EMIT',
        samples=1,
        bg_color=(0, 0, 0, 1)
    )


def bake_wireframe_map(obj, resolution=4096, thickness=0.01):
    """Bake wireframe map"""
    def setup_with_thickness(tree):
        setup_wireframe_nodes(tree, thickness)

    return bake_with_material(
        obj,
        mat_name="TempMat_Wireframe",
        image_name=f"{obj.name}_wireframe",
        resolution=resolution,
        setup_func=setup_with_thickness,
        bake_type='EMIT',
        samples=1,
        bg_color=(0, 0, 0, 1)
    )


def bake_paint_base_map(obj, resolution=512):
    """Bake paint base gradient map"""
    return bake_with_material(
        obj,
        mat_name="TempMat_PaintBase",
        image_name=f"{obj.name}_paint_base",
        resolution=resolution,
        setup_func=setup_paint_base_nodes,
        bake_type='EMIT',
        samples=1,
        bg_color=(0.5, 0.5, 0.5, 1)
    )


def bake_normal_object_map(obj, resolution=512):
    """Bake object-space normal map"""
    # Ensure UV map
    ensure_uv_map(obj)

    # Create image
    img = create_bake_image(
        f"{obj.name}_normal_object",
        resolution,
        resolution,
        color=(0.5, 0.5, 1, 1)  # Default normal color
    )

    # Create simple material for baking
    mat = create_bake_material("TempMat_Normal", setup_normal_object_nodes)
    assign_bake_image_to_material(mat, img)

    # Apply to object
    orig_mats = apply_material_to_object(obj, mat)

    # Store settings
    prev_engine = bpy.context.scene.render.engine
    prev_samples = bpy.context.scene.cycles.samples

    try:
        # Setup for normal baking
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.samples = 1

        # Select object
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Setup normal space for object
        bake_settings = bpy.context.scene.render.bake
        bake_settings.normal_space = 'OBJECT'
        bake_settings.normal_r = 'POS_X'
        bake_settings.normal_g = 'POS_Z'
        bake_settings.normal_b = 'NEG_Y'

        # Bake
        bpy.ops.object.bake(
            type='NORMAL',
            use_clear=True,
            margin=16,
            use_selected_to_active=False,
        )
    finally:
        # Restore
        restore_materials(obj, orig_mats)
        bpy.context.scene.render.engine = prev_engine
        bpy.context.scene.cycles.samples = prev_samples

        # Clean up temp material
        if mat.name in bpy.data.materials:
            bpy.data.materials.remove(mat, do_unlink=True)

    return img


def bake_base_color_map(obj, resolution=512):
    """Bake base color from materials"""
    # This requires the object to have materials with base color
    # We'll use DIFFUSE bake type to extract the base color

    ensure_uv_map(obj)

    # Create image
    img = create_bake_image(
        f"{obj.name}_base_color",
        resolution,
        resolution,
        color=(0.8, 0.8, 0.8, 1)
    )

    # For base color, we need to check if object has materials
    if not obj.data.materials or len(obj.data.materials) == 0:
        # Create a simple gray material
        mat = bpy.data.materials.new("TempMat_BaseColor")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
        obj.data.materials.append(mat)
        created_temp_mat = True
    else:
        created_temp_mat = False

    # Add bake target node to first material
    first_mat = obj.data.materials[0]
    if not first_mat.use_nodes:
        first_mat.use_nodes = True

    assign_bake_image_to_material(first_mat, img)

    # Store settings
    prev_engine = bpy.context.scene.render.engine
    prev_samples = bpy.context.scene.cycles.samples

    try:
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.samples = 1

        # Select object
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Bake diffuse color only
        bake_settings = bpy.context.scene.render.bake
        bake_settings.use_pass_direct = False
        bake_settings.use_pass_indirect = False
        bake_settings.use_pass_color = True

        bpy.ops.object.bake(
            type='DIFFUSE',
            use_clear=True,
            margin=16,
            use_selected_to_active=False,
        )
    finally:
        # Restore
        bpy.context.scene.render.engine = prev_engine
        bpy.context.scene.cycles.samples = prev_samples

        # Remove temp material if created
        if created_temp_mat and "TempMat_BaseColor" in bpy.data.materials:
            obj.data.materials.clear()
            bpy.data.materials.remove(bpy.data.materials["TempMat_BaseColor"], do_unlink=True)

    return img


def bake_ao_map(obj, resolution=512, samples=128):
    """Bake ambient occlusion map"""
    ensure_uv_map(obj)

    # Create image
    img = create_bake_image(
        f"{obj.name}_ao",
        resolution,
        resolution,
        color=(1, 1, 1, 1)
    )

    # Create simple material
    mat = create_bake_material("TempMat_AO", setup_ao_nodes)
    assign_bake_image_to_material(mat, img)

    # Apply to object
    orig_mats = apply_material_to_object(obj, mat)

    # Store settings
    prev_engine = bpy.context.scene.render.engine
    prev_samples = bpy.context.scene.cycles.samples

    try:
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.samples = samples

        # Select object
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Bake
        bpy.ops.object.bake(
            type='AO',
            use_clear=True,
            margin=16,
            use_selected_to_active=False,
        )
    finally:
        # Restore
        restore_materials(obj, orig_mats)
        bpy.context.scene.render.engine = prev_engine
        bpy.context.scene.cycles.samples = prev_samples

        # Clean up
        if mat.name in bpy.data.materials:
            bpy.data.materials.remove(mat, do_unlink=True)

    return img


def bake_thickness_map(obj, resolution=512, distance=1.0, samples=32):
    """Bake thickness map"""
    def setup_with_distance(tree):
        setup_thickness_nodes(tree, distance)

    return bake_with_material(
        obj,
        mat_name="TempMat_Thickness",
        image_name=f"{obj.name}_thickness",
        resolution=resolution,
        setup_func=setup_with_distance,
        bake_type='EMIT',
        samples=samples,
        bg_color=(0, 0, 0, 1)
    )


def bake_curvature_map(obj, resolution=512):
    """
    Bake curvature map.
    This requires baking normals first, then post-processing.
    For now, we'll return a normal bake (full curvature impl would need compositing).
    """
    # Simplified curvature - just use normal map for now
    # Full implementation would require Sobel filter on normals
    return bake_normal_object_map(obj, resolution)


# ============================================================
# Batch Baking
# ============================================================

def bake_all_modes(obj, settings):
    """
    Bake all enabled modes for an object.

    Args:
        obj: Object to bake
        settings: UNetExporterSettings with enabled modes

    Returns:
        Dictionary mapping mode names to baked images
    """
    baked_images = {}

    if settings.bake_position:
        baked_images['position'] = bake_position_map(obj, settings.bake_resolution)

    if settings.bake_wireframe:
        baked_images['wireframe'] = bake_wireframe_map(
            obj, settings.wireframe_resolution, settings.wireframe_thickness
        )

    if settings.bake_paint_base:
        baked_images['paint_base'] = bake_paint_base_map(obj, settings.bake_resolution)

    if settings.bake_normal_object:
        baked_images['normal_object'] = bake_normal_object_map(obj, settings.bake_resolution)

    if settings.bake_base_color:
        baked_images['base_color'] = bake_base_color_map(obj, settings.bake_resolution)

    if settings.bake_ao:
        baked_images['ao'] = bake_ao_map(obj, settings.bake_resolution, settings.ao_samples)

    if settings.bake_thickness:
        baked_images['thickness'] = bake_thickness_map(
            obj, settings.bake_resolution, settings.thickness_distance
        )

    if settings.bake_curvature:
        baked_images['curvature'] = bake_curvature_map(obj, settings.bake_resolution)

    return baked_images
