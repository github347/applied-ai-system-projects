"""Tests for pawpal_context: serializing live PawPal objects into (filename, text) docs."""

from datetime import date, datetime

from pawpal_system import Owner, Pet, Scheduler
from pawpal_context import (
    _slug,
    _fmt_date,
    build_pet_store,
    build_pawpal_documents,
)


def test_slug_replaces_non_alphanumeric():
    assert _slug("Morning Walk") == "Morning_Walk"
    assert _slug("Vet: 3pm!") == "Vet_3pm"


def test_slug_empty_falls_back_to_unnamed():
    assert _slug("") == "unnamed"
    assert _slug("   ") == "unnamed"


def test_fmt_date_handles_none():
    assert _fmt_date(None) == "unknown"
    assert _fmt_date(date(2026, 3, 15)) == "2026-03-15"


def test_build_pet_store_collects_all_pets():
    o1 = Owner(name="Alex")
    o1.add_pet(Pet(name="Bella"))
    o2 = Owner(name="Sam")
    o2.add_pet(Pet(name="Rex"))
    o2.add_pet(Pet(name="Milo"))

    store = build_pet_store([o1, o2])

    assert len(store) == 3
    assert {p.name for p in store.values()} == {"Bella", "Rex", "Milo"}


def test_build_documents_includes_owner_and_pet_docs():
    owner = Owner(name="Alex")
    owner.add_pet(Pet(name="Bella", species="dog", sex="F"))

    docs = build_pawpal_documents(owners=[owner])
    filenames = [name for name, _ in docs]

    assert "owner_Alex.txt" in filenames
    assert "pet_Bella.txt" in filenames

    owner_text = next(text for name, text in docs if name == "owner_Alex.txt")
    assert "Alex" in owner_text
    assert "Bella" in owner_text


def test_pet_document_mentions_owner_and_details():
    owner = Owner(name="Alex")
    pet = Pet(name="Bella", species="dog", sex="F", allergies=["pollen"])
    owner.add_pet(pet)

    docs = build_pawpal_documents(owners=[owner])
    pet_text = next(text for name, text in docs if name == "pet_Bella.txt")

    assert "Bella" in pet_text
    assert "dog" in pet_text
    assert "pollen" in pet_text
    assert "Owner: Alex" in pet_text


def test_build_documents_includes_task_docs():
    owner = Owner(name="Alex")
    pet = Pet(name="Bella")
    owner.add_pet(pet)

    sched = Scheduler()
    sched.create_task(
        title="Morning Walk",
        scheduled_at=datetime(2026, 3, 15, 9, 0),
        pet_ids=[pet.id],
        priority=2,
    )

    docs = build_pawpal_documents(owners=[owner], scheduler=sched)
    filenames = [name for name, _ in docs]

    assert "task_Morning_Walk.txt" in filenames
    task_text = next(text for name, text in docs if name == "task_Morning_Walk.txt")
    assert "Morning Walk" in task_text
    assert "Bella" in task_text  # assigned pet resolved by name


def test_loose_pets_are_deduplicated_against_owner_pets():
    owner = Owner(name="Alex")
    pet = Pet(name="Bella")
    owner.add_pet(pet)

    # Passing the same pet again via `pets` must not duplicate its document.
    docs = build_pawpal_documents(owners=[owner], pets=[pet])
    pet_docs = [name for name, _ in docs if name == "pet_Bella.txt"]

    assert len(pet_docs) == 1


def test_loose_pet_without_owner_is_included():
    stray = Pet(name="Ghost")
    docs = build_pawpal_documents(owners=[], pets=[stray])
    filenames = [name for name, _ in docs]

    assert "pet_Ghost.txt" in filenames


def test_empty_input_returns_no_documents():
    assert build_pawpal_documents() == []
