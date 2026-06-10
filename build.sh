#!/bin/bash
set -e
# Install pydantic-core first with specific binary
pip install pydantic_core-2.27.2-cp314-cp314-manylinux_2_28_x86_64.whl || pip install pydantic==2.7.1
pip install fastapi uvicorn httpx tree-sitter tree-sitter-python qdrant-client numpy aiofiles python-dotenv