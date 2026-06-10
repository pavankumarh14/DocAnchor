#!/usr/bin/env bash
# Start the DocAnchor frontend (Vite + React)
set -e

cd "$(dirname "$0")/frontend"

# Install node modules if needed
if [ ! -d node_modules ]; then
  echo "Installing npm dependencies..."
  npm install
fi

echo ""
echo "Starting DocAnchor frontend on http://localhost:3000"
echo ""

npm run dev
