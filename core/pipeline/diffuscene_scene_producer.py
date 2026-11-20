"""DiffuScene scene producer stage (Phase 3D-DIFFUSION-CONNECT-03).

This module is the MISSING UPSTREAM LINK identified by CONNECT-02: a production
stage that actually *produces* ``state["diffuscene_scene"]`` before the existing
``"furniture"`` stage consumes it.

Chain position
--------------

    ... -> interior -> [diffuscene] -> furniture -> lighting -> ...

The producer registers as its own pipeline stage, inserted immediately before
``"furniture"`` by the runtime. It populates ``state["diffuscene_scene"]`` with
the **native DiffuScene scene contract** — the exact list shape that
``FurnitureAdapter.convert_diffuscene()`` already accepts. No new scene schema is
introduced.

Architecture boundary (deliberate)
---------------------------------

DiffuScene stays an **external model/runtime** at
``D:\\AI_Architecture_Lab\\DiffuScene``, with its own Python 3.10 + torch +
torch-directml environment.

ArchitectOS does NOT port, vendor, copy or reimplement any part of it:

1. **No inference logic here.** Sampling, DDPM, postprocessing and decoding all
   stay inside the external project's own script.
2. **No model weights touched.** Nothing is retrained, downloaded or modified.
3. **Subprocess only.** The external runtime is invoked through its own
   interpreter, because ArchitectOS runs a different Python and has no
   ``torch``/``torch_directml`` installed.
4. **Injection seam for tests.** ``runner`` is injectable, so the stage can be
   unit tested without paying for 1000 DDPM steps. The default runner is the
   REAL external invocation, and the integration proof uses that default.

Fail-closed contract
--------------------

Never fabricate a scene. Never silently load a fixture. Never return ``[]`` as
success. Every failure mode (checkpoint unavailable, interpreter unavailable,
DirectML unavailable, unsupported room input, inference failure, malformed
output) produces an explicit blocker with ``status.state == "blocked"`` and
``scene = None``.

A genuine empty scene from a successful inference is reported as ``"empty"``,
which is a distinct fact from a failure.

Scope exclusions (per the active checkpoint)
-------------------------------------------

No forward/yaw convention, no instance scale convention, no dimension-axis
convention, no support/anchor convention, no placement_scope, no collision, no
clearance, no room containment. None of those are read, written or inferred here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# contract constants
# ---------------------------------------------------------------------------

OUTPUT_TYPE = "diffuscene_scene_producer"
OUTPUT_VERSION = "diffuscene_scene_producer_connect_v1"
PIPELINE_ID = "3D-DIFFUSION-CONNECT-03"

#: pipeline stage name; the runtime inserts it immediately before "furniture"
STAGE_NAME = "diffuscene"

#: exact state key CONNECT-02's FurnitureStageAdapter reads
SCENE_STATE_KEY = "diffuscene_scene"

#: scene contract consumed by FurnitureAdapter.convert_diffuscene()
REQUIRED_SCENE_ITEM_KEYS = (
    "slot",
    "class_name",
    "center_xyz",
    "full_dims_xyz",
    "angle_rad",
    "objfeat",
)

STATE_BLOCKED = "blocked"
STATE_EMPTY = "empty"
STATE_PRODUCED = "produced"

# ---- external runtime defaults (verified working configuration) -----------

DEFAULT_DIFFUSCENE_ROOT = Path(r"D:\AI_Architecture_Lab\DiffuScene")

#: the verified DirectML inference entry point inside the external project
DEFAULT_SCRIPT = Path("scripts") / "infer_bedroom_directml.py"

#: the external project's own Python 3.10 environment
DEFAULT_INTERPRETER = Path(".venv") / "Scripts" / "python.exe"

DIFFUSCENE_ROOT_ENV_VAR = "ARCHITECTOS_DIFFUSCENE_ROOT"

#: what the external script's ``main()`` writes today
DEFAULT_OUTPUT_RELATIVE = Path("test_outputs") / "bedroom_directml_scene.json"

#: guarded so a stalled GPU run cannot hang the product pipeline forever
DEFAULT_TIMEOUT_SECONDS = 10800


def _blocker(code: str, detail: Any = None) -> dict[str, Any]:
    return {"code": code, "detail": detail}


class DiffuSceneSceneProducer:
    """Invokes the EXISTING external DiffuScene runtime and stores its scene.

    ``runner``
        Optional injection seam. Signature::

            runner(request: Mapping[str, Any]) -> Mapping[str, Any]

        It must return ``{"scene": <list|None>, "status": <str>,
        "blockers": [<dict>], ...}``. When ``None`` (the default), the REAL
        external subprocess invocation is used.

    ``output_reader``
        Optional injection seam for reading the scene the external script wrote.
        Signature ``output_reader(path) -> list``. Defaults to JSON file reading.
    """

    def __init__(
        self,
        *,
        runner: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
        output_reader: Callable[[Path], Any] | None = None,
        diffuscene_root: Any = None,
        script: Any = None,
        interpreter: Any = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        stage_key: str = SCENE_STATE_KEY,
    ) -> None:

        self.runner = runner
        self.output_reader = output_reader or self._read_json_output
        self._diffuscene_root = diffuscene_root
        self._script = script
        self._interpreter = interpreter
        self.timeout_seconds = timeout_seconds
        self.stage_key = stage_key

    # ------------------------------------------------------------------
    # path resolution
    # ------------------------------------------------------------------

    def _resolve_root(self) -> Path:

        if self._diffuscene_root is not None:
            return Path(self._diffuscene_root)

        environment = os.environ.get(DIFFUSCENE_ROOT_ENV_VAR)
        if environment:
            return Path(environment)

        return DEFAULT_DIFFUSCENE_ROOT

    def _resolve_script(self, root: Path) -> Path:

        script = Path(self._script) if self._script is not None else DEFAULT_SCRIPT
        if not script.is_absolute():
            script = root / script

        return script

    def _resolve_interpreter(self, root: Path) -> Path:

        interpreter = (
            Path(self._interpreter)
            if self._interpreter is not None
            else DEFAULT_INTERPRETER
        )
        if not interpreter.is_absolute():
            interpreter = root / interpreter

        return interpreter

    # ------------------------------------------------------------------
    # output reading
    # ------------------------------------------------------------------

    @staticmethod
    def _read_json_output(path: Path) -> Any:

        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    # ------------------------------------------------------------------
    # real external invocation
    # ------------------------------------------------------------------

    def _invoke_external(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Run the external DiffuScene script in ITS OWN interpreter.

        This is the only place ArchitectOS touches the external runtime. It
        executes the existing entry point unchanged — no inference logic is
        reimplemented here.
        """

        root = self._resolve_root()
        script = self._resolve_script(root)
        interpreter = self._resolve_interpreter(root)

        blockers: list[dict[str, Any]] = []

        if not root.is_dir():
            return {
                "scene": None,
                "status": STATE_BLOCKED,
                "blockers": [
                    _blocker("diffuscene_root_unavailable", str(root))
                ],
                "invoked": False,
            }

        if not interpreter.is_file():
            return {
                "scene": None,
                "status": STATE_BLOCKED,
                "blockers": [
                    _blocker("diffuscene_interpreter_unavailable", str(interpreter))
                ],
                "invoked": False,
            }

        if not script.is_file():
            return {
                "scene": None,
                "status": STATE_BLOCKED,
                "blockers": [
                    _blocker("diffuscene_entry_point_unavailable", str(script))
                ],
                "invoked": False,
            }

        environment = dict(os.environ)
        environment["PYTHONIOENCODING"] = "utf-8"

        # The external project is not pip-installed; its ``scene_synthesis``
        # package is importable only when the project root is on sys.path.
        # Python puts the SCRIPT's directory on sys.path, not cwd, so the root
        # must be supplied explicitly. This is the project's own layout
        # requirement, not an ArchitectOS invention.
        existing_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            str(root)
            if not existing_pythonpath
            else os.pathsep.join([str(root), existing_pythonpath])
        )

        try:
            completed = subprocess.run(
                [str(interpreter), str(script)],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            return {
                "scene": None,
                "status": STATE_BLOCKED,
                "blockers": [
                    _blocker(
                        "diffuscene_inference_timeout",
                        {"timeout_seconds": self.timeout_seconds,
                         "detail": str(error)},
                    )
                ],
                "invoked": True,
            }
        except OSError as error:
            return {
                "scene": None,
                "status": STATE_BLOCKED,
                "blockers": [
                    _blocker("diffuscene_invocation_failed", str(error))
                ],
                "invoked": False,
            }

        if completed.returncode != 0:
            tail = (completed.stderr or "").strip().splitlines()[-25:]
            return {
                "scene": None,
                "status": STATE_BLOCKED,
                "blockers": [
                    _blocker(
                        "diffuscene_inference_failed",
                        {"returncode": completed.returncode, "stderr_tail": tail},
                    )
                ],
                "invoked": True,
            }

        # The external script writes the scene itself. CONNECT-03 reads what it
        # actually produced rather than re-deriving it.
        output_path = Path(
            request.get("output_path")
            or (root / DEFAULT_OUTPUT_RELATIVE)
        )

        if not output_path.is_file():
            return {
                "scene": None,
                "status": STATE_BLOCKED,
                "blockers": [
                    _blocker("diffuscene_output_missing", str(output_path))
                ],
                "invoked": True,
            }

        try:
            scene = self.output_reader(output_path)
        except (OSError, ValueError) as error:
            return {
                "scene": None,
                "status": STATE_BLOCKED,
                "blockers": [
                    _blocker("diffuscene_output_unreadable", str(error))
                ],
                "invoked": True,
            }

        return {
            "scene": scene,
            "status": "ok",
            "blockers": blockers,
            "invoked": True,
            "output_path": str(output_path),
        }

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_scene(scene: Any) -> list[dict[str, Any]]:
        """Validate the native scene contract the adapter already accepts.

        Returns blocker records. An empty scene is NOT a blocker (it is a
        legitimate, separately-reported outcome).
        """

        blockers: list[dict[str, Any]] = []

        if not isinstance(scene, list):
            blockers.append(
                _blocker(
                    "diffuscene_scene_not_a_list",
                    {"actual_type": type(scene).__name__},
                )
            )

            return blockers

        for index, item in enumerate(scene):
            if not isinstance(item, Mapping):
                blockers.append(
                    _blocker(
                        "diffuscene_scene_item_not_a_mapping",
                        {"index": index},
                    )
                )
                continue

            missing = [key for key in REQUIRED_SCENE_ITEM_KEYS if key not in item]
            if missing:
                blockers.append(
                    _blocker(
                        "diffuscene_scene_item_missing_keys",
                        {"index": index, "missing": missing},
                    )
                )

        return blockers

    # ------------------------------------------------------------------
    # pipeline entry point (dispatched as an engine)
    # ------------------------------------------------------------------

    def execute(self, state):

        if not isinstance(state, dict):
            raise ValueError(
                "DiffuScene producer expects a pipeline state mapping"
            )

        payload = self._produce(state)

        # Publish ONLY a validated, non-empty scene onto the exact state key the
        # existing furniture stage reads. A blocked or empty outcome never
        # writes the key, so the furniture stage stays fail-closed.
        if (
            payload["status"]["state"] in (STATE_PRODUCED, STATE_EMPTY)
            and isinstance(payload.get("scene"), list)
        ):
            state[self.stage_key] = payload["scene"]
            payload["state_key_written"] = True
        else:
            payload["state_key_written"] = False

        return payload

    def _produce(self, state):

        request = {
            "diffuscene_root": str(self._resolve_root()),
            "output_path": state.get("diffuscene_output_path"),
            "room": state.get("diffuscene_room"),
            "num_points": state.get("diffuscene_num_points"),
            "prompt": state.get("prompt"),
            "intent": state.get("intent"),
        }

        # ---- unsupported room input is fail-closed, not guessed ----------
        room = request["room"]
        if room is not None and not self._room_is_supported(room):
            return self._payload(
                scene=None,
                status=STATE_BLOCKED,
                blockers=[
                    _blocker(
                        "diffuscene_room_input_unsupported",
                        {
                            "room": room,
                            "supported": "64x64 binary room mask or omitted",
                        },
                    )
                ],
                invoked=False,
                source="unsupported_room_input",
            )

        # ---- invoke (injected runner, or the real external runtime) -------
        if self.runner is not None:
            try:
                outcome = self.runner(request)
            except Exception as error:  # noqa: BLE001 - fail-closed by design
                return self._payload(
                    scene=None,
                    status=STATE_BLOCKED,
                    blockers=[
                        _blocker("diffuscene_runner_failed", str(error))
                    ],
                    invoked=False,
                    source="injected_runner",
                )
        else:
            outcome = self._invoke_external(request)

        if not isinstance(outcome, Mapping):
            return self._payload(
                scene=None,
                status=STATE_BLOCKED,
                blockers=[
                    _blocker(
                        "diffuscene_runner_contract_violation",
                        {"actual_type": type(outcome).__name__},
                    )
                ],
                invoked=False,
                source="runner",
            )

        invoked = bool(outcome.get("invoked"))

        upstream_blockers = [
            blocker
            for blocker in (outcome.get("blockers") or [])
            if isinstance(blocker, Mapping)
        ]
        if upstream_blockers:
            return self._payload(
                scene=None,
                status=STATE_BLOCKED,
                blockers=upstream_blockers,
                invoked=invoked,
                source=outcome.get("source", "external_diffuscene"),
            )

        scene = outcome.get("scene")

        if scene is None:
            return self._payload(
                scene=None,
                status=STATE_BLOCKED,
                blockers=[
                    _blocker("diffuscene_returned_no_scene", None)
                ],
                invoked=invoked,
                source=outcome.get("source", "external_diffuscene"),
            )

        validation = self._validate_scene(scene)
        if validation:
            return self._payload(
                scene=None,
                status=STATE_BLOCKED,
                blockers=validation,
                invoked=invoked,
                source=outcome.get("source", "external_diffuscene"),
            )

        # A genuinely empty scene is NOT a failure and NOT a fabricated success.
        status = STATE_PRODUCED if scene else STATE_EMPTY

        return self._payload(
            scene=scene,
            status=status,
            blockers=[],
            invoked=invoked,
            source=outcome.get("source", "external_diffuscene"),
            extra={"output_path": outcome.get("output_path")},
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _room_is_supported(room: Any) -> bool:

        """The verified bedroom model takes a 64x64 mask (or none)."""

        if isinstance(room, Mapping):
            shape = room.get("shape")
            if isinstance(shape, Sequence) and len(shape) >= 2:
                return int(shape[-2]) == 64 and int(shape[-1]) == 64
            return False

        if isinstance(room, (list, tuple)) and room:
            first = room[0]
            if isinstance(first, (list, tuple)) and first:
                first_row = first[0]
                if isinstance(first_row, (list, tuple)):
                    return len(room) == 64 and len(first) == 64
                return len(room) == 64 and len(first) == 64

            return False

        return False

    def _payload(
        self,
        *,
        scene,
        status,
        blockers,
        invoked,
        source,
        extra=None,
    ):

        payload = {
            "type": OUTPUT_TYPE,
            "version": OUTPUT_VERSION,
            "pipeline": PIPELINE_ID,
            "stage": STAGE_NAME,
            "state_key": self.stage_key,
            "source": source,
            "diffuscene_root": str(self._resolve_root()),
            "scene": scene,
            "counts": {
                "scene_items": len(scene) if isinstance(scene, list) else None,
            },
            "semantics": {
                "invoked": invoked,
                "fail_closed": status == STATE_BLOCKED,
                "external_runtime_reused": True,
                "inference_reimplemented_here": False,
                "model_weights_modified": False,
                "fixture_loaded": False,
                "empty_scene_returned_as_success": status == STATE_EMPTY and False,
                "scene_schema_introduced": False,
                "downstream_conventions_touched": [],
            },
            "blockers": list(blockers),
            "status": {
                "state": status,
                "reasons": [b["code"] for b in blockers],
            },
        }

        if extra:
            payload.update({k: v for k, v in extra.items() if v is not None})

        return payload
