from datetime import datetime, date, time
from pawpal_system import Owner, Pet, Scheduler


def print_tasks(label: str, tasks, pet_store):
    print(f"\n{label}")
    if not tasks:
        print("  (none)")
        return
    for t in tasks:
        time_str = t.scheduled_at.strftime("%H:%M")
        pet_names = [pet_store[pid].name for pid in t.pet_ids if pid in pet_store]
        status = "done" if t.completed else "pending"
        print(f"  {time_str} | {t.title} | Pets: {', '.join(pet_names)} | {status}")


def main():
    owner = Owner(name="Alex")

    pet1 = Pet(name="Bella", birthday=date(2020, 5, 4), sex="F")
    pet2 = Pet(name="Max", birthday=date(2019, 8, 12), sex="M")

    owner.add_pet(pet1)
    owner.add_pet(pet2)

    sched = Scheduler()

    # Add tasks out of order (evening first, then morning, then midday)
    t3 = sched.create_task(
        title="Evening Play",
        scheduled_at=datetime.combine(date.today(), time(hour=18, minute=0)),
        owner_id=owner.id,
        pet_ids=[pet1.id, pet2.id],
    )

    t1 = sched.create_task(
        title="Morning Walk",
        scheduled_at=datetime.combine(date.today(), time(hour=9, minute=0)),
        owner_id=owner.id,
        pet_ids=[pet1.id],
        recurrence="daily",
    )

    t2 = sched.create_task(
        title="Midday Meds",
        scheduled_at=datetime.combine(date.today(), time(hour=11, minute=30)),
        owner_id=owner.id,
        pet_ids=[pet2.id],
        recurrence="weekly",
    )

    sched.assign_task_to_pets(t1.id, [pet1.id], pet_store=owner.pets)
    sched.assign_task_to_pets(t2.id, [pet2.id], pet_store=owner.pets)
    sched.assign_task_to_pets(t3.id, [pet1.id, pet2.id], pet_store=owner.pets)

    # Mark recurring tasks complete — each returns a next-occurrence Task
    next_t1 = t1.mark_complete()
    if next_t1:
        sched.add_task(next_t1)
        sched.assign_task_to_pets(next_t1.id, next_t1.pet_ids, pet_store=owner.pets)

    next_t2 = t2.mark_complete()
    if next_t2:
        sched.add_task(next_t2)
        sched.assign_task_to_pets(next_t2.id, next_t2.pet_ids, pet_store=owner.pets)

    all_tasks = sched.view_tasks_on(date.today())

    # Sort by time
    sorted_tasks = sched.sort_by_time(all_tasks)
    print_tasks("All tasks sorted by time:", sorted_tasks, owner.pets)

    # Filter: pending only
    pending = sched.filter_tasks(all_tasks, completed=False)
    sorted_pending = sched.sort_by_time(pending)
    print_tasks("Pending tasks:", sorted_pending, owner.pets)

    # Filter: completed only
    done = sched.filter_tasks(all_tasks, completed=True)
    print_tasks("Completed tasks:", done, owner.pets)

    # Filter: tasks for Bella
    bella_tasks = sched.filter_tasks(all_tasks, pet_name="Bella", pet_store=owner.pets)
    sorted_bella = sched.sort_by_time(bella_tasks)
    print_tasks("Tasks for Bella:", sorted_bella, owner.pets)

    # Filter: tasks for Max
    max_tasks = sched.filter_tasks(all_tasks, pet_name="Max", pet_store=owner.pets)
    sorted_max = sched.sort_by_time(max_tasks)
    print_tasks("Tasks for Max:", sorted_max, owner.pets)

    # Show next occurrences created by mark_complete
    print("\n--- Recurring task next occurrences ---")
    if next_t1:
        print(f"  '{next_t1.title}' next run: {next_t1.scheduled_at.strftime('%Y-%m-%d %H:%M')} (recurrence: {next_t1.recurrence})")
    if next_t2:
        print(f"  '{next_t2.title}' next run: {next_t2.scheduled_at.strftime('%Y-%m-%d %H:%M')} (recurrence: {next_t2.recurrence})")

    # --- Conflict detection demo ---
    # Same-pet conflict: Bella has two tasks at 09:00
    sched.create_task(
        title="Vet Check",
        scheduled_at=datetime.combine(date.today(), time(hour=9, minute=0)),
        owner_id=owner.id,
        pet_ids=[pet1.id],
    )
    # Cross-pet conflict: Max gets a task at 18:00 (same as Evening Play)
    sched.create_task(
        title="Bath Time",
        scheduled_at=datetime.combine(date.today(), time(hour=18, minute=0)),
        owner_id=owner.id,
        pet_ids=[pet2.id],
    )

    all_tasks_with_conflicts = sched.view_tasks_on(date.today())
    print("\n--- Conflict detection ---")
    warnings = sched.check_conflicts(all_tasks_with_conflicts, pet_store=owner.pets)
    if warnings:
        for w in warnings:
            print(f"  {w}")
    else:
        print("  No conflicts found.")


if __name__ == "__main__":
    main()
