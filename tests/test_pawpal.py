"""Tests for the PawPal+ core classes.

Run from the project root with:

    pytest

Test plan — the edge cases that matter most for a pet scheduler
----------------------------------------------------------------
Sorting (Scheduler.sort_by_time)
  * Scrambled input comes back in chronological order.
  * Tasks with no time go last, not first (a blank string sorts before "07:00").
  * Tasks sharing a time keep their input order (stable sort).
  * An empty list sorts to an empty list; the input list is never mutated.
  * An unpadded "7:30" sorts before "10:00", not after it as plain text would.

Recurrence (Task.mark_complete / next_occurrence, Pet.complete_task)
  * Completing a daily task creates a new task due the following day.
  * Weekly tasks come back seven days later, on the same weekday only.
  * Date arithmetic survives month, year and leap-day boundaries.
  * Early and late completions both land on a sensible next due date.
  * The new task is a separate object: fresh reminders, original untouched.
  * Only daily/weekly roll forward; completing twice never spawns two copies.
  * End to end: the next occurrence is planned tomorrow, not today.
  * A malformed date raises without marking the task done, so a retry can
    still create the next occurrence.

Conflict detection (Scheduler.detect_conflicts)
  * Duplicate start times are flagged, for the same pet or different pets.
  * Three tasks in one slot give one warning naming all three.
  * No duplicates means no warnings; overlapping durations are not flagged.
  * Done, untimed and not-due tasks are ignored; bad times warn, never raise.
  * A generated plan never conflicts with itself.
"""

from datetime import datetime, timedelta

import pytest

from pawpal_system import Owner, Pet, Reminder, Scheduler, Task, TaskCategory

DAY = "2026-10-12"  # a Monday


def _timed(name: str, pet_name: str, clock: str, minutes: int = 10) -> Task:
    """Build a daily task for the given pet at the given time."""
    return Task(name, TaskCategory.WALK, minutes, is_recurring=True, recurrence="daily",
                scheduled_time=clock, pet_name=pet_name)


def _daily(name: str = "Feed", recurrence: str = "daily", **kwargs) -> Task:
    """Build a recurring (daily by default) feeding task."""
    return Task(name, TaskCategory.FEEDING, 10, is_recurring=True, recurrence=recurrence,
                **kwargs)


def _times(tasks: list[Task]) -> list[str]:
    return [task.scheduled_time for task in tasks]


# --- Basics ------------------------------------------------------------------


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


# --- Sorting correctness -----------------------------------------------------


def test_sort_by_time_returns_chronological_order():
    """Tasks added out of order come back earliest first."""
    schedule = Scheduler(DAY, "07:00", 60)
    for name, clock in [("Litter", "12:00"), ("Feed", "07:30"), ("Walk", "18:00"),
                        ("Pill", "08:00"), ("Trim", "10:00"), ("Run", "07:00")]:
        schedule.add_task(_timed(name, "Rex", clock))

    ordered = schedule.sort_by_time()

    assert _times(ordered) == ["07:00", "07:30", "08:00", "10:00", "12:00", "18:00"]


def test_sort_by_time_puts_untimed_tasks_last():
    """A blank time would sort first as text; the key pushes it to the end."""
    tasks = [_timed("Later", "Rex", ""), _timed("Feed", "Rex", "09:00"),
             _timed("Walk", "Rex", "06:15")]

    ordered = Scheduler(DAY, "07:00", 60).sort_by_time(tasks)

    assert _times(ordered) == ["06:15", "09:00", ""]


def test_sort_by_time_keeps_input_order_for_ties():
    """Tasks sharing a time stay in the order they were given (stable sort)."""
    first, second, third = (_timed(n, "Rex", "08:00") for n in ("A", "B", "C"))

    ordered = Scheduler(DAY, "07:00", 60).sort_by_time([first, second, third])

    assert [task.name for task in ordered] == ["A", "B", "C"]


def test_sort_by_time_handles_empty_list_and_does_not_mutate_input():
    """Sorting returns a new list and leaves the caller's list alone."""
    schedule = Scheduler(DAY, "07:00", 60)
    assert schedule.sort_by_time([]) == []
    assert schedule.sort_by_time() == []  # no candidate tasks yet

    tasks = [_timed("Late", "Rex", "18:00"), _timed("Early", "Rex", "06:00")]
    ordered = schedule.sort_by_time(tasks)

    assert ordered is not tasks
    assert _times(tasks) == ["18:00", "06:00"]


def test_sort_by_time_handles_unpadded_times():
    """An unpadded hour should still sort by clock time."""
    tasks = [_timed("Late", "Rex", "10:00"), _timed("Early", "Rex", "7:30")]

    ordered = Scheduler(DAY, "07:00", 60).sort_by_time(tasks)

    assert [task.name for task in ordered] == ["Early", "Late"]


# --- Recurrence logic --------------------------------------------------------


def test_completing_daily_task_queues_tomorrow():
    """A daily task completed on Monday spawns a fresh copy due Tuesday."""
    pet = Pet(name="Mochi", species="cat")
    feed = pet.add_task(_daily("Morning feed"))
    feed.add_reminder(Reminder("Feed Mochi", "07:30", sent=True))

    next_feed = pet.complete_task(feed, DAY)

    assert feed.is_complete is True
    assert next_feed in pet.tasks and len(pet.tasks) == 2
    assert next_feed is not feed
    assert next_feed.is_complete is False
    assert next_feed.due_date == "2026-10-13"
    assert next_feed.pet_name == "Mochi"
    assert next_feed.reminders[0].sent is False
    assert next_feed.reminders[0] is not feed.reminders[0]
    assert not next_feed.is_due_today(DAY)
    assert next_feed.is_due_today("2026-10-13")


def test_completing_weekly_task_queues_next_week():
    """A weekly task comes back seven days later, on the same weekday only."""
    pet = Pet(name="Rex", species="dog")
    bath = pet.add_task(
        Task("Bath", TaskCategory.GROOMING, 30, is_recurring=True, recurrence="weekly")
    )

    next_bath = pet.complete_task(bath, DAY)

    assert next_bath.due_date == "2026-10-19"
    assert not next_bath.is_due_today("2026-10-18")
    assert next_bath.is_due_today("2026-10-19")
    assert not next_bath.is_due_today("2026-10-20")
    assert next_bath.is_due_today("2026-10-26")


@pytest.mark.parametrize(
    ("completed_on", "expected"),
    [
        ("2026-10-31", "2026-11-01"),  # end of month
        ("2026-12-31", "2027-01-01"),  # end of year
        ("2028-02-28", "2028-02-29"),  # leap year
        ("2027-02-28", "2027-03-01"),  # non-leap year
    ],
)
def test_daily_next_occurrence_crosses_calendar_boundaries(completed_on, expected):
    """Date arithmetic rolls over months, years and leap days correctly."""
    assert _daily().mark_complete(completed_on).due_date == expected


def test_next_occurrence_counts_from_later_of_completion_and_due_date():
    """Early completion steps from the due date; late completion from today."""
    early = _daily(due_date="2026-10-15")
    assert early.mark_complete(DAY).due_date == "2026-10-16"

    late = _daily(due_date="2026-10-01")
    assert late.mark_complete(DAY).due_date == "2026-10-13"


def test_mark_complete_defaults_to_today():
    """With no date given, tomorrow's copy is due the day after today."""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    assert _daily().mark_complete().due_date == tomorrow


def test_next_occurrence_does_not_change_original():
    """Building the next occurrence leaves the source task as it was."""
    feed = _daily(scheduled_time="07:30", due_date=DAY)

    copy = feed.next_occurrence(DAY)

    assert feed.due_date == DAY and feed.is_complete is False
    assert copy.scheduled_time == "07:30"  # preferred time carries over


def test_recurrence_name_is_case_insensitive():
    """'Daily' and ' WEEKLY ' roll forward just like the lowercase forms."""
    assert _daily(recurrence="Daily").mark_complete(DAY).due_date == "2026-10-13"
    weekly = Task("Bath", TaskCategory.GROOMING, 30, is_recurring=True, recurrence=" WEEKLY ")
    assert weekly.mark_complete(DAY).due_date == "2026-10-19"


def test_non_rolling_tasks_do_not_spawn_copies():
    """One-off and weekdays tasks, and repeat completions, create nothing new."""
    pet = Pet(name="Rex", species="dog")
    vet = pet.add_task(Task("Vet visit", TaskCategory.VET, 60))
    walk = pet.add_task(
        Task("Walk", TaskCategory.WALK, 30, is_recurring=True, recurrence="weekdays")
    )
    feed = pet.add_task(_daily())

    assert pet.complete_task(vet, DAY) is None
    assert pet.complete_task(walk, DAY) is None
    assert pet.complete_task(feed, DAY) is not None
    assert pet.complete_task(feed, DAY) is None  # already done
    assert len(pet.tasks) == 4


def test_completed_daily_task_is_planned_tomorrow_not_today():
    """End to end: today's plan drops the done task; tomorrow's plan has the copy."""
    owner = Owner(name="Jordan")
    mochi = owner.add_pet(Pet(name="Mochi", species="cat"))
    feed = mochi.add_task(_daily())
    mochi.complete_task(feed, DAY)

    today = owner.plan_day(DAY, "07:00", 60)
    tomorrow = owner.plan_day("2026-10-13", "07:00", 60)

    assert today.planned_tasks == []
    assert len(tomorrow.planned_tasks) == 1
    assert tomorrow.planned_tasks[0] is not feed


def test_bad_completion_date_does_not_lose_next_occurrence():
    """A malformed date should fail without leaving the task half-completed."""
    feed = _daily()

    with pytest.raises(ValueError):
        feed.mark_complete("10/12/2026")

    # Otherwise a retry returns None and tomorrow's copy is never created.
    assert feed.is_complete is False


# --- Conflict detection ------------------------------------------------------


def test_detect_conflicts_flags_same_and_different_pets():
    """Shared start times are reported, labelled by whether the pets match."""
    schedule = Scheduler(DAY, "07:00", 60)
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


def test_detect_conflicts_reports_three_way_clash_once():
    """Three tasks in one slot give a single warning that names all three."""
    tasks = [_timed("Feed", "Mochi", "08:00"), _timed("Walk", "Rex", "08:00"),
             _timed("Pill", "Mochi", "08:00")]

    warnings = Scheduler(DAY, "07:00", 60).detect_conflicts(tasks)

    assert len(warnings) == 1
    assert warnings[0].startswith("WARNING: 3 tasks at 08:00")
    for name in ("Feed for Mochi", "Walk for Rex", "Pill for Mochi"):
        assert name in warnings[0]


def test_detect_conflicts_returns_empty_list_when_times_are_unique():
    """Distinct start times — including overlapping durations — are not flagged."""
    tasks = [
        _timed("Walk", "Rex", "07:00", minutes=30),
        _timed("Feed", "Rex", "07:15"),  # overlaps the walk, but starts later
        _timed("Pill", "Mochi", "07:30"),
    ]

    assert Scheduler(DAY, "07:00", 60).detect_conflicts(tasks) == []


def test_detect_conflicts_ignores_done_untimed_and_not_due_tasks():
    """Only live tasks on this date can clash; bad times warn instead of raising."""
    schedule = Scheduler(DAY, "07:00", 60)
    done = _timed("Feed", "Mochi", "07:30")
    done.mark_complete(DAY)
    tomorrow = _timed("Feed", "Mochi", "07:30")
    tomorrow.due_date = "2026-10-13"
    untimed = [_timed("Walk", "Rex", ""), _timed("Run", "Rex", "")]
    for task in [done, tomorrow, *untimed]:
        schedule.add_task(task)
    assert schedule.detect_conflicts() == []

    schedule.add_task(_timed("Bath", "Rex", "noon"))
    warnings = schedule.detect_conflicts()
    assert len(warnings) == 1 and "bad time 'noon'" in warnings[0]


def test_generated_plan_has_no_conflicts():
    """Planning assigns back-to-back slots, so clashing preferences disappear."""
    owner = Owner(name="Jordan")
    rex = owner.add_pet(Pet(name="Rex", species="dog"))
    for name in ("Feed", "Walk", "Brush"):
        rex.add_task(_timed(name, "Rex", "08:00"))

    schedule = owner.plan_day(DAY, "07:00", 60)

    assert schedule.detect_conflicts(schedule.planned_tasks) == []
    assert _times(schedule.planned_tasks) == ["07:00", "07:10", "07:20"]
