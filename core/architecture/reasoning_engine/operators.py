from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpatialIntent:
    operator: str; subjects: tuple[str,...]; parameters: dict


def _i(name,*subjects,**parameters): return SpatialIntent(name,subjects,parameters)
def place_adjacent(a,b): return _i("place_adjacent",a,b)
def place_near(a,b): return _i("place_near",a,b)
def place_far(a,b): return _i("place_far",a,b)
def place_between(a,b,c): return _i("place_between",a,b,c)
def place_on_frontage(space,edge): return _i("place_on_frontage",space,edge=edge)
def place_on_valid_daylight_source(space,source): return _i("place_on_valid_daylight_source",space,source)
def create_transition(public,private): return _i("create_transition",public,private)
def create_short_private_hall(*destinations): return _i("create_short_private_hall",*destinations)
def create_entry_bifurcation(public_branch,private_branch): return _i("create_entry_bifurcation",public_branch,private_branch)
def cluster_wet_spaces(*spaces): return _i("cluster_wet_spaces",*spaces)
def reserve_furniture_wall(space,length): return _i("reserve_furniture_wall",space,length=length)
def create_open_connection(a,b): return _i("create_open_connection",a,b)
def create_courtyard_for(*spaces): return _i("create_courtyard_for",*spaces)
def reserve_parking_access_maneuver(): return _i("reserve_parking_access_maneuver")
