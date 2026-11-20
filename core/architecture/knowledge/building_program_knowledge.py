class BuildingProgramKnowledge:

    VERSION = "1.2"


    def __init__(self):

        print(
            "🏛 BUILDING PROGRAM KNOWLEDGE v1.2 ONLINE"
        )


        self.programs = {

            "residential": {


                "required_spaces": [

                    {
                        "name": "entrance",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 3,
                            "preferred_area": 5,
                            "minimum_width": 1.5,
                            "minimum_depth": 1.8
                        }
                    },

                    {
                        "name": "living",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 16,
                            "preferred_area": 24,
                            "minimum_width": 3.5,
                            "minimum_depth": 4
                        },

                        "environmental_requirements": {
                            "natural_light": True,
                            "natural_ventilation": True,
                            "orientation_preference": [
                                "south",
                                "east"
                            ]
                        },

                        "privacy_requirements": {
                            "level": "medium"
                        },

                        "access_requirements": {
                            "user_type": [
                                "family"
                            ]
                        }
                        
                    },

                    {
                        "name": "kitchen",
                        "zone": "service",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 7,
                            "preferred_area": 10,
                            "minimum_width": 2.4,
                            "minimum_depth": 2.8
                        }
                    },

                    {
                        "name": "bedroom",
                        "zone": "private",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 10,
                            "preferred_area": 14,
                            "minimum_width": 3,
                            "minimum_depth": 3.2
                        }
                    },

                    {
                        "name": "bathroom",
                        "zone": "private",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 1.8,
                            "minimum_depth": 2.2
                        }
                    },

                    {
                        "name": "corridor",
                        "zone": "circulation",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 3,
                            "preferred_area": 5,
                            "minimum_width": 1.2,
                            "preferred_width": 1.5,
                            "maximum_width": 2.0
                        }
                    }

                ],


                "optional_spaces": [],


                "relationships": [

                    {
                        "from": "entrance",
                        "to": "corridor",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "living",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "bedroom",
                        "type": "direct_connection"
                    },

                    {
                        "from": "living",
                        "to": "kitchen",
                        "type": "adjacent"
                    },

                    {
                        "from": "bedroom",
                        "to": "bathroom",
                        "type": "private_connection"
                    }

                ]

            },

            "villa": {


                "required_spaces": [

                    {
                        "name": "entrance",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 2,
                            "minimum_depth": 2
                        }
                    },

                    {
                        "name": "living",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 20,
                            "preferred_area": 30,
                            "minimum_width": 4,
                            "minimum_depth": 4
                        }
                    },

                    {
                        "name": "dining",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 10,
                            "preferred_area": 14,
                            "minimum_width": 3,
                            "minimum_depth": 3
                        }
                    },

                    {
                        "name": "kitchen",
                        "zone": "service",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 8,
                            "preferred_area": 12,
                            "minimum_width": 2.5,
                            "minimum_depth": 3
                        }
                    },

                    {
                        "name": "guest_wc",
                        "zone": "service",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 2.5,
                            "preferred_area": 4,
                            "minimum_width": 1.5,
                            "minimum_depth": 1.8
                        }
                    },

                    {
                        "name": "stairs",
                        "zone": "circulation",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 5,
                            "preferred_area": 8,
                            "minimum_width": 1.2,
                            "minimum_depth": 4
                        },

                        "connects": [
                            "ground_floor",
                            "upper_floor"
                        ],

                        "vertical_connection": {
                            "type": "stairs",
                            "status": "explicit",
                            "connects": [
                                "ground_floor",
                                "upper_floor"
                            ]
                        },

                        "protected_zone": True
                    
                    },

                    {
                        "name": "corridor",
                        "zone": "circulation",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 3,
                            "preferred_area": 5,
                            "minimum_width": 1.2,
                            "preferred_width": 1.5,
                            "maximum_width": 2.0
                        }
                    },

                    {
                        "name": "master_bedroom",
                        "zone": "private",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 14,
                            "preferred_area": 20,
                            "minimum_width": 3.2,
                            "minimum_depth": 4
                        }
                    },

                    {
                        "name": "corridor",
                        "zone": "circulation",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 3,
                            "preferred_area": 5,
                            "minimum_width": 1.2,
                            "preferred_width": 1.5,
                            "maximum_width": 2.0
                        }
                    },

                    {
                        "name": "bedroom",
                        "zone": "private",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 10,
                            "preferred_area": 14,
                            "minimum_width": 3,
                            "minimum_depth": 3.2
                        }
                    },

                    {
                        "name": "bathroom",
                        "zone": "private",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 1.8,
                            "minimum_depth": 2.2
                        }
                    }

                ],


                "optional_spaces": [

                    {
                        "name": "terrace",
                        "zone": "external",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 8,
                            "preferred_area": 15,
                            "minimum_width": 2,
                            "minimum_depth": 3
                        }
                    },

                    {
                        "name": "balcony",
                        "zone": "external",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 8,
                            "minimum_width": 1.5,
                            "minimum_depth": 2
                        }
                    },

                    {
                        "name": "garden",
                        "zone": "external",
                        "floor": "site_level",

                        "dimensional_requirements": {
                            "minimum_area": 20,
                            "preferred_area": 40,
                            "minimum_width": 4,
                            "minimum_depth": 5
                        }
                    },

                    {
                        "name": "parking",
                        "zone": "external",
                        "floor": "site_level",

                        "dimensional_requirements": {
                            "minimum_area": 12,
                            "preferred_area": 15,
                            "minimum_width": 2.5,
                            "minimum_depth": 5
                        }
                    }

                ],


                "relationships": [

                    {
                        "from": "living",
                        "to": "terrace",
                        "type": "direct_connection"
                    },

                    {
                        "from": "living",
                        "to": "garden",
                        "type": "visual_connection"
                    },

                    {
                        "from": "kitchen",
                        "to": "dining",
                        "type": "adjacent"
                    },

                    {
                        "from": "living",
                        "to": "dining",
                        "type": "adjacent"
                    },

                    {
                        "from": "entrance",
                        "to": "corridor",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "stairs",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "living",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "guest_wc",
                        "type": "adjacent"
                    },

                    {
                        "from": "corridor",
                        "to": "master_bedroom",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "bedroom",
                        "type": "direct_connection"
                    },

                    {
                        "from": "master_bedroom",
                        "to": "bathroom",
                        "type": "private_connection"
                    }

                ],

                "floor_intelligence": {

                        "ground_floor": {

                            "role":
                                "public_access_level",

                            "height":
                                3.2,

                            "height_source":
                                "building_program_knowledge",

                            "allowed_zones": [

                                "public",
                                "service",
                                "circulation",
                                "external"

                            ],

                            "preferred_spaces": [

                                "entrance",
                                "living",
                                "dining",
                                "kitchen",
                                "stairs"

                            ],

                            "constraints": {

                                "requires_access":
                                    True,

                                "vehicle_access_allowed":
                                    True

                            }

                        },


                        "upper_floor": {

                            "role":
                                "private_level",

                            "height":
                                3.2,


                            "height_source":
                                "building_program_knowledge",

                            "allowed_zones": [

                                "private",
                                "circulation"

                            ],

                            "preferred_spaces": [

                                "master_bedroom",
                                "bedroom",
                                "bathroom"

                            ],

                            "constraints": {

                                "requires_vertical_connection":
                                    True,

                                "privacy_priority":
                                    "high"

                            }

                        },


                        "roof_level": {

                            "role":
                                "external_extension",

                            "allowed_zones": [

                                "external"

                            ],

                            "preferred_spaces": [

                                "terrace",
                                "balcony"

                            ]

                        }

                    }

                },


            "commercial": {
                "required_spaces": [

                    {
                        "name": "entrance",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 8,
                            "minimum_width": 2,
                            "minimum_depth": 2
                        }
                    },

                    {
                        "name": "retail",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 20,
                            "preferred_area": 35,
                            "minimum_width": 4,
                            "minimum_depth": 5
                        }
                    },

                    {
                        "name": "corridor",
                        "zone": "circulation",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 1.4,
                            "preferred_width": 1.8,
                            "maximum_width": 2.4
                        }
                    },

                    {
                        "name": "service_core",
                        "zone": "service",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 6,
                            "preferred_area": 10,
                            "minimum_width": 2,
                            "minimum_depth": 3
                        },

                        "protected_zone":
                            True,

                        "connects": [

                            "ground_floor",
                            "upper_floor"

                        ],

                        "vertical_connection": {

                            "type":
                                "service_core",

                            "status":
                                "explicit",

                            "connects": [

                                "ground_floor",
                                "upper_floor"

                            ]

                        }
                    },

                    {
                        "name": "bathroom",
                        "zone": "service",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 1.8,
                            "minimum_depth": 2.2
                        }
                    },

                    {
                        "name": "office_room",
                        "zone": "private",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 10,
                            "preferred_area": 16,
                            "minimum_width": 3,
                            "minimum_depth": 3
                        }
                    },

                    {
                        "name": "corridor",
                        "zone": "circulation",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 1.4,
                            "preferred_width": 1.8,
                            "maximum_width": 2.4
                        }
                    },

                    {
                        "name": "bathroom",
                        "zone": "service",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 1.8,
                            "minimum_depth": 2.2
                        }
                    }

                ],

                "optional_spaces": [],

                "relationships": [

                    {
                        "from": "entrance",
                        "to": "retail",
                        "type": "direct_connection"
                    },

                    {
                        "from": "entrance",
                        "to": "corridor",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "service_core",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "bathroom",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "office_room",
                        "type": "direct_connection"
                    }

                ],

                "floor_intelligence": {

                    "ground_floor": {

                        "role":
                            "commercial_access_level",

                        "allowed_zones": [

                            "public",
                            "service",
                            "circulation"

                        ],

                        "preferred_spaces": [

                            "entrance",
                            "retail",
                            "service_core",
                            "bathroom"

                        ],

                        "constraints": {

                            "requires_access":
                                True,

                            "public_access_priority":
                                "high",

                            "service_access_required":
                                True

                        }

                    },


                    "upper_floor": {

                        "role":
                            "commercial_work_level",

                        "allowed_zones": [

                            "private",
                            "service",
                            "circulation"

                        ],

                        "preferred_spaces": [

                            "office_room",
                            "bathroom",
                            "corridor"

                        ],

                        "constraints": {

                            "requires_vertical_connection":
                                True,

                            "workplace_priority":
                                "high",

                            "public_access":
                                "controlled"

                        }

                    }

                }

            },

            "parking": {

                "required_spaces": [

                    {
                        "name": "parking",
                        "zone": "service",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 12,
                            "preferred_area": 15,
                            "minimum_width": 2.5,
                            "minimum_depth": 5
                        },

                        "protected_zone": True,

                        "placement_scope":
                            "vehicle_access",

                        "access_requirement":
                            "vehicle_access_required"
                    },

                    {
                        "name": "service_core",
                        "zone": "circulation",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 5,
                            "preferred_area": 8,
                            "minimum_width": 1.5,
                            "minimum_depth": 3
                        },

                        "protected_zone": True
                    }

                ],

                "optional_spaces": [],

                "relationships": [

                    {
                        "from": "parking",
                        "to": "service_core",
                        "type": "direct_connection"
                    }

                ]

            },

            "mixed_use": {

                "required_spaces": [

                    {
                        "name": "entrance",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 8,
                            "minimum_width": 2,
                            "minimum_depth": 2
                        }
                    },

                    {
                        "name": "retail",
                        "zone": "public",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 20,
                            "preferred_area": 35,
                            "minimum_width": 4,
                            "minimum_depth": 5
                        }
                    },

                    {
                        "name": "corridor",
                        "zone": "circulation",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 1.4,
                            "preferred_width": 1.8,
                            "maximum_width": 2.4
                        },

                        "protected_zone": True
                    },

                    {
                        "name": "service_core",
                        "zone": "circulation",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 6,
                            "preferred_area": 10,
                            "minimum_width": 2,
                            "minimum_depth": 3
                        },

                        "protected_zone": True
                    },

                    {
                        "name": "living",
                        "zone": "public",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 16,
                            "preferred_area": 24,
                            "minimum_width": 3.5,
                            "minimum_depth": 4
                        }
                    },

                    {
                        "name": "kitchen",
                        "zone": "service",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 7,
                            "preferred_area": 10,
                            "minimum_width": 2.4,
                            "minimum_depth": 2.8
                        }
                    },

                    {
                        "name": "bedroom",
                        "zone": "private",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 10,
                            "preferred_area": 14,
                            "minimum_width": 3,
                            "minimum_depth": 3.2
                        }
                    },

                    {
                        "name": "bathroom",
                        "zone": "private",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 4,
                            "preferred_area": 6,
                            "minimum_width": 1.8,
                            "minimum_depth": 2.2
                        }
                    },

                    {
                        "name": "corridor",
                        "zone": "circulation",
                        "floor": "upper_floor",

                        "dimensional_requirements": {
                            "minimum_area": 3,
                            "preferred_area": 5,
                            "minimum_width": 1.2,
                            "preferred_width": 1.5,
                            "maximum_width": 2.0
                        },

                        "protected_zone": True
                    }

                ],

                "optional_spaces": [

                    {
                        "name": "parking",
                        "zone": "service",
                        "floor": "ground_floor",

                        "dimensional_requirements": {
                            "minimum_area": 12,
                            "preferred_area": 15,
                            "minimum_width": 2.5,
                            "minimum_depth": 5
                        },

                        "protected_zone": True,

                        "placement_scope":
                            "vehicle_access",

                        "access_requirement":
                            "vehicle_access_required"
                    }

                ],

                "relationships": [

                    {
                        "from": "entrance",
                        "to": "retail",
                        "type": "direct_connection"
                    },

                    {
                        "from": "entrance",
                        "to": "corridor",
                        "type": "direct_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "service_core",
                        "type": "direct_connection"
                    },

                    {
                        "from": "service_core",
                        "to": "corridor",
                        "type": "vertical_connection"
                    },

                    {
                        "from": "corridor",
                        "to": "living",
                        "type": "direct_connection"
                    },

                    {
                        "from": "living",
                        "to": "kitchen",
                        "type": "adjacent"
                    },

                    {
                        "from": "corridor",
                        "to": "bedroom",
                        "type": "direct_connection"
                    },

                    {
                        "from": "bedroom",
                        "to": "bathroom",
                        "type": "private_connection"
                    },

                    {
                        "from": "parking",
                        "to": "service_core",
                        "type": "direct_connection"
                    }

                ]

            },

            "cinema": {


                "required_spaces": [

                    {
                        "name": "entrance",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "ticketing",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "foyer",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "audience_circulation",
                        "zone": "circulation",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "auditorium",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "projection_room",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "egress_circulation",
                        "zone": "circulation",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    }

                ],


                "optional_spaces": [],


                "relationships": [

                    {
                        "from": "entrance",
                        "to": "ticketing",
                        "type": "direct_connection"
                    },

                    {
                        "from": "ticketing",
                        "to": "foyer",
                        "type": "direct_connection"
                    },

                    {
                        "from": "foyer",
                        "to": "audience_circulation",
                        "type": "direct_connection"
                    },

                    {
                        "from": "audience_circulation",
                        "to": "auditorium",
                        "type": "direct_connection"
                    },

                    {
                        "from": "projection_room",
                        "to": "auditorium",
                        "type": "technical_connection"
                    },

                    {
                        "from": "auditorium",
                        "to": "egress_circulation",
                        "type": "egress_connection"
                    }

                ]

            },

            "auditorium": {


                "required_spaces": [

                    {
                        "name": "entrance",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "ticketing",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "foyer",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "audience_circulation",
                        "zone": "circulation",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "auditorium",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "stage",
                        "zone": "performance",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "backstage",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "performer_entrance",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "performer_circulation",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "egress_circulation",
                        "zone": "circulation",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    }

                ],


                "optional_spaces": [

                    {
                        "name": "control_room",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "service_access",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    }

                ],


                "relationships": [

                    {
                        "from": "entrance",
                        "to": "ticketing",
                        "type": "direct_connection"
                    },

                    {
                        "from": "ticketing",
                        "to": "foyer",
                        "type": "direct_connection"
                    },

                    {
                        "from": "foyer",
                        "to": "audience_circulation",
                        "type": "direct_connection"
                    },

                    {
                        "from": "audience_circulation",
                        "to": "auditorium",
                        "type": "direct_connection"
                    },

                    {
                        "from": "auditorium",
                        "to": "stage",
                        "type": "performance_connection"
                    },

                    {
                        "from": "stage",
                        "to": "backstage",
                        "type": "performer_connection"
                    },

                    {
                        "from": "performer_entrance",
                        "to": "performer_circulation",
                        "type": "staff_connection"
                    },

                    {
                        "from": "performer_circulation",
                        "to": "backstage",
                        "type": "staff_connection"
                    },

                    {
                        "from": "performer_circulation",
                        "to": "stage",
                        "type": "performer_connection"
                    },

                    {
                        "from": "auditorium",
                        "to": "egress_circulation",
                        "type": "egress_connection"
                    },

                    {
                        "from": "control_room",
                        "to": "auditorium",
                        "type": "technical_connection"
                    },

                    {
                        "from": "service_access",
                        "to": "backstage",
                        "type": "service_connection"
                    }

                ]

            },

            "amphitheater": {


                "required_spaces": [

                    {
                        "name": "entrance",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "foyer",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "audience_circulation",
                        "zone": "circulation",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "audience_area",
                        "zone": "external",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "stage",
                        "zone": "performance",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "backstage",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "performer_entrance",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "performer_circulation",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "egress_circulation",
                        "zone": "circulation",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    }

                ],


                "optional_spaces": [

                    {
                        "name": "ticketing",
                        "zone": "public",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "control_room",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    },

                    {
                        "name": "service_access",
                        "zone": "service",
                        "floor": "ground_floor",
                        "dimensional_requirements": {}
                    }

                ],


                "relationships": [

                    {
                        "from": "entrance",
                        "to": "foyer",
                        "type": "direct_connection"
                    },

                    {
                        "from": "foyer",
                        "to": "audience_circulation",
                        "type": "direct_connection"
                    },

                    {
                        "from": "audience_circulation",
                        "to": "audience_area",
                        "type": "direct_connection"
                    },

                    {
                        "from": "audience_area",
                        "to": "stage",
                        "type": "performance_connection"
                    },

                    {
                        "from": "audience_area",
                        "to": "egress_circulation",
                        "type": "egress_connection"
                    },

                    {
                        "from": "stage",
                        "to": "backstage",
                        "type": "performer_connection"
                    },

                    {
                        "from": "performer_entrance",
                        "to": "performer_circulation",
                        "type": "staff_connection"
                    },

                    {
                        "from": "performer_circulation",
                        "to": "backstage",
                        "type": "staff_connection"
                    },

                    {
                        "from": "performer_circulation",
                        "to": "stage",
                        "type": "performer_connection"
                    },

                    {
                        "from": "control_room",
                        "to": "audience_area",
                        "type": "technical_connection"
                    },

                    {
                        "from": "service_access",
                        "to": "backstage",
                        "type": "service_connection"
                    },

                    {
                        "from": "ticketing",
                        "to": "foyer",
                        "type": "direct_connection"
                    }

                ]

            }

        }

    def _enrich_floor_layer(
        self,
        program
    ):

        floor_intelligence = program.get(
            "floor_intelligence",
            {}
        )


        spaces = (

            program.get(
                "required_spaces",
                []
            )

            +

            program.get(
                "optional_spaces",
                []
            )

        )


        for space in spaces:

            floor = space.get(
                "floor"
            )


            if floor in floor_intelligence:

                space.setdefault(
                    "floor_constraints",
                    {}
                )


                space[
                    "floor_constraints"
                ].update(

                    floor_intelligence[
                        floor
                    ]

                )


        return program


    def _clone_program(
        self,
        program
    ):
        import copy

        return copy.deepcopy(
            program
        )


    def _enrich_semantic_layer(
        self,
        program
    ):

        space_intents = {

            "living": {

                "privacy_level": "medium",

                "daylight_priority": "high",

                "natural_ventilation": True,

                "noise_sensitivity": "medium",

                "placement_priority": "public_view",

                "preferred_edge_role": "open_edge"

            },


            "bedroom": {

                "privacy_level": "high",

                "daylight_priority": "high",

                "natural_ventilation": True,

                "noise_sensitivity": "high",

                "placement_priority": "quiet_zone",

                "preferred_edge_role": "privacy_edge"

            },


            "master_bedroom": {

                "privacy_level": "very_high",

                "daylight_priority": "high",

                "natural_ventilation": True,

                "noise_sensitivity": "high",

                "placement_priority": "quiet_zone",

                "preferred_edge_role": "privacy_edge"

            },


            "kitchen": {

                "privacy_level": "low",

                "service_priority": "high",

                "natural_ventilation": True,

                "placement_priority": "service_zone",

                "adjacency_priority": [

                    "living",

                    "dining"

                ]

            },


            "bathroom": {

                "privacy_level": "high",

                "service_priority": "high",

                "placement_priority": "private_core"

            },


            "corridor": {

                "privacy_level": "low",

                "circulation_priority": "high",

                "placement_priority": "connector"

            },


            "stairs": {

                "vertical_role": "primary",

                "placement_priority": "protected_core"

            },


            "parking": {

                "protected_zone":
                    True,

                "vehicle_access_priority":
                    "high",

                "placement_priority":
                    "vehicle_access"

            },


            "office_room": {

                "privacy_level":
                    "medium",

                "daylight_priority":
                    "high",

                "natural_ventilation":
                    True,

                "noise_sensitivity":
                    "medium",

                "placement_priority":
                    "work_zone",

                "preferred_edge_role":
                    "open_edge"

            },


            "retail": {

                "privacy_level":
                    "low",

                "daylight_priority":
                    "high",

                "public_access_priority":
                    "high",

                "placement_priority":
                    "public_access",

                "preferred_edge_role":
                    "public_edge"

            },


            "service_core": {

                "privacy_level":
                    "low",

                "service_priority":
                    "high",

                "vertical_role":
                    "primary",

                "placement_priority":
                    "protected_core"

            }

        }


        spaces = (

            program.get(
                "required_spaces",
                []
            )

            +

            program.get(
                "optional_spaces",
                []
            )

        )


        for space in spaces:

            name = str(
                space.get(
                    "name",
                    ""
                )
            ).lower()


            intent = space_intents.get(
                name
            )


            if intent:

                space.setdefault(
                    "architectural_intent",
                    {}
                )


                space[
                    "architectural_intent"
                ].update(
                    intent
                )


        return program



    def get_program(
        self,
        building_type,
        functions=None
    ):

        # ==================================================
        # 1. EXPLICIT TYPOLOGY HAS PRIORITY
        # ==================================================

        if isinstance(
            building_type,
            str
        ):

            building_type = (
                building_type
                .strip()
                .lower()
            )


        aliases = {

            "amphitheatre":
                "amphitheater",

            "open_air_theater":
                "amphitheater",

            "open_air_theatre":
                "amphitheater"

        }


        building_type = aliases.get(
            building_type,
            building_type
        )

        if building_type in self.programs:

            import copy

            program = copy.deepcopy(
                self.programs[
                    building_type
                ]
            )


            program = self._enrich_semantic_layer(
                program
            )


            program = self._enrich_floor_layer(
                program
            )


            return program


        # ==================================================
        # 2. GENERIC BUILDING → RESOLVE FROM USE
        #
        # "building" is intentionally generic.
        # Do not guess villa / apartment / office typology.
        # ==================================================

        if not isinstance(
            functions,
            list
        ):

            functions = []


        normalized_functions = {

            str(function).lower()

            for function in functions

            if function is not None

        }


        if (
            building_type in (
                None,
                "",
                "building"
            )
            and
            "residential" in normalized_functions
        ):

            import copy

            program = copy.deepcopy(
                self.programs.get(
                    "residential",
                    {}
                )
            )


            program = self._enrich_semantic_layer(
                program
            )


            program = self._enrich_floor_layer(
                program
            )


            return program


        return {}