from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import unittest

from event_face_finder.cli import (
    clear_match_outputs,
    clear_generated_outputs,
    count_scan_images,
    create_contact_sheets,
    export_matches,
    open_cache,
    run_person_workflow,
    scan_photos,
)
from event_face_finder.validation import is_safe_person_id


class PersonIdTests(unittest.TestCase):
    def test_accepts_simple_person_ids(self) -> None:
        self.assertTrue(is_safe_person_id("marko"))
        self.assertTrue(is_safe_person_id("ana_2026"))
        self.assertTrue(is_safe_person_id("team.member-1"))

    def test_rejects_path_like_person_ids(self) -> None:
        self.assertFalse(is_safe_person_id(""))
        self.assertFalse(is_safe_person_id("../secret"))
        self.assertFalse(is_safe_person_id("name with spaces"))


class ImageCountingTests(unittest.TestCase):
    def test_counts_unique_supported_images_outside_output_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            photos = root / "photos"
            outputs = root / "outputs"
            photos.mkdir()
            outputs.mkdir()

            image = photos / "image.jpg"
            image.write_bytes(b"not a real image")
            (photos / "notes.txt").write_text("ignore me")
            (outputs / "generated.jpg").write_bytes(b"ignore output")

            self.assertEqual(count_scan_images([photos, photos], outputs), 1)

    def test_scan_uses_provided_image_manifest_without_rewalking_roots(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            photos = root / "photos"
            output = root / "output"
            photos.mkdir()

            with (
                patch("event_face_finder.cli.collect_scan_images") as collect,
                patch("event_face_finder.cli.open_cache") as open_cache_mock,
                patch("event_face_finder.cli.load_face_app") as load_app,
                patch("event_face_finder.cli.get_or_detect_cached", return_value=[]),
                patch("event_face_finder.cli.np.load", return_value={"embeddings": []}),
                redirect_stdout(StringIO()),
            ):
                scan_photos(
                    [photos],
                    root / "reference.npz",
                    output,
                    None,
                    0.43,
                    0.34,
                    640,
                    2200,
                    root / "models",
                    "cpu",
                    0,
                    None,
                    "overwrite",
                    [],
                )

            collect.assert_not_called()
            open_cache_mock.assert_called_once()
            load_app.assert_called_once()

    def test_run_person_reuses_model_and_cache_across_chunks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / "reference"
            workspace = root / "outputs"
            reference.mkdir()
            images = [root / "a.jpg", root / "b.jpg"]
            cache = unittest.mock.Mock()

            with (
                patch("event_face_finder.cli.load_face_app", return_value=object()) as load_app,
                patch("event_face_finder.cli.build_reference") as build_reference,
                patch("event_face_finder.cli.collect_scan_images", return_value=images),
                patch("event_face_finder.cli.open_cache", return_value=cache) as open_cache_mock,
                patch("event_face_finder.cli.load_reference_embeddings", return_value=[]),
                patch("event_face_finder.cli.scan_image_paths", return_value=[]) as scan_paths,
                patch("event_face_finder.cli.write_matches_csv"),
                patch("event_face_finder.cli.export_matches"),
                patch("event_face_finder.cli.create_contact_sheets"),
                redirect_stdout(StringIO()),
            ):
                run_person_workflow(
                    "alex",
                    [root / "photos"],
                    reference,
                    workspace,
                    None,
                    0.43,
                    0.34,
                    640,
                    2200,
                    root / "models",
                    "cpu",
                    1,
                    "symlink",
                )

            load_app.assert_called_once()
            build_reference.assert_called_once()
            open_cache_mock.assert_called_once()
            self.assertEqual(scan_paths.call_count, 2)
            self.assertEqual(cache.commit.call_count, 2)
            cache.close.assert_called_once()


class OutputCleanupTests(unittest.TestCase):
    def test_clears_only_generated_result_directories(self) -> None:
        with TemporaryDirectory() as tmp:
            output = Path(tmp)
            for name in ("matches_high", "matches_review", "contact_sheets"):
                generated = output / name
                generated.mkdir()
                (generated / "old.txt").write_text("stale")
            profile = output / "reference_profile.npz"
            profile.write_text("keep")

            clear_generated_outputs(output)

            self.assertFalse((output / "matches_high").exists())
            self.assertFalse((output / "matches_high").is_symlink())
            self.assertFalse((output / "matches_review").exists())
            self.assertFalse((output / "contact_sheets").exists())
            self.assertTrue(profile.exists())

    def test_clears_generated_symlinks_without_recursing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output"
            external = root / "external"
            output.mkdir()
            external.mkdir()
            (external / "keep.txt").write_text("keep")
            (output / "matches_high").symlink_to(external, target_is_directory=True)

            clear_generated_outputs(output)

            self.assertFalse((output / "matches_high").exists())
            self.assertTrue((external / "keep.txt").exists())

    def test_export_clears_stale_match_directories(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jpg"
            output = root / "output"
            stale = output / "matches_high" / "stale.jpg"
            source.write_bytes(b"image")
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"stale")
            csv_path = root / "matches.csv"
            csv_path.write_text(
                "image_path,face_index,score,bucket,bbox,det_score\n"
                f"{source},0,0.5,review,\"[1, 2, 3, 4]\",0.9\n"
            )

            with redirect_stdout(StringIO()):
                export_matches(csv_path, output, "symlink")

            self.assertFalse(stale.exists())
            self.assertTrue((output / "matches_review" / "source.jpg").is_symlink())

    def test_clear_match_outputs_does_not_remove_contact_sheets(self) -> None:
        with TemporaryDirectory() as tmp:
            output = Path(tmp)
            for name in ("matches_high", "matches_review", "contact_sheets"):
                generated = output / name
                generated.mkdir()
                (generated / "old.txt").write_text("old")

            clear_match_outputs(output)

            self.assertFalse((output / "matches_high").exists())
            self.assertFalse((output / "matches_review").exists())
            self.assertTrue((output / "contact_sheets" / "old.txt").exists())

    def test_cache_schema_uses_path_as_single_cache_record(self) -> None:
        with TemporaryDirectory() as tmp:
            cache = open_cache(Path(tmp) / "cache.sqlite")
            indexes = {
                row[1]
                for row in cache.execute("pragma index_list(detections)").fetchall()
            }

            self.assertNotIn("detections_cache_key", indexes)

    def test_contact_sheet_command_removes_stale_pages_for_bucket(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "matches.csv"
            sheets = root / "sheets"
            sheets.mkdir()
            stale = sheets / "review_001.jpg"
            stale.write_bytes(b"stale")
            (sheets / "high_001.jpg").write_bytes(b"keep")
            csv_path.write_text("image_path,face_index,score,bucket,bbox,det_score\n")

            with redirect_stdout(StringIO()):
                create_contact_sheets(csv_path, sheets, "review", 180, 5)

            self.assertFalse(stale.exists())
            self.assertTrue((sheets / "high_001.jpg").exists())

    def test_contact_sheet_rejects_invalid_dimensions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "matches.csv"
            sheets = root / "sheets"
            csv_path.write_text("image_path,face_index,score,bucket,bbox,det_score\n")

            with self.assertRaises(ValueError):
                create_contact_sheets(csv_path, sheets, "review", 180, 0)
            with self.assertRaises(ValueError):
                create_contact_sheets(csv_path, sheets, "review", 0, 5)


if __name__ == "__main__":
    unittest.main()
