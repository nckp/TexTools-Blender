"""
Batch Processor - Efficient large-scale dataset processing
===========================================================

This module handles batch processing with memory management, progress tracking,
and crash recovery for processing millions of meshes.
"""

import bpy
import os
import time
from datetime import datetime
from . import bake_engine
from . import render_engine
from . import utils


def generate_mesh_id():
    """Generate a unique timestamp ID for a mesh"""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def setup_output_directories(base_path, settings):
    """
    Create output directory structure.

    Args:
        base_path: Base output path
        settings: UNetExporterSettings

    Returns:
        Dict of output directories {mode_name: path}
    """
    # Convert relative path to absolute
    abs_base = bpy.path.abspath(base_path)

    # Create base directory
    if not os.path.exists(abs_base):
        os.makedirs(abs_base)

    # Create subdirectories for each enabled mode
    output_dirs = {}

    if settings.bake_position:
        path = os.path.join(abs_base, "position")
        os.makedirs(path, exist_ok=True)
        output_dirs['position'] = path

    if settings.bake_wireframe:
        path = os.path.join(abs_base, "wireframe")
        os.makedirs(path, exist_ok=True)
        output_dirs['wireframe'] = path

    if settings.bake_paint_base:
        path = os.path.join(abs_base, "paint_base")
        os.makedirs(path, exist_ok=True)
        output_dirs['paint_base'] = path

    if settings.bake_normal_object:
        path = os.path.join(abs_base, "normal_object")
        os.makedirs(path, exist_ok=True)
        output_dirs['normal_object'] = path

    if settings.bake_base_color:
        path = os.path.join(abs_base, "base_color")
        os.makedirs(path, exist_ok=True)
        output_dirs['base_color'] = path

    if settings.bake_ao:
        path = os.path.join(abs_base, "ao")
        os.makedirs(path, exist_ok=True)
        output_dirs['ao'] = path

    if settings.bake_curvature:
        path = os.path.join(abs_base, "curvature")
        os.makedirs(path, exist_ok=True)
        output_dirs['curvature'] = path

    if settings.bake_thickness:
        path = os.path.join(abs_base, "thickness")
        os.makedirs(path, exist_ok=True)
        output_dirs['thickness'] = path

    # Create textures backup directory
    textures_path = os.path.join(abs_base, "textures_backup")
    os.makedirs(textures_path, exist_ok=True)
    output_dirs['textures_backup'] = textures_path

    return output_dirs


def process_single_mesh(obj, output_dirs, settings, mesh_index, total_meshes):
    """
    Process a single mesh: bake textures and render views.

    Args:
        obj: Mesh object to process
        output_dirs: Dict of output directories
        settings: UNetExporterSettings
        mesh_index: Current mesh index
        total_meshes: Total number of meshes

    Returns:
        Processing statistics dict
    """
    start_time = time.time()

    print("\n" + "=" * 60)
    print(f"[{mesh_index}/{total_meshes}] Processing: {obj.name}")
    print("=" * 60)

    # Generate unique ID for this mesh
    mesh_id = generate_mesh_id()

    # STEP 1: Bake all textures
    print(f"\n  Step 1/3: Baking textures...")
    bake_start = time.time()
    baked_images = bake_engine.bake_all_modes(obj, settings)
    bake_time = time.time() - bake_start
    print(f"  ✓ Baked {len(baked_images)} texture types in {bake_time:.2f}s")

    # STEP 2: Save baked textures (optional backup)
    print(f"\n  Step 2/3: Saving textures...")
    save_start = time.time()
    saved_paths = render_engine.save_baked_textures(
        baked_images,
        output_dirs['textures_backup'],
        utils.sanitize_filename(obj.name),
        mesh_id
    )
    save_time = time.time() - save_start
    print(f"  ✓ Saved {len(saved_paths)} textures in {save_time:.2f}s")

    # STEP 3: Render multi-view
    print(f"\n  Step 3/3: Rendering {settings.camera_count} views...")
    render_start = time.time()
    view_count = render_engine.render_multiview_turnaround(
        obj,
        baked_images,
        output_dirs,
        settings,
        mesh_id
    )
    render_time = time.time() - render_start
    print(f"  ✓ Rendered {view_count} views in {render_time:.2f}s")

    # Calculate total time
    total_time = time.time() - start_time

    # Return statistics
    stats = {
        'mesh_name': obj.name,
        'mesh_id': mesh_id,
        'bake_count': len(baked_images),
        'view_count': view_count,
        'bake_time': bake_time,
        'save_time': save_time,
        'render_time': render_time,
        'total_time': total_time,
    }

    print(f"\n✓ Completed {obj.name} in {total_time:.2f}s")
    print(f"  - Textures: {output_dirs['textures_backup']}/{obj.name}_{mesh_id}_*.png")
    print(f"  - Views: {view_count} renders across {len(baked_images)} modes")

    return stats, baked_images


def cleanup_after_mesh(baked_images, auto_cleanup=True):
    """
    Clean up resources after processing a mesh.

    Args:
        baked_images: Dict of baked images to clean up
        auto_cleanup: Whether to auto cleanup
    """
    if not auto_cleanup:
        return

    # Remove baked images from memory
    for image in baked_images.values():
        if image and image.name in bpy.data.images:
            bpy.data.images.remove(image, do_unlink=True)


def process_dataset(context, selected_meshes, settings, operator):
    """
    Main batch processing function.

    Args:
        context: Blender context
        selected_meshes: List of mesh objects to process
        settings: UNetExporterSettings
        operator: Calling operator (for reporting)
    """
    print("\n" + "=" * 80)
    print("UNET DATASET EXPORT - BATCH PROCESSING")
    print("=" * 80)

    # Setup output directories
    output_dirs = setup_output_directories(settings.output_path, settings)

    print(f"\nOutput structure:")
    print(f"  Base: {bpy.path.abspath(settings.output_path)}")
    for mode_name, path in output_dirs.items():
        if mode_name != 'textures_backup':
            print(f"  - {mode_name}: {path}")
    print(f"  - Texture backups: {output_dirs['textures_backup']}")

    print(f"\nDataset configuration:")
    print(f"  - Meshes to process: {len(selected_meshes)}")
    print(f"  - Camera views per mesh: {settings.camera_count}")
    print(f"  - Bake resolution: {settings.bake_resolution}x{settings.bake_resolution}")
    print(f"  - Render resolution: {settings.render_resolution}x{settings.render_resolution}")
    print(f"  - Batch size: {settings.batch_size if settings.batch_size > 0 else 'All at once'}")
    print(f"  - Auto cleanup: {settings.auto_cleanup}")

    # Count enabled bake modes
    enabled_modes = []
    if settings.bake_position: enabled_modes.append('position')
    if settings.bake_wireframe: enabled_modes.append('wireframe')
    if settings.bake_paint_base: enabled_modes.append('paint_base')
    if settings.bake_normal_object: enabled_modes.append('normal_object')
    if settings.bake_base_color: enabled_modes.append('base_color')
    if settings.bake_ao: enabled_modes.append('ao')
    if settings.bake_curvature: enabled_modes.append('curvature')
    if settings.bake_thickness: enabled_modes.append('thickness')

    print(f"  - Enabled bake modes ({len(enabled_modes)}): {', '.join(enabled_modes)}")
    print("=" * 80)

    # Store initial state
    initial_selection = [obj for obj in context.selected_objects]
    active_prev = context.view_layer.objects.active
    mode_prev = context.object.mode if context.object else 'OBJECT'

    # Ensure object mode
    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Processing statistics
    all_stats = []
    total_start_time = time.time()

    try:
        # Determine batch size
        batch_size = settings.batch_size if settings.batch_size > 0 else len(selected_meshes)

        # Process in batches
        for batch_idx in range(0, len(selected_meshes), batch_size):
            batch_end = min(batch_idx + batch_size, len(selected_meshes))
            batch = selected_meshes[batch_idx:batch_end]

            print(f"\n{'=' * 80}")
            print(f"BATCH {batch_idx // batch_size + 1}: Processing meshes {batch_idx + 1}-{batch_end}")
            print(f"{'=' * 80}")

            batch_start_time = time.time()

            # Process each mesh in batch
            for i, obj in enumerate(batch):
                global_idx = batch_idx + i + 1

                try:
                    stats, baked_images = process_single_mesh(
                        obj,
                        output_dirs,
                        settings,
                        global_idx,
                        len(selected_meshes)
                    )
                    all_stats.append(stats)

                    # Cleanup after each mesh if auto cleanup enabled
                    cleanup_after_mesh(baked_images, settings.auto_cleanup)

                except Exception as e:
                    error_msg = f"Error processing {obj.name}: {str(e)}"
                    print(f"\n✗ {error_msg}")
                    operator.report({'WARNING'}, error_msg)
                    import traceback
                    traceback.print_exc()
                    continue

            batch_time = time.time() - batch_start_time
            print(f"\n✓ Batch {batch_idx // batch_size + 1} completed in {batch_time:.2f}s")

            # Save .blend file incrementally if enabled
            if settings.save_incremental and bpy.data.filepath:
                print(f"  Saving .blend file...")
                bpy.ops.wm.save_mainfile()

            # Additional cleanup between batches
            if settings.auto_cleanup:
                utils.cleanup_unused_data()

    finally:
        # Restore initial state
        bpy.ops.object.select_all(action='DESELECT')
        for obj in initial_selection:
            if obj and obj.name in bpy.data.objects:
                obj.select_set(True)
        if active_prev and active_prev.name in bpy.data.objects:
            context.view_layer.objects.active = active_prev
        if context.object:
            bpy.ops.object.mode_set(mode=mode_prev)

    # Print final statistics
    total_time = time.time() - total_start_time
    print("\n" + "=" * 80)
    print("DATASET EXPORT COMPLETE")
    print("=" * 80)

    if all_stats:
        print(f"\nStatistics:")
        print(f"  - Total meshes processed: {len(all_stats)}")
        print(f"  - Total time: {total_time:.2f}s ({total_time / 60:.1f} minutes)")
        print(f"  - Average time per mesh: {total_time / len(all_stats):.2f}s")

        total_bake_time = sum(s['bake_time'] for s in all_stats)
        total_render_time = sum(s['render_time'] for s in all_stats)

        print(f"  - Total baking time: {total_bake_time:.2f}s")
        print(f"  - Total rendering time: {total_render_time:.2f}s")
        print(f"  - Average bake time: {total_bake_time / len(all_stats):.2f}s")
        print(f"  - Average render time: {total_render_time / len(all_stats):.2f}s")

        total_views = sum(s['view_count'] for s in all_stats)
        print(f"  - Total views rendered: {total_views}")

        # Estimate time for full dataset
        if len(selected_meshes) < 1000:  # Only show estimate if this was a small batch
            avg_time = total_time / len(all_stats)
            est_1k = avg_time * 1000 / 3600  # hours
            est_1m = avg_time * 1000000 / 3600  # hours
            print(f"\n  Estimated time for:")
            print(f"    - 1,000 meshes: {est_1k:.1f} hours")
            print(f"    - 1,000,000 meshes: {est_1m:.0f} hours ({est_1m / 24:.0f} days)")

    print("\n" + "=" * 80)
    print(f"Output location: {bpy.path.abspath(settings.output_path)}")
    print("=" * 80)
