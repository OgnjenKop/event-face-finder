#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 REFERENCE_DIR PHOTOS_ROOT [PHOTOS_ROOT ...]"
  echo
  echo "Example:"
  echo "  $0 reference_people/alex /path/to/event/photos"
  exit 2
fi

PYTHON="${PYTHON:-python}"
REFERENCE_DIR="$1"
shift

photos_root_args=()
for photos_root in "$@"; do
  photos_root_args+=(--photos-root "$photos_root")
done

mkdir -p outputs

"$PYTHON" -m event_face_finder build-reference \
  --reference-dir "$REFERENCE_DIR" \
  --output outputs/reference_profile.npz

"$PYTHON" -m event_face_finder scan \
  "${photos_root_args[@]}" \
  --reference-profile outputs/reference_profile.npz \
  --output-dir outputs \
  --high-threshold 0.43 \
  --review-threshold 0.34

"$PYTHON" -m event_face_finder export \
  --csv outputs/matches.csv \
  --output-dir outputs \
  --mode symlink

"$PYTHON" -m event_face_finder contact-sheets \
  --csv outputs/matches.csv \
  --output-dir outputs/contact_sheets \
  --bucket review
