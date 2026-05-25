# Troubleshooting

## The GUI Starts But A Scan Does Not

Check that:

- the reference folder exists
- the photo folder exists
- the person ID contains only letters, numbers, dots, underscores, or hyphens
- the reference folder contains at least 5 usable face photos

The GUI run log should show the exact error.

## Reference Build Says There Are Not Enough Faces

The face detector did not find enough usable faces in the reference folder.

Try:

- clearer selfies
- larger face crops
- fewer sunglasses, masks, or extreme angles
- event photos where the person is clearly visible

## The First Scan Is Slow

The first scan detects faces in all event photos and writes `outputs/cache.sqlite`.
Later searches for other people can reuse that cache and should usually be much faster.

## Later Scans Are Slow Again

Cache reuse depends on:

- using the same photo files
- unchanged file modification times and sizes
- the same `--max-image-size`
- keeping `outputs/cache.sqlite`

Changing those can force face detection to run again.

## Too Many False Positives

Raise thresholds slightly:

```bash
--high-threshold 0.46 --review-threshold 0.37
```

Also improve reference photos with clearer, more varied examples.

## Missing Obvious Photos

Lower the review threshold slightly:

```bash
--review-threshold 0.31
```

Expect more false positives and review contact sheets carefully.

## Symlink Export Fails

Use copy mode:

```bash
--export-mode copy
```

On Windows, symlinks may require developer mode or administrator privileges.

## HEIC Files Do Not Work

HEIC support depends on your local image libraries. Convert HEIC files to JPEG if they
do not load reliably.
