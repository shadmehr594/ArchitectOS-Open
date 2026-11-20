"""CODER-07C.1 offline Docker CLI identity checks.

The helper reads file bytes only.  It never starts the client or contacts the
engine.  The real host assertion is intentionally a pin: an update must fail
until its path, signature, and digest are reviewed again.
"""

import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "tests", "support")
for _path in (ROOT, SUPPORT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bounded_docker_orchestrator_v1 as orch  # noqa: E402


def test_reviewed_host_docker_binary_matches_offline_pin():
    result = orch.verify_docker_binary_identity(
        orch.OFFLINE_TRUSTED_DOCKER_PATH)

    assert result["trusted"] is True
    assert result["actual_sha256"] == orch.OFFLINE_TRUSTED_DOCKER_SHA256
    assert result["executable_started"] is False


def test_same_bytes_at_an_unapproved_path_are_not_trusted(tmp_path):
    copy = tmp_path / "docker.exe"
    copy.write_bytes(open(orch.OFFLINE_TRUSTED_DOCKER_PATH, "rb").read())

    result = orch.verify_docker_binary_identity(str(copy))

    assert result["trusted"] is False
    assert result["reason"] == "docker_binary_path_mismatch"


def test_wrong_digest_fails_closed():
    result = orch.verify_docker_binary_identity(
        orch.OFFLINE_TRUSTED_DOCKER_PATH,
        expected_sha256="0" * 64,
    )

    assert result["trusted"] is False
    assert result["reason"] == "docker_binary_digest_mismatch"
    assert result["executable_started"] is False


def test_relative_path_is_refused_before_file_access():
    result = orch.verify_docker_binary_identity("docker.exe")

    assert result["trusted"] is False
    assert result["reason"] == "absolute_path_required"


def test_control_plane_truthfully_says_pin_is_not_wired_into_spawn():
    described = orch.describe_control_plane()

    assert described["offline_identity_verification"] == "absolute_path_plus_sha256"
    assert described["offline_pin_wired_into_spawn"] is False
    assert described["binary_resolution"] == "PATH search — NOT pinned to an absolute path"

