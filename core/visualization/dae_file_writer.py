import os
import xml.etree.ElementTree as ET


class DAEFileWriter:

    VERSION = "1.1"


    def __init__(self):

        print(
            f"🎬 DAE File Writer v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # EXPORT
    # ==================================================

    def export(
        self,
        assembly_model,
        filename="architectos_model.dae",
        output_dir="exports"
    ):

        os.makedirs(
            output_dir,
            exist_ok=True
        )


        path = os.path.join(
            output_dir,
            filename
        )


        root = self._build_collada(
            assembly_model
        )


        tree = ET.ElementTree(
            root
        )


        tree.write(
            path,
            encoding="utf-8",
            xml_declaration=True
        )


        return {

            "status":
                "exported",

            "format":
                "DAE",

            "version":
                "1.4.1",

            "file":
                path,

            "engine":
                f"DAEFileWriter_v{self.VERSION}"

        }



    # ==================================================
    # COLLADA
    # ==================================================

    def _build_collada(
        self,
        model
    ):

        root = ET.Element(
            "COLLADA",
            {
                "xmlns":
                "http://www.collada.org/2005/11/COLLADASchema",

                "version":
                "1.4.1"
            }
        )


        asset = ET.SubElement(
            root,
            "asset"
        )


        ET.SubElement(
            asset,
            "unit",
            {
                "name":"meter",
                "meter":"1"
            }
        )


        geometries = ET.SubElement(
            root,
            "library_geometries"
        )


        elements = model.get(
            "elements",
            {}
        )


        counter = 0


        # ROOMS

        for room in elements.get(
            "rooms",
            []
        ):

            self._add_box_geometry(
                geometries,
                f"room_{counter}",
                room["geometry"]
            )

            counter += 1



        # WALLS

        for wall in elements.get(
            "walls",
            []
        ):

            for w in wall.get(
                "walls",
                []
            ):

                self._add_wall_geometry(
                    geometries,
                    f"wall_{counter}",
                    w
                )

                counter += 1



        scenes = ET.SubElement(
            root,
            "library_visual_scenes"
        )


        ET.SubElement(
            scenes,
            "visual_scene",
            {
                "id":
                "ArchitectOSScene"
            }
        )


        ET.SubElement(
            root,
            "scene"
        )


        return root



    # ==================================================
    # BOX GEOMETRY
    # ==================================================

    def _add_box_geometry(
        self,
        parent,
        name,
        geo
    ):


        width = geo.get(
            "width",
            geo.get("w",3)
        )


        depth = geo.get(
            "depth",
            geo.get("h",3)
        )


        height = 3


        vertices = [

            (0,0,0),
            (width,0,0),
            (width,depth,0),
            (0,depth,0),

            (0,0,height),
            (width,0,height),
            (width,depth,height),
            (0,depth,height)

        ]


        faces = [

            (0,1,2),
            (0,2,3),

            (4,6,5),
            (4,7,6),

            (0,4,5),
            (0,5,1),

            (1,5,6),
            (1,6,2),

            (2,6,7),
            (2,7,3),

            (3,7,4),
            (3,4,0)

        ]


        self._mesh(
            parent,
            name,
            vertices,
            faces
        )



    # ==================================================
    # WALL GEOMETRY
    # ==================================================

    def _add_wall_geometry(
        self,
        parent,
        name,
        wall
    ):


        length = wall.get(
            "length",
            3
        )


        height = 3

        thickness = 0.2


        vertices = [

            (0,0,0),
            (length,0,0),
            (length,thickness,0),
            (0,thickness,0),

            (0,0,height),
            (length,0,height),
            (length,thickness,height),
            (0,thickness,height)

        ]


        faces = [

            (0,1,2),
            (0,2,3),

            (4,6,5),
            (4,7,6),

            (0,4,5),
            (0,5,1),

            (1,5,6),
            (1,6,2),

            (2,6,7),
            (2,7,3),

            (3,7,4),
            (3,4,0)

        ]


        self._mesh(
            parent,
            name,
            vertices,
            faces
        )



    # ==================================================
    # MESH WRITER
    # ==================================================

    def _mesh(
        self,
        parent,
        name,
        vertices,
        faces
    ):


        geometry = ET.SubElement(
            parent,
            "geometry",
            {
                "id":name
            }
        )


        mesh = ET.SubElement(
            geometry,
            "mesh"
        )


        source = ET.SubElement(
            mesh,
            "source",
            {
                "id":
                f"{name}_positions"
            }
        )


        array = ET.SubElement(
            source,
            "float_array",
            {
                "id":
                f"{name}_array",

                "count":
                str(len(vertices)*3)
            }
        )


        array.text = " ".join(

            str(v)

            for vertex in vertices

            for v in vertex

        )


        ET.SubElement(
            mesh,
            "triangles",
            {
                "count":
                str(len(faces))
            }
        )