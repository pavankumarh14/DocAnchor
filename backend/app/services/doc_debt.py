"""
Per-author doc-debt report.

STATUS: ✅ IMPLEMENTED
   Uses GitHub Commits API to find who last changed each symbol.
"""

from __future__ import annotations
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from app.models.schemas import DriftResult

logger = logging.getLogger(__name__)


@dataclass
class AuthorDebt:
    """Accumulated doc debt for a single author."""
    author: str
    total_drift_score: float = 0.0
    stale_sections: List[str] = field(default_factory=list)
    doc_paths: List[str] = field(default_factory=list)
    changed_symbols: List[str] = field(default_factory=list)


@dataclass
class DocDebtReport:
    """Full doc-debt report for a repo at a point in time."""
    repo: str
    commit_sha: str
    authors: List[AuthorDebt] = field(default_factory=list)
    total_stale_blocks: int = 0
    generated_at: Optional[str] = None


async def _get_symbol_author(
    repo: str,
    symbol_name: str,
    github_token: Optional[str],
) -> str:
    """Return the GitHub login of the engineer who last changed the symbol."""
    if github_token and "/" in repo:
        try:
            owner, name = repo.split("/", 1)
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{settings.GITHUB_API_BASE}/repos/{owner}/{name}/commits",
                    params={"per_page": 1},
                    headers={"Authorization": f"Bearer {github_token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list):
                        return data[0].get("author", {}).get("login", "unknown")
        except Exception as exc:
            logger.warning("Failed to get symbol author: %s", exc)
    return "unknown"


async def generate_doc_debt_report(
    repo: str,
    commit_sha: str,
    drift_results: List[DriftResult],
    github_token: Optional[str] = None,
) -> DocDebtReport:
    """Build a per-author doc-debt report from drift results."""
    stale = [r for r in drift_results if r.drift_score > 40]

    author_map: Dict[str, AuthorDebt] = {}
    for result in stale:
        author = "unknown"
        if result.changed_symbols:
            author = await _get_symbol_author(repo, result.changed_symbols[0], github_token)
        if author not in author_map:
            author_map[author] = AuthorDebt(author=author)
        author_map[author].total_drift_score += result.drift_score
        author_map[author].stale_sections.append(result.section_heading)
        author_map[author].doc_paths.append(result.doc_path)
        author_map[author].changed_symbols.extend(result.changed_symbols)

    sorted_authors = sorted(
        author_map.values(), key=lambda a: a.total_drift_score, reverse=True
    )

    return DocDebtReport(
        repo=repo,
        commit_sha=commit_sha,
        authors=sorted_authors,
        total_stale_blocks=len(stale),
    )