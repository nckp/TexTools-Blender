"""
Material Inspector Script for TexTools
=======================================

Run this script in Blender with TexTools installed to extract
the exact shader node structure of bake materials.

Usage:
1. Open Blender 4.5
2. Make sure TexTools is installed
3. Go to Scripting workspace
4. Open and run this script
5. Copy the output from the console
"""

import bpy
import os

# Path to TexTools materials
addon_path = os.path.dirname(bpy.context.preferences.addons['TexTools'].module.__file__)
materials_path = os.path.join(addon_path, "resources", "materials.blend")

print("\n" + "="*80)
print("TEXTOOLS MATERIAL INSPECTOR")
print("="*80)
print(f"\nMaterials file: {materials_path}")

# Materials we care about
materials_to_inspect = ['bake_wireframe', 'bake_position', 'bake_paint_base']

for mat_name in materials_to_inspect:
    print("\n" + "="*80)
    print(f"MATERIAL: {mat_name}")
    print("="*80)

    # Load the material if not already loaded
    if mat_name not in bpy.data.materials:
        mat_path = os.path.join(materials_path, "Material")
        bpy.ops.wm.append(
            filename=mat_name,
            directory=mat_path,
            link=False,
            autoselect=False
        )

    if mat_name in bpy.data.materials:
        mat = bpy.data.materials[mat_name]

        if mat.use_nodes:
            tree = mat.node_tree

            print(f"\nNodes in {mat_name}:")
            print("-" * 40)

            for node in tree.nodes:
                print(f"\nNode: {node.name}")
                print(f"  Type: {node.bl_idname}")
                print(f"  Location: ({node.location.x:.1f}, {node.location.y:.1f})")

                # Print inputs
                if hasattr(node, 'inputs') and node.inputs:
                    print(f"  Inputs:")
                    for inp in node.inputs:
                        if hasattr(inp, 'default_value'):
                            print(f"    - {inp.name}: {inp.default_value}")
                        if inp.is_linked:
                            for link in inp.links:
                                print(f"      ← Connected from: {link.from_node.name}.{link.from_socket.name}")

                # Print outputs
                if hasattr(node, 'outputs') and node.outputs:
                    print(f"  Outputs:")
                    for out in node.outputs:
                        if out.is_linked:
                            for link in out.links:
                                print(f"    → Connected to: {link.to_node.name}.{link.to_socket.name}")

                # Special properties
                if node.bl_idname == 'ShaderNodeWireframe':
                    print(f"  use_pixel_size: {node.use_pixel_size}")
                elif node.bl_idname == 'ShaderNodeValToRGB':
                    print(f"  ColorRamp stops:")
                    for i, elem in enumerate(node.color_ramp.elements):
                        print(f"    Stop {i}: pos={elem.position:.3f}, color={tuple(elem.color)}")
                elif node.bl_idname == 'ShaderNodeAmbientOcclusion':
                    print(f"  samples: {node.samples}")
                    print(f"  only_local: {node.only_local}")
        else:
            print(f"  ERROR: Material {mat_name} doesn't use nodes!")
    else:
        print(f"  ERROR: Could not load material {mat_name}")

print("\n" + "="*80)
print("INSPECTION COMPLETE")
print("="*80)
print("\nCopy the output above to recreate these materials accurately.")
