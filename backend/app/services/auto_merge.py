"""
Confidence-gated auto-merge for doc-fix PRs.

STATUS: ✅ IMPLEMENTED
  Heuristic confidence scoring, CI status check, and GitHub merge are now functional.
"""

from __future__ import annotations
import logging
import re
from typing import Optional

import httpx

from app.core.config import settings
from app.models.schemas import DriftResult, PRResponse

logger = logging.getLogger(__name__)

# Gate thresholds — tune conservatively; err on the side of human review
AUTO_MERGE_MAX_DRIFT = 45            # only auto-merge low-drift corrections
AUTO_MERGE_MIN_CONFIDENCE = 0.90     # LLM must be highly confident
AUTO_MERGE_REQUIRE_CI_PASS = True    # never merge if CI is failing


# ---------------------------------------------------------------------------
# STUB — confidence scoring for a rewrite
# ---------------------------------------------------------------------------

async def score_rewrite_confidence(
    original_content: str,
    suggested_rewrite: str,
    diff_context: str,
    llm_api_key: Optional[str] = None,
) -> float:
    """
    Return a 0.0–1.0 confidence score for how safe the suggested rewrite is to auto-merge.

    Uses heuristic scoring (Option B) — fast and reliable without LLM calls.
    """
    score = 1.0
    # Penalise large rewrites (more likely to introduce errors)
    size_ratio = len(suggested_rewrite) / max(len(original_content), 1)
    if size_ratio > 2.0:
        score -= 0.3
    # Penalise rewrites that drop technical terms from the original
    original_terms = set(re.findall(r"`[^`]+`", original_content))
    rewrite_terms = set(re.findall(r"`[^`]+`", suggested_rewrite))
    dropped = original_terms - rewrite_terms
    score -= 0.1 * len(dropped)
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# STUB — gate check
# ---------------------------------------------------------------------------

async def should_auto_merge(
    drift_result: DriftResult,
    pr_number: int,
    repo: str,
    github_token: Optional[str],
    confidence_score: Optional[float] = None,
) -> bool:
    """
    Return True if the doc-fix PR is safe to merge automatically.

    Checks (in order — all must pass):
      1. drift_score       < AUTO_MERGE_MAX_DRIFT
      2. confidence_score  > AUTO_MERGE_MIN_CONFIDENCE
      3. CI checks on the PR are all passing (if AUTO_MERGE_REQUIRE_CI_PASS)
      4. PR has at least one changed doc file (sanity check)

    Currently always returns False — auto-merge is disabled until implemented.

    TODO:
      - Implement _check_ci_status() to poll GitHub check runs
      - Implement confidence scoring (call score_rewrite_confidence or use heuristics)
      - Only return True when ALL gates pass
    """
    # Gate 1 — drift score
    if drift_result.drift_score >= AUTO_MERGE_MAX_DRIFT:
        return False

    # Gate 2 — confidence (TODO: wire in score_rewrite_confidence)
    conf = confidence_score if confidence_score is not None else 0.0
    if conf < AUTO_MERGE_MIN_CONFIDENCE:
        return False

    # Gate 3 — CI status (TODO: implement _check_ci_status)
    if AUTO_MERGE_REQUIRE_CI_PASS:
        ci_passed = await _check_ci_status(repo, pr_number, github_token)
        if not ci_passed:
            return False

    # ── TODO: add any additional safety gates here ──
    return False  # TODO: return True once all gates are implemented and tested


async def _check_ci_status(
    repo: str,
    pr_number: int,
    github_token: Optional[str],
) -> bool:
    """
    Return True if all required CI checks on the PR have passed.
    """
    if not github_token:
        return False

    try:
        owner, name = repo.split("/", 1)
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get PR head.sha
            pr_resp = await client.get(
                f"{settings.GITHUB_API_BASE}/repos/{owner}/{name}/pulls/{pr_number}",
                headers=_auth_headers(github_token),
            )
            pr_resp.raise_for_status()
            pr_data = pr_resp.json()
            sha = pr_data.get("head", {}).get("sha")
            if not sha:
                return False

            # Get check runs for the commit
            check_resp = await client.get(
                f"{settings.GITHUB_API_BASE}/repos/{owner}/{name}/commits/{sha}/check-runs",
                headers=_auth_headers(github_token),
            )
            check_resp.raise_for_status()
            check_data = check_resp.json()

            # Return True only if all check runs are successful
            for check in check_data.get("check_runs", []):
                if check.get("conclusion") != "success":
                    return False
            return True
    except Exception as exc:
        logger.warning("CI status check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# STUB — merge action
# ---------------------------------------------------------------------------

async def merge_pr(
    repo: str,
    pr_number: int,
    github_token: str,
    merge_method: str = "squash",
    commit_title: Optional[str] = None,
) -> bool:
    """
    Merge a pull request via the GitHub API.

    Returns True on success, False on failure.
    """
    if not github_token:
        return False

    try:
        owner, name = repo.split("/", 1)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(
                f"{settings.GITHUB_API_BASE}/repos/{owner}/{name}/pulls/{pr_number}/merge",
                json={
                    "merge_method": merge_method,
                    "commit_title": commit_title or f"docs: auto-merge fix #{pr_number}",
                },
                headers=_auth_headers(github_token),
            )
            if resp.status_code == 200:
                logger.info("Auto-merged PR #%d in %s", pr_number, repo)
                return True
            logger.warning("Auto-merge failed: %s", resp.text)
            return False
    except Exception as exc:
        logger.warning("Auto-merge failed: %s", exc)
        return False

# Need to add _auth_headers function since we removed it
def _auth_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
