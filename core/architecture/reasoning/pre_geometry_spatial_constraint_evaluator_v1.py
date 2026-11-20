"""Read-only evaluation of room placement before physical geometry exists."""
from __future__ import annotations

class PreGeometrySpatialConstraintEvaluatorV1:
    EPS=1e-7
    def evaluate(self,placements,connections,buildable_boundary=None,protected_zones=None):
        ps=[dict(p) for p in placements or [] if isinstance(p,dict)]
        by={(str(p.get('name')).lower(),p.get('floor')):p for p in ps if p.get('name')}
        failed=[];passed=[];unresolved=[];required=[];privacy=[];degree={p.get('name'):0 for p in ps}
        for i,r in enumerate(connections or []):
            if not isinstance(r,dict): continue
            a,b=r.get('from'),r.get('to'); floor=r.get('floor')
            left=[p for (n,f),p in by.items() if n==str(a).lower() and (floor is None or f==floor)]
            right=[p for (n,f),p in by.items() if n==str(b).lower() and (floor is None or f==floor)]
            item={'constraint_id':r.get('connection_id') or f'PG-{i+1:03d}','type':'required_shared_boundary',
                  'affected_spaces':[a,b],'relationship':dict(r)}
            if len(left)!=1 or len(right)!=1: item['reason']='unique_placed_endpoints';unresolved.append(item);continue
            if left[0].get('floor')!=right[0].get('floor'):
                item['type']='deferred_vertical_connection';item['reason']='evaluated_after_vertical_geometry'
                passed.append(item);continue
            shared=self.shared(left[0],right[0]); item['shared_boundary']=shared
            forbidden=r.get('direct_connection_forbidden') is True or r.get('type') in ('privacy_separation','forbidden_direct')
            if forbidden:
                if shared: privacy.append(item)
                else: passed.append(item)
                continue
            if r.get('required') is not True: continue
            (passed if shared else failed).append(item)
            if shared: degree[a]=degree.get(a,0)+1;degree[b]=degree.get(b,0)+1
            if not shared: required.append(item)
        boundary_fail=[]; protected=[]; overlaps=[]
        bb=self._poly_bbox(buildable_boundary)
        for p in ps:
            box=self.box(p)
            if not box: unresolved.append({'type':'placement_dimensions','affected_spaces':[p.get('name')]});continue
            if bb and not self.contains(bb,box): boundary_fail.append(p.get('name'))
            for z in protected_zones or []:
                zb=self._poly_bbox(z.get('polygon',z.get('points')) if isinstance(z,dict) else z)
                if zb and self.overlap(box,zb): protected.append({'space':p.get('name'),'zone':z.get('id') if isinstance(z,dict) else None})
        for i,a in enumerate(ps):
            for b in ps[i+1:]:
                if a.get('floor')==b.get('floor') and self.overlap(self.box(a),self.box(b)):
                    overlaps.append([a.get('name'),b.get('name')])
        isolated=[p.get('name') for p in ps if p.get('connection_required') is True and degree.get(p.get('name'),0)==0]
        dead=[p.get('name') for p in ps if p.get('circulation_role') and isinstance(p.get('minimum_connections'),int) and degree.get(p.get('name'),0)<p['minimum_connections']]
        failures=len(failed)+len(boundary_fail)+len(protected)+len(overlaps)+len(privacy)+len(isolated)+len(dead)
        score=max(0,100-20*len(failed)-20*len(privacy)-20*len(isolated)-15*len(dead)-25*len(boundary_fail)-25*len(protected)-15*len(overlaps)-10*len(unresolved))
        return {'status':'passed' if not failures and not unresolved else 'failed','passed_constraints':passed,
                'failed_constraints':failed,'unresolved_constraints':unresolved,
                'affected_space_ids':sorted({x for f in failed+unresolved for x in f.get('affected_spaces',[]) if x}),
                'failure_reasons':[f.get('reason','required_shared_boundary_missing') for f in failed]+(['privacy_violation'] if privacy else [])+(['isolated_space'] if isolated else [])+(['dead_end_circulation'] if dead else [])+(['buildable_boundary_violation'] if boundary_fail else [])+(['protected_zone_conflict'] if protected else [])+(['space_overlap'] if overlaps else []),
                'required_shared_boundaries':required,'required_circulation_interfaces':[], 'privacy_violations':privacy,
                'isolated_spaces':isolated, 'dead_end_circulation':dead, 'floor_violations':[], 'buildable_boundary_violations':boundary_fail,
                'protected_zone_conflicts':protected,'overlap_conflicts':overlaps,'quality_score':score,
                'evidence':{'placement_count':len(ps),'connection_count':len(connections or [])}}
    def shared(self,a,b):
        A,B=self.box(a),self.box(b)
        if not A or not B:return None
        y0,y1=max(A[1],B[1]),min(A[3],B[3]);x0,x1=max(A[0],B[0]),min(A[2],B[2])
        if y1-y0>self.EPS and (abs(A[2]-B[0])<=self.EPS or abs(B[2]-A[0])<=self.EPS):
            x=B[0] if abs(A[2]-B[0])<=self.EPS else A[0];return {'start':[x,y0],'end':[x,y1]}
        if x1-x0>self.EPS and (abs(A[3]-B[1])<=self.EPS or abs(B[3]-A[1])<=self.EPS):
            y=B[1] if abs(A[3]-B[1])<=self.EPS else A[1];return {'start':[x0,y],'end':[x1,y]}
    @staticmethod
    def box(p):
        try:return [float(p['x']),float(p['y']),float(p['x'])+float(p['width']),float(p['y'])+float(p['depth'])]
        except (KeyError,TypeError,ValueError):return None
    @staticmethod
    def overlap(a,b):return bool(a and b and min(a[2],b[2])-max(a[0],b[0])>1e-7 and min(a[3],b[3])-max(a[1],b[1])>1e-7)
    @staticmethod
    def contains(a,b):return b[0]>=a[0]-1e-7 and b[1]>=a[1]-1e-7 and b[2]<=a[2]+1e-7 and b[3]<=a[3]+1e-7
    @staticmethod
    def _poly_bbox(v):
        if isinstance(v,dict):v=v.get('points')
        if not isinstance(v,list) or len(v)<3:return None
        return [min(float(p[0]) for p in v),min(float(p[1]) for p in v),max(float(p[0]) for p in v),max(float(p[1]) for p in v)]
