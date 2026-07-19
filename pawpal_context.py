"""
Bridge between the live PawPal system and PawPalBot.

Turns the mutable PawPal objects (Owner, Pet, Scheduler/Task) into plain-text
"documents" — the same (filename, text) shape PawPalBot already indexes for the
docs/ folder. This lets the retrieval + RAG pipeline answer questions about the
owner's actual pets and care schedule, not just static markdown files.
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

from pawpal_system import Owner, Pet, Scheduler


def _slug(text: str) -> str:
    """Filesystem/citation friendly label, e.g. 'Morning Walk' -> 'Morning_Walk'."""
    cleaned = "".join(c if c.isalnum() else "_" for c in (text or "").strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "unnamed"


def _fmt_date(value: Optional[date]) -> str:
    return value.isoformat() if value else "unknown"


def build_pet_store(owners: List[Owner]) -> Dict[str, Pet]:
    """Collect every pet from every owner into one {pet_id: Pet} map."""
    pet_store: Dict[str, Pet] = {}
    for owner in owners:
        for pet_id, pet in owner.pets.items():
            pet_store[pet_id] = pet
    return pet_store


def _owner_document(owner: Owner) -> Tuple[str, str]:
    pet_names = [pet.name for pet in owner.pets.values()] or ["no pets yet"]
    text = (
        f"Owner profile: {owner.name} (id {owner.id}).\n"
        f"{owner.name} cares for {len(owner.pets)} pet(s): {', '.join(pet_names)}."
    )
    return f"owner_{_slug(owner.name)}.txt", text


def _pet_document(pet: Pet, owner_name: Optional[str]) -> Tuple[str, str]:
    allergies = ", ".join(pet.allergies) if pet.allergies else "none recorded"
    lines = [
        f"Pet profile: {pet.name} (id {pet.id}).",
        f"Species: {pet.species or 'unknown'}. Sex: {pet.sex or 'unknown'}.",
        f"Birthday: {_fmt_date(pet.birthday)}.",
        f"Allergies: {allergies}.",
        f"Number of assigned tasks: {len(pet.tasks)}.",
    ]
    if owner_name:
        lines.append(f"Owner: {owner_name}.")
    return f"pet_{_slug(pet.name)}.txt", "\n".join(lines)


def _task_document(task, pet_store: Dict[str, Pet]) -> Tuple[str, str]:
    pet_names = [
        pet_store[pid].name for pid in task.pet_ids if pid in pet_store
    ] or ["unassigned"]
    lines = [
        f"Care task: {task.title} (id {task.id}).",
        f"Scheduled for: {task.scheduled_at.strftime('%Y-%m-%d %H:%M')}.",
        f"Assigned pets: {', '.join(pet_names)}.",
        f"Priority: {task.priority}. Recurrence: {task.recurrence or 'none'}.",
        f"Reminder set: {'yes' if task.reminder else 'no'}. "
        f"Status: {'completed' if task.completed else 'pending'}.",
    ]
    if task.description:
        lines.append(f"Description: {task.description}")
    return f"task_{_slug(task.title)}.txt", "\n".join(lines)


def build_pawpal_documents(
    owners: Optional[List[Owner]] = None,
    scheduler: Optional[Scheduler] = None,
    pets: Optional[List[Pet]] = None,
) -> List[Tuple[str, str]]:
    """
    Serialize the current PawPal state into a list of (filename, text) documents
    that PawPalBot can index and retrieve over.

    owners: list of Owner objects (their pets are read from owner.pets)
    scheduler: Scheduler holding the authoritative Task objects
    pets: extra Pet objects to include (e.g. pets created in the UI that are not
        yet linked to an owner); deduplicated against owners' pets by id
    """
    owners = owners or []
    documents: List[Tuple[str, str]] = []

    pet_store = build_pet_store(owners)

    # Fold in any loose pets not attached to an owner (kept only if new).
    for pet in pets or []:
        pet_store.setdefault(pet.id, pet)

    # Map pet_id -> owner name so pet docs can mention who they belong to.
    pet_owner_name: Dict[str, str] = {}
    for owner in owners:
        documents.append(_owner_document(owner))
        for pet_id in owner.pets:
            pet_owner_name[pet_id] = owner.name

    for pet_id, pet in pet_store.items():
        documents.append(_pet_document(pet, pet_owner_name.get(pet_id)))

    if scheduler is not None:
        for task in scheduler.tasks_by_id.values():
            documents.append(_task_document(task, pet_store))

    return documents
