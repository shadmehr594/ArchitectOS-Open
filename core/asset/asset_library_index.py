class AssetLibraryIndex:


    VERSION="1.0"



    def __init__(self):

        self.assets = {


            "sofa":

            [

                {

                "id":
                "sofa_classic_001",

                "style":
                "classical",

                "file":
                "sofa_classic.ifc"

                },

            ],



            "window":

            [

                {

                "id":
                "roman_window_001",

                "style":
                "roman",

                "file":
                "roman_window.ifc"

                }

            ],



            "column":

            [

                {

                "id":
                "roman_column_001",

                "style":
                "roman",

                "file":
                "column.ifc"

                }

            ]

        }



    def search(
        self,
        asset_type,
        style=None
    ):


        result = self.assets.get(
            asset_type,
            []
        )


        if style:

            result = [

                x for x in result

                if x.get("style")
                == style

            ]


        return result