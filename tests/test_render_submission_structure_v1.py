"""EXECUTOR_CONTROL_FLOW_RECOVERY_V3 — AST structural guard.

WHY THIS FILE EXISTS
====================
The B+ diff produced a *syntactically valid* module that could never
submit a render:

    try:
        ...open the progress WebSocket...
    except Exception as _ws_error:
        ...print a warning...
        def _publish_submitted(prompt_id): ...
        execution = self.executor.execute(...)      # <-- dead on the happy path
    except BaseException:                            # <-- cannot catch the above
        raise

`except BaseException` after `except Exception` does NOT catch exceptions
raised inside the first handler, so that clause was unreachable too. The
only assignment of `execution` lived in a branch that runs solely when
telemetry setup fails.

No test that mocks `executor.execute` can see this: "the executor was
never called" is invisible when the executor is a mock, and a substring
check over `inspect.getsource` finds the call — inside the dead handler.
The defect is *structural*, so the guard must be structural.

FIVE ASSERTIONS
===============
A1  The submission call is not inside any `except` handler.
A2  The `_publish_submitted` callback is not inside any `except` handler.
A3  The innermost `try` around submission contains the call in its BODY
    and has exactly one handler, typed `BaseException`.
A4  That `try`'s `finally` still references `_render_guard` and
    `_ws_listener` — lease release and listener cleanup still cover the
    submission.
A5  No local is assigned ONLY inside an `except` handler of `render()`.
    This is the general defect class, not just this instance: it is the
    rule that makes "assigned only on the failure path" detectable.

The checks are pure functions over source text so the RED proof can apply
them to the preserved pre-fix copy without touching the live module.
"""

import ast
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

LIVE_MODULE = os.path.join(_PROJECT_ROOT, "core", "render", "render_runtime.py")
RENDER_FUNCTION = "render"
SUBMISSION_ATTR = "execute"
SUBMISSION_OWNER = "executor"
CALLBACK_NAME = "_publish_submitted"


# ======================================================
# AST HELPERS
# ======================================================


def _parse(source):
    return ast.parse(source)


def _render_function(tree):
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == RENDER_FUNCTION
    ]
    assert found, "RenderRuntime.render() not found"
    return found[0]


def _parent_map(root):
    parents = {}
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _ancestors(node, parents):
    chain = []
    current = parents.get(node)
    while current is not None:
        chain.append(current)
        current = parents.get(current)
    return chain


def _is_submission_call(node):
    """`self.executor.execute(...)` and nothing looser."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != SUBMISSION_ATTR:
        return False
    owner = func.value
    return isinstance(owner, ast.Attribute) and owner.attr == SUBMISSION_OWNER


def _submission_calls(fn):
    return [node for node in ast.walk(fn) if _is_submission_call(node)]


def _walk_skipping_handlers(node):
    """Yield nodes, never descending into an `except` handler."""
    yield node
    if isinstance(node, ast.ExceptHandler):
        return
    for child in ast.iter_child_nodes(node):
        yield from _walk_skipping_handlers(child)


def _store_names(node):
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
            names.add(sub.id)
    return names


def _assignments(iterable):
    names = set()
    for node in iterable:
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                names |= _store_names(target)
    return names


def _inside_try_body(call, try_node):
    """True when `call` is lexically inside `try_node.body`, not its handlers."""
    for statement in try_node.body:
        for node in ast.walk(statement):
            if node is call:
                return True
    return False


# ======================================================
# THE FIVE CHECKS — pure functions over source text
# ======================================================


def check_submission_not_in_handler(source):
    fn = _render_function(_parse(source))
    parents = _parent_map(fn)
    calls = _submission_calls(fn)

    if not calls:
        return False, "no self.executor.execute(...) call found in render()"

    if len(calls) != 1:
        return False, "expected exactly 1 submission call, found %d at lines %r" % (
            len(calls),
            [c.lineno for c in calls],
        )

    call = calls[0]
    handlers = [
        node for node in _ancestors(call, parents) if isinstance(node, ast.ExceptHandler)
    ]
    if handlers:
        return False, (
            "submission at line %d is inside an except handler at line %d — "
            "it only runs when that handler runs" % (call.lineno, handlers[0].lineno)
        )
    return True, "submission at line %d is not inside any except handler" % call.lineno


def check_callback_not_in_handler(source):
    fn = _render_function(_parse(source))
    parents = _parent_map(fn)

    definitions = [
        node
        for node in ast.walk(fn)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == CALLBACK_NAME
    ]
    if not definitions:
        return False, "%s() definition not found in render()" % CALLBACK_NAME

    for definition in definitions:
        handlers = [
            node
            for node in _ancestors(definition, parents)
            if isinstance(node, ast.ExceptHandler)
        ]
        if handlers:
            return False, (
                "%s at line %d is inside an except handler at line %d"
                % (CALLBACK_NAME, definition.lineno, handlers[0].lineno)
            )
    return True, "%s is defined on the normal path" % CALLBACK_NAME


def check_submission_try_reattaches_base_exception(source):
    fn = _render_function(_parse(source))
    parents = _parent_map(fn)
    calls = _submission_calls(fn)

    if not calls:
        return False, "no self.executor.execute(...) call found in render()"

    call = calls[0]
    tries = [node for node in _ancestors(call, parents) if isinstance(node, ast.Try)]
    if not tries:
        return False, "submission at line %d is not guarded by any try" % call.lineno

    nearest = tries[0]

    if not _inside_try_body(call, nearest):
        return False, (
            "submission at line %d is in a handler/orelse/finally of try at line %d, "
            "not in its body" % (call.lineno, nearest.lineno)
        )

    if len(nearest.handlers) != 1:
        return False, (
            "try at line %d has %d handlers (%r); the submission try must have "
            "exactly one"
            % (
                nearest.lineno,
                len(nearest.handlers),
                [ast.unparse(h.type) if h.type else None for h in nearest.handlers],
            )
        )

    handler_type = nearest.handlers[0].type
    if not (isinstance(handler_type, ast.Name) and handler_type.id == "BaseException"):
        return False, (
            "try at line %d catches %r, not BaseException"
            % (nearest.lineno, ast.unparse(handler_type) if handler_type else None)
        )

    return True, (
        "submission at line %d is in the body of try at line %d with a single "
        "BaseException handler" % (call.lineno, nearest.lineno)
    )


def check_submission_try_finally_cleans_up(source):
    fn = _render_function(_parse(source))
    parents = _parent_map(fn)
    calls = _submission_calls(fn)

    if not calls:
        return False, "no self.executor.execute(...) call found in render()"

    call = calls[0]
    tries = [node for node in _ancestors(call, parents) if isinstance(node, ast.Try)]
    if not tries:
        return False, "submission at line %d is not guarded by any try" % call.lineno

    nearest = tries[0]
    if not nearest.finalbody:
        return False, "try at line %d has no finally — cleanup would not cover it" % (
            nearest.lineno
        )

    names = set()
    for statement in nearest.finalbody:
        for node in ast.walk(statement):
            if isinstance(node, ast.Name):
                names.add(node.id)

    missing = {"_render_guard", "_ws_listener"} - names
    if missing:
        return False, (
            "finally of try at line %d does not reference %r — lease release or "
            "listener cleanup no longer covers the submission"
            % (nearest.lineno, sorted(missing))
        )

    return True, (
        "finally of try at line %d still releases the lease and stops the listener"
        % nearest.lineno
    )


def check_no_handler_only_locals(source):
    fn = _render_function(_parse(source))

    in_handlers = _assignments(
        node for handler in ast.walk(fn) if isinstance(handler, ast.ExceptHandler)
        for node in ast.walk(handler)
    )
    outside_handlers = _assignments(_walk_skipping_handlers(fn))

    only_in_handlers = in_handlers - outside_handlers
    if only_in_handlers:
        return False, (
            "these locals are assigned ONLY inside except handlers of render(): %r — "
            "reading them on the normal path raises UnboundLocalError"
            % sorted(only_in_handlers)
        )

    return True, "no local is assigned exclusively inside an except handler"


ASSERTIONS = [
    ("A1_submission_not_in_handler", check_submission_not_in_handler),
    ("A2_callback_not_in_handler", check_callback_not_in_handler),
    ("A3_submission_try_reattaches_base_exception", check_submission_try_reattaches_base_exception),
    ("A4_submission_try_finally_cleans_up", check_submission_try_finally_cleans_up),
    ("A5_no_handler_only_locals", check_no_handler_only_locals),
]


# ======================================================
# TESTS — run against the LIVE module
# ======================================================


@pytest.fixture(scope="module")
def live_source():
    with open(LIVE_MODULE, encoding="utf-8") as handle:
        return handle.read()


@pytest.mark.parametrize("name,check", ASSERTIONS, ids=[a[0] for a in ASSERTIONS])
def test_structural_assertion_holds(live_source, name, check):
    ok, detail = check(live_source)
    assert ok, "%s failed: %s" % (name, detail)


def test_all_assertions_are_defined():
    """The guard must stay at five assertions; silently dropping one is a regression."""
    assert len(ASSERTIONS) == 5
