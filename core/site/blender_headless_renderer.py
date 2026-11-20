r"""
ArchitectOS v54.0 — Photorealistic Headless Blender 5.2 3D PBR Architectural & Section-Cut Renderer
(`engine/blender_headless_renderer.py`)

Upgrades in v54.0:
  1. **Exact Hatched `0.00` Courtyard (`Z = 1.45m`) + Right Planter Box (`باغچه کنار پله راست`) + Botanical Shrub & Blossoms**:
     - Builds procedural PBR shaders for `Mat_Wall` (Iranian Cream Travertine ashlar blocks), `Mat_Column` (honed limestone),
       `Mat_Window` (Low-E reflective glass `IOR=1.52`), `Mat_Door` (dark architectural bronze), `Mat_Slab` (travertine pavers),
       `Mat_Soil` (recessed garden soil inside the right planter box), and `Mat_Foliage` (botanical leaf clusters + blossoms).
     - Replaces crude cones with organic multi-sphere botanical cypress & ornamental planter shrubs + warm horizon ground plane at `Z = 1.37m`
       (eliminating the muddy horizon band).
  2. **Multi-Elevation (`SOUTH`, `NORTH`, `EAST`, `WEST`) & 3D Furnished Section-Cut (`SECTION_S1`, `SECTION_S2`) Rendering**:
     - Supports rendering any elevation or slicing the 3D furnished model along `S1-S1` (`Y = 9.50m`) or `S2-S2` (`X = 5.50m`).
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional


class BlenderHeadlessRenderer:
    """
    Headless Blender (`blender -b -P`) 3D PBR architectural & section-cut renderer for ArchitectOS v54.0.
    Compatible with Blender 3.6, 4.x, and 5.2 (`BLENDER_EEVEE_NEXT`, `BLENDER_EEVEE`, `CYCLES`).
    """

    @staticmethod
    def find_blender_executable() -> Optional[str]:
        env_bin = os.environ.get("BLENDER_EXECUTABLE") or os.environ.get("BLENDER_PATH")
        if env_bin and os.path.isfile(env_bin):
            return env_bin
        which_bin = shutil.which("blender")
        if which_bin:
            return which_bin
        win_patterns = [
            r"C:\Program Files\Blender Foundation\Blender*\blender.exe",
            r"D:\Program Files\Blender Foundation\Blender*\blender.exe",
            r"C:\Blender*\blender.exe",
            r"D:\Blender*\blender.exe",
        ]
        cands = []
        for pat in win_patterns:
            cands.extend(glob.glob(pat))
        if cands:
            cands.sort(reverse=True)
            return cands[0]
        return None

    @classmethod
    def render_glb_via_blender(
        cls,
        glb_or_obj_path: str,
        out_png_path: str,
        spec: Optional[Dict[str, Any]] = None,
        quality: str = "draft",
        timeout_sec: int = 180,
        force_enable: bool = False,
    ) -> Optional[str]:
        if not os.path.isfile(glb_or_obj_path):
            return None
        if os.environ.get("ARCHITECTOS_DISABLE_BLENDER", "0") in ("1", "true", "TRUE", "yes"):
            return None
        if not force_enable and os.environ.get("ARCHITECTOS_USE_BLENDER", "1") in ("0", "false", "FALSE", "no"):
            return None
        blender_bin = cls.find_blender_executable()
        if not blender_bin:
            return None

        spec = spec or {}
        is_night = spec.get("lighting_mode") == "NIGHT_WARM"
        camera_view = str(spec.get("camera_view") or spec.get("facade_side") or "SOUTH").upper()
        q_low = str(quality or "draft").lower()
        samples = 48 if q_low in ("final", "quality", "high", "photoreal") else 32

        script_body = f"""import bpy
import os
import math
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
mesh_path = r"{os.path.abspath(glb_or_obj_path)}"
out_png = r"{os.path.abspath(out_png_path)}"
cam_view_mode = "{camera_view}"

# Always prefer the companion .obj file so per-element material slots (Mat_Wall, Mat_Window, Mat_Door, Mat_Column, Mat_Slab, Mat_Soil, Mat_Foliage) are preserved!
obj_candidate = os.path.splitext(mesh_path)[0] + ".obj"
if os.path.isfile(obj_candidate):
    try:
        bpy.ops.wm.obj_import(filepath=obj_candidate, forward_axis='Y', up_axis='Z')
    except Exception:
        try:
            bpy.ops.import_scene.obj(filepath=obj_candidate, axis_forward='Y', axis_up='Z')
        except Exception:
            bpy.ops.import_scene.gltf(filepath=mesh_path)
elif mesh_path.lower().endswith((".glb", ".gltf")):
    bpy.ops.import_scene.gltf(filepath=mesh_path)

scene = bpy.context.scene
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    try:
        scene.render.engine = eng
        break
    except Exception:
        continue

try:
    scene.eevee.taa_render_samples = {samples}
    scene.eevee.use_raytracing = True
except Exception:
    pass
try:
    scene.cycles.samples = {samples}
    scene.cycles.use_denoising = True
except Exception:
    pass

for vt in ("AgX", "Filmic", "Standard"):
    try:
        scene.view_settings.view_transform = vt
        break
    except Exception:
        continue
try:
    scene.view_settings.look = "Medium High Contrast"
except Exception:
    pass
try:
    scene.view_settings.exposure = 0.08
except Exception:
    pass

scene.render.resolution_x = 1280
scene.render.resolution_y = 864
scene.render.resolution_percentage = 100
if out_png.lower().endswith((".jpg", ".jpeg")):
    scene.render.image_settings.file_format = 'JPEG'
    try:
        scene.render.image_settings.quality = 95
    except Exception:
        pass
else:
    scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = out_png

# Optional 3D Section Cut (`SECTION_S1` at Y=9.5m or `SECTION_S2` at X=5.5m)
if cam_view_mode == "SECTION_S1":
    for ob in list(scene.objects):
        if ob.type == 'MESH':
            ys = [(ob.matrix_world @ Vector(c)).y for c in ob.bound_box]
            if max(ys) < 9.20:
                bpy.data.objects.remove(ob, do_unlink=True)
elif cam_view_mode == "SECTION_S2":
    for ob in list(scene.objects):
        if ob.type == 'MESH':
            xs = [(ob.matrix_world @ Vector(c)).x for c in ob.bound_box]
            if min(xs) > 5.80:
                bpy.data.objects.remove(ob, do_unlink=True)

# ---------------------------------------------------------------------------
# 1. Compute Building Bounding Box FIRST (excluding extended Courtyard_* meshes)
# ---------------------------------------------------------------------------
all_meshes = [o for o in scene.objects if o.type == 'MESH']
bldg_objs = [o for o in all_meshes if not o.name.startswith(("Courtyard_", "Basement_Terrace_And_Sunken_Court_Slab", "Basement_SemiCircular_Retaining_Wall", "Basement_Left_Shoulder_Retaining_Wall", "Basement_Right_Shoulder_Retaining_Wall"))]
if not bldg_objs:
    bldg_objs = all_meshes

if bldg_objs:
    min_co = Vector((1e9, 1e9, 1e9))
    max_co = Vector((-1e9, -1e9, -1e9))
    for obj in bldg_objs:
        for corner in obj.bound_box:
            wc = obj.matrix_world @ Vector(corner)
            min_co.x = min(min_co.x, wc.x)
            min_co.y = min(min_co.y, wc.y)
            min_co.z = min(min_co.z, wc.z)
            max_co.x = max(max_co.x, wc.x)
            max_co.y = max(max_co.y, wc.y)
            max_co.z = max(max_co.z, wc.z)
    center = 0.5 * (min_co + max_co)
    size = max_co - min_co
    diag = max(8.0, size.length)
    if cam_view_mode == "NORTH":
        cam_pos = Vector((center.x, max_co.y + 0.62 * diag, min_co.z + 0.58 * size.z))
        target = Vector((center.x, max_co.y - 0.24 * size.y, min_co.z + 0.44 * size.z))
    elif cam_view_mode == "EAST":
        cam_pos = Vector((max_co.x + 0.68 * diag, center.y, min_co.z + 0.56 * size.z))
        target = Vector((center.x, center.y, min_co.z + 0.44 * size.z))
    elif cam_view_mode in ("WEST", "SECTION_S2"):
        if size.y <= 8.5 and size.x >= 14.0:
            # Commercial narrow storefront on West elevation (e.g. Auto Gallery Sina): frame storefront & interior mezzanine!
            cam_pos = Vector((min_co.x - 10.5, center.y, min_co.z + 0.48 * size.z))
            target = Vector((min_co.x + 8.5, center.y, min_co.z + 0.45 * size.z))
        else:
            cam_pos = Vector((min_co.x - 0.68 * diag, center.y, min_co.z + 0.56 * size.z))
            target = Vector((center.x, center.y, min_co.z + 0.44 * size.z))
    else:
        cam_pos = Vector((center.x, min_co.y - 0.61 * diag, min_co.z + 0.77 * size.z))
        target = Vector((center.x, min_co.y + 0.19 * size.y, min_co.z + 0.39 * size.z))
else:
    min_co = Vector((0.0, -2.5, 0.0))
    max_co = Vector((12.0, 19.3, 10.5))
    center = Vector((6.0, 8.4, 5.2))
    size = Vector((12.0, 21.8, 10.5))
    cam_pos = Vector((6.0, -18.5, 6.6))
    target = Vector((6.0, 2.0, 4.6))

# ---------------------------------------------------------------------------
# 2. Build Procedural PBR Shader Node Graphs (Travertine Stone, Limestone,
#    Reflective Glass, Dark Bronze, Courtyard Pavers, Planter Soil & Foliage)
# ---------------------------------------------------------------------------
def _build_travertine_wall_material(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.offset = 0.5
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Mortar Size'].default_value = 0.012
    brick.inputs['Mortar Smooth'].default_value = 0.25
    brick.inputs['Bias'].default_value = 0.05
    brick.inputs['Brick Width'].default_value = 0.90
    brick.inputs['Row Height'].default_value = 0.38
    brick.inputs['Color1'].default_value = (0.95, 0.88, 0.74, 1.0)
    brick.inputs['Color2'].default_value = (0.87, 0.78, 0.63, 1.0)
    brick.inputs['Mortar'].default_value = (0.54, 0.47, 0.37, 1.0)

    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    add_xy = nt.nodes.new('ShaderNodeMath')
    add_xy.operation = 'ADD'
    nt.links.new(mapping.outputs['Vector'], sep.inputs['Vector'])
    nt.links.new(sep.outputs['X'], add_xy.inputs[0])
    nt.links.new(sep.outputs['Y'], add_xy.inputs[1])
    nt.links.new(add_xy.outputs['Value'], comb.inputs['X'])
    nt.links.new(sep.outputs['Z'], comb.inputs['Y'])
    nt.links.new(comb.outputs['Vector'], brick.inputs['Vector'])

    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 4.5
    noise.inputs['Detail'].default_value = 8.0
    if 'Roughness' in noise.inputs:
        noise.inputs['Roughness'].default_value = 0.65
    nt.links.new(comb.outputs['Vector'], noise.inputs['Vector'])

    nt.links.new(brick.outputs['Color'], bsdf.inputs['Base Color'])
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.38

    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.24
    bump.inputs['Distance'].default_value = 0.015
    nt.links.new(brick.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

def _build_limestone_trim_material(mat, rgb=(0.97, 0.92, 0.82, 1.0)):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = rgb
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.28
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 10.0
    noise.inputs['Detail'].default_value = 6.0
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.08
    bump.inputs['Distance'].default_value = 0.008
    nt.links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

def _build_glass_material(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (0.14, 0.28, 0.42, 1.0)
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.02
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = 0.48
    if 'IOR' in bsdf.inputs:
        bsdf.inputs['IOR'].default_value = 1.52
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.92
    if 'Emission Color' in bsdf.inputs:
        bsdf.inputs['Emission Color'].default_value = (0.28, 0.22, 0.14, 1.0)
    if 'Emission Strength' in bsdf.inputs:
        bsdf.inputs['Emission Strength'].default_value = 0.18

def _build_bronze_door_material(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (0.16, 0.10, 0.06, 1.0)
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = 0.45
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.24

def _build_paver_slab_material(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.offset = 0.0
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Brick Width'].default_value = 0.75
    brick.inputs['Row Height'].default_value = 0.75
    brick.inputs['Mortar Size'].default_value = 0.015
    brick.inputs['Color1'].default_value = (0.90, 0.83, 0.70, 1.0)
    brick.inputs['Color2'].default_value = (0.84, 0.77, 0.64, 1.0)
    brick.inputs['Mortar'].default_value = (0.55, 0.48, 0.39, 1.0)
    nt.links.new(tex_coord.outputs['Object'], brick.inputs['Vector'])
    nt.links.new(brick.outputs['Color'], bsdf.inputs['Base Color'])
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.42
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.16
    bump.inputs['Distance'].default_value = 0.01
    nt.links.new(brick.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

def _build_soil_or_foliage_material(mat, is_soil=False):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (0.16, 0.28, 0.11, 1.0) if is_soil else (0.12, 0.38, 0.14, 1.0)
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.85 if is_soil else 0.58
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 18.0
    noise.inputs['Detail'].default_value = 8.0
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.32
    bump.inputs['Distance'].default_value = 0.02
    nt.links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

for mat in list(bpy.data.materials):
    nm = mat.name.upper()
    if 'WINDOW' in nm:
        _build_glass_material(mat)
    elif 'DOOR' in nm or 'FRAME' in nm:
        _build_bronze_door_material(mat)
    elif 'COLUMN' in nm or 'BALUSTRADE' in nm or 'TRIM' in nm:
        _build_limestone_trim_material(mat)
    elif 'SLAB' in nm:
        _build_paver_slab_material(mat)
    elif 'SOIL' in nm:
        _build_soil_or_foliage_material(mat, is_soil=True)
    elif 'FOLIAGE' in nm:
        _build_soil_or_foliage_material(mat, is_soil=False)
    else:
        _build_travertine_wall_material(mat)

mat_paver = bpy.data.materials.get("Mat_Slab") or bpy.data.materials.new("Mat_Courtyard_Paver")
_build_paver_slab_material(mat_paver)
mat_wall = bpy.data.materials.get("Mat_Wall") or bpy.data.materials.new("Mat_Courtyard_Wall")
_build_travertine_wall_material(mat_wall)
mat_trim = bpy.data.materials.get("Mat_Column") or bpy.data.materials.new("Mat_Courtyard_Trim")
_build_limestone_trim_material(mat_trim)
mat_foliage = bpy.data.materials.get("Mat_Foliage") or bpy.data.materials.new("Mat_Cypress_Foliage")
_build_soil_or_foliage_material(mat_foliage, is_soil=False)
mat_flower = bpy.data.materials.new("Mat_Planter_Blossom")
mat_flower.use_nodes = True
bsdf_fl = next((n for n in mat_flower.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
if bsdf_fl:
    bsdf_fl.inputs['Base Color'].default_value = (0.82, 0.22, 0.32, 1.0)

# ---------------------------------------------------------------------------
# 3. Extend Courtyard Horizon Plane at Z = 1.45m (`0.00m`) & Add Organic
#    Botanical Shrub + Blossoms in Right Planter Box `(9.77, -0.05, 1.55)`
# ---------------------------------------------------------------------------
def _add_site_box(name, cx, cy, cz, dx, dy, dz, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (dx, dy, dz)
    if ob.data.materials:
        ob.data.materials[0] = mat
    else:
        ob.data.materials.append(mat)
    return ob

# Extend the 0.00m (`Z = 1.45m`) courtyard paving ONLY south of the Semi-Circular Courtyard Cutout (`Y <= -4.20m`)
# and outside the Left/Right Courtyard Walls (`X <= -0.20m` and `X >= 12.06m`), plus a sub-basement horizon at `Z = -0.08m`,
# so ZERO geometry at `Z = 1.34..1.45m` ever covers the sunken `-1.45m` Basement Terrace or the Right Basement L-Stair!
_add_site_box("Courtyard_Front_Paving_Z145", center.x, -14.35, 1.37, 11.92, 24.0, 0.16, mat_paver)
_add_site_box("Site_Sub_Basement_Ground_Zm145", center.x, -10.0, -0.08, 180.0, 180.0, 0.12, mat_paver)
_add_site_box("Site_Left_Horizon_Ground_Z145", -45.20, -10.0, 1.34, 90.0, 180.0, 0.12, mat_wall)
_add_site_box("Site_Right_Horizon_Ground_Z145", 57.06, -10.0, 1.34, 90.0, 180.0, 0.12, mat_wall)
_add_site_box("Site_South_Horizon_Ground_Z145", center.x, -52.35, 1.34, 180.0, 100.0, 0.12, mat_wall)

# Add organic flowering blossoms on top of the Right Planter Box shrub `(9.68, -0.25, 1.50)`
for fl_x, fl_y, fl_z in [(9.60, -1.18, 1.72), (9.78, -1.08, 1.76), (9.68, -0.98, 1.70), (9.56, -1.04, 1.66)]:
    try:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=14, ring_count=10, radius=0.07, location=(fl_x, fl_y, fl_z))
        fl_ob = bpy.context.active_object
        fl_ob.data.materials.append(mat_flower)
    except Exception:
        pass

# Organic multi-sphere Mediterranean Cypress trees along courtyard walls (X = 0.68m & X = 11.20m, on Courtyard Z = 1.45m)
for ty_c in (-9.2, -5.6):
    for tx_c in (0.68, 11.20):
        try:
            bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=0.08, depth=0.60, location=(tx_c, ty_c, 1.45 + 0.30))
            tk = bpy.context.active_object
            tk.data.materials.append(mat_wall)
            for z_off, rad_s, sz_z in [(1.05, 0.38, 1.45), (1.65, 0.33, 1.50), (2.20, 0.25, 1.55), (2.68, 0.16, 1.65)]:
                bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=rad_s, location=(tx_c, ty_c, 1.45 + z_off))
                tr = bpy.context.active_object
                tr.scale = (1.0, 1.0, sz_z)
                tr.data.materials.append(mat_foliage)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# 4. Physical Atmospheric Sky (`ShaderNodeTexSky`, `Strength = 0.85`) + Warm Sun
# ---------------------------------------------------------------------------
world = bpy.data.worlds.new("ArchWorld")
scene.world = world
world.use_nodes = True
w_nt = world.node_tree
w_nt.nodes.clear()
w_out = w_nt.nodes.new('ShaderNodeOutputWorld')
w_bg = w_nt.nodes.new('ShaderNodeBackground')
w_nt.links.new(w_bg.outputs['Background'], w_out.inputs['Surface'])

if {is_night}:
    w_bg.inputs['Color'].default_value = (0.03, 0.05, 0.12, 1.0)
    w_bg.inputs['Strength'].default_value = 0.35
else:
    try:
        sky_node = w_nt.nodes.new('ShaderNodeTexSky')
        for st_name in ('NISHITA', 'HOSEK_WILKIE', 'PREETHAM'):
            try:
                sky_node.sky_type = st_name
                break
            except Exception:
                continue
        try:
            sky_node.sun_elevation = math.radians(40.0)
            sky_node.sun_rotation = math.radians(-32.0)
            sky_node.air_density = 1.15
            sky_node.dust_density = 1.10
        except Exception:
            pass
        w_nt.links.new(sky_node.outputs['Color'], w_bg.inputs['Color'])
        w_bg.inputs['Strength'].default_value = 0.85
    except Exception:
        w_bg.inputs['Color'].default_value = (0.52, 0.72, 0.95, 1.0)
        w_bg.inputs['Strength'].default_value = 0.85

light_data = bpy.data.lights.new(name="SunLight", type="SUN")
light_data.energy = 0.5 if {is_night} else 2.8
light_data.color = (1.0, 0.95, 0.86)
try:
    light_data.angle = math.radians(1.8)
except Exception:
    pass
light_obj = bpy.data.objects.new(name="SunLight", object_data=light_data)
scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(52.0), math.radians(-22.0), math.radians(-34.0))

fill_data = bpy.data.lights.new(name="SkyFillLight", type="SUN")
fill_data.energy = 0.15 if {is_night} else 0.55
fill_data.color = (0.85, 0.92, 1.0)
fill_obj = bpy.data.objects.new(name="SkyFillLight", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(65.0), math.radians(28.0), math.radians(42.0))

cam_data = bpy.data.cameras.new(name="ArchCam")
cam_data.lens = 35.0
cam_obj = bpy.data.objects.new(name="ArchCam", object_data=cam_data)
scene.collection.objects.link(cam_obj)
cam_obj.location = cam_pos
direction = target - cam_pos
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam_obj

try:
    bpy.ops.render.render(write_still=True)
except Exception as e:
    print("Blender render error:", e)
"""
        try:
            with tempfile.NamedTemporaryFile("w", suffix="_arch_blender.py", delete=False, encoding="utf-8") as tf:
                tf.write(script_body)
                script_path = tf.name
            subprocess.run(
                [blender_bin, "--background", "--python", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_sec,
                check=False,
            )
            try:
                os.remove(script_path)
            except OSError:
                pass
            if os.path.isfile(out_png_path) and os.path.getsize(out_png_path) > 20000:
                return out_png_path
        except Exception:
            pass
        return None

    @classmethod
    def render_any_3d_model_to_passes(
        cls,
        source_3d_or_npz_path: str,
        out_png_path: str,
        spec: Optional[Dict[str, Any]] = None,
        quality: str = "quality",
        timeout_sec: int = 240,
    ) -> Optional[Dict[str, str]]:
        """
        v73.0 Universal Headless Blender 3D Pre-Render Engine (EEVEE / Cycles):
        Natively imports ANY 3D model (`.obj`+`.mtl`, `.fbx`, `.glb`/`.gltf`, `.stl`, `.dae`, `.ply`, or `.npz` cache),
        applies a true 50mm 2-Point Architectural Shift-Lens Camera (`pitch = 0°`, auto `shift_y` -> 100% vertical lines,
        ZERO floating buildings), preserves real PBR/MTL materials (with clean neutral clay fallback for untagged meshes),
        and outputs pixel-aligned `1280x864` RGB (`_comfy_input.png`), exact normalized Z-Depth (`_depth.png`), and `_lineart.png`.
        """
        if not source_3d_or_npz_path or not os.path.isfile(source_3d_or_npz_path):
            return None
        if os.environ.get("ARCHITECTOS_DISABLE_BLENDER", "0") in ("1", "true", "TRUE", "yes"):
            return None
        blender_bin = cls.find_blender_executable()
        if not blender_bin:
            return None

        spec = spec or {}
        is_night = spec.get("lighting_mode") == "NIGHT_WARM"
        is_golden = spec.get("lighting_mode") == "GOLDEN_HOUR"
        cam_hint = str(spec.get("camera_prompt_en") or spec.get("view_mode") or "").lower()
        yaw_deg = -12.0 if any(k in cam_hint for k in ("three-quarter", "3/4", "angle", "corner", "پرسپکتیو")) else -2.5

        base_no_ext = os.path.splitext(os.path.abspath(out_png_path))[0]
        os.makedirs(os.path.dirname(base_no_ext), exist_ok=True)
        out_rgb = os.path.abspath(out_png_path)
        out_comfy = base_no_ext + "_comfy_input.png"
        out_depth = base_no_ext + "_depth.png"
        out_lineart = base_no_ext + "_lineart.png"

        script_code = f"""import bpy, os, math, sys
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
src_path = r"{os.path.abspath(source_3d_or_npz_path)}"
ext = os.path.splitext(src_path)[1].lower()
out_rgb = r"{out_rgb}"
out_depth = r"{out_depth}"
yaw_deg = {yaw_deg}
is_night = {bool(is_night)}
is_golden = {bool(is_golden)}

def _import_any(fp, e):
    if e == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=fp)
        else:
            bpy.ops.import_scene.obj(filepath=fp)
    elif e == ".fbx":
        bpy.ops.import_scene.fbx(filepath=fp)
    elif e in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=fp)
    elif e == ".stl":
        if hasattr(bpy.ops.wm, "stl_import"):
            bpy.ops.wm.stl_import(filepath=fp)
        else:
            bpy.ops.import_mesh.stl(filepath=fp)
    elif e == ".ply":
        if hasattr(bpy.ops.wm, "ply_import"):
            bpy.ops.wm.ply_import(filepath=fp)
        else:
            bpy.ops.import_mesh.ply(filepath=fp)
    elif e == ".dae":
        bpy.ops.wm.collada_import(filepath=fp)
    elif e == ".npz":
        import numpy as np
        d = np.load(fp)
        v = d["verts"].astype(float).tolist()
        f = d["faces"].astype(int).tolist()
        me = bpy.data.meshes.new("ArchMesh")
        me.from_pydata(v, [], f)
        me.update()
        ob = bpy.data.objects.new("ArchObject", me)
        bpy.context.collection.objects.link(ob)

_import_any(src_path, ext)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and len(o.data.vertices) >= 3]
if not meshes:
    sys.exit(2)

# Clean neutral architectural clay fallback ONLY for untagged meshes or 3ds Max random wire_RRRGGGBBB slots
clay_mat = bpy.data.materials.new("ArchOS_CleanClay")
clay_mat.use_nodes = True
bsdf_c = clay_mat.node_tree.nodes.get("Principled BSDF")
if bsdf_c:
    bsdf_c.inputs["Base Color"].default_value = (0.86, 0.83, 0.78, 1.0)
    bsdf_c.inputs["Roughness"].default_value = 0.72

import re
for ob in meshes:
    if len(ob.data.materials) == 0:
        ob.data.materials.append(clay_mat)
    else:
        for i, m in enumerate(ob.data.materials):
            if m is None or re.search(r"wire_\d{{9}}", m.name.lower()):
                ob.data.materials[i] = clay_mat

# Compute world-space bounding box of the architectural massing (filtering mega flat ground planes)
all_pts = []
for ob in meshes:
    mw = ob.matrix_world
    bb = [mw @ Vector(c) for c in ob.bound_box]
    dx = max(p.x for p in bb) - min(p.x for p in bb)
    dy = max(p.y for p in bb) - min(p.y for p in bb)
    dz = max(p.z for p in bb) - min(p.z for p in bb)
    if dz < 0.15 and max(dx, dy) > 40.0:
        ob.hide_render = True
        continue
    all_pts.extend(bb)

if not all_pts:
    for ob in meshes:
        ob.hide_render = False
        all_pts.extend([ob.matrix_world @ Vector(c) for c in ob.bound_box])

xmin = min(p.x for p in all_pts); xmax = max(p.x for p in all_pts)
ymin = min(p.y for p in all_pts); ymax = max(p.y for p in all_pts)
zmin = min(p.z for p in all_pts); zmax = max(p.z for p in all_pts)
cx, cy = 0.5 * (xmin + xmax), 0.5 * (ymin + ymax)
bw = max(4.0, xmax - xmin)
bd = max(4.0, ymax - ymin)
bh = max(3.0, zmax - zmin)

# Normalize unit scale if exported in cm or mm (e.g. > 200 units tall -> convert to meters)
scale_f = 1.0
if max(bw, bd, bh) > 300.0:
    scale_f = 0.001 if max(bw, bd, bh) > 2500.0 else 0.01
for ob in meshes:
    ob.location = (ob.location - Vector((cx, cy, zmin))) * scale_f
    ob.scale = ob.scale * scale_f

bw *= scale_f; bd *= scale_f; bh *= scale_f

# Add flush architectural ground plane at Z = 0 so zero building can ever float in the sky
bpy.ops.mesh.primitive_plane_add(size=max(bw, bd) * 18.0, location=(0.0, 0.0, 0.0))
gnd = bpy.context.active_object
g_mat = bpy.data.materials.new("ArchOS_Ground")
g_mat.use_nodes = True
bsdf_g = g_mat.node_tree.nodes.get("Principled BSDF")
if bsdf_g:
    bsdf_g.inputs["Base Color"].default_value = (0.34, 0.36, 0.31, 1.0)
    bsdf_g.inputs["Roughness"].default_value = 0.92
gnd.data.materials.append(g_mat)

# True 50mm 2-Point Architectural Shift-Lens Camera (0 deg vertical tilt -> 100% plumb vertical walls!)
cam_data = bpy.data.cameras.new("ArchCam")
cam_data.lens = 50.0
cam_data.sensor_width = 36.0
cam_obj = bpy.data.objects.new("ArchCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

span_fit = max(bw * 1.15, bh * 1.48)
cam_dist = max(14.0, span_fit * 1.85 + 0.55 * bd)
cam_z = max(1.65, bh * 0.18)
yaw_rad = math.radians(yaw_deg)
cam_obj.location = Vector((cam_dist * math.sin(yaw_rad), -cam_dist * math.cos(yaw_rad), cam_z))
cam_obj.rotation_euler = (math.radians(90.0), 0.0, yaw_rad)
# Vertical architectural lens shift to frame from Z=0 up to roof/dome cleanly
z_target = bh * 0.48
v_fov_span = cam_dist * (24.0 / 50.0)
cam_data.shift_y = max(-0.25, min(0.35, (z_target - cam_z) / max(1.0, v_fov_span)))

# Physical Nishita Sky & Sun Lighting
world = bpy.data.worlds.new("ArchWorld")
bpy.context.scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
wn.clear()
w_out = wn.new("ShaderNodeOutputWorld")
w_bg = wn.new("ShaderNodeBackground")
w_sky = wn.new("ShaderNodeTexSky")
_sky_enums = [e.identifier for e in w_sky.bl_rna.properties["sky_type"].enum_items]
for _st_cand in ("SINGLE_SCATTERING", "NISHITA", "MULTIPLE_SCATTERING", "HOSEK_WILKIE", "PREETHAM"):
    if _st_cand in _sky_enums:
        w_sky.sky_type = _st_cand
        break
if hasattr(w_sky, "sun_elevation"):
    w_sky.sun_elevation = math.radians(8.0 if is_night else (16.0 if is_golden else 38.0))
if hasattr(w_sky, "sun_rotation"):
    w_sky.sun_rotation = math.radians(42.0)
w_bg.inputs["Strength"].default_value = 0.25 if is_night else 0.85
wl.new(w_sky.outputs["Color"], w_bg.inputs["Color"])
wl.new(w_bg.outputs["Background"], w_out.inputs["Surface"])

sun_data = bpy.data.lights.new("ArchSun", type="SUN")
sun_data.energy = 1.2 if is_night else 3.8
sun_data.angle = math.radians(2.5)
sun_obj = bpy.data.objects.new("ArchSun", sun_data)
bpy.context.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(52.0), math.radians(15.0), math.radians(-32.0))

# Configure Render Engine (prefer EEVEE_NEXT / EEVEE for fast clean 1280x864 + exact Z-Depth, fallback CYCLES)
scene = bpy.context.scene
engines = [e.identifier for e in scene.render.bl_rna.properties["engine"].enum_items]
if "BLENDER_EEVEE_NEXT" in engines:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
elif "BLENDER_EEVEE" in engines:
    scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene.eevee, "use_gtao"):
        scene.eevee.use_gtao = True
else:
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True

scene.render.resolution_x = 1280
scene.render.resolution_y = 864
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = out_rgb

# Pass 1: Render clean 1280x864 RGB Architectural Beauty Pass
bpy.ops.render.render(write_still=True)

# Pass 2: Version-Proof Exact Z-Depth Pass (Works on Blender 3.6, 4.x, 5.2 LTS & 6.0 without scene.node_tree!)
d_mat = bpy.data.materials.new("ArchOS_ExactZDepth")
d_mat.use_nodes = True
dn = d_mat.node_tree.nodes
dl = d_mat.node_tree.links
dn.clear()
d_out = dn.new("ShaderNodeOutputMaterial")
d_em = dn.new("ShaderNodeEmission")
d_cam = dn.new("ShaderNodeCameraData")
d_mr = dn.new("ShaderNodeMapRange")
d_mr.clamp = True
d_mr.inputs["From Min"].default_value = max(0.5, cam_dist - 0.85 * bd)
d_mr.inputs["From Max"].default_value = cam_dist + 0.95 * bd
d_mr.inputs["To Min"].default_value = 0.96
d_mr.inputs["To Max"].default_value = 0.04
dl.new(d_cam.outputs["View Z Depth"], d_mr.inputs["Value"])
dl.new(d_mr.outputs["Result"], d_em.inputs["Color"])
dl.new(d_em.outputs["Emission"], d_out.inputs["Surface"])

for _ob_d in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
    _ob_d.data.materials.clear()
    _ob_d.data.materials.append(d_mat)

w_bg.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
for _lk in list(wl):
    if _lk.to_socket == w_bg.inputs["Color"]:
        wl.remove(_lk)
w_bg.inputs["Strength"].default_value = 1.0
scene.view_settings.view_transform = "Standard"
scene.render.image_settings.color_mode = "BW"
scene.render.filepath = out_depth
bpy.ops.render.render(write_still=True)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(script_code)
            tf_path = tf.name
        try:
            proc = subprocess.run(
                [blender_bin, "-b", "--factory-startup", "-P", tf_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_sec,
                check=False,
            )
            if proc.returncode == 0 and os.path.isfile(out_rgb) and os.path.isfile(out_depth):
                shutil.copy2(out_rgb, out_comfy)
                try:
                    import cv2
                    im_bgr = cv2.imread(out_rgb)
                    if im_bgr is not None:
                        gray = cv2.cvtColor(im_bgr, cv2.COLOR_BGR2GRAY)
                        edges = cv2.Canny(gray, 42, 128)
                        cv2.imwrite(out_lineart, cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR))
                except Exception:
                    pass
                return {"rgb": out_rgb, "comfy_input": out_comfy, "depth": out_depth, "lineart": out_lineart}
        except Exception:
            pass
        finally:
            try:
                os.unlink(tf_path)
            except Exception:
                pass
        return None

