# -*- coding: utf-8 -*-
"""ArchitectOS CODER MVP V1 — bounded local Python execution owner.

Default state is OFF. A production run requires all of:

* the exact server environment opt-in ``ARCHITECTOS_CODER_MVP_EXECUTION=1``;
* a separately signed trusted-local UI consent action;
* an atomically consumed execute-scoped capability;
* the reviewed absolute Docker CLI path and SHA-256;
* the existing bounded Docker lifecycle/cleanup adapter.

The source is sent over the attach client's stdin. A fixed guest bootstrap
hashes those bytes, writes them only to the container's noexec tmpfs, emits a
server-checked verification marker, and only then replaces itself with the
fixed Python interpreter. There is no host bind mount and no caller argv.
"""

import hashlib
import hmac
import os
import re
import subprocess
import threading
import time

from core.chat.execution_approval_foundation_v1 import DEFAULT_RESOURCE_LIMITS
from core.chat.project_code_file_writer_v1 import (
    MAX_CODE_FILE_BYTES,
    _is_reparse_point,
    validate_code_filename,
    validate_project_id,
)
from core.chat.trusted_execution_consent_bridge_v1 import (
    CONSENT_PATH,
    PREVIEW_PATH,
    TrustedExecutionConsentBridge,
)
from core.execution.execution_contract_v1 import (
    APPROVAL_ISSUER_SERVER,
    BACKEND_EVIDENCE_VERIFIED,
    BACKEND_RESTRICTED_CONTAINER,
    authorize_execution,
)
from tests.support.bounded_docker_orchestrator_v1 import (
    APPROVED_IMAGES,
    OFFLINE_TRUSTED_DOCKER_PATH,
    OFFLINE_TRUSTED_DOCKER_SHA256,
    BoundedDockerOrchestrator,
    ContainerSpec,
    OrchestrationRefused,
    SourceHandoffFailed,
    assert_trusted_environment,
    trusted_environment,
    verify_docker_binary_identity,
)


CONTRACT = "ArchitectOSCoderMvpV1"
VERSION = "1.0"
OPT_IN_ENV = "ARCHITECTOS_CODER_MVP_EXECUTION"
PYTHON_IMAGE_KEY = "python-3.11"
GUEST_SOURCE_PATH = "/tmp/architectos_main.py"
DIGEST_MARKER = "ARCHITECTOS_SOURCE_SHA256_VERIFIED="

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

# Fixed guest program: no model/user command reaches this string. It accepts
# one server-computed hex digest and source bytes on stdin, then execs the
# fixed interpreter only after byte-for-byte SHA-256 verification.
GUEST_BOOTSTRAP = (
    "import hashlib,hmac,os,sys\n"
    "expected=sys.argv[1]\n"
    "source=sys.stdin.buffer.read(262145)\n"
    "if len(source)>262144: raise SystemExit(91)\n"
    "actual=hashlib.sha256(source).hexdigest()\n"
    "if not hmac.compare_digest(actual,expected): raise SystemExit(92)\n"
    "path='/tmp/architectos_main.py'\n"
    "with open(path,'wb') as handle:\n"
    " handle.write(source); handle.flush(); os.fsync(handle.fileno())\n"
    "sys.stderr.write('ARCHITECTOS_SOURCE_SHA256_VERIFIED='+actual+'\\n')\n"
    "sys.stderr.flush()\n"
    "os.execv(sys.executable,[sys.executable,'-I','-B',path])\n"
)


def _result(ok, reason=None, **values):
    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "ok": bool(ok),
        "reason": reason,
    }
    result.update(values)
    return result


def execution_opted_in(environ=None):
    """Exact server environment flag; request/model fields are irrelevant."""
    source = os.environ if environ is None else environ
    return str(source.get(OPT_IN_ENV, "")) == "1"


class PinnedPythonDockerExecutor(BoundedDockerOrchestrator):
    """One fixed Python source path over the accepted bounded lifecycle."""

    backend_verified = True

    def __init__(self):
        identity = verify_docker_binary_identity(
            OFFLINE_TRUSTED_DOCKER_PATH,
            expected_path=OFFLINE_TRUSTED_DOCKER_PATH,
            expected_sha256=OFFLINE_TRUSTED_DOCKER_SHA256,
        )
        if identity.get("trusted") is not True:
            raise OrchestrationRefused(
                "control_plane_untrusted", identity.get("reason") or "docker_identity")
        environment = trusted_environment()
        assert_trusted_environment(environment)
        # The accepted adapter keeps a bare-name constructor for offline fault
        # injection. After the reviewed identity check, production invocation
        # is pinned to the exact absolute executable.
        super().__init__(docker_bin="docker", env=environment)
        self.docker_bin = OFFLINE_TRUSTED_DOCKER_PATH
        self.binary_identity = identity
        self._source_bytes = None
        self._source_sha256 = None

    @staticmethod
    def _source_spec(resource_limits):
        limits = dict(resource_limits or {})
        return ContainerSpec(
            image_key=PYTHON_IMAGE_KEY,
            # Base validation still receives an accepted fixed command id;
            # this subclass replaces it with GUEST_BOOTSTRAP below.
            command_id="echo_ok",
            max_output_bytes=limits["max_output_bytes"],
            deadline_seconds=limits["max_runtime_seconds"],
            grace_seconds=2.0,
            memory_mb=limits["max_memory_mb"],
            cpus=limits["max_cpus"],
            pids_limit=limits["max_pids"],
        )

    def _fixed_create_args(self, spec, name):
        memory = "%dm" % int(spec.memory_mb)
        return [
            "create",
            "--pull=never",
            "--name", name,
            "--interactive",
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
            APPROVED_IMAGES[PYTHON_IMAGE_KEY],
            "python3", "-I", "-B", "-c", GUEST_BOOTSTRAP,
            self._source_sha256,
        ]

    def _popen(self, args):
        return subprocess.Popen(
            [self.docker_bin] + list(args),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )

    def _attach_command(self, container_id):
        return ["start", "-a", "-i", container_id]

    def _supply_input(self, proc):
        try:
            proc.stdin.write(self._source_bytes)
            proc.stdin.flush()
            proc.stdin.close()
        except Exception as exc:
            raise SourceHandoffFailed("approved source stdin handoff failed: %s" % exc)

    def run_source(self, source_bytes, source_sha256, resource_limits):
        if not isinstance(source_bytes, bytes) or not source_bytes:
            return _result(False, "execution_source_unavailable")
        if len(source_bytes) > MAX_CODE_FILE_BYTES:
            return _result(False, "execution_source_too_large")
        actual = hashlib.sha256(source_bytes).hexdigest()
        if (not isinstance(source_sha256, str)
                or _SHA256.fullmatch(source_sha256) is None
                or not hmac.compare_digest(actual, source_sha256)):
            return _result(False, "execution_source_digest_mismatch")

        self._source_bytes = source_bytes
        self._source_sha256 = source_sha256
        try:
            run = super().run(self._source_spec(resource_limits))
        except OrchestrationRefused as exc:
            return _result(
                False, exc.reason, detail=exc.detail,
                source_digest_verified=False, removal_verified=False)
        finally:
            self._source_bytes = None
            self._source_sha256 = None

        result = run.as_dict()
        marker = DIGEST_MARKER + source_sha256
        stderr_lines = str(result.get("stderr") or "").splitlines()
        digest_verified = marker in stderr_lines
        result["stderr"] = "\n".join(line for line in stderr_lines if line != marker)
        if result["stderr"]:
            result["stderr"] += "\n"
        result["source_digest_verified"] = digest_verified
        if not digest_verified:
            result["ok"] = False
            if result.get("reason") == "completed":
                result["reason"] = "source_digest_unverified"
        return result


class ExecutionMvpService(object):
    """Core-side preview, consent, gate, claim, and bounded dispatch owner."""

    def __init__(
        self,
        *,
        bridge=None,
        code_root_resolver=None,
        executor_factory=None,
        opt_in_reader=None,
    ):
        self.bridge = bridge or TrustedExecutionConsentBridge(test_mode=False)
        self.code_root_resolver = code_root_resolver or self._project_code_root
        self.executor_factory = executor_factory or PinnedPythonDockerExecutor
        self.opt_in_reader = opt_in_reader or execution_opted_in
        self._lock = threading.RLock()

    @staticmethod
    def _project_code_root(project_id):
        from core.project.project_workspace_v1 import project_workspace

        if not project_workspace.exists(project_id):
            raise ValueError("project_not_found")
        return os.path.join(project_workspace.subdir(project_id, "documents"), "code")

    @staticmethod
    def _read_saved_artifact(code_root, filename):
        valid, _reason = validate_code_filename(filename)
        if not valid or not isinstance(code_root, str) or not os.path.isabs(code_root):
            return None
        root = os.path.normcase(os.path.realpath(os.path.abspath(code_root)))
        artifact = os.path.normcase(os.path.realpath(
            os.path.abspath(os.path.join(root, filename))))
        if (os.path.normcase(os.path.dirname(artifact)) != root
                or not os.path.isfile(artifact)
                or _is_reparse_point(root)
                or _is_reparse_point(artifact)):
            return None
        try:
            with open(artifact, "rb") as handle:
                content = handle.read(MAX_CODE_FILE_BYTES + 1)
        except OSError:
            return None
        if not content or len(content) > MAX_CODE_FILE_BYTES:
            return None
        try:
            source = content.decode("utf-8")
        except UnicodeDecodeError:
            return None
        digest = hashlib.sha256(content).hexdigest()
        return root, artifact, content, source, digest

    def prepare_preview(
        self, *, proxy_secret, headers, payload, path, remote_addr,
        nonce_ledger, now=None
    ):
        if not isinstance(payload, dict):
            return _result(False, "execution_preview_payload_invalid")
        project_id = payload.get("project_id")
        filename = payload.get("filename")
        if not validate_project_id(project_id):
            return _result(False, "execution_preview_payload_invalid")
        try:
            code_root = self.code_root_resolver(project_id)
        except Exception:
            return _result(False, "execution_project_unavailable")
        saved = self._read_saved_artifact(code_root, filename)
        if saved is None:
            return _result(False, "saved_python_artifact_unavailable")
        root, artifact, content, source, digest = saved
        save_evidence = {
            "status": "written", "verified_on_disk": True,
            "writes_performed": 1, "project_id": project_id,
            "filename": filename, "digest": digest,
        }
        proposal = self.bridge.prepare_live_preview(
            proxy_secret=proxy_secret, headers=headers, payload=payload,
            path=path, remote_addr=remote_addr, nonce_ledger=nonce_ledger,
            project_id=project_id, authorized_code_root=root,
            artifact_path=artifact, verified_save=save_evidence, now=now,
        )
        if not proposal.get("ok"):
            return _result(False, proposal.get("reason"))
        proposal["preview"]["source"] = source
        proposal["execution_enabled"] = bool(self.opt_in_reader())
        return proposal

    def approve_and_run(
        self, *, proxy_secret, headers, payload, path, remote_addr,
        nonce_ledger, now=None
    ):
        if not self.opt_in_reader():
            return _result(False, "execution_disabled", execution_enabled=False)
        project_id = payload.get("project_id") if isinstance(payload, dict) else None
        if not validate_project_id(project_id):
            return _result(False, "execution_consent_payload_invalid")

        try:
            executor = self.executor_factory()
        except Exception as exc:
            return _result(False, "trusted_execution_backend_unavailable",
                           detail=str(exc)[:240])

        grant = self.bridge.record_trusted_local_consent(
            proxy_secret=proxy_secret, headers=headers, payload=payload,
            path=path, remote_addr=remote_addr, nonce_ledger=nonce_ledger,
            project_id=project_id, now=now,
        )
        if not grant.get("ok"):
            return _result(False, grant.get("reason"))

        capability_id = grant["capability_id"]
        authorization = self.bridge.authorization_for_dispatch(capability_id)
        status = self.bridge.ledger.inspect_status(capability_id, now=now)
        if not authorization or not status.get("ok"):
            return _result(False, "execution_capability_not_available")
        try:
            source_bytes = open(status["artifact_path"], "rb").read(MAX_CODE_FILE_BYTES + 1)
            source_text = source_bytes.decode("utf-8")
        except Exception:
            source_bytes = b""
            source_text = None

        request_record = {
            "project_id": project_id,
            "source_sha256": grant["source_sha256"],
            "backend_kind": BACKEND_RESTRICTED_CONTAINER,
            "backend_evidence": BACKEND_EVIDENCE_VERIFIED,
            "network_policy": "none",
            "mounts": [],
            "privileged": False,
            "interpreter": "python3.11",
            "argv": [],
            "limits": dict(grant["resource_limits"]),
        }
        gate = authorize_execution(
            request_record, authorization,
            source_text=source_text,
            now=time.time() if now is None else now,
            bound_session_id=authorization.get("session_id"),
            server_mvp_opt_in=True,
            server_backend_verified=(executor.backend_verified is True),
        )
        if not gate.get("allowed"):
            # Consume rather than retain authority after a failed gate.
            self.bridge.claim_capability_for_dispatch(capability_id, now=now)
            return _result(False, gate.get("reason"), gate=gate)

        claim = self.bridge.claim_capability_for_dispatch(capability_id, now=now)
        if not claim.get("ok"):
            return _result(False, claim.get("reason"))

        execution = executor.run_source(
            source_bytes, grant["source_sha256"], grant["resource_limits"])
        success = bool(
            execution.get("ok")
            and execution.get("source_digest_verified") is True
            and execution.get("removal_verified") is True
        )
        return _result(
            success,
            None if success else execution.get("reason") or "execution_failed",
            stage="execution_finished",
            filename=payload.get("filename"),
            source_sha256=grant["source_sha256"],
            execution=execution,
            capability_consumed=True,
        )


execution_mvp_service = ExecutionMvpService()


def describe_mvp():
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "default_enabled": False,
        "opt_in_environment": OPT_IN_ENV,
        "image_key": PYTHON_IMAGE_KEY,
        "image_reference": APPROVED_IMAGES[PYTHON_IMAGE_KEY],
        "docker_binary": OFFLINE_TRUSTED_DOCKER_PATH,
        "docker_sha256": OFFLINE_TRUSTED_DOCKER_SHA256,
        "source_transport": "docker_attach_stdin",
        "guest_digest_verification_before_exec": True,
        "network": "none",
        "host_mounts": [],
        "shell": False,
        "arbitrary_argv": False,
    }
