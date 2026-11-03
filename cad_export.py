"""ASCII DXF R12 export for RoofStudio."""
from pathlib import Path
import math


def write_outline_dxf(filename, points, ridges=(), objects=(), valleys=(), planes=()):
    def pair(code, v):
        return f'{code}\n{v}\n'
    out = []
    def add(*kv):
        for code, value in kv:
            out.append(pair(code, value))
    add((0, 'SECTION'), (2, 'HEADER'), (9, '$ACADVER'), (1, 'AC1009'), (0, 'ENDSEC'),
        (0, 'SECTION'), (2, 'TABLES'), (0, 'ENDSEC'), (0, 'SECTION'), (2, 'ENTITIES'))
    def line(a, b, layer):
        add((0, 'LINE'), (8, layer), (10, format(a[0] * 1000, '.3f')),
            (20, format(a[1] * 1000, '.3f')), (30, 0),
            (11, format(b[0] * 1000, '.3f')), (21, format(b[1] * 1000, '.3f')), (31, 0))
    def label(p, s, layer='ROOF_DIM_TEXT', h=180):
        safe = ''.join(ch if ord(ch) < 128 else '?' for ch in str(s))
        add((0, 'TEXT'), (8, layer), (10, format(p[0] * 1000, '.3f')),
            (20, format(p[1] * 1000, '.3f')), (30, 0), (40, h), (1, safe))
    for plane in planes:
        poly = plane.polygon
        for i, p in enumerate(poly):
            q = poly[(i + 1) % len(poly)]
            line(p, q, f'ROOF_PLANE_{plane.index}')
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        label((cx, cy), f'P{plane.index} {plane.area:.1f}m2', f'ROOF_PLANE_TEXT_{plane.index}', 160)
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        line(p, q, 'BUILDING_CONTOUR')
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        label((mx, my), f'{math.hypot(q[0] - p[0], q[1] - p[1]):.2f} m')
        label((p[0] + 0.15, p[1] + 0.15), f'P{i + 1}', 'ROOF_POINTS', 130)
    for i, (a, b) in enumerate(ridges):
        line(a, b, 'ROOF_RIDGE')
        label(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), f'R{i + 1}', 'ROOF_RIDGE_TEXT')
    for i, (a, b) in enumerate(valleys):
        line(a, b, 'ROOF_VALLEY')
        label(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), f'V{i + 1}', 'ROOF_VALLEY_TEXT')
    for i, obj in enumerate(objects):
        p = (float(obj['x']), float(obj['y']))
        d = 0.18
        for a, b in [((p[0] - d, p[1] - d), (p[0] + d, p[1] - d)), ((p[0] + d, p[1] - d), (p[0] + d, p[1] + d)),
                    ((p[0] + d, p[1] + d), (p[0] - d, p[1] + d)), ((p[0] - d, p[1] + d), (p[0] - d, p[1] - d))]:
            line(a, b, 'ROOF_OBJECTS')
        label((p[0] + 0.25, p[1]), f'O{i + 1}', 'ROOF_OBJECT_LABELS')
    left = min(p[0] for p in points)
    bottom = min(p[1] for p in points)
    label((left, bottom - 1.2), 'ROOFSTUDIO 0.7 - PRELIMINARY ROOF GEOMETRY', h=240)
    add((0, 'ENDSEC'), (0, 'EOF'))
    Path(filename).write_text(''.join(out), encoding='ascii', newline='\n')


def write_gable_dxf(filename, L, W):
    """Редактируемая двускатная схема: контур и продольный конёк в мм."""
    write_outline_dxf(filename, [[0, 0], [L, 0], [L, W], [0, W]], [[[0, W / 2], [L, W / 2]]])
