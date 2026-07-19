from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from datetime import datetime, date, timedelta
from uuid import uuid4


@dataclass
class Task:
    """
    Represents a task associated with pets and their owners.

    Attributes:
        id (str): Unique identifier for the task.
        title (str): Title of the task.
        scheduled_at (datetime): Date and time when the task is scheduled.
        description (str): Detailed description of the task.
        reminder (bool): Whether a reminder is set for the task.
        repeated (bool): Whether the task is recurring.
        priority (int): Priority level of the task.
        completed (bool): Whether the task has been completed.
        owner_id (Optional[str]): Identifier of the owner associated with the task.
        pet_ids (List[str]): List of pet identifiers assigned to the task.

    Methods:
        mark_complete(): Marks the task as completed.
    """
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = ""
    scheduled_at: datetime = field(default_factory=lambda: datetime.now())
    description: str = ""
    reminder: bool = False
    repeated: bool = False
    recurrence: Optional[str] = None  # "daily" | "weekly" | None
    priority: int = 0
    completed: bool = False
    owner_id: Optional[str] = None
    pet_ids: List[str] = field(default_factory=list)  # allow assignment to multiple pets

    def mark_complete(self) -> Optional["Task"]:
        """Mark this task as completed.

        Returns a new Task for the next occurrence if recurrence is "daily" or
        "weekly", otherwise returns None.
        """
        self.completed = True
        if self.recurrence == "daily":
            delta = timedelta(days=1)
        elif self.recurrence == "weekly":
            delta = timedelta(weeks=1)
        else:
            return None
        return Task(
            title=self.title,
            scheduled_at=self.scheduled_at + delta,
            description=self.description,
            reminder=self.reminder,
            repeated=self.repeated,
            recurrence=self.recurrence,
            priority=self.priority,
            owner_id=self.owner_id,
            pet_ids=list(self.pet_ids),
        )

@dataclass
class Pet:
    """
    Represents a pet with attributes such as name, birthday, sex, allergies, and associated tasks.

    Attributes:
        id (str): Unique identifier for the pet.
        name (str): Name of the pet.
        birthday (Optional[date]): Birthday of the pet.
        sex (Optional[str]): Sex of the pet.
        allergies (List[str]): List of allergies the pet has.
        tasks (List[str]): List of task IDs associated with the pet.

    Methods:
        edit_name(new_name: str): Updates the pet's name.
        edit_sex(new_sex: str): Updates the pet's sex.
        edit_birthday(new_birthday: date): Updates the pet's birthday.
        add_task(task_id: str): Adds a task ID to the pet's task list if not already present.
        remove_task(task_id: str): Removes a task ID from the pet's task list if present.
    """
    id: str = field(default_factory=lambda: uuid4().hex)
    name: str = ""
    birthday: Optional[date] = None
    sex: Optional[str] = None
    species: Optional[str] = None
    allergies: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)  # store task ids

    def edit_name(self, new_name: str) -> None:
        self.name = new_name

    def edit_sex(self, new_sex: str) -> None:
        self.sex = new_sex

    def edit_species(self, new_species: str) -> None:
        self.species = new_species

    def edit_birthday(self, new_birthday: date) -> None:
        self.birthday = new_birthday

    def add_task(self, task_id: str) -> None:
        if task_id not in self.tasks:
            self.tasks.append(task_id)

    def remove_task(self, task_id: str) -> None:
        if task_id in self.tasks:
            self.tasks.remove(task_id)


class Owner:
    """
    Represents a pet owner in the PawPal system.

    Attributes:
        id (str): Unique identifier for the owner.
        name (str): Name of the owner.
        pets (Dict[str, Pet]): Dictionary mapping pet IDs to Pet objects owned by the owner.

    Methods:
        add_pet(pet: Pet) -> None:
            Adds a pet to the owner's collection.

        edit_pet(pet_id: str, **kwargs) -> None:
            Edits attributes of a pet owned by the owner, given the pet's ID and attribute values.

        delete_pet(pet_id: str) -> None:
            Removes a pet from the owner's collection by pet ID.
    """
    def __init__(self, name: str):
        self.id: str = uuid4().hex
        self.name = name
        self.pets: Dict[str, Pet] = {}

    def add_pet(self, pet: Pet) -> None:
        self.pets[pet.id] = pet
        pet.owner = self

    def edit_pet(self, pet_id: str, **kwargs) -> None:
        pet = self.pets.get(pet_id)
        if not pet:
            return
        for key, value in kwargs.items():
            setattr(pet, key, value)

    def delete_pet(self, pet_id: str) -> None:
        if pet_id in self.pets:
            del self.pets[pet_id]


class Scheduler:
    """
    Scheduler is a canonical store for Task objects, providing fast lookup and management by task ID, date, and pet association.

    Attributes:
        tasks_by_id (Dict[str, Task]): Maps task IDs to Task objects.
        tasks_by_date (Dict[date, Set[str]]): Maps dates to sets of task IDs scheduled on those dates.
        tasks_by_pet (Dict[str, Set[str]]): Maps pet IDs to sets of task IDs assigned to each pet.

    Methods:
        __init__():
            Initializes empty task indexes.

        _index_task(task: Task) -> None:
            Adds a Task to all relevant indexes (ID, date, pet).

        _unindex_task(task: Task) -> None:
            Removes a Task from all relevant indexes.

        create_task(title: str, scheduled_at: datetime, owner_id: Optional[str] = None, pet_ids: Optional[List[str]] = None, **kwargs) -> Task:
            Creates a new Task, indexes it, and returns the Task object.

        add_task(task: Task) -> None:
            Adds an existing Task object to the scheduler and indexes it.

        edit_task(task_id: str, **kwargs) -> None:
            Edits attributes of a Task. Reindexes if scheduled_at or pet_ids change.

        delete_task(task_id: str) -> None:
            Removes a Task from the scheduler and all indexes.

        assign_task_to_pets(task_id: str, pet_ids: List[str], pet_store: Dict[str, Pet] = None) -> None:
            Assigns a Task to multiple pets and updates indexes and optional pet_store.

        unassign_task_from_pet(task_id: str, pet_id: str, pet_store: Dict[str, Pet] = None) -> None:
            Removes a Task assignment from a specific pet and updates indexes and optional pet_store.

        view_tasks_on(target_date: date) -> List[Task]:
            Returns a list of Tasks scheduled on a specific date.

        view_future_tasks(from_date: date) -> List[Task]:
            Returns a list of Tasks scheduled after a given date.
    """
    """Canonical store for tasks. Indexes tasks by id, date, and pet for fast lookups.
    Pets store task ids; Scheduler maintains the authoritative Task objects."""

    def __init__(self):
        self.tasks_by_id: Dict[str, Task] = {}
        self.tasks_by_date: Dict[date, Set[str]] = {}
        self.tasks_by_pet: Dict[str, Set[str]] = {}

    def _index_task(self, task: Task) -> None:
        self.tasks_by_id[task.id] = task
        d = task.scheduled_at.date()
        self.tasks_by_date.setdefault(d, set()).add(task.id)
        for pid in task.pet_ids:
            self.tasks_by_pet.setdefault(pid, set()).add(task.id)

    def _unindex_task(self, task: Task) -> None:
        self.tasks_by_id.pop(task.id, None)
        d = task.scheduled_at.date()
        if d in self.tasks_by_date:
            self.tasks_by_date[d].discard(task.id)
            if not self.tasks_by_date[d]:
                del self.tasks_by_date[d]
        for pid in list(self.tasks_by_pet.keys()):
            self.tasks_by_pet[pid].discard(task.id)
            if not self.tasks_by_pet[pid]:
                del self.tasks_by_pet[pid]

    def create_task(self, title: str, scheduled_at: datetime, owner_id: Optional[str] = None, pet_ids: Optional[List[str]] = None, **kwargs) -> Task:
        t = Task(title=title, scheduled_at=scheduled_at, owner_id=owner_id, pet_ids=pet_ids or [], **kwargs)
        self._index_task(t)
        return t

    def add_task(self, task: Task) -> None:
        # add an existing Task object into the scheduler
        self._index_task(task)

    def edit_task(self, task_id: str, **kwargs) -> None:
        task = self.tasks_by_id.get(task_id)
        if not task:
            return
        # If scheduled_at or pet_ids change, reindex
        old_date = task.scheduled_at.date()
        old_pet_ids = set(task.pet_ids)
        for key, value in kwargs.items():
            setattr(task, key, value)
        new_date = task.scheduled_at.date()
        new_pet_ids = set(task.pet_ids)
        if old_date != new_date or old_pet_ids != new_pet_ids:
            self._unindex_task(task)
            self._index_task(task)

    def delete_task(self, task_id: str) -> None:
        task = self.tasks_by_id.get(task_id)
        if not task:
            return
        self._unindex_task(task)

    def assign_task_to_pets(self, task_id: str, pet_ids: List[str], pet_store: Dict[str, Pet] = None) -> None:
        """Assigns task to multiple pets. Optionally updates provided pet_store to include task ids in pets."""
        task = self.tasks_by_id.get(task_id)
        if not task:
            return
        # update index removal for old pet ids
        old_pet_ids = set(task.pet_ids)
        for pid in old_pet_ids - set(pet_ids):
            if pid in self.tasks_by_pet:
                self.tasks_by_pet[pid].discard(task.id)
        task.pet_ids = pet_ids
        for pid in pet_ids:
            self.tasks_by_pet.setdefault(pid, set()).add(task.id)
            if pet_store and pid in pet_store:
                pet_store[pid].add_task(task.id)

    def unassign_task_from_pet(self, task_id: str, pet_id: str, pet_store: Dict[str, Pet] = None) -> None:
        task = self.tasks_by_id.get(task_id)
        if not task:
            return
        if pet_id in task.pet_ids:
            task.pet_ids.remove(pet_id)
        if pet_id in self.tasks_by_pet:
            self.tasks_by_pet[pet_id].discard(task.id)
        if pet_store and pet_id in pet_store:
            pet_store[pet_id].remove_task(task.id)

    def view_tasks_on(self, target_date: date) -> List[Task]:
        ids = self.tasks_by_date.get(target_date, set())
        return [self.tasks_by_id[i] for i in ids]

    def view_future_tasks(self, from_date: date) -> List[Task]:
        result: List[Task] = []
        for d, ids in self.tasks_by_date.items():
            if d > from_date:
                result.extend(self.tasks_by_id[i] for i in ids)
        return result

    def sort_by_time(self, tasks: List[Task]) -> List[Task]:
        return sorted(tasks, key=lambda t: t.scheduled_at)

    def check_conflicts(
        self,
        tasks: List[Task],
        pet_store: Dict[str, "Pet"] = None,
    ) -> List[str]:
        """Return a list of warning strings for tasks sharing the same scheduled_at.

        Checks both same-pet and cross-pet conflicts. Does not raise — callers
        decide what to do with the warnings.
        """
        by_time: Dict[datetime, List[Task]] = {}
        for task in tasks:
            by_time.setdefault(task.scheduled_at, []).append(task)

        warnings = []
        for dt, conflicting in by_time.items():
            if len(conflicting) < 2:
                continue
            time_str = dt.strftime("%Y-%m-%d %H:%M")
            for i, a in enumerate(conflicting):
                for b in conflicting[i + 1:]:
                    shared_pets = set(a.pet_ids) & set(b.pet_ids)
                    if shared_pets and pet_store:
                        names = ", ".join(
                            pet_store[pid].name for pid in shared_pets if pid in pet_store
                        )
                        warnings.append(
                            f"WARNING [{time_str}] Same-pet conflict: '{a.title}' and "
                            f"'{b.title}' both assigned to {names}."
                        )
                    elif shared_pets:
                        warnings.append(
                            f"WARNING [{time_str}] Same-pet conflict: '{a.title}' and "
                            f"'{b.title}' share pet IDs {shared_pets}."
                        )
                    else:
                        warnings.append(
                            f"WARNING [{time_str}] Scheduling conflict: '{a.title}' and "
                            f"'{b.title}' are scheduled at the same time."
                        )
        return warnings

    def filter_tasks(
        self,
        tasks: List[Task],
        completed: Optional[bool] = None,
        pet_name: Optional[str] = None,
        pet_store: Dict[str, "Pet"] = None,
    ) -> List[Task]:
        result = []
        for task in tasks:
            if completed is not None and task.completed != completed:
                continue
            if pet_name is not None:
                if not pet_store:
                    continue
                pet_names = [
                    pet_store[pid].name
                    for pid in task.pet_ids
                    if pid in pet_store
                ]
                if pet_name not in pet_names:
                    continue
            result.append(task)
        return result

if __name__ == "__main__":
    # Minimal usage example (updated for id/datetime-based API)
    from datetime import datetime, date, time

    owner = Owner(name="Alex")
    pet = Pet(name="Bella", birthday=date(2020, 5, 4), sex="F")
    owner.add_pet(pet)

    sched = Scheduler()
    # create a task scheduled for today at 09:00
    scheduled = datetime.combine(date.today(), time(hour=9, minute=0))
    t1 = sched.create_task(title="Walk Bella", scheduled_at=scheduled, owner_id=owner.id, pet_ids=[pet.id], priority=1)

    # ensure pet knows about the task (optionally keep pets synced via a pet_store)
    pet.add_task(t1.id)

    print("Owner:", owner.name, "id=", owner.id)
    print("Pet:", pet.name, "id=", pet.id, "tasks=", pet.tasks)
    print("Tasks today:", [t.title for t in sched.view_tasks_on(date.today())])
