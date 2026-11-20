# ==========================================================
# ArchitectOS Runtime Preflight v1
#
# RUNTIME_FOUNDATION_01
#
# One lightweight preflight / status function that truthfully
# reports the state of the local runtime:
#
#   CORE_API   -> ArchitectOS gateway      (app.py)
#   UI         -> ArchitectOS frontend     (ui/app.py)
#   COMFYUI    -> externally managed render backend
#   OLLAMA     -> externally managed LLM backend
#   workflows  -> required workflow JSON files
#   comfy paths-> required ComfyUI input/output directories
#
# Uses ONLY the standard library so that it keeps working when the
# environment is broken - which is exactly when it is needed.
#
# CLI:
#   python -m core.runtime.runtime_preflight
#   python -m core.runtime.runtime_preflight --json
#   python -m core.runtime.runtime_preflight --quiet
# ==========================================================


import json
import os
import time
import urllib.error
import urllib.request


from config import runtime_config as RC



# ==========================================================
# DIRECT (PROXY-FREE) OPENER
#
# Localhost health checks MUST NOT be routed through an ambient
# HTTP_PROXY. On this machine an HTTP_PROXY is set, and proxied
# probes to 127.0.0.1 falsely return 502 even when nothing is
# listening - which would make the preflight report lies.
# ==========================================================

_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)



# ==========================================================
# LOW LEVEL HTTP PROBE
# ==========================================================

def probe_http(
    url,
    timeout=None
):
    """Single GET probe.

    Returns a dict:
      reachable    -> transport succeeded (any HTTP status)
      ok           -> HTTP 2xx
      status_code  -> int or None
      latency_ms   -> float
      body         -> parsed JSON when possible
      error        -> transport error string or None
    """

    if timeout is None:

        timeout = RC.PROBE_TIMEOUT

    started = time.time()

    result = {

        "url":
            url,

        "reachable":
            False,

        "ok":
            False,

        "status_code":
            None,

        "latency_ms":
            None,

        "body":
            None,

        "error":
            None,

    }


    try:

        request = urllib.request.Request(
            url,
            method="GET"
        )

        with _OPENER.open(
            request,
            timeout=timeout
        ) as response:

            raw = response.read()

            result["reachable"] = True

            result["status_code"] = response.status

            result["ok"] = 200 <= response.status < 300

            try:

                result["body"] = json.loads(
                    raw.decode("utf-8")
                )

            except Exception:

                result["body"] = None


    except urllib.error.HTTPError as e:

        # Server answered, but with a non-2xx status.
        result["reachable"] = True

        result["status_code"] = e.code

        result["ok"] = False

        result["error"] = "http_" + str(e.code)


    except Exception as e:

        result["error"] = (
            type(e).__name__
            + ": "
            + str(e)
        )


    result["latency_ms"] = round(
        (time.time() - started) * 1000,
        1
    )

    return result



# ==========================================================
# SERVICE CHECKS
# ==========================================================

def check_core_api():
    """ArchitectOS Core API gateway (must be started by the launcher)."""

    probe = probe_http(
        RC.CORE_API_URL + RC.CORE_API_HEALTH_PATH
    )

    body = probe.get("body")

    return {

        "name":
            "CORE_API",

        "url":
            RC.CORE_API_URL,

        "managed_by":
            "architectos_launcher",

        "reachable":
            probe["reachable"],

        "ok":
            probe["ok"],

        "status_code":
            probe["status_code"],

        "latency_ms":
            probe["latency_ms"],

        "detail":
            (
                body.get("status")
                if isinstance(body, dict)
                else None
            ),

        "error":
            probe["error"],

    }


def check_ui():
    """ArchitectOS UI server (must be started by the launcher)."""

    probe = probe_http(
        RC.UI_URL + RC.UI_STATUS_PATH
    )

    body = probe.get("body")

    return {

        "name":
            "UI",

        "url":
            RC.UI_URL,

        "managed_by":
            "architectos_launcher",

        "reachable":
            probe["reachable"],

        "ok":
            probe["ok"],

        "status_code":
            probe["status_code"],

        "latency_ms":
            probe["latency_ms"],

        "detail":
            (
                body.get("system")
                if isinstance(body, dict)
                else None
            ),

        "error":
            probe["error"],

    }


def check_comfyui():
    """ComfyUI render backend. Externally managed - detected only."""

    probe = probe_http(
        RC.COMFYUI_URL + RC.COMFYUI_HEALTH_PATH
    )

    body = probe.get("body")

    comfy_version = None

    if isinstance(body, dict):

        system = body.get("system")

        if isinstance(system, dict):

            comfy_version = system.get("comfyui_version")


    return {

        "name":
            "COMFYUI",

        "url":
            RC.COMFYUI_URL,

        "root":
            RC.COMFYUI_ROOT,

        "managed_by":
            "external",

        "reachable":
            probe["reachable"],

        "ok":
            probe["ok"],

        "status_code":
            probe["status_code"],

        "latency_ms":
            probe["latency_ms"],

        "detail":
            comfy_version,

        "error":
            probe["error"],

    }


def check_ollama():
    """Ollama LLM backend. Externally managed - detected only."""

    probe = probe_http(
        RC.OLLAMA_URL + RC.OLLAMA_HEALTH_PATH
    )

    body = probe.get("body")

    models = []

    if isinstance(body, dict):

        models = [
            m.get("name")
            for m in body.get("models", [])
            if isinstance(m, dict)
        ]

    return {

        "name":
            "OLLAMA",

        "url":
            RC.OLLAMA_URL,

        "managed_by":
            "external",

        "reachable":
            probe["reachable"],

        "ok":
            probe["ok"],

        "status_code":
            probe["status_code"],

        "latency_ms":
            probe["latency_ms"],

        "detail":
            str(len(models)) + " model(s)",

        "models":
            models,

        "error":
            probe["error"],

    }



# ==========================================================
# FILE / PATH CHECKS
# ==========================================================

def check_workflows():
    """Required workflow JSON files used by WorkflowSelector."""

    entries = []

    missing = []


    for name, path in RC.required_workflow_paths().items():

        exists = os.path.isfile(path)

        size = (
            os.path.getsize(path)
            if exists
            else None
        )

        entries.append({

            "name":
                name,

            "path":
                path,

            "exists":
                exists,

            "bytes":
                size,

        })

        if not exists:

            missing.append(name)


    return {

        "name":
            "WORKFLOWS",

        "dir":
            RC.WORKFLOW_DIR,

        "ok":
            not missing,

        "required":
            list(RC.REQUIRED_WORKFLOW_FILES),

        "files":
            entries,

        "missing":
            missing,

    }


def check_comfy_paths():
    """Required ComfyUI directories for input/output resolution."""

    entries = []

    missing = []


    for key, path in RC.required_comfy_paths().items():

        exists = os.path.isdir(path)

        entries.append({

            "key":
                key,

            "path":
                path,

            "exists":
                exists,

        })

        if not exists:

            missing.append(path)


    return {

        "name":
            "COMFY_PATHS",

        "root":
            RC.COMFYUI_ROOT,

        "ok":
            not missing,

        "paths":
            entries,

        "missing":
            missing,

    }



# ==========================================================
# FULL PREFLIGHT
# ==========================================================

def run_preflight():
    """Run every check and return one truthful, serializable report."""

    core_api = check_core_api()

    ui = check_ui()

    comfyui = check_comfyui()

    ollama = check_ollama()

    workflows = check_workflows()

    comfy_paths = check_comfy_paths()


    blockers = []


    # ------------------------------------------------------
    # HARD BLOCKERS (ArchitectOS-owned or local files)
    # ------------------------------------------------------

    if not core_api["ok"]:

        blockers.append(
            "CORE_API not reachable at " + core_api["url"]
        )

    if not workflows["ok"]:

        blockers.append(
            "missing workflow file(s): "
            + ", ".join(workflows["missing"])
        )

    if not comfy_paths["ok"]:

        blockers.append(
            "missing ComfyUI path(s): "
            + ", ".join(comfy_paths["missing"])
        )


    # ------------------------------------------------------
    # EXTERNAL DEGRADATION (detected, never auto-started)
    # ------------------------------------------------------

    external_degraded = []

    if not comfyui["ok"]:

        external_degraded.append(
            "COMFYUI not reachable at " + comfyui["url"]
        )

    if not ollama["ok"]:

        external_degraded.append(
            "OLLAMA not reachable at " + ollama["url"]
        )


    chat_ready = (
        core_api["ok"]
        and ui["ok"]
    )

    render_ready = (
        core_api["ok"]
        and comfyui["ok"]
        and workflows["ok"]
        and comfy_paths["ok"]
    )


    return {

        "preflight":
            "ARCHITECTOS_RUNTIME_FOUNDATION_01",

        "checked_at":
            time.time(),

        "config":
            RC.as_dict(),

        "services": {

            "CORE_API":
                core_api,

            "UI":
                ui,

            "COMFYUI":
                comfyui,

            "OLLAMA":
                ollama,

        },

        "files": {

            "WORKFLOWS":
                workflows,

            "COMFY_PATHS":
                comfy_paths,

        },

        "chat_ready":
            chat_ready,

        "render_ready":
            render_ready,

        "ok":
            not blockers,

        "blockers":
            blockers,

        "external_degraded":
            external_degraded,

    }



# ==========================================================
# TEXT REPORT
# ==========================================================

def _line(
    label,
    ok,
    detail=""
):

    mark = "[ OK ]" if ok else "[FAIL]"

    return (
        "  "
        + mark
        + " "
        + label.ljust(18)
        + str(detail or "")
    )


def format_report(
    result
):

    services = result["services"]

    files = result["files"]

    lines = []


    lines.append("=" * 62)

    lines.append("   ARCHITECTOS RUNTIME PREFLIGHT")

    lines.append("=" * 62)


    lines.append("")

    lines.append("SERVICES")


    for key in (
        "CORE_API",
        "UI",
        "COMFYUI",
        "OLLAMA",
    ):

        service = services[key]

        detail = service["url"]

        if service.get("detail"):

            detail += "  (" + str(service["detail"]) + ")"

        if not service["ok"] and service.get("error"):

            detail += "  <- " + str(service["error"])

        lines.append(
            _line(
                service["name"],
                service["ok"],
                detail
            )
        )


    lines.append("")

    lines.append("WORKFLOW FILES")


    for entry in files["WORKFLOWS"]["files"]:

        lines.append(
            _line(
                entry["name"],
                entry["exists"],
                entry["path"]
            )
        )


    lines.append("")

    lines.append("COMFY PATHS")


    for entry in files["COMFY_PATHS"]["paths"]:

        lines.append(
            _line(
                entry["key"],
                entry["exists"],
                entry["path"]
            )
        )


    lines.append("")

    lines.append("=" * 62)

    lines.append(
        "CHAT READY   : "
        + ("YES" if result["chat_ready"] else "NO")
    )

    lines.append(
        "RENDER READY : "
        + ("YES" if result["render_ready"] else "NO")
    )


    if result["blockers"]:

        lines.append("")

        lines.append("BLOCKERS")

        for blocker in result["blockers"]:

            lines.append("  - " + blocker)


    if result["external_degraded"]:

        lines.append("")

        lines.append("EXTERNAL DEGRADED (not auto-started)")

        for item in result["external_degraded"]:

            lines.append("  - " + item)


    lines.append("")

    lines.append(
        "OVERALL: "
        + (
            "RUNTIME_FOUNDATION_01_PASS"
            if result["ok"]
            else "RUNTIME_FOUNDATION_01_BLOCKED"
        )
    )

    lines.append("=" * 62)


    return "\n".join(lines)



# ==========================================================
# CLI
# ==========================================================

def main():

    import sys


    as_json = "--json" in sys.argv

    quiet = "--quiet" in sys.argv


    result = run_preflight()


    if as_json:

        print(
            json.dumps(
                result,
                indent=4
            )
        )

    elif not quiet:

        print(
            format_report(result)
        )


    return 0 if result["ok"] else 1



if __name__ == "__main__":

    import sys

    sys.exit(
        main()
    )
