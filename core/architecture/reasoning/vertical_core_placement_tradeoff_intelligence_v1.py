"""Rigid, vertically aligned core-placement alternatives."""
from copy import deepcopy
from shapely.affinity import translate
from shapely.geometry import Polygon


class VerticalCorePlacementTradeoffIntelligenceV1:
    STRATEGIES=("CURRENT_REFERENCE","NORTH","SOUTH","EAST","WEST","CENTRAL","OFFSET")

    def generate(self, buildable_envelope, reference_core):
        envelope=Polygon(buildable_envelope);ref=Polygon(reference_core["polygon"]);x0,y0,x1,y1=envelope.bounds
        w,d=ref.bounds[2]-ref.bounds[0],ref.bounds[3]-ref.bounds[1];margin=.25
        targets={
            "CURRENT_REFERENCE":(ref.bounds[0],ref.bounds[1]),
            "NORTH":(min(max(ref.bounds[0],x0+margin),x1-w-margin),y1-d-margin),
            "SOUTH":(min(max(ref.bounds[0],x0+margin),x1-w-margin),y0+margin),
            "EAST":(x1-w-margin,(y0+y1-d)/2), "WEST":(x0+margin,(y0+y1-d)/2),
            "CENTRAL":((x0+x1-w)/2,(y0+y1-d)/2),
            "OFFSET":(x0+(x1-x0-w)*.68,y0+(y1-y0-d)*.62),
        }
        out=[]
        for strategy,(tx,ty) in targets.items():
            dx,dy=tx-ref.bounds[0],ty-ref.bounds[1];geometry={}
            for key,value in reference_core.items():
                if key in ("polygon","stair","elevator","lobby") and isinstance(value,list):geometry[key]=self._poly(translate(Polygon(value),dx,dy))
                else:geometry[key]=deepcopy(value)
            shape=Polygon(geometry["polygon"]);valid=envelope.buffer(1e-6).covers(shape)
            geometry["location"]=strategy.lower()
            out.append({"strategy":strategy,"translation_vector":[dx,dy],"core":geometry,"core_area":shape.area,
                        "ground_floor_core_polygon":geometry["polygon"],"residential_core_polygon":deepcopy(geometry["polygon"]),
                        "vertical_alignment_status":"exact_xy_alignment" if valid else "failed",
                        "hard_validation_status":"hard_valid" if valid else "not_feasible",
                        "hard_rejection_reasons":[] if valid else ["core_outside_buildable_envelope"]})
        return {"contract":"VerticalCorePlacementTradeoffIntelligenceV1","strategies_explored":list(self.STRATEGIES),"candidates":out}

    def search_north_wall_offsets(self, buildable_envelope, reference_core, requested_offset=8.0, offsets=None):
        """Rigidly test the core around a requested clear offset from the north wall."""
        envelope=Polygon(buildable_envelope);ref=Polygon(reference_core["polygon"]);x0,y0,x1,y1=envelope.bounds
        offsets=list(offsets or [requested_offset-1.0,requested_offset-.5,requested_offset,requested_offset+.5,requested_offset+1.0])
        out=[]
        for offset in offsets:
            target_top=y1-float(offset);dx=0.0;dy=target_top-ref.bounds[3];geometry={}
            for key,value in reference_core.items():
                if key in ("polygon","stair","elevator","lobby") and isinstance(value,list):geometry[key]=self._poly(translate(Polygon(value),dx,dy))
                else:geometry[key]=deepcopy(value)
            shape=Polygon(geometry["polygon"]);valid=envelope.buffer(1e-6).covers(shape)
            geometry["location"]="north_wall_offset_search"
            out.append({"strategy":"NORTH_WALL_OFFSET_SEARCH","requested_north_wall_offset":requested_offset,
                        "actual_north_wall_offset":y1-shape.bounds[3],"translation_vector":[dx,dy],"core":geometry,
                        "core_area":shape.area,"containment_status":"contained" if valid else "outside",
                        "hard_validation_status":"hard_valid" if valid else "not_feasible",
                        "hard_rejection_reasons":[] if valid else ["core_outside_buildable_envelope"]})
        return {"contract":"VerticalCoreNorthWallOffsetSearchV1","requested_offset":requested_offset,
                "tested_offsets":offsets,"candidates":out}

    @staticmethod
    def _poly(shape):return [[float(x),float(y)] for x,y in list(shape.exterior.coords)[:-1]]
