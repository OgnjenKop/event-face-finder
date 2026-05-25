from __future__ import annotations

import csv
import json
import mimetypes
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from event_face_finder.validation import is_safe_person_id


STATIC_DIR = Path(__file__).with_name("static")
DEFAULT_WORKSPACE = Path("outputs")


@dataclass
class GuiJob:
    command: list[str] = field(default_factory=list)
    status: str = "idle"
    returncode: int | None = None
    lines: list[str] = field(default_factory=list)
    process: subprocess.Popen[str] | None = None


class GuiState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.job = GuiJob()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.job.status,
                "returncode": self.job.returncode,
                "command": self.job.command,
                "lines": self.job.lines[-500:],
            }

    def start(self, command: list[str]) -> bool:
        with self.lock:
            if self.job.status in {"running", "stopping"}:
                return False
            self.job = GuiJob(command=command, status="running")

        thread = threading.Thread(target=self._run, args=(command,), daemon=True)
        thread.start()
        return True

    def stop(self) -> bool:
        with self.lock:
            process = self.job.process
            if self.job.status != "running" or process is None:
                return False
            self.job.status = "stopping"
        process.terminate()
        thread = threading.Thread(target=self._kill_if_still_stopping, args=(process,), daemon=True)
        thread.start()
        return True

    def append_line(self, line: str) -> None:
        with self.lock:
            self.job.lines.append(line.rstrip())

    def _run(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            with self.lock:
                self.job.process = process

            assert process.stdout is not None
            for line in process.stdout:
                self.append_line(line)

            returncode = process.wait()
            with self.lock:
                self.job.returncode = returncode
                self.job.status = "completed" if returncode == 0 else "failed"
                self.job.process = None
        except Exception as exc:  # pragma: no cover - defensive server boundary.
            with self.lock:
                self.job.status = "failed"
                self.job.returncode = -1
                self.job.process = None
                self.job.lines.append(f"GUI server error: {exc}")

    def _kill_if_still_stopping(self, process: subprocess.Popen[str]) -> None:
        try:
            process.wait(timeout=8)
            return
        except subprocess.TimeoutExpired:
            pass

        with self.lock:
            should_kill = self.job.process is process and self.job.status == "stopping"
        if should_kill:
            process.kill()
            self.append_line("Scan did not stop after 8 seconds; force-stopped it.")


def run_gui(host: str, port: int, should_open: bool) -> None:
    state = GuiState()
    handler = make_handler(state)
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}"
    print(f"Event Face Finder GUI running at {url}")
    if should_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        print("Stopping GUI server.")
    finally:
        server.server_close()


def make_handler(state: GuiState):
    class EventFaceFinderHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self.serve_static(STATIC_DIR / "index.html")
            elif parsed.path.startswith("/static/"):
                relative = parsed.path.removeprefix("/static/")
                self.serve_static(STATIC_DIR / unquote(relative))
            elif parsed.path == "/api/status":
                self.send_json(state.snapshot())
            elif parsed.path == "/api/results":
                query = parse_qs(parsed.query)
                person_id = query.get("person_id", [""])[0]
                workspace = Path(query.get("workspace", [str(DEFAULT_WORKSPACE)])[0])
                self.send_json(read_results(person_id, workspace))
            elif parsed.path == "/api/reference-people":
                query = parse_qs(parsed.query)
                reference_root = Path(query.get("reference_root", ["reference_people"])[0])
                self.send_json({"people": list_reference_people(reference_root)})
            elif parsed.path == "/api/contact-sheet":
                query = parse_qs(parsed.query)
                person_id = query.get("person_id", [""])[0]
                workspace = Path(query.get("workspace", [str(DEFAULT_WORKSPACE)])[0])
                filename = query.get("filename", [""])[0]
                self.serve_contact_sheet(person_id, workspace, filename)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/start":
                payload = self.read_json()
                try:
                    command = build_run_command(payload)
                except ValueError as exc:
                    self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                    return

                if not state.start(command):
                    self.send_json(
                        {"ok": False, "error": "A scan is already running."},
                        HTTPStatus.CONFLICT,
                    )
                    return
                self.send_json({"ok": True, "command": command})
            elif parsed.path == "/api/stop":
                self.send_json({"ok": state.stop()})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            if not body:
                return {}
            return json.loads(body)

        def send_json(
            self,
            payload: dict[str, Any],
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def serve_static(self, path: Path) -> None:
            try:
                resolved = path.resolve()
                resolved.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not resolved.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            content_type, _ = mimetypes.guess_type(str(resolved))
            body = resolved.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", content_type or "application/octet-stream")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def serve_contact_sheet(self, person_id: str, workspace: Path, filename: str) -> None:
            if not is_safe_person_id(person_id) or Path(filename).name != filename:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            if Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return

            contact_dir = (workspace / "people" / person_id / "contact_sheets").resolve()
            resolved = (contact_dir / filename).resolve()
            try:
                resolved.relative_to(contact_dir)
            except ValueError:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not resolved.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type, _ = mimetypes.guess_type(str(resolved))
            body = resolved.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", content_type or "application/octet-stream")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return EventFaceFinderHandler


def build_run_command(payload: dict[str, Any]) -> list[str]:
    person_id = str(payload.get("person_id", "")).strip()
    reference_dir = Path(
        str(payload.get("reference_dir", "")).strip() or f"reference_people/{person_id}"
    )
    photos_roots = [
        Path(value.strip())
        for value in str(payload.get("photos_roots", "")).splitlines()
        if value.strip()
    ]
    if not person_id:
        raise ValueError("Person ID is required.")
    if not is_safe_person_id(person_id):
        raise ValueError(
            "Person ID can only contain letters, numbers, dots, underscores, and hyphens."
        )
    if not photos_roots:
        raise ValueError("At least one photo folder is required.")
    if not reference_dir.is_dir():
        raise ValueError(f"Reference folder not found: {reference_dir}")
    missing_roots = [str(path) for path in photos_roots if not path.is_dir()]
    if missing_roots:
        raise ValueError(f"Photo folder not found: {missing_roots[0]}")

    high_threshold = parse_float(payload.get("high_threshold"), 0.43, "High threshold")
    review_threshold = parse_float(payload.get("review_threshold"), 0.34, "Review threshold")
    max_image_size = parse_int(payload.get("max_image_size"), 2200, "Max image size")
    chunk_size = parse_int(payload.get("chunk_size"), 500, "Chunk size")
    min_reference_faces = parse_int(
        payload.get("min_reference_faces"),
        5,
        "Minimum reference faces",
    )
    if not 0 <= review_threshold <= high_threshold <= 1:
        raise ValueError("Thresholds must satisfy 0 <= review <= high <= 1.")
    if max_image_size < 0:
        raise ValueError("Max image size must be zero or greater.")
    if chunk_size < 1:
        raise ValueError("Chunk size must be greater than zero.")
    if min_reference_faces < 1:
        raise ValueError("Minimum reference faces must be greater than zero.")

    provider = str(payload.get("provider") or "cpu")
    export_mode = str(payload.get("export_mode") or "symlink")
    if provider not in {"cpu", "coreml"}:
        raise ValueError("Provider must be cpu or coreml.")
    if export_mode not in {"copy", "symlink"}:
        raise ValueError("Export mode must be copy or symlink.")

    command = [
        sys.executable,
        "-m",
        "event_face_finder",
        "run-person",
        "--person-id",
        person_id,
        "--workspace",
        str(payload.get("workspace") or DEFAULT_WORKSPACE),
        "--high-threshold",
        str(high_threshold),
        "--review-threshold",
        str(review_threshold),
        "--max-image-size",
        str(max_image_size),
        "--chunk-size",
        str(chunk_size),
        "--min-reference-faces",
        str(min_reference_faces),
        "--provider",
        provider,
        "--export-mode",
        export_mode,
    ]

    command.extend(["--reference-dir", str(reference_dir)])

    cache_path = str(payload.get("cache_path", "")).strip()
    if cache_path:
        command.extend(["--cache-path", cache_path])

    for photos_root in photos_roots:
        command.extend(["--photos-root", str(photos_root)])

    return command


def parse_float(value: Any, default: float, name: str) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc


def parse_int(value: Any, default: int, name: str) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def list_reference_people(reference_root: Path) -> list[str]:
    if not reference_root.is_dir():
        return []
    return sorted(path.name for path in reference_root.iterdir() if path.is_dir())


def read_results(person_id: str, workspace: Path) -> dict[str, Any]:
    if not person_id or not is_safe_person_id(person_id):
        return {"exists": False, "rows": [], "summary": empty_summary()}
    person_dir = workspace / "people" / person_id
    csv_path = person_dir / "matches.csv"
    if not csv_path.exists():
        return {"exists": False, "rows": [], "summary": empty_summary()}

    rows = []
    with csv_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)

    summary = empty_summary()
    summary["total"] = len(rows)
    summary["high"] = sum(1 for row in rows if row.get("bucket") == "high")
    summary["review"] = sum(1 for row in rows if row.get("bucket") == "review")
    summary["csv_path"] = str(csv_path)
    summary["high_dir"] = str(person_dir / "matches_high")
    summary["review_dir"] = str(person_dir / "matches_review")
    summary["contact_sheets_dir"] = str(person_dir / "contact_sheets")
    summary["contact_sheets"] = [
        path.name
        for path in sorted((person_dir / "contact_sheets").glob("*.jpg"))
    ]
    return {"exists": True, "rows": rows[:200], "summary": summary}


def empty_summary() -> dict[str, Any]:
    return {
        "total": 0,
        "high": 0,
        "review": 0,
        "csv_path": "",
        "high_dir": "",
        "review_dir": "",
        "contact_sheets_dir": "",
        "contact_sheets": [],
    }
