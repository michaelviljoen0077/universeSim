"""Procedural sphere geometry.

Panda3D doesn't ship a guaranteed unit-sphere model, so we build a UV sphere with
correct per-vertex normals and texture coordinates. Normals matter: the PBR pipeline
(simplepbr) needs them to light the surface, and UVs are ready for the photoreal
planet textures coming in Phase 1 (FR-CAM-04).
"""

from __future__ import annotations

import math
import random

from panda3d.core import (
    CardMaker,
    ColorBlendAttrib,
    Geom,
    GeomNode,
    GeomPoints,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    PNMImage,
    Texture,
    TexturePool,
)


def make_uv_sphere(radius: float = 1.0, lat_segments: int = 32,
                   lon_segments: int = 64, name: str = "sphere") -> NodePath:
    """Create a UV sphere NodePath of the given radius."""
    fmt = GeomVertexFormat.get_v3n3t2()  # position, normal, uv
    vdata = GeomVertexData(name, fmt, Geom.UH_static)
    vdata.set_num_rows((lat_segments + 1) * (lon_segments + 1))

    vertex = GeomVertexWriter(vdata, "vertex")
    normal = GeomVertexWriter(vdata, "normal")
    texcoord = GeomVertexWriter(vdata, "texcoord")

    for i in range(lat_segments + 1):
        theta = math.pi * i / lat_segments          # 0 .. pi  (pole to pole)
        sin_t, cos_t = math.sin(theta), math.cos(theta)
        for j in range(lon_segments + 1):
            phi = 2.0 * math.pi * j / lon_segments   # 0 .. 2pi (around)
            nx = sin_t * math.cos(phi)
            ny = sin_t * math.sin(phi)
            nz = cos_t
            vertex.add_data3(nx * radius, ny * radius, nz * radius)
            normal.add_data3(nx, ny, nz)
            texcoord.add_data2(j / lon_segments, 1.0 - i / lat_segments)

    tris = GeomTriangles(Geom.UH_static)
    row = lon_segments + 1
    for i in range(lat_segments):
        for j in range(lon_segments):
            a = i * row + j
            b = a + row
            tris.add_vertices(a, b, a + 1)
            tris.add_vertices(a + 1, b, b + 1)

    geom = Geom(vdata)
    geom.add_primitive(tris)
    node = GeomNode(name)
    node.add_geom(geom)
    return NodePath(node)


def make_starfield(count: int = 2500, radius: float = 4000.0,
                   seed: int = 7, name: str = "starfield") -> NodePath:
    """A sphere of randomly scattered point-stars for the background (FR-CAM-07).

    Placed far beyond the simulated scene (~radius AU) and rendered unlit with depth
    write off, so it reads as an at-infinity sky regardless of camera position.
    """
    rng = random.Random(seed)
    fmt = GeomVertexFormat.get_v3c4()  # position + colour
    vdata = GeomVertexData(name, fmt, Geom.UH_static)
    vdata.set_num_rows(count)
    vertex = GeomVertexWriter(vdata, "vertex")
    color = GeomVertexWriter(vdata, "color")

    points = GeomPoints(Geom.UH_static)
    for i in range(count):
        # Uniformly distributed direction on the unit sphere.
        z = rng.uniform(-1.0, 1.0)
        phi = rng.uniform(0.0, 2.0 * math.pi)
        r_xy = math.sqrt(max(0.0, 1.0 - z * z))
        direction = (r_xy * math.cos(phi), r_xy * math.sin(phi), z)
        vertex.add_data3(direction[0] * radius, direction[1] * radius, direction[2] * radius)
        b = rng.uniform(0.5, 1.0)  # brightness jitter
        color.add_data4(b, b, b * rng.uniform(0.9, 1.0), 1.0)
        points.add_vertex(i)

    geom = Geom(vdata)
    geom.add_primitive(points)
    node = GeomNode(name)
    node.add_geom(geom)
    np_ = NodePath(node)
    np_.set_light_off()
    np_.set_shader_off(1)        # bypass simplepbr; render the points unlit
    np_.set_depth_write(False)
    np_.set_bin("background", 0)
    np_.set_render_mode_thickness(1.5)
    return np_


def make_skybox(texture_path: str, radius: float = 6000.0, name: str = "skybox") -> NodePath:
    """An inside-out textured sphere for an equirectangular sky map (e.g. Milky Way).

    Rendered unlit, two-sided, with depth-write off in the background bin, so it sits
    at infinity behind everything regardless of camera position.
    """
    sphere = make_uv_sphere(radius=radius, lat_segments=32, lon_segments=64, name=name)
    tex = TexturePool.load_texture(texture_path)
    if tex is not None:
        sphere.set_texture(tex, 1)
    sphere.set_two_sided(True)   # we view it from the inside
    sphere.set_light_off()
    sphere.set_shader_off(1)
    sphere.set_depth_write(False)
    sphere.set_bin("background", 0)
    sphere.set_color(1, 1, 1, 1)
    return sphere


def _radial_glow_texture(size: int = 128) -> Texture:
    """A soft radial alpha falloff used for additive glow sprites."""
    img = PNMImage(size, size)
    img.add_alpha()
    c = (size - 1) / 2.0
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - c, y - c) / c
            a = max(0.0, 1.0 - d)
            a = a * a            # quadratic falloff -> soft edge
            img.set_xel(x, y, 1.0, 1.0, 1.0)
            img.set_alpha(x, y, a)
    tex = Texture("glow")
    tex.load(img)
    return tex


def make_glow_sprite(color=(1.0, 0.9, 0.6), size: float = 1.0,
                     name: str = "glow") -> NodePath:
    """An additive, camera-facing glow card — gives stars a radiant halo."""
    cm = CardMaker(name)
    cm.set_frame(-1, 1, -1, 1)
    card = NodePath(cm.generate())
    card.set_texture(_radial_glow_texture(), 1)
    card.set_billboard_point_eye()
    card.set_attrib(ColorBlendAttrib.make(
        ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha, ColorBlendAttrib.O_one))
    card.set_light_off()
    card.set_shader_off(1)
    card.set_depth_write(False)
    card.set_bin("fixed", 0)
    card.set_color_scale(color[0], color[1], color[2], 1.0)
    card.set_scale(size)
    return card
