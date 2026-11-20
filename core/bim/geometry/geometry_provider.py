class GeometryProvider:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🧱 Geometry Provider v{self.VERSION} ACTIVE"
        )


    def create_wall_geometry(
        self,
        wall_data
    ):

        raise NotImplementedError(
            "Wall geometry provider not implemented"
        )