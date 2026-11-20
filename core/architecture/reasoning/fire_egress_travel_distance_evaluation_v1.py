from shapely.geometry import LineString

class FireEgressTravelDistanceEvaluationV1:
    RULE_KEYS={'total_exit_access_travel_distance':'maximum_exit_access_travel_distance','common_path_of_egress_travel':'maximum_common_path_of_egress_travel','dead_end_corridor_length':'maximum_dead_end_corridor_length'}
    def evaluate(self,paths,regulation_context=None):
        regulation_context=regulation_context or {};evaluations={};unresolved=[]
        for concept,key in self.RULE_KEYS.items():
            path=paths.get(concept);distance=LineString(path).length if path and len(path)>1 else None;limit=regulation_context.get(key)
            if limit is None:status='pending_rule_resolution';margin=None;unresolved.append(key)
            elif distance is None:status='pending_path_geometry';margin=None
            else:margin=float(limit)-distance;status='passed' if margin>=-1e-7 else 'exceeded'
            evaluations[concept]={'actual_path_polyline':path,'travel_distance':distance,'applicable_limit':limit,'margin':margin,'status':status,'rule_source':regulation_context.get('source')}
        dead_path=paths.get('dead_end_corridor_length')
        return {'contract':'FireEgressTravelDistanceEvaluationV1','evaluations':evaluations,'rule_status':'pending_rule_resolution' if unresolved else 'resolved','unresolved_rules':unresolved,'common_path_evaluation':{'contract':'CommonPathOfEgressEvaluationV1',**evaluations['common_path_of_egress_travel']},'dead_end_evaluation':{'contract':'DeadEndCorridorEvaluationV1','dead_end_detected':bool(dead_path),'dead_end_start':dead_path[0] if dead_path else None,'dead_end_end':dead_path[-1] if dead_path else None,**evaluations['dead_end_corridor_length']}}
