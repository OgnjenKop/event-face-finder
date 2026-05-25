#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-.venv/bin/python}"

"$PYTHON" -m event_face_finder gui "$@"
