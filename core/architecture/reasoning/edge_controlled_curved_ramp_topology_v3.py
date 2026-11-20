"""Independent edge-controlled curved-ramp XY generator.

This constructor never accepts or revalidates FarEndOperationalTurnV2
candidates.  It generates north starts, far-region tangent events, aligned
maneuver fields and terminal legs directly from the current clear envelope.
"""
from math import cos, pi, sin
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.curved_ramp_physical_path_length_contract_v1 import CurvedRampPhysicalPathLengthContractV1
from core.architecture.reasoning.far_end_operational_turn_v2 import RampOperationalEndV1, RampWidthTransitionV1
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2


class EdgeControlledCurvedRampTopologyV3:
    EPS=1e-7

    def resolve(self,parcel,frontage,wall_contract,requirements,request):
        result={'contract':'EdgeControlledCurvedRampTopologyV3','new_search_source':'edge_controlled_bidirectional_geometry',
            'old_search_source':'FarEndOperationalTurnV2_198_candidates','old_candidates_reused':False,'candidates':[],
            'length_valid_candidates':[],'operational_candidates':[],'physical_ramp_published':False,'human_visual_acceptance':'pending'}
        if request.get('status')!='required':return result
        binding=request.get('authoritative_ramp_endpoint_binding')
        if not isinstance(binding,dict) or binding.get('contract')!='AuthoritativeRampEndpointBindingContractV1' or binding.get('status')!='resolved' or binding.get('binding_resolved') is not True:
            result.update({'status':'pending_requirement','failure_reasons':['authoritative_ramp_endpoint_binding_missing_or_unresolved']})
            return result
        base=BasementRampParkingDesignReasonerV2();frame=base._frame(parcel,frontage)
        outer=base._to_local_polygon(wall_contract['outer_face'],frame);inner=base._to_local_polygon(wall_contract['inner_face'],frame)
        u0,v0,u1,v1=inner.bounds;entry=3.;curve_width=3.5;terminal=3.;rin=max(5.,float(requirements['ramp']['minimum_inner_turn_radius']))
        slope=float(request['slope']);start_z=float(binding['expected_start_z']);end_z=float(binding['expected_end_z'])
        result['authoritative_ramp_endpoint_binding']=binding
        ctor=RampCenterlineTopologyV2();theta=pi/2;rcenter=rin+curve_width/2;rout=rin+curve_width
        # Side-corridor start events derive from outer-radius containment.
        systems=[('west',u0+curve_width/2,'right',[1,0]),('east',u1-curve_width/2,'left',[-1,0])]
        latest_leg1=max(0.,v1-v0-rout)
        leg1_events=self._events(max(0.,latest_leg1-rin),latest_leg1)
        # Phase A: edge-length-controlled XY generation, not centerline targeting.
        for side,start_u,turn,h2 in systems:
            for leg1 in leg1_events:
                probe=ctor.construct([start_u,v0],[0,1],leg1,turn,theta,rin,curve_width,0,start_z,slope,end_z)
                tangent_out=probe['tangent_out'];limit=(u1-terminal/2-tangent_out[0]) if h2[0]>0 else (tangent_out[0]-(u0+terminal/2))
                for leg2 in self._events(0,max(0.,limit)):
                    self._append(result,ctor,outer,inner,[start_u,v0],leg1,turn,theta,rin,curve_width,leg2,
                        entry,terminal,start_z,end_z,slope,None,side,'length_generation')
        # Phase B: axis-aligned far maneuver fields generate a full END
        # cross-section first; tangent geometry is solved backward.  The END
        # may retain a meaningful diagonal arrival heading, but the field is
        # never rotated to accommodate it.
        for size in (5.,4.5):
            xevents=self._events(u0,u1-size);yevents=self._events(max(v0,(v0+v1)/2),v1-size)
            for fx in xevents:
              for fy in yevents:
                field=box(fx,fy,fx+size,fy+size)
                if not inner.buffer(self.EPS).covers(field):continue
                for degrees in (45,50,55,60,65,70,75,80,85,90):
                  candidate_theta=degrees*pi/180
                  for side,start_u,turn,_ in systems:
                    sign=1 if turn=='left' else -1
                    h2=[-sign*sin(candidate_theta),cos(candidate_theta)]
                    for ex in self._events(fx+terminal/2,fx+size-terminal/2):
                      for ey in self._events(fy+terminal/2,fy+size-terminal/2):
                        end=[ex,ey];end_edge=self._edge(end,h2,terminal)
                        if not field.buffer(self.EPS).covers(LineString(end_edge)):continue
                        zero=ctor.construct([start_u,v0],[0,1],0,turn,candidate_theta,rin,curve_width,0,start_z,slope,end_z)
                        tout=zero['tangent_out']
                        if abs(h2[0])<=self.EPS:continue
                        leg2=(end[0]-tout[0])/h2[0]
                        leg1=end[1]-tout[1]-h2[1]*leg2
                        if leg1<-self.EPS or leg2<-self.EPS:continue
                        self._append(result,ctor,outer,inner,[start_u,v0],leg1,turn,candidate_theta,rin,curve_width,leg2,
                            entry,terminal,start_z,end_z,slope,field,side,'operational_bidirectional')
        result['length_valid_candidates']=[c['candidate_id'] for c in result['candidates'] if c['physical_path_length']['geometry_status']=='resolved' and c['surface_contained']]
        result['operational_candidates']=[c['candidate_id'] for c in result['candidates'] if c['geometry_status']=='hard_valid']
        result['status']='candidates_for_human_review' if result['operational_candidates'] else 'unresolved_no_feasible_edge_controlled_topology'
        result['geometric_maximum']=self._maximum(result['candidates'],latest_leg1,rin*theta)
        return result

    def _append(self,result,ctor,outer,inner,start,leg1,turn,theta,rin,width,leg2,entry,terminal,start_z,end_z,slope,field,side,phase):
        topology=ctor.construct(start,[0,1],leg1,turn,theta,rin,width,leg2,start_z,slope,end_z)
        widths=RampWidthTransitionV1().resolve(topology,entry,width,terminal)
        physical=CurvedRampPhysicalPathLengthContractV1().resolve(topology,widths,start_z,end_z,slope)
        surface=self._surface(topology,widths);poly=Polygon(surface);contained=outer.buffer(1e-6).covers(poly)
        end_contract=None;failures=[]
        if physical['geometry_status']!='resolved':failures.extend(physical['failure_reasons'])
        if not contained:failures.append('ramp_surface_outside_legal_envelope')
        if field is not None:
            end_contract=self._embedded_end(topology['end_edge'],field,terminal,end_z,topology['end_heading'],result['authoritative_ramp_endpoint_binding']['expected_end_z'])
            if end_contract['geometry_status']!='resolved':failures.extend(end_contract['failure_reasons'])
        else:failures.append('operational_maneuvering_field_not_bound')
        cid=f"ECV3-{phase}-{side}-A{topology['turn_angle_degrees']:.1f}-L1-{leg1:.3f}-L2-{leg2:.3f}"
        result['candidates'].append({'candidate_id':cid,'search_phase':phase,'side':side,'geometry_status':'hard_valid' if not failures else 'not_feasible',
            'failure_reasons':sorted(set(failures)),'topology':topology,'width_transition':widths,'physical_path_length':physical,
            'surface':surface,'surface_contained':contained,'maneuvering_field':list(field.exterior.coords)[:-1] if field is not None else [],
            'maneuvering_dimensions':[field.bounds[2]-field.bounds[0],field.bounds[3]-field.bounds[1]] if field is not None else None,
            'operational_end':end_contract,'parking_search_status':'not_run_upstream_ramp_invalid' if failures else 'not_run_by_scope'})

    @staticmethod
    def _surface(t,w):
        h1=t['leg_1_heading'];n1=[-h1[1],h1[0]];a=t['leg_1_start'];b=t['leg_1_end']
        leg1=Polygon([[a[0]-n1[0]*w['entry_width']/2,a[1]-n1[1]*w['entry_width']/2],[a[0]+n1[0]*w['entry_width']/2,a[1]+n1[1]*w['entry_width']/2],[b[0]+n1[0]*w['curve_width']/2,b[1]+n1[1]*w['curve_width']/2],[b[0]-n1[0]*w['curve_width']/2,b[1]-n1[1]*w['curve_width']/2]])
        curve=LineString(t['centerline_arc']).buffer(w['curve_width']/2,cap_style=2,join_style=1)
        pieces=[leg1,curve]
        if t['leg_2_length']>1e-7:
            h=t['leg_2_heading'];n=[-h[1],h[0]];c=t['leg_2_start'];d=t['leg_2_end'];pieces.append(Polygon([[c[0]-n[0]*w['curve_width']/2,c[1]-n[1]*w['curve_width']/2],[c[0]+n[0]*w['curve_width']/2,c[1]+n[1]*w['curve_width']/2],[d[0]+n[0]*w['terminal_leg_width']['end']/2,d[1]+n[1]*w['terminal_leg_width']['end']/2],[d[0]-n[0]*w['terminal_leg_width']['end']/2,d[1]-n[1]*w['terminal_leg_width']['end']/2]]))
        union=unary_union(pieces).buffer(0);return [[float(x),float(y)] for x,y in list(union.exterior.coords)[:-1]]

    @staticmethod
    def _events(low,high):
        if high<low:return []
        span=high-low;return sorted({low,low+span*.25,low+span*.5,low+span*.75,high})

    @staticmethod
    def _edge(center,heading,width):
        n=[-heading[1],heading[0]]
        return [[center[0]-n[0]*width/2,center[1]-n[1]*width/2],[center[0]+n[0]*width/2,center[1]+n[1]*width/2]]

    def _embedded_end(self,end_edge,field,required_width,end_z,heading,expected_end_z):
        edge=LineString(end_edge);interface=edge.intersection(field);width=interface.length
        mid=edge.interpolate(.5,normalized=True);probe=LineString([[mid.x,mid.y],[mid.x+heading[0]*.1,mid.y+heading[1]*.1]])
        downstream=field.buffer(self.EPS).covers(probe);endpoint_bound=abs(end_z-float(expected_end_z))<=self.EPS
        valid=width>=required_width-self.EPS and downstream and endpoint_bound
        reasons=[]
        if width<required_width-self.EPS:reasons.append('no_valid_end_interface')
        if not downstream:reasons.append('end_facing_away_from_drivable_space')
        if not endpoint_bound:reasons.append('end_elevation_not_at_authoritative_endpoint')
        return {'contract':'RampOperationalEndV1','interface_semantics':'full_cross_section_embedded_in_floor_field',
            'geometry_status':'resolved' if valid else 'not_feasible','failure_reasons':reasons,'end_edge':end_edge,
            'end_elevation':end_z,'interface_segment':end_edge if valid else [],'interface_length':width,
            'required_connection_width':required_width,'downstream_free_space':downstream,'faces_wall':not downstream}

    @staticmethod
    def _maximum(candidates,max_leg1,inner_arc):
        if not candidates:return {'maximum_leg1':max_leg1,'inner_arc_length':inner_arc,'maximum_terminal_leg':0,'maximum_shortest_physical_path':0,'limiting_constraint':'no_tangent_solution'}
        best=max(candidates,key=lambda c:c['physical_path_length']['shortest_physical_path']);q=best['physical_path_length'];t=best['topology']
        return {'candidate_id':best['candidate_id'],'maximum_leg1':t['leg_1_length'],'inner_arc_length':t['R_inner']*abs(t['turn_angle']),
            'maximum_terminal_leg':t['leg_2_length'],'maximum_shortest_physical_path':q['shortest_physical_path'],
            'required_shortest_path':q['required_minimum_path'],'limiting_constraint':'transverse_clear_boundary_or_aligned_maneuver_field_requires_terminal_extension_beyond_envelope'}
