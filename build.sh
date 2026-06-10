#!/bin/bash
set -e
# Upgrade pip first to get latest wheel support
pip install --upgrade pip setuptools wheel
# Install pydantic with binary wheel
pip install --prefer-binary pydantic-core==2.27.2 || pip install pydantic
# Install remaining dependencies
pip install --prefer-binary fastapi uvicorn httpx tree-sitter tree-sitter-python qdrant-client numpy aiofiles python-dotenv