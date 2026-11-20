# ==================================================
# ArchitectOS Asset Resolver v2.1
# BIM -> Asset Intelligence Bridge
# ==================================================

from core.asset.asset_contract import AssetContract
from core.asset.asset_library_index import AssetLibraryIndex



class AssetResolver:


    VERSION = "2.1"



    # ==================================================
    # REAL ASSET TYPES
    # ==================================================

    ASSET_TYPES = {


        "door",
        "window",
        "stair",
        "railing",
        "roof",
        "furniture",
        "facade",
        "lighting",
        "sanitary",
        "kitchen"


    }



    IFC_ASSET_MAP = {


        "IfcDoor":
        "door",


        "IfcWindow":
        "window",


        "IfcStair":
        "stair",


        "IfcRailing":
        "railing",


        "IfcRoof":
        "roof",


        "IfcFurniture":
        "furniture"


    }



    def __init__(self):


        print(
            "🧩 Asset Resolver v2.1 ACTIVE"
        )


        self.contract = AssetContract()

        self.library = AssetLibraryIndex()





    # ==================================================
    # RESOLVE
    # ==================================================

    def resolve(
        self,
        requests
    ):


        print(
            "\n====== ASSET RESOLVER DEBUG ======"
        )


        elements = []



        if not isinstance(
            requests,
            list
        ):


            print(
                "INVALID INPUT"
            )


            return elements





        print(
            "REQUEST COUNT:",
            len(requests)
        )



        counter = 1


        skipped = 0




        for request in requests:


            ifc_type = request.get(
                "ifc_type"
            )
 

            allowed_assets = [

                "IfcDoor",
                "IfcWindow",
                "IfcStair",
                "IfcRailing",
                "IfcFurniture",
                "IfcRoof"

            ]


            if ifc_type not in allowed_assets:

                print(
                    "SKIPPED BIM GEOMETRY:",
                    request.get("id"),
                    ifc_type
                )

                continue



            if not isinstance(
                request,
                dict
            ):

                continue




            asset_type = self._resolve_type(
                request
            )



            # ----------------------------------
            # FILTER BIM GEOMETRY
            # ----------------------------------

            if asset_type not in self.ASSET_TYPES:


                skipped += 1


                continue




            style = self._resolve_style(
                request
            )



            print(
                "ASSET REQUEST:",
                asset_type,
                style
            )





            # ----------------------------------
            # LIBRARY SEARCH
            # ----------------------------------

            try:


                matches = self.library.search(

                    asset_type,

                    style

                )


            except Exception as error:


                print(
                    "LIBRARY ERROR:",
                    error
                )


                matches = []





            # ----------------------------------
            # CREATE CONTRACT
            # ----------------------------------

            asset = self.contract.create(

                asset_type,

                style

            )



            if not isinstance(
                asset,
                dict
            ):


                asset = {}




            asset.setdefault(

                "asset",

                {}

            )





            if matches:



                asset["asset"]["reference"] = (

                    matches[0].get(
                        "file"
                    )

                )


                asset["asset"]["library_match"] = (

                    matches[0]

                )


            else:



                asset["asset"]["reference"] = None


                asset["asset"]["library_match"] = None





            asset["id"] = (

                f"asset_{counter:03}"

            )



            asset["source"] = request




            elements.append(
                asset
            )



            counter += 1






        print(
            "SKIPPED BIM GEOMETRY:",
            skipped
        )


        print(
            "ASSET ELEMENT COUNT:",
            len(elements)
        )



        return elements







    # ==================================================
    # TYPE RESOLUTION
    # ==================================================

    def _resolve_type(
        self,
        request
    ):



        raw_type = request.get(
            "type"
        )


        if raw_type in self.ASSET_TYPES:


            return raw_type




        ifc_type = request.get(

            "ifc_type",

            ""

        )



        return self.IFC_ASSET_MAP.get(

            ifc_type,

            "generic"

        )







    # ==================================================
    # STYLE RESOLUTION
    # ==================================================

    def _resolve_style(
        self,
        request
    ):



        explicit = request.get(
            "style"
        )


        if explicit:


            return explicit





        semantic = request.get(

            "semantic_type",

            ""

        )



        role = request.get(

            "functional_role",

            ""

        )




        # WINDOWS

        if semantic == "window":


            return "classical"




        # DOORS

        if role == "access":


            return "classical"




        # ROOF

        if semantic == "roof":


            return "classical_roman"




        return "generic"