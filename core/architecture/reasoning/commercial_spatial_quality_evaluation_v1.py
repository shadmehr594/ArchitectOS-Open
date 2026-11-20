import math
from shapely.geometry import LineString, Polygon, box


class CommercialSpatialQualityEvaluationV1:
    """Measures commercial shape quality; thresholds are design heuristics, not code limits."""
    EPS=1e-7
    def evaluate(self,candidate,clear_face):
        clear=clear_face if isinstance(clear_face,Polygon) else Polygon(clear_face)
        parts=[Polygon(p) for p in candidate['ground_floor']['commercial_space_polygons']]
        parts=[p for p in parts if p.area>self.EPS];commercial=max(parts,key=lambda p:p.area)
        u0,v0,u1,v1=clear.bounds;core=Polygon(candidate['core_polygon']);cx0,cy0,cx1,cy1=core.bounds
        frontage=LineString([(u0,v0),(u1,v0)]);front_inter=commercial.boundary.intersection(frontage.buffer(1e-6)).length
        effective=min(candidate['ground_floor']['commercial_frontage_width'],front_inter) if front_inter>self.EPS else candidate['ground_floor']['commercial_frontage_width']
        neck_zone=commercial.intersection(box(cx1,cy0,u1,cy1));neck_width=self._minimum_section_width(neck_zone,cy0,cy1)
        neck_length=max(0,cy1-cy0);tail=commercial.intersection(box(u0,cy1,u1,v1));tail_area=tail.area
        narrow_threshold=max(1.5,.45*effective) # Explicit architectural heuristic, never a regulation.
        neck_detected=neck_width<narrow_threshold and tail_area>self.EPS
        rect,rect_area=self._largest_grid_rectangle(commercial,.25)
        total=sum(p.area for p in parts);largest=max(p.area for p in parts);perimeter=sum(p.length for p in parts)
        compact=4*math.pi*total/(perimeter*perimeter) if perimeter else 0
        convex=total/sum(p.convex_hull.area for p in parts) if parts else 0
        strip=neck_zone.area if neck_detected else 0
        failures=[]
        if len(parts)>1:failures.append('commercial_space_fragmented_by_core')
        if neck_detected:failures += ['commercial_rear_tail_created','commercial_narrow_neck_dependency','commercial_core_position_creates_unusable_residual_space']
        if total>80 and (neck_detected or compact<.25):failures.append('commercial_area_high_but_quality_low')
        if effective>0 and (v1-v0)/effective>3.0:failures.append('commercial_storefront_to_depth_quality_poor')
        return {
          'contract':'CommercialSpatialQualityEvaluationV1','candidate_id':candidate['candidate_id'],'geometry_source':'production_commercial_space_polygons','commercial_total_area':total,'largest_contiguous_commercial_area':largest,'commercial_component_count':len(parts),'commercial_frontage_width':candidate['ground_floor']['commercial_frontage_width'],'effective_storefront_width':effective,'maximum_commercial_depth':v1-v0,'average_commercial_depth':total/effective if effective else None,'minimum_local_width':neck_width,'narrow_strip_area':strip,'narrow_strip_length':neck_length if neck_detected else 0,'narrow_strip_ratio':strip/total if total else 0,'core_induced_commercial_fragmentation':len(parts)+(1 if neck_detected else 0),'commercial_space_compactness':compact,'commercial_convexity_ratio':convex,'commercial_perimeter_to_area_ratio':perimeter/total if total else None,'frontage_connected_area':largest,'rear_area_reachable_only_through_narrow_neck':tail_area if neck_detected else 0,'neck_width':neck_width,'neck_length':neck_length if neck_detected else 0,'usable_rectangular_field_area':rect_area,'largest_inscribed_usable_field':self._poly(rect) if rect else None,
          'neck_and_tail':{'contract':'CommercialNeckAndTailDetectionV1','detected':neck_detected,'neck_polygon':self._poly(neck_zone) if not neck_zone.is_empty and neck_zone.geom_type=='Polygon' else None,'neck_width':neck_width,'neck_length':neck_length,'tail_polygon':self._poly(tail) if not tail.is_empty and tail.geom_type=='Polygon' else None,'tail_area':tail_area,'tail_area_ratio':tail_area/total if total else 0,'number_of_direction_changes':2 if neck_detected else 0,'distance_from_storefront_to_tail':cy1-v0,'threshold_basis':'architectural_relative_width_heuristic_not_regulation'},
          'architectural_quality_failures':failures,'architectural_quality_status':'quality_failed' if failures else 'quality_valid'
        }
    @staticmethod
    def _minimum_section_width(g,y0,y1):
        if g.is_empty:return 0.0
        widths=[]
        for i in range(21):
            y=y0+(y1-y0)*(i+.5)/21;cut=g.intersection(LineString([(-1e4,y),(1e4,y)]));widths.append(cut.length)
        return min(widths) if widths else 0.0
    @staticmethod
    def _largest_grid_rectangle(p,step):
        x0,y0,x1,y1=p.bounds;nx=max(1,int((x1-x0)/step));ny=max(1,int((y1-y0)/step));heights=[0]*nx;best=(0,None)
        for j in range(ny):
            y=y0+(j+.5)*step
            for i in range(nx):
                cell=box(x0+i*step,y0+j*step,x0+(i+1)*step,y0+(j+1)*step);heights[i]=heights[i]+1 if p.covers(cell) else 0
            stack=[]
            for i,h in enumerate(heights+[0]):
                start=i
                while stack and stack[-1][1]>h:
                    idx,hh=stack.pop();area=hh*(i-idx)*step*step
                    if area>best[0]:best=(area,box(x0+idx*step,y-step*(hh-.5),x0+i*step,y+step/2))
                    start=idx
                stack.append((start,h))
        return best[1],best[0]
    @staticmethod
    def _poly(p):return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
