"""CODER-07B.3 §3 — Docker control-plane environment.

The Docker CLI is a privileged control plane. Two properties are examined here:

  1. Which environment variables can REDIRECT it to a different daemon.
  2. Which inherited variables are credentials it has no use for.

Both are removed from the default environment. The explicit `env=` seam is kept
(a degraded-CLI scenario must remain simulable) and is policed by
`assert_trusted_environment()`, which is what a production adapter must call.

All tests are offline: no engine, no container, no daemon contact.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "tests", "support")
for _path in (ROOT, SUPPORT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bounded_docker_orchestrator_v1 as orch  # noqa: E402


def check(condition, message):
    if not condition:
        raise AssertionError(message)


REDIRECT_VARS = {
    "DOCKER_HOST": "tcp://10.0.0.9:2375",
    "DOCKER_CONTEXT": "remote-prod",
    "DOCKER_CONFIG": "C:/somewhere/else",
    "DOCKER_TLS": "1",
    "DOCKER_TLS_VERIFY": "1",
    "DOCKER_CERT_PATH": "C:/certs",
    "DOCKER_API_VERSION": "1.40",
    "DOCKER_CUSTOM_HEADERS": "X-A: b",
    "DOCKER_DEFAULT_PLATFORM": "linux/arm64",
    "DOCKER_BUILDKIT": "1",
}


# ==========================================================
# §3a — REDIRECT VECTORS ARE REMOVED FROM THE DEFAULT ENVIRONMENT
# ==========================================================

def test_every_denylisted_variable_is_actually_in_the_denylist():
    for key in REDIRECT_VARS:
        check(orch.is_redirect_capable_env(key),
              "%s must be recognised as a redirect vector" % (key,))
        check(key in orch.CONTROL_PLANE_ENV_DENYLIST,
              "%s must appear in CONTROL_PLANE_ENV_DENYLIST" % (key,))


@pytest.mark.parametrize("key", sorted(REDIRECT_VARS))
def test_default_environment_drops_each_redirect_vector(key, monkeypatch):
    monkeypatch.setenv(key, REDIRECT_VARS[key])
    orchestrator = orch.BoundedDockerOrchestrator()

    check(key not in orchestrator.env,
          "%s must not reach the Docker CLI, but it survived" % (key,))
    check(key in orchestrator._env_removed,
          "%s must be recorded as removed, got %r" % (key, orchestrator._env_removed))


def test_a_redirect_vector_cannot_redirect_the_adapter(monkeypatch):
    """The concrete risk: an inherited DOCKER_HOST silently retargets the CLI."""
    monkeypatch.setenv("DOCKER_HOST", "tcp://attacker.invalid:2375")
    orchestrator = orch.BoundedDockerOrchestrator()

    check("DOCKER_HOST" not in orchestrator.env,
          "an inherited DOCKER_HOST must not survive into the child environment")


# ==========================================================
# §3b — CREDENTIALS ARE NOT HANDED TO THE CLI
# ==========================================================

@pytest.mark.parametrize("key", [
    "OPENAI_API_KEY", "WORKBUDDY_VLM_AUTH_TOKEN", "GITHUB_TOKEN",
    "AWS_SECRET_ACCESS_KEY", "DB_PASSWORD", "SOME_CREDENTIAL", "TLS_PRIVATE_KEY",
])
def test_default_environment_drops_credential_variables(key, monkeypatch):
    monkeypatch.setenv(key, "sensitive-value")
    orchestrator = orch.BoundedDockerOrchestrator()

    check(key not in orchestrator.env,
          "%s must not be passed to the Docker CLI" % (key,))
    check(key in orchestrator._env_removed,
          "%s must be recorded as removed" % (key,))


def test_the_credential_value_never_appears_in_the_environment(monkeypatch):
    marker = "do-not-leak-0123456789"
    monkeypatch.setenv("SOME_API_KEY", marker)
    orchestrator = orch.BoundedDockerOrchestrator()

    leaked = [k for k, v in orchestrator.env.items() if v == marker]
    check(leaked == [], "the credential value reached the child env via %r" % (leaked,))


# ==========================================================
# §3c — WHAT THE CLI NEEDS IS KEPT
# ==========================================================

def test_sanitization_keeps_the_variables_the_cli_needs(monkeypatch):
    monkeypatch.setenv("PATH", "C:/windows/system32;C:/tools")
    monkeypatch.setenv("SYSTEMROOT", "C:/windows")
    monkeypatch.setenv("USERPROFILE", "C:/test-home/tester")
    orchestrator = orch.BoundedDockerOrchestrator()

    for key in ("PATH", "SYSTEMROOT", "USERPROFILE"):
        check(key in orchestrator.env,
              "%s is needed for executable resolution and must survive" % (key,))
    check(orchestrator.env["PATH"] == "C:/windows/system32;C:/tools",
          "a surviving variable must keep its value")


def test_sanitize_environment_is_not_vacuous():
    """It must remove something and keep something, in the same call."""
    clean, removed = orch.sanitize_environment({
        "PATH": "x", "DOCKER_HOST": "tcp://h:2375", "OPENAI_API_KEY": "k",
        "USERPROFILE": "u",
    })

    check(sorted(removed) == ["DOCKER_HOST", "OPENAI_API_KEY"],
          "removed=%r" % (removed,))
    check(sorted(clean) == ["PATH", "USERPROFILE"], "clean=%r" % (sorted(clean),))


def test_sanitization_is_case_insensitive():
    clean, removed = orch.sanitize_environment({"docker_host": "tcp://h:1"})
    check(removed == ["docker_host"], "a lower-case variable must also be caught")
    check(clean == {}, "clean=%r" % (clean,))


# ==========================================================
# §3d — THE EXPLICIT SEAM IS PRESERVED BUT POLICED
# ==========================================================

def test_the_explicit_env_seam_is_used_verbatim():
    """Degraded-CLI simulation depends on this; it must keep working."""
    injected = {"PATH": "x", "DOCKER_HOST": "npipe:////./pipe/c07b3-does-not-exist"}
    orchestrator = orch.BoundedDockerOrchestrator(env=injected)

    check(orchestrator.env == injected,
          "an explicit env must be used as given, got %r" % (orchestrator.env,))
    check(orchestrator.env_inherited is False,
          "an explicit env must be reported as not inherited")
    check(orchestrator._env_removed == [],
          "an explicit env must not be silently rewritten")


@pytest.mark.parametrize("key", sorted(REDIRECT_VARS))
def test_assert_trusted_environment_refuses_each_redirect_vector(key):
    with pytest.raises(orch.OrchestrationRefused) as caught:
        orch.assert_trusted_environment({"PATH": "x", key: REDIRECT_VARS[key]})
    check(caught.value.reason == orch.R_CONTROL_PLANE_UNTRUSTED,
          "%s must be refused, got %r" % (key, caught.value.reason))


def test_assert_trusted_environment_refuses_credentials():
    with pytest.raises(orch.OrchestrationRefused) as caught:
        orch.assert_trusted_environment({"PATH": "x", "OPENAI_API_KEY": "k"})
    check(caught.value.reason == orch.R_CONTROL_PLANE_UNTRUSTED,
          "a credential-bearing environment must be refused")


def test_assert_trusted_environment_accepts_a_clean_environment():
    check(orch.assert_trusted_environment({"PATH": "x", "SYSTEMROOT": "y"}) is True,
          "a clean environment must be accepted")


def test_assert_trusted_environment_refuses_a_non_mapping():
    for bad in ([], "PATH=x", None, 42):
        with pytest.raises(orch.OrchestrationRefused) as caught:
            orch.assert_trusted_environment(bad)
        check(caught.value.reason == orch.R_CONTROL_PLANE_UNTRUSTED,
              "%r must be refused" % (bad,))


# ==========================================================
# §3e — THE MINIMAL, SERVER-OWNED ENVIRONMENT
# ==========================================================

def test_trusted_environment_is_a_minimal_subset():
    source = {
        "PATH": "x", "SYSTEMROOT": "y", "USERPROFILE": "u",
        "DOCKER_HOST": "tcp://h:2375", "OPENAI_API_KEY": "k", "RANDOM_VAR": "z",
    }
    minimal = orch.trusted_environment(source)

    check(sorted(minimal) == ["PATH", "SYSTEMROOT", "USERPROFILE"],
          "minimal=%r" % (sorted(minimal),))
    check("DOCKER_HOST" not in minimal, "a redirect vector must not be in the minimal set")
    check("OPENAI_API_KEY" not in minimal, "a credential must not be in the minimal set")


def test_the_minimal_allowlist_contains_path():
    check("PATH" in orch.MINIMAL_ENV_ALLOWLIST,
          "PATH is required for executable resolution")


def test_trusted_environment_reads_the_real_process_environment():
    minimal = orch.trusted_environment()
    check(isinstance(minimal, dict), "must return a dict")
    for key in minimal:
        check(key.upper() in orch.MINIMAL_ENV_ALLOWLIST,
              "%s is not on the allowlist" % (key,))


# ==========================================================
# §3f — BINARY RESOLUTION IS RECORDED, NOT ASSUMED
# ==========================================================

def test_resolve_docker_binary_never_raises():
    for env in ({"PATH": "x"}, {}, {"PATH": ""}):
        value = orch.resolve_docker_binary("docker", env)
        check(value is None or isinstance(value, str),
              "resolution must return a path or None, got %r" % (value,))


def test_control_plane_reports_the_environment_in_force():
    orchestrator = orch.BoundedDockerOrchestrator()
    described = orch.describe_control_plane(orchestrator)

    check(described["environment_inherited"] is True,
          "the default environment is inherited-and-sanitized")
    check(described["environment_sanitized"] is True,
          "the default environment must be reported as sanitized")
    check(described["redirect_or_credential_keys_present"] == [],
          "no redirect or credential keys may survive, got %r"
          % (described["redirect_or_credential_keys_present"],))
    check(isinstance(described["environment_keys_removed"], list),
          "removed keys must be reported")


def test_control_plane_declares_that_binary_resolution_is_not_pinned():
    described = orch.describe_control_plane(orch.BoundedDockerOrchestrator())

    check(described["binary_is_bare_name"] is True, "the executable is a bare name")
    check("PATH" in described["binary_resolution"],
          "the report must admit that resolution is a PATH search, got %r"
          % (described["binary_resolution"],))
    check("resolved_binary_path" in described,
          "the resolved absolute path must be recorded for a future pin")


def test_control_plane_lists_the_denylist_and_allowlist():
    described = orch.describe_control_plane(orch.BoundedDockerOrchestrator())

    check("DOCKER_HOST" in described["denylisted_env_variables"],
          "the denylist must be discoverable")
    check("PATH" in described["minimal_env_allowlist"],
          "the minimal allowlist must be discoverable")
