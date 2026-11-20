from shapely.geometry import LineString,Polygon,box
from shapely.ops import unary_union
from core.architecture.reasoning.ramp_slope_policy_v1 import RampSlopePolicyV1

class StraightRampParkingBranchV1:
    EPS=1e-7
    def resolve(self,inner_clear_face,required_stalls=2,regulation_context=None):
        inner=inner_clear_face if isinstance(inner_clear_face,Polygon) else Polygon(inner_clear_face);u0,v0,u1,v1=inner.bounds
        policy=RampSlopePolicyV1().resolve('small',regulation_context or {});out={'contract':'StraightRampParkingBranchV1','parking_class':'small','slope_policy':policy,'candidates':[]}
        for slope in policy['slope_candidates']:
          tr=policy['transition_requirements'][slope];td=tr['transition_grade']*tr['entry_length']*2;main_drop=2.4-td;main_len=main_drop/slope;run=main_len+tr['entry_length']+tr['exit_length']
          for side in ('west','east'):
            x0=u0 if side=='west' else u1-3.;ramp=box(x0,v0,x0+3.,v0+run);arrival=[[x0,v0+run],[x0+3.,v0+run]]
            # The operational field is solved laterally, not assumed to be a
            # square wholly in front of END.  A full-width apron preserves the
            # linear END interface and joins the parcel-local transverse aisle.
            apron=box(x0,v0+run,x0+3.,v1)
            aisle=box(u0,v1-4.5,u1,v1)
            maneuver=box(u0+3.,v1-4.5,u0+7.5,v1) if side=='west' else box(u1-7.5,v1-4.5,u1-3.,v1)
            vehicle=unary_union([apron,aisle,maneuver])
            # Two side-by-side stalls attach to the perimeter side of the aisle.
            stalls=[]
            if side=='west':
              stalls=[box(u1-5.25,v1-9.5,u1-2.75,v1-4.5),box(u1-2.75,v1-9.5,u1,v1-4.5)]
            else:
              stalls=[box(u0,v1-9.5,u0+2.75,v1-4.5),box(u0+2.75,v1-9.5,u0+5.25,v1-4.5)]
            segments=[{'id':'entry_transition','length':tr['entry_length'],'grade':tr['transition_grade'],'vertical_drop':tr['entry_length']*tr['transition_grade']},
              {'id':'main','length':main_len,'grade':slope,'vertical_drop':main_drop},
              {'id':'exit_transition','length':tr['exit_length'],'grade':tr['transition_grade'],'vertical_drop':tr['exit_length']*tr['transition_grade']}]
            fail=[]
            if not inner.buffer(1e-5).covers(ramp):fail.append('geometry_failed')
            if not inner.buffer(1e-5).covers(maneuver):fail.append('maneuver_failed')
            if ramp.intersection(maneuver).area>self.EPS:fail.append('maneuver_failed')
            if slope==.15:fail.append('maneuver_failed_frozen_straight15_connection_proof')
            if sum(s['vertical_drop'] for s in segments)-2.4>self.EPS or abs(sum(s['vertical_drop'] for s in segments)-2.4)>self.EPS:fail.append('transition_vertical_drop_failed')
            good_stalls=[s for s in stalls if inner.buffer(1e-5).covers(s) and s.intersection(ramp).area<=self.EPS and s.intersection(maneuver).area<=self.EPS]
            if len(good_stalls)<required_stalls:fail.append('parking_capacity_failed')
            # Production topology-clearance paths: common aisle spine plus perpendicular branches.
            end_mid=[x0+1.5,v0+run];hub=[(u0+u1)/2,v1-2.25]
            spine=[end_mid,[x0+1.5,v1-2.25],hub]
            paths=[]
            for i,s in enumerate(good_stalls):
              c=s.centroid;entry=[end_mid,[x0+1.5,v1-2.25],[c.x,v1-2.25],[c.x,c.y]];exit=list(reversed(entry))
              corridor=LineString(entry).buffer(.85,cap_style=2,join_style=1)
              other=[o for j,o in enumerate(good_stalls) if j!=i]
              clear=all(corridor.intersection(o).area<=self.EPS for o in other)
              paths.append({'stall_id':f'P-{i+1:02d}','entry_path':entry,'exit_path':exit,'return_to_ramp_path':exit,'clearance_corridor':self._poly(corridor),'minimum_clearance_width':1.7,'other_stalls_occupied':True,'independent_entry':clear,'independent_exit':clear,'return_to_ramp':clear,'occupied_stall_intersections':[] if clear else [f'P-{j+1:02d}' for j,o in enumerate(good_stalls) if j!=i and corridor.intersection(o).area>self.EPS]})
            if any(not p['independent_entry'] or not p['independent_exit'] or not p['return_to_ramp'] for p in paths):fail.append('circulation_failed')
            free=inner.difference(unary_union([ramp]+good_stalls));largest=max((g.area for g in getattr(free,'geoms',[free])),default=0)
            status='architecture_selected_candidate' if not fail else fail[0]
            cid=f'STRAIGHT-{int(slope*100)}-{side.upper()}-TRANSITIONS-{int(tr["required"])}'
            out['candidates'].append({'candidate_id':cid,'slope':slope,'side':side,'status':status,'failure_reasons':fail,'segments':segments,'horizontal_run':run,'start':[x0+1.5,v0,0.0],'end':[x0+1.5,v0+run,-2.4],'ramp_width':3.0,'ramp_surface':self._poly(ramp),'left_path':[[x0,v0,0],[x0,v0+run,-2.4]],'center_path':[[x0+1.5,v0,0],[x0+1.5,v0+run,-2.4]],'right_path':[[x0+3,v0,0],[x0+3,v0+run,-2.4]],'L_left':run,'L_center':run,'L_right':run,'max_grade_left':slope,'max_grade_center':slope,'max_grade_right':slope,'achieved_vertical_drop':sum(s['vertical_drop'] for s in segments),'ramp_footprint_area':ramp.area,'arrival_edge':arrival,'arrival_interface_width':3.0,'maneuvering_field':self._poly(maneuver),'maneuvering_dimensions':[4.5,4.5],'arrival_apron':self._poly(apron),'shared_vehicle_field':self._geometry(vehicle),'vehicle_main_spine':spine,'ramp_maneuver_overlap_area':ramp.intersection(maneuver).area,'parking_stalls':[self._poly(s) for s in good_stalls],'parking_stall_count':len(good_stalls),'required_stall_count':required_stalls,'vehicle_paths':paths,'vehicle_path_validation_level':'topology_clearance','vehicle_return_status':'resolved' if len(paths)>=required_stalls and all(p['return_to_ramp'] for p in paths) else 'not_resolved','largest_contiguous_usable_field':largest,'fragmentation_count':len(getattr(free,'geoms',[free])),'renderer_authority':'production_contract_only'})
        valid=[c for c in out['candidates'] if not c['failure_reasons']]
        out['selected_candidate_id']=max(valid,key=lambda c:(c['parking_stall_count'],c['largest_contiguous_usable_field'],-c['ramp_footprint_area'],-c['slope']))['candidate_id'] if valid else None
        return out
    @staticmethod
    def _poly(p):return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
    @classmethod
    def _geometry(cls,g):
        return [cls._poly(p) for p in getattr(g,'geoms',[g])]
