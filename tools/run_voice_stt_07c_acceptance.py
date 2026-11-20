# ==========================================================
# VOICE_07C — PERSIAN STT ACCURACY : TARGETED ACCEPTANCE
#
# Verifies the properties that the offline comparison actually
# PROVED, on the SAME saved real human recordings. It deliberately
# does NOT assert that the transcript equals the target sentence,
# because that is exactly what the comparison could not establish.
#
# Runs the real worker through its real JSON contract.
# Zero ComfyUI / zero renders (nothing here can reach ComfyUI).
#
# Usage: <system python 3.11> tools/run_voice_stt_07c_acceptance.py
# ==========================================================


import hashlib
import json
import os
import subprocess
import sys
import time


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SYSTEM_PYTHON = os.environ.get("ARCHITECTOS_VOICE_PYTHON", sys.executable)

WORKER = os.path.join(REPO, "tools", "whisper_stt_worker.py")

REPORT = os.path.join(REPO, "tools", "acceptance_07c_report.json")

ARCH_PROMPT = "سلام. پروژه معماری. پلان. طراحی. معماری. تصویر. رندر. پروژه من."

RECORDINGS = {
    "030": os.path.join(
        REPO, "data", "projects", "project_23e5dae6", "documents",
        "voice_030_9e1635.webm",
    ),
    "275": os.path.join(
        REPO, "data", "projects", "project_23e5dae6", "documents",
        "voice_275_c9bc97.webm",
    ),
}


RESULTS = []


def check(name, passed, detail=None, **extra):

    entry = {
        "name": name,
        "passed": bool(passed),
        "detail": detail,
    }

    entry.update(extra)

    RESULTS.append(entry)

    print("[%s] %-46s %s"
          % ("PASS" if passed else "FAIL", name,
             "" if detail is None else str(detail)[:110]),
          flush=True)

    return passed


def sha256(path):

    digest = hashlib.sha256()

    with open(path, "rb") as handle:

        for block in iter(lambda: handle.read(65536), b""):

            digest.update(block)

    return digest.hexdigest()


def call_worker(audio_path, language="fa", **options):

    request = {
        "audio_path": audio_path,
        "language": language,
        "model": "large-v3-turbo",
    }

    request.update(options)

    completed = subprocess.run(
        [SYSTEM_PYTHON, WORKER],
        input=json.dumps(request),
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

    return payload or {"status": "no_output",
                       "stderr": (completed.stderr or "")[-300:]}


def persian_chars(text):

    return sum(1 for c in str(text or "") if "\u0600" <= c <= "\u06FF")


def load_worker_module():

    """Import the worker so its pure guard functions can be unit-tested.

    The worker only imports stdlib at module level, so this is safe.
    """

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "architectos_whisper_stt_worker", WORKER
    )

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    return module


def main():

    started = time.strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 74)
    print("  VOICE_07C — TARGETED ACCEPTANCE")
    print("=" * 74, flush=True)

    evidence = {"recordings": {}}

    # ---- 1. source recordings are never modified ----------------
    before = {key: sha256(path) for key, path in RECORDINGS.items()}

    for key in ("030", "275"):

        print("\n--- %s ---" % key, flush=True)

        path = RECORDINGS[key]

        fa = call_worker(path, language="fa")

        evidence["recordings"].setdefault(key, {})["fa"] = fa

        preprocessing = fa.get("audio_preprocessing") or {}

        check("%s preprocessing applied" % key,
              preprocessing.get("applied") is True,
              preprocessing.get("note"))

        check("%s original audio preserved" % key,
              preprocessing.get("original_audio_preserved") is True)

        check("%s natural leading pause detected" % key,
              (preprocessing.get("trimmed_seconds") or 0) > 1.5,
              "trimmed %.2f s of %.2f s"
              % (preprocessing.get("trimmed_seconds") or 0,
                 preprocessing.get("source_duration") or 0))

        check("%s resampled to 16 kHz mono" % key,
              preprocessing.get("resampled_hz") == 16000
              and preprocessing.get("channels") == 1)

        check("%s first phoneme preserved" % key,
              preprocessing.get("first_phoneme_preserved") is True)

        check("%s no initial_prompt by default" % key,
              fa.get("initial_prompt_used") is False)

        # the proven improvement: Persian script instead of Latin garbage
        text = fa.get("transcript") or fa.get("raw_transcript") or ""

        check("%s Persian script produced (was Latin garbage)" % key,
              persian_chars(text) > 0,
              repr(text))

        # ---- 07D confidence gate ---------------------------------
        # These two real recordings are KNOWN-WRONG (semantic
        # substitution). The model's own word probabilities must catch
        # that without any target vocabulary.
        check("%s known-wrong Persian is rejected (low confidence)" % key,
              fa.get("status") == "unusable_transcript"
              and fa.get("reason") == "low_confidence_detected",
              "mean_wp=%s min_wp=%s status=%s"
              % (fa.get("mean_word_probability"),
                 fa.get("min_word_probability"), fa.get("status")))

        check("%s low-confidence transcript is not exposed" % key,
              fa.get("transcript") is None
              and bool(fa.get("raw_transcript")),
              "raw preserved=%s" % bool(fa.get("raw_transcript")))

        # ---- repetition guard ----------------------------------
        # The guard is validated as a CONTRACT, not by demanding that
        # every clip loops: a clip whose decode is clean must stay
        # usable, and a clip whose decode loops must be rejected.
        loop = call_worker(path, language="fa",
                           initial_prompt=ARCH_PROMPT, beam_size=5)

        evidence["recordings"][key]["guarded_attempt"] = loop

        compression = loop.get("compression_ratio")
        unique = loop.get("unique_word_ratio")
        words = len(str(loop.get("raw_transcript") or "").split())
        mean_wp = loop.get("mean_word_probability")
        min_wp = loop.get("min_word_probability")

        loops = bool(
            (compression is not None and compression > 2.4)
            or (unique is not None and words >= 6 and unique < 0.35)
        )

        low_conf = bool(
            (mean_wp is not None and mean_wp < 0.75)
            or (min_wp is not None and min_wp < 0.60)
        )

        check("%s guards match measurement" % key,
              (loop.get("status") == "unusable_transcript")
              == (loops or low_conf),
              "comp=%s uniq=%s mean_wp=%s status=%s"
              % (compression, unique, mean_wp, loop.get("status")))

        if key == "030":

            # The 030 clip is the one that actually produced the
            # observed repetition loop in the offline comparison.
            check("%s observed repetition loop is rejected" % key,
                  loops
                  and loop.get("status") == "unusable_transcript"
                  and loop.get("reason") == "repetition_detected",
                  "status=%s reason=%s" % (loop.get("status"),
                                           loop.get("reason")))

        # ---- unusable output can never become the transcript ----
        quality = loop.get("quality") or {}

        check("%s unusable decode never becomes the transcript" % key,
              (loop.get("transcript") is None)
              == (quality.get("usable") is False),
              "usable=%s transcript_set=%s"
              % (quality.get("usable"), loop.get("transcript") is not None))

        check("%s raw transcript preserved for diagnostics" % key,
              bool(loop.get("raw_transcript")),
              repr(str(loop.get("raw_transcript"))[:60]))

        # ---- auto detection is reported truthfully --------------
        auto = call_worker(path, language="auto")

        evidence["recordings"][key]["auto"] = auto

        check("%s auto path reports a language truthfully" % key,
              bool(auto.get("detected_language")),
              "detected=%s" % auto.get("detected_language"))

    # ---- guard unit checks (pure functions, deterministic) ------
    print("\n--- guard unit checks ---", flush=True)

    guards = load_worker_module()

    latin = guards.assess_quality(
        "Sálán, próbé marók og skerði.",
        {}, None, "fa",
        mean_word_probability=0.99, min_word_probability=0.95,
        avg_logprob=-0.30,
    )

    check("script guard rejects Latin output when fa requested",
          latin["script_mismatch_suspected"] is True
          and latin["usable"] is False)

    persian = guards.assess_quality(
        "سلام پروژه من",
        {}, None, "fa",
        mean_word_probability=0.99, min_word_probability=0.95,
        avg_logprob=-0.30,
    )

    check("script guard accepts Persian output",
          persian["script_mismatch_suspected"] is False
          and persian["usable"] is True)

    confident = guards.assess_quality(
        "سلام پروژه من رو باز کردی",
        {}, None, "fa",
        mean_word_probability=0.99, min_word_probability=0.95,
        avg_logprob=-0.30,
    )

    check("confidence gate accepts high-confidence text",
          confident["low_confidence_suspected"] is False
          and confident["usable"] is True)

    unsure = guards.assess_quality(
        "سلام پروژه من",
        {}, None, "fa",
        mean_word_probability=0.55, min_word_probability=0.40,
        avg_logprob=-0.30,
    )

    check("confidence gate rejects low-confidence text",
          unsure["low_confidence_suspected"] is True
          and unsure["usable"] is False)

    echoed = guards.assess_quality(
        "سلام. پروژه معماری.",
        {}, "سلام. پروژه معماری.", "fa",
        mean_word_probability=0.99, min_word_probability=0.95,
        avg_logprob=-0.30,
    )

    check("prompt-echo guard rejects the prompt itself",
          echoed["prompt_echo_suspected"] is True
          and echoed["usable"] is False)

    looping = guards.assess_quality(
        "سلام سلام سلام سلام سلام سلام سلام",
        {"compression_ratio": 9.5}, None, "fa",
        mean_word_probability=0.99, min_word_probability=0.95,
        avg_logprob=-0.30,
    )

    check("repetition guard rejects a compression loop",
          looping["repetition_suspected"] is True
          and looping["usable"] is False)

    # ---- 2. positive control: known-good English is NOT rejected ----
    # The confidence gate must not create false rejections on reliable
    # speech. These clips were transcribed correctly by the VOICE_07
    # acceptance.
    print("\n--- positive control (known-correct English) ---", flush=True)

    evidence["english_controls"] = {}

    for name in ("en_b.wav", "en_b2.wav", "en_h.wav"):

        path = os.path.join(REPO, ".pytest_tmp", "voice", name)

        if not os.path.isfile(path):

            continue

        result = call_worker(path, language="en")

        evidence["english_controls"][name] = result

        check("%s correct English accepted (no false reject)" % name,
              result.get("status") == "ok"
              and bool(result.get("transcript")),
              "mean_wp=%s | %s" % (result.get("mean_word_probability"),
                                   result.get("transcript")))

    # ---- 3. sources byte-identical after everything ------------
    after = {key: sha256(path) for key, path in RECORDINGS.items()}

    for key in ("030", "275"):

        check("%s source recording byte-identical" % key,
              before[key] == after[key], after[key][:16])

    passed = sum(1 for r in RESULTS if r["passed"])
    total = len(RESULTS)

    report = {
        "phase": "VOICE_07C",
        "started_at": started,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "real_renders": 0,
        "comfy_invocations": 0,
        "checks": RESULTS,
        "passed": passed,
        "total": total,
        "source_sha256_before": before,
        "source_sha256_after": after,
        "evidence": evidence,
    }

    with open(REPORT, "w", encoding="utf-8") as handle:

        json.dump(report, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 74)
    print("VOICE_07C targeted acceptance: %d / %d checks passed" %
          (passed, total))
    print("report -> tools/acceptance_07c_report.json")
    print("=" * 74)

    return 0 if passed == total else 1


if __name__ == "__main__":

    sys.exit(main())
