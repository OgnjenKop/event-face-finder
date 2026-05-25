# Workflow

## 1. Prepare Reference Photos

Create one folder per person:

```bash
mkdir -p reference_people/alex
```

Add clear photos of that person to the folder. Good references include:

- front-facing photos
- side-angle photos
- event lighting
- similar hair, glasses, facial hair, or clothing context when available

Use at least 5 usable face photos. 8-15 is better for event collections with many
people and varied camera angles.

## 2. Run The GUI

```bash
python -m event_face_finder gui
```

Open `http://127.0.0.1:8765`.

Enter:

- person ID, such as `alex`
- reference folder, such as `reference_people/alex`
- one or more photo folders, one per line

Start the scan and watch the run log. Results appear after the scan exports matches
and creates contact sheets.

## 3. Review Results

Inspect:

```text
outputs/people/alex/matches_high/
outputs/people/alex/matches_review/
outputs/people/alex/contact_sheets/
outputs/people/alex/matches.csv
```

Treat high matches as likely matches, not proof. Review candidates should always be
checked manually.

## 4. Search Another Person

Create a new reference folder and run a new person ID. The face-detection cache in
`outputs/cache.sqlite` can make later searches much faster when using the same photo
folders and image-size settings.

## CLI Equivalent

```bash
python -m event_face_finder run-person \
  --person-id alex \
  --photos-root "/path/to/event/photos"
```

Repeat `--photos-root` for multiple folders.
