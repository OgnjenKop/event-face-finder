import sys
import threading
import unittest
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from event_face_finder.gui import (
    GuiState,
    _parse_progress,
    build_run_command,
    list_reference_people,
    parse_workspace,
    read_results,
)


class GuiCommandTests(unittest.TestCase):
    def test_builds_run_person_command(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference_dir = root / "reference"
            day1 = root / "day1"
            day2 = root / "day2"
            reference_dir.mkdir()
            day1.mkdir()
            day2.mkdir()

            command = build_run_command(
                {
                    "person_id": "alex",
                    "reference_dir": str(reference_dir),
                    "photos_roots": f"{day1}\n{day2}",
                    "workspace": "outputs",
                    "high_threshold": "0.43",
                    "review_threshold": "0.34",
                    "max_image_size": "2200",
                    "chunk_size": "500",
                    "min_reference_faces": "4",
                    "provider": "cpu",
                    "export_mode": "symlink",
                }
            )

        self.assertEqual(command[:4], [sys.executable, "-m", "event_face_finder", "run-person"])
        self.assertIn("--person-id", command)
        self.assertIn("alex", command)
        self.assertEqual(command.count("--photos-root"), 2)
        self.assertIn("--min-reference-faces", command)
        self.assertIn("4", command)

    def test_requires_person_and_photo_roots(self) -> None:
        with self.assertRaises(ValueError):
            build_run_command({"person_id": "", "photos_roots": "/photos"})
        with self.assertRaises(ValueError):
            build_run_command({"person_id": "alex", "photos_roots": ""})

    def test_rejects_unsafe_person_id_before_subprocess(self) -> None:
        with self.assertRaises(ValueError):
            build_run_command({"person_id": "../alex", "photos_roots": "/photos"})

    def test_rejects_unknown_provider_and_export_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference_dir = root / "reference"
            photos = root / "photos"
            reference_dir.mkdir()
            photos.mkdir()

            with self.assertRaises(ValueError):
                build_run_command(
                    {
                        "person_id": "alex",
                        "reference_dir": str(reference_dir),
                        "photos_roots": str(photos),
                        "provider": "gpu",
                    }
                )
            with self.assertRaises(ValueError):
                build_run_command(
                    {
                        "person_id": "alex",
                        "reference_dir": str(reference_dir),
                        "photos_roots": str(photos),
                        "export_mode": "move",
                    }
                )

    def test_rejects_missing_reference_and_photo_folders(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            photos = root / "photos"
            photos.mkdir()
            with self.assertRaises(ValueError):
                build_run_command(
                    {
                        "person_id": "alex",
                        "reference_dir": str(root / "missing-reference"),
                        "photos_roots": str(photos),
                    }
                )

            reference_dir = root / "reference"
            reference_dir.mkdir()
            with self.assertRaises(ValueError):
                build_run_command(
                    {
                        "person_id": "alex",
                        "reference_dir": str(reference_dir),
                        "photos_roots": str(root / "missing-photos"),
                    }
                )

    def test_rejects_invalid_numeric_settings(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference_dir = root / "reference"
            photos = root / "photos"
            reference_dir.mkdir()
            photos.mkdir()
            base = {
                "person_id": "alex",
                "reference_dir": str(reference_dir),
                "photos_roots": str(photos),
            }

            with self.assertRaises(ValueError):
                build_run_command({**base, "high_threshold": "abc"})
            with self.assertRaises(ValueError):
                build_run_command({**base, "high_threshold": "0.3", "review_threshold": "0.4"})
            with self.assertRaises(ValueError):
                build_run_command({**base, "chunk_size": "0"})
            with self.assertRaises(ValueError):
                build_run_command({**base, "max_image_size": "-1"})
            with self.assertRaises(ValueError):
                build_run_command({**base, "min_reference_faces": "0"})


class GuiReferencePeopleTests(unittest.TestCase):
    def test_missing_reference_root_returns_empty_list(self) -> None:
        self.assertEqual(list_reference_people(Path("/missing-root")), [])


class GuiResultsTests(unittest.TestCase):
    def test_contact_sheets_are_returned_as_filenames_only(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            person_dir = workspace / "people" / "alex"
            sheets = person_dir / "contact_sheets"
            sheets.mkdir(parents=True)
            (sheets / "review_001.jpg").write_bytes(b"fake")
            (person_dir / "matches.csv").write_text(
                "image_path,face_index,score,bucket,bbox,det_score\n"
                "/photos/a.jpg,0,0.5,high,\"[1, 2, 3, 4]\",0.9\n"
            )

            results = read_results("alex", workspace)

        self.assertEqual(results["summary"]["contact_sheets"], ["review_001.jpg"])
        self.assertEqual(results["summary"]["high"], 1)
        self.assertEqual(results["summary"]["review"], 0)

    def test_unsafe_person_id_does_not_read_results(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            outside = workspace / "secret"
            outside.mkdir()
            (outside / "matches.csv").write_text(
                "image_path,face_index,score,bucket,bbox,det_score\n"
                "/photos/a.jpg,0,0.5,high,\"[1, 2, 3, 4]\",0.9\n"
            )

            results = read_results("../secret", workspace / "people")

        self.assertFalse(results["exists"])
        self.assertEqual(results["summary"]["total"], 0)


class GuiStateTests(unittest.TestCase):
    def test_does_not_start_second_running_job(self) -> None:
        state = GuiState()
        state.job.status = "running"

        self.assertFalse(state.start([sys.executable, "--version"]))

    def test_does_not_start_while_stopping(self) -> None:
        state = GuiState()
        state.job.status = "stopping"

        self.assertFalse(state.start([sys.executable, "--version"]))

    def test_force_kills_process_that_does_not_stop(self) -> None:
        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("scan", 8)
        state = GuiState()
        state.job.status = "stopping"
        state.job.process = process

        state._kill_if_still_stopping(process)

        process.kill.assert_called_once()
        self.assertIn("force-stopped", state.job.lines[-1])

    def test_progress_is_tracked_from_cli_lines(self) -> None:
        state = GuiState()
        state.append_line("PROGRESS total=100")
        state.append_line("PROGRESS done=10 total=100 matches=3")
        state.append_line("PROGRESS done=50 total=100 matches=12")
        state.append_line("Skipping unreadable image: a.jpg (boom)")
        state.append_line("PROGRESS done=100 total=100 matches=20")

        snapshot = state.snapshot()
        self.assertEqual(snapshot["progress"]["total"], 100)
        self.assertEqual(snapshot["progress"]["done"], 100)

    def test_non_progress_lines_do_not_change_progress(self) -> None:
        state = GuiState()
        state.append_line("Hello world")
        state.append_line("Scanning alex chunk starting at image offset 0")
        snapshot = state.snapshot()
        self.assertEqual(snapshot["progress"], {"total": 0, "done": 0})


class WorkspaceValidationTests(unittest.TestCase):
    def test_absolute_paths_without_traversal_are_accepted(self) -> None:
        path = parse_workspace("/Users/alex/outputs")
        self.assertEqual(path, Path("/Users/alex/outputs"))

    def test_relative_paths_are_rejected(self) -> None:
        self.assertIsNone(parse_workspace(""))
        self.assertIsNone(parse_workspace("foo/bar"))
        self.assertIsNone(parse_workspace("~/outputs"))

    def test_default_workspace_is_accepted(self) -> None:
        from event_face_finder.gui import DEFAULT_WORKSPACE

        self.assertEqual(parse_workspace(str(DEFAULT_WORKSPACE)), DEFAULT_WORKSPACE)

    def test_parent_traversal_is_rejected(self) -> None:
        self.assertIsNone(parse_workspace("/Users/alex/../etc"))

    def test_workspace_constraint_holds_for_results(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            secret = workspace / "secret"
            secret.mkdir()
            (secret / "matches.csv").write_text("image_path\n/a.jpg\n")
            results = read_results("alex", secret.parent)  # parent is real workspace
            self.assertFalse(results["exists"])


class GuiContactSheetTests(unittest.TestCase):
    def test_contact_sheet_symlink_is_rejected(self) -> None:
        """A symlink inside contact_sheets/ must not be served."""
        import http.client
        from contextlib import closing
        from http.server import ThreadingHTTPServer

        from event_face_finder.gui import make_handler

        with TemporaryDirectory() as tmp:
            ws = Path(tmp)
            sheets = ws / "people" / "alex" / "contact_sheets"
            sheets.mkdir(parents=True)
            target = ws / "secret.txt"
            target.write_text("private content")
            (sheets / "leak.jpg").symlink_to(target)

            state = Mock()
            handler_cls = make_handler(state)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with closing(http.client.HTTPConnection(host, port, timeout=2)) as conn:
                    conn.request(
                        "GET",
                        f"/api/contact-sheet?person_id=alex&workspace={ws}&filename=leak.jpg",
                    )
                    response = conn.getresponse()
                    self.assertEqual(response.status, 403)
            finally:
                server.shutdown()
                server.server_close()

    def test_contact_sheet_legitimate_file_is_served(self) -> None:
        import http.client
        from contextlib import closing
        from http.server import ThreadingHTTPServer

        from event_face_finder.gui import make_handler

        with TemporaryDirectory() as tmp:
            ws = Path(tmp)
            sheets = ws / "people" / "alex" / "contact_sheets"
            sheets.mkdir(parents=True)
            (sheets / "real.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

            state = Mock()
            handler_cls = make_handler(state)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
            host, port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with closing(http.client.HTTPConnection(host, port, timeout=2)) as conn:
                    conn.request(
                        "GET",
                        f"/api/contact-sheet?person_id=alex&workspace={ws}&filename=real.jpg",
                    )
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    body = response.read()
                    self.assertEqual(body, b"\xff\xd8\xff\xe0fake-jpeg")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
