# Current Status & Deep Diagnosis

## Working Modes ✓
1. **Position** - Correctly baking world-space XYZ as RGB
2. **Normal (Object)** - Correctly baking object-space normals
3. **Base Color** - Now properly preserves materials and extracts color

## Broken Modes ✗

### 1. Wireframe - Grey Silhouette Instead of Lines

**Symptoms:**
- Baked texture shows solid grey silhouette
- No wireframe lines visible
- Just the shape of the mesh

**Current Implementation:**
```python
Value (0.61) → Wireframe.Size
Wireframe.Fac → ColorRamp → Emission → Output
```

**Possible Causes:**
A) Emission strength is wrong
B) Wireframe node isn't producing correct output
C) Bake type should be DIFFUSE not EMIT
D) The loaded material from materials.blend has additional nodes we're missing
E) Color space settings on the image are wrong

**What TexTools Does:**
- Loads material 'bake_wireframe' from materials.blend
- Sets Value node to wireframe thickness
- Bakes with EMIT type (default)

**Need to Verify:**
- Exact node structure in bake_wireframe material
- All node connections
- Any hidden nodes or settings

### 2. Paint_Base - Random Grey Patches (UV Mismatch)

**Symptoms:**
- Baked texture has multiple shades of grey
- Pattern looks random/misaligned
- "Looks like texture applied to wrong UV layout"
- Doesn't match mesh geometry

**Current Implementation:**
```python
AmbientOcclusion → ColorRamp → Emission → Output
```

**Critical Insight:**
"UV mismatch" strongly suggests the shader is NOT using UV coordinates!

**Possible Causes:**
A) Shader uses OBJECT or WORLD coordinates instead of UV
B) AO node is calculating in object space
C) The loaded material has coordinate transformation nodes
D) Material uses Generated or Normal coordinates
E) We're baking in wrong coordinate system

**What TexTools Does:**
- Loads material 'bake_paint_base' from materials.blend
- Does NOT use vertex colors (no setVColor)
- Bakes with EMIT type (default)

**Need to Verify:**
- What coordinates does paint_base material use?
- Is there a texture coordinate node?
- Does it use UV mapping or Generated mapping?

## The Core Problem

We're trying to **recreate** materials without knowing what's actually IN them!

TexTools loads these from `resources/materials.blend`:
- `bake_wireframe`
- `bake_position`
- `bake_paint_base`

We need to extract the EXACT node structure from these materials.

## Solution Paths

### Path A: Extract Materials (Recommended)

Run `inspect_textools_materials.py` in Blender to get:
1. Complete node list
2. All connections
3. All parameters
4. Exact shader setup

Then recreate them EXACTLY in Python.

### Path B: Include Materials.blend

Copy the needed materials and ship them with our addon:
1. Extract just bake_wireframe, bake_position, bake_paint_base
2. Create minimal materials.blend
3. Load from there like TexTools does

Pros: Guaranteed to work
Cons: Copying TexTools assets

### Path C: Reverse Engineer by Testing

Try different configurations:
1. Test with actual TexTools side-by-side
2. Compare outputs pixel by pixel
3. Iterate until they match

Pros: No dependency on materials extraction
Cons: Very slow trial-and-error

## Immediate Actions Needed

### For Wireframe:
1. Check if Emission should be 1.0 or different value
2. Try baking with DIFFUSE instead of EMIT
3. Verify ColorRamp settings match TexTools
4. Check if wireframe needs specific color space

### For Paint_Base:
1. **CRITICAL**: Determine what coordinates it uses
2. Check if there's a Texture Coordinate node
3. Try using Object coordinates instead of UV
4. Test if it needs Normal input
5. Verify AO settings (distance, samples)

## Debug Script

I've created `inspect_textools_materials.py` which will:
- Load the three materials
- Print complete node structure
- Show all connections
- Display all parameters

**Please run this in Blender and share the output!**

## What I Need From You

To fix this properly, I need ONE of:

1. **Best**: Output from inspect_textools_materials.py
2. **Alternative**: Screenshots of shader editor showing these materials
3. **Manual**: Description of nodes and connections

Without knowing the actual shader setup in materials.blend, I'm essentially guessing.

## Temporary Workaround

Until we have material data, you could:
1. Use TexTools for wireframe and paint_base
2. Use our addon only for position, normal, base_color
3. Process in two passes

Not ideal, but functional.

## Next Steps

1. Run inspection script
2. Share node structure
3. I'll recreate materials exactly
4. Test and verify
5. Ship working addon

The key is: **We must match TexTools exactly, not approximate it.**
