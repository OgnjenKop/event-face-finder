#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 REFERENCE_DIR TOTAL_IMAGES CHUNK_SIZE PHOTOS_ROOT [PHOTOS_ROOT ...]"
  echo
  echo "Example:"
  echo "  $0 reference_people/alex 14000 500 /path/to/event/photos"
  exit 2
fi

PYTHON="${PYTHON:-python}"
REFERENCE_DIR="$1"
TOTAL="$2"
CHUNK_SIZE="$3"
shift 3

photos_root_args=()
for photos_root in "$@"; do
  photos_root_args+=(--photos-root "$photos_root")
done

mkdir -p outputs

"$PYTHON" -m event_face_finder build-reference \
  --reference-dir "$REFERENCE_DIR" \
  --output outputs/reference_profile.npz

rm -f outputs/matches.csv

offset=0
while [ "$offset" -lt "$TOTAL" ]; do
  echo "Scanning chunk starting at image offset $offset"
  "$PYTHON" -m event_face_finder scan \
    "${photos_root_args[@]}" \
    --reference-profile outputs/reference_profile.npz \
    --output-dir outputs \
    --cache-path outputs/cache.sqlite \
    --high-threshold 0.43 \
    --review-threshold 0.34 \
    --max-image-size 2200 \
    --offset "$offset" \
    --limit "$CHUNK_SIZE" \
    --csv-mode append
  offset=$((offset + CHUNK_SIZE))
done

"$PYTHON" -m event_face_finder export \
  --csv outputs/matches.csv \
  --output-dir outputs \
  --mode symlink

"$PYTHON" -m event_face_finder contact-sheets \
  --csv outputs/matches.csv \
  --output-dir outputs/contact_sheets \
  --bucket review
