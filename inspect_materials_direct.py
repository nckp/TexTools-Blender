"""
Direct Material Inspector - No TexTools Required
================================================

This script directly loads materials from TexTools' materials.blend file
WITHOUT needing TexTools to be enabled.

Usage:
1. Open Blender 4.5
2. Go to Scripting workspace
3. Edit TEXTOOLS_PATH below to point to your TexTools folder
4. Run this script
5. Copy the output from the console
"""

import bpy
import os

# EDIT THIS PATH to point to your TexTools addon folder
# Examples:
#   Windows: "C:/Users/YourName/AppData/Roaming/Blender Foundation/Blender/4.5/scripts/addons/TexTools-Blender"
#   Linux: "/home/username/.config/blender/4.5/scripts/addons/TexTools-Blender"
#   macOS: "/Users/username/Library/Application Support/Blender/4.5/scripts/addons/TexTools-Blender"

TEXTOOLS_PATH = r"E:\path\to\TexTools-Blender"  # EDIT THIS!

# Or try to auto-detect
import sys
for path in sys.path:
    if "addons" in path:
        test_path = os.path.join(path, "TexTools-Blender")
        if os.path.exists(test_path):
            TEXTOOLS_PATH = test_path
            break

print("\n" + "="*80)
print("DIRECT MATERIAL INSPECTOR")
print("="*80)
print(f"\nTexTools path: {TEXTOOLS_PATH}")

# Path to materials.blend
materials_path = os.path.join(TEXTOOLS_PATH, "resources", "materials.blend")

if not os.path.exists(materials_path):
    print(f"\nERROR: Cannot find materials.blend at:")
    print(f"  {materials_path}")
    print("\nPlease edit TEXTOOLS_PATH in the script to point to your TexTools folder!")
    print("You can find it in Blender preferences > Add-ons > search 'TexTools' > see file path")
else:
    print(f"Materials file: {materials_path}")

    # Materials we want to inspect
    materials_to_inspect = ['bake_wireframe', 'bake_position', 'bake_paint_base']

    for mat_name in materials_to_inspect:
        print("\n" + "="*80)
        print(f"MATERIAL: {mat_name}")
        print("="*80)

        # Load the material
        with bpy.data.libraries.load(materials_path, link=False) as (data_from, data_to):
            if mat_name in data_from.materials:
                data_to.materials = [mat_name]
            else:
                print(f"  ERROR: Material '{mat_name}' not found in materials.blend")
                print(f"  Available materials: {data_from.materials}")
                continue

        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]

            if mat.use_nodes:
                tree = mat.node_tree

                print(f"\nNodes in {mat_name}: ({len(tree.nodes)} total)")
                print("-" * 40)

                for node in tree.nodes:
                    print(f"\nNode: {node.name}")
                    print(f"  Type: {node.bl_idname}")
                    print(f"  Location: ({node.location.x:.1f}, {node.location.y:.1f})")

                    # Print inputs with values and connections
                    if hasattr(node, 'inputs') and node.inputs:
                        print(f"  Inputs:")
                        for inp in node.inputs:
                            value_str = ""
                            if hasattr(inp, 'default_value'):
                                try:
                                    val = inp.default_value
                                    if hasattr(val, '__len__') and not isinstance(val, str):
                                        value_str = f" = {tuple(val)}"
                                    else:
                                        value_str = f" = {val}"
                                except:
                                    value_str = " = [complex value]"

                            conn_str = ""
                            if inp.is_linked:
                                for link in inp.links:
                                    conn_str = f" ← {link.from_node.name}.{link.from_socket.name}"

                            print(f"    [{inp.name}]{value_str}{conn_str}")

                    # Print outputs with connections
                    if hasattr(node, 'outputs') and node.outputs:
                        for out in node.outputs:
                            if out.is_linked:
                                for link in out.links:
                                    print(f"  Output [{out.name}] → {link.to_node.name}.{link.to_socket.name}")

                    # Special node properties
                    if node.bl_idname == 'ShaderNodeWireframe':
                        print(f"  SPECIAL: use_pixel_size = {node.use_pixel_size}")

                    elif node.bl_idname == 'ShaderNodeValToRGB':
                        print(f"  SPECIAL: ColorRamp stops:")
                        for i, elem in enumerate(node.color_ramp.elements):
                            print(f"    Stop {i}: position={elem.position:.3f}, color=({elem.color[0]:.3f}, {elem.color[1]:.3f}, {elem.color[2]:.3f}, {elem.color[3]:.3f})")

                    elif node.bl_idname == 'ShaderNodeAmbientOcclusion':
                        print(f"  SPECIAL: samples = {node.samples}")
                        print(f"  SPECIAL: only_local = {node.only_local}")
                        if hasattr(node, 'inside'):
                            print(f"  SPECIAL: inside = {node.inside}")

                    elif node.bl_idname == 'ShaderNodeEmission':
                        print(f"  SPECIAL: Emission node (check Strength input)")

                    elif node.bl_idname == 'ShaderNodeTexCoord':
                        print(f"  SPECIAL: Texture Coordinate node")
                        print(f"    Available outputs: UV, Object, Camera, Window, Normal, Generated, Reflection")

                    elif node.bl_idname == 'ShaderNodeNewGeometry':
                        print(f"  SPECIAL: Geometry node")
                        print(f"    Available outputs: Position, Normal, Tangent, etc.")

                # Print connection summary
                print("\n" + "-" * 40)
                print("CONNECTION FLOW:")
                # Find nodes with no inputs (start nodes)
                start_nodes = [n for n in tree.nodes if not any(inp.is_linked for inp in n.inputs if hasattr(n, 'inputs'))]
                if start_nodes:
                    print("Start nodes (no inputs):", [n.name for n in start_nodes])

                # Find output node
                output_nodes = [n for n in tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
                if output_nodes:
                    print("Output nodes:", [n.name for n in output_nodes])
            else:
                print(f"  ERROR: Material {mat_name} doesn't use nodes!")
        else:
            print(f"  ERROR: Could not load material {mat_name}")

    print("\n" + "="*80)
    print("INSPECTION COMPLETE")
    print("="*80)
    print("\nCopy ALL the output above and share it!")
    print("This will allow exact recreation of the shaders.")
