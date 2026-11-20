import math
from core.cad.parcel_extractor import ParcelExtractor
from core.cad.site_intelligence import SiteIntelligenceBuilder
from core.cad.site_constraints import SiteConstraintExtractor


class CADImportEngine:


    VERSION = "CAD_IMPORT_ENGINE_v2_REAL"



    def load(
        self,
        dxf_data,
        target_parcel=None
    ):


        geometry = self._extract_geometry(
            dxf_data
        )


        geometry["parcel_candidates"] = self._detect_parcel_candidates(
            geometry.get("hatches", []),
            geometry.get("polylines", []),
            geometry.get("text", [])
        )

        parcel = ParcelExtractor().extract(
            geometry,
            target_parcel=target_parcel
        )


        site_intelligence = SiteIntelligenceBuilder().build(
            parcel
        )


        constraints = SiteConstraintExtractor().extract(
            site_intelligence,
            geometry
        )


        scale = self._detect_scale(
            geometry
        )


        site = self._build_site(
            geometry,
            scale,
            parcel=parcel
        )

        if isinstance(site, dict):
            site["pedestrian_access_candidates"] = list(
                geometry.get("pedestrian_access_candidates", [])
            )

        # ==================================================
        # NORMALIZED ARCHITECTURAL SITE CONTRACT
        #
        # CADImportEngine already produces:
        #
        #     site
        #     site_intelligence
        #     constraints
        #
        # SiteReasoner consumes these as one normalized
        # architectural site contract.
        #
        # Preserve the existing CAD outputs unchanged while
        # enriching the site object used by Architecture.
        # ==================================================

        if isinstance(
            site,
            dict
        ):

            site[
                "site_intelligence"
            ] = (
                dict(
                    site_intelligence
                )
                if isinstance(
                    site_intelligence,
                    dict
                )
                else {}
            )


            if (
                isinstance(
                    constraints,
                    dict
                )
                and
                isinstance(
                    constraints.get(
                        "constraints"
                    ),
                    dict
                )
            ):

                site[
                    "site_constraints"
                ] = dict(
                    constraints.get(
                        "constraints"
                    )
                )

            elif isinstance(
                constraints,
                dict
            ):

                site[
                    "site_constraints"
                ] = dict(
                    constraints
                )

            else:

                site[
                    "site_constraints"
                ] = {}


            if (
                site.get(
                    "type"
                ) == "polygon"
            ):

                site[
                    "source_type"
                ] = "polygon"


            site[
                "boundary"
            ] = {

                "type":
                    "polygon",

                "points":
                    list(
                        site.get(
                            "points",
                            []
                        )
                    )

            }


        return {

            "type":
                "cad",

            "scale":
                scale,

            "geometry":
                geometry,

            "site":
                site,

            "parcel":
                parcel,

            "site_intelligence":
                site_intelligence,

            "constraints":
                constraints

        }




    # ==================================================
    # REAL DXF ENTRY
    # ==================================================

    def _extract_geometry(
        self,
        dxf_data
    ):


        layers = {}



        file_object = dxf_data.get(
            "file_object"
        )



        if file_object:


            return self._parse_dxf(
                file_object
            )



        return {

            "layers":
                layers,

            "walls":
                [],

            "text":
                [],

            "entities":
                [],

            "polylines":
                [],

            "hatches":
                [],

            "parcel_candidates":
                []

        }




    # ==================================================
    # DXF PARSER
    # ==================================================

    def _parse_dxf(
        self,
        file_object
    ):


        try:


            import ezdxf



            doc = ezdxf.readfile(
                file_object
            )



            modelspace = doc.modelspace()



            layers = {}

            walls = []

            text = []

            entities = []

            polylines = []

            hatches = []
            pedestrian_access_candidates = []

            drawing_units = doc.header.get("$INSUNITS", 0)




            for entity in modelspace:


                layer = entity.dxf.layer



                layers.setdefault(
                    layer,
                    []
                )



                # --------------------------
                # LINE
                # --------------------------

                if entity.dxftype()=="LINE":


                    item = {

                        "type":
                            "LINE",

                        "start":
                            [
                            entity.dxf.start.x,
                            entity.dxf.start.y
                            ],


                        "end":
                            [
                            entity.dxf.end.x,
                            entity.dxf.end.y
                            ]

                    }



                    layers[layer].append(
                        item
                    )


                    walls.append(
                        item
                    )

                    if layer.upper() in {"SITE_PEDESTRIAN_ACCESS", "PEDESTRIAN_ACCESS", "MAIN_ENTRANCE_ACCESS"}:
                        pedestrian_access_candidates.append({
                            "access_id": entity.dxf.handle,
                            "approach_start": list(item["start"]),
                            "approach_end": list(item["end"]),
                            "approach_line": [list(item["start"]), list(item["end"])],
                            "geometry_status": "candidate",
                            "source_evidence": [f"DXF layer {layer}", f"DXF handle {entity.dxf.handle}"],
                        })


                # --------------------------
                # LWPOLYLINE
                # --------------------------

                elif entity.dxftype()=="LWPOLYLINE":


                    points = []


                    for p in entity.get_points():

                        points.append(
                            [
                                p[0],
                                p[1]
                            ]
                        )


                    item = {

                        "type":
                            "LWPOLYLINE",


                        "layer":
                            layer,


                        "closed":
                            entity.closed,

                        "handle":
                            entity.dxf.handle,

                        # Elevation is retained as source metadata only.  Site
                        # geometry is deliberately built from the XY ordinates.
                        "elevation":
                            float(entity.dxf.elevation),


                        "points":
                            points

                    }


                    polylines.append(
                        item
                    )


                    layers[layer].append(
                        item
                    )

                    if layer.upper() in {"SITE_PEDESTRIAN_ACCESS", "PEDESTRIAN_ACCESS", "MAIN_ENTRANCE_ACCESS"} and len(points) == 2:
                        pedestrian_access_candidates.append({
                            "access_id": entity.dxf.handle,
                            "approach_start": list(points[0]),
                            "approach_end": list(points[1]),
                            "approach_line": [list(points[0]), list(points[1])],
                            "geometry_status": "candidate",
                            "source_evidence": [f"DXF layer {layer}", f"DXF handle {entity.dxf.handle}"],
                        })



                # --------------------------
                # HATCH
                # --------------------------

                elif entity.dxftype()=="HATCH":


                    item = {

                        "type":
                            "HATCH",

                        "layer":
                            layer,

                        "pattern":
                            entity.dxf.pattern_name,

                        "boundary":
                            [],

                        "boundaries":
                            []

                    }


                    for path in entity.paths:

                        if not hasattr(
                            path,
                            "vertices"
                        ):
                            continue


                        boundary = [

                            [
                                float(v[0]),
                                float(v[1])
                            ]

                            for v in path.vertices

                        ]


                        if len(
                            boundary
                        ) < 3:
                            continue


                        item[
                            "boundaries"
                        ].append(
                            boundary
                        )


                    if item[
                        "boundaries"
                    ]:

                        item[
                            "boundary"
                        ] = max(

                            item[
                                "boundaries"
                            ],

                            key=lambda points: abs(

                                sum(

                                    points[i][0]
                                    *
                                    points[
                                        (i + 1)
                                        %
                                        len(points)
                                    ][1]

                                    -

                                    points[
                                        (i + 1)
                                        %
                                        len(points)
                                    ][0]
                                    *
                                    points[i][1]

                                    for i in range(
                                        len(points)
                                    )

                                )
                                / 2

                            )

                        )



                    hatches.append(
                        item
                    )



                    layers[layer].append(
                        item
                    )




                                # --------------------------
                # TEXT
                # --------------------------

                elif entity.dxftype() == "TEXT":

                    item = {

                        "type":
                            "TEXT",

                        "value":
                            entity.dxf.text,

                        "position":
                            [
                                entity.dxf.insert.x,
                                entity.dxf.insert.y
                            ],

                        "layer":
                            layer

                    }


                    text.append(
                        item
                    )


                    layers[layer].append(
                        item
                    )


                # --------------------------
                # MTEXT
                # --------------------------

                elif entity.dxftype() == "MTEXT":

                    try:

                        value = entity.plain_text()

                    except Exception:

                        value = entity.text


                    item = {

                        "type":
                            "MTEXT",

                        "value":
                            value.strip(),

                        "raw_value":
                            entity.text,

                        "position":
                            [
                                entity.dxf.insert.x,
                                entity.dxf.insert.y
                            ],

                        "layer":
                            layer

                    }


                    text.append(
                        item
                    )


                    layers[layer].append(
                        item
                    )


                entities.append(
                    entity.dxftype()
                )



            parcel_candidates = self._detect_parcel_candidates(
                hatches
            )


            return {


                "layers":
                    layers,


                "walls":
                    walls,


                "text":
                    text,


                "entities":
                    entities,


                "polylines":
                    polylines,


                "hatches":
                    hatches,

                "pedestrian_access_candidates":
                    pedestrian_access_candidates,

                "drawing_units":
                    drawing_units,



            }




        except Exception as e:


            return {


                "layers":
                    {},


                "walls":
                    [],


                "text":
                    [],


                "entities":
                    [],


                "polylines":
                    [],


                "hatches":
                    [],


                "parcel_candidates":
                    [],


                "error":
                    str(e)

            }


    def _detect_parcel_candidates(
        self,
        hatches,
        polylines=None,
        text_items=None
    ):

        candidates = []

        polylines = polylines or []
        text_items = text_items or []


        ignored_layers = [
            "hach sabz",
            "green",
            "vegetation",
            "park"
        ]


        for hatch in hatches:


            layer = hatch.get(
                "layer",
                ""
            ).lower()


            pattern = hatch.get(
                "pattern",
                ""
            )


            points = hatch.get(
                "boundary",
                []
            )


            if len(points) < 3:
                continue


            if layer in ignored_layers:
                continue


            area = abs(
                sum(
                    points[i][0] * points[(i+1)%len(points)][1]
                    -
                    points[(i+1)%len(points)][0] * points[i][1]

                    for i in range(len(points))
                )
                / 2
            )


            score = 0


            # --------------------------------
            # Geometry confidence
            # --------------------------------

            # polygon بزرگ‌تر از یک خط ساده باشد
            if len(points) >= 4:
                score += 30


            # --------------------------------
            # Hatch pattern intelligence
            # --------------------------------

            pattern_lower = pattern.lower()


            if pattern_lower in [
                "ansi31",
                "ansi32",
                "ansi33"
            ]:
                score += 25


            # Solid معمولاً فضای پر شده، محوطه یا سبز است
            if pattern_lower == "solid":
                score -= 10



            # --------------------------------
            # Layer semantic hints
            # --------------------------------

            layer_lower = layer.lower()


            negative_keywords = [
                "green",
                "veget",
                "park",
                "sabz",
                "tree",
                "garden"
            ]


            for word in negative_keywords:

                if word in layer_lower:
                    score -= 40



            positive_keywords = [
                "parcel",
                "plot",
                "land",
                "site",
                "boundary",
                "kol",
                "kadr"
            ]


            for word in positive_keywords:

                if word in layer_lower:
                    score += 20



            # --------------------------------
            # Area sanity
            # --------------------------------

            if 30 < area < 5000:
                score += 20


            candidates.append({

                "source":
                    "hatch",

                "layer": 
                    layer,

                "pattern":
                    pattern,

                "points":
                    points,

                "area":
                    area,

                "score":
                    score

            })

        # A closed LWPOLYLINE is a stronger parcel boundary source than a
        # coincident display hatch: it carries explicit closure and vertices.
        for polyline in polylines:
            points = polyline.get("points", [])
            if not polyline.get("closed") or len(points) < 3:
                continue

            area = self._polygon_area(points)
            if area <= 0 or self._polygon_self_intersects(points):
                continue

            perimeter = sum(
                math.dist(points[index], points[(index + 1) % len(points)])
                for index in range(len(points))
            )
            labels = []
            for item in text_items:
                position = item.get("position")
                if (
                    item.get("layer", "").upper() == "CODE"
                    and position
                    and self._point_in_polygon(position, points)
                ):
                    labels.append(str(item.get("value", "")).strip())

            score = 70
            if 30 < area < 5000:
                score += 20
            if labels:
                score += 10

            candidates.append({
                "source": "closed_lwpolyline",
                "layer": polyline.get("layer", ""),
                "pattern": None,
                "handle": polyline.get("handle"),
                "points": points,
                "closed": True,
                "valid": True,
                "area": area,
                "perimeter": perimeter,
                "contained_code_labels": labels,
                "elevation_ignored_for_2d": polyline.get("elevation"),
                "score": score,
            })


        if not candidates:
            return []


        return candidates

    @staticmethod
    def _polygon_area(points):
        return abs(sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        ) / 2.0)

    @staticmethod
    def _point_in_polygon(point, polygon):
        x, y = float(point[0]), float(point[1])
        inside = False
        previous = len(polygon) - 1
        for current in range(len(polygon)):
            xi, yi = polygon[current]
            xj, yj = polygon[previous]
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi) + xi
            ):
                inside = not inside
            previous = current
        return inside

    @staticmethod
    def _polygon_self_intersects(points):
        def orientation(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        count = len(points)
        for first in range(count):
            a = points[first]
            b = points[(first + 1) % count]
            for second in range(first + 1, count):
                if second in {first, (first + 1) % count} or (second + 1) % count == first:
                    continue
                c = points[second]
                d = points[(second + 1) % count]
                if orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0:
                    return True
        return False




    # ==================================================
    # SCALE
    # ==================================================

    def _detect_scale(
        self,
        geometry
    ):


        # Some municipal drawings advertise INSUNITS=1 (inches) while their
        # parcel geometry and annotations are plainly metric.  Prefer that
        # internally consistent contract over the misleading header.
        for candidate in geometry.get("parcel_candidates", []):
            labels = candidate.get("contained_code_labels", [])
            area = candidate.get("area", 0)
            perimeter = candidate.get("perimeter", 0)
            numeric_labels = []
            for label in labels:
                try:
                    numeric_labels.append(float(label))
                except (TypeError, ValueError):
                    continue
            annotated_area_matches = any(
                math.isclose(value, area, rel_tol=0.0, abs_tol=0.05)
                for value in numeric_labels
            )
            if (
                candidate.get("source") == "closed_lwpolyline"
                and annotated_area_matches
                and area > 30
                and perimeter > 20
            ):
                geometry["unit_resolution"] = {
                    "scale": 1.0,
                    "contract": "metric_geometry_and_annotations",
                    "header_insunits": geometry.get("drawing_units"),
                    "header_ignored": geometry.get("drawing_units") == 1,
                }
                return 1.0

        walls = geometry.get(
            "walls",
            []
        )


        if not walls:
            return 1.0



        xs=[]

        ys=[]


        for w in walls:


            xs.extend(
                [
                w["start"][0],
                w["end"][0]
                ]
            )


            ys.extend(
                [
                w["start"][1],
                w["end"][1]
                ]
            )



        max_dim=max(
            max(xs),
            max(ys)
        )



        if max_dim > 1000:
            return 0.001


        return 1.0





    # ==================================================
    # SITE
    # ==================================================

    def _build_site(
        self,
        geometry,
        scale,
        parcel=None
    ):


        # ==========================================
        # AUTHORITATIVE PARCEL SITE
        # ==========================================

        if (
            parcel
            and
            parcel.get("status") == "ready"
            and
            len(parcel.get("points", [])) >= 3
        ):

            source_points = parcel.get(
                "points",
                []
            )


            xs = [
                float(p[0])
                for p in source_points
            ]

            ys = [
                float(p[1])
                for p in source_points
            ]


            min_x = min(xs)
            min_y = min(ys)

            max_x = max(xs)
            max_y = max(ys)


            local_points = [

                [
                    round(
                        float(p[0]) - min_x,
                        6
                    ),
                    round(
                        float(p[1]) - min_y,
                        6
                    )
                ]

                for p in source_points

            ]


            return {

                "type":
                    "polygon",

                "source":
                    "parcel",

                "target_parcel":
                    parcel.get(
                        "target_parcel"
                    ),

                "coordinate_system":
                    "local_normalized",

                "origin":
                    {
                        "x":
                            min_x,

                        "y":
                            min_y
                    },

                "points":
                    local_points,

                "bbox":
                    {

                        "width":
                            round(
                                max_x - min_x,
                                6
                            ),

                        "height":
                            round(
                                max_y - min_y,
                                6
                            )

                    },

                "area":
                    parcel.get(
                        "area"
                    )

            }


        walls = geometry.get(
            "walls",
            []
        )



        if not walls:


            return {


                "type":
                    "unknown",


                "error":
                    "no geometry found"

            }




        xs=[]

        ys=[]



        for w in walls:


            xs += [
                w["start"][0],
                w["end"][0]
            ]


            ys += [
                w["start"][1],
                w["end"][1]
            ]



        points=[

            [
            min(xs)*scale,
            min(ys)*scale
            ],


            [
            max(xs)*scale,
            min(ys)*scale
            ],


            [
            max(xs)*scale,
            max(ys)*scale
            ],


            [
            min(xs)*scale,
            max(ys)*scale
            ]

        ]



        return {


            "type":
                "rect",


            "points":
                points,


            "bbox":
                {

                "width":
                    max(xs)*scale-min(xs)*scale,


                "height":
                    max(ys)*scale-min(ys)*scale

                }


        }
