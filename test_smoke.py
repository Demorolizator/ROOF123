import os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from perimeter_editor import validate_polygon, polygon_area
from cad_export import write_outline_dxf
from complex_roof import generate_roof_geometry

assert validate_polygon([[0,0],[20,0],[20,7],[12,7],[12,14],[0,14]]) is None
assert abs(polygon_area([[0,0],[20,0],[20,7],[12,7],[12,14],[0,14]]) - 224) < 1e-8
assert validate_polygon([[0,0],[5,5],[0,5],[5,0]]) is not None

roof = generate_roof_geometry([[0,0],[20,0],[20,7],[12,7],[12,14],[0,14]], [], 0.0, 3.2, 28.0)
assert roof['plane_count'] >= 4
assert roof['roof_area_total'] > 224
assert roof['ridge_total'] > 0

with tempfile.TemporaryDirectory() as t:
    p = os.path.join(t, 'out.dxf')
    write_outline_dxf(p, [[0,0],[20,0],[20,7],[12,7],[12,14],[0,14]], [((3,3),(12,3))], planes=roof['planes'], valleys=roof['valley_segments'])
    s = open(p, encoding='ascii').read()
    assert 'BUILDING_CONTOUR' in s and 'ROOF_RIDGE' in s
    assert s.endswith('EOF\n')
print('PASS - roof geometry and DXF')
