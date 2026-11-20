import ezdxf

from core.architecture.geometry.architectural_cad_drawing_resolver_v1 import ArchitecturalCadDrawingResolverV1
from core.export.dwg.dwg_writer import DWGWriter


def _geometry():
    geometry={"floor_geometry":[
        {"floor":"basement","bottom":-2.4,"footprint":{"points":[[0,0],[20,0],[20,15],[0,15]]}},
        {"floor":"F1","bottom":0.0,"footprint":{"points":[[0,0],[12,0],[12,9],[0,9]]}}],
        "physical_walls":[],"spaces":[],"openings":[],"vertical_geometry":[],"site_geometry":{}}
    geometry["cad_drawing_contract"]=ArchitecturalCadDrawingResolverV1().resolve(geometry)
    return geometry


def test_resolver_derives_overall_dimensions_and_non_overlapping_level_markers():
    contract=_geometry()["cad_drawing_contract"]
    assert any(d["role"]=="overall_width" and d["value"]==20 for d in contract["dimensions"])
    points=[tuple(m["label_point"]) for m in contract["level_markers"]]
    assert len(points)==2 and len(set(points))==2


def test_dxf_contains_geometry_derived_dimension_and_level_layers(tmp_path):
    path=tmp_path/"drawing_intelligence.dxf"
    DWGWriter().export(_geometry(),{},output=str(path))
    msp=ezdxf.readfile(path).modelspace()
    assert len(msp.query('*[layer=="ARCH_DIMENSIONS"]'))>0
    assert len(msp.query('DIMENSION[layer=="ARCH_DIMENSIONS"]'))>0
    assert len(msp.query('*[layer=="ARCH_LEVELS"]'))>=4
