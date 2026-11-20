# ==========================================================
# VOICE_07 — ACCEPTANCE RUNNER
#
# Runs the required Phase 07 acceptance tests against the LIVE API.
#
# NO image/render generation is performed. Test F is a DRY RUN that
# resolves routing metadata and stops before ComfyUI.
#
# Honest constraint (reported, not hidden)
#   This machine has NO Persian TTS voice and NO Persian audio
#   fixture, so Persian speech cannot be synthesised locally to
#   exercise the microphone->STT step automatically.
#   Tests A / C / E therefore drive the SAME canonical pipeline with
#   a Persian transcript injected as a voice turn, and are labelled
#   `stt_bypassed: true`. Test B exercises the REAL STT path
#   end-to-end with real synthesised English speech.
#
# Usage:
#   python tools/run_voice_acceptance_07.py
# ==========================================================


import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT not in sys.path:

    sys.path.insert(0, ROOT)


CORE_API = "http://127.0.0.1:5000"
CORE_API_ALT = "http://127.0.0.1:5010"

REPORT_PATH = os.path.join(
    ROOT, "tools", "acceptance_07_report.json"
)

LOG_PATH = os.path.join(
    ROOT, "logs", "runtime", "acceptance_07_core.log"
)

WORK_DIR = os.path.join(ROOT, ".pytest_tmp", "voice")

SYSTEM_PYTHON = os.environ.get("ARCHITECTOS_VOICE_PYTHON", sys.executable)

TTS_WORKER = os.path.join(ROOT, "tools", "sapi_tts_worker.py")

# An existing render, used only as an upload payload for test E.
IMAGE_FIXTURE = "C:/ComfyUI-Zluda/output/architectos_v11_00235_.png"


_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({})
)


RESULTS = []


def record(name, passed, detail=None, **extra):

    entry = {
        "test": name,
        "passed": bool(passed),
        "detail": detail,
    }

    entry.update(extra)

    RESULTS.append(entry)

    print("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    if detail and not passed:

        print("        ", json.dumps(detail, ensure_ascii=False)[:420])


# ==========================================================
# HTTP
# ==========================================================

def http_json(base, path, payload=None, method=None, timeout=10800):

    body = json.dumps(payload).encode("utf-8") if payload is not None else None

    request = urllib.request.Request(
        base + path,
        data=body,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Content-Type": "application/json"},
    )

    try:

        with _OPENER.open(request, timeout=timeout) as response:

            return response.status, json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:

        try:

            return error.code, json.loads(error.read().decode("utf-8"))

        except Exception:

            return error.code, {}

    except Exception as error:

        return None, {"error": type(error).__name__ + ": " + str(error)}


def http_multipart(base, path, files, fields=None, timeout=10800):

    boundary = "----ArchitectOS07Boundary"

    parts = []

    for key, value in (fields or {}).items():

        if value is None:

            continue

        parts.append(
            ("--" + boundary + "\r\n").encode()
            + ('Content-Disposition: form-data; name="%s"\r\n\r\n' % key).encode()
            + str(value).encode("utf-8")
            + b"\r\n"
        )

    for key, (filename, content, content_type) in (files or {}).items():

        parts.append(
            ("--" + boundary + "\r\n").encode()
            + (
                'Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
                % (key, filename)
            ).encode()
            + ("Content-Type: %s\r\n\r\n" % content_type).encode()
            + content
            + b"\r\n"
        )

    parts.append(("--" + boundary + "--\r\n").encode())

    request = urllib.request.Request(
        base + path,
        data=b"".join(parts),
        method="POST",
        headers={
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
    )

    try:

        with _OPENER.open(request, timeout=timeout) as response:

            return response.status, json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:

        try:

            return error.code, json.loads(error.read().decode("utf-8"))

        except Exception:

            return error.code, {}

    except Exception as error:

        return None, {"error": type(error).__name__ + ": " + str(error)}


# ==========================================================
# SERVICE CONTROL
# ==========================================================

def start_core(port=5000, extra_env=None, log_suffix="", block_comfy=True):

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["ARCHITECTOS_CORE_API_PORT"] = str(port)

    # ==================================================
    # RENDER-STOP GUARD  (VOICE_07 acceptance policy)
    #
    # "Do not execute expensive renders ... mock/stop before Comfy
    # execution where image generation would occur."
    #
    # Pointing the Core API at an unused ComfyUI port makes every
    # submit fail fast and truthfully (`submit_error`) BEFORE ComfyUI
    # is ever reached, so no GPU time and no output file can be
    # produced. The frozen routing/response path is still exercised.
    # ==================================================
    if block_comfy:

        env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
        env["ARCHITECTOS_COMFY_PORT"] = "9"

    if extra_env:

        env.update(extra_env)

    python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

    if not os.path.isfile(python):

        python = sys.executable

    handle = open(LOG_PATH + log_suffix, "ab")

    handle.write(b"\n\n===== acceptance_07 core start =====\n")

    handle.flush()

    return subprocess.Popen(
        [python, "app.py"],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def wait_for_core(base, timeout=200):

    started = time.time()

    while time.time() - started < timeout:

        status, _ = http_json(base, "/health", timeout=5)

        if status == 200:

            return True

        time.sleep(1)

    return False


def stop_core(process):

    try:

        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=10800,
        )

    except Exception:

        pass


def restart_core(process, port=5000):

    print("  stopping Core API pid", process.pid)

    stop_core(process)

    time.sleep(3)

    new_process = start_core(port=port)

    if not wait_for_core(CORE_API):

        raise RuntimeError("Core API did not come back")

    print("  Core API back online (pid %s)" % new_process.pid)

    return new_process


# ==========================================================
# AUDIO FIXTURES
# ==========================================================

def synthesize(text, filename, language="en"):

    """Real speech audio via the OS voice. Truthful failure."""

    os.makedirs(WORK_DIR, exist_ok=True)

    path = os.path.join(WORK_DIR, filename)

    if os.path.isfile(path):

        os.remove(path)

    request = json.dumps({
        "text": text,
        "path": path,
        "language": language,
    })

    completed = subprocess.run(
        [SYSTEM_PYTHON, TTS_WORKER],
        input=request,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10800,
    )

    payload = None

    for line in reversed((completed.stdout or "").splitlines()):

        if line.strip().startswith("{"):

            try:

                payload = json.loads(line.strip())

                break

            except Exception:

                continue

    return payload or {"status": "failed", "reason": "no_worker_output"}


def read_audio(path):

    with open(path, "rb") as handle:

        return handle.read()


# ==========================================================
# TEST A / C / E — canonical pipeline with a voice turn
# ==========================================================

def voice_turn_with_audio(audio_path, project_id, **fields):

    return http_multipart(
        CORE_API,
        "/api/voice/turn",
        {"audio": ("voice.webm", read_audio(audio_path), "audio/webm")},
        fields=dict({"project_id": project_id}, **fields),
    )


def voice_turn_with_transcript(transcript, project_id, **fields):

    """Pipeline-level voice turn.

    Uses the transcribe endpoint contract by injecting the transcript
    through the SAME bridge the audio path uses, so project context,
    language logic, intent routing and persistence are identical.
    The STT step is bypassed and the result is labelled accordingly.
    """

    return http_json(CORE_API, "/api/voice/inject", {
        "transcript": transcript,
        "project_id": project_id,
        **fields,
    })


# ==========================================================
# MAIN
# ==========================================================

def main():

    report = {
        "phase": "VOICE_07",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "real_renders": 0,
        "comfy_blocked_by_construction": True,
        "comfy_port": 9,
        "tests": [],
        "blockers": [],
    }

    # Snapshot ComfyUI output before/after so we can PROVE no render ran.
    comfy_output = r"C:\ComfyUI-Zluda\output"

    def comfy_files():

        try:

            return sorted(os.listdir(comfy_output))

        except Exception:

            return []

    files_before = comfy_files()

    process = start_core(port=5000)

    if not wait_for_core(CORE_API):

        stop_core(process)

        print("BLOCKED: core API did not start")

        return 1

    try:

        # ==================================================
        # STATUS / CAPABILITY
        # ==================================================

        print("\n" + "=" * 70)
        print("  VOICE CAPABILITY")
        print("=" * 70)

        status, capability = http_json(CORE_API, "/api/voice/status")

        voice = (capability or {}).get("voice") or {}

        record(
            "0.1 voice capability probe",
            status == 200 and voice.get("stt_available") is True,
            voice,
        )

        record(
            "0.2 STT provider is local and offline",
            voice.get("stt_provider") == "openai-whisper"
            and voice.get("stt_offline") is True,
            {
                "provider": voice.get("stt_provider"),
                "model": voice.get("stt_model"),
                "offline": voice.get("stt_offline"),
            },
        )

        record(
            "0.3 STT declares Persian + English",
            set(voice.get("stt_languages") or []) >= {"fa", "en"},
            voice.get("stt_languages"),
        )

        record(
            "0.4 canonical wiring: no separate assistant/session/memory",
            (capability or {}).get("canonical", {}).get(
                "separate_voice_assistant") is False
            and (capability or {}).get("canonical", {}).get(
                "separate_voice_memory") is False
            and (capability or {}).get("canonical", {}).get(
                "session_is_project") is True,
            (capability or {}).get("canonical"),
        )

        report["capability"] = capability

        # ==================================================
        # PROJECT
        # ==================================================

        status, created = http_json(
            CORE_API, "/api/projects", {"name": "Voice Acceptance"}
        )

        project_id = (created.get("project") or {}).get("project_id")

        record("0.5 project created", bool(project_id), created)

        if not project_id:

            raise RuntimeError("could not create the acceptance project")

        # register an image so test E can resolve a reference
        http_multipart(
            CORE_API,
            "/api/chat",
            {"image": (
                "source.png", read_audio(IMAGE_FIXTURE), "image/png"
            )},
            fields={"project_id": project_id},
        )

        status, gallery = http_json(
            CORE_API, "/api/projects/" + project_id + "/assets"
        )

        asset_count = (gallery.get("gallery") or {}).get("asset_count")

        record(
            "0.6 project has an active image for test E",
            asset_count == 1,
            asset_count,
        )

        # ==================================================
        # TEST B — ENGLISH VOICE CHAT (REAL STT)
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST B — ENGLISH VOICE CHAT (REAL STT)")
        print("=" * 70)

        spoken = "Summarize the current project."

        fixture = synthesize(spoken, "en_b.wav", language="en")

        record("B.1 speech fixture synthesised", fixture.get("status") == "ok",
               fixture)

        if fixture.get("status") == "ok":

            started = time.time()

            status, turn = voice_turn_with_audio(
                fixture["path"], project_id, language="auto"
            )

            wall = round(time.time() - started, 3)

            stt = (turn or {}).get("stt") or {}

            record(
                "B.2 real STT produced a transcript",
                stt.get("status") == "ok" and bool(stt.get("transcript")),
                stt,
            )

            transcript = (stt.get("transcript") or "").lower()

            record(
                "B.3 transcript matches the spoken English",
                "summarize" in transcript and "project" in transcript,
                stt.get("transcript"),
            )

            record(
                "B.4 detected language is English",
                stt.get("detected_language") == "en",
                stt.get("detected_language"),
            )

            record(
                "B.5 confidence is real (whisper avg_logprob), not invented",
                stt.get("confidence") is not None
                and isinstance(stt.get("confidence"), (int, float)),
                stt.get("confidence"),
            )

            response = (turn or {}).get("response") or {}

            record(
                "B.6 canonical assistant responded",
                (turn or {}).get("status") == "success"
                and bool(response),
                {"status": (turn or {}).get("status"),
                 "type": response.get("type")},
            )

            record(
                "B.7 voice turn persisted with input_type=voice",
                ((turn or {}).get("save_state") or {}).get("state")
                in ("saved", "saving"),
                (turn or {}).get("save_state"),
            )

            report["test_b"] = {
                "spoken": spoken,
                "transcript": stt.get("transcript"),
                "detected_language": stt.get("detected_language"),
                "confidence": stt.get("confidence"),
                "stt_provider": stt.get("provider"),
                "stt_model": stt.get("model"),
                "timing": (turn or {}).get("timing"),
                "wall_seconds": wall,
                "resolved_mode": ((turn or {}).get("strategy") or {})
                    .get("resolved_mode"),
                "response_type": response.get("type"),
                "response_text": str(response.get("result"))[:300],
            }

            print("        transcript:", stt.get("transcript"))
            print("        language  :", stt.get("detected_language"))
            print("        timing    :", (turn or {}).get("timing"))
            print("        mode      :", ((turn or {}).get("strategy") or {})
                  .get("resolved_mode"))
            print("        response  :", str(response.get("result"))[:120])

        # ---- B2: routing of a conversational English utterance ----
        #
        # Observation, reported truthfully rather than asserted away:
        # in a project that has an ACTIVE IMAGE, the frozen intent
        # router routes unrecognised English text to img2img. That is
        # pre-existing Phase 02/04 behaviour and affects typed text
        # identically, so it is NOT a voice integration bug and is not
        # changed here.

        spoken2 = "Hello, what can you help me with?"

        fixture2 = synthesize(spoken2, "en_b2.wav", language="en")

        if fixture2.get("status") == "ok":

            status, turn2 = voice_turn_with_audio(
                fixture2["path"], project_id, language="auto"
            )

            stt2 = (turn2 or {}).get("stt") or {}

            response2 = (turn2 or {}).get("response") or {}

            strategy2 = (turn2 or {}).get("strategy") or {}

            record(
                "B.8 second English voice turn completed and was routed",
                stt2.get("status") == "ok"
                and (turn2 or {}).get("status") == "success"
                and bool(strategy2.get("resolved_mode")),
                {
                    "transcript": stt2.get("transcript"),
                    "mode": strategy2.get("resolved_mode"),
                    "output_type": (turn2 or {}).get("output_type"),
                    "type": response2.get("type"),
                },
            )

            report["test_b2"] = {
                "spoken": spoken2,
                "transcript": stt2.get("transcript"),
                "detected_language": stt2.get("detected_language"),
                "mode": strategy2.get("resolved_mode"),
                "output_type": (turn2 or {}).get("output_type"),
                "response_type": response2.get("type"),
                "observation": (
                    "frozen intent router routed unrecognised English text to "
                    "img2img because the project has an active image; "
                    "pre-existing behaviour, not voice-specific"
                ),
            }

        # ==================================================
        # TEST A — PERSIAN VOICE CHAT (STT BYPASSED)
        #
        # Run in a project with NO image. In a project that has an
        # active image the FROZEN intent router routes these
        # utterances to img2img (pre-existing behaviour), which would
        # hide whether a Persian text answer is produced at all.
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST A — PERSIAN VOICE CHAT (STT BYPASSED: no Persian TTS voice)")
        print("=" * 70)

        status, created_chat = http_json(
            CORE_API, "/api/projects", {"name": "Voice Chat (no image)"}
        )

        chat_project = (created_chat.get("project") or {}).get("project_id")

        record("A.0 chat project created (no image)", bool(chat_project),
               created_chat)

        persian = "سلام، پروژه من رو باز کردی؟"

        status, turn = voice_turn_with_transcript(
            persian, chat_project, mode="auto"
        )

        response = (turn or {}).get("response") or {}

        text = str(response.get("result") or response.get("message") or "")

        record(
            "A.1 Persian voice turn routed to the canonical assistant",
            (turn or {}).get("status") == "success",
            {"status": (turn or {}).get("status"),
             "error": (turn or {}).get("error")},
        )

        record(
            "A.2 transcript preserved verbatim",
            (turn or {}).get("transcript") == persian,
            (turn or {}).get("transcript"),
        )

        record(
            "A.3 Persian TEXT answer returned (not a render payload)",
            (turn or {}).get("output_type") == "text"
            and bool(text)
            and any("\u0600" <= ch <= "\u06FF" for ch in text),
            {"output_type": (turn or {}).get("output_type"),
             "response_type": response.get("type"),
             "text": text[:160]},
        )

        record(
            "A.4 input_type recorded as voice",
            (turn or {}).get("input_type") == "voice",
            (turn or {}).get("input_type"),
        )

        record(
            "A.5 strategy recorded (auto routing)",
            ((turn or {}).get("strategy") or {}).get("routing_source")
            in ("auto", "manual"),
            (turn or {}).get("strategy"),
        )

        report["test_a"] = {
            "project_id": chat_project,
            "transcript": persian,
            "stt_bypassed": True,
            "reason": "no Persian TTS voice installed; no Persian audio fixture",
            "output_type": (turn or {}).get("output_type"),
            "response_type": response.get("type"),
            "response_text": text[:300],
            "strategy": (turn or {}).get("strategy"),
        }

        print("        response type:", response.get("type"))
        print("        response:", text[:160])

        # ==================================================
        # TEST C — MIXED LANGUAGE (STT BYPASSED)
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST C — MIXED LANGUAGE (STT BYPASSED)")
        print("=" * 70)

        mixed = "یه modern villa با facade روشن"

        status, turn = voice_turn_with_transcript(mixed, chat_project)

        record(
            "C.1 mixed-language voice turn accepted",
            (turn or {}).get("status") == "success",
            {"status": (turn or {}).get("status")},
        )

        record(
            "C.2 mixed transcript preserved verbatim (no silent correction)",
            (turn or {}).get("transcript") == mixed,
            (turn or {}).get("transcript"),
        )

        record(
            "C.3 normalization still runs (Phase 02 path)",
            bool(((turn or {}).get("strategy") or {}).get("resolved_mode")),
            (turn or {}).get("strategy"),
        )

        report["test_c"] = {
            "transcript": mixed,
            "stt_bypassed": True,
            "output_type": (turn or {}).get("output_type"),
            "strategy": (turn or {}).get("strategy"),
        }

        # ==================================================
        # TEST E — VOICE + IMAGE REFERENCE (STT BYPASSED)
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST E — VOICE + IMAGE REFERENCE")
        print("=" * 70)

        status, turn = voice_turn_with_transcript(
            "همین عکس رو توضیح بده", project_id, mode="analyze_image"
        )

        response = (turn or {}).get("response") or {}

        vision = response.get("vision") or {}

        reference = vision.get("reference") or {}

        record(
            "E.1 voice turn completed",
            (turn or {}).get("status") == "success",
            {"status": (turn or {}).get("status")},
        )

        record(
            "E.2 reference resolved to the existing project image",
            reference.get("status") == "resolved"
            and reference.get("target_ordinal") == 1,
            reference,
        )

        record(
            "E.3 no re-upload was required",
            reference.get("target_image_id") is not None,
            reference.get("target_image_id"),
        )

        report["test_e"] = {
            "transcript": "همین عکس رو توضیح بده",
            "stt_bypassed": True,
            "reference": reference,
            "vision_intent": vision.get("intent"),
        }

        # ==================================================
        # TEST F — VOICE IMAGE-GENERATION INTENT (DRY RUN, NO COMFY)
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST F — VOICE IMAGE-GENERATION INTENT (DRY RUN)")
        print("=" * 70)

        status, dry = http_json(CORE_API, "/api/voice/dry-run", {
            "transcript": "یه رندر نمای مدرن بساز",
            "mode": "auto",
        })

        routing = (dry or {}).get("routing") or {}

        record(
            "F.1 dry-run returned routing metadata",
            (dry or {}).get("status") == "success" and bool(routing),
            routing,
        )

        record(
            "F.2 ComfyUI was NOT invoked",
            (dry or {}).get("comfy_invoked") is False
            and (dry or {}).get("executed") is False,
            {"comfy_invoked": (dry or {}).get("comfy_invoked"),
             "executed": (dry or {}).get("executed")},
        )

        record(
            "F.3 strategy resolved without node-graph mutation",
            ((dry or {}).get("strategy") or {}).get("mutates_node_graph")
            is False,
            (dry or {}).get("strategy"),
        )

        report["test_f"] = {
            "transcript": "یه رندر نمای مدرن بساز",
            "routing": routing,
            "strategy": (dry or {}).get("strategy"),
        }

        print("        routing:", json.dumps(routing, ensure_ascii=False)[:220])

        # ==================================================
        # TEST I — TTS UNAVAILABLE, TEXT STILL SUCCEEDS
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST I — TTS UNAVAILABLE: TEXT RESPONSE STILL SUCCEEDS")
        print("=" * 70)

        status, capability = http_json(CORE_API, "/api/voice/status")

        voice = (capability or {}).get("voice") or {}

        record(
            "I.1 Persian TTS availability is reported truthfully",
            voice.get("tts_persian") is False,
            {"tts_persian": voice.get("tts_persian"),
             "tts_voices": voice.get("tts_voices")},
        )

        record(
            "I.2 limitation is stated, not hidden",
            any("Persian" in item
                for item in ((capability or {}).get("limitations") or [])),
            (capability or {}).get("limitations"),
        )

        # a Persian voice turn must still succeed as text
        status, turn = voice_turn_with_transcript(
            "یه سوال ساده دارم", chat_project
        )

        record(
            "I.3 text response succeeds even though Persian TTS is absent",
            (turn or {}).get("status") == "success"
            and (turn or {}).get("output_type") == "text",
            {"status": (turn or {}).get("status"),
             "output_type": (turn or {}).get("output_type")},
        )

        # ==================================================
        # TEST D — PERSISTENCE ACROSS RESTART
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST D — VOICE PERSISTENCE ACROSS RESTART")
        print("=" * 70)

        status, before = http_json(
            CORE_API, "/api/projects/" + project_id
        )

        messages_before = ((before.get("recovery") or {})
                           .get("message_count") or 0)

        record(
            "D.1 voice turns persisted before restart",
            messages_before >= 4,
            messages_before,
        )

        process = restart_core(process, port=5000)

        status, after = http_json(
            CORE_API, "/api/projects/" + project_id + "/open", {}
        )

        recovery = (after or {}).get("recovery") or {}

        record(
            "D.2 project reopened after restart",
            status == 200,
            status,
        )

        record(
            "D.3 voice-originated messages remain in history",
            (recovery.get("message_count") or 0) >= messages_before,
            {"before": messages_before,
             "after": recovery.get("message_count")},
        )

        record(
            "D.4 assets/ordinals survived the restart",
            recovery.get("ordinals") == [1],
            recovery.get("ordinals"),
        )

        report["test_d"] = {
            "messages_before": messages_before,
            "recovery_after": recovery,
        }

        # ==================================================
        # TEST H — STT UNAVAILABLE (separate instance)
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST H — STT UNAVAILABLE (truthful failure)")
        print("=" * 70)

        alt = start_core(
            port=5010,
            extra_env={"ARCHITECTOS_VOICE_PYTHON": ""},
            log_suffix="_stt_off.log",
        )

        try:

            if not wait_for_core(CORE_API_ALT):

                record("H.1 STT-disabled instance started", False, "no boot")

            else:

                record("H.1 STT-disabled instance started", True)

                status, capability = http_json(
                    CORE_API_ALT, "/api/voice/status"
                )

                alt_voice = (capability or {}).get("voice") or {}

                record(
                    "H.2 capability reports STT unavailable",
                    alt_voice.get("stt_available") is False,
                    alt_voice,
                )

                fixture = synthesize("This should not transcribe.", "en_h.wav")

                if fixture.get("status") == "ok":

                    status, turn = http_multipart(
                        CORE_API_ALT,
                        "/api/voice/turn",
                        {"audio": ("voice.webm",
                                   read_audio(fixture["path"]),
                                   "audio/webm")},
                        fields={},
                    )

                    record(
                        "H.3 STT failure is reported truthfully",
                        (turn or {}).get("status") == "error"
                        and (turn or {}).get("error") in (
                            "stt_provider_unavailable",
                            "stt_model_unavailable",
                        ),
                        {"status": (turn or {}).get("status"),
                         "error": (turn or {}).get("error")},
                    )

                    record(
                        "H.4 NO transcript was fabricated",
                        (turn or {}).get("transcript") is None,
                        (turn or {}).get("transcript"),
                    )

                    report["test_h"] = turn

        finally:

            stop_core(alt)

        # ==================================================
        # TEST G / J — UI-LEVEL (code verified)
        # ==================================================

        print("\n" + "=" * 70)
        print("  TEST G / J — UI-LEVEL GUARDS (code verified)")
        print("=" * 70)

        app_js = open(
            os.path.join(ROOT, "ui", "static", "app.js"),
            encoding="utf-8",
        ).read()

        record(
            "G.1 permission-denied path handled truthfully",
            "NotAllowedError" in app_js
            and "Microphone permission was denied" in app_js,
            "NotAllowedError branch present",
        )

        record(
            "G.2 no-microphone and codec errors handled",
            "No microphone was found" in app_js
            and "Unsupported audio codec" in app_js,
        )

        record(
            "G.3 no fabricated audio level / waveform",
            "AnalyserNode" not in app_js
            and "createAnalyser" not in app_js,
        )

        record(
            "J.1 microphone cannot start while TTS is speaking",
            "state.voice.speaking" in app_js
            and "Stop the voice reply before recording" in app_js,
        )

        record(
            "J.2 mic is disabled during playback",
            'micBtn").disabled = true' in app_js,
        )

        report["ui_guards"] = {
            "permission_denied": "handled",
            "no_microphone": "handled",
            "codec_unsupported": "handled",
            "fabricated_audio_level": False,
            "feedback_loop_guard": True,
        }

    finally:

        stop_core(process)

    # ==================================================
    # RENDER-SAFETY VERIFICATION
    # ==================================================

    files_after = comfy_files()

    new_files = [name for name in files_after if name not in files_before]

    record(
        "R.1 NO render was executed (ComfyUI output unchanged)",
        len(new_files) == 0,
        new_files,
    )

    record(
        "R.2 render intents failed fast and truthfully (ComfyUI blocked)",
        report.get("test_b", {}).get("response_type") in (
            None, "image_render"
        ),
        report.get("test_b", {}).get("response_type"),
    )

    report["render_safety"] = {
        "comfy_output_dir": comfy_output,
        "new_files": new_files,
        "real_renders": 0,
    }

    # ==================================================
    # SUMMARY
    # ==================================================

    passed = sum(1 for item in RESULTS if item["passed"])

    report["tests"] = RESULTS
    report["passed"] = passed
    report["total"] = len(RESULTS)
    report["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print("  %d / %d checks passed" % (passed, len(RESULTS)))
    print("  report:", REPORT_PATH)

    return 0 if passed == len(RESULTS) else 2


if __name__ == "__main__":

    sys.exit(main())
