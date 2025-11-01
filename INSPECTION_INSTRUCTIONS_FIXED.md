# Instructions for Material Inspection

## Quick Fix for the Error

The error means TexTools isn't enabled in Blender. Use the new script instead:

### Use `inspect_materials_direct.py` (Easier!)

This script works WITHOUT TexTools enabled.

1. Open `inspect_materials_direct.py` in a text editor
2. Find this line (around line 20):
   ```python
   TEXTOOLS_PATH = r"E:\path\to\TexTools-Blender"  # EDIT THIS!
   ```

3. Change it to your actual TexTools path. To find it:
   - Open Blender
   - Go to: Edit → Preferences → Add-ons
   - Search for "TexTools" (even if disabled)
   - Look for the file path shown
   - Copy that path

   Examples:
   ```python
   # Windows:
   TEXTOOLS_PATH = r"C:\Users\YourName\AppData\Roaming\Blender Foundation\Blender\4.5\scripts\addons\TexTools-Blender"

   # The path you showed in error suggests:
   TEXTOOLS_PATH = r"E:\win_projects\view2uv\unet29_new\TexTools-Blender"
   ```

4. Save the script
5. In Blender: Scripting workspace → Open → `inspect_materials_direct.py`
6. Click "Run Script"
7. Copy ALL console output

## Alternative: Quick Manual Check

If the script still doesn't work, do this manually:

1. In Blender, go to: File → Open
2. Navigate to: `E:\win_projects\view2uv\unet29_new\TexTools-Blender\resources\materials.blend`
3. Open it
4. Go to Shading workspace
5. For each material (bake_wireframe, bake_position, bake_paint_base):
   - Select the material
   - Take a screenshot of the Shader Editor showing ALL nodes
   - Take note of:
     - What nodes exist
     - How they're connected
     - Any special values

Then share the screenshots with me.

## Expected Output Format

When the script works, you should see something like:

```
================================================================================
MATERIAL: bake_wireframe
================================================================================

Nodes in bake_wireframe: (6 total)
----------------------------------------

Node: Value
  Type: ShaderNodeValue
  Location: (-600.0, 0.0)
  Inputs:
  Output [Value] → Wireframe.Size

Node: Wireframe
  Type: ShaderNodeWireframe
  Location: (-400.0, 0.0)
  SPECIAL: use_pixel_size = False
  Inputs:
    [Size] ← Value.Value
  Output [Fac] → ColorRamp.Fac

... etc ...
```

## Troubleshooting

**"Cannot find materials.blend"**
- The path is wrong
- Edit TEXTOOLS_PATH in the script
- Make sure it points to the TexTools-Blender folder

**"Material not found in materials.blend"**
- The file might be from a different TexTools version
- Try listing what IS in the file

**Script won't run**
- Make sure you're in Blender (not external Python)
- Use the Scripting workspace
- Check for syntax errors

## Why We Need This

Without seeing the exact shader node setup, I'm guessing:
- Wireframe shows grey = my shader connections are wrong
- Paint_base has UV mismatch = my coordinate system is wrong

With the actual material structure, I can recreate them EXACTLY and fix both issues immediately.
