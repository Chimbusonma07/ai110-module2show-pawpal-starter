"""PawPal+ Streamlit UI, wired to the classes in pawpal_system.py."""

from datetime import datetime, timedelta

import streamlit as st

from pawpal_system import Owner, Pet, Priority, Reminder, Task, TaskCategory

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption("A pet care planning assistant — add pets, give them tasks, and plan the day.")

# --- The session vault -------------------------------------------------------
# Streamlit reruns this whole script on every interaction. Guarding the
# assignment keeps one Owner alive across reruns instead of rebuilding it (and
# losing every pet) each time. Mutating it in place is enough — no reassignment.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", email="jordan@example.com")

owner = st.session_state.owner


def end_time(start: str, duration_minutes: int) -> str:
    """Return the "HH:MM" a task finishes, given its start and duration."""
    return (datetime.strptime(start, "%H:%M") + timedelta(minutes=duration_minutes)).strftime(
        "%H:%M"
    )


# --- Owner -------------------------------------------------------------------
with st.expander("Owner details", expanded=False):
    owner.name = st.text_input("Owner name", value=owner.name)
    owner.email = st.text_input("Email", value=owner.email)

st.divider()

# --- Add a pet ---------------------------------------------------------------
st.subheader("Add a Pet")

with st.form("add_pet", clear_on_submit=True):
    new_pet_name = st.text_input("Pet name", placeholder="Mochi")
    col1, col2, col3 = st.columns(3)
    with col1:
        new_species = st.selectbox("Species", ["dog", "cat", "other"])
    with col2:
        new_breed = st.text_input("Breed", placeholder="shorthair")
    with col3:
        new_age = st.number_input("Age", min_value=0, max_value=40, value=1)
    new_notes = st.text_area("Medical notes (one per line)", placeholder="hypothyroid")

    if st.form_submit_button("Add pet", type="primary"):
        if not new_pet_name.strip():
            st.warning("Give the pet a name first.")
        else:
            # Owner.add_pet() is the method that owns this data.
            owner.add_pet(
                Pet(
                    name=new_pet_name.strip(),
                    species=new_species,
                    breed=new_breed.strip(),
                    age=int(new_age),
                    medical_notes=[n.strip() for n in new_notes.splitlines() if n.strip()],
                )
            )
            st.rerun()

if owner.pets:
    st.table(
        [
            {
                "Pet": pet.name,
                "Species": pet.species,
                "Breed": pet.breed or "—",
                "Age": pet.age,
                "Tasks": len(pet.tasks),
            }
            for pet in owner.pets
        ]
    )
else:
    st.info("No pets yet. Add one above to get started.")

st.divider()

# --- Schedule a task ---------------------------------------------------------
st.subheader("Schedule a Task")

if not owner.pets:
    st.info("Add a pet first — tasks belong to a pet.")
else:
    with st.form("add_task", clear_on_submit=True):
        target_pet_name = st.selectbox("For which pet?", [pet.name for pet in owner.pets])
        task_title = st.text_input("Task title", placeholder="Morning walk")

        col1, col2, col3 = st.columns(3)
        with col1:
            category = st.selectbox(
                "Category", list(TaskCategory), format_func=lambda c: c.value
            )
        with col2:
            duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
        with col3:
            priority = st.selectbox(
                "Priority", list(Priority), index=2, format_func=lambda p: p.value
            )

        col4, col5 = st.columns(2)
        with col4:
            frequency = st.selectbox(
                "Frequency",
                ["daily", "weekly", "weekdays", "weekends", "one-off (today only)"],
            )
        with col5:
            remind_at = st.text_input("Remind at (HH:MM, optional)", placeholder="08:00")

        if st.form_submit_button("Add task", type="primary"):
            if not task_title.strip():
                st.warning("Give the task a title first.")
            else:
                one_off = frequency.startswith("one-off")
                task = Task(
                    name=task_title.strip(),
                    category=category,
                    duration_minutes=int(duration),
                    priority=priority,
                    is_recurring=not one_off,
                    recurrence="" if one_off else frequency,
                )
                if remind_at.strip():
                    task.add_reminder(
                        Reminder(f"{task.name} for {target_pet_name}", remind_at.strip())
                    )
                # Pet.add_task() stamps task.pet_name and stores it on the pet.
                owner.get_pet(target_pet_name).add_task(task)
                st.rerun()

    all_tasks = owner.get_all_tasks()
    if all_tasks:
        st.table(
            [
                {
                    "Task": task.name,
                    "Pet": task.pet_name,
                    "Category": task.category.value,
                    "Min": task.duration_minutes,
                    "Priority": task.priority.value,
                    "Repeats": task.recurrence or "one-off",
                    "Due from": task.due_date or "now",
                    "Done": "yes" if task.is_complete else "no",
                }
                for task in all_tasks
            ]
        )
    else:
        st.info("No tasks yet. Add one above.")

st.divider()

# --- Build the schedule ------------------------------------------------------
st.subheader("Build Schedule")

col1, col2, col3 = st.columns(3)
with col1:
    plan_date = st.date_input("Date", value=datetime.now())
with col2:
    start_time = st.time_input("Start time", value=datetime.strptime("07:30", "%H:%M").time())
with col3:
    available = st.number_input("Minutes free", min_value=5, max_value=960, value=90, step=15)

if st.button("Generate schedule", type="primary", disabled=not owner.get_all_tasks()):
    # Owner.plan_day() flattens tasks across pets, then Schedule packs them.
    st.session_state.plan = owner.plan_day(
        plan_date.strftime("%Y-%m-%d"), start_time.strftime("%H:%M"), int(available)
    )

if "plan" in st.session_state:
    plan = st.session_state.plan

    st.markdown("### Today's Schedule")
    if plan.planned_tasks:
        st.table(
            [
                {
                    "Time": f"{t.scheduled_time}–{end_time(t.scheduled_time, t.duration_minutes)}",
                    "Task": t.name,
                    "Pet": t.pet_name,
                    "Min": t.duration_minutes,
                    "Category": t.category.value,
                }
                for t in plan.planned_tasks
            ]
        )
        col1, col2, col3 = st.columns(3)
        col1.metric("Tasks planned", len(plan.planned_tasks))
        col2.metric("Minutes used", plan.total_planned_minutes())
        col3.metric("Minutes free", plan.remaining_minutes())
    else:
        st.warning("Nothing fits in the time available.")

    if plan.skipped_tasks:
        st.markdown("### Didn't fit")
        for task in plan.skipped_tasks:
            reason = (
                "already done"
                if task.is_complete
                else f"needs {task.duration_minutes} min, {plan.remaining_minutes()} min left"
            )
            st.write(f"- **{task.label()}** — {reason}")

    # Tasks filtered out by is_due_today() never reach the scheduler, so say so
    # explicitly — otherwise they just silently vanish from the page.
    not_due = [t for t in owner.get_all_tasks() if not t.is_due_today(plan.date)]
    if not_due:
        st.markdown("### Not due today")
        for task in not_due:
            when = (
                f"next due {task.due_date}"
                if task.due_date > plan.date
                else f"runs {task.recurrence or 'one-off'}"
            )
            st.write(f"- **{task.label()}** — {when}")

    messages = plan.send_reminders()
    if messages:
        st.markdown("### Reminders")
        for message in messages:
            st.info(message)

    with st.expander("Why this plan?"):
        st.code(plan.explain_plan(), language=None)

    if plan.planned_tasks:
        st.markdown("### Mark tasks done")
        for index, task in enumerate(plan.planned_tasks):
            if st.checkbox(task.label(), value=task.is_complete, key=f"done_{index}"):
                if not task.is_complete:
                    # Drops out of the next plan; a daily/weekly task also
                    # gets a fresh copy queued for its next occurrence.
                    next_task = owner.get_pet(task.pet_name).complete_task(task, plan.date)
                    if next_task is not None:
                        st.session_state.flash = (
                            f"Next {next_task.label()} queued for {next_task.due_date}."
                        )
                    st.rerun()

    # Shown once, on the rerun after a recurring task was completed.
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))
