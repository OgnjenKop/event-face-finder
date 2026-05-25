# Roadmap

This roadmap is directional, not a promise. The project prioritizes local operation,
privacy, and reviewability over hosted workflows.

## 0.1: Reliable Local Workflow

- Generic `run-person` workflow for any event folder.
- Local GUI for common scans.
- Shared cache for fast repeated searches across multiple people.
- High and review match buckets.
- Contact sheets for manual verification.
- Privacy, security, contribution, and conduct documentation.

## 0.2: Review Experience

- Richer GUI run history.
- Direct accept/reject review workflow.
- Export accepted matches separately.
- Threshold guidance based on observed score distribution.
- HTML review report for sharing local results without rerunning scans.

## 0.3: Scale And Resume

- Resume interrupted runs without deleting partial results.
- Store scan manifests so folder changes are easier to reason about.
- Improve cache migrations and add cache health checks.
- Add benchmark documentation for CPU, CoreML, CUDA, and common image sizes.

## 0.4: Packaging

- Publish installable wheels.
- Add a `pipx` install path.
- Provide Docker documentation for Linux users.
- Add GitHub Actions for tests and linting.

## Future Ideas

- Optional native desktop packaging.
- Duplicate image grouping.
- Person galleries with manual verification status.
- Pluggable embedding backends.
- Better HEIC and RAW-adjacent workflows.
