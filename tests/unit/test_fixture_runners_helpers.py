"""Unit coverage for fixture_runners helpers (mocked Lake; no network)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lpe.models import CandidateDescriptor, FindingStatus
from lpe.providers import fixture_runners as fr
from lpe.providers.base import CancellationToken, ProviderContext
from lpe.workspace.artifacts import ContentAddressedArtifactStore
from lpe.workspace.models import (
    EvaluationWorkspace,
    ExecutorDescriptor,
    WorkspaceCleanupToken,
)


def _generator():
    from lpe.models import GeneratorProvenance

    return GeneratorProvenance(generator_type="test", name="test", version="0")


def _ctx(project_path: Path, candidate: CandidateDescriptor) -> ProviderContext:
    from lpe.execution.runner import SubprocessLeanExecutor

    store = ContentAddressedArtifactStore(project_path)
    desc = ExecutorDescriptor(
        backend="host",
        network_policy="allow",
        readonly_root=False,
        source_mount_readonly=False,
    )
    ws = EvaluationWorkspace(
        run_id="run_fix",
        repository_origin=project_path,
        base_path=project_path,
        candidate_path=project_path,
        base_commit=candidate.base_commit,
        head_commit=candidate.head_commit,
        patch_sha256=None,
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        executor=SubprocessLeanExecutor(),
        executor_descriptor=desc,
        artifact_store=store,
        cleanup_token=WorkspaceCleanupToken(run_id="run_fix"),
    )
    mock_contract = MagicMock()
    mock_contract.project.execution.environment_allowlist = ["PATH"]
    return ProviderContext(
        workspace=ws,
        contract=mock_contract,
        candidate=candidate,
        cancellation=CancellationToken(),
    )


def test_diagnostic_matches() -> None:
    assert fr._diagnostic_matches("Error: boom", regex=r"boom", needles=[]) is True
    assert fr._diagnostic_matches("alpha beta", regex=None, needles=["alpha", "beta"])
    assert fr._diagnostic_matches("alpha", regex=None, needles=["alpha", "missing"]) is False
    assert fr._diagnostic_matches("anything", regex=None, needles=[]) is True


def test_is_unrelated_lean_failure() -> None:
    assert fr._is_unrelated_lean_failure("unknown package foo", 1) is True
    assert fr._is_unrelated_lean_failure("type mismatch", 1) is False
    assert fr._is_unrelated_lean_failure("", None) is True


def test_redact_and_try_lake(tmp_path: Path) -> None:
    out = fr._redact_log_snippet("secret=ABCDEFGHIJKLMNOP", limit=15)
    assert len(out) <= 15

    candidate = CandidateDescriptor(
        candidate_id="cand-fix",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    ctx = _ctx(tmp_path, candidate)
    ctx.workspace.executor.run = MagicMock(side_effect=OSError("no lake"))  # type: ignore[method-assign]
    err = fr._try_lake_env_lean(ctx, "A.lean")
    assert err["ok"] is False

    ctx.workspace.executor.run = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(exit_code=0, timed_out=False, stderr="", stdout="ok")
    )
    ok = fr._try_lake_env_lean(ctx, "A.lean")
    assert ok["ok"] is True

    ctx.workspace.executor.run = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(exit_code=1, timed_out=True, stderr="timed out", stdout="")
    )
    timed = fr._try_lake_env_lean(ctx, "A.lean")
    assert timed["ok"] is False


def test_collect_fixture_suite_obligation_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tests = tmp_path / ".lean-project-contract" / "tests" / "examples"
    tests.mkdir(parents=True)
    candidate = CandidateDescriptor(
        candidate_id="cand-fix",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    provider = SimpleNamespace(provider_id="p", provider_version="0.2.0")

    class FakeSuite:
        suite_id = "suite-x"
        obligation_ids = ["O-99"]
        fixtures = [SimpleNamespace(path="a.lean")]

    monkeypatch.setattr(
        fr,
        "load_fixture_suite",
        lambda *_a, **_k: (FakeSuite(), {"ok": True}),
    )
    monkeypatch.setattr(fr, "has_lakefile", lambda _p: False)
    monkeypatch.setattr(fr, "lean_toolchain_available", lambda _p: False)

    result = fr.collect_fixture_suite(
        provider,
        _ctx(tmp_path, candidate),
        kind="examples",
        check_id="semantic.project_examples",
        expected_success=True,
    )
    assert result.findings[0].status is FindingStatus.UNKNOWN
    assert "obligation" in result.findings[0].summary.lower()


def test_collect_fixture_suite_lake_unavailable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ex.lean").write_text("def x := 1\n", encoding="utf-8")
    candidate = CandidateDescriptor(
        candidate_id="cand-fix",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    provider = SimpleNamespace(provider_id="p", provider_version="0.2.0")

    class FakeEntry:
        fixture_id = "fx1"
        path = "ex.lean"
        run_on = "candidate"
        expected_exit = 0
        expected_diagnostic_regex = None
        expected_diagnostics: list[str] = []

    class FakeSuite:
        suite_id = "suite-ok"
        obligation_ids = ["O-01"]
        fixtures = [FakeEntry()]

    monkeypatch.setattr(
        fr,
        "load_fixture_suite",
        lambda *_a, **_k: (FakeSuite(), {"ok": True}),
    )
    monkeypatch.setattr(fr, "has_lakefile", lambda _p: False)
    monkeypatch.setattr(fr, "lean_toolchain_available", lambda _p: False)

    result = fr.collect_fixture_suite(
        provider,
        _ctx(tmp_path, candidate),
        kind="examples",
        check_id="semantic.project_examples",
        expected_success=True,
    )
    assert result.findings[0].status is FindingStatus.UNKNOWN
    assert result.findings[0].details["unknowns"] == ["fx1"]


def test_collect_fixture_suite_lake_executed_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover lake-capable success / fail / unknown / diagnostic branches."""
    (tmp_path / "ok.lean").write_text("-- ok\n", encoding="utf-8")
    (tmp_path / "bad.lean").write_text("-- bad\n", encoding="utf-8")
    (tmp_path / "diag.lean").write_text("-- diag\n", encoding="utf-8")
    candidate = CandidateDescriptor(
        candidate_id="cand-fix",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    provider = SimpleNamespace(provider_id="p", provider_version="0.2.0")

    class Entry:
        def __init__(
            self,
            fid: str,
            path: str,
            *,
            expected_exit: int = 0,
            regex: str | None = None,
            needles: list[str] | None = None,
        ) -> None:
            self.fixture_id = fid
            self.path = path
            self.run_on = "candidate"
            self.expected_exit = expected_exit
            self.expected_diagnostic_regex = regex
            self.expected_diagnostics = list(needles or [])

    class FakeSuite:
        suite_id = "suite-lake"
        obligation_ids = ["O-01"]
        fixtures = [
            Entry("ok", "ok.lean"),
            Entry("fail", "bad.lean", expected_exit=0),
            Entry("unrelated", "diag.lean", expected_exit=1),
            Entry(
                "mismatch",
                "diag.lean",
                expected_exit=1,
                needles=["EXPECTED_TOKEN"],
            ),
        ]

    responses = {
        "ok.lean": {
            "ok": True,
            "reason": "lake_env_ok",
            "exit_code": 0,
            "stderr": "",
        },
        "bad.lean": {
            "ok": False,
            "reason": "lake_env_failed",
            "exit_code": 1,
            "stderr": "type mismatch",
        },
        "diag.lean": {
            "ok": False,
            "reason": "lake_env_failed",
            "exit_code": 1,
            "stderr": "unknown package foo",
        },
    }
    call_n = {"i": 0}

    def _fake_lake(_ctx: object, rel: str) -> dict[str, object]:
        call_n["i"] += 1
        # Fourth call (mismatch) uses same path but should not be unrelated.
        if call_n["i"] == 4:
            return {
                "ok": False,
                "reason": "lake_env_failed",
                "exit_code": 1,
                "stderr": "some other error without expected token",
            }
        return responses[rel]

    monkeypatch.setattr(
        fr,
        "load_fixture_suite",
        lambda *_a, **_k: (FakeSuite(), {"ok": True}),
    )
    monkeypatch.setattr(fr, "has_lakefile", lambda _p: True)
    monkeypatch.setattr(fr, "lean_toolchain_available", lambda _p: True)
    monkeypatch.setattr(fr, "_try_lake_env_lean", _fake_lake)

    # examples expected_success=True → failures + unknowns mixed
    result = fr.collect_fixture_suite(
        provider,
        _ctx(tmp_path, candidate),
        kind="examples",
        check_id="semantic.project_examples",
        expected_success=True,
    )
    finding = result.findings[0]
    assert finding.status in {FindingStatus.UNKNOWN, FindingStatus.FAIL}
    assert "ok" in {r["fixture_id"] for r in finding.details["fixtures"] if r.get("ok")}

    # counterexamples expected_success=False → diagnostic_mismatch / fail branches
    class CounterSuite:
        suite_id = "suite-counter"
        obligation_ids = ["O-01"]
        fixtures = [
            Entry("counter_ok", "bad.lean", expected_exit=1),
            Entry(
                "counter_mismatch",
                "bad.lean",
                expected_exit=1,
                needles=["NEEDLE_MISSING"],
            ),
        ]

    def _fake_lake2(_ctx: object, rel: str) -> dict[str, object]:
        return {
            "ok": False,
            "reason": "lake_env_failed",
            "exit_code": 1,
            "stderr": "type mismatch at line 1",
        }

    monkeypatch.setattr(
        fr,
        "load_fixture_suite",
        lambda *_a, **_k: (CounterSuite(), {"ok": True}),
    )
    monkeypatch.setattr(fr, "_try_lake_env_lean", _fake_lake2)
    counter = fr.collect_fixture_suite(
        provider,
        _ctx(tmp_path, candidate),
        kind="counterexamples",
        check_id="semantic.project_counterexamples",
        expected_success=False,
    )
    assert counter.findings[0].status in {FindingStatus.UNKNOWN, FindingStatus.FAIL}
    assert counter.findings[0].details["attempted"] is True


def test_collect_fixture_suite_invoke_error_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.lean").write_text("-- a\n", encoding="utf-8")
    candidate = CandidateDescriptor(
        candidate_id="cand-fix",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    provider = SimpleNamespace(provider_id="p", provider_version="0.2.0")

    class Entry:
        fixture_id = "fx"
        path = "a.lean"
        run_on = "candidate"
        expected_exit = 0
        expected_diagnostic_regex = None
        expected_diagnostics: list[str] = []

    class FakeSuite:
        suite_id = "suite"
        obligation_ids = ["O-01"]
        fixtures = [Entry()]

    monkeypatch.setattr(fr, "load_fixture_suite", lambda *_a, **_k: (FakeSuite(), {"ok": True}))
    monkeypatch.setattr(fr, "has_lakefile", lambda _p: True)
    monkeypatch.setattr(fr, "lean_toolchain_available", lambda _p: True)
    monkeypatch.setattr(
        fr,
        "_try_lake_env_lean",
        lambda *_a, **_k: {
            "ok": False,
            "reason": "lake_invoke_error",
            "exit_code": None,
            "stderr": "boom",
        },
    )
    result = fr.collect_fixture_suite(
        provider,
        _ctx(tmp_path, candidate),
        kind="examples",
        check_id="semantic.project_examples",
        expected_success=True,
    )
    assert result.findings[0].status is FindingStatus.UNKNOWN
    assert result.findings[0].details["unknowns"] == ["fx"]


def test_collect_fixture_suite_missing_and_non_lean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ok.json").write_text("{}", encoding="utf-8")
    candidate = CandidateDescriptor(
        candidate_id="cand-fix",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    provider = SimpleNamespace(provider_id="p", provider_version="0.2.0")

    class Entry:
        def __init__(self, fid: str, path: str) -> None:
            self.fixture_id = fid
            self.path = path
            self.run_on = "both"
            self.expected_exit = 0
            self.expected_diagnostic_regex = None
            self.expected_diagnostics: list[str] = []

    class FakeSuite:
        suite_id = "suite-mixed"
        obligation_ids = ["O-01"]
        fixtures = [Entry("missing", "gone.lean"), Entry("json", "ok.json")]

    monkeypatch.setattr(
        fr,
        "load_fixture_suite",
        lambda *_a, **_k: (FakeSuite(), {"ok": True}),
    )
    monkeypatch.setattr(fr, "has_lakefile", lambda _p: True)
    monkeypatch.setattr(fr, "lean_toolchain_available", lambda _p: True)

    result = fr.collect_fixture_suite(
        provider,
        _ctx(tmp_path, candidate),
        kind="examples",
        check_id="semantic.project_examples",
        expected_success=True,
    )
    unknowns = set(result.findings[0].details["unknowns"])
    assert "missing" in unknowns
    assert "json" in unknowns
