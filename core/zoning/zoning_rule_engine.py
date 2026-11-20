class ZoningRuleEngine:

    def __init__(self, ruleset=None):
        self.ruleset = ruleset or self.default_rules()


    # ======================
    # DEFAULT RULES
    # ======================
    def default_rules(self):

        return {

            "coverage": {

                "enabled": True,
 
                "min": 0.1,

                "max": 1.0,

                "value": None

            },


            "density": {

                "enabled": True,

                "value": None

            },


            "setbacks": {

                "enabled": True,

                "mandatory": False,

                "front": None,

                "rear": None,

                "side": None,

                "north": None,

                "south": None,

                "east": None,

                "west": None

            },


            "height": {

                "enabled": True,

                "max": None

            },


            "parking": {

                "enabled": True,

                "per_unit": None

            },


            "basement": {

                "allowed": True

            },


            "fire": {

                "enabled": False,

                "mandatory": False

            },


            "accessibility": {

                "enabled": False,

                "mandatory": False

            }

        }


    # ======================
    # MAIN VALIDATION
    # ======================
    def validate(self, site, building_plan):

        result = {
            "valid": True,
            "violations": [],
            "metrics": {}
        }


        area = self._site_area(site)

        footprint = self._footprint(
            building_plan
        )


        # ======================
        # INTENT COVERAGE OVERRIDE
        # ======================

        intent_constraints = building_plan.get(
            "site_constraints",
            {}
        )


        if isinstance(intent_constraints, dict):

            coverage_value = intent_constraints.get(
                "coverage"
            )

            if coverage_value:

                self.ruleset["coverage"]["max"] = coverage_value


        # ======================
        # SITE INTELLIGENCE
        # ======================

        result["metrics"]["site_area"] = area

        result["metrics"]["footprint"] = footprint


        # Current coverage

        coverage = (
            footprint / area
            if area > 0
            else 0
        )


        result["metrics"]["coverage"] = round(
            coverage,
            3
        )



        # Allowed footprint

        coverage_rule = self.ruleset.get(
            "coverage",
            {}
        )

        site_coverage_limit = site.get(
            "coverage_limit"
        )

        if site_coverage_limit is not None:

            coverage_rule[
                "max"
            ] = float(
                site_coverage_limit
            )


        max_coverage = coverage_rule.get(
            "max",
            1.0
        )


        result["metrics"]["allowed_footprint"] = (
            round(
                area * max_coverage,
                2
            )
        )


        # ======================
        # DENSITY / FAR CALCULATION
        # ======================


        density_value = None


        # از Intent

        intent_constraints = building_plan.get(
            "site_constraints",
            {}
        )


        if isinstance(intent_constraints, dict):

            density_value = intent_constraints.get(
                "density"
            )


        # اگر در ruleset بود

        if density_value is None:

            density_value = self.ruleset.get(
                "density",
                {}
            ).get(
                "value"
            )


        if density_value:


            result["metrics"]["density"] = density_value


            result["metrics"]["max_gross_floor_area"] = round(
                area * (density_value / 100),
                2
            )



        # Remaining open space

        result["metrics"]["remaining_open_space"] = (
            round(
                area - footprint,
                2
            )
        )



        # Buildable area

        result["metrics"]["buildable_area"] = (
            round(
                area * max_coverage,
                2
            )
        )


        coverage = (
            footprint / area
            if area > 0
            else 0
        )


        result["metrics"]["coverage"] = round(
            coverage,
            3
        )


        # COVERAGE RULE

        coverage_rule = self.ruleset["coverage"]


        if coverage_rule.get(
            "enabled",
            True
        ):

            if coverage > max_coverage:

                result[
                    "valid"
                ] = False

                result[
                    "violations"
                ].append(
                    f"Coverage {coverage:.2f} > allowed {max_coverage:.2f}"
                )


        # -----------------
        # HEIGHT RULE
        # -----------------

        height = building_plan.get(
            "height",
            3
        )


        height_rule = self.ruleset["height"]


        if (
            height_rule["enabled"]
            and
            height_rule["max"] is not None
        ):

            if height > height_rule["max"]:

                result["valid"] = False

                result["violations"].append(
                    f"Height {height} > allowed {height_rule['max']}"
                )



        # -----------------
        # SETBACK RULE
        # -----------------

        if not self._check_setbacks(site):

            result["valid"] = False

            result["violations"].append(
                "Setback violation detected"
            )


        return result



    # ======================
    # FOOTPRINT CALCULATOR
    # ======================
    def _footprint(self, building_plan):


        # direct value

        if "footprint" in building_plan:

            return float(
                building_plan["footprint"]
            )


        if "area" in building_plan:

            return float(
                building_plan["area"]
            )


        # rectangle geometry

        if (
            "width" in building_plan
            and
            "depth" in building_plan
        ):

            return (
                building_plan["width"]
                *
                building_plan["depth"]
            )


        if (
            "width" in building_plan
            and
            "height" in building_plan
        ):

            return (
                building_plan["width"]
                *
                building_plan["height"]
            )


        # bounds

        if "bounds" in building_plan:

            x1,y1,x2,y2 = building_plan["bounds"]

            return abs(x2-x1) * abs(y2-y1)



        # polygon

        if "points" in building_plan:

            return self._polygon_area(
                building_plan["points"]
            )


        # BIM spaces fallback

        if "spaces" in building_plan:

            total = 0

            for space in building_plan["spaces"]:

                total += self._footprint(
                    space
                )

            return total


        return 0



    # ======================
    # SITE AREA
    # ======================
    def _site_area(self, site):


        site_type = site.get(
            "type"
        )

        if site_type == "architectural_site":

            boundary = site.get(
                "boundary",
                {}
            )

            if isinstance(
                boundary,
                dict
            ):

                bounds = boundary.get(
                    "bounds"
                )

                if bounds:

                    x1, y1, x2, y2 = bounds

                    return (
                        abs(x2 - x1)
                        *
                        abs(y2 - y1)
                    )


            buildable_area = site.get(
                "buildable_area"
            )

            if isinstance(
                buildable_area,
                tuple
            ) and len(
                buildable_area
            ) == 4:

                x1, y1, x2, y2 = buildable_area

                return (
                    abs(x2 - x1)
                    *
                    abs(y2 - y1)
                )


        if site_type == "rect":


            if (
                "width" in site
                and
                "height" in site
            ):

                return (
                    site["width"]
                    *
                    site["height"]
                )


            if "bounds" in site:

                x1,y1,x2,y2 = site["bounds"]

                return abs(x2-x1)*abs(y2-y1)



            if "buildable_area" in site:

                area = site["buildable_area"]


                if isinstance(area, tuple):

                    x1,y1,x2,y2 = area

                    return abs(x2-x1)*abs(y2-y1)



        if site_type == "polygon":

            return self._polygon_area(
                site.get("points", [])
            )


        if site_type == "utm":

            return site.get(
                "approx_area",
                1000
            )


        if "area" in site:

            return site["area"]


        return 0



    # ======================
    # POLYGON AREA
    # ======================
    def _polygon_area(self, points):

        if not points:
            return 0


        area = 0


        for i in range(len(points)):

            x1,y1 = points[i]

            x2,y2 = points[
                (i+1)%len(points)
            ]

            area += (
                x1*y2
                -
                x2*y1
            )


        return abs(area)/2



    # ======================
    # SETBACK CHECK
    # VARIABLE BASED
    # ======================
    def _check_setbacks(self, site):


        setbacks = site.get(
            "setbacks"
        )


        # اگر ضوابط عقب نشینی وارد نشده باشد
        # یعنی اختیاری است
        if not setbacks:

            return True



        rule = self.ruleset.get(
            "setbacks",
            {}
        )



        # ----------------------
        # FRONT
        # ----------------------

        if (
            setbacks.get("front") is not None
            and
            rule.get("front") is not None
        ):

            if setbacks["front"] < rule["front"]:

                return False



        # ----------------------
        # REAR
        # ----------------------

        if (
            setbacks.get("rear") is not None
            and
            rule.get("rear") is not None
        ):

            if setbacks["rear"] < rule["rear"]:

                return False



        # ----------------------
        # SIDE
        # ----------------------

        if (
            setbacks.get("side") is not None
            and
            rule.get("side") is not None
        ):

            if setbacks["side"] < rule["side"]:

                return False



        # ----------------------
        # MULTI SIDE
        # شمال / جنوب / شرق / غرب
        # ----------------------

        directions = [
            "north",
            "south",
            "east",
            "west"
        ]


        for direction in directions:


            if direction in setbacks:


                value = setbacks[direction]


                minimum = rule.get(
                    direction
                )


                if (
                    minimum is not None
                    and
                    value < minimum
                ):

                    return False



        return True