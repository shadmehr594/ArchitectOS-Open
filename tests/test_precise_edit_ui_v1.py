"""PRECISE_EDIT_UI_V1 — a mask must reach the precise route, never be dropped.

Guards ARCHITECTOS_LIVE_PRODUCT_SMOKE_ACCEPTANCE_V2 §6:

  * `WorkflowSelector` discarded a supplied `mask` unless the caller ALSO set
    `kontext_edit`, so a localized request silently ran the whole-image graph;
  * `bool(data.get("conditioned_render"))` treated the string "0" as ON.

The UI now uploads mask bytes (the server names the file) and sends
`kontext_edit=1`; this suite locks the server-side contract that makes that
safe.

Run:
  ./.venv/Scripts/python.exe -m pytest tests/test_precise_edit_ui_v1.py -q \
      --basetemp=runs/_pytest_tmp_peui
"""

import pytest

from core.render.workflow_selector import WorkflowSelector
from core.render.dual_image_conditioning_v1 import parse_conditioned_flag


SELECTOR = WorkflowSelector()

BASE = {"mode": "img2img", "image": {"filename": "source.png"}}
MASK = {"filename": "architectos_mask_abc.png"}


# ----------------------------------------------------------
# 1. A MASK IS NEVER SILENTLY IGNORED
# ----------------------------------------------------------

def test_mask_without_the_explicit_flag_still_selects_kontext():
    """The measured silent drop: mask present, flag absent -> whole-image."""
    workflow = SELECTOR.select({**BASE, "mask": MASK})
    assert workflow == "flux_kontext_edit.json"


def test_mask_with_the_explicit_flag_selects_kontext():
    workflow = SELECTOR.select({**BASE, "mask": MASK, "kontext_edit": True})
    assert workflow == "flux_kontext_edit.json"


def test_no_mask_and_no_flag_keeps_the_global_img2img_graph():
    """Global I2I stays an explicitly different operation."""
    assert SELECTOR.select(dict(BASE)) == "flux_img2img.json"


def test_empty_mask_dict_does_not_select_kontext():
    assert SELECTOR.select({**BASE, "mask": {}}) == "flux_img2img.json"


def test_explicit_kontext_without_a_mask_is_still_honoured():
    """An explicit route choice is the caller's, not the selector's, to make."""
    workflow = SELECTOR.select({**BASE, "kontext_edit": True})
    assert workflow == "flux_kontext_edit.json"


# ----------------------------------------------------------
# 2. THE KONTEXT GRAPH REALLY CONSUMES THE MASK
# ----------------------------------------------------------

def test_kontext_graph_wires_a_mask_node():
    import json
    import os

    path = os.path.join(
        os.path.dirname(__file__), "..", "core", "render", "workflows",
        "flux_kontext_edit.json",
    )
    with open(path, encoding="utf-8") as handle:
        graph = json.load(handle)

    class_types = {node.get("class_type") for node in graph.values()}
    assert "LoadImageMask" in class_types
    assert "ImageCompositeMasked" in class_types


# ----------------------------------------------------------
# 3. TRI-STATE OPT-IN SURVIVES THE MULTIPART STRING FORM
# ----------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("0", False),
    ("false", False),
    ("1", True),
    (None, None),
])
def test_conditioned_flag_from_multipart_strings(raw, expected):
    assert parse_conditioned_flag(raw) is expected
