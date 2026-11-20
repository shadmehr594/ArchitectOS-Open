"""V25_PLAN_SESSION — four-turn end-to-end verification.

Drives the real Flask app through its test client, so what is verified is the
HTTP contract the chat UI consumes, not a private helper.

Turn 1  design a duplex villa            -> plan + svg/dxf/png/json
Turn 2  "آشپزخانه رو بزرگتر کن"          -> incremental edit, new revision
Turn 3  "…نئوکلاسیک و سنگ تراورتن…"      -> render state extracted from plan
Turn 4  "حالا رندر شب همین ساختمان…"      -> locked night relight chain

Also covers the v25 engine invariants that requirement 1 names: zero orphan
columns, and the AutoCAD 2025 DXF layer set.

CPU only — the render turns verify the DISPATCH DECISION, not pixels.
"""

import json
import os
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent

if str(REPO) not in sys.path:
    sys.path.append(str(REPO))


DESIGN_PROMPT = "یک ساختمان ویلایی دوبلکس مدرن در زمین 10*20 طراحی کن"
EDIT_PROMPT = "آشپزخانه رو بزرگتر کن"
RENDER_DAY = "حالا از همین پلان با سبک نئوکلاسیک و سنگ تراورتن رندر روز بگیر"
RENDER_NIGHT = "حالا رندر شب همین ساختمان رو بگیر"


@pytest.fixture(scope="module")
def client():
    import app as server

    server.app.config.update(TESTING=True)

    return server.app.test_client()


@pytest.fixture(scope="module")
def project_id():
    # The session persists `active_plan_params` to
    # `outputs/plans/<project_id>/session_state.json`. A fixed id therefore
    # made this module non-repeatable: the second run started with an active
    # plan, so turn 1 was routed as an EDIT and `mode == "create"` failed.
    # A per-run id keeps the four turns in one session while making the run
    # independent of every earlier run.
    import uuid

    return "pytest_v25_turns_" + uuid.uuid4().hex[:8]


def _path_from_url(url: str) -> pathlib.Path:
    """Map /planning/drawing/<pid>/renders/<name> to the file on disk."""

    marker = "/planning/drawing/"

    assert url.startswith(marker), url

    return REPO / "outputs" / "plans" / url[len(marker):]


def _post(client, route, prompt, project_id):
    response = client.post(
        route,
        json={"prompt": prompt, "project_id": project_id},
    )

    return response, response.get_json()


# ---------------------------------------------------------------------------
# Turn 1 — plan creation
# ---------------------------------------------------------------------------

def test_turn1_design_creates_plan_and_returns_downloadable_assets(client, project_id):
    response, body = _post(client, "/api/plan/turn", DESIGN_PROMPT, project_id)

    assert response.status_code == 200, body
    assert body["status"] == "ok"
    assert body["mode"] == "create"
    assert body["plan_revision"] == 1

    assets = body["assets"]
    for key in ("svg", "dxf", "png", "json"):
        assert assets.get(key), "missing %s url" % key

    # every link resolves to a real, non-empty file
    for key in ("svg", "dxf", "png", "json"):
        path = _path_from_url(assets[key])
        assert path.is_file(), path
        assert path.stat().st_size > 0, path

    # the response carries an image the UI can display immediately
    assert body["image_url"]

    assert body["plan"]["floors"] == 2
    assert body["plan"]["audit_status"] == "VALID"

    params = body["active_plan_params"]
    assert params["typology"] == "DUPLEX_2FLOOR"
    assert params["site_width_mm"] == 10000
    assert params["site_length_mm"] == 20000


# ---------------------------------------------------------------------------
# Turn 2 — unlimited plan editing, never a text-only reply
# ---------------------------------------------------------------------------

def test_turn2_kitchen_edit_increases_width_and_reissues_drawings(client, project_id):
    before = client.get(
        "/api/plan/session", query_string={"project_id": project_id}
    ).get_json()

    previous_width = int(
        (before.get("active_plan_params") or {}).get("kitchen_extra_width_mm") or 0
    )
    previous_revision = int(before.get("plan_revision") or 0)

    response, body = _post(client, "/api/plan/turn", EDIT_PROMPT, project_id)

    assert response.status_code == 200, body
    assert body["status"] == "ok"
    assert body["mode"] == "edit", "a modification turn must edit, not create"

    # the edit is applied to the stored params
    assert int(body["active_plan_params"]["kitchen_extra_width_mm"]) > previous_width
    assert int(body["active_plan_params"]["edit_revision"]) >= 1

    # a NEW revision was written, not the old one re-served
    assert body["plan_revision"] == previous_revision + 1
    assert "plan_rev_%d" % body["plan_revision"] in body["assets"]["svg"]

    for key in ("svg", "dxf", "png"):
        path = _path_from_url(body["assets"][key])
        assert path.is_file(), path
        assert path.stat().st_size > 0, path

    # and it is not a text-only acknowledgement
    assert body["image_url"]
    assert body["downloads"]


def test_turn2_state_persists_to_disk(client, project_id):
    state_file = REPO / "outputs" / "plans" / project_id / "session_state.json"

    assert state_file.is_file(), state_file

    state = json.loads(state_file.read_text(encoding="utf-8"))

    assert state["active_plan_params"], "params must survive a restart"
    assert state["plan_revision"] >= 2
    assert state["active_plan_files"]["svg_url"]


# ---------------------------------------------------------------------------
# Turn 3 — plan-to-render handoff
# ---------------------------------------------------------------------------

def test_turn3_render_extracts_plan_attributes(client, project_id):
    response, body = _post(client, "/api/render/turn", RENDER_DAY, project_id)

    assert response.status_code == 200, body
    assert body["floors"] == 2
    assert body["style"] == "neoclassical"
    # v27 resolves materials to a longer canonical phrase
    # ("cream honed travertine stone slabs"). The property under test is that
    # the travertine the user asked for survives the plan -> render handoff,
    # not that one exact string survives a vocabulary upgrade.
    _materials = " ".join(body["materials"]).lower()
    assert "travertine" in _materials, body["materials"]
    assert "cream" in _materials, body["materials"]
    assert body["lighting"] == "day"
    assert body["use_locked_night_chain"] is False

    # a 2-storey villa is below the high-rise threshold: no floor scaffold
    assert body["chain"] == "conditioned_t2i"
    assert body["scaffold"] is None

    # the state is persisted for the next render turn
    state = client.get(
        "/api/plan/session", query_string={"project_id": project_id}
    ).get_json()

    assert state["active_render_state"]["style"] == "neoclassical"
    assert state["active_render_state"]["floors"] == 2


# ---------------------------------------------------------------------------
# Turn 4 — locked night relight of the previous day render
# ---------------------------------------------------------------------------

def test_turn4_night_dispatches_the_locked_chain(client, project_id):
    from core.planning import plan_session_v25 as session

    # a day render must exist for the night turn to relight it
    state = session.load_state(project_id)
    day_render = str(REPO / "outputs" / "plans" / project_id / "renders" / "day_probe.png")
    state["active_render_state"]["last_day_render_path"] = day_render
    session.save_state(project_id, state)

    response, body = _post(client, "/api/render/turn", RENDER_NIGHT, project_id)

    assert response.status_code == 200, body
    assert body["lighting"] == "night"
    assert body["use_locked_night_chain"] is True
    assert body["chain"] == "locked_night_relight"

    # the relight is locked to the day geometry, not a fresh generation
    assert body["render_state"]["night_denoise"] <= 0.32
    assert body["render_state"]["last_day_render_path"] == day_render

    # the floor count is preserved across the lighting change
    assert body["floors"] == 2


# ---------------------------------------------------------------------------
# Requirement 1 — engine invariants
# ---------------------------------------------------------------------------

def test_engine_has_zero_orphan_columns_on_every_floor():
    from core.planning import plan_session_v25 as session

    engine = session.load_engine()
    nl = session.parser()

    project = engine.ParametricArchitecturalSynthesizer().synthesize_from_params(
        nl.parse_architectural_prompt(DESIGN_PROMPT)
    )

    assert project.floors, "synthesis produced no floors"

    for floor in project.floors:
        xs = [value for _, value in floor.grid_x_mm]
        ys = [value for _, value in floor.grid_y_mm]

        orphans = [
            column
            for column in floor.columns
            if not any(abs(column.rect_mm.center[0] - x) <= 160 for x in xs)
            or not any(abs(column.rect_mm.center[1] - y) <= 160 for y in ys)
        ]

        assert orphans == [], "floor %d has orphan columns: %r" % (
            floor.floor_index,
            [column.col_id for column in orphans],
        )

        # axis labels are sequential, not sparse
        assert [label for label, _ in floor.grid_x_mm] == [
            chr(ord("A") + i) for i in range(len(floor.grid_x_mm))
        ]
        assert [label for label, _ in floor.grid_y_mm] == [
            str(i + 1) for i in range(len(floor.grid_y_mm))
        ]


def test_dxf_carries_the_v25_layer_set(tmp_path):
    from core.planning import plan_session_v25 as session

    engine = session.load_engine()
    nl = session.parser()

    project = engine.ParametricArchitecturalSynthesizer().synthesize_from_params(
        nl.parse_architectural_prompt(DESIGN_PROMPT)
    )

    target = tmp_path / "v25.dxf"
    engine.export_project_to_dxf(project, str(target))

    text = target.read_text(encoding="utf-8", errors="ignore")

    # ==========================================================
    # v27 exports STRICT AutoCAD R12 (`AC1009`).
    #
    # `$LWDISPLAY` is an R2000 header variable and `290`/`370` are R2000
    # group codes; writing them into an AC1009 file is what made AutoCAD 2025
    # reject the sheet. v27 dropped all three on purpose, so the v25 assertion
    # that demanded `$LWDISPLAY` is now the defect. The LAYER SET is the part
    # that must survive, and it is still asserted below.
    # ==========================================================

    assert "$ACADVER" in text
    assert "AC1009" in text, "DXF is not strict R12"

    lines = [line.strip() for line in text.splitlines()]

    group_codes = {lines[i] for i in range(0, len(lines) - 1, 2)}

    for illegal in ("290", "370"):

        assert illegal not in group_codes, (
            "R12 DXF must not carry group code %s" % illegal
        )

    for marker in (
        "A-WALL",
        "S-COLS",
        "A-FURN",
        "A-DIM",
        "A-SEISMIC-GAP",
        "A-ANNO-LEVL",
    ):
        assert marker in text, "DXF missing %s" % marker


def test_exporter_keeps_both_call_contracts(tmp_path):
    """One argument returns CONTENT; a path writes the file and returns it."""

    from core.planning import plan_session_v25 as session

    engine = session.load_engine()
    nl = session.parser()

    project = engine.ParametricArchitecturalSynthesizer().synthesize_from_params(
        nl.parse_architectural_prompt(DESIGN_PROMPT)
    )

    content = engine.export_project_to_svg(project)
    assert isinstance(content, str) and content.lstrip().startswith("<svg")

    target = tmp_path / "sheet.svg"
    returned = engine.export_project_to_svg(project, str(target))

    assert os.path.abspath(returned) == os.path.abspath(str(target))
    assert target.is_file()


# ---------------------------------------------------------------------------
# High-rise scaffold path
# ---------------------------------------------------------------------------

def test_highrise_render_stages_an_exact_floor_scaffold(client):
    """floors >= 6 must use the exact-N wireframe, not a plain generation."""

    pid = "pytest_v25_highrise"

    response, body = _post(
        client,
        "/api/plan/turn",
        "یک ساختمان 12 طبقه مسکونی مدرن در زمین 15*20 طراحی کن",
        pid,
    )

    assert response.status_code == 200, body

    response, body = _post(
        client,
        "/api/render/turn",
        "حالا ازش رندر روز بگیر",
        pid,
    )

    assert response.status_code == 200, body
    assert body["floors"] == 12
    assert body["chain"] == "exact_floors_t2i"
    assert body["scaffold"] and body["scaffold"].startswith("scaffold_N12_")
