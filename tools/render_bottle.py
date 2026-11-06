"""Render one product bottle in Blender: a lathed bottle with the label art wrapped on it.

    python3 tools/render_bottle.py spec.json

spec.json:
  profile      [[y, r], ...] bottle outline in inches, y from the base up, r = radius
  parts        [[y_from, y_to, "#rrggbb", roughness], ...] colour bands (cap, shoulder, body)
  label        path to the front label PNG (rendered from the print PDF)
  label_size   [width_in, height_in] of the label art
  label_y      height of the label's bottom edge above the base, inches
  out          output PNG (transparent background)
  px           output height in pixels (default 1800)

Same camera, lens and three-light studio on every bottle, so the whole line
reads as one set. Label art comes from the print files and is never edited.
"""
import json, math, sys
import bpy, bmesh

spec = json.load(open(sys.argv[1]))
prof = spec["profile"]
H = max(y for y, r in prof)
R = max(r for y, r in prof)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def hex_rgb(h):
    h = h.lstrip("#")
    return [((int(h[i:i + 2], 16) / 255) ** 2.2) for i in (0, 2, 4)] + [1]


def plastic(name, color, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hex_rgb(color)
    b.inputs["Roughness"].default_value = rough
    return m


def lathe(name, pts, segs=96, a0=0.0, a1=2 * math.pi, closed=True, uv=False):
    """Revolve [(y, r)] around Z. Optional UVs: u along the angle, v along the height."""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    n = segs if closed else segs + 1
    rings = []
    for y, r in pts:
        ring = []
        for i in range(n):
            a = a0 + (a1 - a0) * i / segs
            ring.append(bm.verts.new((r * math.sin(a), -r * math.cos(a), y)))
        rings.append(ring)
    uvl = bm.loops.layers.uv.new() if uv else None
    y0, y1 = pts[0][0], pts[-1][0]
    for j in range(len(rings) - 1):
        for i in range(segs):
            i2 = (i + 1) % n if closed else i + 1
            f = bm.faces.new((rings[j][i], rings[j][i2], rings[j + 1][i2], rings[j + 1][i]))
            if uv:
                for loop, (ii, jj) in zip(f.loops, ((i, j), (i2, j), (i2, j + 1), (i, j + 1))):
                    loop[uvl].uv = (ii / segs, (pts[jj][0] - y0) / (y1 - y0))
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    return ob


def radius_at(y):
    for (ya, ra), (yb, rb) in zip(prof, prof[1:]):
        if ya <= y <= yb:
            return ra + (rb - ra) * (y - ya) / max(yb - ya, 1e-6)
    return prof[-1][1]


# Bottle, one object per colour band so cap and body can differ.
for k, (ya, yb, color, rough) in enumerate(spec["parts"]):
    pts = [(y, r) for y, r in prof if ya <= y <= yb]
    pts = [(ya, radius_at(ya))] + [p for p in pts if ya < p[0] < yb] + [(yb, radius_at(yb))]
    ob = lathe(f"part{k}", pts)
    ob.data.materials.append(plastic(f"m{k}", color, rough))
# Base and top caps
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=radius_at(0.0), fill_type="NGON", location=(0, 0, 0))
bpy.context.object.data.materials.append(plastic("base", spec["parts"][-1][2] if False else spec["parts"][0][2], 0.4))
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=prof[-1][1], fill_type="NGON", location=(0, 0, H))
bpy.context.object.data.materials.append(plastic("top", spec["parts"][-1][2], 0.4))

# Label: a sleeve just proud of the body, centred on the front (facing -Y, the camera).
lw, lh = spec["label_size"]; ly = spec["label_y"]
ys = [ly + lh * t / 40 for t in range(41)]
rl = max(radius_at(y) for y in ys) + 0.004
span = lw / rl
lab = lathe("label", [(y, radius_at(y) + 0.004) for y in ys], segs=128, a0=-span / 2, a1=span / 2, closed=False, uv=True)
m = bpy.data.materials.new("label"); m.use_nodes = True
nt = m.node_tree; b = nt.nodes["Principled BSDF"]
tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(spec["label"])
tex.extension = "CLIP"
nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
b.inputs["Roughness"].default_value = 0.32
b.inputs["Coat Weight"].default_value = 0.25
lab.data.materials.append(m)

# Studio: soft key left, fill right, rim behind, white world at low strength.
def area(name, loc, size, energy, rot):
    bpy.ops.object.light_add(type="AREA", location=loc, rotation=rot)
    l = bpy.context.object; l.data.size = size; l.data.energy = energy; l.name = name
area("key", (-H * 1.2, -H * 1.4, H * 0.9), H * 1.2, 900 * H * H / 40, (math.radians(60), 0, math.radians(-40)))
# Tall strip lights either side of the camera: the vertical highlights that read as glossy plastic.
for side, e in ((-1, 420), (1, 260)):
    bpy.ops.object.light_add(type="AREA", location=(side * R * 3.2, -H * 1.6, H * 0.55), rotation=(math.radians(90), 0, math.radians(side * 18)))
    l = bpy.context.object; l.data.shape = "RECTANGLE"; l.data.size = R * 0.5; l.data.size_y = H * 1.3; l.data.energy = e * H * H / 40
area("fill", (H * 1.4, -H * 1.0, H * 0.6), H * 1.4, 350 * H * H / 40, (math.radians(65), 0, math.radians(55)))
area("rim", (0, H * 1.5, H * 1.1), H * 0.8, 500 * H * H / 40, (math.radians(-55), 0, 0))
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

# Camera: long lens, square on, a touch above the label centre; frames the bottle height.
bpy.ops.object.camera_add(location=(0, -H * 6, H * 0.5), rotation=(math.radians(90), 0, 0))
cam = bpy.context.object; sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = H * 1.04
px = spec.get("px", 1800)
sc.render.resolution_y = px
sc.render.resolution_x = int(px * (2 * R * 1.08) / (H * 1.04)) // 2 * 2
cam.data.sensor_fit = "VERTICAL"
sc.render.engine = "CYCLES"; sc.cycles.samples = spec.get("samples", 96); sc.cycles.use_denoising = True
sc.cycles.device = "CPU"
sc.render.film_transparent = True
sc.view_settings.view_transform = "Standard"
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.filepath = spec["out"]
bpy.ops.render.render(write_still=True)
print("wrote", spec["out"])
