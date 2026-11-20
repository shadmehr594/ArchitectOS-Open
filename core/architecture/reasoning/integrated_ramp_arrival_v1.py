"""Integrated curved-ramp arrival directly into a maneuver/aisle field."""
from math import atan2, pi
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from core.architecture.reasoning.curved_ramp_physical_path_length_contract_v1 import CurvedRampPhysicalPathLengthContractV1
from core.architecture.reasoning.far_end_operational_turn_v2 import RampWidthTransitionV1
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


class IntegratedRampArrivalV1:
    EPS=1e-7

    def resolve(self,inner_clear_face,start_z=0.,end_z=-2.4,maximum_grade=.15):
        inner=inner_clear_face if isinstance(inner_clear_face,Polygon) else Polygon(inner_clear_face)
        u0,v0,u1,v1=inner.bounds;sw,cw=3.,3.5;ctor=RampCenterlineTopologyV2()
        result={'contract':'IntegratedRampArrivalV1','integrated_arrival_topology':True,
            'separate_terminal_leg_required':False,'old_reverse_solve_reused':False,
            'arrival_edge_trials':[],'candidates':[],'hard_valid_candidates':[],
            'physical_ramp_published':False,'human_visual_acceptance':'pending'}
        for fid,field,size in self._fields(inner):
          for edge_name,edge,inward in self._edges(field):
            for sense in (1,-1):
              heading=[inward[0]*sense,inward[1]*sense];faces=sense==1
              result['arrival_edge_trials'].append({'field_id':fid,'edge':edge_name,'approach_sense':'into_field' if faces else 'away_from_field','tested':True})
              if not faces or abs(heading[0])<.5:continue
              for end in self._midpoints(edge,sw):
                for side,start_u,turn in (('west',u0+cw/2,'right'),('east',u1-cw/2,'left')):
                  signed=self._turn([0,1],heading);expected=-1 if turn=='right' else 1
                  if signed*expected<=0:continue
                  theta=abs(signed)
                  for rin in (5.,5.5,6.,6.5):
                    zero=ctor.construct([start_u,v0],[0,1],0,turn,theta,rin,cw,0,start_z,maximum_grade,end_z)
                    tangent0=zero['tangent_out']
                    # With no terminal leg, tangent-out/arrival is authoritative.
                    transverse_error=abs(end[0]-tangent0[0])
                    if transverse_error>self.EPS:
                      result['candidates'].append(self._failure(fid,field,size,edge_name,side,end,rin,theta,transverse_error,'arrival_edge_not_reachable_without_terminal_leg'));continue
                    leg1=end[1]-tangent0[1]
                    if leg1<=self.EPS:
                      result['candidates'].append(self._failure(fid,field,size,edge_name,side,end,rin,theta,transverse_error,'north_leg_cannot_connect_to_frontage'));continue
                    t=ctor.construct([start_u,v0],[0,1],leg1,turn,theta,rin,cw,0,start_z,maximum_grade,end_z)
                    widths=RampWidthTransitionV1().resolve(t,sw,cw,cw);surface=self._surface(t,widths)
                    physical=CurvedRampPhysicalPathLengthContractV1().resolve(t,widths,start_z,end_z,maximum_grade)
                    result['candidates'].append(self._validate(fid,field,size,edge_name,side,heading,t,widths,surface,physical,inner,end_z,sw))
        result['hard_valid_candidates']=[c['candidate_id'] for c in result['candidates'] if c['geometry_status']=='ramp_operational']
        result['status']='integrated_arrival_candidates_for_human_review' if result['hard_valid_candidates'] else 'integrated_arrival_geometric_contradiction'
        result['first_geometric_contradiction']=self._contradiction(result['candidates'],inner)
        return result

    def _validate(self,fid,field,size,edge_name,side,heading,t,widths,surface,physical,inner,end_z,required):
        ramp=Polygon(surface);arrival=self._edge(t['end_point'],heading,required);interface=LineString(arrival).intersection(field.boundary);overlap=ramp.intersection(field).area;fail=[]
        if not inner.buffer(self.EPS).covers(ramp):fail.append('ramp_surface_outside_legal_envelope')
        if physical['geometry_status']!='resolved':fail.extend(physical['failure_reasons'])
        if interface.length<required-self.EPS:fail.append('integrated_arrival_interface_below_3m')
        if overlap>self.EPS:fail.append('maneuver_field_overlaps_sloped_ramp')
        if t['R_inner']<5-self.EPS:fail.append('inner_turn_radius_below_5m')
        if t['z_profile']['geometry_status']!='resolved':fail.extend(t['z_profile']['failure_reasons'])
        movement=list(t['centerline'])+[[field.centroid.x,field.centroid.y]]
        if not field.buffer(self.EPS).covers(LineString(movement[-2:])):fail.append('integrated_vehicle_path_disconnected')
        remaining=inner.difference(ramp.union(field));largest=max((g.area for g in getattr(remaining,'geoms',[remaining])),default=0)
        cid=f"IRA-{fid}-{edge_name}-{side}-R{t['R_inner']:.1f}-A{t['turn_angle_degrees']:.1f}-L1{t['leg_1_length']:.3f}"
        return {'candidate_id':cid,'side':side,'field_id':fid,'field_edge':edge_name,
            'geometry_status':'ramp_operational' if not fail else 'not_feasible','failure_reasons':sorted(set(fail)),
            'integrated_arrival_topology':True,'separate_terminal_leg_required':False,'topology':t,
            'width_transition':widths,'physical_path_length':physical,'ramp_surface':surface,
            'maneuvering_field':self._poly(field),'maneuvering_dimensions':[size,size],
            'arrival_edge':arrival,'arrival_interface_width':interface.length,'ramp_maneuver_overlap_area':overlap,
            'end_left_z':end_z,'end_center_z':end_z,'end_right_z':end_z,
            'vehicle_movement_path':movement,'return_path':list(reversed(movement)),
            'largest_contiguous_remaining_free_field':largest,'remaining_free_area':remaining.area,
            'parking_search_status':'not_run_integrated_arrival_validation'}

    @staticmethod
    def _fields(inner):
        u0,v0,u1,v1=inner.bounds;out=[]
        for size in (5.,4.5):
          # Boundary events include the tangent-out positions induced by each
          # searched R_inner, so a valid integrated contact is not missed by
          # an arbitrary midpoint grid.
          xs={u0,(u0+u1-size)/2,u1-size}
          for rin in (5.,5.5,6.,6.5):
            xs.add(u0+rin+3.5)                 # west ramp -> field west edge
            xs.add(u1-(rin+3.5)-size)          # east ramp -> field east edge
          for ix,x in enumerate(sorted(xs)):
            for iy,y in enumerate(sorted({v0,(v0+v1-size)/2,v1-size})):
              p=box(x,y,x+size,y+size)
              if inner.buffer(1e-7).covers(p):out.append((f'M{size:.1f}-X{ix}-Y{iy}',p,size))
        return out

    @staticmethod
    def _edges(p):
        x0,y0,x1,y1=p.bounds
        return (('west',[[x0,y0],[x0,y1]],[1,0]),('east',[[x1,y1],[x1,y0]],[-1,0]),('south',[[x1,y0],[x0,y0]],[0,1]),('north',[[x0,y1],[x1,y1]],[0,-1]))
    @staticmethod
    def _midpoints(edge,w):
        line=LineString(edge);lo=w/2;hi=line.length-w/2
        return [] if hi<lo else [[line.interpolate(d).x,line.interpolate(d).y] for d in sorted({lo,(lo+hi)/2,hi})]
    @staticmethod
    def _turn(a,b):return atan2(a[0]*b[1]-a[1]*b[0],a[0]*b[0]+a[1]*b[1])
    @staticmethod
    def _edge(c,h,w):
        n=[-h[1],h[0]];return [[c[0]-n[0]*w/2,c[1]-n[1]*w/2],[c[0]+n[0]*w/2,c[1]+n[1]*w/2]]
    @staticmethod
    def _surface(t,w):
        h=t['leg_1_heading'];n=[-h[1],h[0]];a=t['leg_1_start'];b=t['leg_1_end']
        leg=Polygon([[a[0]-n[0]*w['entry_width']/2,a[1]-n[1]*w['entry_width']/2],[a[0]+n[0]*w['entry_width']/2,a[1]+n[1]*w['entry_width']/2],[b[0]+n[0]*w['curve_width']/2,b[1]+n[1]*w['curve_width']/2],[b[0]-n[0]*w['curve_width']/2,b[1]-n[1]*w['curve_width']/2]])
        # Exact annular sector: unlike a sampled-line buffer, its terminal
        # boundary is the authoritative radial arrival cross-section and does
        # not leak a rounded sliver into the downstream floor field.
        center=t['curve_center'];rc=t['R_centerline'];ri=t['R_inner'];ro=t['R_outer']
        inner=[];outer=[]
        for p in t['centerline_arc']:
            dx=p[0]-center[0];dy=p[1]-center[1]
            inner.append([center[0]+dx*ri/rc,center[1]+dy*ri/rc])
            outer.append([center[0]+dx*ro/rc,center[1]+dy*ro/rc])
        curve=Polygon(inner+list(reversed(outer)))
        joined=unary_union([leg,curve]).buffer(1e-8,join_style=2).buffer(-1e-8,join_style=2)
        return IntegratedRampArrivalV1._poly(joined)
    @staticmethod
    def _failure(fid,field,size,edge,side,end,rin,theta,error,reason):
        return {'candidate_id':f'IRA-{fid}-{edge}-{side}-R{rin:.1f}-failed','geometry_status':'not_feasible','failure_reasons':[reason],
            'field_id':fid,'field_edge':edge,'side':side,'maneuvering_field':IntegratedRampArrivalV1._poly(field),'maneuvering_dimensions':[size,size],
            'proposed_arrival_midpoint':end,'R_inner':rin,'R_centerline':rin+1.75,'R_outer':rin+3.5,'turn_angle_degrees':theta*180/pi,
            'arrival_transverse_mismatch':error,'separate_terminal_leg_required':False}
    @staticmethod
    def _contradiction(candidates,inner):
        assembled=[c for c in candidates if 'ramp_surface' in c]
        if assembled:
          b=min(assembled,key=lambda c:len(c['failure_reasons']))
          return {'candidate_id':b['candidate_id'],'failure_reasons':b['failure_reasons'],'available_transverse_clear_width':inner.bounds[2]-inner.bounds[0]}
        b=min(candidates,key=lambda c:c.get('arrival_transverse_mismatch',1e9)) if candidates else None
        return {'candidate_id':b['candidate_id'] if b else None,'failure_reasons':b['failure_reasons'] if b else ['no_integrated_arrival_geometry'],
            'minimum_arrival_transverse_mismatch':b.get('arrival_transverse_mismatch') if b else None,'available_transverse_clear_width':inner.bounds[2]-inner.bounds[0]}
    @staticmethod
    def _poly(p):
        if p.geom_type=='MultiPolygon':p=max(p.geoms,key=lambda g:g.area)
        return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
