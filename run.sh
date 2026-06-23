#!/bin/bash
# Wrapper launchd invokes — cd's into the project, runs scan.py in the venv, logs output.
cd "$(dirname "$0")"
mkdir -p logs
./.venv/bin/python scan.py >> "logs/scheduled-$(date +%Y%m%d).log" 2>&1
