import math


class SiteIntelligenceBuilder:


    VERSION = "SITE_INTELLIGENCE_v1"



    def build(
        self,
        parcel
    ):


        if not parcel or parcel.get("status") != "ready":

            return {

                "status":
                    "failed",

                "reason":
                    "invalid parcel"

            }



        points = parcel["points"]



        origin = self._origin(
            points
        )



        normalized = self._normalize(
            points,
            origin
        )



        bbox = self._bbox(
            normalized
        )



        orientation = self._orientation(
            normalized
        )



        return {


            "status":
                "ready",


            "site_id":
                self._generate_site_id(origin),


            "coordinate_system":
                "local_normalized",


            "origin":
                {

                    "x":
                        origin[0],

                    "y":
                        origin[1]

                },


            "boundary":
                normalized,


            "area":
                parcel.get(
                    "area"
                ),


            "bbox":
                bbox,


            "orientation":
                orientation,


            "source":
                {

                    "layer":
                        parcel.get("layer"),

                    "pattern":
                        parcel.get("pattern"),

                    "confidence":
                        parcel.get("confidence")

                }

        }


    def _generate_site_id(
        self,
        origin
    ):

        x = int(origin[0])

        y = int(origin[1])


        return (
            f"site_{x}_{y}"
        )




    # --------------------------------------

    def _origin(
        self,
        points
    ):

        min_x = min(
            float(p[0])
            for p in points
        )

        min_y = min(
            float(p[1])
            for p in points
        )


        return (
            min_x,
            min_y
        )




    # --------------------------------------

    def _normalize(
        self,
        points,
        origin
    ):


        ox,oy = origin


        return [

            {

                "x":
                    round(
                        p[0]-ox,
                        3
                    ),

                "y":
                    round(
                        p[1]-oy,
                        3
                    )

            }

            for p in points

        ]




    # --------------------------------------

    def _bbox(
        self,
        points
    ):


        xs=[
            p["x"]
            for p in points
        ]


        ys=[
            p["y"]
            for p in points
        ]


        return {

            "width":
                max(xs)-min(xs),


            "height":
                max(ys)-min(ys)

        }




    # --------------------------------------

    def _orientation(
        self,
        points
    ):


        if len(points)<2:

            return None



        dx = (
            points[1]["x"]
            -
            points[0]["x"]
        )


        dy = (
            points[1]["y"]
            -
            points[0]["y"]
        )



        angle = math.degrees(
            math.atan2(
                dy,
                dx
            )
        )


        return round(
            angle,
            2
        )