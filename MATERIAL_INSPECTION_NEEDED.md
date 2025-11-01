# Material Inspection Instructions

Since I cannot directly inspect the .blend files in this environment, I need you to run a material inspection script in Blender to understand what TexTools actually creates.

## Steps to Extract Material Information:

### 1. Run the Inspector Script

In Blender 4.5 with TexTools installed:

```python
# Open Blender
# Go to Scripting workspace
# Open: inspect_textools_materials.py
# Click "Run Script"
# Copy ALL console output
```

### 2. What I Need to Know

For each material (wireframe, position, paint_base), I need:

**Node Structure:**
- What nodes exist?
- How are they connected?
- What are the exact parameters?

**Critical Details for Wireframe:**
- Is wireframe using ShaderNodeWireframe?
- How is Value node connected?
- What are the ColorRamp settings?
- Is it baking with EMIT or something else?

**Critical Details for Paint_Base:**
- Does it use vertex colors or texture baking?
- If vertex colors: How are they set up?
- If textures: What shader nodes?
- Is there AO involved?

**Critical Details for Position:**
- Does it use Geometry node?
- How is position data encoded?
- Any color correction?

### 3. Alternative: Manual Inspection

If you can't run the script, manually check:

1. Open `resources/materials.blend` in Blender
2. For each material (bake_wireframe, bake_position, bake_paint_base):
   - Open Shader Editor
   - Screenshot the node setup
   - Note all node types and connections
   - Note all parameter values

### 4. Possible Issues with Current Implementation

Based on your feedback:

**Wireframe (grey silhouette):**
- My shader might not be connected correctly
- ColorRamp settings might be wrong
- Emission strength might be wrong
- Baking might use wrong type (EMIT vs DIFFUSE)

**Paint_Base (UV mismatch):**
- This strongly suggests it's using VERTEX COLORS not texture baking!
- TexTools might paint vertex colors then bake those
- OR it's using a completely different approach

## What I'll Do Once I Have the Data

Once you provide the material node structure, I will:

1. Create EXACT replicas of those shader setups
2. Use the same baking approach (EMIT, DIFFUSE, etc.)
3. Match all parameters precisely
4. Handle vertex colors if that's what paint_base uses

## Temporary Workaround

Until we have the exact material data, I could try a different approach:

**Option A: Ship TexTools Materials**
- Include materials.blend in the addon
- Load from there (like TexTools does)
- Pro: Guaranteed to work
- Con: Copying TexTools assets

**Option B: Reverse Engineer from Blender**
- You run the inspector script
- I get exact node structure
- I recreate it programmatically
- Pro: Clean standalone implementation
- Con: Requires your help to run script

**Option C: Trial and Error**
- Try different shader configurations
- Test each variation
- Slow but possible

I recommend Option B - please run the inspector script and share the output.
