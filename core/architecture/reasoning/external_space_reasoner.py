"""Semantic external / site space reasoning (ARCH-SITE-03).

Enriches an external-space node with the semantic profile implied by its
AUTHORITATIVE site metadata.

ARCH-SITE-03 replaced the previous name-based classification. Site-ness is now
read from the space's own semantic fields:

    placement_domain == "site"   (preferred)
    floor            == "site_level"

A space is therefore recognised identically regardless of its name: garden,
courtyard, pool, landscape, driveway and outdoor_kitchen all behave the same
when they carry site metadata, with NO code change required for a new name.

PROFILE SELECTION IS SEMANTIC TOO
---------------------------------
The site profile is chosen from the space's own architectural intent, not its
name:

- a space whose ``architectural_intent`` declares vehicle access
  (``vehicle_access_priority`` / ``placement_priority == "vehicle_access"``)
  receives the vehicle site profile;
- every other site space receives the generic landscape site profile.

That keeps a parking site space a vehicle space while letting an unknown site
name inherit the generic profile.

This module is enrichment ONLY. It:

- never drops or filters a space (an unrecognised space is returned unchanged)
- never creates coordinates, polygons, geometry, elevations or placement
- never mutates its input (the result is a NEW dict)
- never decides whether a node becomes external - that is the caller's job
- does not import LayoutReasoner or any geometry/parcel subsystem
"""


# ---------------------------------------------------------------------------
# semantic site profiles
#
# These are profile VALUES, not a name list: nothing here is compared against a
# space name. "terrace" and "vehicle_access" below are preferred-NEIGHBOUR
# references carried as data, not classification keys.
# ---------------------------------------------------------------------------

GENERIC_SITE_PROFILE = {
    "space_type": "landscape",
    "relation_to_building": "visual_extension",
    "privacy": "external",
    "placement_rule": "open_edge",
    "preferred_neighbors": ["living", "dining", "terrace"],
}

VEHICLE_SITE_PROFILE = {
    "space_type": "vehicle_space",
    "relation_to_building": "service_access",
    "placement_rule": "road_edge",
    "preferred_neighbors": ["entrance", "vehicle_access"],
}

SITE_FLOOR = "site_level"
SITE_PLACEMENT_DOMAIN = "site"

VEHICLE_PLACEMENT_PRIORITY = "vehicle_access"


def is_site_space(space):
    """Return True when ``space`` carries authoritative site semantics.

    Data-driven on the space's own fields - never on its name.
    """

    if not isinstance(space, dict):
        return False

    return (
        space.get("placement_domain") == SITE_PLACEMENT_DOMAIN
        or space.get("floor") == SITE_FLOOR
    )


def has_vehicle_intent(space):
    """Return True when the space's own intent declares vehicle access."""

    if not isinstance(space, dict):
        return False

    intent = space.get("architectural_intent")

    if not isinstance(intent, dict):
        return False

    if intent.get("vehicle_access_priority"):
        return True

    return intent.get("placement_priority") == VEHICLE_PLACEMENT_PRIORITY


class ExternalSpaceReasoner:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🌿 EXTERNAL SPACE REASONER v{self.VERSION} ONLINE"
        )


    def resolve(
        self,
        external_space,
        connections=None
    ):

        # ``connections`` is retained for call-site compatibility; the
        # semantic profile is derived from the space's own metadata.
        connections = connections or []


        result = dict(
            external_space
        )


        if not is_site_space(
            external_space
        ):

            # NOT a site space. It is returned unchanged: a space on a
            # building floor is never enriched as an external site node.
            return result


        if has_vehicle_intent(
            external_space
        ):

            result.update(
                dict(
                    VEHICLE_SITE_PROFILE
                )
            )

        else:

            result.update(
                dict(
                    GENERIC_SITE_PROFILE
                )
            )


        # A site space stays a site space, whatever profile was applied.
        result["placement_domain"] = SITE_PLACEMENT_DOMAIN

        # Contract normalisation only. A space recognised as a site space via
        # placement_domain == "site" may arrive without an explicit floor; the
        # site contract states floor == "site_level", so it is asserted here.
        # This is not an invented value: it is the declared site contract, and
        # it never fires when a floor is already present.
        if not result.get("floor"):

            result["floor"] = SITE_FLOOR


        return result
