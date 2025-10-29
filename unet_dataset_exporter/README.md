# UNet Dataset Exporter

A high-performance standalone Blender addon for generating texture baking and multi-view rendering datasets for 3D meshes. Designed to process millions of meshes efficiently without any dependency on TexTools.

## Features

### 🎨 Texture Baking Modes
- **Position Map**: World-space XYZ position encoded as RGB
- **Wireframe Map**: High-resolution wireframe overlay (configurable thickness)
- **Paint Base**: Gradient reference map for painting
- **Normal Map (Object Space)**: Object-space normal mapping
- **Base Color**: Material base color extraction
- **Ambient Occlusion**: High-quality AO with configurable samples
- **Thickness**: Inverted AO for thickness/cavity detection
- **Curvature**: Surface curvature detection

### 📷 Multi-View Rendering
- Configurable number of camera views (default: 8-view turnaround)
- Smart camera distance calculation across all views
- Prevents clipping while maximizing mesh size in frame
- Preserves original camera logic with perfect framing
- Black background for clean masking

### ⚡ Performance Optimizations
- **Batch Processing**: Process meshes in configurable batch sizes
- **Memory Management**: Automatic cleanup of unused images, materials, and data
- **Incremental Saving**: Optional .blend file saving between batches
- **Crash Recovery**: Process can be resumed from where it left off
- **Progress Tracking**: Detailed statistics and time estimates

### 🔧 Technical Features
- No TexTools dependency - completely standalone
- Blender 4.5+ compatible
- Cycles-based baking for high quality
- EEVEE rendering for speed
- Automatic UV unwrapping if needed
- Configurable resolutions per bake type

## Installation

1. Download or clone this repository
2. In Blender, go to Edit → Preferences → Add-ons
3. Click "Install" and select the `unet_dataset_exporter` folder
4. Enable the "UNet Dataset Exporter" addon

Or manually copy the `unet_dataset_exporter` folder to your Blender addons directory:
- Windows: `%APPDATA%\Blender Foundation\Blender\4.5\scripts\addons\`
- macOS: `~/Library/Application Support/Blender/4.5/scripts/addons/`
- Linux: `~/.config/blender/4.5/scripts/addons/`

## Usage

### Quick Start

1. **Open the panel**:
   - View3D → Sidebar (N key) → "UNet Exporter" tab

2. **Configure settings**:
   - Set output path
   - Choose bake modes (enable/disable as needed)
   - Adjust resolutions
   - Configure camera settings

3. **Select meshes**:
   - Select all mesh objects you want to process

4. **Export**:
   - Click "Export Dataset" button
   - Monitor progress in the console

### Settings Explained

#### Output Settings
- **Output Path**: Base directory for all exported files
  - Creates subdirectories for each bake mode
  - Creates `textures_backup` folder for saved baked textures

#### Resolution
- **Bake Resolution**: Resolution for most baked textures (512, 1024, 2048, etc.)
- **Render Resolution**: Square resolution for rendered views (1536 recommended)
- **Wireframe Resolution**: Higher resolution for wireframe maps (4096 for crisp lines)

#### Bake Modes
Enable/disable individual bake modes as needed:
- Position ✓ (recommended for UNet input)
- Wireframe ✓ (recommended for UNet target)
- Paint Base ✓ (provides UV reference)
- Normal (Object) (optional, for 3D reconstruction)
- Base Color (optional, for texture datasets)
- AO, Curvature, Thickness (optional, advanced features)

#### Camera Settings
- **Camera Views**: Number of turnaround positions (8 = 360°/8 = 45° apart)
- **Focal Length**: Camera lens focal length in mm (50mm = realistic)
- **Coverage Padding**: Safety margin to prevent edge clipping (1.15 = 15% padding)

#### Batch Processing
- **Batch Size**: Process N meshes before cleanup (50-100 recommended)
  - 0 = process all at once (only for small datasets)
  - Larger batches = faster but more memory
  - Smaller batches = slower but safer for large datasets
- **Auto Cleanup**: Remove baked images from memory after each mesh
- **Save Incrementally**: Save .blend file after each batch (crash recovery)

### Output Structure

```
output_path/
├── position/
│   ├── mesh_name_timestamp_view00.png
│   ├── mesh_name_timestamp_view01.png
│   └── ...
├── wireframe/
│   ├── mesh_name_timestamp_view00.png
│   └── ...
├── paint_base/
│   └── ...
├── normal_object/
│   └── ...
├── base_color/
│   └── ...
└── textures_backup/
    ├── mesh_name_timestamp_position.png
    ├── mesh_name_timestamp_wireframe.png
    └── ...
```

Each mesh generates:
- N views × M bake modes rendered images
- M baked texture files (in textures_backup)

Example with 8 views and 3 modes (position, wireframe, paint_base):
- 24 rendered view images (8 × 3)
- 3 baked texture files

## Performance Guide

### Recommended Settings by Dataset Size

**Small Dataset (1-100 meshes)**:
```
Batch Size: 0 (process all)
Auto Cleanup: No
Bake Resolution: 1024
Render Resolution: 2048
```

**Medium Dataset (100-1,000 meshes)**:
```
Batch Size: 50
Auto Cleanup: Yes
Bake Resolution: 512
Render Resolution: 1536
Save Incrementally: Yes
```

**Large Dataset (1,000-10,000 meshes)**:
```
Batch Size: 25
Auto Cleanup: Yes
Bake Resolution: 512
Render Resolution: 1024
Save Incrementally: Yes
```

**Massive Dataset (10,000+ meshes)**:
```
Batch Size: 10
Auto Cleanup: Yes
Bake Resolution: 256
Render Resolution: 512
Save Incrementally: Yes
Process in multiple sessions
```

### Time Estimates

Based on typical hardware (modern GPU):
- Simple mesh (1K tris): ~5-10 seconds
- Medium mesh (10K tris): ~15-30 seconds
- Complex mesh (100K tris): ~30-60 seconds

For 1 million meshes at 20s average:
- Total time: ~20,000,000 seconds
- = ~5,556 hours
- = ~231 days continuous processing
- **Recommendation**: Distribute across multiple machines

### Optimization Tips

1. **Reduce Resolution**: Lower resolutions drastically speed up baking
2. **Disable Unused Modes**: Only enable bake modes you need
3. **Reduce Camera Views**: 4 views instead of 8 cuts time in half
4. **Use Multiple Machines**: Process different batches in parallel
5. **Close Blender UI**: Run in background/command line for better performance
6. **Disable AO/Thickness**: These require many samples and are slowest
7. **SSD Storage**: Use SSD for output directory

## Scripting / Command Line

You can automate the export process with Python:

```python
import bpy

# Get settings
settings = bpy.context.scene.unet_exporter_settings

# Configure
settings.output_path = "//my_dataset/"
settings.bake_position = True
settings.bake_wireframe = True
settings.bake_paint_base = True
settings.render_resolution = 1024
settings.camera_count = 8
settings.batch_size = 50
settings.auto_cleanup = True

# Select meshes
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        obj.select_set(True)

# Export
bpy.ops.unet.export_dataset()
```

Run from command line:
```bash
blender my_file.blend --background --python export_script.py
```

## Comparison with Original Script

### Original `blender_unet29_exporter_script.py`:
- ✗ Depends on TexTools addon
- ✗ Can only handle ~100 meshes
- ✗ Crashes with larger datasets
- ✗ Limited to position, wireframe, paint_base
- ✗ No batch processing
- ✗ No memory management

### New `unet_dataset_exporter`:
- ✓ Completely standalone
- ✓ Handles millions of meshes
- ✓ Built-in crash recovery
- ✓ Supports 8 different bake modes
- ✓ Advanced batch processing
- ✓ Automatic memory cleanup
- ✓ Progress tracking and estimates
- ✓ Configurable batch sizes
- ✓ Preserves all camera logic
- ✓ GUI panel for easy configuration

### What's Preserved:
- ✓ Exact camera positioning logic
- ✓ Smart framing across all views
- ✓ Optimal distance calculation
- ✓ Turnaround view generation
- ✓ World origin XY rotation
- ✓ Mesh center Z height
- ✓ Coverage padding system

## Troubleshooting

### "No mesh objects selected"
- Make sure you have mesh objects selected before clicking Export

### "Export failed: ..."
- Check console for detailed error
- Try reducing batch size
- Ensure output path is writable
- Check mesh has faces/vertices

### Out of Memory
- Reduce batch size
- Enable auto cleanup
- Lower resolution settings
- Close other applications
- Reduce number of bake modes

### Slow Performance
- Enable auto cleanup
- Use smaller resolutions
- Reduce camera view count
- Disable AO/thickness modes
- Use SSD for output

### Blender Crashes
- Enable "Save Incrementally"
- Reduce batch size to 10-25
- Process smaller subsets
- Check system memory

## Technical Details

### Module Structure
```
unet_dataset_exporter/
├── __init__.py           # Main addon registration, UI panel, operators
├── bake_engine.py        # Core texture baking, shader node creation
├── render_engine.py      # Camera placement, multi-view rendering
├── batch_processor.py    # Batch processing, memory management
└── utils.py              # Helper functions, cleanup utilities
```

### Shader Node Implementation
Each bake mode creates shader nodes procedurally:
- **Position**: Geometry node → Emission
- **Wireframe**: Wireframe node → ColorRamp → Emission
- **Paint Base**: Geometry Z → MapRange → ColorRamp → Emission
- **Normal (Object)**: Standard Cycles normal bake (OBJECT space)
- **Base Color**: DIFFUSE bake with color pass only
- **AO**: Standard Cycles AO bake
- **Thickness**: Inverted normals → AO → Emission

### Camera Distance Algorithm
1. Get object bounding box in world space
2. For each camera angle in turnaround:
   - Calculate view direction vector
   - Project bounding box corners onto view plane
   - Calculate maximum extent (effective radius)
   - Calculate required distance for this angle
3. Use maximum distance across all angles
4. Apply coverage padding
5. Ensure minimum distance threshold

This ensures perfect framing without clipping across all views.

## License

This addon is released under the same license as the TexTools addon (GPL).

## Credits

- Original camera logic from `blender_unet29_exporter_script.py`
- Baking techniques inspired by TexTools addon
- Developed for large-scale 3D dataset generation

## Support

For issues, questions, or improvements, please open an issue on the repository.
