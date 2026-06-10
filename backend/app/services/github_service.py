"""
GitHub API integration — real pull request creation.

STATUS: ✅ IMPLEMENTED
   Both _push_file_changes_to_branch() and github_create_pr() are now functional.
"""

from __future__ import annotations
import base64
import logging
from typing import Dict, Optional

import httpx

from app.core.config import settings
from app.models.schemas import PRRequest, PRResponse

logger = logging.getLogger(__name__)

_HEADERS_BASE = {
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _auth_headers(token: str) -> dict:
    return {**_HEADERS_BASE, "Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# STUB — implement this
# ---------------------------------------------------------------------------

async def _push_file_changes_to_branch(
    owner: str,
    repo: str,
    base_branch: str,
    head_branch: str,
    file_changes: Dict[str, str],
    commit_message: str,
    token: str,
) -> str:
    """
    Push file_changes to a new branch and return the head_branch name.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Get the current HEAD SHA of the base branch
        ref_resp = await client.get(
            f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/git/ref/heads/{base_branch}",
            headers=_auth_headers(token),
        )
        ref_resp.raise_for_status()
        head_sha = ref_resp.json()["object"]["sha"]

        # Step 2: Get the tree SHA of that commit
        commit_resp = await client.get(
            f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/git/commits/{head_sha}",
            headers=_auth_headers(token),
        )
        commit_resp.raise_for_status()
        tree_sha = commit_resp.json()["tree"]["sha"]

        # Step 3-4: Create blobs for each file and build a new tree
        tree_items = []
        for file_path, content in file_changes.items():
            blob_resp = await client.post(
                f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/git/blobs",
                json={"content": base64.b64encode(content.encode()).decode(), "encoding": "base64"},
                headers=_auth_headers(token),
            )
            blob_resp.raise_for_status()
            blob_sha = blob_resp.json()["sha"]
            tree_items.append({
                "path": file_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        # Step 4: Create a new tree
        tree_resp = await client.post(
            f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees",
            json={"base_tree": tree_sha, "tree": tree_items},
            headers=_auth_headers(token),
        )
        tree_resp.raise_for_status()
        new_tree_sha = tree_resp.json()["sha"]

        # Step 5: Create a commit
        new_commit_resp = await client.post(
            f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/git/commits",
            json={"message": commit_message, "tree": new_tree_sha, "parents": [head_sha]},
            headers=_auth_headers(token),
        )
        new_commit_resp.raise_for_status()
        new_commit_sha = new_commit_resp.json()["sha"]

        # Step 6: Create (or update) the head branch
        ref_create_resp = await client.post(
            f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{head_branch}", "sha": new_commit_sha},
            headers=_auth_headers(token),
        )
        if ref_create_resp.status_code not in (200, 201):
            # If branch exists, try to update it (delete + recreate pattern)
            try:
                patch_resp = await client.patch(
                    f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/git/refs/heads/{head_branch}",
                    json={"sha": new_commit_sha},
                    headers=_auth_headers(token),
                )
                patch_resp.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning("Could not create or update branch %s", head_branch)

        return head_branch


# ---------------------------------------------------------------------------
# PR creation — calls _push_file_changes_to_branch first (once implemented)
# ---------------------------------------------------------------------------

async def github_create_pr(
    request: PRRequest,
    github_token: str,
) -> PRResponse:
    """
    Open a real GitHub pull request with the doc fixes.
    """
    if not github_token:
        raise ValueError("GitHub token is required for real PR creation")

    repo_parts = request.repo.split("/")
    if len(repo_parts) != 2:
        raise ValueError(f"Invalid repo format: {request.repo}. Expected 'owner/repo'")
    owner, repo_name = repo_parts

    await _push_file_changes_to_branch(
        owner=owner,
        repo=repo_name,
        base_branch=request.base_branch,
        head_branch=request.head_branch,
        file_changes=request.file_changes,
        commit_message=f"docs: {request.title}",
        token=github_token,
    )

    pr_payload = {
        "title": request.title,
        "body": request.body,
        "head": request.head_branch,
        "base": request.base_branch,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo_name}/pulls",
            json=pr_payload,
            headers=_auth_headers(github_token),
        )
        resp.raise_for_status()
        data = resp.json()

    return PRResponse(
        pr_number=data["number"],
        pr_url=data["html_url"],
        head_branch=data["head"]["ref"],
        status="open",
    )


async def choose_github_pr(request: PRRequest, github_token: Optional[str]) -> PRResponse:
    """Create a real GitHub PR if token is provided, otherwise raise an error."""
    if not github_token:
        raise ValueError("No GitHub token provided for PR creation")
    return await github_create_pr(request, github_token)
