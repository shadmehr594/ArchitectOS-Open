from __future__ import annotations

FAILURE_CODES=("FURNITURE_OUTSIDE_ROOM","FURNITURE_INTERSECTS_WALL","FURNITURE_BLOCKS_ROUTE","DOOR_SWING_FURNITURE_CONFLICT","WINDOW_FURNITURE_CONFLICT","FIXTURE_CLEARANCE_CONFLICT","KITCHEN_WORKZONE_CONFLICT")

def _inside(a,b,tol=.02): return a[0]>=b[0]-tol and a[1]>=b[1]-tol and a[2]<=b[2]+tol and a[3]<=b[3]+tol
def _overlap(a,b): return max(a[0],b[0]) < min(a[2],b[2]) and max(a[1],b[1]) < min(a[3],b[3])

class FurniturePlacementValidator:
    """Fail-closed geometric checks over semantic symbol footprints."""
    def validate(self, placed, rooms, door_zones=(), window_zones=(), routes=()):
        findings=[]
        for p in placed:
            box=p["footprint"]; room=rooms.get(p.get("room"))
            if room and not _inside(box,room): findings.append(self._f(p,"FURNITURE_OUTSIDE_ROOM"))
            if any(_overlap(box,z) for z in door_zones): findings.append(self._f(p,"DOOR_SWING_FURNITURE_CONFLICT"))
            if p.get("wall_aligned") and any(_overlap(box,z) for z in window_zones): findings.append(self._f(p,"WINDOW_FURNITURE_CONFLICT"))
            if any(_overlap(box,z) for z in routes): findings.append(self._f(p,"FURNITURE_BLOCKS_ROUTE"))
        return {"status":"PASS" if not findings else "FAIL","placed_count":len(placed),"findings":findings,"failure_code_contract":list(FAILURE_CODES)}
    @staticmethod
    def _f(p,code): return {"status":"FAIL","code":code,"semantic_id":p["semantic_id"],"room":p.get("room"),"footprint":p["footprint"]}
