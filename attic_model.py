"""Attic and ventilation shaft geometry. Units: metres for coordinates, mm for sizes.

This module deliberately retains measured values separately from rounded
construction annotations. It does not claim a structural or thermal check.
"""
import math
from dataclasses import dataclass, asdict

WALL_PRESETS = {
    'Кирпичный': [('Кирпич 380 мм', 380), ('Кирпич 510 мм', 510), ('Кирпич 640 мм', 640)],
    'Панельный': [('Панель 300 мм', 300), ('Панель 350 мм', 350), ('Панель 400 мм', 400)],
    'Блочный': [('Блок 300 мм', 300), ('Блок 400 мм', 400), ('Блок 500 мм', 500)],
    'Другой': [('Задать вручную', 400)]
}


def ceil5(value_mm):
    """Ceiling to 5 mm, safe around floating representation noise."""
    if not math.isfinite(float(value_mm)):
        raise ValueError('Некорректная длина')
    return 5 * math.ceil((float(value_mm) - 1e-8) / 5)


def polygon_area_signed(points):
    return 0.5 * sum(points[i][0] * points[(i+1) % len(points)][1] - points[(i+1) % len(points)][0] * points[i][1] for i in range(len(points)))


def polygon_area(points):
    return abs(polygon_area_signed(points))


def segment_intersection_line(p, v, q, w):
    d = v[0] * w[1] - v[1] * w[0]
    if abs(d) < 1e-10:
        return None
    a = ((q[0] - p[0]) * w[1] - (q[1] - p[1]) * w[0]) / d
    return (p[0] + a * v[0], p[1] + a * v[1])


def offset_polygon_inward(outline, thickness_m):
    """Miter intersection of inward offset lines, for a simple uniform-wall polygon.

    Rejects self-intersecting/invalid output instead of silently giving an
    incorrect attic area. Intended for rectilinear buildings and modest offsets.
    """
    from perimeter_editor import validate_polygon
    points = [(float(x), float(y)) for x, y in outline]
    if len(points) < 3 or validate_polygon(points):
        raise ValueError('Контур здания не замкнут или содержит пересечения')
    if not 0 < thickness_m < 3:
        raise ValueError('Толщина стен должна быть от 1 до 2999 мм')
    winding = 1 if polygon_area_signed(points) > 0 else -1
    shifted = []
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 0.01:
            raise ValueError('В контуре есть очень короткая стена')
        normal = (-dy / length * winding, dx / length * winding)
        shifted.append(((a[0] + normal[0] * thickness_m, a[1] + normal[1] * thickness_m), (dx, dy)))
    result = []
    for i in range(n):
        prev = shifted[(i - 1) % n]
        curr = shifted[i]
        intersection = segment_intersection_line(prev[0], prev[1], curr[0], curr[1])
        if intersection is None:
            # 180-degree collinearity: use current translated point
            intersection = curr[0]
        result.append((round(intersection[0], 7), round(intersection[1], 7)))
    if validate_polygon(result) or polygon_area(result) >= polygon_area(points):
        raise ValueError('При выбранной толщине стен внутренний контур некорректен. Проверьте выступы и размеры.')
    return result


def distance_point_segment(point, a, b):
    ax, ay = a
    bx, by = b
    px, py = point
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    t = max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/den)) if den else 0
    return math.hypot(px - ax - dx*t, py - ay - dy*t)


def point_in_polygon(point, poly):
    x, y = point
    inside = False
    for i in range(len(poly)):
        a = poly[i]
        b = poly[(i+1) % len(poly)]
        if distance_point_segment(point, a, b) < 1e-8:
            return True
        if (a[1] > y) != (b[1] > y):
            if x < a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                inside = not inside
    return inside


def local_roof_elevation_mm(point, outline, wall_above_slag_mm, ridge_height_mm, pitch_deg):
    """Local level from the same provisional transverse section used for drawing.

    Roof eave elevation is the attic wall top above slag; ridge elevation is
    independent, so an entered pitch mismatch is reported in the section.
    This construction assumes an axial ridge/roof normal to the y direction;
    hips/valleys require a later exact surface intersection model.
    """
    if not point_in_polygon(point, outline):
        raise ValueError('ВШ расположена вне здания')
    section = section_geometry(outline, float(point[0]), wall_above_slag_mm, ridge_height_mm, pitch_deg, 0)
    ymin, ymax = section['ymin'], section['ymax']
    relative = min(float(point[1]) - ymin, ymax - float(point[1])) / max((ymax-ymin)/2, 0.01)
    relative = max(0.0, min(1.0, relative))
    return float(wall_above_slag_mm) + relative*(float(ridge_height_mm)-float(wall_above_slag_mm))


def shaft_rect(instance, shaft_type):
    x = float(instance['x'])
    y = float(instance['y'])
    w = float(shaft_type['width_mm'])/1000
    h = float(shaft_type['length_mm'])/1000
    if int(instance.get('rotation', 0)) % 180 == 90:
        w, h = h, w
    return (x-w/2, y-h/2, x+w/2, y+h/2)


def shaft_corners(instance, shaft_type):
    x0,y0,x1,y1 = shaft_rect(instance,shaft_type)
    return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]


def validate_shaft_placement(instance, shaft_type, outline):
    return all(point_in_polygon(p, outline) for p in shaft_corners(instance, shaft_type))


def shaft_quantities(instance, shaft_type, outline, wall_above_slag_mm, ridge_height_mm, pitch_deg):
    roof_mm = local_roof_elevation_mm((float(instance['x']),float(instance['y'])), outline, wall_above_slag_mm, ridge_height_mm, pitch_deg)
    visible_mm = float(shaft_type['above_roof_mm'])
    if visible_mm <= 0:
        raise ValueError('Возвышение над кровлей должно быть положительным')
    top_raw_mm = roof_mm + visible_mm
    outer_w = float(shaft_type['width_mm'])/1000
    outer_l = float(shaft_type['length_mm'])/1000
    thickness = float(shaft_type.get('wall_mm', 0))/1000
    if not 0 <= thickness < min(outer_w,outer_l)/2:
        raise ValueError('Недопустимая толщина стенки ВШ')
    perim = 2*(outer_w+outer_l)
    skin_area = perim*visible_mm/1000
    insulation_m3 = skin_area * float(shaft_type.get('insulation_mm', 0))/1000
    attic_exposure_area = perim * max(roof_mm, 0)/1000
    attic_insulation_m3 = attic_exposure_area * float(shaft_type.get('insulation_mm', 0))/1000 if shaft_type.get('insulate_attic', True) else 0
    net_section = outer_w*outer_l-(outer_w-2*thickness)*(outer_l-2*thickness) if thickness else 0
    return {
        'roof_elevation_raw_mm': roof_mm,
        'roof_elevation_rounded_mm': ceil5(roof_mm),
        'above_roof_raw_mm': visible_mm,
        'above_roof_rounded_mm': ceil5(visible_mm),
        'top_from_slag_raw_mm': top_raw_mm,
        'top_from_slag_rounded_mm': ceil5(top_raw_mm),
        'cladding_above_roof_m2': skin_area,
        'insulation_above_roof_m3': insulation_m3,
        'shaft_wall_volume_above_roof_m3': net_section*visible_mm/1000,
        'shaft_wall_volume_full_m3': net_section*top_raw_mm/1000,
        'attic_exposure_area_m2': attic_exposure_area,
        'insulation_attic_m3': attic_insulation_m3,
        'insulation_full_m3': attic_insulation_m3 + insulation_m3,
        'roof_opening_m2': outer_w*outer_l,
    }


def section_geometry(outline, cut_x, wall_above_slag_mm, ridge_height_mm, pitch_deg, eave_projection_m):
    """Section through a vertical x=const. line. Returns y-extents in metres."""
    intersections = []
    for i, (x1,y1) in enumerate(outline):
        x2,y2 = outline[(i+1) % len(outline)]
        if abs(x1-x2) < 1e-8:
            if abs(x1-cut_x) < 1e-6:
                intersections.extend([y1,y2])
        elif min(x1,x2) <= cut_x <= max(x1,x2):
            t=(cut_x-x1)/(x2-x1)
            intersections.append(y1+t*(y2-y1))
    intersections = sorted(set(round(v,7) for v in intersections))
    if len(intersections) < 2:
        raise ValueError('Разрез не пересекает контур')
    ymin, ymax = min(intersections), max(intersections)
    wall_mm = float(wall_above_slag_mm)
    ridge_mm = max(float(ridge_height_mm),wall_mm+5)
    slope_angle = math.degrees(math.atan2((ridge_mm-wall_mm)/1000, max((ymax-ymin)/2, .01)))
    target_ridge_mm = wall_mm + (ymax-ymin)/2 * 1000 * math.tan(math.radians(float(pitch_deg)))
    return {'ymin':ymin,'ymax':ymax,'span_m':ymax-ymin,'wall_height_mm':wall_mm,
            'ridge_height_mm':ridge_mm,'rise_mm':ridge_mm-wall_mm,'effective_pitch_deg':slope_angle,
            'requested_pitch_deg':float(pitch_deg),'eave_projection_m':float(eave_projection_m),
            'target_ridge_mm_by_pitch':target_ridge_mm,
            'ridge_pitch_difference_mm':ridge_mm-target_ridge_mm}
