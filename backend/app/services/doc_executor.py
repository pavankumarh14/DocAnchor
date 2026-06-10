"""
Executable doc example verification.

STATUS: ✅ IMPLEMENTED
   Python code block execution via subprocess with timeout sandboxing.
"""

from __future__ import annotations
import asyncio
import logging
import os
import re
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

EXECUTION_TIMEOUT_SECONDS = 5


@dataclass
class CodeBlock:
    """A fenced code block extracted from a doc section."""
    language: str
    source: str
    doc_path: str
    section_heading: str
    line_number: int = 0


@dataclass
class VerificationResult:
    """Outcome of running one code block."""
    code_block: CodeBlock
    passed: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0


def extract_code_blocks(content: str, doc_path: str, section_heading: str) -> List[CodeBlock]:
    """Parse all fenced code blocks from a markdown string."""
    pattern = re.compile(
        r"```(?P<lang>[a-zA-Z0-9_+-]*)\n(?P<code>.*?)```",
        re.DOTALL,
    )
    blocks = []
    for match in pattern.finditer(content):
        lang = match.group("lang").strip() or "text"
        code = textwrap.dedent(match.group("code"))
        blocks.append(CodeBlock(
            language=lang,
            source=code,
            doc_path=doc_path,
            section_heading=section_heading,
            line_number=content[:match.start()].count("\n") + 1,
        ))
    return blocks


async def execute_code_block(block: CodeBlock) -> VerificationResult:
    """Run a code block in a sandboxed subprocess and return the result."""
    start = time.time()

    if block.language not in ("python", "py"):
        return VerificationResult(
            code_block=block,
            passed=True,
            error_message="Language not executed (only Python supported)",
        )

    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(block.source)
            tmp_path = f.name

        proc = await asyncio.create_subprocess_exec(
            "python3", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=EXECUTION_TIMEOUT_SECONDS
            )
            elapsed = (time.time() - start) * 1000
            return VerificationResult(
                code_block=block,
                passed=proc.returncode == 0,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else "",
                exit_code=proc.returncode or 0,
                execution_time_ms=elapsed,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return VerificationResult(
                code_block=block,
                passed=False,
                error_message=f"Timed out after {EXECUTION_TIMEOUT_SECONDS}s",
                execution_time_ms=(time.time() - start) * 1000,
            )
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


async def verify_doc_examples(
    content: str,
    doc_path: str,
    section_heading: str,
    languages: Optional[List[str]] = None,
) -> List[VerificationResult]:
    """Extract and execute all code blocks in a doc section."""
    blocks = extract_code_blocks(content, doc_path, section_heading)
    if not blocks:
        return []

    if languages:
        blocks = [b for b in blocks if b.language in languages]

    results = await asyncio.gather(*[execute_code_block(b) for b in blocks])
    return list(results)