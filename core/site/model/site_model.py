class SiteModel:

    VERSION = "1.0"


    def __init__(
        self,
        boundary,
        north=None,
        roads=None,
        climate=None,
        location=None
    ):

        self.boundary = boundary

        self.north = north

        self.roads = roads or []

        self.climate = climate or {}

        self.location = location


    def area_estimate(self):

        if len(self.boundary) < 3:
            return 0


        area = 0

        points = self.boundary


        for i in range(len(points)):

            x1, y1 = points[i]

            x2, y2 = points[
                (i + 1) % len(points)
            ]

            area += (
                x1 * y2 -
                x2 * y1
            )


        return abs(area) / 2


    def to_dict(self):

        return {

            "boundary": self.boundary,

            "north": self.north,

            "roads": self.roads,

            "climate": self.climate,

            "location": self.location,

            "area":
                self.area_estimate()

        }