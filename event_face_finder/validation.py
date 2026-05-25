from __future__ import annotations


def is_safe_person_id(person_id: str) -> bool:
    return bool(person_id) and all(
        char.isalnum() or char in "._-" for char in person_id
    )
