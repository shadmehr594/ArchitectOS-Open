"""Fresh contract-only room/partition synthesis for the Parcel2 final design gate.

No CAD, prior candidate, or historical room coordinate is read by this module.
Areas are project design intent for this software gate, not regulatory claims.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Parcel2ProjectContract:
    width_m: float = 10.0
    depth_m: float = 20.0
    north: str = "TOP"
    south: str = "ONLY_STREET_ACCESS_DIRECT_EXTERNAL_DAYLIGHT"
    constrained_edges: tuple[str, ...] = ("EAST", "WEST", "NORTH")
    coverage_ground: float = 1.0
    coverage_upper: float = 1.0
    levels_m: dict[str, float] = field(default_factory=lambda: {"G": 0.0, "R1": 5.20, "R2": 8.44, "ROOF": 11.68, "PENTHOUSE_TOP": 14.38})
    stairs: dict[str, Any] = field(default_factory=lambda: {
        "G_R1": {"risers": 32, "flights": [8, 8, 8, 8], "riser_m": 0.1625},
        "R1_R2": {"risers": 20, "flights": [10, 10], "riser_m": 0.162},
        "R2_ROOF": {"risers": 20, "flights": [10, 10], "riser_m": 0.162},
    })


@dataclass(frozen=True)
class RoomProgram:
    room_id: str
    unit_id: str
    floor: str
    semantic_class: str
    required: bool
    area_class: str
    daylight_need: str
    privacy_zone: str
    wet_zone: bool = False
    terrace_relation: str | None = None
    adjacency_requirements: tuple[str, ...] = ()
    separation_requirements: tuple[str, ...] = ()
    open_plan_cell: str | None = None


@dataclass(frozen=True)
class GraphEdge:
    from_space: str
    to_space: str
    relation: str
    reason: str


@dataclass(frozen=True)
class DoorIntent:
    door_id: str
    floor: str
    from_space: str
    to_space: str
    host_partition_id: str
    desired_clear_width_m: float
    swing_policy: str
    privacy_transition: str
    center: tuple[float, float]
    axis: str


@dataclass(frozen=True)
class WindowIntent:
    window_id: str
    floor: str
    room_id: str
    allowed_exposure: str
    host_boundary_intent: str
    daylight_role: str
    center: tuple[float, float]
    axis: str


class Parcel2AutonomousRoomPartitionDesignGateV1:
    """Deterministic baseline solver whose decisions precede all wall geometry."""

    def __init__(self):
        self.contract = Parcel2ProjectContract()

    @staticmethod
    def _room(room_id, unit, floor, semantic, privacy, daylight="NONE", wet=False,
              terrace=None, adjacent=(), separate=(), open_cell=None):
        return RoomProgram(room_id, unit, floor, semantic, True, "PROJECT_DESIGN_INTENT",
                           daylight, privacy, wet, terrace, tuple(adjacent), tuple(separate), open_cell)

    def build_room_programs(self):
        r1 = [
            self._room("R1_U1_ENTRY", "R1_U1", "R1", "ENTRY_SHOE_OFF", "TRANSITION", adjacent=("R1_U1_HALL_1",)),
            self._room("R1_U1_LIVING", "R1_U1", "R1", "LIVING_RECEPTION", "PUBLIC", "DIRECT_OR_TERRACE", terrace="R1_U1_TERRACE", adjacent=("R1_U1_KITCHEN",)),
            self._room("R1_U1_KITCHEN", "R1_U1", "R1", "OPEN_KITCHEN_DINING", "PUBLIC", "DIRECT_OR_TERRACE", wet=True, open_cell="R1_U1_PUBLIC_OPEN_PLAN"),
            self._room("R1_U1_MASTER_SLEEP", "R1_U1", "R1", "MASTER_BEDROOM_SLEEPING", "PRIVATE", "REQUIRED", terrace="R1_U1_LIGHTWELL", adjacent=("R1_U1_DRESSING",)),
            self._room("R1_U1_DRESSING", "R1_U1", "R1", "MASTER_DRESSING", "PRIVATE", adjacent=("R1_U1_MASTER_SLEEP", "R1_U1_ENSUITE")),
            self._room("R1_U1_ENSUITE", "R1_U1", "R1", "MASTER_ENSUITE", "PRIVATE", wet=True, adjacent=("R1_U1_DRESSING",)),
            self._room("R1_U1_BEDROOM_2", "R1_U1", "R1", "BEDROOM", "PRIVATE", "REQUIRED", terrace="R1_U1_LIGHTWELL"),
            self._room("R1_U1_FAMILY_BATH", "R1_U1", "R1", "FAMILY_BATHROOM", "PRIVATE", wet=True),
            self._room("R1_U1_GUEST_WC", "R1_U1", "R1", "GUEST_WC", "TRANSITION", wet=True, separate=("R1_U1_LIVING",)),
            self._room("R1_U1_STORAGE", "R1_U1", "R1", "STORAGE_LINEN", "TRANSITION"),
            self._room("R1_U1_TERRACE", "R1_U1", "R1", "PRIVATE_TERRACE", "PUBLIC", "SOUTH_STREET"),
            self._room("R1_U1_LIGHTWELL", "R1_U1", "R1", "LIGHTWELL_OPEN_TO_SKY", "SERVICE", "OPEN_SKY"),
        ]
        r2=[]
        for u in ("R2_U1", "R2_U2"):
            r2 += [
                self._room(f"{u}_ENTRY_HALL",u,"R2","PRIVATE_ENTRY_HALL","TRANSITION"),
                self._room(f"{u}_LIVING_DINING",u,"R2","LIVING_DINING","PUBLIC","TERRACE",terrace=f"{u}_TERRACE",open_cell=f"{u}_PUBLIC_OPEN_PLAN"),
                self._room(f"{u}_KITCHEN",u,"R2","OPEN_KITCHEN","PUBLIC","BORROWED_OPEN_PLAN",wet=True,open_cell=f"{u}_PUBLIC_OPEN_PLAN"),
                self._room(f"{u}_BEDROOM_1",u,"R2","BEDROOM","PRIVATE","LIGHTWELL",terrace=f"{u}_LIGHTWELL"),
                self._room(f"{u}_BEDROOM_2",u,"R2","BEDROOM","PRIVATE","LIGHTWELL",terrace=f"{u}_LIGHTWELL"),
                self._room(f"{u}_BATH",u,"R2","BATHROOM","PRIVATE",wet=True),
                self._room(f"{u}_WC",u,"R2","SEPARATE_WC","TRANSITION",wet=True,separate=(f"{u}_LIVING_DINING",)),
                self._room(f"{u}_TERRACE",u,"R2","PRIVATE_TERRACE","PUBLIC","SOUTH_STREET"),
                self._room(f"{u}_LIGHTWELL",u,"R2","LIGHTWELL_OPEN_TO_SKY","SERVICE","OPEN_SKY"),
            ]
        return r1,r2

    @staticmethod
    def _rect(room_id, unit_id, floor, x0,y0,x1,y1, semantic, zone, subzones=()):
        return {"room_id":room_id,"unit_id":unit_id,"floor":floor,"semantic_class":semantic,"privacy_zone":zone,
                "polygon":[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],"area_m2":round((x1-x0)*(y1-y0),4),
                "open_plan_subzones":list(subzones),"generated_before_walls":True}

    def synthesize_partition_plans(self):
        # Grid coordinates are derived only from the 10x20 contract and program counts.
        xs=[0.2,2.6,5.0,7.4,9.8]; ys=[0.2,4.12,8.04,11.96,15.88,19.8]
        ids=[
            ["R1_U1_TERRACE","R1_U1_LIVING","R1_U1_ENTRY","R1_U1_KITCHEN"],
            ["R1_CORE","R1_U1_STORAGE","R1_U1_HALL_1","R1_U1_GUEST_WC"],
            ["R1_SERVICE_1","R1_U1_FAMILY_BATH","R1_U1_HALL_2","R1_U1_BEDROOM_2"],
            ["R1_SERVICE_2","R1_U1_DRESSING","R1_U1_HALL_3","R1_U1_LIGHTWELL"],
            ["R1_U1_LIGHTWELL_AUX","R1_U1_MASTER_SLEEP","R1_U1_HALL_4","R1_U1_ENSUITE"],
        ]
        semantics={"TERRACE":"TERRACE","LIVING":"PUBLIC_OPEN_PLAN","ENTRY":"ENTRY_SHOE_OFF","KITCHEN":"OPEN_KITCHEN_DINING",
                   "GUEST_WC":"GUEST_WC","STORAGE":"STORAGE_LINEN","HALL":"PRIVATE_CIRCULATION","FAMILY_BATH":"FAMILY_BATHROOM",
                   "CORE":"COMMON_VERTICAL_CORE","DRESSING":"MASTER_DRESSING","BEDROOM_2":"BEDROOM","ENSUITE":"MASTER_ENSUITE",
                   "MASTER_SLEEP":"MASTER_BEDROOM_SLEEPING","LIGHTWELL":"LIGHTWELL","SERVICE":"SERVICE"}
        r1=[]
        for row in range(5):
            for col in range(4):
                rid=ids[row][col]; key=next((k for k in semantics if k in rid),"HALL")
                r1.append(self._rect(rid,"COMMON" if rid=="R1_CORE" else "R1_U1","R1",xs[col],ys[row],xs[col+1],ys[row+1],semantics[key],"COMMON" if rid=="R1_CORE" else ("CIRCULATION" if "HALL" in rid or "ENTRY" in rid else "ROOM")))

        # R2: two independent strips, their own hall columns, and a vertically aligned central core.
        xs2=[0.2,3.6,4.2,5.8,6.4,9.8]; ys2=[0.2+i*2.45 for i in range(9)]
        order=["TERRACE","PUBLIC_OPEN_PLAN","BATH","BEDROOM_1","LIGHTWELL","BEDROOM_2","WC","STORAGE"]
        r2=[]
        for side,u,room_col,hall_col in (("L","R2_U1",0,1),("R","R2_U2",4,3)):
            for row,name in enumerate(order):
                rid=f"{u}_{name}"
                subs=[f"{u}_LIVING_DINING",f"{u}_KITCHEN"] if name=="PUBLIC_OPEN_PLAN" else []
                semantic={"TERRACE":"TERRACE","PUBLIC_OPEN_PLAN":"PUBLIC_OPEN_PLAN","BATH":"BATHROOM","BEDROOM_1":"BEDROOM","LIGHTWELL":"LIGHTWELL","BEDROOM_2":"BEDROOM","WC":"SEPARATE_WC","STORAGE":"STORAGE_LINEN"}[name]
                r2.append(self._rect(rid,u,"R2",xs2[room_col],ys2[row],xs2[room_col+1],ys2[row+1],semantic,"ROOM",subs))
                hall_id=f"{u}_ENTRY_HALL" if row==0 else f"{u}_HALL_{row}"
                r2.append(self._rect(hall_id,u,"R2",xs2[hall_col],ys2[row],xs2[hall_col+1],ys2[row+1],"PRIVATE_ENTRY_HALL" if row==0 else "PRIVATE_CIRCULATION","CIRCULATION"))
        r2.append(self._rect("R2_CORE","COMMON","R2",xs2[2],ys2[0],xs2[3],ys2[-1],"COMMON_VERTICAL_CORE","COMMON"))
        return r1,r2

    @staticmethod
    def _shared_edge(a,b):
        ax0,ay0=a["polygon"][0]; ax1,ay1=a["polygon"][2]
        bx0,by0=b["polygon"][0]; bx1,by1=b["polygon"][2]
        if abs(ax1-bx0)<1e-8 or abs(bx1-ax0)<1e-8:
            x=ax1 if abs(ax1-bx0)<1e-8 else bx1; lo=max(ay0,by0); hi=min(ay1,by1)
            if hi-lo>.5:return "V",(x,(lo+hi)/2)
        if abs(ay1-by0)<1e-8 or abs(by1-ay0)<1e-8:
            y=ay1 if abs(ay1-by0)<1e-8 else by1; lo=max(ax0,bx0); hi=min(ax1,bx1)
            if hi-lo>.5:return "H",((lo+hi)/2,y)
        return None

    @staticmethod
    def _partition_id(floor,axis,value): return f"{floor}_PART_{axis}_{value:.3f}"

    def synthesize_graph_and_intents(self,r1,r2):
        by={x["room_id"]:x for x in r1+r2}; edges=[]; doors=[]
        def connect(a,b,relation="MUST_CONNECT",privacy="SAME_ZONE"):
            shared=self._shared_edge(by[a],by[b]);
            if not shared: raise ValueError(f"NON_ADJACENT_INTENT:{a}:{b}")
            axis,center=shared; pid=self._partition_id(by[a]["floor"],axis,center[0] if axis=="V" else center[1])
            edges.append(GraphEdge(a,b,relation,"ACCESS_WITHOUT_ROOM_THROUGH_ROOM"))
            doors.append(DoorIntent(f"D_{len(doors)+1:03d}",by[a]["floor"],a,b,pid,.90,"ROOM_AWARE",privacy,center,axis))
        def exterior_entry(floor,inside,center):
            edges.append(GraphEdge(f"EXTERIOR:{floor}",inside,"MUST_CONNECT","AUTHORITATIVE_SOUTH_ACCESS"))
            doors.append(DoorIntent(f"D_{len(doors)+1:03d}",floor,f"EXTERIOR:{floor}",inside,self._partition_id(floor,"H",.2),1.0,"INWARD","PUBLIC_PRIVATE",center,"H"))
        # R1 circulation spine and room access. Public kitchen/living adjacency is open (no door).
        exterior_entry("R1","R1_U1_ENTRY",(6.2,.2))
        connect("R1_U1_ENTRY","R1_U1_HALL_1","PUBLIC_TO_PRIVATE_TRANSITION","PUBLIC_PRIVATE")
        connect("R1_U1_HALL_1","R1_U1_HALL_2"); connect("R1_U1_HALL_2","R1_U1_HALL_3"); connect("R1_U1_HALL_3","R1_U1_HALL_4")
        for a,b in [("R1_U1_ENTRY","R1_U1_LIVING"),("R1_U1_ENTRY","R1_U1_KITCHEN"),("R1_U1_HALL_1","R1_U1_STORAGE"),("R1_U1_HALL_1","R1_U1_GUEST_WC"),("R1_U1_HALL_2","R1_U1_FAMILY_BATH"),("R1_U1_HALL_2","R1_U1_BEDROOM_2"),("R1_U1_HALL_3","R1_U1_DRESSING"),("R1_U1_HALL_4","R1_U1_MASTER_SLEEP"),("R1_U1_HALL_4","R1_U1_ENSUITE"),("R1_U1_LIVING","R1_U1_TERRACE")]: connect(a,b)
        # R2 hall chains and one door from each hall segment to its same-row room.
        for u in ("R2_U1","R2_U2"):
            prev=f"{u}_ENTRY_HALL"
            for row,name in enumerate(["TERRACE","PUBLIC_OPEN_PLAN","BATH","BEDROOM_1","LIGHTWELL","BEDROOM_2","WC","STORAGE"]):
                hall=prev if row==0 else f"{u}_HALL_{row}"
                if row: connect(prev,hall)
                connect(hall,f"{u}_{name}",privacy="PUBLIC_PRIVATE" if name in {"PUBLIC_OPEN_PLAN","BEDROOM_1","BEDROOM_2"} else "SAME_ZONE")
                prev=hall
        exterior_entry("R2","R2_U1_ENTRY_HALL",(3.9,.2)); exterior_entry("R2","R2_U2_ENTRY_HALL",(6.1,.2))
        # Explicit negative and preference edges exist before geometry.
        for u in ("R2_U1","R2_U2"):
            edges += [GraphEdge(f"{u}_LIVING_DINING",f"{u}_WC","MUST_NOT_CONNECT","WC_NOT_DIRECT_TO_GUEST_AREA"),GraphEdge(f"{u}_BATH",f"{u}_WC","WET_CLUSTER_PREFERENCE","CLUSTER_SERVICES")]
        edges += [GraphEdge("R2_U1_ENTRY_HALL","R2_U2_ENTRY_HALL","MUST_NOT_CONNECT","INDEPENDENT_DWELLINGS")]
        windows=[
            WindowIntent("W_R1_LIVING","R1","R1_U1_LIVING","SOUTH_STREET",self._partition_id("R1","H",.2),"PUBLIC_DAYLIGHT",(3.8,.2),"H"),
            WindowIntent("W_R1_KITCHEN","R1","R1_U1_KITCHEN","SOUTH_STREET",self._partition_id("R1","H",.2),"PUBLIC_DAYLIGHT",(8.6,.2),"H"),
            WindowIntent("W_R1_MASTER","R1","R1_U1_MASTER_SLEEP","LIGHTWELL",self._partition_id("R1","V",2.6),"SLEEPING_DAYLIGHT",(2.6,17.84),"V"),
            WindowIntent("W_R1_BED2","R1","R1_U1_BEDROOM_2","LIGHTWELL",self._partition_id("R1","H",11.96),"BEDROOM_DAYLIGHT",(8.6,11.96),"H"),
        ]
        for u,x_room,x_lw in (("R2_U1",3.6,1.9),("R2_U2",6.4,8.1)):
            # Windows are on boundaries between bedroom rows and the open-sky lightwell row.
            windows += [WindowIntent(f"W_{u}_B1","R2",f"{u}_BEDROOM_1","LIGHTWELL",self._partition_id("R2","H",10.0),"BEDROOM_DAYLIGHT",(x_lw,10.0),"H"),
                        WindowIntent(f"W_{u}_B2","R2",f"{u}_BEDROOM_2","LIGHTWELL",self._partition_id("R2","H",12.45),"BEDROOM_DAYLIGHT",(x_lw,12.45),"H")]
        return edges,doors,windows

    def synthesize_geometry(self,plans,doors,windows):
        floors={}
        for floor,rooms in plans.items():
            vertical=sorted({p[0] for r in rooms for p in r["polygon"]}); horizontal=sorted({p[1] for r in rooms for p in r["polygon"]})
            walls=[]
            def add(axis,value,start,end,outer=False):
                pid=self._partition_id(floor,axis,value)
                minimum=vertical[0] if axis=="V" else horizontal[0]
                offsets=(-0.2,0.0) if outer and value==minimum else ((0.0,0.2) if outer else (-0.1,0.1))
                for j,o in enumerate(offsets):
                    a=[value+o,start] if axis=="V" else [start,value+o]; b=[value+o,end] if axis=="V" else [end,value+o]
                    walls.append({"start":a,"end":b,"source_handle":pid,"source_handles":[pid],"source_layer":f"{floor}_ROOM_WALL","entity_type":"LINE","role":"wall","face_index":j})
            for x in vertical:add("V",x,.2,19.8,x in {vertical[0],vertical[-1]})
            for y in horizontal:add("H",y,.2,9.8,y in {horizontal[0],horizontal[-1]})
            labels=[]
            for r in rooms:
                x0,y0=r["polygon"][0]; x1,y1=r["polygon"][2]
                labels.append({"handle":f"LBL_{r['room_id']}","text":r["room_id"],"point":[(x0+x1)/2,(y0+y1)/2],"semantic_class":r["semantic_class"]})
            openings=[]
            for intent in [*doors,*windows]:
                if intent.floor!=floor:continue
                x,y=intent.center; half=intent.desired_clear_width_m/2 if isinstance(intent,DoorIntent) else .55
                a,b=([x-half,y],[x+half,y]) if intent.axis=="H" else ([x,y-half],[x,y+half])
                kind="DOOR" if isinstance(intent,DoorIntent) else "WINDOW"
                openings.append({"handle":intent.door_id if kind=="DOOR" else intent.window_id,"kind":kind,"layer":f"{floor}_{kind}","entity_type":"LINE",
                    "segments":[{"start":a,"end":b,"source_handle":intent.door_id if kind=="DOOR" else intent.window_id,"source_handles":[intent.door_id if kind=="DOOR" else intent.window_id],"source_layer":f"{floor}_{kind}","entity_type":"LINE","role":kind.lower()}],"points":[a,b],
                    "expected_from_space":intent.from_space if kind=="DOOR" else intent.room_id,"expected_to_space":intent.to_space if kind=="DOOR" else None,
                    "expected_host_partition":intent.host_partition_id if kind=="DOOR" else intent.host_boundary_intent,"expected_exposure":None if kind=="DOOR" else intent.allowed_exposure})
            floors[floor]={"wall_segments":walls,"opening_entities":openings,"labels":labels,"extent":[0.0,0.0,10.0,20.0]}
        return floors

    def generate(self):
        r1_program,r2_program=self.build_room_programs(); r1,r2=self.synthesize_partition_plans()
        edges,doors,windows=self.synthesize_graph_and_intents(r1,r2)
        geometry=self.synthesize_geometry({"R1":r1,"R2":r2},doors,windows)
        units={}
        for unit in ("R1_U1","R2_U1","R2_U2"):
            unit_edges=[asdict(e) for e in edges if e.from_space.startswith(unit) and e.to_space.startswith(unit)]
            units[unit]={"entry_node":f"{unit}_ENTRY" if unit=="R1_U1" else f"{unit}_ENTRY_HALL","public_zone":[x.room_id for x in r1_program+r2_program if x.unit_id==unit and x.privacy_zone=="PUBLIC"],"transition_private_zone":[x.room_id for x in r1_program+r2_program if x.unit_id==unit and x.privacy_zone in {"TRANSITION","PRIVATE"}],"terrace_connection":f"{unit}_TERRACE","lightwell_connection":f"{unit}_LIGHTWELL","edges":unit_edges,"room_through_room_edges":[]}
        return {"project_contract":asdict(self.contract),"r1_room_program":[asdict(x) for x in r1_program],"r2_room_program":[asdict(x) for x in r2_program],"adjacency_graph":[asdict(x) for x in edges],"unit_layout_graph":units,"partition_plan_r1":r1,"partition_plan_r2":r2,"door_intents":[asdict(x) for x in doors],"window_intents":[asdict(x) for x in windows],"geometry":geometry,"provenance":{"room_coordinates_from_dwg":False,"manual_geometry_fallback":False,"source":"PARCEL2_PROJECT_CONTRACT_AND_ROOM_PROGRAM_ONLY"}}
