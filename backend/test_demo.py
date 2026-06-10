"""
Mock integration tests for DocAnchor demo scenarios.
Run with: pytest test_demo.py -v
"""

import pytest
from datetime import datetime, timezone
from app.mocks.mock_interfaces import (
    get_mock_commit,
    mock_llm_rewrite,
    mock_create_pr,
)
from app.services.symbol_extractor import extract_symbols_from_diff_text
from app.services.doc_parser import parse_doc_content
from app.services.drift_scorer import score_all_blocks, generate_changelog


class TestMockScenarios:
    def test_scenario_0_process_payment_drift(self):
        commit = get_mock_commit(0)
        symbols = []
        for f in commit.changed_files:
            symbols.extend(extract_symbols_from_diff_text(f.patch))
        assert "process_payment" in symbols

    @pytest.mark.asyncio
    async def test_scenario_0_llm_rewrite(self):
        rewrite = await mock_llm_rewrite("### process_payment", "old content", "diff")
        assert "multi-currency" in rewrite
        assert "tax" in rewrite

    def test_scenario_0_changelog(self):
        from app.models.schemas import DriftResult
        drift = DriftResult(
            doc_block_id="test",
            doc_path="test.md",
            section_heading="### process_payment",
            drift_score=65.0,
            changed_symbols=["process_payment"],
            original_content="old",
            suggested_rewrite="new content",
        )
        changelog = generate_changelog([drift], ["feat: ..."])
        assert "process_payment" in changelog


class TestAutoUpdatingPRs:
    @pytest.mark.asyncio
    async def test_mock_pr_creation(self):
        from app.models.schemas import PRRequest
        pr = await mock_create_pr(PRRequest(
            repo="test/repo",
            base_branch="main",
            head_branch="docanchor/fix-test",
            title="test",
            body="test",
            file_changes={"test.md": "content"},
        ))
        assert pr.pr_number > 100
        assert pr.status == "open"


class TestDocDebtTracking:
    def test_freshness_score(self):
        from app.models.schemas import DriftResult
        results = [
            DriftResult(doc_block_id="a", doc_path="a.md", section_heading="a",
                      drift_score=30.0, changed_symbols=[], original_content=""),
            DriftResult(doc_block_id="b", doc_path="b.md", section_heading="b",
                      drift_score=70.0, changed_symbols=[], original_content=""),
        ]
        freshness = sum(r.drift_score for r in results) / len(results)
        assert freshness == 50.0

    def test_stale_critical_counts(self):
        from app.models.schemas import DriftResult
        results = [
            DriftResult(doc_block_id="a", doc_path="a.md", section_heading="a",
                      drift_score=20.0, changed_symbols=[], original_content=""),
            DriftResult(doc_block_id="b", doc_path="b.md", section_heading="b",
                      drift_score=50.0, changed_symbols=[], original_content=""),
            DriftResult(doc_block_id="c", doc_path="c.md", section_heading="c",
                      drift_score=80.0, changed_symbols=[], original_content=""),
        ]
        stale = sum(1 for r in results if r.drift_score > 40)
        critical = sum(1 for r in results if r.drift_score > 70)
        assert stale == 2
        assert critical == 1


class TestExecutableDocs:
    @pytest.mark.asyncio
    async def test_python_code_execution(self):
        from app.services.doc_executor import verify_doc_examples
        result = await verify_doc_examples(
            "```python\nx = 1\ny = 2\nprint(x + y)\n```",
            "test.md",
            "test",
        )
        assert len(result) == 1
        assert result[0].passed


class TestChangelogGeneration:
    def test_changelog_format(self):
        from app.models.schemas import DriftResult
        drifts = [
            DriftResult(doc_block_id="a", doc_path="a.md", section_heading="### process_payment",
                      drift_score=65.0, changed_symbols=["process_payment"], original_content="old",
                      suggested_rewrite="new content"),
        ]
        changelog = generate_changelog(drifts, [])
        assert "# Auto-Generated Documentation Changelog" in changelog
        assert "process_payment" in changelog