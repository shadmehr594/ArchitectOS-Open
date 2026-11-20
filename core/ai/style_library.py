# ==========================================================
# ArchitectOS Style Library v69
# Architectural Knowledge Base
# ==========================================================


STYLE_LIBRARY = {

    # ======================================================
    # MODERN
    # ======================================================

    "modern": {

        "materials": [

            "glass curtain wall",
            "white concrete",
            "natural stone",
            "black aluminum"

        ],

        "design_language": [

            "clean lines",
            "minimal detailing",
            "large glazing",
            "simple geometry",
            "premium architecture"

        ],

        "lighting": [

            "natural daylight",
            "soft shadows"

        ],

        "negative": [

            "low quality",
            "crooked columns",
            "distorted facade",
            "warped geometry",
            "extra windows",
            "extra floors"

        ],

        "runtime": {

            "steps": 32,
            "cfg": 7.5,
            "denoise": 0.55

        }

    },

    # ======================================================
    # MINIMAL
    # ======================================================

    "minimal": {

        "materials": [

            "white concrete",
            "glass",
            "smooth plaster"

        ],

        "design_language": [

            "minimal",
            "simple",
            "clean facade",
            "few materials"

        ],

        "lighting": [

            "soft daylight"

        ],

        "negative": [

            "ornaments",
            "decorations",
            "complex geometry"

        ],

        "runtime": {

            "steps": 30,
            "cfg": 7.0,
            "denoise": 0.50

        }

    },

    # ======================================================
    # CLASSIC
    # ======================================================

    "classic": {

        "materials": [

            "travertine",
            "marble",
            "stone"

        ],

        "design_language": [

            "columns",
            "arches",
            "symmetry",
            "luxury"

        ],

        "lighting": [

            "golden daylight"

        ],

        "negative": [

            "modern glass curtain wall",
            "industrial facade"

        ],

        "runtime": {

            "steps": 30,
            "cfg": 7.2,
            "denoise": 0.50

        }

    },

    # ======================================================
    # LUXURY
    # ======================================================

    "luxury": {

        "materials": [

            "premium marble",
            "glass",
            "bronze metal",
            "natural stone"

        ],

        "design_language": [

            "luxury",
            "high-end",
            "premium detailing",
            "grand entrance"

        ],

        "lighting": [

            "cinematic daylight"

        ],

        "negative": [

            "cheap materials",
            "unfinished"

        ],

        "runtime": {

            "steps": 36,
            "cfg": 8.0,
            "denoise": 0.60

        }

    },

    # ======================================================
    # INDUSTRIAL
    # ======================================================

    "industrial": {

        "materials": [

            "raw concrete",
            "steel",
            "black metal",
            "glass"

        ],

        "design_language": [

            "industrial",
            "exposed steel",
            "raw materials"

        ],

        "lighting": [

            "dramatic daylight"

        ],

        "negative": [

            "classical ornament"

        ],

        "runtime": {

            "steps": 32,
            "cfg": 7.3,
            "denoise": 0.55

        }

    }

}