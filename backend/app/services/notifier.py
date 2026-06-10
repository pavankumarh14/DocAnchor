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

# Thresholds — tune these in production
DRIFT_ALERT_THRESHOLD = 60       # drift_score above which we alert
READ_COUNT_ALERT_THRESHOLD = 500  # only alert for high-traffic doc sections


async def notify_drift_detected(
    repo_health: RepoHealth,
    stale_results: List[DriftResult],
    channel: str = "slack",  # "slack" | "teams" | "both"
) -> None:
    """
    Send a notification for every high-traffic stale doc block.

    Filters stale_results to blocks where:
      - drift_score   > DRIFT_ALERT_THRESHOLD
      - read_count    > READ_COUNT_ALERT_THRESHOLD
    """
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


async def send_slack_message(webhook_url: str, message: dict) -> bool:
    """POST a Block Kit message payload to a Slack incoming webhook URL."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=message)
            return resp.status_code == 200
    except Exception as exc:
        logger.warning("Slack notification failed: %s", exc)
        return False


def _format_slack_message(repo: str, result: DriftResult) -> dict:
    """Build a Slack Block Kit payload for a single stale doc block."""
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
    """POST an Adaptive Card payload to a Microsoft Teams incoming webhook."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=message)
            return resp.status_code == 200 and resp.text.strip() == "1"
    except Exception as exc:
        logger.warning("Teams notification failed: %s", exc)
        return False


def _format_teams_message(repo: str, result: DriftResult) -> dict:
    """Build a Microsoft Teams Adaptive Card payload for a stale doc block."""
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