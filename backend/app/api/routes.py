"""FastAPI route definitions for DocAnchor."""

from __future__ import annotations
import asyncio
import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.models.schemas import (
    CommitPayload,
    AnalysisJob,
    DashboardMetrics,
    JobStatus,
    FileDiff,
)
from app.workers.analysis_worker import run_analysis, get_job, list_jobs
from app.mocks.mock_interfaces import get_mock_commit, list_mock_commits

import logging
logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Mock-based webhook (commit_index picks one of the 4 demo scenarios)
# ---------------------------------------------------------------------------

class WebhookRequest(BaseModel):
    commit_index: Optional[int] = 0
    llm_api_key: Optional[str] = None
    github_token: Optional[str] = None
    custom_path: Optional[str] = None
    custom_patch: Optional[str] = None


@router.post("/webhook/github", summary="Receive a commit webhook")
async def receive_webhook(
    body: WebhookRequest,
    background_tasks: BackgroundTasks,
):
    api_key = body.llm_api_key.strip() if body.llm_api_key else None
    github_token = body.github_token.strip() if body.github_token else None

    if body.custom_path and body.custom_patch:
        cp = body.custom_path.strip()
        patch_text = body.custom_patch
        if not cp:
            raise HTTPException(400, "custom_path must be a non-empty relative path")
        if cp.startswith("/") or ".." in cp:
            raise HTTPException(400, "custom_path must be a safe relative path")
        if len(patch_text) > 20000:
            raise HTTPException(400, "custom_patch is too large (max 20000 characters)")
        if not patch_text.strip():
            raise HTTPException(400, "custom_patch must contain content to evaluate")
        commit = CommitPayload(
            repo=settings.MOCK_GITHUB_REPO,
            commit_sha=f"custom-{uuid.uuid4().hex[:8]}",
            branch="local/custom",
            author="local",
            message="Custom input run",
            timestamp=datetime.now(timezone.utc),
            changed_files=[
                FileDiff(
                    path=cp,
                    patch=patch_text,
                    additions=0,
                    deletions=0,
                )
            ],
        )
    else:
        commit = get_mock_commit(body.commit_index or 0)

    job = AnalysisJob(
        job_id=str(uuid.uuid4()),
        repo=commit.repo,
        commit_sha=commit.commit_sha,
        status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )

    background_tasks.add_task(run_analysis, job, commit, api_key, github_token)
    return {"job_id": job.job_id, "status": job.status, "commit": commit.commit_sha}


# ---------------------------------------------------------------------------
# Real GitHub push-event webhook
# ---------------------------------------------------------------------------

class GitHubPushEvent(BaseModel):
    ref: str
    repository: dict
    commits: list = []
    sender: dict = {}
    head_commit: Optional[dict] = None


@router.post("/webhook/push", summary="Receive a real GitHub push event")
async def receive_push_webhook(
    request: Request,
    body: GitHubPushEvent,
    background_tasks: BackgroundTasks,
):
    signature = request.headers.get("X-Hub-Signature-256", "")
    if settings.WEBHOOK_SECRET:
        payload_bytes = await request.body()
        expected = hmac.new(
            settings.WEBHOOK_SECRET.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(f"sha256={expected}", signature):
            raise HTTPException(401, "Invalid webhook signature")

    repo = body.repository.get("full_name", "")
    commits = body.commits or []
    if not commits:
        raise HTTPException(400, "No commits in push event")

    for commit in commits:
        commit_sha = commit.get("id", "")
        from app.services.github_fetcher import build_commit_payload
        try:
            commit_payload = await build_commit_payload(repo, commit_sha, settings.GITHUB_TOKEN)
        except Exception as exc:
            logger.warning("Failed to build payload for %s: %s", commit_sha, exc)
            continue

        job = AnalysisJob(
            job_id=str(uuid.uuid4()),
            repo=repo,
            commit_sha=commit_sha,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        background_tasks.add_task(run_analysis, job, commit_payload, None, settings.GITHUB_TOKEN, None)

    return {"status": "accepted", "jobs_scheduled": len(commits)}


# ---------------------------------------------------------------------------
# Real GitHub repo analysis
# ---------------------------------------------------------------------------

class GithubCommitsRequest(BaseModel):
    repo: str
    github_token: str
    limit: int = 5


@router.post("/github/commits", summary="Fetch recent commits from a real GitHub repo")
async def list_github_commits(body: GithubCommitsRequest):
    from app.services.github_fetcher import fetch_repo_commits
    try:
        commits = await fetch_repo_commits(
            body.repo, body.github_token, min(body.limit, 10)
        )
        return commits
    except httpx.HTTPStatusError as exc:
        raise HTTPException(exc.response.status_code, f"GitHub API error: {exc.response.text}")
    except Exception as exc:
        raise HTTPException(400, str(exc))


class RepoAnalysisRequest(BaseModel):
    repo: str
    sha: str
    github_token: str
    llm_api_key: Optional[str] = None


@router.post("/analyze/repo", summary="Analyze a real GitHub commit for doc drift")
async def analyze_repo_commit(
    body: RepoAnalysisRequest,
    background_tasks: BackgroundTasks,
):
    from app.services.github_fetcher import build_commit_payload, fetch_markdown_files

    try:
        commit = await build_commit_payload(body.repo, body.sha, body.github_token)
        markdown_docs = await fetch_markdown_files(body.repo, body.sha, body.github_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            exc.response.status_code,
            f"GitHub API error: {exc.response.text[:300]}",
        )
    except Exception as exc:
        raise HTTPException(400, f"Could not fetch from GitHub: {exc}")

    job = AnalysisJob(
        job_id=str(uuid.uuid4()),
        repo=body.repo,
        commit_sha=commit.commit_sha,
        status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )

    background_tasks.add_task(
        run_analysis,
        job,
        commit,
        body.llm_api_key,
        body.github_token,
        markdown_docs,
    )
    return {"job_id": job.job_id, "status": job.status, "commit": commit.commit_sha}


# ---------------------------------------------------------------------------
# GitHub token validation
# ---------------------------------------------------------------------------

class GithubValidateRequest(BaseModel):
    token: str


@router.post("/github/validate", summary="Validate a GitHub token")
async def validate_github_token(body: GithubValidateRequest):
    token = body.token.strip()
    if not token:
        return {"connected": False, "login": None, "name": None, "scopes": None, "error": "No token provided"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "connected": True,
                    "login": data.get("login"),
                    "name": data.get("name"),
                    "scopes": resp.headers.get("X-OAuth-Scopes", ""),
                    "error": None,
                }
            return {
                "connected": False, "login": None, "name": None, "scopes": None,
                "error": f"GitHub returned {resp.status_code}",
            }
    except Exception as exc:
        return {"connected": False, "login": None, "name": None, "scopes": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Job status polling
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}", summary="Poll job status")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id!r} not found")
    return job


@router.get("/jobs", summary="List all jobs")
async def list_all_jobs():
    return list_jobs()


# ---------------------------------------------------------------------------
# Dashboard data with release notes
# ---------------------------------------------------------------------------

@router.get("/dashboard/{job_id}", summary="Get dashboard metrics including release notes")
async def get_dashboard(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id!r} not found")
    if job.status != JobStatus.DONE:
        raise HTTPException(409, f"Job {job_id!r} is {job.status} – wait for DONE")
    
    from app.services.drift_scorer import generate_release_notes
    release_notes = generate_release_notes(
        job.result.drift_results,
        [c.message for c in job.result.recent_commits]
    )
    
    return {
        **job.result.model_dump(),
        "release_notes": release_notes,
    }


# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

@router.get("/mock/commits", summary="List available mock commit scenarios")
async def list_mock_commit_scenarios():
    commits = list_mock_commits()
    return [
        {
            "index": i,
            "sha": c.commit_sha,
            "author": c.author,
            "message": c.message,
            "branch": c.branch,
            "files": [f.path for f in c.changed_files],
        }
        for i, c in enumerate(commits)
    ]


@router.get("/config", summary="Show current config flags")
async def get_config():
    return {
        "USE_MOCKS": settings.USE_MOCKS,
        "MOCK_GITHUB_REPO": settings.MOCK_GITHUB_REPO,
        "SAMPLE_REPO_PATH": settings.SAMPLE_REPO_PATH,
        "LLM_CONFIGURED": bool(settings.LLM_API_KEY),
        "GITHUB_CONFIGURED": bool(settings.GITHUB_TOKEN),
    }