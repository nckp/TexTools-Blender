"""
Baking Engine - Core texture baking functionality (FIXED)
==========================================================

This module implements all texture baking modes without any dependency on TexTools.
Each bake mode creates the necessary shader nodes procedurally and performs Cycles baking.

FIXES:
- Base color now properly preserves and relinks existing materials
- Wireframe now creates actual lines with proper shader setup
- Paint base now uses AO for realistic surface depth
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
    Create nodes for wireframe baking - FIXED VERSION.

    Uses the same pattern as TexTools: Value node → Wireframe → ColorRamp → Emission

    Args:
        thickness: Wireframe line thickness
    """
    # Value node to control wireframe size (like TexTools)
    value_node = tree.nodes.new("ShaderNodeValue")
    value_node.name = "Value"
    value_node.label = "Wireframe Size"
    value_node.location = (-600, 0)
    value_node.outputs[0].default_value = thickness

    # Wireframe node
    wireframe = tree.nodes.new("ShaderNodeWireframe")
    wireframe.location = (-400, 0)
    wireframe.use_pixel_size = False  # Use Blender units

    # Color ramp to make lines sharp and white on black
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 0)
    # Black background (position 0)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    # White lines (position 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)

    # Emission shader
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (0, 0)
    emission.inputs['Strength'].default_value = 1.0

    # Material output
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (200, 0)

    # Connect: Value → Wireframe.Size
    tree.links.new(value_node.outputs[0], wireframe.inputs['Size'])
    # Wireframe.Fac → ColorRamp
    tree.links.new(wireframe.outputs['Fac'], ramp.inputs['Fac'])
    # ColorRamp → Emission
    tree.links.new(ramp.outputs['Color'], emission.inputs['Color'])
    # Emission → Output
    tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])


def setup_paint_base_nodes(tree):
    """
    Create nodes for paint base baking - IMPROVED VERSION.

    Paint base provides a foundation for hand-painting by showing surface depth.
    This uses AO (ambient occlusion) which is what most paint base maps are.
    """
    # Ambient Occlusion node for surface depth
    ao_node = tree.nodes.new("ShaderNodeAmbientOcclusion")
    ao_node.location = (-400, 0)
    ao_node.inputs['Distance'].default_value = 1.0
    ao_node.samples = 16
    ao_node.only_local = False

    # Color ramp to adjust contrast
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 0)
    # Darker shadows
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (0.1, 0.1, 0.15, 1)
    # Lighter highlights
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.9, 0.9, 0.95, 1)

    # Emission
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (0, 0)

    # Output
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (200, 0)

    # Connect
    tree.links.new(ao_node.outputs['Color'], ramp.inputs['Fac'])
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
    """Bake wireframe map - FIXED to show actual lines"""
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
    """Bake paint base map - IMPROVED with AO"""
    return bake_with_material(
        obj,
        mat_name="TempMat_PaintBase",
        image_name=f"{obj.name}_paint_base",
        resolution=resolution,
        setup_func=setup_paint_base_nodes,
        bake_type='EMIT',
        samples=16,  # More samples for AO quality
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
    """
    Bake base color from materials - COMPLETELY REWRITTEN.

    This now properly preserves existing materials and uses the TexTools
    relink mechanism to extract base color through emission.
    """
    ensure_uv_map(obj)

    # Create image
    img = create_bake_image(
        f"{obj.name}_base_color",
        resolution,
        resolution,
        color=(0.8, 0.8, 0.8, 1)
    )

    # Check if object has materials
    if not obj.data.materials or len(obj.data.materials) == 0:
        # Create a default grey material if none exists
        default_mat = bpy.data.materials.new("TempDefaultMat")
        default_mat.use_nodes = True
        default_mat.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
        obj.data.materials.append(default_mat)
        created_default = True
    else:
        created_default = False

    # Store original material states
    original_material_states = []

    # For each material, modify it to output base color through emission
    for slot in obj.material_slots:
        if slot.material and slot.material.use_nodes:
            mat = slot.material
            tree = mat.node_tree

            # Store original state
            orig_state = {'material': mat, 'modifications': []}

            # Find the Principled BSDF
            bsdf_node = None
            for node in tree.nodes:
                if node.bl_idname == "ShaderNodeBsdfPrincipled":
                    bsdf_node = node
                    break
                elif node.bl_idname == "ShaderNodeGroup":
                    # Check inside node groups
                    for ng in node.node_tree.nodes:
                        if ng.bl_idname == "ShaderNodeBsdfPrincipled":
                            bsdf_node = ng
                            tree = node.node_tree
                            break

            if bsdf_node:
                # Store original connections from BSDF output
                orig_bsdf_outputs = []
                if bsdf_node.outputs['BSDF'].is_linked:
                    for link in bsdf_node.outputs['BSDF'].links:
                        orig_bsdf_outputs.append({
                            'to_node': link.to_node,
                            'to_socket': link.to_socket.name
                        })
                        tree.links.remove(link)

                orig_state['modifications'].append({
                    'type': 'bsdf_disconnect',
                    'outputs': orig_bsdf_outputs,
                    'tree': tree
                })

                # Create emission node
                emission_node = tree.nodes.new("ShaderNodeEmission")
                emission_node.location = (bsdf_node.location.x + 300, bsdf_node.location.y)
                emission_node.name = "TempEmission_BaseColor"

                orig_state['modifications'].append({
                    'type': 'emission_created',
                    'node': emission_node,
                    'tree': tree
                })

                # Find Material Output node
                output_node = None
                for node in tree.nodes:
                    if node.bl_idname == "ShaderNodeOutputMaterial":
                        output_node = node
                        break

                if output_node:
                    # Connect Base Color → Emission
                    base_color_input = bsdf_node.inputs['Base Color']
                    if base_color_input.is_linked:
                        # Get what's connected to Base Color
                        base_color_link = base_color_input.links[0]
                        tree.links.new(base_color_link.from_socket, emission_node.inputs['Color'])
                    else:
                        # Use default value
                        emission_node.inputs['Color'].default_value = base_color_input.default_value

                    # Connect Emission → Surface Output
                    tree.links.new(emission_node.outputs['Emission'], output_node.inputs['Surface'])

            original_material_states.append(orig_state)

    # Add bake target to first material
    if obj.data.materials and obj.data.materials[0]:
        first_mat = obj.data.materials[0]
        if first_mat.use_nodes:
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

        # Bake with EMIT type to capture the emission color
        bpy.ops.object.bake(
            type='EMIT',
            use_clear=True,
            margin=16,
            use_selected_to_active=False,
        )
    finally:
        # Restore all material modifications
        for state in original_material_states:
            for mod in state['modifications']:
                if mod['type'] == 'emission_created':
                    # Remove emission node
                    if mod['node'].name in mod['tree'].nodes:
                        mod['tree'].nodes.remove(mod['node'])

                elif mod['type'] == 'bsdf_disconnect':
                    # Reconnect original BSDF outputs
                    bsdf_node = None
                    for node in mod['tree'].nodes:
                        if node.bl_idname == "ShaderNodeBsdfPrincipled":
                            bsdf_node = node
                            break

                    if bsdf_node:
                        for orig_link in mod['outputs']:
                            if orig_link['to_node'].name in mod['tree'].nodes:
                                to_node = mod['tree'].nodes[orig_link['to_node'].name]
                                mod['tree'].links.new(
                                    bsdf_node.outputs['BSDF'],
                                    to_node.inputs[orig_link['to_socket']]
                                )

        # Remove bake target node
        if obj.data.materials and obj.data.materials[0]:
            first_mat = obj.data.materials[0]
            if first_mat.use_nodes and "BakeTarget" in first_mat.node_tree.nodes:
                first_mat.node_tree.nodes.remove(first_mat.node_tree.nodes["BakeTarget"])

        # Restore settings
        bpy.context.scene.render.engine = prev_engine
        bpy.context.scene.cycles.samples = prev_samples

        # Remove temp default material if created
        if created_default and "TempDefaultMat" in bpy.data.materials:
            obj.data.materials.clear()
            bpy.data.materials.remove(bpy.data.materials["TempDefaultMat"], do_unlink=True)

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
