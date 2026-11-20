"""Field-first two-curve/S-ramp joint physical-band solver."""
from math import atan2, cos, hypot, pi, sin
from shapely.geometry import LineString, Polygon, box


class TwoCurveRampTopologyV1:
    EPS=1e-7

    def resolve(self,inner_clear_face,start_z=0.,end_z=-2.4,max_grade=.15):
        inner=inner_clear_face if isinstance(inner_clear_face,Polygon) else Polygon(inner_clear_face)
        u0,v0,u1,v1=inner.bounds;result={'contract':'TwoCurveRampTopologyV1',
            'new_search_source':'two_curve_joint_reverse_geometry','single_curve_candidates_reused':False,
            'candidates':[],'hard_valid_candidates':[],'parking_search_status':'not_run',
            'physical_ramp_published':False,'human_visual_acceptance':'pending'}
        # A counter-turn returning to the longitudinal heading arrives through
        # the field edge facing the north frontage. All field placements are
        # established before ramp parameters are solved.
        for fid,field,size in self._fields(inner):
          x0,y0,x1,y1=field.bounds;arrival_y=y0
          for end_x in sorted({x0+1.75,(x0+x1)/2,x1-1.75}):
            for side,start_x,chirality in (('west',u0+1.75,'right_left'),('east',u1-1.75,'left_right')):
              direction=1 if chirality=='right_left' else -1;dx=direction*(end_x-start_x)
              if dx<=self.EPS:continue
              for rin_a in (5.,5.5,6.):
                for rin_b in (5.,5.5,6.):
                  rca=rin_a+1.75;rcb=rin_b+1.75
                  for deg_a in range(15,76,5):
                    # The operational target is +local-longitudinal; Curve B
                    # independently solves the counter-angle (equal only when
                    # that target requires it).
                    deg_b=deg_a;aa=deg_a*pi/180;ab=deg_b*pi/180
                    lateral_arcs=rca*(1-cos(aa))+rcb*(cos(aa-ab)-cos(aa))
                    denom=sin(aa)
                    transition=(dx-lateral_arcs)/denom if denom>self.EPS else -1
                    if transition<-self.EPS:continue
                    transition=max(0.,transition)
                    advance=rca*sin(aa)+transition*cos(aa)+rcb*(sin(aa)-sin(aa-ab))
                    for terminal in (0.,.5,1.):
                      leg1=arrival_y-v0-advance-terminal
                      if leg1<=self.EPS:continue
                      c=self._construct([start_x,v0],leg1,chirality,aa,ab,rin_a,rin_b,transition,terminal,start_z,end_z,max_grade)
                      result['candidates'].append(self._validate(c,field,size,fid,side,inner,max_grade))
        result['hard_valid_candidates']=[c['candidate_id'] for c in result['candidates'] if c['geometry_status']=='ramp_operational']
        result['status']='two_curve_candidates_for_human_review' if result['hard_valid_candidates'] else 'two_curve_topology_no_hard_valid_candidate'
        invalid=[c for c in result['candidates'] if c['geometry_status']!='ramp_operational']
        result['first_exact_geometric_contradiction']=min(invalid,key=lambda c:(len(c['failure_reasons']),abs(c['path_length_margin'])),default=None)
        return result

    def _construct(self,start,leg1,chirality,a,b,rin_a,rin_b,transition,terminal,start_z,end_z,max_grade):
        sign_a=-1 if chirality=='right_left' else 1;sign_b=-sign_a;w=3.5
        pts=[];tans=[];segments=[]
        def add(p,t,label):
            if not pts or hypot(p[0]-pts[-1][0],p[1]-pts[-1][1])>self.EPS:pts.append(p);tans.append(t);segments.append(label)
        h=[0.,1.];p=list(start);add(p,h,'main_leg');p=[p[0],p[1]+leg1];add(p,h,'main_leg');tin_a=list(p)
        arc_a,ha,center_a=self._arc(p,h,sign_a,a,rin_a+w/2)
        for q,t in arc_a[1:]:add(q,t,'curve_A')
        p=arc_a[-1][0];h=ha;tout_a=list(p);trans_start=list(p);p=[p[0]+h[0]*transition,p[1]+h[1]*transition];add(p,h,'transition');trans_end=list(p)
        arc_b,hb,center_b=self._arc(p,h,sign_b,b,rin_b+w/2)
        for q,t in arc_b[1:]:add(q,t,'curve_B')
        p=arc_b[-1][0];h=hb;tout_b=list(p);p=[p[0]+h[0]*terminal,p[1]+h[1]*terminal];add(p,h,'terminal_tangent')
        stations=[0.]
        for i in range(1,len(pts)):stations.append(stations[-1]+hypot(pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1]))
        widths=[3.+.5*min(1,s/max(leg1,self.EPS)) for s in stations]
        left=[];right=[]
        for p,t,wid in zip(pts,tans,widths):n=[-t[1],t[0]];left.append([p[0]+n[0]*wid/2,p[1]+n[1]*wid/2]);right.append([p[0]-n[0]*wid/2,p[1]-n[1]*wid/2])
        surface=Polygon(left+list(reversed(right))).buffer(0);L={'left':self._length(left),'center':stations[-1],'right':self._length(right)}
        drop=start_z-end_z
        # Each real longitudinal path carries the full drop over its own
        # physical length. Cross slope is evidence, not silently constrained;
        # all three paths reunite at one level, untwisted arrival edge.
        def edge_z(path,total):
            out=[start_z];run=0.
            for a,b in zip(path,path[1:]):run+=hypot(b[0]-a[0],b[1]-a[1]);out.append(start_z-drop*run/total)
            return out
        z_left=edge_z(left,L['left']);z=edge_z(pts,L['center']);z_right=edge_z(right,L['right'])
        grades={'left':self._max_grade(z_left,left),'center':self._max_grade(z,pts),'right':self._max_grade(z_right,right)}
        return {'start':start,'start_heading':[0,1],'leg1_length':leg1,'chirality':chirality,
            'curve_A':{'R_inner':rin_a,'R_centerline':rin_a+1.75,'R_outer':rin_a+3.5,'angle_degrees':a*180/pi,
                'inner_arc_length':rin_a*a,'centerline_arc_length':(rin_a+1.75)*a,'outer_arc_length':(rin_a+3.5)*a,
                'center':center_a,'points':[q for q,_ in arc_a],'tangent_in':tin_a,'tangent_out':tout_a},
            'transition_length':transition,'transition_start':trans_start,'transition_end':trans_end,
            'curve_B':{'R_inner':rin_b,'R_centerline':rin_b+1.75,'R_outer':rin_b+3.5,'angle_degrees':b*180/pi,
                'inner_arc_length':rin_b*b,'centerline_arc_length':(rin_b+1.75)*b,'outer_arc_length':(rin_b+3.5)*b,
                'center':center_b,'points':[q for q,_ in arc_b],'tangent_in':trans_end,'tangent_out':tout_b},
            'terminal_tangent_length':terminal,'arrival_midpoint':p,'arrival_heading':h,'centerline':pts,'left_path':left,'right_path':right,
            'surface':self._poly(surface),'stations':stations,'z_profile':z,'left_edge_z':z_left,'right_edge_z':z_right,
            'path_lengths':L,'max_local_grades':grades,'cross_slope_compliance':'pending_requirement',
            'arrival_edge':self._edge(p,h,3.),'arrival_z':[end_z,end_z,end_z],'surface_valid':surface.is_valid}

    def _validate(self,c,field,size,fid,side,inner,max_grade):
        ramp=Polygon(c['surface']);arrival=LineString(c['arrival_edge']);interface=arrival.intersection(field.boundary);overlap=ramp.intersection(field).area
        shortest=min(c['path_lengths'].values());margin=shortest-2.4/max_grade;fail=[]
        if not inner.buffer(self.EPS).covers(ramp):fail.append('two_curve_surface_outside_clear_face')
        if not c['surface_valid']:fail.append('two_curve_surface_self_intersection')
        if shortest<16-self.EPS:fail.append('controlling_physical_path_below_required_run')
        if any(g>max_grade+self.EPS for g in c['max_local_grades'].values()):fail.append('physical_path_local_grade_exceeds_15_percent')
        if interface.length<3-self.EPS:fail.append('arrival_interface_below_3m')
        if overlap>self.EPS:fail.append('maneuver_field_overlaps_sloped_ramp')
        corridor=LineString(c['centerline']+[[field.centroid.x,field.centroid.y]]).buffer(1.5,cap_style=2,join_style=1)
        if not inner.buffer(self.EPS).covers(corridor):fail.append('vehicle_clearance_corridor_outside_drivable_field')
        remaining=inner.difference(ramp.union(field));largest=max((g.area for g in getattr(remaining,'geoms',[remaining])),default=0)
        controlling=min(c['path_lengths'],key=c['path_lengths'].get);cid=f"TC-{fid}-{side}-{c['chirality']}-A{c['curve_A']['angle_degrees']:.0f}-B{c['curve_B']['angle_degrees']:.0f}-T{c['transition_length']:.3f}"
        return {'candidate_id':cid,'geometry_status':'ramp_operational' if not fail else 'not_feasible','failure_reasons':sorted(set(fail)),
            'field_id':fid,'side':side,'topology':c,'maneuvering_field':self._poly(field),'maneuvering_size':[size,size],
            'arrival_interface_width':interface.length,'ramp_maneuver_overlap_area':overlap,'L_left':c['path_lengths']['left'],'L_center':c['path_lengths']['center'],'L_right':c['path_lengths']['right'],
            'controlling_path':controlling,'path_length_margin':margin,'max_local_grades':c['max_local_grades'],
            'remaining_contiguous_floor_area':largest,'vehicle_path':c['centerline']+[[field.centroid.x,field.centroid.y]],
            'clearance_corridor':self._poly(corridor),'return_path':list(reversed(c['centerline']+[[field.centroid.x,field.centroid.y]])),
            'renderer_authority':'production_contract_only','parking_search_status':'not_run'}

    @staticmethod
    def _arc(p,h,sign,angle,r):
        n=[-h[1],h[0]];center=[p[0]+sign*n[0]*r,p[1]+sign*n[1]*r];rv=[p[0]-center[0],p[1]-center[1]];out=[];steps=max(6,int(angle*180/pi/2))
        for i in range(steps+1):
            q=sign*angle*i/steps;c=cos(q);s=sin(q);pt=[center[0]+rv[0]*c-rv[1]*s,center[1]+rv[0]*s+rv[1]*c];tt=[h[0]*c-h[1]*s,h[0]*s+h[1]*c];out.append((pt,tt))
        return out,out[-1][1],center
    @staticmethod
    def _fields(inner):
        u0,v0,u1,v1=inner.bounds;out=[]
        for size in (5.,4.5):
          for ix,x in enumerate(sorted({u0,(u0+u1-size)/2,u1-size})):
            for iy,y in enumerate(sorted({(v0+v1)/2,v1-size})):
              p=box(x,y,x+size,y+size)
              if inner.buffer(1e-5).covers(p):out.append((f'M{size:.1f}-X{ix}-Y{iy}',p,size))
        return out
    @staticmethod
    def _edge(c,h,w):n=[-h[1],h[0]];return [[c[0]-n[0]*w/2,c[1]-n[1]*w/2],[c[0]+n[0]*w/2,c[1]+n[1]*w/2]]
    @staticmethod
    def _length(ps):return sum(hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(ps,ps[1:]))
    @staticmethod
    def _max_grade(z,ps):return max((abs(bz-az)/hypot(b[0]-a[0],b[1]-a[1]) for az,bz,a,b in zip(z,z[1:],ps,ps[1:])),default=0)
    @staticmethod
    def _poly(p):
        if p.geom_type=='MultiPolygon':p=max(p.geoms,key=lambda g:g.area)
        return [[float(x),float(y)] for x,y in list(p.exterior.coords)[:-1]]
