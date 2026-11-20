import datetime
import os
from collections import Counter


try:
    import ifcopenshell
except Exception:
    ifcopenshell = None


class BIMExportValidator:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"✅ BIM Export Validator v{self.VERSION} ACTIVE"
        )


    # ==========================================
    # MAIN VALIDATION
    # ==========================================

    def validate(
        self,
        bim_result,
        exports
    ):


        print("\n====== VALIDATOR INPUT DEBUG ======")

        print(
            "BIM RESULT KEYS:",
            bim_result.keys()
        )

        print(
            "EXPORT KEYS:",
            exports.keys()
        )


        quality_v2 = {}


        real_ifc = self._load_real_ifc(
            exports
        )

        print("\n====== REAL IFC LOADED DEBUG ======")
        print(type(real_ifc))
        print(real_ifc)


        checks = {


            "element_count":
                self._check_element_count(
                    bim_result,
                    exports
                ),


            "revit_mapping":
                self._check_revit_mapping(
                    bim_result
                ),


            "ifc_consistency":
                self._check_ifc(
                    exports
                ),


            "build_plan":
                self._check_build_plan(
                    exports
                )

        }


        # ======================================
        # QUALITY VALIDATION v2
        # ======================================

        quality_checks = {

            "ifc_structure":
                self._validate_ifc_structure(
                    exports
                ),

            "geometry_quality":
                self._validate_geometry_quality(
                    bim_result
                ),

            "opening_relationships":
                self._validate_openings(
                    exports
                ),

            "placement_quality":
                self._validate_placements(
                    bim_result
                )

        }



        # ======================================
        # FINAL IFC DEBUG
        # ======================================

        self._debug_ifc_types(
            exports
        )


        self._debug_real_ifc_file(
            exports
        )


        self._debug_opening_relationships(
            exports
        )


        self._debug_spatial_containment(
            exports
        )


        quality_v2 = {

            "ifc_structure":
                self._validate_ifc_structure(
                    exports
                ),


            "real_ifc":
                self._validate_real_ifc(
                    exports
                ),


            "relationships":
                self._validate_relationships(
                    exports
                ),


            "spatial_structure":
                self._validate_ifc_spatial_structure(
                    exports
                ),


            "geometry":
                self._validate_geometry_quality(
                    bim_result
                )

        }


        status = (

            "passed"

            if all(
                [
                    checks["ifc_consistency"],
                    quality_v2["real_ifc"]["status"] == "passed",
                    quality_v2["relationships"]["status"] == "passed"
                ]
            )

            else

            "warning"

        )


        return {


            "engine":

                f"BIM_EXPORT_VALIDATOR_v{self.VERSION}",



            "created":

                datetime.datetime.now().isoformat(),



            "status":

                status,



            "checks":

                checks,



            "quality_v2": {

                "basic":
                    quality_checks,

                "advanced":
                    quality_v2

            },



            "statistics":

                self._statistics(
                    bim_result,
                    exports
                )

        }




    # ==========================================
    # IFC DEBUG
    # ==========================================

    def _debug_ifc_types(
        self,
        exports
    ):

        print(
            "\n====== REAL IFC TYPE DEBUG ======"
        )

        ifc_data = exports.get(
            "ifc",
            {}
        )

        ifc_path = ifc_data.get(
            "path"
        )

        if not ifc_path:
            print(
                "⚠️ IFC PATH MISSING"
            )
            return


        if ifcopenshell is None:
            print(
                "⚠️ IFCOPEN_SHELL NOT AVAILABLE"
            )
            return


        model = ifcopenshell.open(
            ifc_path
        )


        counter = Counter()


        for entity in model.by_type(
            "IfcRoot"
        ):

            counter[
                entity.is_a()
            ] += 1


        for k,v in sorted(
            counter.items()
        ):

            print(
                k,
                ":",
                v
            )


        print(
            "TOTAL REAL IFC ENTITIES:",
            sum(counter.values())
        )



        # ----------------------------------
        # REAL IFC FILE
        # ----------------------------------

        ifc_data = exports.get(
            "ifc",
            {}
        )


        ifc_path = ifc_data.get(
            "path"
        )


        if not ifc_path:

            print(
                "⚠️ IFC PATH MISSING"
            )

            return


        if ifcopenshell is None:

            print(
                "⚠️ IFCOPENSHELL NOT AVAILABLE"
            )

            return


        model = ifcopenshell.open(
            ifc_path
        )


        print(
            "\n====== REAL IFC ENTITY DEBUG ======"
        )


        real_counter = Counter()


        for entity in model.by_type(
            "IfcRoot"
        ):

            real_counter[
                entity.is_a()
            ] += 1



        for ifc_type, count in sorted(
            real_counter.items()
        ):

            print(
                ifc_type,
                ":",
                count
            )


        print(
            "TOTAL REAL IFC ENTITIES:",
            sum(
                real_counter.values()
            )
        )



    # ==========================================
    # ELEMENT COUNT
    # ==========================================

    def _check_element_count(
        self,
        bim_result,
        exports
    ):


        bim_elements = bim_result.get(
            "bim_elements",
            []
        )


        revit = exports.get(
            "revit",
            {}
        )


        revit_elements = revit.get(
            "elements",
            []
        )


        return (

            len(bim_elements)

            ==

            len(revit_elements)

        )




    # ==========================================
    # REVIT FAMILY CHECK
    # ==========================================

    def _check_revit_mapping(
        self,
        bim_result
    ):


        bim = bim_result.get(
            "bim",
            {}
        )


        mapping = bim.get(
            "revit_mapping",
            {}
        )


        return bool(mapping)




    # ==========================================
    # IFC CHECK
    # ==========================================

    def _check_ifc(
        self,
        exports
    ):


        ifc = exports.get(
            "ifc",
            {}
        )


        return (

            ifc.get(
                "status"
            )

            ==

            "exported"

        )




    # ==========================================
    # BUILD PLAN CHECK
    # ==========================================

    def _check_build_plan(
        self,
        exports
    ):


        plan = exports.get(
            "revit_build_plan",
            {}
        )


        return (

            plan.get(
                "status"
            )

            ==

            "generated"

        )


    # ==========================================
    # REAL IFC FILE DEBUG
    # ==========================================

    def _debug_real_ifc_file(
        self,
        exports
    ):


        if "ifc" not in exports:

            print(
                "⚠️ IFC EXPORT BLOCK MISSING"
            )

            print(
                "EXPORT ERROR:",
                exports.get("error")
            )

            return False


        print("\n====== EXPORTS OBJECT DEBUG ======")

        
        print(
            "EXPORT OBJECT KEYS:",
            exports.keys()
        )

        print(
            "\n====== REAL IFC FILE DEBUG ======"
        )


        ifc = exports.get(
            "ifc",
            {}
        )


        if not ifc:

            ifc = exports.get(
                "exports",
                {}
            ).get(
                "ifc",
                {}
            )


        print(
            "IFC EXPORT KEYS:",
            ifc.keys()
        )


        ifc_path = (
            ifc.get("path")
            or
            ifc.get("file")
            or
            ifc.get("filepath")
        )


        print(
            "IFC PATH:",
            ifc_path
        )


        if not ifc_path:

            print(
                "⚠️ IFC PATH NOT FOUND"
            )

            return False



        if not os.path.exists(
            ifc_path
        ):

            print(
                "❌ IFC FILE DOES NOT EXIST:",
                ifc_path
            )

            return False



        print(
            "✅ IFC FILE EXISTS"
        )


        if ifcopenshell:

            try:

                model = ifcopenshell.open(
                    ifc_path
                )


                print(
                    "✅ IFC OPEN SUCCESS"
                )


                products = model.by_type(
                    "IfcProduct"
                )

                print(
                     "\n====== REAL IFC ENTITY TYPES ======"
                    )

                counter = Counter()

                for entity in model.by_type("IfcRoot"):

                    counter[
                        entity.is_a()
                    ] += 1


                for k,v in sorted(counter.items()):

                    print(
                        k,
                        ":",
                        v
                    )


                print(
                    "IFC PRODUCTS:",
                    len(products)
                )


                counter = Counter()


                for p in products:

                    counter[
                        p.is_a()
                    ] += 1



                print(
                    "====== REAL IFC TYPES ======"
                )


                for k,v in sorted(
                    counter.items()
                ):

                    print(
                        k,
                        ":",
                        v
                    )


                return True


            except Exception as e:

                print(
                    "❌ IFC OPEN FAILED:",
                    e
                )


        return False


    # ==========================================
    # REAL IFC QUALITY READER v2
    # ==========================================

    def _load_real_ifc(
        self,
        exports
    ):

        ifc = exports.get(
            "ifc",
            {}
        )


        ifc_path = ifc.get(
            "path"
        )


        if not ifc_path:

            print(
                "⚠️ REAL IFC PATH MISSING"
            )

            return None


        if ifcopenshell is None:

            print(
                "⚠️ IFCOPEN_SHELL NOT AVAILABLE"
            )

            return None


        try:

            model = ifcopenshell.open(
                ifc_path
            )


            print(
                "✅ REAL IFC LOADED FOR QUALITY V2"
            )


            return model


        except Exception as error:


            print(
                "❌ REAL IFC LOAD FAILED:",
                error
            )


            return None


    # ==========================================
    # QUALITY VALIDATION v2
    # ==========================================


    def _validate_ifc_structure(
        self,
        exports
    ):

        ifc_path = exports.get(
            "ifc",
            {}
        ).get(
            "path"
        )

        model = ifcopenshell.open(
            ifc_path
        )

        entities = {}

        for entity in model.by_type(
            "IfcRoot"
        ):

            entities.setdefault(
                entity.is_a(),
                []
            ).append(
                entity
            )


        required = [

            "IfcProject",
            "IfcSite",
            "IfcBuilding",
            "IfcBuildingStorey",

            "IfcWall",
            "IfcColumn",
            "IfcBeam",
            "IfcSlab",

            "IfcDoor",
            "IfcWindow"

        ]


        missing = []


        for item in required:

            if item not in entities:

                missing.append(item)


        return {

            "status":
                "passed"
                if not missing
                else "warning",

            "missing":
                missing

        }



    def _validate_geometry_quality(
        self,
        bim_result
    ):

        elements = bim_result.get(
            "bim_elements",
            []
        )


        missing_geometry = []


        for element in elements:

            if not element.get(
                "data"
            ):

                missing_geometry.append(
                    element.get(
                        "id"
                    )
                )


        return {

            "status":
                "passed"
                if not missing_geometry
                else "warning",

            "missing_geometry":
                missing_geometry

        }



    def _validate_openings(
        self,
        exports
    ):

        ifc = exports.get(
            "ifc",
            {}
        )


        model = ifc.get(
            "ifc_model",
            {}
        )


        entities = model.get(
            "entities",
            {}
        )


        doors = len(
            entities.get(
                "IfcDoor",
                []
            )
        )


        windows = len(
            entities.get(
                "IfcWindow",
                []
            )
        )


        openings = (
            doors
            +
            windows
        )


        return {

            "status":
                "passed",

            "doors":
                doors,

            "windows":
                windows,

            "expected_openings":
                openings

        }



    def _validate_placements(
        self,
        bim_result
    ):

        elements = bim_result.get(
            "bim_elements",
            []
        )


        missing = []


        for element in elements:

            data = element.get(
                "data",
                {}
            )

            print(
                "PLACEMENT DEBUG:",
                element.get("id"),
                element.get("ifc_type"),
                data
            )


            if (
                "x" not in data
                and
                "start" not in data
                and
                "location" not in data
                and
                "boundary" not in data
                and
                "corners" not in data
                and
                "profile" not in data
                and
                "points" not in data
            ):

                missing.append(
                    element.get(
                        "id"
                    )
                )


        return {

            "status":
                "passed"
                if not missing
                else "warning",

            "missing_placement":
                missing

        }


    # ==========================================
    # IFC SPATIAL STRUCTURE VALIDATION v2
    # ==========================================

    def _validate_ifc_spatial_structure(
        self,
        exports
    ):

        result = {

            "IfcProject": False,
            "IfcSite": False,
            "IfcBuilding": False,
            "IfcBuildingStorey": False,

            "status": "failed"

        }


        ifc = exports.get(
            "ifc",
            {}
        )


        ifc_path = ifc.get(
            "path"
        )


        if not ifc_path:

            return result


        if ifcopenshell is None:

            return result


        try:

            model = ifcopenshell.open(
                ifc_path
            )


            result["IfcProject"] = bool(
                model.by_type(
                    "IfcProject"
                )
            )


            result["IfcSite"] = bool(
                model.by_type(
                    "IfcSite"
                )
            )


            result["IfcBuilding"] = bool(
                model.by_type(
                    "IfcBuilding"
                )
            )


            result["IfcBuildingStorey"] = bool(
                model.by_type(
                    "IfcBuildingStorey"
                )
            )


            result["status"] = (

                "passed"

                if all(
                    result.values()
                )

                else

                "warning"

            )


        except Exception as error:


            result["error"] = str(error)


        return result


    # ==========================================
    # REAL IFC VALIDATION v2
    # ==========================================

    def _validate_real_ifc(
        self,
        exports
    ):


        result = {

            "status":
                "failed",

            "entities":
                0,

            "products":
                0

        }



        ifc = exports.get(
            "ifc",
            {}
        )


        ifc_path = ifc.get(
            "path"
        )


        if not ifc_path:


            result["error"] = (
                "IFC PATH MISSING"
            )

            return result



        if ifcopenshell is None:


            result["error"] = (
                "IFCOPENSHELL NOT AVAILABLE"
            )

            return result



        try:


            model = ifcopenshell.open(
                ifc_path
            )



            entities = model.by_type(
                "IfcRoot"
            )


            products = model.by_type(
                "IfcProduct"
            )



            result["entities"] = len(
                entities
            )


            result["products"] = len(
                products
            )



            result["status"] = (

                "passed"

                if len(entities) > 0

                else

                "warning"

            )



        except Exception as error:


            result["error"] = str(
                error
            )



        return result



    # ==========================================
    # IFC RELATIONSHIP VALIDATION v2
    # ==========================================

    def _validate_relationships(
        self,
        exports
    ):


        result = {


            "IfcRelVoidsElement":
                0,


            "IfcRelFillsElement":
                0,


            "status":
                "failed"

        }



        ifc = exports.get(
            "ifc",
            {}
        )


        ifc_path = ifc.get(
            "path"
        )


        if not ifc_path:

            return result



        if ifcopenshell is None:

            return result



        try:


            model = ifcopenshell.open(
                ifc_path
            )



            voids = model.by_type(
                "IfcRelVoidsElement"
            )


            fills = model.by_type(
                "IfcRelFillsElement"
            )



            result["IfcRelVoidsElement"] = len(
                voids
            )


            result["IfcRelFillsElement"] = len(
                fills
            )



            result["status"] = (

                "passed"

                if len(voids) > 0
                and
                len(fills) > 0

                else

                "warning"

            )



        except Exception as error:


            result["error"] = str(
                error
            )



        return result


    # ==========================================
    # IFC OPENING RELATIONSHIP DEBUG
    # ==========================================

    def _debug_opening_relationships(
        self,
        exports
    ):

        print(
            "\n====== IFC OPENING RELATIONSHIP DEBUG ======"
        )


        ifc = exports.get(
            "ifc",
            {}
        )


        ifc_path = ifc.get(
            "path"
        )


        if not ifc_path:

            print(
                "⚠️ IFC PATH MISSING"
            )

            return


        if ifcopenshell is None:

            print(
                "⚠️ IFCOPEN_SHELL NOT AVAILABLE"
            )

            return


        model = ifcopenshell.open(
            ifc_path
        )


        walls = model.by_type(
            "IfcWall"
        )


        doors = model.by_type(
            "IfcDoor"
        )


        windows = model.by_type(
            "IfcWindow"
        )


        voids = model.by_type(
            "IfcRelVoidsElement"
        )


        fills = model.by_type(
            "IfcRelFillsElement"
        )


        print(
            "WALL COUNT:",
            len(walls)
        )


        print(
            "DOOR COUNT:",
            len(doors)
        )


        print(
            "WINDOW COUNT:",
            len(windows)
        )


        print(
            "VOID RELATION COUNT:",
            len(voids)
        )


        print(
            "FILL RELATION COUNT:",
            len(fills)
        )


        print(
            "====== OPENING RELATION STATUS ======"
        )


        if len(voids) == len(fills):

            print(
                "✅ OPENING RELATIONSHIPS MATCH"
            )

        else:

            print(
                "⚠️ OPENING RELATIONSHIP MISMATCH"
            )


    def _debug_spatial_containment(
        self,
        exports
    ):

        print(
            "\n====== IFC SPATIAL CONTAINMENT DEBUG ======"
        )

        ifc = exports.get(
            "ifc",
            {}
        )

        ifc_path = ifc.get(
            "path"
        )

        if not ifc_path:
            print("IFC PATH MISSING")
            return


        if ifcopenshell is None:
            print("IFCOPENSHELL NOT AVAILABLE")
            return


        model = ifcopenshell.open(
            ifc_path
        )


        relations = model.by_type(
            "IfcRelContainedInSpatialStructure"
        )


        print(
            "CONTAINMENT RELATIONS:",
            len(relations)
        )


        for rel in relations:

            print(
                "RELATION:",
                rel.GlobalId
            )


            structure = rel.RelatingStructure


            print(
                "STOREY:",
                structure.is_a(),
                structure.Name
            )


            elements = rel.RelatedElements


            print(
                "ELEMENT COUNT:",
                len(elements)
            )


            counter = Counter()


            for e in elements:

                counter[
                    e.is_a()
                ] += 1


            print(
                counter
            )


    # ==========================================
    # STATISTICS
    # ==========================================

    def _statistics(
        self,
        bim_result,
        exports
    ):


        return {


            "bim_elements":

                len(
                    bim_result.get(
                        "bim_elements",
                        []
                    )
                ),



            "revit_elements":

                len(
                    exports.get(
                        "revit",
                        {}
                    ).get(
                        "elements",
                        []
                    )
                ),



            "build_plan_elements":

                exports.get(
                    "revit_build_plan",
                    {}
                ).get(
                    "elements",
                    0
                )

        }