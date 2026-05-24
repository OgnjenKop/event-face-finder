#!/usr/bin/env bash
set -euo pipefail

python -m event_face_finder build-reference \
  --reference-dir reference_me \
  --output outputs/reference_profile.npz

python -m event_face_finder scan \
  --photos-root "/Users/ognjen.koprivica/Pictures" \
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
