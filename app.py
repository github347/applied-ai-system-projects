import streamlit as st
from datetime import datetime
from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Add a owner")
owner_name = st.text_input("Owner name", value="Jordan")
# pet_name = st.text_input("Pet name", value="Mochi")
# species = st.selectbox("Species", ["dog", "cat", "other"])

# Owner creation UI
col_owner1, col_owner2 = st.columns([2, 1])

# ensure owner object slot
if "owner_obj" not in st.session_state:
    st.session_state.owner_obj = None

with col_owner1:
    if st.button("Create owner"):
        try:
            st.session_state.owner_obj = Owner(name=owner_name)
            st.success(f"Created owner {owner_name}")
        except TypeError:
            try:
                st.session_state.owner_obj = Owner(owner_name)
                st.success(f"Created owner {owner_name}")
            except Exception as e:
                st.error(f"Failed to create Owner: {e}")
                st.session_state.owner_obj = None

with col_owner2:
    st.write("Current owner:")
    owner_obj = st.session_state.get("owner_obj")
    if owner_obj:
        st.write(getattr(owner_obj, "name", "Unknown"))
    else:
        st.info("No owner yet. Create one above.")

# Ensure pets list exists (store objects)
if "pets" not in st.session_state:
    st.session_state.pets = []

st.markdown("### Add a pet")
with st.form("add_pet_form"):
    pet_name_input = st.text_input("Pet name", value="Mochi")
    pet_birthday = st.date_input("Birthday")
    pet_species = st.selectbox("Species", ["dog", "cat", "other"])
    # Owner selection inside the form (uses owner_obj or owners list if present)
    owners_for_select = []
    if "owners" in st.session_state and isinstance(st.session_state["owners"], list):
        owners_for_select = st.session_state["owners"]
    else:
        single_owner = st.session_state.get("owner_obj")
        if single_owner:
            owners_for_select = [single_owner]

    selected_owner = st.selectbox(
        "Owner",
        options=[None] + owners_for_select,
        format_func=lambda o: "No owner" if o is None else getattr(o, "name", "Unknown"),
    )

    submitted = st.form_submit_button("Add pet")

if submitted:
    try:
        pet_obj = Pet(name=pet_name_input, birthday=pet_birthday, species=pet_species)
    except TypeError:
        try:
            pet_obj = Pet(pet_name_input, pet_birthday, pet_species)
        except Exception as e:
            st.error(f"Failed to create Pet: {e}")
            pet_obj = None

    if pet_obj:
        # Use owner chosen in the form first, else fall back to session owner_obj
        owner_instance = selected_owner or st.session_state.get("owner_obj")
        if owner_instance:
            if hasattr(owner_instance, "add_pet"):
                try:
                    owner_instance.add_pet(pet_obj)
                except Exception:
                    try:
                        setattr(pet_obj, "owner", owner_instance)
                    except Exception:
                        pass
            else:
                try:
                    setattr(pet_obj, "owner", owner_instance)
                except Exception:
                    pass
        else:
            st.info("No owner to link to; pet will be created without owner.")

        st.session_state.pets.append(pet_obj)
        st.success(f"Added pet {pet_name_input}")

st.write("Current pets:")
if st.session_state.pets:
    pets_display = []
    for p in st.session_state.pets:
        name = getattr(p, "name", None) or getattr(p, "title", None)
        species_attr = getattr(p, "species", None)
        owner_attr = None
        owner_obj = getattr(p, "owner", None)
        if owner_obj:
            owner_attr = owner_obj if isinstance(owner_obj, str) else getattr(owner_obj, "name", None)
        pets_display.append({"name": name, "species": species_attr, "owner": owner_attr})
    st.table(pets_display)
else:
    st.info("No pets yet. Add one above.")

st.divider()

# ── Scheduler singleton ──────────────────────────────────────────────────────
if "scheduler" not in st.session_state:
    st.session_state.scheduler = Scheduler()

scheduler: Scheduler = st.session_state.scheduler

# ── Add a Task ───────────────────────────────────────────────────────────────
st.subheader("Add a Task")

with st.form("add_task_form"):
    task_title = st.text_input("Task title", value="Walk")
    task_desc  = st.text_area("Description", value="")

    col_d, col_t = st.columns(2)
    with col_d:
        task_date = st.date_input("Date", value=datetime.today().date())
    with col_t:
        task_time = st.time_input("Time", value=datetime.now().replace(second=0, microsecond=0).time())

    col_p, col_r, col_rec = st.columns(3)
    with col_p:
        task_priority = st.number_input("Priority (0 = low)", min_value=0, max_value=10, value=1, step=1)
    with col_r:
        task_reminder = st.checkbox("Reminder")
    with col_rec:
        task_recurrence = st.selectbox("Recurrence", ["none", "daily", "weekly"])

    # Pet multi-select – use pets already in session state
    pet_options = st.session_state.pets
    selected_pets = st.multiselect(
        "Assign to pets",
        options=pet_options,
        format_func=lambda p: getattr(p, "name", "?"),
    )

    task_submitted = st.form_submit_button("Add Task")

if task_submitted:
    if not task_title.strip():
        st.error("Task title is required.")
    else:
        owner_obj = st.session_state.get("owner_obj")
        scheduled_at = datetime.combine(task_date, task_time)
        rec = task_recurrence if task_recurrence != "none" else None

        new_task = scheduler.create_task(
            title=task_title.strip(),
            scheduled_at=scheduled_at,
            owner_id=owner_obj.id if owner_obj else None,
            pet_ids=[p.id for p in selected_pets],
            description=task_desc,
            priority=int(task_priority),
            reminder=task_reminder,
            recurrence=rec,
        )
        # keep pet objects in sync
        pet_store = {p.id: p for p in st.session_state.pets}
        for p in selected_pets:
            p.add_task(new_task.id)

        st.success(f"Task '{new_task.title}' added for {scheduled_at.strftime('%Y-%m-%d %H:%M')}")

st.divider()

# ── Build / View Schedule ────────────────────────────────────────────────────
st.subheader("Build Schedule")

col_view1, col_view2, col_view3 = st.columns(3)
with col_view1:
    view_date = st.date_input("View tasks for date", value=datetime.today().date(), key="view_date")
with col_view2:
    filter_completed = st.selectbox("Filter by status", ["all", "pending", "completed"], key="filter_completed")
with col_view3:
    filter_pet_names = [getattr(p, "name", "?") for p in st.session_state.pets]
    filter_pet = st.selectbox("Filter by pet", ["all"] + filter_pet_names, key="filter_pet")

if st.button("Generate schedule"):
    st.session_state.show_schedule = True

if st.session_state.get("show_schedule"):
    pet_store = {p.id: p for p in st.session_state.pets}

    # show any confirmation carried over from a previous rerun
    if st.session_state.get("complete_msg"):
        st.success(st.session_state.pop("complete_msg"))

    tasks = scheduler.view_tasks_on(view_date)

    # filter
    completed_filter = None if filter_completed == "all" else (filter_completed == "completed")
    pet_name_filter  = None if filter_pet == "all" else filter_pet
    tasks = scheduler.filter_tasks(
        tasks,
        completed=completed_filter,
        pet_name=pet_name_filter,
        pet_store=pet_store,
    )

    # sort
    tasks = scheduler.sort_by_time(tasks)

    if not tasks:
        st.info("No tasks found for the selected date / filters.")
    else:
        # conflict warnings
        conflicts = scheduler.check_conflicts(tasks, pet_store=pet_store)
        for w in conflicts:
            st.warning(w)

        # display
        rows = []
        for t in tasks:
            pet_names = ", ".join(
                pet_store[pid].name for pid in t.pet_ids if pid in pet_store
            ) or "—"
            rows.append({
                "Time":        t.scheduled_at.strftime("%H:%M"),
                "Title":       t.title,
                "Priority":    t.priority,
                "Pet(s)":      pet_names,
                "Recurrence":  t.recurrence or "—",
                "Reminder":    "✓" if t.reminder else "",
                "Done":        "✓" if t.completed else "",
                "Description": t.description or "—",
            })
        st.table(rows)

        # Mark complete buttons (one per task)
        st.markdown("**Mark tasks complete:**")
        for t in tasks:
            if not t.completed:
                if st.button(f"✅ {t.title} @ {t.scheduled_at.strftime('%H:%M')}", key=f"complete_{t.id}"):
                    next_task = t.mark_complete()
                    if next_task:
                        scheduler.add_task(next_task)
                        # sync pets
                        for pid in next_task.pet_ids:
                            if pid in pet_store:
                                pet_store[pid].add_task(next_task.id)
                        st.session_state.complete_msg = (
                            f"'{t.title}' marked complete. Next occurrence added."
                        )
                    else:
                        st.session_state.complete_msg = f"'{t.title}' marked complete."
                    st.rerun()
