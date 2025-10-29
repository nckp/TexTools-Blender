"""
UNet Dataset Exporter - Standalone Addon for Blender 4.5+
========================================================

A high-performance standalone addon for generating texture baking and multi-view
rendering datasets for 3D meshes, optimized for processing millions of meshes.

Features:
- Bakes multiple texture types: position, wireframe, paint_base, normal_object, base_color
- Multi-view turnaround rendering with optimized camera placement
- Memory-efficient batch processing for large datasets
- No dependency on TexTools addon
- Crash recovery and incremental processing

Author: Claude
Version: 1.0.0
Blender: 4.5+
"""

bl_info = {
    "name": "UNet Dataset Exporter",
    "author": "Claude",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > UNet Exporter",
    "description": "High-performance texture baking and multi-view rendering for large datasets",
    "category": "Render",
}

import bpy
from bpy.types import Operator, Panel, PropertyGroup, AddonPreferences
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    PointerProperty,
)

# Import submodules
from . import bake_engine
from . import render_engine
from . import batch_processor
from . import utils

# ============================================================
# Properties
# ============================================================

class UNetExporterSettings(PropertyGroup):
    """Settings for UNet Dataset Exporter"""

    # Output settings
    output_path: StringProperty(
        name="Output Path",
        description="Base output directory for dataset",
        default="//blender_outputs/unet_dataset/",
        subtype='DIR_PATH'
    )

    # Resolution settings
    bake_resolution: IntProperty(
        name="Bake Resolution",
        description="Resolution for baked textures",
        default=512,
        min=64,
        max=8192
    )

    render_resolution: IntProperty(
        name="Render Resolution",
        description="Resolution for rendered views",
        default=1536,
        min=64,
        max=8192
    )

    wireframe_resolution: IntProperty(
        name="Wireframe Resolution",
        description="Higher resolution for wireframe maps",
        default=4096,
        min=64,
        max=8192
    )

    wireframe_thickness: FloatProperty(
        name="Wireframe Thickness",
        description="Thickness of wireframe lines",
        default=0.61,
        min=0.01,
        max=10.0
    )

    # Bake mode selection
    bake_position: BoolProperty(name="Position", default=True)
    bake_wireframe: BoolProperty(name="Wireframe", default=True)
    bake_paint_base: BoolProperty(name="Paint Base", default=True)
    bake_normal_object: BoolProperty(name="Normal (Object)", default=False)
    bake_base_color: BoolProperty(name="Base Color", default=False)
    bake_ao: BoolProperty(name="Ambient Occlusion", default=False)
    bake_curvature: BoolProperty(name="Curvature", default=False)
    bake_thickness: BoolProperty(name="Thickness", default=False)

    # Camera settings
    camera_count: IntProperty(
        name="Camera Views",
        description="Number of camera positions (turnaround)",
        default=8,
        min=1,
        max=64
    )

    focal_length: FloatProperty(
        name="Focal Length",
        description="Camera focal length in mm",
        default=50.0,
        min=1.0,
        max=200.0
    )

    coverage_padding: FloatProperty(
        name="Coverage Padding",
        description="Margin to prevent edge clipping (1.0 = exact fit)",
        default=1.15,
        min=1.0,
        max=2.0
    )

    # Batch processing
    batch_size: IntProperty(
        name="Batch Size",
        description="Number of meshes to process before cleanup (0 = all at once)",
        default=50,
        min=0,
        max=1000
    )

    auto_cleanup: BoolProperty(
        name="Auto Cleanup",
        description="Automatically clean up images and materials after each mesh",
        default=True
    )

    save_incremental: BoolProperty(
        name="Save Incrementally",
        description="Save .blend file after each batch",
        default=False
    )

    # Cycles settings
    ao_samples: IntProperty(
        name="AO Samples",
        description="Samples for AO baking",
        default=128,
        min=1,
        max=4096
    )

    thickness_distance: FloatProperty(
        name="Thickness Distance",
        description="Maximum distance for thickness calculation",
        default=1.0,
        min=0.001,
        max=100.0
    )

    curvature_size: FloatProperty(
        name="Curvature Size",
        description="Sample radius for curvature detection",
        default=0.005,
        min=0.0001,
        max=1.0
    )


# ============================================================
# Operators
# ============================================================

class UNET_OT_ExportDataset(Operator):
    """Export UNet dataset from selected meshes"""
    bl_idname = "unet.export_dataset"
    bl_label = "Export Dataset"
    bl_description = "Bake textures and render multi-view dataset from selected meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects and any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        settings = context.scene.unet_exporter_settings

        # Get selected mesh objects
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if not selected_meshes:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}

        # Run batch processor
        try:
            batch_processor.process_dataset(context, selected_meshes, settings, self)
            self.report({'INFO'}, f"Successfully processed {len(selected_meshes)} meshes")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class UNET_OT_TestBake(Operator):
    """Test bake on active object"""
    bl_idname = "unet.test_bake"
    bl_label = "Test Bake"
    bl_description = "Test baking on the active object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        settings = context.scene.unet_exporter_settings
        obj = context.active_object

        try:
            # Test bake position map
            bake_engine.bake_position_map(obj, 512)
            self.report({'INFO'}, "Test bake successful")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Test bake failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class UNET_OT_CleanupImages(Operator):
    """Clean up all baked images"""
    bl_idname = "unet.cleanup_images"
    bl_label = "Cleanup Images"
    bl_description = "Remove all baked images from the scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = utils.cleanup_baked_images()
        self.report({'INFO'}, f"Removed {count} baked images")
        return {'FINISHED'}


# ============================================================
# UI Panel
# ============================================================

class UNET_PT_MainPanel(Panel):
    """Main panel for UNet Dataset Exporter"""
    bl_label = "UNet Dataset Exporter"
    bl_idname = "UNET_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'UNet Exporter'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.unet_exporter_settings

        # Output settings
        box = layout.box()
        box.label(text="Output Settings", icon='OUTPUT')
        box.prop(settings, "output_path")

        # Resolution settings
        box = layout.box()
        box.label(text="Resolution", icon='IMAGE_DATA')
        box.prop(settings, "bake_resolution")
        box.prop(settings, "render_resolution")
        box.prop(settings, "wireframe_resolution")

        # Bake modes
        box = layout.box()
        box.label(text="Bake Modes", icon='SHADING_RENDERED')
        col = box.column(align=True)
        col.prop(settings, "bake_position")
        col.prop(settings, "bake_wireframe")
        col.prop(settings, "bake_paint_base")
        col.prop(settings, "bake_normal_object")
        col.prop(settings, "bake_base_color")
        col.prop(settings, "bake_ao")
        col.prop(settings, "bake_curvature")
        col.prop(settings, "bake_thickness")

        # Wireframe settings
        if settings.bake_wireframe:
            box.prop(settings, "wireframe_thickness")

        # Camera settings
        box = layout.box()
        box.label(text="Camera Settings", icon='CAMERA_DATA')
        box.prop(settings, "camera_count")
        box.prop(settings, "focal_length")
        box.prop(settings, "coverage_padding")

        # Batch processing
        box = layout.box()
        box.label(text="Batch Processing", icon='PROPERTIES')
        box.prop(settings, "batch_size")
        box.prop(settings, "auto_cleanup")
        box.prop(settings, "save_incremental")

        # Advanced settings
        box = layout.box()
        box.label(text="Advanced Bake Settings", icon='PREFERENCES')
        if settings.bake_ao:
            box.prop(settings, "ao_samples")
        if settings.bake_thickness:
            box.prop(settings, "thickness_distance")
        if settings.bake_curvature:
            box.prop(settings, "curvature_size")

        # Operators
        layout.separator()
        col = layout.column(align=True)
        col.scale_y = 1.5
        col.operator("unet.export_dataset", icon='RENDER_ANIMATION')

        layout.separator()
        row = layout.row(align=True)
        row.operator("unet.test_bake", icon='MATERIAL')
        row.operator("unet.cleanup_images", icon='TRASH')

        # Info
        layout.separator()
        box = layout.box()
        selected_count = len([obj for obj in context.selected_objects if obj.type == 'MESH'])
        box.label(text=f"Selected Meshes: {selected_count}", icon='MESH_DATA')


# ============================================================
# Registration
# ============================================================

classes = (
    UNetExporterSettings,
    UNET_OT_ExportDataset,
    UNET_OT_TestBake,
    UNET_OT_CleanupImages,
    UNET_PT_MainPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.unet_exporter_settings = PointerProperty(type=UNetExporterSettings)
    print("UNet Dataset Exporter addon registered")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.unet_exporter_settings
    print("UNet Dataset Exporter addon unregistered")


if __name__ == "__main__":
    register()
