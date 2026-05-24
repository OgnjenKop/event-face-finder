#!/usr/bin/env bash
set -euo pipefail

python -m event_face_finder build-reference \
  --reference-dir reference_me \
  --output outputs/reference_profile.npz

python -m event_face_finder scan \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 2" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 3" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 4" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 5" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 6" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 7" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 8" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 9" \
  --photos-root "/Users/ognjen.koprivica/Pictures/FOTOGRAFIJE - CAHSE THE HUNT 10" \
  --reference-profile outputs/reference_profile.npz \
  --output-dir outputs \
  --high-threshold 0.43 \
  --review-threshold 0.34

python -m event_face_finder export \
  --csv outputs/matches.csv \
  --output-dir outputs \
  --mode symlink

python -m event_face_finder contact-sheets \
  --csv outputs/matches.csv \
  --output-dir outputs/contact_sheets \
  --bucket review
