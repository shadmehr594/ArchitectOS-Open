"""Evidence-led, floor-aware site resource contract; no directional defaults."""
from copy import deepcopy
from shapely.geometry import LineString, Polygon, shape, mapping

CHANNELS = ("frontage_value", "public_access_value", "daylight_value", "visibility_value",
            "privacy_value", "quietness_value", "terrace_value", "commercial_value")


def _geometry(value):
    if hasattr(value, "geom_type"):
        return value
    if isinstance(value, dict) and "type" in value:
        return shape(value)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return LineString(value) if len(value) == 2 else Polygon(value)
    raise ValueError("geometry evidence must be a geometry, GeoJSON, or coordinate sequence")


class ContextualSiteResourceMapV1:
    """Normalize explicit edge/region evidence without inventing missing values."""
    def build(self, context):
        if context.get("contract")=="EvidenceBasedSiteResourceRegionDerivationV1":
            context={"floors":sorted({f for r in context.get("resource_regions",[]) for f in r.get("floor_scope",[])}),
                     "resource_regions":context.get("resource_regions",[]),
                     "site_evidence":{"derivation_contract":context["contract"],"provenance":deepcopy(context.get("provenance",[]))}}
        floors = tuple(context.get("floors", ()))
        records = []
        for index, raw in enumerate(context.get("resource_regions", ())):
            geom = _geometry(raw["geometry"])
            floor_scope = tuple(raw.get("floor_scope", floors))
            channels = {}
            supplied = raw.get("channels", {})
            for name in CHANNELS:
                item = supplied.get(name)
                if item is None:
                    channels[name] = {"value": None, "status": "unknown", "source": None,
                                      "provenance": [], "confidence": 0.0}
                else:
                    value = item.get("value")
                    status = item.get("status", "known" if value is not None else "unknown")
                    channels[name] = {"value": float(value) if value is not None else None,
                                      "status": status, "source": item.get("source"),
                                      "provenance": deepcopy(item.get("provenance", [])),
                                      "confidence": float(item.get("confidence", 0.0))}
            usable = raw.get("usable_capacity")
            if usable is None and raw.get("capacity_derivation") == "geometry_measure":
                usable = geom.length if geom.geom_type in ("LineString", "MultiLineString") else geom.area
            records.append({"resource_id": raw.get("resource_id", "resource-%d" % index),
                            "geometry": mapping(geom), "geometry_type": geom.geom_type,
                            "floor_scope": list(floor_scope), "gross_capacity": float(raw.get("gross_capacity", geom.length if "Line" in geom.geom_type else geom.area)),
                            "usable_capacity": float(usable) if usable is not None else None,
                            "capacity_status": "known" if usable is not None else "unknown",
                            "evidence_kind": raw.get("evidence_kind", "unspecified"),
                            "capacity_role":raw.get("capacity_role"),"capacity_unit":raw.get("capacity_unit","m2" if geom.geom_type in ("Polygon","MultiPolygon") else "m"),
                            "capacity_derivation":raw.get("capacity_derivation"),"capacity_provenance":deepcopy(raw.get("capacity_provenance",[])),
                            "capacity_confidence":float(raw.get("capacity_confidence",raw.get("confidence",0.0))),
                            "source_evidence":deepcopy(raw.get("source_evidence",{})),"channels": channels})
        return {"contract": "ContextualSiteResourceMapV1", "channels": list(CHANNELS),
                "resources": records, "context_evidence": deepcopy(context.get("site_evidence", {})),
                "unknown_is_neutral": False, "complete": bool(records)}
