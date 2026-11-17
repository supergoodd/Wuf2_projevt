#!/usr/bin/env python3
"""Zombie Apocalypse — Hari Pertama. Render 3D BENARAN pakai Blender (Eevee).

Karakter Raka 3D low-poly asli (bukan gambar datar): badan, hoodie, tas, sepatu
dibangun dari mesh 3D dengan volume, shading, dan bayangan sungguhan.
Dunia kota + kamar juga mesh 3D, kamera perspektif dengan keyframe per shot.

Jalankan di VPS (Ubuntu 24.04, di folder repo zombie-apocalypse-3d):
    sudo apt install -y blender
    git pull
    blender -b --python blender_scene.py -- --test     # 12 frame tes (1 per shot)
    blender -b --python blender_scene.py -- --full     # 1800 frame penuh (30fps)

--test  : render 12 frame ke test/shot_01.png .. shot_12.png (cek dulu sebelum full)
--full  : render PNG sequence ke frames/frame_0000.png .. (1800 frame)
          lalu gabung + subtitle + audio (langkah berikut, pakai ffmpeg).
--samples N : jumlah TAA samples Eevee (default 32; 16 atau 8 jauh lebih cepat
          di VPS tanpa GPU — 32 samples ~21 detik/frame, 8 samples ~5 detik/frame).
--frames N  : di mode --full, render hanya N frame pertama (misal 130 = ~4 detik
          video, buat cek gerak dulu sebelum gas 1800 penuh).

Perkiraan render Eevee di VPS (2 vCPU): ~2-5 detik/frame -> 1800 frame = 1-2,5 jam.
Blender 4.0 (Ubuntu 24.04) dan 4.2+ didukung (engine Eevee dipilih otomatis).
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

BASE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
SHOT_DUR = 5.0
FRAMES_PER_SHOT = int(SHOT_DUR * FPS)  # 150

# ---------------------------------------------------------------- helpers
_MATS = {}


def mat(name, rgb, rough=0.8, metallic=0.0):
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    _MATS[name] = m
    return m


def mat_emit(name, rgb, strength=3.0):
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1.0)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    _MATS[name] = m
    return m


def _finish(obj, material, bevel=0.0):
    if material is not None:
        obj.data.materials.append(material)
    if bevel > 0:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def box(name, center, size, material, rot=(0, 0, 0), bevel=0.015):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.rotation_euler = rot
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish(o, material, bevel)


def sphere(name, center, r, material, scale=(1, 1, 1), bevel=0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=center)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish(o, material, bevel)


def cyl_between(name, p1, p2, r, material):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length,
                                        location=(p1 + p2) / 2, vertices=12)
    o = bpy.context.active_object
    o.name = name
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return _finish(o, material)


def plane(name, center, size, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=center)
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0], size[1], 1.0)
    o.rotation_euler = rot
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish(o, material)


def torus(name, center, major, minor, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     location=center)
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler = rot
    return _finish(o, material)


def light_sun(name, energy, color, rot_deg=(50, 0, 30)):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = energy
    data.color = color
    o = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    return o


def light_point(name, loc, energy, color, radius=0.5):
    data = bpy.data.lights.new(name, "POINT")
    data.energy = energy
    data.color = color
    data.shadow_soft_size = radius
    o = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    return o


def set_world(color, strength=1.0):
    sc = bpy.context.scene
    world = sc.world or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*color, 1.0)
    bg.inputs[1].default_value = strength
    return bg


def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def hide_keyframes(objs, f_show0, f_show1):
    """Sembunyikan objek di luar rentang frame [f_show0, f_show1].
    Dipakai untuk karakter/zombie yang hanya muncul di satu shot."""
    for o in objs:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=max(0, f_show0 - 1))
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=f_show0)
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=f_show1)
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=f_show1 + 1)


def show_keyframes(objs, f0, f1):
    """Paksa objek TERLIHAT selama [f0, f1] (untuk set yang dipakai shot ini)."""
    for o in objs:
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=f0)
        o.keyframe_insert("hide_render", frame=f1)


def hide_during(objs, f0, f1):
    """Paksa objek TERSEMBUNYI selama [f0, f1] (untuk set yang tidak dipakai shot ini)."""
    for o in objs:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=f0)
        o.keyframe_insert("hide_render", frame=f1)


# ---------------------------------------------------------------- karakter
SKIN = (0.92, 0.76, 0.62)
HAIR = (0.10, 0.08, 0.07)
HOODIE = (0.32, 0.38, 0.16)      # hijau olive
HOODIE_D = (0.24, 0.29, 0.12)
JEANS = (0.16, 0.20, 0.32)
JEANS_D = (0.11, 0.14, 0.24)
SNEAKER = (0.59, 0.59, 0.58)
SOLE = (0.82, 0.82, 0.81)
BAG = (0.45, 0.40, 0.28)
DARK = (0.05, 0.05, 0.06)
ZSKIN = (0.45, 0.52, 0.40)
ZCLOTH = (0.20, 0.22, 0.20)

POSE_STAND = dict(
    neck=(0, 0, 1.42), sh_l=(-0.20, 0, 1.42), sh_r=(0.20, 0, 1.42),
    el_l=(-0.24, 0, 1.12), el_r=(0.24, 0, 1.12),
    wr_l=(-0.25, 0, 0.84), wr_r=(0.25, 0, 0.84),
    hip=(0, 0, 0.95), hip_l=(-0.10, 0, 0.95), hip_r=(0.10, 0, 0.95),
    knee_l=(-0.10, 0, 0.48), knee_r=(0.10, 0, 0.48),
    ank_l=(-0.10, 0, 0.07), ank_r=(0.10, 0, 0.07),
    head=(0, 0, 1.62))
POSE_CROUCH = dict(
    neck=(0, 0, 0.98), sh_l=(-0.20, 0, 0.98), sh_r=(0.20, 0, 0.98),
    el_l=(-0.24, 0, 0.72), el_r=(0.24, 0, 0.72),
    wr_l=(-0.25, 0, 0.50), wr_r=(0.25, 0, 0.50),
    hip=(0, 0, 0.55), hip_l=(-0.10, 0, 0.55), hip_r=(0.10, 0, 0.55),
    knee_l=(-0.13, -0.20, 0.32), knee_r=(0.13, -0.20, 0.32),
    ank_l=(-0.13, -0.08, 0.06), ank_r=(0.13, -0.08, 0.06),
    head=(0, 0, 1.15))
POSE_WALK = dict(
    neck=(0, 0, 1.42), sh_l=(-0.20, 0, 1.42), sh_r=(0.20, 0, 1.42),
    el_l=(-0.22, 0.10, 1.10), el_r=(0.22, -0.10, 1.10),
    wr_l=(-0.22, 0.18, 0.82), wr_r=(0.22, -0.18, 0.82),
    hip=(0, 0, 0.95), hip_l=(-0.10, 0, 0.95), hip_r=(0.10, 0, 0.95),
    knee_l=(-0.10, -0.18, 0.50), knee_r=(0.10, 0.15, 0.48),
    ank_l=(-0.10, -0.32, 0.06), ank_r=(0.10, 0.28, 0.06),
    head=(0, 0, 1.62))
POSE_LISTEN = dict(POSE_STAND, el_r=(0.24, 0, 1.10), wr_r=(0.22, -0.06, 1.52))
POSE_ZOMBIE = dict(
    neck=(0, 0, 1.38), sh_l=(-0.21, 0, 1.38), sh_r=(0.21, 0, 1.38),
    el_l=(-0.22, -0.25, 1.05), el_r=(0.22, -0.25, 1.05),
    wr_l=(-0.22, -0.48, 0.98), wr_r=(0.22, -0.48, 0.98),
    hip=(0, 0, 0.92), hip_l=(-0.10, 0, 0.92), hip_r=(0.10, 0, 0.92),
    knee_l=(-0.10, -0.05, 0.46), knee_r=(0.10, 0.05, 0.46),
    ank_l=(-0.10, -0.08, 0.07), ank_r=(0.10, 0.06, 0.07),
    head=(0, -0.06, 1.56))


def _off(p, dx, dy, dz=0.0):
    return (p[0] + dx, p[1] + dy, p[2] + dz)


def build_raka(prefix, pose, origin=(0, 0, 0), zombie=False):
    """Raka 3D low-poly. origin = posisi kaki di tanah. Menghadap -Y (ke kamera)."""
    ox, oy, oz = origin
    P = {k: _off(v, ox, oy, oz) for k, v in pose.items()}
    skin, cloth, pants = (ZSKIN, ZCLOTH, ZCLOTH) if zombie else (SKIN, HOODIE, JEANS)
    m_skin, m_cloth, m_pants = mat("skin", skin, 0.7), mat("cloth", cloth, 0.9), mat("pants", pants, 0.9)
    m_shoe, m_sole = mat("shoe", SNEAKER, 0.7), mat("sole", SOLE, 0.6)
    m_hair, m_bag = mat("hair", HAIR, 0.9), mat("bag", BAG, 0.9)
    objs = []
    # torso hoodie (kotak membulat) + hood + saku + tali
    hip, neck = P["hip"], P["neck"]
    torso_h = neck[2] - hip[2] + 0.10
    objs.append(box(prefix + "_torso", (hip[0], hip[1], hip[2] + torso_h / 2 - 0.05),
                    (0.44, 0.26, torso_h), m_cloth, bevel=0.06))
    objs.append(sphere(prefix + "_hood", (hip[0], hip[1] + 0.12, neck[2] + 0.04),
                       0.13, mat("cloth_d", HOODIE_D, 0.9), scale=(1.25, 0.85, 0.95)))
    objs.append(box(prefix + "_pocket", (hip[0], hip[1] - 0.135, hip[2] + torso_h * 0.45),
                    (0.20, 0.03, 0.15), mat("cloth_d", HOODIE_D, 0.9), bevel=0.01))
    # kepala + rambut + mata + mulut
    hc = P["head"]
    objs.append(sphere(prefix + "_head", hc, 0.115, m_skin))
    objs.append(sphere(prefix + "_hair", (hc[0], hc[1] + 0.015, hc[2] + 0.035),
                       0.12, m_hair, scale=(1.0, 0.95, 0.72)))
    for sx in (-1, 1):
        objs.append(sphere(prefix + f"_eye{'+' if sx > 0 else '-'}",
                           (hc[0] + sx * 0.042, hc[1] - 0.098, hc[2] + 0.01),
                           0.016, mat("dark", DARK, 0.4)))
    objs.append(box(prefix + "_mouth", (hc[0], hc[1] - 0.108, hc[2] - 0.045),
                    (0.05, 0.012, 0.008), mat("dark", DARK, 0.4), bevel=0.0))
    # lengan + kaki (silinder antar sendi)
    for s in ("l", "r"):
        objs.append(cyl_between(prefix + f"_arm_{s}", P[f"sh_{s}"], P[f"el_{s}"], 0.05, m_cloth))
        objs.append(cyl_between(prefix + f"_forearm_{s}", P[f"el_{s}"], P[f"wr_{s}"], 0.042, m_skin))
        objs.append(cyl_between(prefix + f"_thigh_{s}", P[f"hip_{s}"], P[f"knee_{s}"], 0.065, m_pants))
        objs.append(cyl_between(prefix + f"_shin_{s}", P[f"knee_{s}"], P[f"ank_{s}"], 0.055, m_pants))
        # sepatu + sol
        ax, ay, az = P[f"ank_{s}"]
        objs.append(box(prefix + f"_shoe_{s}", (ax, ay - 0.03, 0.035),
                        (0.10, 0.26, 0.07), m_shoe, bevel=0.02))
        objs.append(box(prefix + f"_sole_{s}", (ax, ay - 0.03, 0.012),
                        (0.105, 0.27, 0.024), m_sole, bevel=0.005))
    if not zombie:
        # tas kanvas di punggung + tali diagonal dada
        objs.append(box(prefix + "_bag", (hip[0], hip[1] + 0.18, hip[2] + torso_h * 0.55),
                        (0.30, 0.10, 0.38), m_bag, bevel=0.02))
        objs.append(box(prefix + "_strap", (hip[0] - 0.08, hip[1] - 0.145, hip[2] + torso_h * 0.55),
                        (0.045, 0.02, 0.55), m_bag, rot=(0, 0, 1.0), bevel=0.005))
    return objs


# ---------------------------------------------------------------- set kota
def build_city():
    """Jalanan kota + gedung. Jalan memanjang sumbu Y, kamera di -Y melihat +Y."""
    objs = []
    m_road = mat("road", (0.12, 0.12, 0.13), 0.95)
    m_ground = mat("ground", (0.18, 0.17, 0.15), 1.0)
    objs.append(plane("ground", (0, 5, 0), (70, 60), m_ground))
    objs.append(plane("road", (0, 5, 0.01), (8, 60), m_road))
    for y in range(-8, 22, 4):
        objs.append(box(f"line_{y}", (0, y, 0.02), (0.12, 1.6, 0.01),
                        mat("line", (0.55, 0.55, 0.50), 0.9), bevel=0.0))
    # gedung kiri-kanan + jendela menyala
    import random
    rng = random.Random(7)
    m_win = mat_emit("win_warm", (1.0, 0.75, 0.35), 2.0)
    m_win2 = mat_emit("win_cool", (0.7, 0.85, 1.0), 1.2)
    for side in (-1, 1):
        for i, y in enumerate(range(-6, 20, 7)):
            h = rng.choice([4.5, 6.0, 8.0, 10.0])
            col = (rng.uniform(0.38, 0.58), rng.uniform(0.32, 0.48), rng.uniform(0.28, 0.42))
            bx = side * rng.uniform(5.6, 7.0)
            objs.append(box(f"bld_{side}_{i}", (bx, y, h / 2),
                            (rng.uniform(3.5, 5.0), 5.0, h), mat(f"bld{side}{i}", col, 0.95),
                            bevel=0.05))
            for wy in (y - 1.5, y + 1.5):
                for wz in (1.6, 3.0, 4.4):
                    if wz < h - 0.5 and rng.random() < 0.7:
                        objs.append(plane(f"win_{side}_{i}_{wy}_{wz}",
                                          (bx - side * 2.55, wy, wz), (0.9, 1.1),
                                          m_win if rng.random() < 0.6 else m_win2,
                                          rot=(0, math.radians(90 if side > 0 else -90), 0)))
    # gedung ujung jalan (latar, menghadap kamera) supaya jalan tidak berakhir kosong
    for j, ex in enumerate((-3.0, 0.0, 3.0)):
        h = rng.choice([7.0, 9.0, 12.0])
        col = (rng.uniform(0.38, 0.55), rng.uniform(0.32, 0.45), rng.uniform(0.28, 0.40))
        objs.append(box(f"bld_end_{j}", (ex, 17.0, h / 2),
                        (3.2, 4.0, h), mat(f"bldend{j}", col, 0.95), bevel=0.05))
        for wx in (ex - 0.8, ex + 0.8):
            for wz in (1.8, 3.2, 4.6):
                if wz < h - 0.5 and rng.random() < 0.7:
                    objs.append(plane(f"win_end_{j}_{wx}_{wz}",
                                      (wx, 14.95, wz), (0.9, 1.1),
                                      m_win if rng.random() < 0.6 else m_win2,
                                      rot=(math.radians(90), 0, 0)))
    # lampu jalan
    m_pole = mat("pole", (0.15, 0.15, 0.16), 0.6, 0.6)
    for (lx, ly) in ((-4.5, -2), (4.5, 8)):
        objs.append(cyl_between(f"pole_{lx}", (lx, ly, 0), (lx, ly, 3.2), 0.06, m_pole))
        objs.append(cyl_between(f"polearm_{lx}", (lx, ly, 3.2),
                                (lx - (0.8 if lx < 0 else -0.8), ly, 3.2), 0.04, m_pole))
        objs.append(sphere(f"lampbulb_{lx}", (lx - (0.8 if lx < 0 else -0.8), ly, 3.15),
                           0.12, mat_emit("bulb", (1.0, 0.85, 0.55), 4.0)))
    return objs


# ---------------------------------------------------------------- set kamar
ROOM_Y = 40.0  # kamar digeser +40 di Y supaya tidak bentrok dengan kota


def build_room():
    """Kamar: lantai kayu, dinding belakang (y=ROOM_Y+3.5), pintu, jendela dipalang,
    meja + botol + kotak obat, lampu gantung, radio tua, ransel."""
    oy = ROOM_Y
    objs = []
    m_floor = mat("floor", (0.45, 0.33, 0.22), 0.9)
    m_wall = mat("wall", (0.59, 0.46, 0.34), 0.95)
    m_door = mat("door", (0.38, 0.26, 0.16), 0.9)
    objs.append(plane("room_floor", (0, oy, 0), (11, 9), m_floor))
    objs.append(box("room_backwall", (0, oy + 3.5, 1.7), (11, 0.15, 3.4), m_wall, bevel=0.0))
    objs.append(box("room_wall_l", (-5.5, oy, 1.7), (0.15, 9, 3.4), m_wall, bevel=0.0))
    objs.append(box("room_wall_r", (5.5, oy, 1.7), (0.15, 9, 3.4), m_wall, bevel=0.0))
    # pintu kiri + kenop
    objs.append(box("room_door", (-3.5, oy + 3.42, 1.2), (1.1, 0.08, 2.4), m_door, bevel=0.01))
    objs.append(sphere("room_knob", (-3.05, oy + 3.36, 1.05), 0.05,
                       mat("gold", (0.86, 0.74, 0.47), 0.4, 0.8)))
    # jendela dipalang kanan
    objs.append(plane("room_window", (3.5, oy + 3.42, 2.0), (1.8, 1.4),
                      mat("nightglass", (0.11, 0.12, 0.16), 0.4)))
    m_plank = mat("plank", (0.35, 0.27, 0.20), 0.95)
    objs.append(box("plank1", (3.5, oy + 3.36, 2.0), (2.2, 0.06, 0.18), m_plank,
                    rot=(0, 0, 0.6), bevel=0.01))
    objs.append(box("plank2", (3.5, oy + 3.36, 2.0), (2.2, 0.06, 0.18), m_plank,
                    rot=(0, 0, -0.6), bevel=0.01))
    # meja kanan + botol + kotak obat
    m_table = mat("table", (0.35, 0.24, 0.15), 0.9)
    objs.append(box("room_tabletop", (2.2, oy + 2.6, 0.95), (1.6, 0.9, 0.06), m_table, bevel=0.01))
    for dx in (-0.7, 0.7):
        for dy in (-0.35, 0.35):
            objs.append(box(f"tableleg_{dx}_{dy}", (2.2 + dx, oy + 2.6 + dy, 0.46),
                            (0.08, 0.08, 0.92), m_table, bevel=0.0))
    for i, (bx, col) in enumerate([(1.4, (0.35, 0.55, 0.78)), (1.9, (0.78, 0.47, 0.24)),
                                   (2.4, (0.86, 0.86, 0.86))]):
        objs.append(cyl_between(f"bottle_{i}", (bx, oy + 2.6, 0.98), (bx, oy + 2.6, 1.38),
                                0.07, mat(f"bot{i}", col, 0.3)))
    objs.append(box("medbox", (2.9, oy + 2.6, 1.12), (0.5, 0.3, 0.28),
                    mat("medbox", (0.94, 0.94, 0.92), 0.6), bevel=0.01))
    objs.append(box("medcross1", (2.9, oy + 2.44, 1.12), (0.24, 0.02, 0.07),
                    mat("red", (0.78, 0.24, 0.16), 0.6), bevel=0.0))
    objs.append(box("medcross2", (2.9, oy + 2.44, 1.12), (0.07, 0.02, 0.24),
                    mat("red", (0.78, 0.24, 0.16), 0.6), bevel=0.0))
    # lampu gantung + radio di atas meja
    objs.append(sphere("room_lamp", (0, oy, 3.05), 0.12, mat_emit("lampglow", (1.0, 0.78, 0.43), 5.0)))
    objs.append(cyl_between("lampcord", (0, oy, 3.4), (0, oy, 3.15), 0.015,
                            mat("dark", DARK, 0.6)))
    objs += build_radio((1.0, oy + 2.6, 0.98))
    # ransel di lantai kiri
    objs.append(box("room_bag", (-3.2, oy + 1.2, 0.3), (0.6, 0.4, 0.6),
                    mat("bag", BAG, 0.9), bevel=0.03))
    return objs


def build_radio(origin):
    """Radio tua: bodi kayu + speaker + antena + gelombang suara (torus kuning)."""
    ox, oy, oz = origin
    objs = []
    m_wood = mat("radiowood", (0.35, 0.22, 0.12), 0.7)
    objs.append(box("radio_body", (ox, oy, oz + 0.15), (0.55, 0.28, 0.30), m_wood, bevel=0.03))
    objs.append(cyl_between("radio_speaker", (ox - 0.13, oy - 0.145, oz + 0.15),
                            (ox - 0.13, oy - 0.155, oz + 0.15), 0.09,
                            mat("speaker", (0.08, 0.08, 0.09), 0.9)))
    objs.append(box("radio_dial", (ox + 0.12, oy - 0.145, oz + 0.18), (0.16, 0.01, 0.08),
                    mat_emit("dial", (1.0, 0.9, 0.6), 2.0), bevel=0.0))
    objs.append(cyl_between("radio_ant", (ox + 0.2, oy, oz + 0.30),
                            (ox + 0.45, oy, oz + 0.75), 0.008,
                            mat("metal", (0.75, 0.75, 0.78), 0.3, 0.9)))
    m_wave = mat_emit("wave", (1.0, 0.85, 0.4), 2.5)
    for i, r in enumerate((0.22, 0.34, 0.46)):
        objs.append(torus(f"wave_{i}", (ox, oy - 0.20, oz + 0.18), r, 0.012, m_wave,
                          rot=(math.radians(90), 0, 0)))
    return objs


# ---------------------------------------------------------------- mood/lighting
MOODS = {
    "warm": dict(bg=(0.88, 0.64, 0.38), bg_s=1.0, sun_e=3.2, sun_c=(1.0, 0.85, 0.60)),
    "day": dict(bg=(0.72, 0.83, 0.95), bg_s=1.0, sun_e=4.0, sun_c=(1.0, 1.0, 1.0)),
    "dusk": dict(bg=(0.95, 0.55, 0.35), bg_s=1.0, sun_e=3.0, sun_c=(1.0, 0.55, 0.30)),
    "night": dict(bg=(0.05, 0.06, 0.10), bg_s=1.0, sun_e=0.7, sun_c=(0.55, 0.65, 1.0)),
    "room": dict(bg=(0.55, 0.42, 0.30), bg_s=0.9, sun_e=0.5, sun_c=(1.0, 0.85, 0.60)),
    "room_dark": dict(bg=(0.10, 0.09, 0.10), bg_s=0.9, sun_e=0.15, sun_c=(0.7, 0.7, 0.9)),
}


# ---------------------------------------------------------------- shots
# Kamera: (loc, target, lens). Semua koordinat meter, Z ke atas, karakter menghadap -Y.
def orbit_loc(th, radius=2.6, y=1.6):
    return (radius * math.sin(th), -radius * math.cos(th), y)


SHOTS = [
    dict(id=1, mood="warm", set="city", pose="stand", raka=(0, 0, 0),
         cam0=((0.3, -4.6, 1.5), (0, 0, 1.0), 50),
         cam1=((0.2, -3.4, 1.5), (0, 0, 1.0), 50), zombies=[]),
    dict(id=2, mood="day", set="city", pose="stand", raka=(0, 0, 0),
         cam0=((0, -4.0, 1.8), (-1.5, 0, 1.0), 40),
         cam1=((0, -4.0, 1.8), (1.5, 0, 1.0), 40), zombies=[]),
    dict(id=3, mood="warm", set="city", pose="stand", raka=(0, 0, 0),
         cam0=((0, -4.5, 1.6), (0, 2, 1.0), 40),
         cam1=((0, -2.8, 1.6), (0, 2, 1.0), 40),
         zombies=[(-2.8, 6.5), (2.6, 7.0)]),
    dict(id=4, mood="day", set="city", pose="stand", raka=(0, 0, 0),
         cam0=((0, -4.0, 1.6), (0, 0, 1.0), 35),
         cam1=((0, -4.0, 1.6), (0, 0, 1.0), 55),
         zombies=[(-3.2, 6.0), (0.2, 6.5), (3.4, 6.0)]),
    dict(id=5, mood="warm", set="city", pose="stand", raka=(0, 0, 0),
         cam0=(orbit_loc(-0.6), (0, 0, 1.0), 45),
         cam1=(orbit_loc(0.6), (0, 0, 1.0), 45), zombies=[]),
    dict(id=6, mood="room", set="room", pose="crouch", raka=(-0.9, ROOM_Y + 1.5, 0),
         cam0=((0, ROOM_Y - 1.6, 1.5), (-0.5, ROOM_Y + 1.5, 0.8), 40),
         cam1=((0, ROOM_Y - 3.2, 1.7), (-0.5, ROOM_Y + 1.5, 0.8), 40),
         zombies=[], lamp=60),
    dict(id=7, mood="room_dark", set="room", pose="stand", raka=(0, ROOM_Y + 1.5, 0),
         cam0=((0, ROOM_Y - 2.8, 1.2), (0, ROOM_Y + 1.5, 1.0), 40),
         cam1=((0, ROOM_Y - 2.8, 1.9), (0, ROOM_Y + 1.5, 1.0), 40),
         zombies=[], lamp=0),
    dict(id=8, mood="room", set="room", pose="listen", raka=(-0.5, ROOM_Y + 1.5, 0),
         cam0=((0, ROOM_Y - 2.2, 1.5), (1.0, ROOM_Y + 2.6, 1.25), 38),
         cam1=((0.6, ROOM_Y - 1.2, 1.45), (1.0, ROOM_Y + 2.6, 1.25), 45),
         zombies=[], lamp=60),
    dict(id=9, mood="warm", mood_end="night", set="city", pose="stand", raka=(0, 0, 0),
         cam0=((0.3, -4.6, 1.5), (0, 0, 1.0), 50),
         cam1=((0.2, -3.4, 1.5), (0, 0, 1.0), 50), zombies=[]),
    dict(id=10, mood="dusk", set="city", pose="walk", raka=(0, 0, 0),
         cam0=((0, -4.5, 1.6), (0, 2, 1.0), 40),
         cam1=((0, -2.8, 1.6), (0, 2, 1.0), 40), zombies=[]),
    dict(id=11, mood="night", set="city", pose="stand", raka=(0, 0, 0),
         cam0=((0, -3.0, 1.5), (0, 0, 1.0), 40),
         cam1=((0, -4.5, 3.2), (0, 0, 1.0), 40),
         zombies=[(-3.0, 6.0), (0.0, 6.5), (3.2, 6.0)]),
    dict(id=12, mood="night", set="city", pose="stand", raka=(0, 0, 0),
         cam0=((0.3, -4.6, 1.5), (0, 0, 1.0), 50),
         cam1=((0.2, -3.4, 1.5), (0, 0, 1.0), 50), zombies=[]),
]

POSES = {"stand": POSE_STAND, "crouch": POSE_CROUCH, "walk": POSE_WALK,
         "listen": POSE_LISTEN, "zombie": POSE_ZOMBIE}


def setup_render(samples=32):
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = W
    sc.render.resolution_y = H
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.compression = 15
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Filmic"
    ev = sc.eevee
    for attr, val in (("taa_render_samples", samples), ("use_bloom", True),
                      ("bloom_threshold", 0.9), ("bloom_intensity", 0.15),
                      ("use_soft_shadows", True), ("use_ambient_occlusion", True),
                      ("ao_distance", 0.5)):
        if hasattr(ev, attr):
            try:
                setattr(ev, attr, val)
            except Exception:
                pass
    print("render engine:", sc.render.engine)


def key_cam(cam, cam_data, spec, frame):
    loc, target, lens = spec
    cam.location = loc
    look_at(cam, target)
    cam.keyframe_insert("location", frame=frame)
    cam.keyframe_insert("rotation_euler", frame=frame)
    cam_data.lens = lens
    cam_data.keyframe_insert("lens", frame=frame)


def key_mood(bg_node, sun_data, mood_name, frame):
    m = MOODS[mood_name]
    bg_node.inputs[0].default_value = (*m["bg"], 1.0)
    bg_node.inputs[0].keyframe_insert("default_value", frame=frame)
    bg_node.inputs[1].default_value = m["bg_s"]
    bg_node.inputs[1].keyframe_insert("default_value", frame=frame)
    sun_data.energy = m["sun_e"]
    sun_data.keyframe_insert("energy", frame=frame)
    sun_data.color = m["sun_c"]
    sun_data.keyframe_insert("color", frame=frame)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras,
                 bpy.data.lights, bpy.data.worlds):
        pass  # biarkan data orphan, Blender yang bersihkan saat save


def _walk_keys(objs, f0, f1):
    """Shot jalan: geser badan maju + naik-turun kecil supaya pose jalan
    tidak diam di tempat selama shot."""
    fmid = (f0 + f1) // 2
    for o in objs:
        bx, by, bz = o.location.x, o.location.y, o.location.z
        o.location = (bx, by - 0.9, bz)
        o.keyframe_insert("location", frame=f0)
        o.location = (bx, by, bz + 0.05)
        o.keyframe_insert("location", frame=fmid)
        o.location = (bx, by + 0.9, bz)
        o.keyframe_insert("location", frame=f1)


def build_all():
    sc = bpy.context.scene
    bg_node = set_world(MOODS["warm"]["bg"], 1.0)
    sun = light_sun("Sun", 4.0, (1.0, 0.85, 0.60))
    room_lamp = light_point("RoomLamp", (0, ROOM_Y, 2.8), 0.0, (1.0, 0.78, 0.43))
    for (lx, ly) in ((-5.3, -2), (3.7, 8)):
        light_point(f"StreetLamp_{lx}", (lx, ly, 3.1), 15.0, (1.0, 0.85, 0.55))
    city_objs = build_city()
    room_objs = build_room()
    lamp_bulb = bpy.data.objects["room_lamp"]

    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam

    n_shots = len(SHOTS)
    sc.frame_start = 0
    sc.frame_end = n_shots * FRAMES_PER_SHOT - 1
    for i, sh in enumerate(SHOTS):
        f0 = i * FRAMES_PER_SHOT
        f1 = f0 + FRAMES_PER_SHOT - 1
        # set terlihat hanya di shot ini (keyframe eksplisit, bukan set manual —
        # nilai manual kalah dengan F-curve saat frame berubah)
        if sh["set"] == "city":
            hide_during(room_objs, f0, f1)
            show_keyframes(city_objs, f0, f1)
        else:
            hide_during(city_objs, f0, f1)
            show_keyframes(room_objs, f0, f1)
        # karakter + zombie shot ini
        raka_objs = build_raka(f"s{sh['id']:02d}_raka", POSES[sh["pose"]], sh["raka"])
        hide_keyframes(raka_objs, f0, f1)
        if sh["pose"] == "walk":
            try:
                _walk_keys(raka_objs, f0, f1)
            except Exception as e:
                print(f"walk keys gagal shot {sh['id']}: {e}")
        for j, (zx, zy) in enumerate(sh["zombies"]):
            z_objs = build_raka(f"s{sh['id']:02d}_z{j}", POSE_ZOMBIE, (zx, zy, 0), zombie=True)
            hide_keyframes(z_objs, f0, f1)
        # kamera + mood + lampu kamar
        key_cam(cam, cam_data, sh["cam0"], f0)
        key_cam(cam, cam_data, sh["cam1"], f1)
        key_mood(bg_node, sun.data, sh["mood"], f0)
        if sh.get("mood_end"):
            key_mood(bg_node, sun.data, sh["mood_end"], f0 + FRAMES_PER_SHOT // 2)
            key_mood(bg_node, sun.data, sh["mood_end"], f1)
        lamp_e = sh.get("lamp", 0)
        room_lamp.data.energy = lamp_e
        room_lamp.data.keyframe_insert("energy", frame=f0)
        room_lamp.data.keyframe_insert("energy", frame=f1)
        # bohlam lampu: mati di shot 7
        bulb_show = sh["id"] in (6, 8)
        lamp_bulb.hide_render = not bulb_show
        lamp_bulb.keyframe_insert("hide_render", frame=f0)
        lamp_bulb.keyframe_insert("hide_render", frame=f1)
        print(f"shot {sh['id']:02d} frames {f0}-{f1} mood={sh['mood']} pose={sh['pose']}")
    return sc


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mode = "test"
    if "--full" in argv:
        mode = "full"
    samples = 32
    if "--samples" in argv:
        try:
            samples = max(1, int(argv[argv.index("--samples") + 1]))
        except (ValueError, IndexError):
            pass
    frames = None
    if "--frames" in argv:
        try:
            frames = max(1, int(argv[argv.index("--frames") + 1]))
        except (ValueError, IndexError):
            pass
    print("Blender", bpy.app.version_string, "mode:", mode, "samples:", samples,
          "frames:", frames or "semua")
    clear_scene()
    sc = build_all()
    setup_render(samples)
    if mode == "test":
        outdir = os.path.join(BASE, "blender_test")
        os.makedirs(outdir, exist_ok=True)
        for i, sh in enumerate(SHOTS):
            fmid = i * FRAMES_PER_SHOT + FRAMES_PER_SHOT // 2
            sc.frame_set(fmid)
            sc.render.filepath = os.path.join(outdir, f"shot_{sh['id']:02d}.png")
            bpy.ops.render.render(write_still=True)
            print(f"TEST shot {sh['id']:02d} frame {fmid} -> {sc.render.filepath}")
        print("DONE test: 12 frame di blender_test/")
    else:
        outdir = os.path.join(BASE, "blender_frames")
        os.makedirs(outdir, exist_ok=True)
        sc.render.filepath = os.path.join(outdir, "frame_")
        if frames:
            sc.frame_end = min(sc.frame_end, frames - 1)
        bpy.ops.render.render(animation=True)
        print(f"DONE full: {sc.frame_end + 1} frame di blender_frames/")


if __name__ == "__main__":
    main()
