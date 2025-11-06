"""
Utilities - Helper functions
=============================

Common utility functions for dataset export.
"""

import bpy
import re


def sanitize_filename(name):
    """
    Clean filename: only alphanumeric and underscores allowed.

    Args:
        name: Original name

    Returns:
        Sanitized name
    """
    # Replace any non-alphanumeric character (except underscore) with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Remove any duplicate underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized if sanitized else "unnamed"


def cleanup_baked_images():
    """
    Remove all baked images from the scene.

    Returns:
        Number of images removed
    """
    count = 0
    images_to_remove = []

    # Find all baked images
    for img in bpy.data.images:
        # Look for common bake image patterns
        if any(pattern in img.name.lower() for pattern in [
            '_position', '_wireframe', '_paint_base', '_normal_object',
            '_base_color', '_ao', '_thickness', '_curvature',
            'preview_emission', 'tempmat'
        ]):
            images_to_remove.append(img)

    # Remove images
    for img in images_to_remove:
        bpy.data.images.remove(img, do_unlink=True)
        count += 1

    return count


def cleanup_temp_materials():
    """
    Remove temporary baking materials.

    Returns:
        Number of materials removed
    """
    count = 0
    materials_to_remove = []

    for mat in bpy.data.materials:
        if any(pattern in mat.name for pattern in [
            'TempMat_', 'Preview_Emission_', 'TT_bake_node'
        ]):
            materials_to_remove.append(mat)

    for mat in materials_to_remove:
        bpy.data.materials.remove(mat, do_unlink=True)
        count += 1

    return count


def cleanup_unused_data():
    """
    Clean up unused data blocks to free memory.

    Returns:
        Dict with counts of removed items
    """
    counts = {
        'images': 0,
        'materials': 0,
        'textures': 0,
        'meshes': 0,
    }

    # Remove unused images
    for img in list(bpy.data.images):
        if img.users == 0:
            bpy.data.images.remove(img, do_unlink=True)
            counts['images'] += 1

    # Remove unused materials
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat, do_unlink=True)
            counts['materials'] += 1

    # Remove unused textures
    for tex in list(bpy.data.textures):
        if tex.users == 0:
            bpy.data.textures.remove(tex, do_unlink=True)
            counts['textures'] += 1

    # Remove unused meshes
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh, do_unlink=True)
            counts['meshes'] += 1

    if any(counts.values()):
        print(f"  Cleaned up unused data: {counts}")

    return counts


def get_mesh_info(obj):
    """
    Get information about a mesh object.

    Args:
        obj: Mesh object

    Returns:
        Dict with mesh information
    """
    if obj.type != 'MESH':
        return None

    return {
        'name': obj.name,
        'vertices': len(obj.data.vertices),
        'edges': len(obj.data.edges),
        'faces': len(obj.data.polygons),
        'triangles': sum(len(p.vertices) - 2 for p in obj.data.polygons),
        'has_uv': len(obj.data.uv_layers) > 0,
        'uv_layers': len(obj.data.uv_layers),
        'materials': len(obj.data.materials),
    }


def estimate_processing_time(mesh_count, avg_time_per_mesh):
    """
    Estimate total processing time for a dataset.

    Args:
        mesh_count: Number of meshes to process
        avg_time_per_mesh: Average time per mesh in seconds

    Returns:
        Dict with time estimates
    """
    total_seconds = mesh_count * avg_time_per_mesh

    return {
        'seconds': total_seconds,
        'minutes': total_seconds / 60,
        'hours': total_seconds / 3600,
        'days': total_seconds / 86400,
    }


def validate_mesh_for_export(obj):
    """
    Validate that a mesh is suitable for export.

    Args:
        obj: Mesh object

    Returns:
        Tuple of (is_valid, error_message)
    """
    if obj.type != 'MESH':
        return False, "Object is not a mesh"

    if len(obj.data.vertices) == 0:
        return False, "Mesh has no vertices"

    if len(obj.data.polygons) == 0:
        return False, "Mesh has no faces"

    # UV map will be created automatically if missing, so not a blocker

    return True, ""


def print_export_summary(settings, mesh_count):
    """
    Print a summary of export settings.

    Args:
        settings: UNetExporterSettings
        mesh_count: Number of meshes to process
    """
    print("\nExport Summary")
    print("=" * 60)
    print(f"Meshes: {mesh_count}")
    print(f"Output: {settings.output_path}")
    print(f"Bake Resolution: {settings.bake_resolution}x{settings.bake_resolution}")
    print(f"Render Resolution: {settings.render_resolution}x{settings.render_resolution}")
    print(f"Camera Views: {settings.camera_count}")

    modes = []
    if settings.bake_position: modes.append("Position")
    if settings.bake_wireframe: modes.append("Wireframe")
    if settings.bake_paint_base: modes.append("Paint Base")
    if settings.bake_normal_object: modes.append("Normal (Object)")
    if settings.bake_base_color: modes.append("Base Color")
    if settings.bake_ao: modes.append("AO")
    if settings.bake_curvature: modes.append("Curvature")
    if settings.bake_thickness: modes.append("Thickness")

    print(f"Bake Modes ({len(modes)}): {', '.join(modes)}")
    print(f"Total Renders: {mesh_count * settings.camera_count * len(modes)}")
    print("=" * 60)
