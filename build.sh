#!/bin/bash
set -e
# Install without pydantic-core Rust dependency
pip install --prefer-binary --no-build-isolation pydantic==2.6.4 || pip install --prefer-binary pydantic
pip install --prefer-binary fastapi uvicorn httpx tree-sitter tree-sitter-python qdrant-client numpy aiofiles python-dotenv