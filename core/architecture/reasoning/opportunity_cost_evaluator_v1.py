"""Evidence-bearing marginal opportunity cost for allocation hypotheses."""

from .contextual_spatial_allocation_planner_v1 import _stable_unique_provenance


class OpportunityCostEvaluatorV1:
    def evaluate(self, allocation_plan, demand_profile):
        demands={f["function_id"]:f for f in demand_profile.get("functions",[])}; results=[]
        for hypothesis in allocation_plan.get("hypotheses",[]):
            assignments=hypothesis.get("assignments",[]); by_resource={}
            for a in assignments: by_resource.setdefault(a["resource_id"],[]).append(a)
            displaced=[]; losses=[]; marginal=0.0
            for resource, group in by_resource.items():
                ranked=sorted(group,key=lambda a:(-a["utility"],a["function_id"]))
                for item in ranked[1:]: displaced.append(item["function_id"]); marginal+=ranked[0]["utility"]-item["utility"]
            for unresolved in hypothesis.get("unresolved_demands",[]):
                fid=unresolved["function_id"]; losses.append({"function_id":fid,"reason":unresolved["reason"]})
            alternatives=[h for h in allocation_plan.get("hypotheses",[]) if h is not hypothesis and len(h.get("unresolved_demands",[]))<=len(hypothesis.get("unresolved_demands",[]))]
            best=min(alternatives,key=lambda h:(len(h["unresolved_demands"]),h["hypothesis_id"]),default=None)
            evidence=_stable_unique_provenance(e for a in assignments for e in a.get("evidence",[]))
            confidence=.75 if evidence and not hypothesis.get("unresolved_demands") else .35 if evidence else 0.0
            results.append({"hypothesis_id":hypothesis["hypothesis_id"],"consumed_resource_capacity":hypothesis.get("resource_consumption",{}),
                            "displaced_higher_demand_functions":displaced,"best_feasible_lower_cost_alternative":best["hypothesis_id"] if best else None,
                            "downstream_opportunities_lost":losses,"marginal_opportunity_cost":marginal,
                            "evidence":evidence,"provenance":["allocation_hypothesis","program_demand_profile"],"confidence":confidence})
        return {"contract":"OpportunityCostEvaluatorV1","alternatives":results,"fixed_edge_prohibitions":False,"complete":bool(results)}
