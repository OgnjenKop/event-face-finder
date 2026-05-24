from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from tqdm import tqdm

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"}


@dataclass(frozen=True)
class FaceMatch:
    image_path: Path
    face_index: int
    score: float
    bucket: str
    bbox: tuple[int, int, int, int]
    det_score: float


def main() -> None:
    parser = argparse.ArgumentParser(description="Find event photos containing a target face.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build-reference")
    build_parser.add_argument("--reference-dir", required=True, type=Path)
    build_parser.add_argument("--output", required=True, type=Path)
    build_parser.add_argument("--det-size", default=640, type=int)
    build_parser.add_argument("--model-root", default=Path("models"), type=Path)
    build_parser.add_argument("--provider", choices=["coreml", "cpu"], default="cpu")

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--photos-root", required=True, type=Path, action="append")
    scan_parser.add_argument("--reference-profile", required=True, type=Path)
    scan_parser.add_argument("--output-dir", required=True, type=Path)
    scan_parser.add_argument("--high-threshold", default=0.43, type=float)
    scan_parser.add_argument("--review-threshold", default=0.34, type=float)
    scan_parser.add_argument("--det-size", default=640, type=int)
    scan_parser.add_argument("--model-root", default=Path("models"), type=Path)
    scan_parser.add_argument("--provider", choices=["coreml", "cpu"], default="cpu")
    scan_parser.add_argument("--limit", default=None, type=int)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--csv", required=True, type=Path)
    export_parser.add_argument("--output-dir", required=True, type=Path)
    export_parser.add_argument("--mode", choices=["copy", "symlink"], default="symlink")

    sheet_parser = subparsers.add_parser("contact-sheets")
    sheet_parser.add_argument("--csv", required=True, type=Path)
    sheet_parser.add_argument("--output-dir", required=True, type=Path)
    sheet_parser.add_argument("--bucket", choices=["high", "review"], default="review")
    sheet_parser.add_argument("--thumb-size", default=180, type=int)
    sheet_parser.add_argument("--columns", default=5, type=int)

    args = parser.parse_args()

    if args.command == "build-reference":
        build_reference(args.reference_dir, args.output, args.det_size, args.model_root, args.provider)
    elif args.command == "scan":
        scan_photos(
            args.photos_root,
            args.reference_profile,
            args.output_dir,
            args.high_threshold,
            args.review_threshold,
            args.det_size,
            args.model_root,
            args.provider,
            args.limit,
        )
    elif args.command == "export":
        export_matches(args.csv, args.output_dir, args.mode)
    elif args.command == "contact-sheets":
        create_contact_sheets(args.csv, args.output_dir, args.bucket, args.thumb_size, args.columns)


def build_reference(
    reference_dir: Path,
    output: Path,
    det_size: int,
    model_root: Path,
    provider: str,
) -> None:
    app = load_face_app(det_size, model_root, provider)
    embeddings: list[np.ndarray] = []
    rows: list[dict[str, object]] = []

    images = list(iter_images(reference_dir))
    if not images:
        raise SystemExit(f"No reference images found in {reference_dir}")

    for image_path in tqdm(images, desc="Reference images"):
        faces = detect_faces(app, image_path)
        if not faces:
            rows.append({"path": str(image_path), "faces": 0, "used": False})
            continue

        face = max(faces, key=lambda item: face_area(item.bbox))
        embeddings.append(normalize_embedding(face.embedding))
        rows.append({"path": str(image_path), "faces": len(faces), "used": True})

    if len(embeddings) < 5:
        raise SystemExit("Need at least 5 usable reference faces; 15-30 is recommended.")

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        embeddings=np.stack(embeddings),
        manifest=json.dumps(rows, indent=2),
    )
    print(f"Saved {len(embeddings)} reference embeddings to {output}")


def scan_photos(
    photos_roots: list[Path],
    reference_profile: Path,
    output_dir: Path,
    high_threshold: float,
    review_threshold: float,
    det_size: int,
    model_root: Path,
    provider: str,
    limit: int | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache = open_cache(output_dir / "cache.sqlite")
    app = load_face_app(det_size, model_root, provider)
    reference_embeddings = np.load(reference_profile)["embeddings"]

    images = []
    seen: set[Path] = set()
    for photos_root in photos_roots:
        for path in iter_images(photos_root):
            resolved = path.resolve()
            if resolved in seen or is_inside(path, output_dir):
                continue
            seen.add(resolved)
            images.append(path)
    if limit is not None:
        images = images[:limit]

    matches: list[FaceMatch] = []
    for image_path in tqdm(images, desc="Scanning images"):
        faces = get_or_detect_cached(cache, app, image_path)
        for face_index, face in enumerate(faces):
            score = best_similarity(face["embedding"], reference_embeddings)
            if score >= high_threshold:
                bucket = "high"
            elif score >= review_threshold:
                bucket = "review"
            else:
                continue

            matches.append(
                FaceMatch(
                    image_path=image_path,
                    face_index=face_index,
                    score=score,
                    bucket=bucket,
                    bbox=tuple(face["bbox"]),
                    det_score=float(face["det_score"]),
                )
            )

    csv_path = output_dir / "matches.csv"
    write_matches_csv(csv_path, matches)
    print(f"Wrote {len(matches)} candidate face matches to {csv_path}")


def export_matches(csv_path: Path, output_dir: Path, mode: str) -> None:
    rows = read_match_rows(csv_path)
    exported: set[tuple[str, str]] = set()

    for row in rows:
        source = Path(row["image_path"])
        bucket = row["bucket"]
        if (str(source), bucket) in exported:
            continue
        exported.add((str(source), bucket))

        target_dir = output_dir / f"matches_{bucket}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if target.exists() or target.is_symlink():
            target = target_dir / f"{stable_id(source)}_{source.name}"

        if mode == "copy":
            shutil.copy2(source, target)
        else:
            os.symlink(source, target)

    print(f"Exported {len(exported)} unique image links/files into {output_dir}")


def create_contact_sheets(
    csv_path: Path,
    output_dir: Path,
    bucket: str,
    thumb_size: int,
    columns: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [row for row in read_match_rows(csv_path) if row["bucket"] == bucket]
    if not rows:
        print(f"No {bucket} rows found.")
        return

    label_height = 44
    cell_w = thumb_size
    cell_h = thumb_size + label_height
    rows_per_sheet = 8
    page_size = columns * rows_per_sheet

    for page, chunk_start in enumerate(range(0, len(rows), page_size), start=1):
        chunk = rows[chunk_start : chunk_start + page_size]
        sheet_rows = int(np.ceil(len(chunk) / columns))
        sheet = Image.new("RGB", (columns * cell_w, sheet_rows * cell_h), "white")
        draw = ImageDraw.Draw(sheet)

        for index, row in enumerate(chunk):
            image_path = Path(row["image_path"])
            x = index % columns * cell_w
            y = index // columns * cell_h
            crop = load_face_crop(image_path, parse_bbox(row["bbox"]))
            crop.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
            sheet.paste(crop, (x + (thumb_size - crop.width) // 2, y))
            label = f'{row["score"]}  {image_path.name[:24]}'
            draw.text((x + 4, y + thumb_size + 4), label, fill=(0, 0, 0))

        sheet.save(output_dir / f"{bucket}_{page:03d}.jpg", quality=92)

    print(f"Wrote contact sheets to {output_dir}")


def load_face_app(det_size: int, model_root: Path, provider: str):
    from insightface.app import FaceAnalysis

    model_root.mkdir(parents=True, exist_ok=True)
    providers = ["CPUExecutionProvider"]
    if provider == "coreml":
        providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    app = FaceAnalysis(name="buffalo_l", root=str(model_root), providers=providers)
    app.prepare(ctx_id=-1, det_size=(det_size, det_size))
    return app


def detect_faces(app, image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        return []
    return app.get(image)


def get_or_detect_cached(cache: sqlite3.Connection, app, image_path: Path) -> list[dict[str, object]]:
    stat = image_path.stat()
    row = cache.execute(
        "select faces_json from detections where path = ? and mtime_ns = ? and size = ?",
        (str(image_path), stat.st_mtime_ns, stat.st_size),
    ).fetchone()
    if row:
        return decode_faces(row[0])

    faces = []
    for face in detect_faces(app, image_path):
        faces.append(
            {
                "bbox": [int(value) for value in face.bbox.tolist()],
                "det_score": float(face.det_score),
                "embedding": normalize_embedding(face.embedding),
            }
        )

    cache.execute(
        """
        insert or replace into detections(path, mtime_ns, size, faces_json)
        values (?, ?, ?, ?)
        """,
        (str(image_path), stat.st_mtime_ns, stat.st_size, encode_faces(faces)),
    )
    cache.commit()
    return faces


def open_cache(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        create table if not exists detections (
            path text primary key,
            mtime_ns integer not null,
            size integer not null,
            faces_json text not null
        )
        """
    )
    return connection


def encode_faces(faces: list[dict[str, object]]) -> str:
    rows = []
    for face in faces:
        rows.append(
            {
                "bbox": face["bbox"],
                "det_score": face["det_score"],
                "embedding": np.asarray(face["embedding"], dtype=np.float32).tolist(),
            }
        )
    return json.dumps(rows)


def decode_faces(payload: str) -> list[dict[str, object]]:
    rows = json.loads(payload)
    for row in rows:
        row["embedding"] = np.asarray(row["embedding"], dtype=np.float32)
    return rows


def write_matches_csv(path: Path, matches: list[FaceMatch]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["image_path", "face_index", "score", "bucket", "bbox", "det_score"],
        )
        writer.writeheader()
        for match in sorted(matches, key=lambda item: item.score, reverse=True):
            writer.writerow(
                {
                    "image_path": str(match.image_path),
                    "face_index": match.face_index,
                    "score": f"{match.score:.6f}",
                    "bucket": match.bucket,
                    "bbox": json.dumps(match.bbox),
                    "det_score": f"{match.det_score:.6f}",
                }
            )


def read_match_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def iter_images(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    vector = np.asarray(embedding, dtype=np.float32)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def best_similarity(embedding: np.ndarray, reference_embeddings: np.ndarray) -> float:
    vector = normalize_embedding(embedding)
    scores = reference_embeddings @ vector
    return float(np.max(scores))


def face_area(bbox: np.ndarray) -> float:
    x1, y1, x2, y2 = bbox
    return float(max(0, x2 - x1) * max(0, y2 - y1))


def parse_bbox(value: str) -> tuple[int, int, int, int]:
    parsed = json.loads(value)
    return int(parsed[0]), int(parsed[1]), int(parsed[2]), int(parsed[3])


def load_face_crop(image_path: Path, bbox: tuple[int, int, int, int]) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    pad_x = int(width * 0.35)
    pad_y = int(height * 0.45)
    crop_box = (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(image.width, x2 + pad_x),
        min(image.height, y2 + pad_y),
    )
    return image.crop(crop_box)


def stable_id(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:10]


if __name__ == "__main__":
    main()
