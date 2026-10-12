"""Tests for the PawPal+ core classes.

Run from the project root with:

    pytest
"""

from pawpal_system import Pet, Reminder, Scheduler, Task, TaskCategory


def test_mark_complete_changes_task_status():
    """A task starts incomplete and mark_complete() flips it."""
    task = Task("Morning feed", TaskCategory.FEEDING, 10)
    assert task.is_complete is False

    task.mark_complete()

    assert task.is_complete is True


def test_adding_task_increases_pet_task_count():
    """Each add_task() call grows the pet's task list by one."""
    pet = Pet(name="Mochi", species="cat")
    assert len(pet.tasks) == 0

    pet.add_task(Task("Morning feed", TaskCategory.FEEDING, 10))
    assert len(pet.tasks) == 1

    before = len(pet.tasks)
    pet.add_task(Task("Thyroid pill", TaskCategory.MEDICATION, 5))
    assert len(pet.tasks) == before + 1


def test_completing_daily_task_queues_tomorrow():
    """A daily task completed on Monday spawns a fresh copy due Tuesday."""
    pet = Pet(name="Mochi", species="cat")
    feed = pet.add_task(
        Task("Morning feed", TaskCategory.FEEDING, 10, is_recurring=True, recurrence="daily")
    )
    feed.add_reminder(Reminder("Feed Mochi", "07:30", sent=True))

    next_feed = pet.complete_task(feed, "2026-10-12")

    assert feed.is_complete is True
    assert next_feed in pet.tasks and len(pet.tasks) == 2
    assert next_feed is not feed
    assert next_feed.is_complete is False
    assert next_feed.due_date == "2026-10-13"
    assert next_feed.pet_name == "Mochi"
    assert next_feed.reminders[0].sent is False
    assert next_feed.reminders[0] is not feed.reminders[0]
    assert not next_feed.is_due_today("2026-10-12")
    assert next_feed.is_due_today("2026-10-13")


def test_completing_weekly_task_queues_next_week():
    """A weekly task comes back seven days later, on the same weekday only."""
    pet = Pet(name="Rex", species="dog")
    bath = pet.add_task(
        Task("Bath", TaskCategory.GROOMING, 30, is_recurring=True, recurrence="weekly")
    )

    next_bath = pet.complete_task(bath, "2026-10-12")

    assert next_bath.due_date == "2026-10-19"
    assert not next_bath.is_due_today("2026-10-18")
    assert next_bath.is_due_today("2026-10-19")
    assert not next_bath.is_due_today("2026-10-20")
    assert next_bath.is_due_today("2026-10-26")


def test_non_rolling_tasks_do_not_spawn_copies():
    """One-off and weekdays tasks, and repeat completions, create nothing new."""
    pet = Pet(name="Rex", species="dog")
    vet = pet.add_task(Task("Vet visit", TaskCategory.VET, 60))
    walk = pet.add_task(
        Task("Walk", TaskCategory.WALK, 30, is_recurring=True, recurrence="weekdays")
    )
    feed = pet.add_task(
        Task("Feed", TaskCategory.FEEDING, 10, is_recurring=True, recurrence="daily")
    )

    assert pet.complete_task(vet, "2026-10-12") is None
    assert pet.complete_task(walk, "2026-10-12") is None
    assert pet.complete_task(feed, "2026-10-12") is not None
    assert pet.complete_task(feed, "2026-10-12") is None  # already done
    assert len(pet.tasks) == 4


def _timed(name: str, pet_name: str, clock: str) -> Task:
    """Build a daily task for the given pet at the given time."""
    return Task(name, TaskCategory.WALK, 10, is_recurring=True, recurrence="daily",
                scheduled_time=clock, pet_name=pet_name)


def test_detect_conflicts_flags_same_and_different_pets():
    """Shared start times are reported, labelled by whether the pets match."""
    schedule = Scheduler("2026-10-12", "07:00", 60)
    for task in [
        _timed("Feed", "Mochi", "07:30"),
        _timed("Brush", "Mochi", "7:30"),  # unpadded still counts as 07:30
        _timed("Pill", "Mochi", "08:00"),
        _timed("Walk", "Rex", "08:00"),
        _timed("Play", "Rex", "09:00"),
    ]:
        schedule.add_task(task)

    warnings = schedule.detect_conflicts()

    assert len(warnings) == 2
    assert "07:30, same pet (Mochi)" in warnings[0]
    assert "08:00, different pets" in warnings[1]


def test_detect_conflicts_ignores_done_untimed_and_not_due_tasks():
    """Only live tasks on this date can clash; bad times warn instead of raising."""
    schedule = Scheduler("2026-10-12", "07:00", 60)
    done = _timed("Feed", "Mochi", "07:30")
    done.mark_complete("2026-10-12")
    tomorrow = _timed("Feed", "Mochi", "07:30")
    tomorrow.due_date = "2026-10-13"
    for task in [done, tomorrow, _timed("Walk", "Rex", ""), _timed("Walk", "Rex", "")]:
        schedule.add_task(task)
    assert schedule.detect_conflicts() == []

    schedule.add_task(_timed("Bath", "Rex", "noon"))
    warnings = schedule.detect_conflicts()
    assert len(warnings) == 1 and "bad time 'noon'" in warnings[0]
