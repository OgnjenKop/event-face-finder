import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_face_finder.gui import GuiState, build_run_command, list_reference_people, read_results


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
                    "provider": "cpu",
                    "export_mode": "symlink",
                }
            )

        self.assertEqual(command[:4], [sys.executable, "-m", "event_face_finder", "run-person"])
        self.assertIn("--person-id", command)
        self.assertIn("alex", command)
        self.assertEqual(command.count("--photos-root"), 2)

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


if __name__ == "__main__":
    unittest.main()
