# Final Analysis & Fix Attempt

## Key Insight: Paint_Base UV Mismatch

The "looks like texture applied to wrong UV" symptom is CRITICAL.

This happens when a shader uses:
- **Object** coordinates instead of **UV** coordinates
- **Generated** coordinates
- **Normal** or **Position** in object/world space

## Most Likely Explanation

Paint_base in TexTools probably:
1. Uses AO or similar in OBJECT space
2. The material has a Texture Coordinate node
3. It specifically uses OBJECT or GENERATED coords
4. This gets baked to UV space, creating the "mismatch" appearance

## The Fix

I need to ensure the shader uses UV-mapped coordinates, OR
I need to match TexTools by using object coordinates if that's what it does.

## Testing Approach

Since I can't inspect materials.blend, I'll create multiple versions:
1. UV-based paint_base
2. Object-based paint_base
3. Generated-based paint_base

And provide a way to switch between them.

## Wireframe Issue

Likely causes ranked:
1. Emission node not set to strength 1.0
2. ColorRamp values incorrect
3. Bake needs specific render settings
4. Need to ensure object is in specific state

## Next Implementation

Create test modes that try different approaches.
