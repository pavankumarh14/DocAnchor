#!/usr/bin/env python3
"""
DocAnchor Demo Script - Run this to see all features in action.
"""

import asyncio
import sys
sys.path.insert(0, '/app/backend')

from app.mocks.mock_interfaces import get_mock_commit, mock_llm_rewrite, mock_create_pr, list_mock_commits
from app.services.symbol_extractor import extract_symbols_from_diff_text
from app.services.doc_parser import parse_all_docs
from app.services.drift_scorer import score_all_blocks, generate_changelog
from app.services.vector_index import build_symbol_doc_map, index_doc_blocks


async def run_demo():
    print("=" * 60)
    print("DocAnchor Demo - Documentation Drift Detection")
    print("=" * 60)
    
    print("\n📋 Available demo scenarios:")
    for c in list_mock_commits():
        print(f"  - {c.message}")
    
    print("\n🔍 Running Scenario 0 (process_payment drift)...")
    commit = get_mock_commit(0)
    
    print(f"  Commit: {commit.commit_sha}")
    print(f"  Message: {commit.message}")
    
    symbols = []
    for f in commit.changed_files:
        syms = extract_symbols_from_diff_text(f.patch)
        symbols.extend(syms)
    print(f"  Changed symbols: {symbols}")
    
    print("\n📄 Loading docs...")
    doc_blocks = parse_all_docs("/app/sample_repo/docs")
    print(f"  Found {len(doc_blocks)} doc blocks")
    
    print("\n🔗 Building symbol-to-doc links...")
    build_symbol_doc_map(doc_blocks, [])
    
    print("\n📊 Scoring drift...")
    drift_results = score_all_blocks(doc_blocks, symbols, commit.timestamp)
    stale = [r for r in drift_results if r.drift_score > 30]
    print(f"  Stale blocks: {len(stale)}")
    for r in stale[:3]:
        print(f"    - {r.section_heading}: {r.drift_score}")
    
    print("\n✍️  LLM rewrites...")
    for r in stale[:2]:
        rewrite = await mock_llm_rewrite(r.section_heading, r.original_content, "diff")
        print(f"  Rewritten {r.section_heading[:40]}...")
    
    print("\n📝 Changelog:")
    print(generate_changelog(stale, [commit.message]))
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(run_demo())