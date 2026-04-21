#!/bin/bash
# Provision Playwright and Chromium.
# `playwright install` is idempotent: it skips the download if the correct
# version is already cached, so this is a fast no-op after the first run.

if ! python -c "import playwright" 2>/dev/null; then
    echo "[setup] Installing playwright package..."
    pip install -q playwright
fi

echo "[setup] Ensuring Playwright Chromium is up to date..."
playwright install chromium
