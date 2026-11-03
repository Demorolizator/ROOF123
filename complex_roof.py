"""Preliminary automatic roof geometry for measured complex outlines.

The model is heuristic: it builds roof planes from a closed polygon outline and
one or more interior ridge lines. It is intended as a practical planning aid
for RoofStudio, not as a replacement for a full CAD/BIM roof modeller.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, List, Sequence, Tuple

Point = Tuple[float, float]
Segment = Tuple[Point, Point]

EPS = 1e-9


@dataclass
class Plane:
    index: int
    edge_index: int
    polygon: List[Point]
    base_edge: Segment
    support_segment: Segment
    run: float
    rise: float
    slope_angle: float
    horiz_area: float
    area: float
    kind: str


def polygon_area(points: Sequence[Point]) -> float:
    if len(points) < 3:
        return 0.0
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1] -
                   points[(i + 1) % len(points)][0] * points[i][1]
                   for i in range(len(points))) / 2.0)


def polygon_edges(points: Sequence[Point]) -> List[Segment]:
    return [(tuple(points[i]), tuple(points[(i + 1) % len(points)])) for i in range(len(points))]


def segment_length(seg: Segment) -> float:
    (x1, y1), (x2, y2) = seg
    return math.hypot(x2 - x1, y2 - y1)


def unit_vector(seg: Segment) -> Point:
    (x1, y1), (x2, y2) = seg
    d = math.hypot(x2 - x1, y2 - y1)
    if d < EPS:
        return (1.0, 0.0)
    return ((x2 - x1) / d, (y2 - y1) / d)


def dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def point_in_polygon(point: Point, poly: Sequence[Point]) -> bool:
    if len(poly) < 3:
        return False
    x, y = point
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / ((y2 - y1) or EPS) + x1):
            inside = not inside
    return inside


def orientation(points: Sequence[Point]) -> float:
    return sum(points[i][0] * points[(i + 1) % len(points)][1] -
               points[(i + 1) % len(points)][0] * points[i][1]
               for i in range(len(points)))


def concave_vertices(points: Sequence[Point]) -> List[int]:
    if len(points) < 4:
        return []
    sign = 1 if orientation(points) >= 0 else -1
    out = []
    n = len(points)
    for i in range(n):
        a = points[(i - 1) % n]
        b = points[i]
        c = points[(i + 1) % n]
        cross = ((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
        if cross * sign < -EPS:
            out.append(i)
    return out


def project_point_to_segment(p: Point, seg: Segment) -> Tuple[Point, float, float]:
    (x1, y1), (x2, y2) = seg
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy
    if denom < EPS:
        q = (x1, y1)
        return q, 0.0, math.hypot(p[0] - x1, p[1] - y1)
    t = ((p[0] - x1) * dx + (p[1] - y1) * dy) / denom
    t = max(0.0, min(1.0, t))
    q = (x1 + t * dx, y1 + t * dy)
    return q, t, math.hypot(p[0] - q[0], p[1] - q[1])


def auto_ridge(points: Sequence[Point]) -> List[Segment]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    if width >= height:
        y = (min_y + max_y) / 2.0
        # collect intersections with horizontal scanline
        xs_int = []
        for (x1, y1), (x2, y2) in polygon_edges(points):
            if abs(y2 - y1) < EPS:
                continue
            if (y1 <= y < y2) or (y2 <= y < y1):
                x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                xs_int.append(x)
        xs_int.sort()
        if len(xs_int) >= 2:
            a = xs_int[0] + 0.05 * width
            b = xs_int[-1] - 0.05 * width
            if b > a:
                return [((a, y), (b, y))]
        return [((min_x + 0.25 * width, y), (max_x - 0.25 * width, y))]
    x = (min_x + max_x) / 2.0
    ys_int = []
    for (x1, y1), (x2, y2) in polygon_edges(points):
        if abs(x2 - x1) < EPS:
            continue
        if (x1 <= x < x2) or (x2 <= x < x1):
            y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
            ys_int.append(y)
    ys_int.sort()
    if len(ys_int) >= 2:
        a = ys_int[0] + 0.05 * height
        b = ys_int[-1] - 0.05 * height
        if b > a:
            return [((x, a), (x, b))]
    return [((x, min_y + 0.25 * height), (x, max_y - 0.25 * height))]


def nearest_support(edge: Segment, ridges: Sequence[Segment]) -> Tuple[Segment, Point, Point, Point, float, float]:
    a, b = edge
    m = midpoint(a, b)
    best = None
    for rid in ridges:
        qa, ta, da = project_point_to_segment(a, rid)
        qb, tb, db = project_point_to_segment(b, rid)
        qm, tm, dm = project_point_to_segment(m, rid)
        score = dm + 0.2 * (da + db)
        if best is None or score < best[0]:
            best = (score, rid, qa, qb, qm, da, db, dm, ta, tb)
    _, rid, qa, qb, qm, da, db, dm, ta, tb = best
    return rid, qa, qb, qm, dm, abs(tb - ta) * segment_length(rid)


def clean_polygon(poly: Iterable[Point]) -> List[Point]:
    out: List[Point] = []
    for p in poly:
        if not out or math.hypot(out[-1][0] - p[0], out[-1][1] - p[1]) > 1e-4:
            out.append((round(p[0], 6), round(p[1], 6)))
    if len(out) >= 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-4:
        out.pop()
    return out


def make_candidate_plane(edge: Segment, ridges: Sequence[Segment], outline: Sequence[Point]) -> Tuple[List[Point], float, float, Segment, str]:
    a, b = edge
    rid, qa, qb, qm, run_mid, proj_span = nearest_support(edge, ridges)
    e_dir = unit_vector(edge)
    r_dir = unit_vector(rid)
    parallel = abs(dot(e_dir, r_dir)) > 0.75
    if parallel and proj_span > 0.2:
        poly = clean_polygon([a, b, qb, qa])
        if polygon_area(poly) < EPS:
            poly = clean_polygon([a, b, qm])
            kind = 'tri'
        else:
            kind = 'quad'
    else:
        poly = clean_polygon([a, b, qm])
        kind = 'tri'
    if polygon_area(poly) < EPS:
        poly = clean_polygon([a, b, midpoint(*rid)])
    # if support point clearly falls outside, shrink to midpoint triangle
    c = (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    if not point_in_polygon(c, outline):
        poly = clean_polygon([a, b, qm])
        kind = 'tri'
    run = max(run_mid, 0.1)
    return poly, run, proj_span, rid, kind


def segment_inside_polygon(seg: Segment, outline: Sequence[Point]) -> bool:
    a, b = seg
    return point_in_polygon(midpoint(a, b), outline)


def generate_roof_geometry(outline_points: Sequence[Point], ridge_segments: Sequence[Sequence[Sequence[float]]] | None,
                           eave_height: float, ridge_height: float, default_pitch: float = 28.0):
    outline = [tuple(map(float, p)) for p in outline_points]
    if len(outline) < 3:
        raise ValueError('Контур здания не задан')
    footprint = polygon_area(outline)
    if footprint <= EPS:
        raise ValueError('Нулевая площадь контура')
    ridges = [(tuple(map(float, a)), tuple(map(float, b))) for a, b in (ridge_segments or []) if segment_length((tuple(map(float, a)), tuple(map(float, b)))) > 0.05]
    if not ridges:
        ridges = auto_ridge(outline)
        auto = True
    else:
        auto = False

    rise = max(float(ridge_height) - float(eave_height), 0.01)
    pitch_default = max(float(default_pitch), 1.0)

    candidates = []
    for idx, edge in enumerate(polygon_edges(outline), start=1):
        poly, run, proj_span, support, kind = make_candidate_plane(edge, ridges, outline)
        h_area = polygon_area(poly)
        if h_area <= EPS:
            continue
        angle = math.degrees(math.atan2(rise, run)) if run > 0.05 else pitch_default
        candidates.append({
            'index': idx,
            'edge_index': idx,
            'polygon': poly,
            'base_edge': edge,
            'support': support,
            'run': run,
            'rise': rise,
            'angle': angle,
            'horiz_area': h_area,
            'kind': kind,
        })
    if not candidates:
        raise ValueError('Не удалось построить плоскости кровли')

    sum_h = sum(c['horiz_area'] for c in candidates) or footprint
    planes: List[Plane] = []
    for c in candidates:
        share = footprint * c['horiz_area'] / sum_h
        area = share / max(math.cos(math.radians(c['angle'])), 0.05)
        planes.append(Plane(
            index=len(planes) + 1,
            edge_index=c['edge_index'],
            polygon=list(c['polygon']),
            base_edge=c['base_edge'],
            support_segment=c['support'],
            run=c['run'],
            rise=rise,
            slope_angle=c['angle'],
            horiz_area=share,
            area=area,
            kind='Основной' if c['kind'] == 'quad' else 'Треугольный',
        ))

    valleys: List[Segment] = []
    for idx in concave_vertices(outline):
        p = outline[idx]
        best = None
        for rid in ridges:
            q, _, d = project_point_to_segment(p, rid)
            if best is None or d < best[0]:
                best = (d, q)
        if best:
            seg = (p, best[1])
            if segment_length(seg) > 0.05 and segment_inside_polygon(seg, outline):
                valleys.append(seg)

    return {
        'outline_area': footprint,
        'ridge_segments': ridges,
        'ridge_total': sum(segment_length(s) for s in ridges),
        'valley_segments': valleys,
        'valley_total': sum(segment_length(s) for s in valleys),
        'planes': planes,
        'plane_count': len(planes),
        'roof_area_total': sum(p.area for p in planes),
        'avg_slope': sum(p.slope_angle for p in planes) / len(planes),
        'auto_ridge': auto,
        'rise': rise,
        'eave_height': float(eave_height),
        'ridge_height': float(ridge_height),
    }
