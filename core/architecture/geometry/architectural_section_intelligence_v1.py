"""Functional architectural section contract derived from resolved model geometry."""

from __future__ import annotations

from math import hypot


class ArchitecturalSectionIntelligenceV1:
    VERSION="1.0"

    def resolve(self,geometry):
        ramps=[r for r in geometry.get("vertical_geometry",[]) if isinstance(r,dict) and r.get("type")=="vehicle_ramp" and r.get("geometry_status")=="resolved"]
        stairs=[s for s in geometry.get("vertical_geometry",[]) if isinstance(s,dict) and s.get("type")=="stair_geometry" and s.get("geometry_status")=="resolved"]
        clearance=geometry.get("ramp_clearance",{})
        floors=[f for f in geometry.get("floor_geometry",[]) if isinstance(f,dict)]
        levels=[]
        for floor in floors:
            z=floor.get("elevation",floor.get("bottom"))
            if isinstance(z,(int,float)):levels.append({"name":floor.get("floor"),"z":float(z),"source":"floor_geometry"})
        base={"section_id":"FUNCTIONAL_VERTICAL_CIRCULATION_SECTION","section_type":"ramp_stair_functional",
              "section_axis":None,"levels":levels,"ramp_profile":None,"headroom_profile":None,
              "slab_profiles":[],"slab_openings":[],"stair_profile":None,"geometry_status":"pending",
              "unresolved_evidence":[],"source":"resolved_architectural_geometry"}
        if not stairs:base["unresolved_evidence"].append("resolved_stair_geometry")
        if ramps and clearance.get("geometry_status")!="resolved":base["unresolved_evidence"].append("resolved_ramp_clearance")
        if not floors:base["unresolved_evidence"].append("resolved_floor_geometry")
        if base["unresolved_evidence"]:return base
        if ramps:
            ramp=ramps[0];line=ramp.get("centerline_3d",[])
            if len(line)<2:return base|{"unresolved_evidence":["ramp_centerline_3d"]}
            stations=self._stations(line)
            base["section_axis"]=[line[0][:2],line[-1][:2]]
            base["ramp_profile"]=[[stations[i],float(p[2])] for i,p in enumerate(line)]
            top=clearance.get("clearance_envelope",{}).get("top_centerline",[])
            base["headroom_profile"]=[[stations[i],float(p[2])] for i,p in enumerate(top)] if len(top)==len(stations) else None
            section_length=stations[-1]
        else:
            stair=stairs[0];line=stair.get("walking_line",[])
            base["section_axis"]=[line[0][:2],line[-1][:2]] if len(line)>=2 else None
            section_length=max((self._stations(line)[-1] if len(line)>=2 else 1.0),1.0)
        for level in levels:base["slab_profiles"].append({"level":level["name"],"z":level["z"],"line":[[0,level["z"]],[section_length,level["z"]]]})
        base["slab_openings"]=[{"type":o.get("type"),"host_level":o.get("host_level"),"z":o.get("z"),"source":o.get("source_evidence")} for o in geometry.get("slab_openings",[]) if isinstance(o,dict) and o.get("geometry_status")=="resolved"]
        stair=stairs[0];walk=stair.get("walking_line",[])
        if walk:base["stair_profile"]=[[self._stations(walk)[i],float(p[2])] for i,p in enumerate(walk)]
        base["geometry_status"]="resolved";return base

    @staticmethod
    def _stations(line):
        result=[0.0]
        for a,b in zip(line,line[1:]):result.append(result[-1]+hypot(float(b[0])-float(a[0]),float(b[1])-float(a[1])))
        return result
