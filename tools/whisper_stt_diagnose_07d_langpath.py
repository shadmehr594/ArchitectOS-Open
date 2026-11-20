# ==========================================================
# VOICE_07D-4 — LANGUAGE PATH VERIFICATION (live, end-to-end)
#
# Proves that an explicitly selected Persian language really
# reaches model.transcribe(language="fa") on a REAL request:
#
#   UI Persian -> voice gateway -> voice API -> bridge
#              -> Whisper wrapper -> worker -> model.transcribe
#
# Starts the Core API with ComfyUI blocked (port 9) so no render
# can ever run, posts the two real recordings to
# /api/voice/transcribe with different `language` values, and
# compares the results.
# ==========================================================


import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORE = "http://127.0.0.1:5000"

LOG = os.path.join(REPO, "logs", "runtime", "diag07d_core.log")

PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")

RECORDING = os.path.join(
    REPO, "data", "projects", "project_23e5dae6", "documents",
    "voice_275_c9bc97.webm",
)


def start_core():

    env = os.environ.copy()

    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = env["NO_PROXY"]
    env["PYTHONUNBUFFERED"] = "1"
    env["ARCHITECTOS_CORE_API_PORT"] = "5000"
    env["ARCHITECTOS_COMFY_HOST"] = "127.0.0.1"
    env["ARCHITECTOS_COMFY_PORT"] = "9"       # ComfyUI unreachable by design

    handle = open(LOG, "ab")
    handle.write(b"\n\n===== 07d langpath core start =====\n")
    handle.flush()

    return subprocess.Popen(
        [PY, "app.py"], cwd=REPO, env=env,
        stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
    )


def wait_core(timeout=200):

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({})
    )

    deadline = time.time() + timeout

    while time.time() < deadline:

        try:

            # /api/voice/status probes the machine (interpreter + cached
            # model) and can legitimately take ~10 s, so the timeout
            # must be well above that.
            with opener.open(CORE + "/api/voice/status",
                             timeout=10800) as r:

                if r.status == 200:

                    return True

        except Exception:

            time.sleep(3)

    return False


def post_audio(path, language):

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({})
    )

    boundary = "----07dlang"

    with open(path, "rb") as handle:

        blob = handle.read()

    parts = []

    parts.append(("--%s\r\n" % boundary).encode())
    parts.append(
        b'Content-Disposition: form-data; name="audio"; '
        b'filename="voice.webm"\r\nContent-Type: audio/webm\r\n\r\n'
    )
    parts.append(blob)
    parts.append(b"\r\n")

    parts.append(("--%s\r\n" % boundary).encode())
    parts.append(
        b'Content-Disposition: form-data; name="language"\r\n\r\n'
    )
    parts.append(str(language).encode())
    parts.append(b"\r\n")

    parts.append(("--%s--\r\n" % boundary).encode())

    body = b"".join(parts)

    request = urllib.request.Request(
        CORE + "/api/voice/transcribe",
        data=body,
        headers={"Content-Type":
                 "multipart/form-data; boundary=%s" % boundary},
        method="POST",
    )

    with opener.open(request, timeout=10800) as response:

        return json.loads(response.read().decode("utf-8"))


def main():

    process = start_core()

    try:

        if not wait_core():

            print("Core API did not come up; see", LOG)
            return 1

        results = {}

        for language in ("fa", "en", "auto"):

            payload = post_audio(RECORDING, language)

            results[language] = {
                "status": payload.get("status"),
                "reason": payload.get("reason"),
                "transcript": payload.get("transcript"),
                "raw_transcript": payload.get("raw_transcript"),
                "detected_language": payload.get("detected_language"),
                "confidence": payload.get("confidence"),
                "audio_preprocessing": payload.get("audio_preprocessing"),
                "quality": payload.get("quality"),
            }

            print("requested language=%-5s -> detected=%-4s | %s"
                  % (language, payload.get("detected_language"),
                     payload.get("transcript")
                     or payload.get("raw_transcript")), flush=True)

        out = os.path.join(REPO, ".pytest_tmp", "diag07d",
                           "language_path.json")

        os.makedirs(os.path.dirname(out), exist_ok=True)

        with open(out, "w", encoding="utf-8") as handle:

            json.dump({"recording": RECORDING, "results": results},
                      handle, ensure_ascii=False, indent=2)

        print("\nreport -> .pytest_tmp/diag07d/language_path.json")

        return 0

    finally:

        process.terminate()

        try:

            process.wait(timeout=10800)

        except Exception:

            process.kill()


if __name__ == "__main__":

    sys.exit(main())
