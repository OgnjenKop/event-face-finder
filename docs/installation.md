# Installation

## From Source

```bash
git clone https://github.com/OgnjenKop/event-face-finder.git
cd event-face-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

## Verify The Install

```bash
python -m event_face_finder --help
python -m event_face_finder gui --help
python -m unittest discover
```

## First Model Download

InsightFace may download model files the first time you run reference building or a
scan. Keep the machine online for the first run.

## Platform Notes

- macOS: CPU is the safest default. CoreML can be tested with `--provider coreml`, but
  it is not always faster.
- Linux: CPU works by default. CUDA support depends on the ONNX Runtime package you
  install and is not configured by this project yet.
- Windows: use PowerShell activation shown above. Symlink export may require developer
  mode or administrator privileges; use `--export-mode copy` if symlinks fail.
