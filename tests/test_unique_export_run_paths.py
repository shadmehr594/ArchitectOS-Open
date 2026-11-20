from core.export.export_orchestrator import ExportOrchestrator


def test_each_export_invocation_gets_a_distinct_safe_run_id():
    first = ExportOrchestrator.create_run_id("acceptance test")
    second = ExportOrchestrator.create_run_id("acceptance test")

    assert first != second
    assert first.startswith("acceptancetest_")
    assert second.startswith("acceptancetest_")
    assert "/" not in first and "\\" not in first
