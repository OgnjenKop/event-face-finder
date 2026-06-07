# Event Face Finder

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

Local face search for large event photo collections.

Event Face Finder helps photographers, event organizers, and participants find photos
of a specific person across thousands of event images. It runs on your machine, keeps
each person's results separate, and reuses a shared face-detection cache so follow-up
searches are much faster.

> Important: this project processes biometric data. Read [PRIVACY.md](PRIVACY.md)
> before using it on real people or public event photos.

## Features

- Local-first workflow; no hosted service or cloud upload.
- Web GUI for common scans and result review.
- CLI for repeatable batch workflows.
- Multiple photo roots per scan.
- Shared local cache for detected face embeddings.
- Separate output folders for each searched person.
- High-confidence and manual-review match buckets.
- Contact sheets for quick visual verification.

## Status

This project is early but usable. The current focus is reliable local operation,
privacy-conscious defaults, and clear review workflows. See [ROADMAP.md](ROADMAP.md)
for planned work.

## Requirements

- Python 3.10 or newer
- macOS, Linux, or Windows
- Disk space for local cache and generated outputs
- Reference photos for each person you want to search

InsightFace may download model files on first use. Model weights and third-party
dependencies may have their own licenses and usage restrictions; review them before
commercial, public-sector, or regulated use.

## Installation From Source

Detailed platform notes are in [docs/installation.md](docs/installation.md).

```bash
git clone https://github.com/OgnjenKop/event-face-finder.git
cd event-face-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

*(Optional)* You can install the package in editable mode to make the `event-face-finder` CLI command available directly in your terminal:

```bash
pip install -e .
```

On Windows PowerShell, activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Start The GUI

See [docs/workflow.md](docs/workflow.md) for the full user workflow.

```bash
python -m event_face_finder gui
```

Open `http://127.0.0.1:8765` if your browser does not open automatically.

From a source checkout, this shortcut does the same thing:

```bash
./scripts/start_gui.sh
```

The GUI runs locally and writes results into `outputs/`.

## Desktop App

An experimental Tauri desktop wrapper is available for users who prefer a native
window and folder pickers while keeping the same local Python engine.

```bash
npm install
npm run desktop:dev
```

See [docs/desktop.md](docs/desktop.md) for setup, Rust requirements, and build
notes.

## CLI Quick Start

Create a reference folder for a person:

```bash
mkdir -p reference_people/alex
```

Add clear reference photos of that person into `reference_people/alex/`. Use at least
5 usable face photos; 8-15 is better. Mix front-facing, side-angle, indoor, outdoor,
and event-lighting photos when possible.

Run a search:

```bash
python -m event_face_finder run-person \
  --person-id alex \
  --photos-root "/path/to/event/photos"
```

For multiple photo folders, repeat `--photos-root`:

```bash
python -m event_face_finder run-person \
  --person-id alex \
  --photos-root "/path/to/event/day-1" \
  --photos-root "/path/to/event/day-2"
```

Results are written to:

```text
outputs/people/alex/matches_high/
outputs/people/alex/matches_review/
outputs/people/alex/contact_sheets/
outputs/people/alex/matches.csv
```

For another person, add a new reference folder and use a new `--person-id`. If the
same photo folders and image-size settings are used, the second run reuses
`outputs/cache.sqlite` and should be much faster.

## Output Files

```text
reference_people/
  alex/                 Reference photos for one person
outputs/
  cache.sqlite          Shared local detections and embeddings cache
  people/
    alex/
      reference_profile.npz
      matches.csv
      matches_high/
      matches_review/
      contact_sheets/
```

The files under `outputs/` can contain biometric data and local file paths. They are
ignored by Git by default and should not be published without consent.

## Thresholds

Defaults are tuned for event photos with many faces:

- `--high-threshold 0.43`
- `--review-threshold 0.34`

Raise thresholds if there are too many false positives. Lower the review threshold if
obvious matches are missing, then inspect contact sheets carefully.

See [docs/troubleshooting.md](docs/troubleshooting.md) for common scan and install
issues.

## Advanced Commands

Build a reference profile manually:

```bash
python -m event_face_finder build-reference \
  --reference-dir reference_people/alex \
  --output outputs/people/alex/reference_profile.npz
```

Scan manually:

```bash
python -m event_face_finder scan \
  --photos-root "/path/to/event/photos" \
  --reference-profile outputs/people/alex/reference_profile.npz \
  --output-dir outputs/people/alex \
  --cache-path outputs/cache.sqlite \
  --high-threshold 0.43 \
  --review-threshold 0.34
```

Export matching originals as symlinks:

```bash
python -m event_face_finder export \
  --csv outputs/people/alex/matches.csv \
  --output-dir outputs/people/alex \
  --mode symlink
```

Create contact sheets:

```bash
python -m event_face_finder contact-sheets \
  --csv outputs/people/alex/matches.csv \
  --output-dir outputs/people/alex/contact_sheets \
  --bucket review
```

## Accuracy

Face recognition is probabilistic. Matches can be wrong, and real appearances can be
missed. Treat `matches_high` as likely matches, not proof. Always review results before
sharing, publishing, or taking action based on them.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for local development guidance.

Install development dependencies:

```bash
pip install -e .[dev]
```

Run linter checks:

```bash
ruff check .
```

Run tests:

```bash
python -m unittest discover
```

## Project Policies

- [Privacy](PRIVACY.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)

## Notes

- JPEG and PNG are the most reliable input formats.
- HEIC files require system/image library support.
- Person IDs may contain letters, numbers, dots, underscores, and hyphens.
- The original event photos are never modified.
