# ==========================================================
# ARCHITECTOS CODER-07B.3 — §4 TRUSTED AUTHORIZATION LIMITATIONS
#
# The contract checks `authorization["issuer"]` and
# `request["backend_evidence"]`. Both are CALLER-SUPPLIED STRINGS.
#
# These tests do not add authority. They assert that the module refuses to
# PRETEND it has authority it does not have, and that no later edit quietly
# upgrades a label comparison into something it describes as proof.
#
# What is being protected:
#   * describe_contract() must declare the limitation in machine-readable form
#   * that declaration must stay pessimistic (no field may become True without
#     a real ledger behind it)
#   * supplying the exact literal issuer and evidence must NOT unlock execution
#   * the number of authority-gating self-declared string comparisons must not
#     grow — "more strings" is the wrong fix and is explicitly forbidden
# ==========================================================

import ast
import pathlib

from core.execution import execution_contract_v1 as ec


MODULE_PATH = pathlib.Path(ec.__file__)


def _source():
    return MODULE_PATH.read_text(encoding="utf-8")


def _module_ast():
    return ast.parse(_source())


# ----------------------------------------------------------
# The declaration exists and is honest
# ----------------------------------------------------------

def test_describe_contract_declares_the_provenance_limitation():
    described = ec.describe_contract()
    assert "provenance_limitation" in described, (
        "describe_contract() must state what the issuer/evidence checks are not"
    )


def test_every_limitation_field_is_present():
    block = ec.describe_contract()["provenance_limitation"]
    required = {
        "issuer_is_self_declared",
        "backend_evidence_is_self_declared",
        "cryptographically_signed",
        "bound_to_session",
        "verified_against_server_ledger",
        "verification_required_before_production",
    }
    missing = required - set(block)
    assert not missing, "missing limitation fields: %s" % sorted(missing)


def test_the_declaration_is_pessimistic_not_optimistic():
    """A limitation that reads as a guarantee is worse than no limitation."""
    block = ec.describe_contract()["provenance_limitation"]

    # These MUST be True: the weakness is acknowledged.
    assert block["issuer_is_self_declared"] is True
    assert block["backend_evidence_is_self_declared"] is True

    # These MUST be False: no cryptographic or ledger machinery exists.
    assert block["cryptographically_signed"] is False, (
        "there is no signature anywhere in this module"
    )
    assert block["bound_to_session"] is False, (
        "the contract compares bound_session_id but does not bind a signature"
    )
    assert block["verified_against_server_ledger"] is False, (
        "no ledger is reachable from this module; claiming otherwise is a lie"
    )


def test_the_declaration_names_the_ledger_as_the_real_fix():
    note = ec.describe_contract()["provenance_limitation"][
        "verification_required_before_production"
    ]
    assert "ledger" in note.lower()


# ----------------------------------------------------------
# Labels do not confer authority
# ----------------------------------------------------------

def _perfect_request(**overrides):
    """A request that satisfies every declarative check, including the labels."""
    payload = {
        "artifact_id": "artifact-1",
        "project_id": "project-1",
        "session_id": "session-1",
        "interpreter": ec.ALLOWED_INTERPRETERS[0],
        "network_policy": "none",
        "backend_kind": ec.BACKEND_RESTRICTED_CONTAINER,
        "backend_evidence": ec.BACKEND_EVIDENCE_VERIFIED,
        "limits": dict(ec.LIMITS),
        "argv": [ec.ALLOWED_INTERPRETERS[0], "%s/main.py" % ec.GUEST_WORKDIR],
        "source_digest": "0" * 64,
        "source": "",
        "_authorization": {
            "source": "user",
            "issuer": ec.APPROVAL_ISSUER_SERVER,
            "scope": ec.EXECUTION_SCOPE,
            "actor": "local-user",
            "project_id": "project-1",
            "session_id": "session-1",
            "expires_at": 9_999_999_999,
            "digest": "0" * 64,
            "single_use": True,
        },
    }
    payload.update(overrides)
    return payload


def test_the_correct_labels_are_not_proof_and_still_do_not_execute():
    """Even with the exact literal issuer and evidence, execution stays off.

    `authorize_execution()` refuses before it validates anything, so a request
    that satisfies every label check still returns allowed=False. That is the
    point of §4: the labels buy nothing on their own.
    """
    request = _perfect_request()
    outcome = ec.authorize_execution(
        request,
        request["_authorization"],
        now=1_700_000_000.0,
        bound_session_id="session-1",
    )
    assert outcome["allowed"] is False
    assert outcome["reason"] == ec.R_EXECUTION_DISABLED
    assert "executed" not in outcome or outcome.get("executed") is not True


def test_the_label_check_only_rejects_inconsistency_not_dishonesty():
    """A caller who lies consistently passes the label check. Say so plainly.

    This is the documented limitation, expressed as a test: `validate` reaches
    the next requirement when the issuer literal matches, and refuses when it
    does not. Neither outcome is proof of who approved anything.
    """
    request = _perfect_request()
    auth = dict(request["_authorization"])

    honest_literal = ec.validate_execution_request(
        request, auth, source_text="", now=1_700_000_000.0,
        bound_session_id="session-1",
    )
    assert honest_literal["reason"] != ec.R_APPROVAL_PROVENANCE_UNVERIFIED, (
        "the literal issuer must clear the label check"
    )

    auth["issuer"] = "totally_not_the_ledger"
    inconsistent = ec.validate_execution_request(
        request, auth, source_text="", now=1_700_000_000.0,
        bound_session_id="session-1",
    )
    assert inconsistent["allowed"] is False
    assert inconsistent["reason"] == ec.R_APPROVAL_PROVENANCE_UNVERIFIED


# ----------------------------------------------------------
# Guard against "add more self-declared strings"
# ----------------------------------------------------------

def test_the_provenance_constant_block_is_exactly_the_two_documented_ones():
    """§4 forbids manufacturing authority by adding more self-declared strings.

    Scoped precisely: this finds every comparison of the form

        <dict>.get("issuer")         != CONST
        <dict>.get("backend_evidence") != CONST

    i.e. the complete set of caller-supplied strings that actually GATE
    authority. Allowlists (interpreters, network policies, backend kinds) and
    reason codes are deliberately excluded — they are not provenance claims.

    If a third gating string appears, this fails and forces the reviewer to ask
    whether it is doing work that belongs to the server capability ledger.
    """
    provenance_keys = {"issuer", "backend_evidence"}
    tree = _module_ast()

    def _is_provenance_get(node):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            return False
        if not node.args:
            return False
        key = node.args[0]
        return isinstance(key, ast.Constant) and key.value in provenance_keys

    # The contract sometimes compares inline (`auth.get("issuer") != CONST`) and
    # sometimes hoists first (`evidence = req.get("backend_evidence")`). Both
    # forms must be covered, so collect the local aliases too.
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_provenance_get(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)

    gating = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        is_provenance = _is_provenance_get(left) or (
            isinstance(left, ast.Name) and left.id in aliases
        )
        if not is_provenance:
            continue
        for comparator in node.comparators:
            if isinstance(comparator, ast.Name):
                gating.add(comparator.id)

    expected = {"APPROVAL_ISSUER_SERVER", "BACKEND_EVIDENCE_VERIFIED"}
    assert gating == expected, (
        "the set of caller-supplied strings that gate authority changed: "
        "found %s, expected %s. Provenance belongs in the server capability "
        "ledger, not in more self-declared strings."
        % (sorted(gating), sorted(expected))
    )


def test_the_two_provenance_constants_are_plain_strings_not_callables():
    """A function named like a proof would be worse than a constant."""
    for name in ("APPROVAL_ISSUER_SERVER", "BACKEND_EVIDENCE_VERIFIED"):
        value = getattr(ec, name)
        assert isinstance(value, str), "%s must stay a plain literal" % name


def test_execution_remains_disabled_and_nothing_is_exposed():
    described = ec.describe_contract()
    assert ec.EXECUTION_ENABLED is False
    assert described["executes_anything"] is False
    assert described["exposes_routes"] == []


def test_this_module_still_imports_no_execution_capability():
    """The limitation is only acceptable because the module cannot execute.

    A self-declared issuer would be far worse if this file also imported a
    process or container API. C07A checks this product-wide; this asserts it
    locally so the §4 declaration can never outlive the property that makes it
    tolerable.
    """
    imported = set()
    for node in ast.walk(_module_ast()):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])

    assert imported <= {"hashlib", "math", "re"}, (
        "unexpected imports in the declarative contract: %s" % sorted(imported)
    )
