# Privacy

Event Face Finder is designed to run locally. It does not upload photos, face crops,
embeddings, reference images, or match results to a hosted service.

This does not make every use appropriate. Face recognition can be sensitive and may be
regulated depending on where you are and how the results are used.

## Data Created Locally

The tool can create these local artifacts:

- `outputs/cache.sqlite`: detected face boxes and face embeddings for scanned photos.
- `outputs/**/reference_profile.npz`: embeddings derived from reference photos.
- `outputs/**/matches.csv`: paths, bounding boxes, and similarity scores for candidate matches.
- `outputs/**/matches_high` and `outputs/**/matches_review`: symlinks or copies of matched source photos.
- `outputs/**/contact_sheets`: review images containing face crops.

These files can contain biometric data and local file paths. Do not publish them,
commit them, or share them without consent from the people involved.

## Consent And Appropriate Use

Use this software only on photo collections you are allowed to process. For public or
commercial events, make sure your use matches:

- local law
- participant consent
- event policies
- venue policies
- platform rules
- photographer or organizer contracts

Do not use this project for non-consensual tracking, surveillance, harassment, or
identification of people in contexts where they would not reasonably expect it.

## Accuracy

Face recognition is probabilistic. A match can be wrong, and a real appearance can be
missed. Treat `matches_high` as likely matches, not proof, and manually review results
before sharing or taking action.

## Local GUI

The GUI is intended for local use on `127.0.0.1`. Do not expose it to untrusted
networks. It can start scans and read generated contact sheets.

## Data Deletion

To remove generated biometric data, delete the relevant output folders:

```bash
rm -rf outputs/cache.sqlite outputs/people
```

Also remove any reference photos you no longer need from `reference_people/`.

## Model And Dependency Licensing

This project uses third-party face analysis models through InsightFace. Check the
licenses and terms for InsightFace, ONNX Runtime, and the model weights before using
the software in commercial, public-sector, or regulated contexts.
