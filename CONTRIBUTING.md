# Contributing

Thanks for considering a contribution. Event Face Finder is a local-first tool for a
sensitive domain, so privacy and reliability matter as much as features.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run tests:

```bash
python -m unittest discover
```

Run the CLI locally:

```bash
python -m event_face_finder --help
python -m event_face_finder gui
```

## Before Opening A Pull Request

- Run the test suite.
- Keep changes scoped and explain the user-facing behavior change.
- Add or update tests for behavior changes.
- Update documentation when commands, outputs, thresholds, or privacy behavior change.
- Do not commit generated outputs, reference photos, event photos, embeddings, caches,
  or match CSVs.

## Privacy Rules

Do not include real people's photos, generated face crops, embeddings, cache databases,
or match outputs in issues or pull requests. Use synthetic fixtures or tiny placeholder
files for tests.

If a bug only reproduces with real data, describe the shape of the data instead:

- image count
- approximate resolution
- file format
- operating system
- command used
- sanitized logs

## Issue Reports

Useful bug reports include:

- Operating system and Python version.
- Install method.
- Command or GUI action used.
- Expected behavior.
- Actual behavior.
- Sanitized logs.

For security or privacy-sensitive issues, follow [SECURITY.md](SECURITY.md) instead of
opening a public issue.

## Pull Request Style

- Prefer small, reviewable changes.
- Preserve CLI compatibility unless there is a strong reason to change it.
- Keep GUI behavior local-first and avoid network services.
- Avoid adding heavy dependencies without explaining why they are necessary.
- Keep comments focused on non-obvious implementation details.

## High-Value Contributions

- Safer resume behavior for interrupted scans.
- Better HTML or GUI review workflows.
- Tests for cache behavior, CSV export, and GUI edge cases.
- Better install documentation for macOS, Linux, and Windows.
- Benchmark documentation for CPU, CoreML, CUDA, and image-size settings.
- Improved handling for very large photo libraries.
