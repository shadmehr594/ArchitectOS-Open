# core/execution/draft_verification_v1.py
"""DraftVerificationV1 — verify an UNSAVED staged draft in the existing sandbox.

WHY THIS EXISTS
---------------
``ExecutionMvpService`` can only execute a SAVED artifact: it calls
``_read_saved_artifact()`` and the ledger re-reads ``artifact_path`` at claim
time. That is correct for "run the file I wrote", but it forces a save before
any behavioural evidence exists — so a draft is either saved unverified or never
verified at all.

The EXECUTOR already supports the unsaved case:
``PinnedPythonDockerExecutor.run_source(source_bytes, source_sha256, limits)``
takes bytes in memory and pipes them over stdin; ``GUEST_BOOTSTRAP`` re-verifies
the SHA-256 inside the container, writes ``/tmp/architectos_main.py`` and
``execv``s it. Nothing is ever written into ``documents/code/``.

VERDICT MODEL (four INDEPENDENT axes)
-------------------------------------
    sandbox     SUCCESS | FAILED          did the container run at all?
    integrity   VALID   | INVALID         is the harness result authentic?
    functional  PASS | FAIL | INCOMPLETE | NOT_RUN
    scenarios   PASS | FAIL | NOT_SUPPORTED | NOT_RUN   (per scenario)

A harness that exits 0 while a scenario fails is ``functional = FAIL``. Missing,
duplicated, forged or unsupported results can never become ``PASS``.

HONEST LIMITS OF THE HARNESS
----------------------------
The harness runs *inside the same interpreter* as the application under test.
A deliberately malicious draft could therefore print a convincing fake result,
monkey-patch the harness, or exit early. What this design does provide:

* the application is imported only AFTER the GUI stub is installed, and only as
  a module (its ``__main__`` block never runs);
* the harness re-hashes the embedded bytes against the staged digest;
* Core accepts exactly ONE result line, validates its shape, the digest, the
  scenario names, their uniqueness, their statuses and the expected count, and
  fails closed on anything ambiguous;
* the process is confined by the existing container (no network, read-only
  root, non-root, dropped caps, pids/cpu/memory caps, 30 s deadline).

It does NOT provide cryptographic protection against code running in the same
process. The container boundary — not the marker — is the security boundary.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time

CONTRACT = "DraftVerificationV1"
VERSION = "1.1"

DRAFT_CONSENT_PATH = "/api/coder/draft-verification/consent"
DRAFT_RUN_PATH = "/api/coder/draft-verification/run"
DRAFT_PENDING_PATH = "/api/coder/draft-verification/pending"
DRAFT_OPERATION = "verify_draft_python"
DRAFT_RUN_OPERATION = "run_draft_verification"
DRAFT_PENDING_OPERATION = "read_pending_draft"
DRAFT_SCOPE = "verify_draft"

#: Short by design: this authorises ONE sandboxed run of ONE exact digest.
DEFAULT_TTL_SECONDS = 120

#: Harness output marker. Exactly one line may carry it; zero or several is a
#: hard failure, so a stray application print cannot be mistaken for a result.
RESULT_MARKER = "__ARCHITECTOS_DRAFT_RESULT__"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_NOT_SUPPORTED = "NOT_SUPPORTED"
STATUS_NOT_RUN = "NOT_RUN"
ALLOWED_STATUSES = (STATUS_PASS, STATUS_FAIL, STATUS_NOT_SUPPORTED, STATUS_NOT_RUN)

SANDBOX_SUCCESS = "SUCCESS"
SANDBOX_FAILED = "FAILED"

INTEGRITY_VALID = "VALID"
INTEGRITY_INVALID = "INVALID"

FUNCTIONAL_PASS = "PASS"
FUNCTIONAL_FAIL = "FAIL"
FUNCTIONAL_INCOMPLETE = "INCOMPLETE"
FUNCTIONAL_NOT_RUN = "NOT_RUN"

_CONSENT_FIELDS = {"operation", "project_id", "proposal_id", "source_sha256", "consent"}

#: Resource envelope for a draft run.
#:
#: These MIRROR ``core.execution.execution_contract_v1.LIMITS`` rather than
#: importing it: the contract module must stay disconnected from production
#: (guarded by tests/test_coder_07b0_backend_gate_v1.py). The bounded
#: orchestrator's own ``validate_spec`` still enforces the ceilings, so a caller
#: cannot widen them by passing a larger dict.
_DEFAULT_LIMITS = {
    "max_runtime_seconds": 30,
    "max_memory_mb": 512,
    "max_cpus": 1.0,
    "max_output_bytes": 65536,
    "max_pids": 64,
}


def staged_proposal_id(digest):
    """Deterministic identity of the single staged proposal for a digest."""

    return "staged:" + str(digest or "")


def _result(ok, reason=None, **values):
    payload = {"contract": CONTRACT, "version": VERSION, "ok": bool(ok), "reason": reason}
    payload.update(values)
    return payload


def _token_hash(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


# ==========================================================
# HARNESS BUILDER (pure string work — nothing is executed here)
# ==========================================================

_HARNESS_TEMPLATE = r'''
import hashlib, importlib.util, inspect, json, sys, traceback, types

APP_SOURCE = __APP_SOURCE__
APP_SHA256 = __APP_SHA256__
SCENARIOS = __SCENARIOS__
MARKER = "__ARCHITECTOS_DRAFT_RESULT__"

def emit(payload):
    sys.stdout.write(MARKER + json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def die(reason, detail=""):
    emit({"ok": False, "reason": reason, "detail": str(detail)[:400]})
    raise SystemExit(0)

# ---- 1. prove the staged bytes BEFORE touching them -----------------------
data = APP_SOURCE.encode("utf-8")
if hashlib.sha256(data).hexdigest() != APP_SHA256:
    die("staged_source_digest_mismatch")

# ---- 2. controlled GUI stub, installed before the app is imported ---------
errors = []
buttons = []
entries = []
vars_created = []
bound = {}
roots = []

class _Var(object):
    def __init__(self, value=""):
        self._v = value
    def set(self, value):
        self._v = value
    def get(self):
        return self._v

class _Widget(object):
    def __init__(self, *a, **k):
        self._opts = dict(k)
        self._command = k.get("command")
        self._text = k.get("text")
        self._var = k.get("textvariable")
        if self._var is not None:
            entries.append(self)
        if self._text is not None and self._command is not None:
            buttons.append(self)
    def grid(self, *a, **k): pass
    def grid_rowconfigure(self, *a, **k): pass
    def grid_columnconfigure(self, *a, **k): pass
    def pack(self, *a, **k): pass
    def place(self, *a, **k): pass
    def config(self, **k):
        if "command" in k: self._command = k["command"]
        if "text" in k: self._text = k["text"]
    configure = config
    def bind(self, sequence=None, func=None, *a, **k):
        if func is not None: bound[sequence] = func
    def focus_set(self, *a, **k): pass
    def focus_force(self, *a, **k): pass
    def insert(self, *a, **k): pass
    def delete(self, *a, **k): pass
    def get(self):
        return self._var.get() if self._var is not None else ""
    def cget(self, key): return self._opts.get(key)

class _Root(_Widget):
    def __init__(self, *a, **k):
        super(_Root, self).__init__(*a, **k)
        roots.append(self)
    def title(self, *a, **k): pass
    def geometry(self, *a, **k): pass
    def resizable(self, *a, **k): pass
    def mainloop(self, *a, **k): pass
    def after(self, *a, **k): return None
    def destroy(self, *a, **k): pass

class _Toplevel(_Widget):
    def title(self, *a, **k): pass
    def geometry(self, *a, **k): pass
    def resizable(self, *a, **k): pass
    def destroy(self, *a, **k): pass

def _string_var(value=""):
    v = _Var(value)
    vars_created.append(v)
    return v

tk = types.ModuleType("tkinter")
tk.Tk = _Root
tk.Toplevel = _Toplevel
tk.Frame = _Widget
tk.Label = _Widget
tk.Button = _Widget
tk.Entry = _Widget
tk.Text = _Widget
tk.Menu = _Widget
tk.StringVar = _string_var
tk.IntVar = _string_var
tk.DoubleVar = _string_var
tk.BooleanVar = _string_var
tk.END = "end"
tk.W = tk.E = tk.N = tk.S = "x"
def _tk_getattr(name):
    return _Widget
tk.__getattr__ = _tk_getattr

msg = types.ModuleType("tkinter.messagebox")
def _showerror(*a, **k):
    errors.append({"kind": "error", "args": [str(x) for x in a]})
def _showinfo(*a, **k):
    errors.append({"kind": "info", "args": [str(x) for x in a]})
def _showwarning(*a, **k):
    errors.append({"kind": "warning", "args": [str(x) for x in a]})
msg.showerror = _showerror
msg.showinfo = _showinfo
msg.showwarning = _showwarning
msg.askyesno = lambda *a, **k: True
tk.messagebox = msg

sys.modules["tkinter"] = tk
sys.modules["tkinter.messagebox"] = msg
for _name in ("tkinter.ttk", "tkinter.simpledialog", "tkinter.filedialog"):
    _sub = types.ModuleType(_name)
    _sub.__getattr__ = _tk_getattr
    sys.modules[_name] = _sub

# ---- 3. import the draft as a module (its __main__ block is NOT run) ------
path = "/tmp/architectos_draft.py"
with open(path, "wb") as handle:
    handle.write(data)

try:
    spec = importlib.util.spec_from_file_location("architectos_draft", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except Exception:
    die("draft_import_failed", traceback.format_exc()[-400:])

classes = [
    obj for obj in vars(module).values()
    if isinstance(obj, type) and getattr(obj, "__module__", "") == module.__name__
]
if not classes:
    die("no_application_class", "the draft defines no class to drive")

# ---- 4. INDEPENDENT STATE PER SCENARIO ------------------------------------
# Every scenario gets a brand-new application instance AND freshly emptied
# stub registries. Reusing one instance let scenario N-1 leak its display,
# decimal flag or pending operator into scenario N, so a verdict depended on
# execution order. The application's own clear button is NOT used as the reset:
# clearing behaviour is itself under test.
def reset_stub_state():
    del errors[:]
    del buttons[:]
    del entries[:]
    del vars_created[:]
    del roots[:]
    bound.clear()

def constructor_form(candidate, root):
    """Select one constructor call shape without executing application code."""
    try:
        signature = inspect.signature(candidate)
    except (TypeError, ValueError) as exc:
        return None, TypeError(
            "constructor_signature_unavailable: %s" % (exc,)
        )

    # Preserve the established root-injection contract whenever the declared
    # signature accepts it.  Only select the self-owned-root form when passing
    # a root cannot bind.  Binding happens before construction, so a TypeError
    # raised inside application code is never mistaken for an arity mismatch.
    try:
        signature.bind(root)
        return "root_argument", None
    except TypeError:
        pass

    try:
        signature.bind()
        return "no_argument", None
    except TypeError:
        return None, TypeError(
            "unsupported_constructor_signature: %s" % (signature,)
        )

def new_instance():
    last = None
    for candidate in classes:
        # A failed candidate must not leave widgets, bindings or roots that a
        # later candidate could accidentally inherit within the same scenario.
        reset_stub_state()
        root_probe = object()
        form, signature_error = constructor_form(candidate, root_probe)
        if form is None:
            last = signature_error
            continue
        try:
            injected_root = _Root() if form == "root_argument" else None
            instance = (
                candidate(injected_root)
                if form == "root_argument"
                else candidate()
            )
        except Exception as exc:
            last = exc
            continue

        # For a root-injected app this is the supplied root. For a no-argument
        # app it is the root created by the application itself. Global widget
        # registries are scenario-local, but a MULTIPLE-root constructor leaves
        # ownership ambiguous and must never be reported as testable.
        if len(roots) > 1:
            last = RuntimeError("ambiguous_tk_root_count:%d" % len(roots))
            continue

        if form == "root_argument":
            if len(roots) != 1 or roots[0] is not injected_root:
                last = RuntimeError("injected_tk_root_not_owned")
                continue
            return roots[0], instance, None

        # A plain (non-GUI) class creates no Tk root. It is still testable: its
        # own server-owned scenarios drive methods and attributes directly, so
        # zero roots is a shape, not an error. Measured 2026-10-26: a plain
        # Calculator class was reported as ``ambiguous_tk_root_count:0`` and
        # every scenario was NOT_RUN.
        if len(roots) == 0:
            return None, instance, None

        return roots[0], instance, None
    return None, None, last

def same_value(actual, expected):
    """Numeric-aware comparison for an attribute assertion."""
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return abs(float(actual) - float(expected)) <= (
                abs(float(expected)) * 1e-9 + 1e-15
            )
        except Exception:
            return False
    return str(actual) == str(expected)

def display_value():
    for widget in entries:
        if widget._var is not None:
            return widget._var.get()
    if vars_created:
        return vars_created[0].get()
    return None

def key_handler():
    for sequence, func in bound.items():
        if "Key" in str(sequence):
            return func
    return None

class _Event(object):
    def __init__(self, keysym):
        self.keysym = keysym
        self.char = keysym if len(keysym) == 1 else ""
        self.widget = None

def click(label):
    for widget in buttons:
        if widget._text == label:
            widget._command()
            return True
    return False

results = []

def record(name, status, detail="", expected=None, actual=None):
    results.append({
        "id": name,
        "status": status,
        "detail": detail,
        "expected": expected,
        "actual": actual,
    })

for scenario in SCENARIOS:
    name = scenario.get("name") or "scenario"
    steps = scenario.get("steps") or []

    root, instance, instantiation_error = new_instance()

    if instance is None:
        record(name, "NOT_RUN", "instantiation_failed: %r" % (instantiation_error,))
        continue

    ok = True
    detail = ""
    expected = None
    actual = None
    unsupported = None

    for step in steps:
        action = step.get("action")
        try:
            if action == "click":
                if not click(str(step.get("label"))):
                    unsupported = "button_not_found:" + str(step.get("label"))
                    break
            elif action == "key":
                handler = key_handler()
                if handler is None:
                    unsupported = "no_key_handler"
                    break
                handler(_Event(str(step.get("keysym"))))
            elif action == "expect_display":
                expected = str(step.get("value"))
                actual = display_value()
                if str(actual) != expected:
                    ok = False
                    detail = "display mismatch"
                    break
            elif action == "expect_float":
                expected = step.get("value")
                raw = display_value()
                actual = raw
                try:
                    if abs(float(raw) - float(expected)) > abs(float(expected)) * 1e-9 + 1e-15:
                        ok = False
                        detail = "numeric mismatch"
                        break
                except Exception:
                    ok = False
                    detail = "not numeric"
                    break
            elif action == "expect_no_double_dot":
                actual = display_value()
                if actual is not None and ".." in str(actual):
                    ok = False
                    detail = "duplicate decimal point accepted"
                    break
            elif action == "expect_error":
                expected = True
                actual = bool(errors)
                if not errors:
                    ok = False
                    detail = "no error was reported"
                    break
            elif action == "expect_not_display":
                forbidden = str(step.get("value"))
                actual = display_value()
                if str(actual) == forbidden:
                    ok = False
                    detail = "forbidden display value"
                    break
            elif action == "call":
                # Plain-class scenario: invoke one application method.
                method = str(step.get("method") or "")
                target = getattr(instance, method, None)
                if not callable(target):
                    unsupported = "method_not_found:" + method
                    break
                target(*(step.get("args") or []))
            elif action == "expect_attr":
                # Plain-class scenario: assert one application attribute.
                attribute = str(step.get("name") or "")
                if not hasattr(instance, attribute):
                    unsupported = "attribute_not_found:" + attribute
                    break
                expected = step.get("value")
                actual = getattr(instance, attribute)
                if not same_value(actual, expected):
                    ok = False
                    detail = "attribute mismatch"
                    break
            else:
                unsupported = "unknown_step:" + str(action)
                break
        except Exception:
            ok = False
            detail = traceback.format_exc()[-300:]
            break

    if unsupported:
        record(name, "NOT_SUPPORTED", unsupported)
    elif ok:
        record(name, "PASS", "", expected, actual)
    else:
        record(name, "FAIL", detail, expected, actual)

emit({
    "ok": True,
    "app_sha256": APP_SHA256,
    "harness": "DraftVerificationHarness/1.1",
    "scenario_count": len(results),
    "scenarios": results,
})
'''


def build_harness_source(app_source, app_sha256, scenarios):
    """Return the harness program that runs ``app_source`` in the container.

    The application bytes are embedded with ``json.dumps`` so they survive
    verbatim; the harness re-hashes them and refuses to continue on any
    mismatch. Building this string executes nothing.
    """

    if not isinstance(app_source, str) or not app_source.strip():

        raise ValueError("empty_source")

    digest = hashlib.sha256(app_source.encode("utf-8")).hexdigest()

    if not isinstance(app_sha256, str) or not _SHA256.match(app_sha256):

        raise ValueError("invalid_digest")

    if not hmac.compare_digest(digest, app_sha256):

        raise ValueError("digest_mismatch")

    if not isinstance(scenarios, list) or not scenarios:

        raise ValueError("empty_scenarios")

    return (
        _HARNESS_TEMPLATE
        .replace("__APP_SOURCE__", json.dumps(app_source, ensure_ascii=False))
        .replace("__APP_SHA256__", json.dumps(app_sha256))
        .replace("__SCENARIOS__", json.dumps(scenarios, ensure_ascii=False))
    )


# ==========================================================
# RESULT PARSING + INTEGRITY VALIDATION
# ==========================================================

def parse_harness_output(stdout, stderr=""):
    """Return ``(payload, reason)`` for the SINGLE marked result line.

    Zero markers, several markers, or an unparseable payload are all failures.
    Taking "the first marker found" let a stray application ``print`` stand in
    for the authoritative result.
    """

    found = []

    for text in (stdout or "", stderr or ""):

        for line in str(text).splitlines():

            if not line.startswith(RESULT_MARKER):

                continue

            body = line[len(RESULT_MARKER):]

            try:

                found.append(json.loads(body))

            except Exception:

                return None, "result_payload_malformed"

    if not found:

        return None, "no_harness_result"

    if len(found) > 1:

        return None, "ambiguous_result_multiple_markers"

    return found[0], None


def validate_harness_result(payload, expected_digest, expected_scenarios):
    """Structural validation of the harness result. Fails closed."""

    if not isinstance(payload, dict):

        return {"integrity": INTEGRITY_INVALID, "reason": "result_not_an_object",
                "scenarios": []}

    if payload.get("ok") is not True:

        return {
            "integrity": INTEGRITY_INVALID,
            "reason": str(payload.get("reason") or "harness_reported_failure"),
            "scenarios": [],
        }

    if not hmac.compare_digest(str(payload.get("app_sha256") or ""), str(expected_digest)):

        return {"integrity": INTEGRITY_INVALID, "reason": "result_digest_mismatch",
                "scenarios": []}

    scenarios = payload.get("scenarios")

    if not isinstance(scenarios, list) or not scenarios:

        return {"integrity": INTEGRITY_INVALID, "reason": "result_scenarios_missing",
                "scenarios": []}

    expected_names = [str(item.get("name")) for item in expected_scenarios or []]

    if not expected_names:

        return {"integrity": INTEGRITY_INVALID, "reason": "expected_scenarios_missing",
                "scenarios": []}

    # The count is MANDATORY and must agree exactly with what was requested.
    # A result that omits it cannot be cross-checked against the scenario set,
    # so it is rejected rather than trusted on the strength of len(scenarios).
    count = payload.get("scenario_count")

    if not isinstance(count, int) or isinstance(count, bool):

        return {"integrity": INTEGRITY_INVALID,
                "reason": "result_scenario_count_invalid", "scenarios": []}

    if count != len(scenarios) or count != len(expected_names):

        return {"integrity": INTEGRITY_INVALID,
                "reason": "result_scenario_count_mismatch", "scenarios": []}

    if len(scenarios) != len(expected_names):

        return {"integrity": INTEGRITY_INVALID, "reason": "result_scenario_count_mismatch",
                "scenarios": []}

    seen = []

    for item in scenarios:

        if not isinstance(item, dict):

            return {"integrity": INTEGRITY_INVALID, "reason": "result_scenario_malformed",
                    "scenarios": []}

        identifier = item.get("id")

        if not isinstance(identifier, str) or not identifier:

            return {"integrity": INTEGRITY_INVALID, "reason": "result_scenario_id_missing",
                    "scenarios": []}

        if identifier in seen:

            return {"integrity": INTEGRITY_INVALID, "reason": "result_scenario_duplicate",
                    "scenarios": []}

        if item.get("status") not in ALLOWED_STATUSES:

            return {"integrity": INTEGRITY_INVALID, "reason": "result_status_unknown",
                    "scenarios": []}

        seen.append(identifier)

    if sorted(seen) != sorted(expected_names):

        return {"integrity": INTEGRITY_INVALID, "reason": "result_scenario_set_mismatch",
                "scenarios": []}

    return {"integrity": INTEGRITY_VALID, "reason": None, "scenarios": scenarios}


def decide_functional(integrity, scenarios, mandatory_ids=None, sandbox_ok=True):
    """PASS requires a SUCCESSFUL sandbox run AND VALID integrity AND all passes.

    ``sandbox_ok`` is checked FIRST and independently of the other two axes: a
    container that failed (timeout, removal unverified, digest unverified) can
    leave a structurally valid result behind, and that result must never be
    promoted to a functional PASS. The sandbox and integrity fields stay
    separate in the reply so the three facts are never conflated.

    ``NOT_SUPPORTED`` and ``NOT_RUN`` are never promoted either: they make the
    overall verdict INCOMPLETE, which is not a pass.
    """

    if sandbox_ok is not True:

        return FUNCTIONAL_NOT_RUN

    if integrity != INTEGRITY_VALID:

        return FUNCTIONAL_NOT_RUN

    if not scenarios:

        return FUNCTIONAL_NOT_RUN

    mandatory = set(str(x) for x in (mandatory_ids or []))

    def is_mandatory(item):
        return not mandatory or str(item.get("id")) in mandatory

    statuses = [item.get("status") for item in scenarios]

    if any(status == STATUS_FAIL for status in statuses):

        return FUNCTIONAL_FAIL

    blocking = [
        item for item in scenarios
        if item.get("status") in (STATUS_NOT_SUPPORTED, STATUS_NOT_RUN)
        and is_mandatory(item)
    ]

    if blocking:

        return FUNCTIONAL_INCOMPLETE

    if any(status != STATUS_PASS for status in statuses):

        # Only non-mandatory gaps remain.
        return FUNCTIONAL_INCOMPLETE

    return FUNCTIONAL_PASS


# ==========================================================
# DIGEST-BOUND CONSENT (separate from the save ledger)
# ==========================================================

class DraftVerificationConsent(object):
    """One-shot authority to verify ONE staged digest, inside the sandbox only.

    Deliberately independent of ``ExecutionApprovalLedger``: the ledger owns
    SAVE-path execution authority and is keyed to a written artifact. Keeping
    the two stores disjoint is what makes "verify" and "save" non-transferable.
    """

    def __init__(self):
        self._entries = {}
        self._lock = threading.RLock()

    def mint(
        self,
        *,
        proxy_secret,
        headers,
        payload,
        path,
        remote_addr,
        nonce_ledger,
        project_id,
        staging_reader=None,
        now=None,
        ttl_seconds=DEFAULT_TTL_SECONDS,
    ):
        from core.chat.project_code_file_writer_v1 import validate_project_id
        from core.runtime.local_authorization_v1 import verify_proxy_request

        if path != DRAFT_CONSENT_PATH:

            return _result(False, "draft_consent_path_invalid")

        verified = verify_proxy_request(
            proxy_secret,
            headers,
            payload,
            path=path,
            remote_addr=remote_addr,
            now=now,
            nonce_ledger=nonce_ledger,
        )

        if not verified.get("trusted"):

            return _result(False, verified.get("reason"))

        if not isinstance(payload, dict) or set(payload) != _CONSENT_FIELDS:

            return _result(False, "draft_consent_payload_invalid")

        if payload.get("operation") != DRAFT_OPERATION or payload.get("consent") is not True:

            return _result(False, "draft_consent_payload_invalid")

        if payload.get("project_id") != project_id or not validate_project_id(project_id):

            return _result(False, "draft_consent_project_mismatch")

        digest = payload.get("source_sha256")

        if not isinstance(digest, str) or not _SHA256.match(digest):

            return _result(False, "draft_consent_digest_invalid")

        if payload.get("proposal_id") != staged_proposal_id(digest):

            return _result(False, "draft_consent_proposal_mismatch")

        reader = staging_reader or _default_staging_reader

        proposal = reader(project_id)

        if not isinstance(proposal, dict):

            return _result(False, "draft_consent_no_staged_proposal")

        if proposal.get("status") != "awaiting_approval":

            return _result(False, "draft_consent_proposal_not_pending")

        if not hmac.compare_digest(str(proposal.get("digest") or ""), digest):

            return _result(False, "draft_consent_digest_mismatch")

        actor_id = verified.get("actor_id")
        session_id = verified.get("session_id")

        if not isinstance(actor_id, str) or not actor_id:

            return _result(False, "draft_consent_actor_missing")

        if not isinstance(session_id, str) or not session_id:

            return _result(False, "draft_consent_session_missing")

        current = time.time() if now is None else float(now)
        ttl = max(1, min(int(ttl_seconds), DEFAULT_TTL_SECONDS))
        token = "dv_" + secrets.token_urlsafe(32)

        with self._lock:

            self._entries[_token_hash(token)] = {
                "project_id": project_id,
                "proposal_id": payload["proposal_id"],
                "source_sha256": digest,
                "operation": DRAFT_OPERATION,
                "scope": DRAFT_SCOPE,
                "actor_id": actor_id,
                "session_id": session_id,
                "issued_at": current,
                "expires_at": current + ttl,
                "consumed": False,
            }

        return _result(
            True,
            None,
            stage="draft_verification_capability_minted",
            token=token,
            project_id=project_id,
            proposal_id=payload["proposal_id"],
            source_sha256=digest,
            operation=DRAFT_OPERATION,
            scope=DRAFT_SCOPE,
            expires_at=current + ttl,
            dispatch_performed=False,
            executed=False,
        )

    def claim(self, *, token, project_id, source_sha256, actor_id, session_id,
              now=None):
        """Consume the capability exactly once for THIS actor and session.

        ``actor_id``/``session_id`` are required: a token is bound to the
        identity that minted it, so possessing the string is not enough. They
        must come from a verified trusted-local request, never from the browser
        payload.
        """

        if not isinstance(token, str) or not token:

            return _result(False, "draft_capability_invalid")

        if not isinstance(actor_id, str) or not actor_id:

            return _result(False, "draft_capability_actor_missing")

        if not isinstance(session_id, str) or not session_id:

            return _result(False, "draft_capability_session_missing")

        current = time.time() if now is None else float(now)

        with self._lock:

            entry = self._entries.get(_token_hash(token))

            if not isinstance(entry, dict):

                return _result(False, "draft_capability_invalid")

            if entry.get("consumed"):

                return _result(False, "draft_capability_consumed")

            if current > float(entry.get("expires_at") or 0):

                return _result(False, "draft_capability_expired")

            if entry.get("project_id") != project_id:

                return _result(False, "draft_capability_binding_mismatch")

            if not hmac.compare_digest(str(entry.get("actor_id") or ""), actor_id):

                return _result(False, "draft_capability_binding_mismatch")

            if not hmac.compare_digest(str(entry.get("session_id") or ""), session_id):

                return _result(False, "draft_capability_binding_mismatch")

            if not hmac.compare_digest(
                str(entry.get("source_sha256") or ""), str(source_sha256 or "")
            ):

                return _result(False, "draft_capability_digest_mismatch")

            entry["consumed"] = True

        return _result(
            True,
            None,
            project_id=project_id,
            source_sha256=source_sha256,
            operation=entry.get("operation"),
            scope=entry.get("scope"),
            consumed_at=current,
        )

    def invalidate_all(self, reason="server_restart"):
        with self._lock:

            for entry in self._entries.values():

                entry["consumed"] = True

        return _result(True, None, reason=reason, invalidated=True)


def _default_staging_reader(project_id):
    from core.chat.code_file_staging_v1 import pending_proposal

    return pending_proposal(project_id)


# ==========================================================
# SERVICE — consent + staging + the EXISTING executor
# ==========================================================

class DraftVerificationService(object):
    """Runs ONE staged draft in the existing sandbox. Never saves anything."""

    def __init__(self, consent=None, executor_factory=None, staging_reader=None,
                 limits=None, opt_in_reader=None):
        self.consent = consent or DraftVerificationConsent()
        self._executor_factory = executor_factory
        self._staging_reader = staging_reader or _default_staging_reader
        self._limits = limits
        self._opt_in_reader = opt_in_reader

    def _limits_for_run(self):
        if isinstance(self._limits, dict):

            return dict(self._limits)

        return dict(_DEFAULT_LIMITS)

    def _opted_in(self):
        """Server-side opt-in, checked at the real dispatch boundary."""

        if self._opt_in_reader is not None:

            return bool(self._opt_in_reader())

        from core.execution.python_execution_mvp_v1 import execution_opted_in

        return bool(execution_opted_in())

    def verify_draft(self, *, project_id, token, scenarios, actor_id, session_id,
                     now=None, executor_factory=None):
        """Claim consent, then run the draft once. Never writes the artifact."""

        proposal = self._staging_reader(project_id)

        if not isinstance(proposal, dict):

            return _result(False, "no_staged_proposal",
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        if proposal.get("status") != "awaiting_approval":

            return _result(False, "staged_proposal_not_pending",
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        source = proposal.get("content")

        digest = proposal.get("digest")

        if not isinstance(source, str) or not source.strip():

            return _result(False, "staged_source_unavailable",
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        if not isinstance(digest, str) or not _SHA256.match(digest):

            return _result(False, "staged_digest_invalid",
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        actual = hashlib.sha256(source.encode("utf-8")).hexdigest()

        if not hmac.compare_digest(actual, digest):

            return _result(False, "staged_source_digest_mismatch",
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        # Opt-in is checked at dispatch, not merely at mint time.
        if not self._opted_in():

            return _result(False, "execution_disabled",
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        # Consent is consumed BEFORE any execution: a failure must never leave
        # reusable authority behind.
        claim = self.consent.claim(
            token=token,
            project_id=project_id,
            source_sha256=digest,
            actor_id=actor_id,
            session_id=session_id,
            now=now,
        )

        if not claim.get("ok"):

            return _result(False, claim.get("reason"),
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        try:

            harness = build_harness_source(source, digest, scenarios)

        except ValueError as error:

            return _result(False, "harness_build_failed", detail=str(error),
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        harness_digest = hashlib.sha256(harness.encode("utf-8")).hexdigest()

        factory = executor_factory or self._executor_factory

        if factory is None:

            from core.execution.python_execution_mvp_v1 import (
                PinnedPythonDockerExecutor,
            )

            factory = PinnedPythonDockerExecutor

        try:

            executor = factory()

        except Exception as error:

            return _result(False, "trusted_execution_backend_unavailable",
                           detail=str(error)[:240],
                           sandbox=SANDBOX_FAILED, integrity=INTEGRITY_INVALID,
                           functional=FUNCTIONAL_NOT_RUN, scenarios=[])

        execution = executor.run_source(
            harness.encode("utf-8"), harness_digest, self._limits_for_run()
        )

        sandbox_ok = bool(execution.get("ok"))
        sandbox = SANDBOX_SUCCESS if sandbox_ok else SANDBOX_FAILED

        payload, parse_reason = parse_harness_output(
            execution.get("stdout"), execution.get("stderr")
        )

        if payload is None:

            return _result(
                False,
                parse_reason,
                stage="draft_verification_finished",
                project_id=project_id,
                source_sha256=digest,
                harness_sha256=harness_digest,
                sandbox=sandbox,
                integrity=INTEGRITY_INVALID,
                functional=FUNCTIONAL_NOT_RUN,
                execution=execution,
                scenarios=[],
                scenario_summary=_summarise([]),
            )

        validation = validate_harness_result(payload, digest, scenarios)
        integrity = validation["integrity"]
        scenarios_out = validation["scenarios"]

        mandatory_ids = [
            str(item.get("name")) for item in scenarios
            if not item.get("optional")
        ]

        functional = decide_functional(
            integrity, scenarios_out, mandatory_ids, sandbox_ok=sandbox_ok
        )

        return _result(
            sandbox_ok and integrity == INTEGRITY_VALID,
            None if integrity == INTEGRITY_VALID else validation["reason"],
            stage="draft_verification_finished",
            project_id=project_id,
            source_sha256=digest,
            harness_sha256=harness_digest,
            sandbox=sandbox,
            integrity=integrity,
            functional=functional,
            execution=execution,
            scenarios=scenarios_out,
            scenario_summary=_summarise(scenarios_out),
        )


def _summarise(scenarios):
    summary = {STATUS_PASS: 0, STATUS_FAIL: 0, STATUS_NOT_SUPPORTED: 0, STATUS_NOT_RUN: 0}

    for item in scenarios or []:

        status = str((item or {}).get("status") or STATUS_NOT_RUN)

        summary[status] = summary.get(status, 0) + 1

    return summary


# ==========================================================
# READ-ONLY PENDING SUMMARY (for the UI)
# ==========================================================

def pending_summary(project_id, staging_reader=None):
    """What the UI may show about the pending draft — never the source bytes.

    The UI needs the DIGEST and the three existing verdicts to display what
    would be verified. It must not receive the source, an approval token or
    anything else that could be replayed.
    """

    reader = staging_reader or _default_staging_reader

    proposal = reader(project_id)

    if not isinstance(proposal, dict):

        return {
            "contract": CONTRACT,
            "version": VERSION,
            "ok": True,
            "pending": False,
            "project_id": project_id,
        }

    digest = str(proposal.get("digest") or "")
    quality = proposal.get("quality") or {}

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "ok": True,
        "pending": proposal.get("status") == "awaiting_approval",
        "project_id": project_id,
        "proposal_id": staged_proposal_id(digest),
        "filename": proposal.get("filename"),
        "status": proposal.get("status"),
        "source_sha256": digest,
        "origin": proposal.get("origin"),
        "syntax": quality.get("syntax"),
        "static_review": quality.get("static_review"),
        "functional": quality.get("functional") or FUNCTIONAL_NOT_RUN,
        "unverified_requirements": list(quality.get("unverified_requirements") or []),
    }


#: One process-wide service, mirroring the existing execution MVP singleton.
draft_verification_service = DraftVerificationService()


# ==========================================================
# DEFAULT SCENARIOS (declarative data, not calculator code)
# ==========================================================

def default_scenarios():
    """The acceptance list, expressed as data.

    Deliberately generic: click a labelled control, press a key by keysym,
    assert the display. Nothing here knows what a calculator is beyond the
    labels the USER specified in the request.
    """

    def click(sequence):
        return [{"action": "click", "label": ch} for ch in sequence]

    def keys(*keysyms):
        return [{"action": "key", "keysym": k} for k in keysyms]

    def calc(sequence, expected, name):
        return {
            "name": name,
            "steps": click(sequence)
            + [{"action": "expect_display", "value": str(expected)}],
        }

    return [
        calc("5+2=", "7", "arithmetic_add"),
        calc("5-2=", "3", "arithmetic_sub"),
        calc("5×2=", "10", "arithmetic_mul"),
        calc("5÷2=", "2.5", "arithmetic_div"),
        calc("2+3×4=", "20", "chained_left_to_right"),
        calc("5+×2=", "10", "operator_replacement"),
        {
            "name": "decimal_preserved",
            "steps": [
                {"action": "click", "label": "1"},
                {"action": "click", "label": "."},
                {"action": "expect_display", "value": "1."},
            ],
        },
        {
            "name": "duplicate_decimal_rejected",
            "steps": [
                {"action": "click", "label": "1"},
                {"action": "click", "label": "."},
                {"action": "expect_display", "value": "1."},
                {"action": "click", "label": "."},
                {"action": "expect_display", "value": "1."},
                {"action": "expect_no_double_dot"},
            ],
        },
        {
            "name": "backspace_keeps_decimal_coherent",
            "steps": [
                {"action": "click", "label": "1"},
                {"action": "click", "label": "."},
                {"action": "click", "label": "5"},
                {"action": "click", "label": "⌫"},
                {"action": "click", "label": "."},
                {"action": "expect_no_double_dot"},
            ],
        },
        {
            "name": "numpad_digit",
            "steps": keys("KP_5") + [{"action": "expect_display", "value": "5"}],
        },
        {
            "name": "numpad_operator",
            "steps": keys("KP_5", "KP_Add", "KP_2", "KP_Enter")
            + [{"action": "expect_display", "value": "7"}],
        },
        {
            "name": "scientific_notation_preserved",
            "steps": click("1÷10000000000=")
            + [{"action": "expect_float", "value": 1e-10}],
        },
        {
            "name": "division_by_zero_resets",
            "steps": click("5")
            + [{"action": "expect_display", "value": "5"}]
            + click("÷0=")
            + [{"action": "expect_error"}, {"action": "expect_display", "value": "0"}],
        },
        {
            "name": "fresh_entry_after_equals",
            "steps": click("5+2=")
            + click("4+2=")
            + [{"action": "expect_display", "value": "6"}],
        },
        {
            "name": "clear_buttons_reset_display",
            "steps": click("123")
            + [{"action": "expect_display", "value": "123"}]
            + [{"action": "click", "label": "C"}, {"action": "expect_display", "value": "0"}],
        },
        {
            "name": "keyboard_matches_gui",
            "steps": keys("5") + [{"action": "expect_display", "value": "5"}],
        },
    ]


# ==========================================================
# PLAIN-CLASS SCENARIO PACK (server-owned, selected by program shape)
#
# Measured 2026-10-26: a plain Calculator class — no Tkinter root — was
# reported as ``ambiguous_tk_root_count:0`` and all 16 GUI scenarios were
# NOT_RUN. The harness required exactly one root, which is right for a GUI
# application and wrong for a class that owns no widgets.
#
# These scenarios drive the class directly: construct it with no root, call one
# method, assert one attribute. Each scenario is self-contained because the
# harness deliberately gives every scenario a fresh instance.
#
# Nothing here asserts arithmetic, decimal, keyboard or GUI behaviour, so a
# draft that does not expose those capabilities reports NOT_SUPPORTED rather
# than PASS.
# ==========================================================

def plain_class_scenarios():
    """The fixed scenario pack for a draft that is a plain Python class."""

    def call(method, *args):
        return {"action": "call", "method": method, "args": list(args)}

    def expect(name, value):
        return {"action": "expect_attr", "name": name, "value": value}

    return [
        {"name": "plain_instantiate", "steps": []},
        {
            "name": "plain_digit_sets_operand1",
            "steps": [call("on_digit", 5), expect("operand1", 5)],
        },
        {
            "name": "plain_operator_keeps_operand1",
            "steps": [
                call("on_digit", 5),
                call("on_operator", "+"),
                expect("operand1", 5),
            ],
        },
        {
            "name": "plain_operator_change_keeps_operand1",
            "steps": [
                call("on_digit", 5),
                call("on_operator", "+"),
                call("on_operator", "*"),
                expect("operand1", 5),
                expect("operator", "*"),
            ],
        },
        {
            "name": "plain_digit_sets_operand2",
            "steps": [
                call("on_digit", 5),
                call("on_operator", "+"),
                call("on_digit", 2),
                expect("operand2", 2),
            ],
        },
    ]


def _imports_tkinter(source):
    """True when the draft is a Tkinter program. Parsing only — nothing runs."""

    try:

        tree = ast.parse(source)

    except Exception:

        # An unparseable source keeps the established pack: syntax is reported
        # separately, and guessing a different pack for a program we cannot
        # read would change behaviour for no reason.
        return True

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                if alias.name.split(".")[0] == "tkinter":

                    return True

        elif isinstance(node, ast.ImportFrom):

            if (node.module or "").split(".")[0] == "tkinter":

                return True

    return False


def scenarios_for_source(source):
    """The server-owned pack that fits THIS draft's shape.

    A Tkinter program keeps the unchanged 16-scenario calculator pack; a plain
    class gets the plain-class pack. The choice is made here, server-side, from
    the draft bytes — never from the browser.
    """

    if _imports_tkinter(source):

        return default_scenarios()

    return plain_class_scenarios()


def scenarios_for_project(project_id, staging_reader=None):
    """The pack for the project's CURRENT pending draft."""

    reader = staging_reader or _default_staging_reader

    proposal = reader(project_id)

    source = proposal.get("content") if isinstance(proposal, dict) else ""

    return scenarios_for_source(source or "")


def describe():
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "consent_path": DRAFT_CONSENT_PATH,
        "operation": DRAFT_OPERATION,
        "scope": DRAFT_SCOPE,
        "ttl_seconds": DEFAULT_TTL_SECONDS,
        "verdicts": ["sandbox", "integrity", "functional", "scenarios"],
        "executes_on_import": False,
    }
