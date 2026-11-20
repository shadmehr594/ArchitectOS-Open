"""Derive geometry-backed site resources from explicit evidence only."""
from copy import deepcopy
from shapely.geometry import LineString, Polygon, shape, mapping

from .contextual_site_resource_map_v1 import CHANNELS


def _geometry(value, expected=None):
    if hasattr(value,"geom_type"): result=value
    elif isinstance(value,dict) and "type" in value: result=shape(value)
    elif expected=="polygon": result=Polygon(value)
    else: result=LineString(value)
    if result.is_empty or not result.is_valid: raise ValueError("site evidence geometry must be valid and non-empty")
    return result


def _json_safe_source_evidence(value):
    """Preserve evidence structure while replacing live geometry objects with GeoJSON mappings."""
    if hasattr(value,"geom_type"):
        return mapping(value)
    if isinstance(value,dict):
        return {key:_json_safe_source_evidence(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):
        return [_json_safe_source_evidence(item) for item in value]
    return deepcopy(value)


class EvidenceBasedSiteResourceRegionDerivationV1:
    def derive(self, parcel_geometry, edge_evidence, floors, interior_evidence=None):
        parcel=_geometry(parcel_geometry,"polygon"); records=[]; unknown=[]
        for index, evidence in enumerate(edge_evidence):
            edge=_geometry(evidence.get("geometry")); provenance=deepcopy(evidence.get("provenance",[]))
            source=evidence.get("source"); confidence=float(evidence.get("confidence",0.0))
            if edge.distance(parcel.boundary)>1e-7: raise ValueError("edge evidence must lie on parcel boundary")
            channels={}
            explicit=evidence.get("channels",{})
            semantic={}
            if "is_frontage" in evidence: semantic["frontage_value"]=1.0 if evidence["is_frontage"] else 0.0
            if "public_access_eligible" in evidence: semantic["public_access_value"]=1.0 if evidence["public_access_eligible"] else 0.0
            if "openness" in evidence: semantic["daylight_value"]=float(evidence["openness"])
            if "visibility" in evidence: semantic["visibility_value"]=float(evidence["visibility"])
            if "privacy" in evidence: semantic["privacy_value"]=float(evidence["privacy"])
            if "quietness" in evidence: semantic["quietness_value"]=float(evidence["quietness"])
            if "terrace_eligibility" in evidence: semantic["terrace_value"]=float(evidence["terrace_eligibility"])
            if "commercial_eligibility" in evidence: semantic["commercial_value"]=float(evidence["commercial_eligibility"])
            for name in CHANNELS:
                supplied=explicit.get(name,semantic.get(name))
                if supplied is None:
                    channels[name]={"value":None,"status":"unknown","source":None,"provenance":[],"confidence":0.0}; unknown.append({"resource_id":evidence.get("evidence_id","edge-%d"%index),"channel":name})
                else:
                    item=supplied if isinstance(supplied,dict) else {"value":supplied}
                    value=item.get("value"); status=item.get("status","known" if value is not None else "unknown")
                    channels[name]={"value":float(value) if value is not None else None,"status":status,
                        "source":item.get("source",source),"provenance":deepcopy(item.get("provenance",provenance)),
                        "confidence":float(item.get("confidence",confidence)) if status!="unknown" else 0.0}
            usable_fraction=evidence.get("usable_fraction")
            records.append({"resource_id":evidence.get("evidence_id","edge-%d"%index),"geometry":mapping(edge),
                "floor_scope":list(evidence.get("floor_scope",floors)),"gross_capacity":edge.length,
                "usable_capacity":edge.length*float(usable_fraction) if usable_fraction is not None else None,
                "capacity_derivation":"explicit_usable_fraction" if usable_fraction is not None else "unknown",
                "evidence_kind":evidence.get("evidence_kind","edge_evidence"),"channels":channels,
                "source_evidence":_json_safe_source_evidence(evidence)})
        interior=interior_evidence or {}; interior_provenance=deepcopy(interior.get("provenance",[]))
        interior_channels={name:{"value":None,"status":"unknown","source":None,"provenance":[],"confidence":0.0} for name in CHANNELS}
        for name,value in interior.get("channels",{}).items():
            if name not in interior_channels: continue
            item=value if isinstance(value,dict) else {"value":value}
            interior_channels[name]={"value":float(item["value"]) if item.get("value") is not None else None,
                "status":item.get("status","known" if item.get("value") is not None else "unknown"),
                "source":item.get("source",interior.get("source")),"provenance":deepcopy(item.get("provenance",interior_provenance)),
                "confidence":float(item.get("confidence",interior.get("confidence",0.0)))}
        records.append({"resource_id":interior.get("evidence_id","site-interior-domain"),"geometry":mapping(parcel),
            "floor_scope":list(interior.get("floor_scope",floors)),"gross_capacity":parcel.area,
            "usable_capacity":parcel.area if interior.get("usable",True) else None,"capacity_derivation":"parcel_geometry_area",
            "evidence_kind":"interior_spatial_domain","channels":interior_channels,"source_evidence":_json_safe_source_evidence(interior)})
        return {"contract":"EvidenceBasedSiteResourceRegionDerivationV1","parcel_geometry":mapping(parcel),
            "resource_regions":records,"unknown_channels":unknown,"directional_fallback_used":False,
            "fixed_band_used":False,"complete":bool(records),"provenance":[p for e in edge_evidence for p in e.get("provenance",[])]}
