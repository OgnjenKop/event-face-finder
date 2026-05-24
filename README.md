# Event Face Finder

Local face search for large event photo sets.

The workflow is designed for reliability:

1. Put 15-30 clear reference photos of the target person in `reference_me/`.
2. Build a reference profile from those faces.
3. Scan the event photo folders once.
4. Export high-confidence matches, review candidates, CSVs, and contact sheets.

The original event photos are never modified.

## Requirements

- Python 3.10+
- macOS, Linux, or Windows
- Enough disk space for cached face crops and outputs

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

InsightFace may download model files on first run.

## Folder Layout

```text
reference_me/          Your reference photos
outputs/
  cache.sqlite         Cached detections and embeddings
  reference_profile.npz
  matches.csv
  matches_high/
  matches_review/
  contact_sheets/
```

## Usage

Build the reference profile:

```bash
python -m event_face_finder build-reference \
  --reference-dir reference_me \
  --output outputs/reference_profile.npz
```

Scan the event photos:

```bash
python -m event_face_finder scan \
  --photos-root "/Users/ognjen.koprivica/Pictures" \
  --reference-profile outputs/reference_profile.npz \
  --output-dir outputs \
  --high-threshold 0.43 \
  --review-threshold 0.34
```

Export/copy matching original files into review folders:

```bash
python -m event_face_finder export \
  --csv outputs/matches.csv \
  --output-dir outputs \
  --mode symlink
```

Create contact sheets for fast manual review:

```bash
python -m event_face_finder contact-sheets \
  --csv outputs/matches.csv \
  --output-dir outputs/contact_sheets
```

## Thresholds

Thresholds depend on image quality and reference photos. Start with:

- `high-threshold`: `0.43`
- `review-threshold`: `0.34`

Then inspect `outputs/contact_sheets/review_*.jpg`. If too many false positives appear, raise thresholds slightly. If obvious photos are missing, lower the review threshold.

## Notes

- Use 15-30 reference photos with varied lighting, angles, expressions, and distance.
- Avoid using blurry or tiny reference faces.
- Event photos are processed recursively.
- HEIC files require system/imageio support; JPEG and PNG are the most reliable.
- InsightFace pretrained model licensing should be checked before commercial use.
