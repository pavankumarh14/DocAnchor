"""
Notification service — alert engineers when high-traffic docs drift.

STATUS: ✅ IMPLEMENTED
   Slack and Teams webhook support with filtering and message formatting.
"""

from __future__ import annotations
import logging
from typing import List

import httpx

from app.core.config import settings
from app.models.schemas import DriftResult, RepoHealth

logger = logging.getLogger(__name__)

DRIFT_ALERT_THRESHOLD = 30
READ_COUNT_ALERT_THRESHOLD = 0


async def notify_drift_detected(
    repo_health: RepoHealth,
    stale_results: List[DriftResult],
    channel: str = "slack",
) -> None:
    for result in stale_results:
        if result.drift_score <= DRIFT_ALERT_THRESHOLD:
            continue
        if getattr(result, 'read_count', 0) <= READ_COUNT_ALERT_THRESHOLD:
            continue

        if channel in ("slack", "both"):
            message = _format_slack_message(repo_health.repo, result)
            webhook_url = settings.SLACK_WEBHOOK_URL
            if webhook_url:
                success = await send_slack_message(webhook_url, message)
                if success:
                    logger.info("Sent Slack notification for %s", result.doc_path)
                else:
                    logger.warning("Failed to send Slack notification for %s", result.doc_path)


async def notify_release_notes(
    repo: str,
    release_notes: str,
    drift_count: int,
) -> None:
    """Send release notes to Slack as a formatted message."""
    if not settings.SLACK_WEBHOOK_URL:
        return
    
    message = {
        "text": f"DocAnchor Release Notes: {drift_count} doc blocks updated in {repo}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":memo: Documentation Update: {drift_count} sections updated",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Repository:* `{repo}`\n*Updated sections:* {drift_count}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```\n{release_notes[:2000]}\n```",
                },
            },
        ],
    }
    
    await send_slack_message(settings.SLACK_WEBHOOK_URL, message)


async def send_slack_message(webhook_url: str, message: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=message)
            return resp.status_code == 200
    except Exception as exc:
        logger.warning("Slack notification failed: %s", exc)
        return False


def _format_slack_message(repo: str, result: DriftResult) -> dict:
    return {
        "text": f"DocAnchor alert: stale docs in {repo}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":warning: Doc drift detected in {repo}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Section:*\n{result.section_heading}"},
                    {"type": "mrkdwn", "text": f"*Drift score:*\n{result.drift_score:.0f} / 100"},
                    {"type": "mrkdwn", "text": f"*File:*\n`{result.doc_path}`"},
                ],
            },
        ],
    }


async def send_teams_message(webhook_url: str, message: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=message)
            return resp.status_code == 200 and resp.text.strip() == "1"
    except Exception as exc:
        logger.warning("Teams notification failed: %s", exc)
        return False


def _format_teams_message(repo: str, result: DriftResult) -> dict:
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"Doc drift detected in {repo}",
                            "weight": "bolder",
                            "size": "medium",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Section", "value": result.section_heading},
                                {"title": "Drift score", "value": f"{result.drift_score:.0f}/100"},
                            ],
                        },
                    ],
                },
            }
        ],
    }