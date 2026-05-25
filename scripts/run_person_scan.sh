#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 PERSON_ID PHOTOS_ROOT [PHOTOS_ROOT ...]"
  echo
  echo "Example:"
  echo "  mkdir -p reference_people/alex"
  echo "  cp /path/to/alex-reference/*.jpg reference_people/alex/"
  echo "  $0 alex /path/to/event/photos"
  exit 2
fi

PYTHON="${PYTHON:-.venv/bin/python}"
PERSON_ID="$1"
shift

photos_root_args=()
for photos_root in "$@"; do
  photos_root_args+=(--photos-root "$photos_root")
done

"$PYTHON" -m event_face_finder run-person \
  --person-id "$PERSON_ID" \
  "${photos_root_args[@]}"
