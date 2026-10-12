"""PawPal+ terminal demo.

Builds a small household — one owner, two pets, six care tasks — and prints
today's schedule. Run it with:

    python main.py
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pawpal_system import (
    Owner,
    Pet,
    Priority,
    Reminder,
    Schedule,
    Task,
    TaskCategory,
)

# The owner's morning window: when they start and how long they have.
START_TIME = "07:30"
AVAILABLE_MINUTES = 90
LINE_WIDTH = 68


def end_time(start: str, duration_minutes: int) -> str:
    """Return the "HH:MM" a task finishes, given its start and duration."""
    base = datetime.strptime(start, "%H:%M")
    return (base + timedelta(minutes=duration_minutes)).strftime("%H:%M")


def build_household() -> Owner:
    """Create the owner, their pets, and the tasks each pet needs."""
    jordan = Owner(
        name="Jordan Avery",
        email="jordan@example.com",
        phone_number="555-0142",
        address="18 Maple Street",
    )

    mochi = jordan.add_pet(
        Pet(
            name="Mochi",
            species="cat",
            breed="shorthair",
            age=3,
            medical_notes=["hypothyroid — pill every morning"],
        )
    )
    rex = jordan.add_pet(Pet(name="Rex", species="dog", breed="corgi", age=5))

    mochi.add_task(
        Task("Morning feed", TaskCategory.FEEDING, 10, Priority.HIGH, True, "daily")
    )
    pill = mochi.add_task(
        Task("Thyroid pill", TaskCategory.MEDICATION, 5, Priority.MEDIUM, True, "daily")
    )
    pill.add_reminder(Reminder("Give Mochi her thyroid pill", "08:00"))
    mochi.add_task(
        Task("Litter box", TaskCategory.GROOMING, 10, Priority.MEDIUM, True, "daily")
    )

    rex.add_task(Task("Morning walk", TaskCategory.WALK, 30, Priority.HIGH, True, "daily"))
    rex.add_task(Task("Evening walk", TaskCategory.WALK, 45, Priority.MEDIUM, True, "daily"))
    rex.add_task(
        Task("Nail trim", TaskCategory.GROOMING, 20, Priority.LOW, True, "weekends")
    )

    return jordan


def print_header(owner: Owner, date: str) -> None:
    """Print who and what this plan is for."""
    pretty_date = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %d %B %Y")
    print("=" * LINE_WIDTH)
    print("PawPal+ — Today's Schedule".center(LINE_WIDTH))
    print("=" * LINE_WIDTH)
    print(f"Owner : {owner.name} ({owner.email})")
    print(f"Date  : {pretty_date}")
    for pet in owner.pets:
        print(f"Pet   : {pet.name} — {pet.breed} {pet.species}, age {pet.age}")
        for note in pet.medical_notes:
            print(f"        note: {note}")
    print(f"Window: {START_TIME} onward, {AVAILABLE_MINUTES} minutes free")


def print_schedule(schedule: Schedule) -> None:
    """Print the planned tasks as a time-ordered table."""
    print("\nTODAY'S SCHEDULE")
    print("-" * LINE_WIDTH)
    if not schedule.planned_tasks:
        print("  Nothing fits in the time available today.")
        return

    print(f"  {'TIME':<15}{'TASK':<20}{'PET':<8}{'MINS':>5}  CATEGORY")
    for task in schedule.planned_tasks:
        window = f"{task.scheduled_time}-{end_time(task.scheduled_time, task.duration_minutes)}"
        print(
            f"  {window:<15}{task.name:<20}{task.pet_name:<8}"
            f"{task.duration_minutes:>5}  {task.category.value}"
        )
    print("-" * LINE_WIDTH)
    print(
        f"  {len(schedule.planned_tasks)} tasks, "
        f"{schedule.total_planned_minutes()} min planned, "
        f"{schedule.remaining_minutes()} min free"
    )


def print_leftovers(owner: Owner, schedule: Schedule, date: str) -> None:
    """Print what did not make the cut, and what simply is not due today."""
    if schedule.skipped_tasks:
        print("\nDIDN'T FIT TODAY")
        print("-" * LINE_WIDTH)
        for task in schedule.skipped_tasks:
            print(
                f"  {task.label()} — needs {task.duration_minutes} min, "
                f"only {schedule.remaining_minutes()} min left"
            )

    not_due = [task for task in owner.get_all_tasks() if not task.is_due_today(date)]
    if not_due:
        print("\nNOT DUE TODAY")
        print("-" * LINE_WIDTH)
        for task in not_due:
            print(f"  {task.label()} — runs {task.recurrence}")


def print_reminders(schedule: Schedule) -> None:
    """Print the reminders that fire for today's planned tasks."""
    messages = schedule.send_reminders()
    if not messages:
        return
    print("\nREMINDERS")
    print("-" * LINE_WIDTH)
    for message in messages:
        print(f"  {message}")


def main() -> None:
    jordan = build_household()
    today = datetime.now().strftime("%Y-%m-%d")

    # The owner flattens tasks across pets, then the schedule fits what it can.
    schedule = jordan.plan_day(today, START_TIME, AVAILABLE_MINUTES)

    print_header(jordan, today)
    print_schedule(schedule)
    print_leftovers(jordan, schedule, today)
    print_reminders(schedule)

    print("\nWHY THIS PLAN")
    print("-" * LINE_WIDTH)
    print(schedule.explain_plan())
    print()


if __name__ == "__main__":
    main()
