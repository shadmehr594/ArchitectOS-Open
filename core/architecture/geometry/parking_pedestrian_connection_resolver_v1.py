"""Fail-closed pedestrian connection from resolved parking to a resolved building interface."""
from __future__ import annotations
from math import hypot

class ParkingPedestrianConnectionResolverV1:
    EPS=1e-7
    def resolve(self,arrival,layout,requirement,walls=None,openings=None,vertical=None,vehicle_zones=None,protected_zones=None):
        level=arrival.get('served_level') if isinstance(arrival,dict) else None
        base={'connection_id':requirement.get('connection_id') if isinstance(requirement,dict) else None,'served_level':level,
              'parking_arrival_reference':None,'parking_aisle_reference':None,'pedestrian_origin':None,'pedestrian_destination':None,
              'target_circulation_space_id':None,'target_stair_core_id':None,'path_centerline':None,'path_corridor':None,
              'required_clear_width':None,'vehicle_conflict_status':'pending','stall_conflict_status':'pending',
              'ramp_conflict_status':'pending','wall_conflict_status':'pending','protected_zone_status':'pending',
              'crossing_policy':None,'geometry_status':'pending','source':'parking_pedestrian_connection_resolver_v1',
              'evidence_status':None,'unresolved_evidence':[]}
        if not isinstance(arrival,dict) or arrival.get('geometry_status')!='resolved':base['unresolved_evidence'].append('resolved_parking_arrival');return base
        if not isinstance(layout,dict) or layout.get('geometry_status')!='resolved':base['unresolved_evidence'].append('resolved_parking_layout');return base
        if not isinstance(requirement,dict) or requirement.get('evidence_status') not in ('authoritative','resolved'):base['unresolved_evidence'].append('authoritative_parking_pedestrian_requirement');return base
        width=requirement.get('required_clear_width')
        if not isinstance(width,(int,float)) or width<=0:base['unresolved_evidence'].append('required_clear_width');return base
        origin=self._point(requirement.get('pedestrian_origin'))
        origin_source='explicit_project_requirement' if origin else None
        if not origin:
            aisle_line=(layout.get('parking_aisle') or {}).get('centerline',[])
            arrival_point=self._point(arrival.get('arrival_point'))
            terminals=[self._point(point) for point in aisle_line if self._point(point)]
            connected=[point for point in terminals if arrival_point and hypot(point[0]-arrival_point[0],point[1]-arrival_point[1])<=self.EPS]
            opposite=[point for point in terminals if point not in connected]
            if len(connected)==1 and len(opposite)==1:
                origin=opposite[0]
                origin_source='resolved_aisle_terminal_opposite_vehicle_arrival'
            elif not terminals:
                origin=arrival_point
                origin_source='resolved_parking_arrival_point'
        destinations=[d for d in requirement.get('destination_interfaces',[]) if isinstance(d,dict) and self._point(d.get('point')) and d.get('interface_status')=='resolved']
        if not origin:base['unresolved_evidence'].append('parking_pedestrian_origin');return base
        if not destinations:base['unresolved_evidence'].append('resolved_destination_interface');return base
        stairs=[v for v in vertical or [] if isinstance(v,dict) and v.get('geometry_status')=='resolved' and v.get('type')=='stair_geometry']
        if not any((not d.get('stair_core_id')) or
                   (d.get('stair_interface_status')=='resolved' and any(
                       (s.get('stair_id') or s.get('id'))==d.get('stair_core_id') or
                       (d.get('stair_requirement_id') and s.get('requirement_id')==d.get('stair_requirement_id'))
                       for s in stairs))
                   for d in destinations):
            base['unresolved_evidence'].append('resolved_stair_entry_interface');return base
        candidates=[]
        for di,destination in enumerate(destinations):
            stair_id=destination.get('stair_core_id')
            if stair_id and not any(
                (s.get('stair_id') or s.get('id'))==stair_id or
                (destination.get('stair_requirement_id') and s.get('requirement_id')==destination.get('stair_requirement_id'))
                for s in stairs):continue
            if stair_id and destination.get('stair_interface_status')!='resolved':continue
            target=self._point(destination['point'])
            paths=[('direct',[origin,target])]
            if requirement.get('orthogonal_paths_allowed') is True and origin[0]!=target[0] and origin[1]!=target[1]:
                paths.extend([('orthogonal_xy',[origin,[target[0],origin[1]],target]),('orthogonal_yx',[origin,[origin[0],target[1]],target])])
            for pi,(kind,path) in enumerate(paths):
                corridor=[self._strip(a,b,float(width)) for a,b in zip(path,path[1:])]
                result=self._validate(path,corridor,walls or [],openings or [],layout,vehicle_zones or [],protected_zones or [],requirement,destination)
                candidates.append({'candidate_id':f'PP-{di+1}-{pi+1}','destination_index':di,'path_type':kind,'path_centerline':path,
                                   'path_corridor':corridor,'path_length':sum(hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(path,path[1:])),**result})
        feasible=[c for c in candidates if c['geometry_status']=='feasible']
        if not feasible:return base|{'pedestrian_origin':origin,'required_clear_width':float(width),'candidates':candidates,
                                    'geometry_status':'unresolved_no_safe_path','unresolved_evidence':['no_safe_pedestrian_path']}
        best_length=min(c['path_length'] for c in feasible);best=[c for c in feasible if abs(c['path_length']-best_length)<=self.EPS]
        if len(best)!=1:return base|{'pedestrian_origin':origin,'required_clear_width':float(width),'candidates':candidates,
                                    'geometry_status':'pending_tie','unresolved_evidence':['equivalent_safe_paths_or_destinations']}
        chosen=best[0];dest=destinations[chosen['destination_index']]
        return base|{'parking_arrival_reference':arrival.get('entry_interface'),'parking_aisle_reference':layout.get('parking_aisle',{}).get('aisle_id','parking_aisle'),
                     'pedestrian_origin':origin,'pedestrian_destination':self._point(dest['point']),'target_circulation_space_id':dest.get('circulation_space_id'),
                     'target_stair_core_id':dest.get('stair_core_id'),'path_centerline':chosen['path_centerline'],'path_corridor':chosen['path_corridor'],
                     'required_clear_width':float(width),'vehicle_conflict_status':chosen['vehicle_conflict_status'],'stall_conflict_status':chosen['stall_conflict_status'],
                     'ramp_conflict_status':chosen['ramp_conflict_status'],'wall_conflict_status':chosen['wall_conflict_status'],
                     'protected_zone_status':chosen['protected_zone_status'],'crossing_policy':requirement.get('crossing_policy'),
                     'physical_opening_ids':chosen['physical_opening_ids'],'vertical_connection_status':'resolved' if dest.get('stair_interface_status')=='resolved' else 'not_required',
                     'parking_to_building_status':'resolved','geometry_status':'resolved','evidence_status':requirement.get('evidence_status'),
                     'origin_evidence':origin_source,'candidates':candidates,'unresolved_evidence':[]}

    def _validate(self,path,corridors,walls,openings,layout,vehicle_zones,protected,requirement,destination):
        allowed=set((requirement.get('crossing_policy') or {}).get('allowed_zone_ids',[])) if isinstance(requirement.get('crossing_policy'),dict) else set()
        physical=[];wall_conflict=False
        for a,b in zip(path,path[1:]):
            for wall in walls:
                if wall.get('floor')!=destination.get('floor'):continue
                hit=self._intersection(a,b,wall.get('start'),wall.get('end'))
                if hit:
                    matches=[o for o in openings if o.get('geometry_status')=='resolved' and o.get('host_wall_id')==wall.get('wall_id') and self._on(hit,o.get('opening_start'),o.get('opening_end'))]
                    if len(matches)!=1:wall_conflict=True
                    else:physical.append(matches[0].get('opening_id') or matches[0].get('id'))
        stalls=[s.get('polygon') for s in layout.get('parking_stalls',[]) if isinstance(s,dict)]
        stall_conflict=any(self._polys_hit(c,p) for c in corridors for p in stalls if p)
        vehicle_conflicts=[];ramp_conflict=False
        for zone in vehicle_zones:
            if not isinstance(zone,dict) or zone.get('id') in allowed:continue
            poly=zone.get('polygon');hit=poly and any(self._polys_hit(c,poly) for c in corridors)
            if hit:
                vehicle_conflicts.append(zone.get('id') or zone.get('type'));ramp_conflict|='ramp' in str(zone.get('type','')) or 'clearance' in str(zone.get('type',''))
        target_zone=destination.get('target_zone_id');protected_conflicts=[]
        for zone in protected:
            if not isinstance(zone,dict) or zone.get('id')==target_zone:continue
            poly=zone.get('polygon') or zone.get('points')
            if poly and any(self._polys_hit(c,poly) for c in corridors):protected_conflicts.append(zone.get('id') or zone.get('type'))
        feasible=not wall_conflict and not stall_conflict and not vehicle_conflicts and not protected_conflicts
        return {'geometry_status':'feasible' if feasible else 'not_feasible','vehicle_conflict_status':'clear' if not vehicle_conflicts else 'conflict',
                'stall_conflict_status':'clear' if not stall_conflict else 'conflict','ramp_conflict_status':'clear' if not ramp_conflict else 'conflict',
                'wall_conflict_status':'clear' if not wall_conflict else 'closed_wall','protected_zone_status':'clear' if not protected_conflicts else 'conflict',
                'physical_opening_ids':physical,'rejection_reasons':(['wall_without_opening'] if wall_conflict else [])+(['stall_conflict'] if stall_conflict else [])+vehicle_conflicts+protected_conflicts}
    @staticmethod
    def _point(v):return [float(v[0]),float(v[1])] if isinstance(v,(list,tuple)) and len(v)>=2 else None
    @staticmethod
    def _strip(a,b,w):
        l=hypot(b[0]-a[0],b[1]-a[1]);nx=-(b[1]-a[1])/l*w/2;ny=(b[0]-a[0])/l*w/2
        return [[a[0]+nx,a[1]+ny],[b[0]+nx,b[1]+ny],[b[0]-nx,b[1]-ny],[a[0]-nx,a[1]-ny]]
    @classmethod
    def _polys_hit(cls,a,b):
        return any(cls._inside(p,b) for p in a) or any(cls._inside(p,a) for p in b) or any(cls._segments(a[i],a[(i+1)%len(a)],b[j],b[(j+1)%len(b)]) for i in range(len(a)) for j in range(len(b)))
    @staticmethod
    def _inside(p,poly):
        inside=False;j=len(poly)-1
        for i in range(len(poly)):
            xi,yi=poly[i][:2];xj,yj=poly[j][:2]
            if (yi>p[1])!=(yj>p[1]) and p[0]<(xj-xi)*(p[1]-yi)/(yj-yi)+xi:inside=not inside
            j=i
        return inside
    @staticmethod
    def _segments(a,b,c,d):
        def o(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
        def on(p,q,r):return min(p[0],q[0])-1e-9<=r[0]<=max(p[0],q[0])+1e-9 and min(p[1],q[1])-1e-9<=r[1]<=max(p[1],q[1])+1e-9
        oa,ob,oc,od=o(a,b,c),o(a,b,d),o(c,d,a),o(c,d,b)
        if oa*ob < -1e-9 and oc*od < -1e-9:return True
        return (abs(oa)<=1e-9 and on(a,b,c)) or (abs(ob)<=1e-9 and on(a,b,d)) or (abs(oc)<=1e-9 and on(c,d,a)) or (abs(od)<=1e-9 and on(c,d,b))
    @classmethod
    def _intersection(cls,a,b,c,d):
        a,b,c,d=map(cls._point,(a,b,c,d))
        if not all((a,b,c,d)) or not cls._segments(a,b,c,d):return None
        x1,y1=a;x2,y2=b;x3,y3=c;x4,y4=d;den=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
        return [((x1*y2-y1*x2)*(x3-x4)-(x1-x2)*(x3*y4-y3*x4))/den,((x1*y2-y1*x2)*(y3-y4)-(y1-y2)*(x3*y4-y3*x4))/den]
    @classmethod
    def _on(cls,p,a,b):
        p,a,b=map(cls._point,(p,a,b));return bool(p and a and b and abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))<1e-6 and min(a[0],b[0])-1e-7<=p[0]<=max(a[0],b[0])+1e-7 and min(a[1],b[1])-1e-7<=p[1]<=max(a[1],b[1])+1e-7)
