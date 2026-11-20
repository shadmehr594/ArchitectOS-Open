"""PLAN_FIRST_PRODUCT_SLICE_V1 — conceptual spatial planning in Chat.

Wraps the EXISTING owner
`core.knowledge.architectural_spatial_planning_understanding_v1` into a Chat
result contract.

That owner had no production caller: it was reachable only from its own
module and from tests. This module is the smallest connection that makes its
output product-visible. It adds no reasoning of its own — it does not add a
room, a dimension, a wall or a coordinate, and it never upgrades a conceptual
planning into a plan drawing.
"""

from core.knowledge.architectural_spatial_planning_understanding_v1 import (
    CONTRACT as PLANNING_CONTRACT,
    ArchitecturalSpatialPlanningUnderstandingError,
    understand_spatial_planning,
)


RESPONSE_TYPE = "spatial_planning"

VERSION = "1.0"


def handle_spatial_planning(text, context=None):

    """Return a Chat result carrying the existing conceptual planning.

    The natural planning text is placed in `result`/`text` so the existing
    response renderer displays it unchanged; the structured contract rides
    alongside for any consumer that wants it.
    """

    request_text = str(text or "").strip()

    if not request_text:

        return {

            "type": RESPONSE_TYPE,

            "status": "empty_request",

            "contract": PLANNING_CONTRACT,

            "result": "",

            "text": "",

        }

    try:

        planning = understand_spatial_planning(request_text)

    except ArchitecturalSpatialPlanningUnderstandingError as error:

        # The owner refuses an unusable request. Report the refusal as a
        # limitation rather than inventing a plan.
        return {

            "type": RESPONSE_TYPE,

            "status": "unsupported",

            "contract": PLANNING_CONTRACT,

            "reason": str(error),

            "result": "",

            "text": "",

        }

    natural = str(planning.get("natural_planning") or "")

    return {

        "type": RESPONSE_TYPE,

        "status": "ok",

        "version": VERSION,

        "contract": PLANNING_CONTRACT,

        # Existing renderer fallback: a string `result` is shown verbatim.
        "result": natural,

        "text": natural,

        "language": planning.get("language"),

        # The full existing contract, unmodified.
        "spatial_planning": planning,

        # Repeated at the top level so a caller cannot read the payload
        # without also seeing what it is NOT.
        "plan_generated": bool(planning.get("plan_generated")),

        "geometry_generated": bool(planning.get("geometry_generated")),

        "is_final_solution": bool(planning.get("is_final_solution")),

        "human_review_required": bool(planning.get("human_review_required")),

        "non_claims": planning.get("non_claims"),

    }
