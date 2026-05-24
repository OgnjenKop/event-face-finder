#!/usr/bin/env bash
set -euo pipefail

PHOTOS_ROOTS=(
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 2"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 3"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 4"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 5"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 6"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 7"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 8"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 9"
  "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 10"
)

photos_root_args=()
for photos_root in "${PHOTOS_ROOTS[@]}"; do
  photos_root_args+=(--photos-root "$photos_root")
done

python -m event_face_finder build-reference \
  --reference-dir reference_me \
  --output outputs/reference_profile.npz

rm -f outputs/matches.csv

offset=0
chunk_size=500
total=13439

while [ "$offset" -lt "$total" ]; do
  echo "Scanning chunk starting at image offset $offset"
  python -m event_face_finder scan \
    "${photos_root_args[@]}" \
    --reference-profile outputs/reference_profile.npz \
    --output-dir outputs \
    --high-threshold 0.43 \
    --review-threshold 0.34 \
    --max-image-size 2200 \
    --offset "$offset" \
    --limit "$chunk_size" \
    --csv-mode append
  offset=$((offset + chunk_size))
done

python -m event_face_finder export \
  --csv outputs/matches.csv \
  --output-dir outputs \
  --mode symlink

python -m event_face_finder contact-sheets \
  --csv outputs/matches.csv \
  --output-dir outputs/contact_sheets \
  --bucket review
