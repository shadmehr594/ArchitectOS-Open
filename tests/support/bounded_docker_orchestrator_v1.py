"""CODER-07B.1 — bounded Docker orchestration (TEST-ONLY boundary).

This module exists to prove the orchestration controls that CODER-07B.0-R could
not verify: wall-clock deadline, bounded output capture, cancellation, graceful
then forced termination, cleanup after failure, and immutable Docker parameters.

It is deliberately NOT part of the product:

  * it lives under tests/support/, not under core/ or ui/
  * no production module imports it (asserted by a guard test)
  * it never reads model text, chat state, or a request body
  * it does not expose a shell, a route, or a function that takes argv

Design rules, all enforced by construction rather than by convention:

  1. The caller supplies a COMMAND ID, never a command. The argv is a frozen
     tuple in APPROVED_COMMANDS. There is no code path where a caller-supplied
     string reaches subprocess.
  2. The caller supplies an IMAGE KEY, never an image reference. The reference
     is a digest-pinned constant in APPROVED_IMAGES.
  3. Every docker invocation is an argument LIST with shell=False. No string is
     ever split, joined, formatted or interpolated into a command line.
  4. Network, mounts, privileges, user, volumes and the Docker socket are not
     parameters at all, so they cannot be requested. They are baked into the
     fixed option set.
  5. Containers are named with a task-owned prefix and tracked by exact id. The
     adapter refuses to touch anything it did not create.

Nothing here executes AI-generated code. The approved commands are fixed,
reviewed probes written for this security experiment.
"""

import json
import hashlib
import hmac
import os
import re
import shutil
import subprocess
import threading
import time
import uuid

# ==========================================================
# FROZEN ALLOWLISTS
# ==========================================================

# Digest-pinned references. A tag alone is never accepted.
APPROVED_IMAGES = {
    "ubuntu-22.04": "ubuntu@sha256:3b06811b2afd352be909dd088a004166d665dc76d38b13eada33522a9d915c6f",
    "python-3.11": "python@sha256:d0199e2a90bf7a206a485b115323a75bc946f30b463d704c5435a454aca084dd",
}

# Fixed, reviewed argv. These are probes for the security experiment, not
# generated programs. Each is deliberately small and harmless.
APPROVED_COMMANDS = {
    # A: normal completion
    "echo_ok": ("/bin/echo", "c07b1-ok"),
    # B: far more output than the cap allows
    "flood_output": ("head", "-c", "1048576", "/dev/zero"),
    # C / D / G: long sleep. As PID 1 it ignores SIGTERM, which is exactly what
    # makes it a valid test of graceful-then-forced termination.
    "sleep_long": ("sleep", "600"),
    # E: deterministic nonzero exit
    "exit_nonzero": ("ls", "/nonexistent-c07b1-path"),
    # environment inspection, names only would need a shell; env prints values,
    # so it is NOT included in the allowlist. Kept out deliberately.
}

NAME_PREFIX = "c07b1-"
ID_RE = re.compile(r"^[0-9a-f]{64}$")

# Bounds for caller-supplied numbers. Anything outside is refused.
LIMITS = {
    "max_output_bytes": (1, 65536),
    "deadline_seconds": (1.0, 60.0),
    "grace_seconds": (0.5, 10.0),
    "memory_mb": (64, 512),
    "cpus": (0.25, 1.0),
    "pids_limit": (8, 64),
}

# Fields that must never appear in a request. Their presence is a refusal, not
# a silently-ignored extra, because a caller that sends them believes they do
# something.
FORBIDDEN_FIELDS = (
    "argv", "command", "cmd", "shell", "image", "image_ref", "network",
    "network_mode", "mount", "mounts", "volume", "volumes", "host_path",
    "privileged", "user", "uid", "docker_socket", "socket", "cap_add",
    "cap_add_all", "security_opt", "env", "env_file", "container_id",
    "container_name", "target", "restart", "pid_mode", "ipc_mode",
)

# Refusal reason codes
R_REQUEST_INVALID = "request_invalid"
R_FORBIDDEN_FIELD = "forbidden_field"
R_IMAGE_NOT_APPROVED = "image_not_approved"
R_COMMAND_NOT_APPROVED = "command_not_approved"
R_LIMIT_OUT_OF_BOUNDS = "limit_out_of_bounds"
R_ENGINE_UNAVAILABLE = "engine_unavailable"
R_CREATE_FAILED = "create_failed"
R_NAME_COLLISION = "name_collision"
R_CREATE_ID_UNVERIFIED = "create_id_unverified"
R_CONTROL_PLANE_UNTRUSTED = "control_plane_untrusted"
R_UNRESOLVED_CLEANUP = "unresolved_cleanup"
R_UNRESOLVED_SUPERVISION = "unresolved_supervision"

# Outcome reason codes
R_COMPLETED = "completed"
R_EXIT_NONZERO = "exit_nonzero"
R_DEADLINE_EXCEEDED = "deadline_exceeded"
R_CANCELLED = "cancelled"
R_FAULT_INJECTED = "fault_injected"
R_ATTACH_FAILED = "attach_failed"
R_SOURCE_HANDOFF_FAILED = "source_handoff_failed"
# The process exited, but its output could not be fully read. That is not a
# verified execution: whatever it printed may be missing, so the run cannot be
# called a success.
R_OUTPUT_UNVERIFIED = "output_unverified"
R_SUPERVISION_UNRESOLVED = "supervision_unresolved"

# Cleanup outcome codes. `CLEANUP_UNVERIFIED` and `INDETERMINATE` exist because
# "we could not see the container" is NOT the same fact as "the container is
# gone". Losing visibility into the daemon must never be recorded as success.
R_CLEANUP_UNVERIFIED = "cleanup_unverified"
R_INDETERMINATE = "indeterminate"

# Three-valued removal state. Only CONFIRMED proves the container is gone.
REMOVAL_CONFIRMED = "confirmed_absent"   # daemon answered decisively: no such object
REMOVAL_PRESENT = "still_present"        # daemon answered decisively: it is here
REMOVAL_UNVERIFIED = "unverified"        # no decisive answer was obtained

# The ONLY non-zero inspect responses that confirm absence. Everything else —
# engine unreachable, named pipe failure, permission denied, unexpected API
# error — is unverified. Checked on the daemon's own wording.
ABSENCE_MARKERS = (
    "no such object",
    "no such container",
)

# ==========================================================
# BOUNDED LIFECYCLE BUDGET
# ==========================================================
#
# `spec.deadline_seconds` bounds ONLY the monitored execution phase. It is not a
# bound on the whole call: name check, create, attach teardown, state
# inspection and cleanup each have their own cap. The honest total is the sum of
# those caps, which is what LIFECYCLE_BUDGET_SECONDS reports. If the daemon or
# the OS stops responding, no budget can be met — that case must surface as
# INDETERMINATE rather than as a missed deadline.
PHASE_TIMEOUTS = {
    "name_check": 20.0,
    "create": 60.0,
    "attach_wait": 15.0,
    "attach_reap": 10.0,
    "reader_join": 5.0,
    "reader_recheck": 1.0,
    "inspect_state": 20.0,
    "stop": 10.0,
    "kill": 20.0,
    "rm": 30.0,
    "inspect_verify": 20.0,
}

# Separate allowance for getting rid of a container after a fault. It is
# deliberately independent of the execution deadline: a run that blew its
# deadline must still be allowed time to clean up.
EMERGENCY_CLEANUP_BUDGET_SECONDS = 75.0


def lifecycle_budget_seconds(grace_seconds):
    """Upper bound on total wall clock for one run, from per-phase caps."""
    return sum(PHASE_TIMEOUTS.values()) + float(grace_seconds)


class OrchestrationRefused(Exception):
    """Raised when a request is refused before any container is created."""

    def __init__(self, reason, detail=""):
        super().__init__("%s: %s" % (reason, detail) if detail else reason)
        self.reason = reason
        self.detail = detail


class _AttachFailed(Exception):
    """Internal: the attach client could not be started.

    Converted into a RunResult with an explicit reason, never into a silent
    success and never into a bare exception that hides the cleanup outcome.
    """


class SourceHandoffFailed(Exception):
    """Internal/product adapter hook: fixed source bytes were not delivered."""


# ==========================================================
# STRUCTURED SPECIFICATION
# ==========================================================

SPEC_FIELDS = (
    "image_key",
    "command_id",
    "max_output_bytes",
    "deadline_seconds",
    "grace_seconds",
    "memory_mb",
    "cpus",
    "pids_limit",
)


class ContainerSpec(object):
    """Narrow, validated specification. There is no argv field by design."""

    __slots__ = SPEC_FIELDS

    def __init__(self, image_key, command_id, max_output_bytes=4096,
                 deadline_seconds=10.0, grace_seconds=2.0, memory_mb=256,
                 cpus=1.0, pids_limit=32):
        self.image_key = image_key
        self.command_id = command_id
        self.max_output_bytes = max_output_bytes
        self.deadline_seconds = deadline_seconds
        self.grace_seconds = grace_seconds
        self.memory_mb = memory_mb
        self.cpus = cpus
        self.pids_limit = pids_limit
        validate_spec(self)

    @classmethod
    def from_request(cls, request):
        """Build from a dict, refusing unknown and forbidden keys."""
        if not isinstance(request, dict):
            raise OrchestrationRefused(R_REQUEST_INVALID, "request must be a dict")
        for key in request:
            if key in FORBIDDEN_FIELDS:
                raise OrchestrationRefused(
                    R_FORBIDDEN_FIELD,
                    "%r is not a parameter of this adapter" % (key,))
            if key not in SPEC_FIELDS:
                raise OrchestrationRefused(R_REQUEST_INVALID, "unknown field %r" % (key,))
        return cls(**request)

    def as_dict(self):
        return {name: getattr(self, name) for name in SPEC_FIELDS}


def validate_spec(spec):
    """Refuse before any docker process is spawned."""
    if spec.image_key not in APPROVED_IMAGES:
        raise OrchestrationRefused(
            R_IMAGE_NOT_APPROVED, "image_key %r is not approved" % (spec.image_key,))
    if spec.command_id not in APPROVED_COMMANDS:
        raise OrchestrationRefused(
            R_COMMAND_NOT_APPROVED, "command_id %r is not approved" % (spec.command_id,))

    for name, (low, high) in LIMITS.items():
        value = getattr(spec, name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise OrchestrationRefused(R_LIMIT_OUT_OF_BOUNDS, "%s must be numeric" % name)
        if not (low <= value <= high):
            raise OrchestrationRefused(
                R_LIMIT_OUT_OF_BOUNDS,
                "%s=%r outside [%r, %r]" % (name, value, low, high))

    # An image reference smuggled through image_key must not look like a ref.
    if "/" in spec.image_key or ":" in spec.image_key or "@" in spec.image_key:
        raise OrchestrationRefused(
            R_IMAGE_NOT_APPROVED, "image_key must be an allowlist key, not a reference")
    return True


# ==========================================================
# RESULT
# ==========================================================

class RunResult(object):
    __slots__ = (
        "ok", "reason", "detail", "container_id", "exit_code", "stdout", "stderr",
        "captured_bytes", "discarded_bytes", "truncated", "timed_out", "cancelled",
        "graceful_stop_succeeded", "forced_kill", "oom_killed", "duration_seconds",
        "removed", "removal_verified", "removal_state", "cleanup_detail",
        "rm_returncode", "lifecycle_budget_seconds", "lifecycle_elapsed_seconds",
        "budget_exceeded", "emergency_cleanup_seconds", "reap_error",
        "attach_error", "reader_errors", "exited_by_sigterm",
        "supervision_unresolved", "unresolved_supervision",
    )

    def __init__(self, **kwargs):
        for name in self.__slots__:
            setattr(self, name, kwargs.get(name))

    def as_dict(self):
        return {name: getattr(self, name) for name in self.__slots__}


class _Capture(object):
    """Incremental, hard-capped capture. Never grows past the cap."""

    def __init__(self, cap):
        self.cap = cap
        self.lock = threading.Lock()
        self.chunks = []
        self.captured = 0
        self.discarded = 0
        self.errors = []

    def add(self, label, data):
        with self.lock:
            room = self.cap - self.captured
            if room > 0:
                take = data[:room]
                self.chunks.append((label, take))
                self.captured += len(take)
                self.discarded += len(data) - len(take)
            else:
                self.discarded += len(data)

    def add_error(self, label, exc):
        """Record a reader failure. Swallowing it would hide lost output."""
        with self.lock:
            self.errors.append("%s reader: %s" % (label, exc))

    def streams(self):
        with self.lock:
            out = bytearray()
            err = bytearray()
            for label, data in self.chunks:
                (out if label == "stdout" else err).extend(data)
            return bytes(out), bytes(err)


def _drain(fd, label, capture):
    try:
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            capture.add(label, chunk)
    except OSError as exc:
        capture.add_error(label, exc)


# ==========================================================
# ORCHESTRATOR
# ==========================================================

TRUSTED_DOCKER_BIN = "docker"
_SAFE_EXECUTABLE_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# CODER-07C.1 offline observation.  This is not wired into spawning: the
# adapter remains TEST-ONLY and keeps its injection seam.  A future production
# owner must pass only an absolute path whose current bytes match this reviewed
# pin, then separately preserve OS signature validation in deployment policy.
OFFLINE_TRUSTED_DOCKER_PATH = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
OFFLINE_TRUSTED_DOCKER_SHA256 = (
    "e768033e4b3f0dc760162f417a80360094644d16cd9fb12ad65c9d97508c076f"
)
OFFLINE_TRUSTED_DOCKER_SIGNER = "Docker Inc"
OFFLINE_TRUSTED_DOCKER_SIGNER_THUMBPRINT = "CACB4F507942C182C47EF14E7B9050CBDE780EB9"

# ==========================================================
# CONTROL-PLANE ENVIRONMENT (C07B.3 §3)
#
# The Docker CLI is a privileged control plane. Any environment variable that can
# point it at a DIFFERENT daemon is a redirect vector, and inheriting the whole
# parent environment hands it credentials it has no use for.
#
# Guarded by construction: the executable name (no path separators, no shell
# metacharacters — C07B.2), argv (frozen allowlist), and now the environment.
# Still NOT trusted: the executable is a bare name, so its resolution depends on
# PATH; and an explicit `env=` seam is used verbatim. A production adapter must
# pin an absolute executable path and use `trusted_environment()`.
# ==========================================================

CONTROL_PLANE_ENV_DENYLIST = (
    "DOCKER_HOST",              # redirect to another daemon
    "DOCKER_CONTEXT",           # redirect via a named context
    "DOCKER_CONFIG",            # redirect via a different config directory
    "DOCKER_TLS",               # change transport security
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
    "DOCKER_API_VERSION",       # pin a different API surface
    "DOCKER_CUSTOM_HEADERS",
    "DOCKER_DEFAULT_PLATFORM",
    "DOCKER_BUILDKIT",
)

#: Substrings that mark a variable as a credential. Such variables are never
#: passed to the Docker CLI: it has no use for them and every one handed over is
#: one more thing a compromised daemon or a wrapper could read.
CREDENTIAL_ENV_MARKERS = (
    "TOKEN", "SECRET", "PASSWORD", "API_KEY", "APIKEY",
    "CREDENTIAL", "PRIVATE_KEY", "ACCESS_KEY",
)

#: What the Docker CLI actually needs on this platform. Used by
#: `trusted_environment()` for a future production adapter.
MINIMAL_ENV_ALLOWLIST = (
    "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "LOCALAPPDATA", "APPDATA", "PROGRAMDATA", "PROGRAMFILES",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
)


def is_redirect_capable_env(key):
    """True if this variable could point the CLI at a different daemon."""
    return str(key).upper() in CONTROL_PLANE_ENV_DENYLIST


def looks_like_credential_env(key):
    """True if this variable's name marks it as a secret."""
    upper = str(key).upper()
    return any(marker in upper for marker in CREDENTIAL_ENV_MARKERS)


def sanitize_environment(env):
    """Return (clean_env, removed_keys). Removes redirect vectors and secrets."""
    clean = {}
    removed = []
    for key, value in dict(env).items():
        if is_redirect_capable_env(key) or looks_like_credential_env(key):
            removed.append(key)
        else:
            clean[key] = value
    return clean, sorted(removed)


def assert_trusted_environment(env):
    """Refuse an environment that carries redirect vectors or credentials.

    This is the check a production adapter must run before spawning the CLI. The
    test adapter keeps an explicit `env=` seam so degraded-CLI scenarios can be
    simulated; that seam is exactly what this function exists to police.
    """
    if not isinstance(env, dict):
        raise OrchestrationRefused(
            R_CONTROL_PLANE_UNTRUSTED, "environment must be a mapping")
    offenders = sorted(k for k in env
                       if is_redirect_capable_env(k) or looks_like_credential_env(k))
    if offenders:
        raise OrchestrationRefused(
            R_CONTROL_PLANE_UNTRUSTED,
            "environment carries redirect or credential variables: %s"
            % ", ".join(offenders))
    return True


def trusted_environment(source=None):
    """A minimal, server-owned environment for a production adapter."""
    source = os.environ if source is None else source
    return {k: v for k, v in dict(source).items()
            if str(k).upper() in MINIMAL_ENV_ALLOWLIST}


def resolve_docker_binary(binary=TRUSTED_DOCKER_BIN, env=None):
    """Where the bare executable name actually resolves to, if anywhere.

    Recorded rather than assumed: a production adapter should pin this absolute
    path instead of trusting a search across every PATH entry.
    """
    source = os.environ if env is None else env
    path = source.get("PATH", "")
    try:
        return shutil.which(binary, path=path)
    except Exception:
        return None


def verify_docker_binary_identity(
    candidate_path,
    expected_path=OFFLINE_TRUSTED_DOCKER_PATH,
    expected_sha256=OFFLINE_TRUSTED_DOCKER_SHA256,
):
    """Offline absolute-path and SHA-256 verification; never launches Docker.

    The expected path and digest are server-owned inputs.  Keeping them as
    parameters preserves deterministic tests without permitting a request or
    model to choose them in any integration.
    """
    result = {
        "trusted": False,
        "reason": None,
        "candidate_path": candidate_path,
        "expected_path": expected_path,
        "expected_sha256": str(expected_sha256 or "").lower(),
        "actual_sha256": None,
        "executable_started": False,
    }
    if not all(isinstance(value, str) and os.path.isabs(value)
               for value in (candidate_path, expected_path)):
        result["reason"] = "absolute_path_required"
        return result
    candidate = os.path.normcase(os.path.realpath(os.path.abspath(candidate_path)))
    expected = os.path.normcase(os.path.realpath(os.path.abspath(expected_path)))
    if not hmac.compare_digest(candidate, expected):
        result["reason"] = "docker_binary_path_mismatch"
        return result
    if os.path.islink(candidate_path) or not os.path.isfile(candidate):
        result["reason"] = "docker_binary_unavailable"
        return result
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(expected_sha256 or "")):
        result["reason"] = "docker_binary_digest_pin_invalid"
        return result
    digest = hashlib.sha256()
    try:
        with open(candidate, "rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        result["reason"] = "docker_binary_unreadable"
        result["detail"] = str(exc)[:200]
        return result
    actual = digest.hexdigest()
    result["actual_sha256"] = actual
    if not hmac.compare_digest(actual, str(expected_sha256).lower()):
        result["reason"] = "docker_binary_digest_mismatch"
        return result
    result["trusted"] = True
    return result


class BoundedDockerOrchestrator(object):
    """Minimal adapter over the existing Docker engine. No shell, ever.

    Control-plane trust (C07B.2 §7): `docker_bin` and `env` exist so the TEST
    adapter can be pointed at a simulated or degraded CLI. They must never be
    plumbed from request data, model output, or a configuration file a user can
    write. A production adapter must use the fixed binary name and a controlled
    environment; see `describe_control_plane()`.
    """

    def __init__(self, docker_bin=TRUSTED_DOCKER_BIN, env=None, poll_interval=0.05):
        if not isinstance(docker_bin, str) or not _SAFE_EXECUTABLE_RE.match(docker_bin):
            # A path separator or a shell metacharacter would let a caller
            # substitute the executable, which is root-equivalent on this host.
            raise OrchestrationRefused(
                R_CONTROL_PLANE_UNTRUSTED,
                "docker_bin must be a bare executable name, got %r" % (docker_bin,))
        if env is not None and not isinstance(env, dict):
            raise OrchestrationRefused(
                R_CONTROL_PLANE_UNTRUSTED, "env must be a mapping or None")
        self.docker_bin = docker_bin
        # Default: inherit the parent environment but strip redirect vectors and
        # credentials. An explicit `env=` is a TEST SEAM and is used verbatim, so
        # degraded-CLI scenarios remain simulable; `assert_trusted_environment()`
        # is what a production adapter must call on it.
        self.env_inherited = env is None
        if env is None:
            self.env, self._env_removed = sanitize_environment(os.environ)
        else:
            self.env = dict(env)
            self._env_removed = []
        self.poll_interval = poll_interval
        # Ownership ledger. `_created_ids` is every id this adapter created;
        # `_removed_ids` is every id whose absence was POSITIVELY confirmed.
        # The difference is what a later recovery is allowed to touch.
        self._created_ids = []
        self._removed_ids = []
        # Names for which creation was attempted but no id was ever parsed, and
        # absence could not be confirmed. These are liabilities, not successes.
        self._unresolved_names = []
        # Local process/thread resources whose completion could not be proved.
        # Keep the actual references, not just labels, so they are never silently
        # forgotten while this adapter instance remains reusable.
        self._supervision_liabilities = []
        self._cancel = threading.Event()

    def _record_supervision_liability(self, label, resource):
        if not any(item[0] == label and item[1] is resource
                   for item in self._supervision_liabilities):
            self._supervision_liabilities.append((label, resource))

    def unresolved_supervision(self):
        """Labels for local resources whose termination was not established."""
        return [label for label, _resource in self._supervision_liabilities]

    @staticmethod
    def _join_readers(reader_threads, allowance):
        """Boundedly join readers under one shared wall-clock allowance."""
        deadline = time.monotonic() + max(0.0, float(allowance))
        survivors = []
        for label, thread, stream in reader_threads:
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(timeout=remaining)
            if thread.is_alive():
                survivors.append((label, thread, stream))
        return survivors

    @staticmethod
    def _close_reader_streams(reader_threads, capture):
        """Best-effort close of local read ends to release blocked readers."""
        for label, _thread, stream in reader_threads:
            close = getattr(stream, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception as exc:
                capture.add_error(label, "pipe close failed: %s" % (exc,))

    # ---------- low level: argument lists only ----------

    def _run_docker(self, args, timeout=10800):
        """Invoke docker with an argument list. shell=False is the default and
        is never overridden anywhere in this module."""
        return subprocess.run(
            [self.docker_bin] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=self.env,
        )

    def _popen(self, args):
        """The single long-lived spawn point (the attach client). argv only."""
        return subprocess.Popen(
            [self.docker_bin] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )

    def _attach_command(self, container_id):
        """Fixed attach argv; source-delivery subclasses may add only ``-i``."""
        return ["start", "-a", container_id]

    def _supply_input(self, proc):
        """No input for the accepted probe commands."""
        return None

    def cancel(self):
        """Request cancellation of the in-flight run, if any."""
        self._cancel.set()

    # ---------- fixed option set ----------

    def _fixed_create_args(self, spec, name):
        """The complete Docker parameter set. Nothing here comes from a caller
        except the six bounded numbers."""
        image = APPROVED_IMAGES[spec.image_key]
        argv = APPROVED_COMMANDS[spec.command_id]
        memory = "%dm" % int(spec.memory_mb)
        return [
            "create",
            "--pull=never",
            "--name", name,
            "--network", "none",
            "--user", "65534:65534",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=1m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(int(spec.pids_limit)),
            "--cpus", str(float(spec.cpus)),
            "--memory", memory,
            "--memory-swap", memory,
            "--restart", "no",
            image,
        ] + list(argv)

    # ---------- name / identity guards ----------

    def _name_is_free(self, name):
        """True if the name is unused. Raises if the engine cannot be reached,
        because 'cannot tell' must never be reported as 'name is free'."""
        res = self._run_docker(["ps", "-a", "--filter", "name=%s" % name,
                                "--format", "{{.Names}}"], timeout=10800)
        if res.returncode != 0:
            detail = res.stderr.decode("utf-8", "replace").strip()[:400]
            raise OrchestrationRefused(R_ENGINE_UNAVAILABLE, detail)
        existing = res.stdout.decode("utf-8", "replace").split()
        return name not in existing

    @staticmethod
    def _parse_id(stdout):
        text = stdout.decode("utf-8", "replace").strip()
        if not ID_RE.match(text):
            return None
        return text

    # ---------- main entry point ----------

    def run(self, spec, _fault_after_start=None):
        """Execute one bounded container.

        _fault_after_start is a test-only injection point: it is called once the
        container is running, and any exception it raises must still leave no
        container behind. It exists to prove the cleanup path, not to simulate
        Docker.
        """
        validate_spec(spec)

        unresolved_supervision = self.unresolved_supervision()
        if unresolved_supervision:
            raise OrchestrationRefused(
                R_UNRESOLVED_SUPERVISION,
                "%d local supervision resource(s) remain unresolved: %s"
                % (len(unresolved_supervision), ", ".join(unresolved_supervision)))

        # Fail closed on an unresolved prior cleanup: creating another container
        # while we cannot prove the last one is gone multiplies the uncertainty.
        unresolved = self.unresolved_liabilities()
        if unresolved:
            raise OrchestrationRefused(
                R_UNRESOLVED_CLEANUP,
                "%d previously created resource(s) have unverified removal: %s"
                % (len(unresolved), ", ".join(unresolved)))

        self._cancel.clear()
        name = NAME_PREFIX + uuid.uuid4().hex[:12]
        started_at = time.monotonic()
        budget_seconds = lifecycle_budget_seconds(spec.grace_seconds)
        budget_deadline = started_at + budget_seconds
        budget_exceeded = False

        if not self._name_is_free(name):
            raise OrchestrationRefused(R_NAME_COLLISION, name)

        # --- create ---
        try:
            created = self._run_docker(self._fixed_create_args(spec, name), timeout=10800)
        except (subprocess.TimeoutExpired, OSError) as exc:
            # The create call may have succeeded on the daemon side before the
            # CLI gave up. We never got an id, so the exact generated name is the
            # only handle — still one exact reference, never a prefix sweep.
            outcome = self._remove_unidentified(name)
            if outcome["removal_state"] != REMOVAL_CONFIRMED:
                self._unresolved_names.append(name)
            raise OrchestrationRefused(
                R_ENGINE_UNAVAILABLE,
                "%s; cleanup=%s (%s)" % (exc, outcome["removal_state"], outcome["detail"]))

        if created.returncode != 0:
            detail = created.stderr.decode("utf-8", "replace").strip()[:400]
            reason = R_ENGINE_UNAVAILABLE if self._looks_like_engine_error(detail) else R_CREATE_FAILED
            outcome = self._remove_unidentified(name)
            if outcome["removal_state"] != REMOVAL_CONFIRMED:
                self._unresolved_names.append(name)
            raise OrchestrationRefused(
                reason,
                "%s; cleanup=%s (%s)" % (detail, outcome["removal_state"], outcome["detail"]))

        container_id = self._parse_id(created.stdout)
        if container_id is None:
            # We may have created something we cannot identify. Remove by name.
            outcome = self._remove_unidentified(name)
            if outcome["removal_state"] != REMOVAL_CONFIRMED:
                self._unresolved_names.append(name)
            raise OrchestrationRefused(
                R_CREATE_ID_UNVERIFIED,
                "%s; cleanup=%s (%s)" % (
                    created.stdout.decode("utf-8", "replace").strip()[:200],
                    outcome["removal_state"], outcome["detail"]))

        self._created_ids.append(container_id)

        capture = _Capture(spec.max_output_bytes)
        timed_out = False
        cancelled = False
        graceful_ok = False
        forced_kill = False
        exit_code = None
        state = None
        proc = None
        reader_threads = []
        cleanup = None
        emergency_seconds = None
        reap_error = ""
        attach_error = ""
        source_handoff_error = ""
        terminate_error = ""

        try:
            try:
                proc = self._popen(self._attach_command(container_id))
            except OSError as exc:
                # The container exists but nothing is attached to it. Record the
                # failure and fall through to cleanup; do not pretend it ran.
                attach_error = "attach client failed to start: %s" % (exc,)
                raise _AttachFailed(attach_error)

            try:
                self._supply_input(proc)
            except SourceHandoffFailed as exc:
                source_handoff_error = str(exc)
                raise

            reader_threads = [
                ("stdout", threading.Thread(
                    target=_drain,
                    args=(proc.stdout.fileno(), "stdout", capture),
                    daemon=True), proc.stdout),
                ("stderr", threading.Thread(
                    target=_drain,
                    args=(proc.stderr.fileno(), "stderr", capture),
                    daemon=True), proc.stderr),
            ]
            for _label, thread, _stream in reader_threads:
                thread.start()

            if _fault_after_start is not None:
                _fault_after_start()

            deadline = started_at + spec.deadline_seconds
            while True:
                if proc.poll() is not None:
                    break
                if self._cancel.is_set():
                    cancelled = True
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                if time.monotonic() >= budget_deadline:
                    # The whole-call budget, not just the execution deadline.
                    budget_exceeded = True
                    timed_out = True
                    break
                time.sleep(self.poll_interval)

            kill_command_used = False
            if timed_out or cancelled:
                termination = self._terminate(container_id, spec.grace_seconds)
                kill_command_used = termination["kill_command_used"]
                if termination["error"]:
                    terminate_error = termination["error"]

            try:
                exit_code = proc.wait(timeout=10800)
            except subprocess.TimeoutExpired:
                proc.kill()
                exit_code = proc.wait(timeout=10)

            # Read the container's own state BEFORE removal: OOMKilled and the
            # authoritative exit code exist only while the container does.
            state = self._inspect_state(container_id)

        except _AttachFailed as exc:
            # Cleanup still runs in the finally below; the run is reported as an
            # explicit failure with its cleanup outcome attached.
            attach_error = str(exc)

        except SourceHandoffFailed as exc:
            # The container exists but the exact approved bytes were not
            # delivered. Cleanup still runs in the same finally block.
            source_handoff_error = str(exc)

        finally:
            # Reap the attach client before the readers' final liveness check.
            # Its termination closes the pipe writers in the normal subprocess
            # case; checking readers first can leave them blocked in os.read().
            proc_still_alive = False
            if proc is not None:
                try:
                    proc_still_alive = proc.poll() is None
                except Exception as exc:  # recorded, never silently swallowed
                    proc_still_alive = True
                    reap_error = "attach client status failed: %s" % (exc,)
            if proc_still_alive:
                try:
                    proc.kill()
                    proc.wait(timeout=PHASE_TIMEOUTS["attach_reap"])
                except Exception as exc:  # recorded, never silently swallowed
                    reap_error = ("%s; attach client reap failed: %s"
                                  % (reap_error, exc)).strip("; ")
                try:
                    proc_still_alive = proc.poll() is None
                except Exception as exc:
                    proc_still_alive = True
                    reap_error = ("%s; attach client final status failed: %s"
                                  % (reap_error, exc)).strip("; ")
                if proc_still_alive:
                    if not reap_error:
                        reap_error = "attach client remained alive after bounded reap"
                    self._record_supervision_liability("attach_client", proc)

            surviving_readers = self._join_readers(
                reader_threads, PHASE_TIMEOUTS["reader_join"])
            if surviving_readers:
                # Closing the local read ends is a bounded, best-effort unblock.
                # Python threads are not killed. They are joined and checked a
                # second time; any survivor becomes an explicit liability.
                self._close_reader_streams(surviving_readers, capture)
                surviving_readers = self._join_readers(
                    surviving_readers, PHASE_TIMEOUTS["reader_recheck"])
            for label, thread, _stream in surviving_readers:
                capture.add_error(
                    label,
                    "thread remained alive after bounded join, pipe close, and recheck")
                self._record_supervision_liability("%s_reader" % label, thread)

            cleanup_started = time.monotonic()
            cleanup = self._cleanup(container_id)
            emergency_seconds = round(time.monotonic() - cleanup_started, 3)

        duration = time.monotonic() - started_at
        out_bytes, err_bytes = capture.streams()

        oom = bool(state.get("OOMKilled")) if state else False

        # Graceful vs forced is decided by the exit code, never by whether
        # `docker stop` returned 0: stop escalates to SIGKILL on its own and
        # still reports success (measured: 6/6 scenarios returned 0, three of
        # them after a SIGKILL).
        exited_by_sigterm = (exit_code == 143)
        if timed_out or cancelled:
            if exit_code == 137:
                forced_kill = True
                graceful_ok = False
            else:
                # Exit 143 proves the process DIED FROM SIGTERM; it does not
                # prove it handled SIGTERM. Measured in C07B.2 §6: under
                # `--init`, a child with no handler at all still exits 143,
                # because tini forwards the signal and the default disposition
                # terminates it. Only a zero exit after a TERM evidences an
                # application-level clean shutdown.
                graceful_ok = (exit_code == 0)
                forced_kill = kill_command_used

        if source_handoff_error:
            reason = R_SOURCE_HANDOFF_FAILED
        elif attach_error:
            reason = R_ATTACH_FAILED
        elif cancelled:
            reason = R_CANCELLED
        elif timed_out:
            reason = R_DEADLINE_EXCEEDED
        elif exit_code == 0:
            reason = R_COMPLETED
        else:
            reason = R_EXIT_NONZERO

        # --- cleanup verdict overrides everything -------------------------
        # A run cannot be "completed" if we cannot prove the container is gone.
        removal_state = cleanup["removal_state"]
        removal_verified = cleanup["removal_verified"]
        run_unresolved_supervision = self.unresolved_supervision()
        supervision_unresolved = bool(run_unresolved_supervision)
        if removal_state == REMOVAL_UNVERIFIED:
            reason = R_INDETERMINATE if budget_exceeded else R_CLEANUP_UNVERIFIED
        elif removal_state == REMOVAL_PRESENT:
            reason = R_CLEANUP_UNVERIFIED
        elif budget_exceeded:
            reason = R_INDETERMINATE

        if supervision_unresolved and removal_state == REMOVAL_CONFIRMED:
            reason = R_SUPERVISION_UNRESOLVED

        # A clean exit cannot outvote an unverified output capture. If either
        # stream could not be drained, what the process printed may be missing,
        # so the run is not a verified success even though it exited 0.
        if capture.errors and reason == R_COMPLETED:
            reason = R_OUTPUT_UNVERIFIED

        detail = "" if exit_code is not None else "no exit code observed"
        if attach_error:
            detail = ("%s; %s" % (detail, attach_error)).strip("; ")
        if source_handoff_error:
            detail = ("%s; %s" % (detail, source_handoff_error)).strip("; ")
        if terminate_error:
            detail = ("%s; %s" % (detail, terminate_error)).strip("; ")
        if capture.errors:
            detail = ("%s; %s" % (detail, "; ".join(capture.errors))).strip("; ")
        if removal_state != REMOVAL_CONFIRMED:
            detail = ("%s; %s" % (detail, cleanup["detail"])).strip("; ")
        if reap_error:
            detail = ("%s; %s" % (detail, reap_error)).strip("; ")

        return RunResult(
            ok=(exit_code == 0 and not timed_out and not cancelled
                and not attach_error
                and not source_handoff_error
                and not capture.errors
                and not reap_error
                and not supervision_unresolved
                and removal_verified is True and not budget_exceeded),
            reason=reason,
            detail=detail,
            container_id=container_id,
            exit_code=exit_code,
            stdout=out_bytes.decode("utf-8", "replace"),
            stderr=err_bytes.decode("utf-8", "replace"),
            captured_bytes=capture.captured,
            discarded_bytes=capture.discarded,
            truncated=capture.discarded > 0,
            timed_out=timed_out,
            cancelled=cancelled,
            graceful_stop_succeeded=graceful_ok,
            forced_kill=forced_kill,
            oom_killed=oom,
            duration_seconds=round(duration, 3),
            removed=cleanup["removed"],
            removal_verified=removal_verified,
            removal_state=removal_state,
            cleanup_detail=cleanup["detail"],
            rm_returncode=cleanup["rm_returncode"],
            lifecycle_budget_seconds=round(budget_seconds, 3),
            lifecycle_elapsed_seconds=round(duration, 3),
            budget_exceeded=budget_exceeded,
            emergency_cleanup_seconds=emergency_seconds,
            reap_error=reap_error,
            attach_error=attach_error,
            reader_errors=list(capture.errors),
            exited_by_sigterm=exited_by_sigterm,
            supervision_unresolved=supervision_unresolved,
            unresolved_supervision=list(run_unresolved_supervision),
        )

    # ---------- termination ----------

    def _terminate(self, container_id, grace_seconds):
        """Ask for a graceful stop, then force it.

        Returns {"kill_command_used": bool, "error": str}.

        Note: `docker stop` escalates to SIGKILL by itself and still exits 0, so
        its return code cannot distinguish a polite exit from a forced one. That
        distinction is taken from the container's exit code (143 = SIGTERM
        honoured, 137 = SIGKILL), which is why the caller derives it there.
        """
        outcome = {"kill_command_used": False, "error": ""}

        try:
            res = self._run_docker(
                ["stop", "-t", str(int(max(1, round(grace_seconds)))), container_id],
                timeout=max(10, int(grace_seconds) + 10))
            if res.returncode == 0:
                return outcome
            outcome["error"] = "stop exited %d" % (res.returncode,)
        except (subprocess.TimeoutExpired, OSError) as exc:
            outcome["error"] = "stop failed: %s" % (exc,)

        try:
            res = self._run_docker(["kill", container_id], timeout=PHASE_TIMEOUTS["kill"])
            outcome["kill_command_used"] = True
            if res.returncode != 0:
                outcome["error"] = ("%s; kill exited %d"
                                    % (outcome["error"], res.returncode)).strip("; ")
        except (subprocess.TimeoutExpired, OSError) as exc:
            outcome["kill_command_used"] = True
            outcome["error"] = ("%s; kill failed: %s"
                                % (outcome["error"], exc)).strip("; ")
        return outcome

    # ---------- cleanup ----------

    @staticmethod
    def _classify_inspect_failure(returncode, stderr):
        """Decide what a failed `docker inspect` actually proved.

        A non-zero exit is NOT evidence of absence. Only a decisive "no such
        object"/"no such container" from the daemon is. An unreachable engine, a
        broken named pipe, a permission failure or an unexpected API error all
        leave the outcome unknown, and unknown must not be recorded as removed.
        """
        if returncode == 0:
            return REMOVAL_PRESENT
        lowered = stderr.lower()
        if any(marker in lowered for marker in ABSENCE_MARKERS):
            return REMOVAL_CONFIRMED
        return REMOVAL_UNVERIFIED

    def _remove_and_verify(self, ref, owned, allowance=None, identity_verified=True):
        """Remove ONE reference this adapter created, then verify it is absent.

        `ref` is an exact id, or — only when the id could never be parsed — the
        exact generated name. Never a prefix, never a filter, never a glob.

        Returns a dict. Never raises: this runs from a `finally`, so an exception
        here would mask the real failure. Every unproven outcome is reported as
        unverified rather than as success.
        """
        result = {
            "owned": owned,
            "identity_verified": identity_verified,
            "rm_returncode": None,
            "removal_state": REMOVAL_UNVERIFIED,
            "removed": False,
            "removal_verified": False,
            "detail": "",
            "elapsed_seconds": 0.0,
        }

        if not owned:
            result["detail"] = "container was not created by this adapter"
            return result

        started = time.monotonic()
        if allowance is None:
            allowance = EMERGENCY_CLEANUP_BUDGET_SECONDS

        def remaining():
            return allowance - (time.monotonic() - started)

        # --- attempt removal ---
        rm_timeout = max(1.0, min(PHASE_TIMEOUTS["rm"], remaining()))
        try:
            rm = self._run_docker(["rm", "-f", ref], timeout=rm_timeout)
            result["rm_returncode"] = rm.returncode
            if rm.returncode != 0:
                result["detail"] = "rm exited %d: %s" % (
                    rm.returncode,
                    rm.stderr.decode("utf-8", "replace").strip()[:300])
        except (subprocess.TimeoutExpired, OSError) as exc:
            result["detail"] = "rm failed: %s" % (exc,)

        # --- verify, with whatever allowance is left ---
        verify_timeout = remaining()
        if verify_timeout < 1.0:
            result["detail"] = ("%s; emergency cleanup allowance exhausted before "
                                "absence could be verified" % (result["detail"] or "rm issued"))
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            return result

        try:
            res = self._run_docker(
                ["inspect", "--format", "{{.Id}}", ref],
                timeout=min(PHASE_TIMEOUTS["inspect_verify"], verify_timeout))
        except (subprocess.TimeoutExpired, OSError) as exc:
            result["detail"] = ("%s; inspection could not run: %s"
                                % (result["detail"] or "rm issued", exc))
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            return result

        state = self._classify_inspect_failure(
            res.returncode, res.stderr.decode("utf-8", "replace"))
        result["removal_state"] = state

        if state == REMOVAL_CONFIRMED:
            result["removed"] = True
            result["removal_verified"] = True
            if identity_verified and ref not in self._removed_ids:
                self._removed_ids.append(ref)
        elif state == REMOVAL_PRESENT:
            result["detail"] = ("container is still present after removal was "
                                "requested (rm_returncode=%r)"
                                % (result["rm_returncode"],))
        else:
            result["detail"] = ("%s; inspection was inconclusive: %s"
                                % (result["detail"] or "rm issued",
                                   res.stderr.decode("utf-8", "replace").strip()[:300]))

        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        return result

    def _cleanup(self, container_id, allowance=None):
        """Remove only the container this adapter created, then verify by id."""
        return self._remove_and_verify(
            container_id,
            owned=container_id in self._created_ids,
            allowance=allowance,
        )

    def _remove_unidentified(self, name, allowance=None):
        """Bounded cleanup for a container whose id was never parsed.

        The exact generated name is the only handle available, and it is still a
        single exact reference — never a prefix sweep. Because the id was never
        confirmed, the outcome cannot clear the ownership ledger.
        """
        return self._remove_and_verify(
            name, owned=True, allowance=allowance, identity_verified=False)

    def verify_cleanup(self, container_id, allowance=None):
        """Bounded recovery: re-check ONE task-owned container, never a prefix.

        Used after a run left its cleanup unresolved. It never enumerates
        broadly — only the exact id this adapter created.
        """
        return self._cleanup(container_id, allowance=allowance)

    def unresolved_container_ids(self):
        """Created ids whose absence has not been positively confirmed."""
        return [cid for cid in self._created_ids if cid not in self._removed_ids]

    def unresolved_liabilities(self):
        """Every task-owned reference whose absence is unproven: ids and names."""
        return list(self.unresolved_container_ids()) + list(self._unresolved_names)

    def _inspect_state(self, container_id):
        try:
            res = self._run_docker(
                ["inspect", "--format", "{{json .State}}", container_id], timeout=10800)
            if res.returncode != 0:
                return None
            return json.loads(res.stdout.decode("utf-8", "replace"))
        except Exception:
            return None

    @staticmethod
    def _looks_like_engine_error(text):
        lowered = text.lower()
        markers = (
            "cannot connect", "failed to connect", "is the docker daemon running",
            "error during connect", "the system cannot find the file",
            "open //./pipe", "npipe", "connection refused",
        )
        return any(marker in lowered for marker in markers)

    # ---------- introspection for tests ----------

    def preexisting_container_ids(self):
        """Snapshot of containers this adapter did NOT create."""
        res = self._run_docker(["ps", "-a", "--format", "{{.ID}}"], timeout=10800)
        if res.returncode != 0:
            return set()
        all_ids = set(res.stdout.decode("utf-8", "replace").split())
        mine = set(cid[:12] for cid in self._created_ids)
        return set(cid for cid in all_ids if cid not in mine)


def describe_boundary():
    """Machine-readable statement of what this module will and will not do."""
    return {
        "executes_generated_code": False,
        "accepts_argv_from_caller": False,
        "accepts_image_reference_from_caller": False,
        "accepts_docker_bin_from_caller": False,
        "accepts_environment_from_caller": False,
        "uses_shell": False,
        "approved_images": sorted(APPROVED_IMAGES),
        "approved_commands": sorted(APPROVED_COMMANDS),
        "forbidden_fields": list(FORBIDDEN_FIELDS),
        "limits": {k: list(v) for k, v in LIMITS.items()},
        "name_prefix": NAME_PREFIX,
        "exposes_routes": [],
        "removal_states": [REMOVAL_CONFIRMED, REMOVAL_PRESENT, REMOVAL_UNVERIFIED],
        "absence_markers": list(ABSENCE_MARKERS),
        "phase_timeouts": dict(PHASE_TIMEOUTS),
        "emergency_cleanup_budget_seconds": EMERGENCY_CLEANUP_BUDGET_SECONDS,
        "cleanup_outcomes": [R_CLEANUP_UNVERIFIED, R_INDETERMINATE],
        "outcome_reasons": [R_COMPLETED, R_EXIT_NONZERO, R_DEADLINE_EXCEEDED,
                             R_CANCELLED, R_ATTACH_FAILED, R_SOURCE_HANDOFF_FAILED,
                             R_OUTPUT_UNVERIFIED,
                             R_SUPERVISION_UNRESOLVED,
                             R_CLEANUP_UNVERIFIED, R_INDETERMINATE],
        "reader_failure_fails_the_run": True,
        "reader_liveness_checked": True,
        "unresolved_supervision_blocks_reuse": True,
        "uses_init": False,
        "graceful_means": "process exited 0 after TERM; 143 only means it died from TERM",
    }


def describe_control_plane(orchestrator=None):
    """What the adapter's control plane is allowed to be.

    C07B.2 §7 / C07B.3 §3: the Docker CLI is a privileged control plane. A
    production adapter must not accept a caller-controlled executable path, a
    Docker context, or privileged environment configuration. This function
    reports the fixed invocation and the environment actually in force, so a
    future integration can be checked against it.
    """
    orchestrator = orchestrator or BoundedDockerOrchestrator()
    offenders = sorted(k for k in orchestrator.env
                       if is_redirect_capable_env(k) or looks_like_credential_env(k))
    return {
        "trusted_binary_name": TRUSTED_DOCKER_BIN,
        "binary_is_bare_name": bool(_SAFE_EXECUTABLE_RE.match(orchestrator.docker_bin)),
        "binary_resolution": ("PATH search — NOT pinned to an absolute path"
                              if _SAFE_EXECUTABLE_RE.match(orchestrator.docker_bin)
                              else "caller-supplied path"),
        "resolved_binary_path": resolve_docker_binary(orchestrator.docker_bin,
                                                       orchestrator.env),
        "offline_trusted_absolute_path": OFFLINE_TRUSTED_DOCKER_PATH,
        "offline_trusted_sha256": OFFLINE_TRUSTED_DOCKER_SHA256,
        "offline_identity_verification": "absolute_path_plus_sha256",
        "offline_signer_observed": OFFLINE_TRUSTED_DOCKER_SIGNER,
        "offline_signer_thumbprint_observed": OFFLINE_TRUSTED_DOCKER_SIGNER_THUMBPRINT,
        "offline_pin_wired_into_spawn": False,
        "binary_may_be_overridden_by_request": False,
        "environment_may_be_overridden_by_request": False,
        "environment_inherited": orchestrator.env_inherited,
        "environment_sanitized": bool(orchestrator.env_inherited),
        "environment_keys_removed": list(orchestrator._env_removed),
        "redirect_or_credential_keys_present": offenders,
        "denylisted_env_variables": list(CONTROL_PLANE_ENV_DENYLIST),
        "minimal_env_allowlist": list(MINIMAL_ENV_ALLOWLIST),
        "accepts_docker_context_argument": False,
        "accepts_host_flag": False,
        "accepts_tls_flags": False,
        "shell_interface": False,
        "env_key_count": len(orchestrator.env),
    }
