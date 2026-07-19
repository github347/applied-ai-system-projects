from datetime import datetime, timedelta
from pawpal_system import Owner, Pet, Scheduler, Task


def test_task_completion():
    t = Task(title="Test Task", scheduled_at=datetime.now())
    assert not t.completed
    t.mark_complete()
    assert t.completed


def test_task_addition_to_pet():
    pet = Pet(name="TestPet")
    initial = len(pet.tasks)
    # create a task and add by id
    t = Task(title="Feed", scheduled_at=datetime.now())
    pet.add_task(t.id)
    assert len(pet.tasks) == initial + 1
    assert t.id in pet.tasks


def test_sort_by_time_chronological_order():
    """Tasks returned by sort_by_time are in ascending chronological order."""
    sched = Scheduler()
    base = datetime(2026, 3, 15, 9, 0)
    t1 = sched.create_task(title="Last",  scheduled_at=base + timedelta(hours=2))
    t2 = sched.create_task(title="First", scheduled_at=base)
    t3 = sched.create_task(title="Mid",   scheduled_at=base + timedelta(hours=1))

    sorted_tasks = sched.sort_by_time([t1, t2, t3])

    assert [t.title for t in sorted_tasks] == ["First", "Mid", "Last"]
    for i in range(len(sorted_tasks) - 1):
        assert sorted_tasks[i].scheduled_at <= sorted_tasks[i + 1].scheduled_at


def test_daily_recurrence_creates_next_day_task():
    """Completing a daily task returns a new task scheduled for the following day."""
    scheduled = datetime(2026, 3, 15, 8, 0)
    t = Task(title="Morning Walk", scheduled_at=scheduled, recurrence="daily")

    next_task = t.mark_complete()

    assert t.completed
    assert next_task is not None
    assert next_task.title == "Morning Walk"
    assert next_task.scheduled_at == scheduled + timedelta(days=1)
    assert next_task.recurrence == "daily"
    assert not next_task.completed


def test_daily_recurrence_new_task_has_different_id():
    """The new task created by recurrence gets a fresh unique ID."""
    t = Task(title="Feed", scheduled_at=datetime(2026, 3, 15, 7, 0), recurrence="daily")
    next_task = t.mark_complete()

    assert next_task is not None
    assert next_task.id != t.id


def test_no_recurrence_returns_none():
    """Completing a non-recurring task returns None."""
    t = Task(title="One-off Vet Visit", scheduled_at=datetime.now())
    result = t.mark_complete()
    assert result is None


def test_conflict_detection_same_time():
    """check_conflicts flags two tasks scheduled at the same datetime."""
    sched = Scheduler()
    dt = datetime(2026, 3, 15, 10, 0)
    t1 = sched.create_task(title="Bath",  scheduled_at=dt)
    t2 = sched.create_task(title="Groom", scheduled_at=dt)

    warnings = sched.check_conflicts([t1, t2])

    assert len(warnings) == 1
    assert "Bath" in warnings[0]
    assert "Groom" in warnings[0]


def test_conflict_detection_no_conflict():
    """check_conflicts returns no warnings when tasks are at different times."""
    sched = Scheduler()
    base = datetime(2026, 3, 15, 10, 0)
    t1 = sched.create_task(title="Bath",  scheduled_at=base)
    t2 = sched.create_task(title="Groom", scheduled_at=base + timedelta(hours=1))

    warnings = sched.check_conflicts([t1, t2])

    assert warnings == []


def test_conflict_detection_same_pet_conflict():
    """check_conflicts produces a same-pet warning when two overlapping tasks share a pet."""
    sched = Scheduler()
    pet = Pet(name="Buddy")
    pet_store = {pet.id: pet}
    dt = datetime(2026, 3, 15, 11, 0)

    t1 = sched.create_task(title="Walk",  scheduled_at=dt, pet_ids=[pet.id])
    t2 = sched.create_task(title="Train", scheduled_at=dt, pet_ids=[pet.id])

    warnings = sched.check_conflicts([t1, t2], pet_store=pet_store)

    assert len(warnings) == 1
    assert "Same-pet conflict" in warnings[0]
    assert "Buddy" in warnings[0]
