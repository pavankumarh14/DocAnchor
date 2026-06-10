"""
Drift scoring engine.
Computes a 0-100 staleness score for each doc block based on
how many of the symbols it references have changed and how recently.
No mocking – pure computation.
"""

from __future__ import annotations
from typing import List, Dict
from datetime import datetime, timezone
import math

from app.models.schemas import DocBlock, DriftResult, CodeSymbol


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

RECENCY_HALF_LIFE_DAYS = 30
SYMBOL_WEIGHT = 0.65
RECENCY_WEIGHT = 0.35
STALE_THRESHOLD = 40.0
CRITICAL_THRESHOLD = 70.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recency_factor(changed_at: datetime) -> float:
    now = datetime.now(timezone.utc)
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - changed_at).total_seconds() / 86400)
    return math.exp(-math.log(2) * age_days / RECENCY_HALF_LIFE_DAYS)


def _symbol_coverage(doc_symbols: List[str], changed_symbol_names: List[str]) -> float:
    if not doc_symbols:
        return 0.0
    changed_set = set(changed_symbol_names)
    hits = sum(1 for s in doc_symbols if s in changed_set)
    return hits / len(doc_symbols)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_drift(
    doc_block: DocBlock,
    changed_symbol_names: List[str],
    changed_at: datetime,
) -> float:
    if not doc_block.symbols:
        return 0.0

    changed_set = set(changed_symbol_names)
    hit_count = sum(1 for s in doc_block.symbols if s in changed_set)
    if hit_count == 0:
        return 0.0

    coverage = math.sqrt(hit_count / len(doc_block.symbols))
    recency = _recency_factor(changed_at)

    raw = SYMBOL_WEIGHT * coverage + RECENCY_WEIGHT * recency
    score = min(100.0, raw * 100.0)
    return round(score, 1)


def score_all_blocks(
    doc_blocks: List[DocBlock],
    changed_symbol_names: List[str],
    changed_at: datetime,
) -> List[DriftResult]:
    results: List[DriftResult] = []
    changed_set = set(changed_symbol_names)

    for block in doc_blocks:
        affected = [s for s in block.symbols if s in changed_set]
        if not affected:
            score = 0.0
        else:
            score = score_drift(block, changed_symbol_names, changed_at)

        results.append(
            DriftResult(
                doc_block_id=block.id,
                doc_path=block.doc_path,
                section_heading=block.section_heading,
                drift_score=score,
                changed_symbols=affected,
                original_content=block.content,
            )
        )

    results.sort(key=lambda r: r.drift_score, reverse=True)
    return results


def compute_repo_freshness(drift_results: List[DriftResult]) -> float:
    if not drift_results:
        return 100.0
    avg_staleness = sum(r.drift_score for r in drift_results) / len(drift_results)
    return round(100.0 - avg_staleness, 1)


def generate_changelog(drift_results: List[DriftResult], commit_messages: List[str]) -> str:
    if not drift_results:
        return "No documentation changes required."

    stale = [r for r in drift_results if r.drift_score > 30]
    if not stale:
        return "No significant documentation changes detected."

    lines = ["# Auto-Generated Documentation Changelog\n"]
    lines.append("## Updated Sections\n")

    for r in stale:
        symbols_str = ", ".join(r.changed_symbols) if r.changed_symbols else "general"
        lines.append(f"- **{r.section_heading}** (symbols: {symbols_str})")
        lines.append(f"  - Drift score: {r.drift_score:.0f}/100")
        if r.suggested_rewrite:
            preview = r.suggested_rewrite.split("\n")[0][:80]
            lines.append(f"  - Preview: {preview}...")

    lines.append(f"\n**Total sections updated:** {len(stale)}")
    return "\n".join(lines)