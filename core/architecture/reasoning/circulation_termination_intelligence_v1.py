"""Terminate circulation at its last required functional destination."""
from math import hypot

from shapely.geometry import LineString


class CirculationTerminationIntelligenceV1:
    EPS = 1e-7

    def resolve(self, origin, direction, destinations, width, previous_end=None):
        dx, dy = map(float, direction)
        length = hypot(dx, dy)
        if length <= self.EPS or not destinations:
            return {"status": "unresolved", "reason": "direction_or_destination_missing"}
        ux, uy = dx/length, dy/length
        ox, oy = map(float, origin)
        stations = [max(0.0, (float(p[0])-ox)*ux + (float(p[1])-oy)*uy) for p in destinations]
        terminal_station = max(stations)
        endpoint = [ox+ux*terminal_station, oy+uy*terminal_station]
        centerline = LineString([[ox, oy], endpoint])
        corridor = centerline.buffer(float(width)/2, cap_style=2)
        previous_station = terminal_station
        if previous_end is not None:
            previous_station = max(0.0, (float(previous_end[0])-ox)*ux + (float(previous_end[1])-oy)*uy)
        dead_run = max(0.0, previous_station-terminal_station)
        return {
            "contract": "CirculationTerminationIntelligenceV1",
            "status": "resolved",
            "origin": [ox, oy],
            "functional_destinations": [[float(x), float(y)] for x, y in destinations],
            "last_functional_destination": endpoint,
            "centerline": [[float(x), float(y)] for x, y in centerline.coords],
            "corridor": self._poly(corridor),
            "circulation_length": centerline.length,
            "circulation_area": corridor.area,
            "dead_run_length": dead_run,
            "saved_length_against_previous_extent": dead_run,
            "saved_area_against_previous_extent": dead_run*float(width),
            "termination_basis": "last_required_functional_destination",
        }

    @staticmethod
    def _poly(polygon):
        return [[float(x), float(y)] for x, y in list(polygon.exterior.coords)[:-1]]
