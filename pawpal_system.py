"""PawPal+ — pet care planning assistant.

Implements the design in diagrams/uml_draft.mmd.

Ownership runs User -> Pet -> Task -> Reminder. Schedule plans one day: the owner
flattens tasks across pets, hands them to a Schedule as candidates, and the
Schedule fits what it can into the available time and explains the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum

_TIME_FORMAT = "%H:%M"
_DATE_FORMAT = "%Y-%m-%d"
_EPOCH = datetime(2000, 1, 1)


def _add_minutes(clock: str, minutes: int) -> str:
    """Return an "HH:MM" string shifted by the given number of minutes."""
    base = datetime.combine(_EPOCH.date(), datetime.strptime(clock, _TIME_FORMAT).time())
    return (base + timedelta(minutes=minutes)).strftime(_TIME_FORMAT)


def _weekday_of(date: str) -> str:
    """Return the lowercase three-letter weekday for a "YYYY-MM-DD" string."""
    try:
        return datetime.strptime(date, _DATE_FORMAT).strftime("%a").lower()
    except ValueError as exc:
        raise ValueError(f"date must look like YYYY-MM-DD, got {date!r}") from exc


def _add_days(date: str, days: int) -> str:
    """Return a "YYYY-MM-DD" string shifted by the given number of days."""
    _weekday_of(date)  # validates the format with a friendly error
    return (datetime.strptime(date, _DATE_FORMAT) + timedelta(days=days)).strftime(_DATE_FORMAT)


class Priority(Enum):
    """How urgent a task is."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCategory(Enum):
    """What kind of care a task provides."""

    WALK = "walk"
    FEEDING = "feeding"
    MEDICATION = "medication"
    GROOMING = "grooming"
    VET = "vet"
    ENRICHMENT = "enrichment"


# Priority is the main sort key; health categories break ties within a level but
# never outrank a higher priority. HIGH walk (30) still beats MEDIUM meds (25).
_PRIORITY_WEIGHTS = {Priority.LOW: 1, Priority.MEDIUM: 2, Priority.HIGH: 3}
_HEALTH_CATEGORIES = {TaskCategory.MEDICATION, TaskCategory.VET}

# Recurrence vocabulary understood by Task.is_due_today().
_RECURRENCE_ALIASES = {
    "weekdays": {"mon", "tue", "wed", "thu", "fri"},
    "weekends": {"sat", "sun"},
}

# Recurrences that roll forward into a fresh task when completed, and how far.
_NEXT_OCCURRENCE_DAYS = {"daily": 1, "weekly": 7}


@dataclass
class Reminder:
    """A nudge attached to a task."""

    message: str
    remind_at: str
    recurring: bool = False
    sent: bool = False

    def send(self) -> str:
        """Deliver the reminder and return the text that was sent."""
        self.sent = True
        return f"[{self.remind_at}] {self.message}"

    def snooze(self, minutes: int) -> None:
        """Push remind_at back by the given number of minutes."""
        self.remind_at = _add_minutes(self.remind_at, minutes)
        self.sent = False


@dataclass
class Task:
    """A single unit of pet care work.

    `name` is the description, `scheduled_time` the time, `is_recurring` plus
    `recurrence` the frequency, and `is_complete` the completion status.
    `due_date` ("YYYY-MM-DD") is the first day the task can be planned; blank
    means it is available right away.
    """

    name: str
    category: TaskCategory
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    is_recurring: bool = False
    recurrence: str = ""
    scheduled_time: str = ""
    is_complete: bool = False
    reminders: list[Reminder] = field(default_factory=list)
    # Stamped by Pet.add_task() so a task stays self-describing once the
    # scheduler has flattened tasks from several pets into one list.
    pet_name: str = ""
    due_date: str = ""

    def add_reminder(self, reminder: Reminder) -> Reminder:
        """Attach a reminder to this task and return it."""
        self.reminders.append(reminder)
        return reminder

    def priority_score(self) -> int:
        """Return a numeric weight the scheduler can sort on."""
        score = _PRIORITY_WEIGHTS[self.priority] * 10
        if self.category in _HEALTH_CATEGORIES:
            score += 5
        return score

    def fits_in(self, minutes_left: int) -> bool:
        """Return True if this task can finish within the time remaining."""
        return self.duration_minutes <= minutes_left

    def is_due_today(self, date: str) -> bool:
        """Return True if the recurrence rule puts this task on the given date.

        Recurring tasks accept "daily" (or blank), "weekly" (the weekday of
        due_date, or any day if there is none), "weekdays", "weekends", or a
        comma-separated list like "mon,wed,fri". A one-off task is due only on
        the date it names, or on any date if it names none. Nothing is due
        before its due_date.
        """
        if self.due_date and date < self.due_date:
            return False
        rule = self.recurrence.strip().lower()
        if not self.is_recurring:
            return rule in ("", date.strip().lower())
        if rule in ("", "daily"):
            return True
        if rule == "weekly":
            return not self.due_date or _weekday_of(date) == _weekday_of(self.due_date)
        if rule in _RECURRENCE_ALIASES:
            return _weekday_of(date) in _RECURRENCE_ALIASES[rule]
        days = {part.strip()[:3] for part in rule.split(",") if part.strip()}
        return _weekday_of(date) in days

    def mark_complete(self, on_date: str = "") -> Task | None:
        """Mark this task done and return its next occurrence, if it has one.

        A "daily" or "weekly" task yields a fresh, incomplete copy due one day
        or one week after `on_date` (default today), or after its own due_date
        if that is later. Other tasks, or one already done, return None. The
        caller owns storing the new task — Pet.complete_task() does that.

        Args:
            on_date: The "YYYY-MM-DD" the task was finished. Blank means today.

        Returns:
            The next-occurrence Task (not yet attached to any pet), or None if
            the task does not roll forward or was already complete. Returning
            None on a repeat call keeps a double-click from queueing two copies.
        """
        if self.is_complete:
            return None
        self.is_complete = True
        return self.next_occurrence(on_date)

    def next_occurrence(self, on_date: str = "") -> Task | None:
        """Return a new task for the next daily/weekly occurrence, else None.

        The next due date is counted from whichever is later: the day the task
        was completed or its own due_date. Counting from the later one means a
        task finished early (before it was due) still moves a full step ahead,
        and a late task never comes back due in the past.

        The copy is made with dataclasses.replace(), so it keeps the name,
        pet, duration, priority, recurrence and preferred time. Its reminders
        are copied too, reset to unsent, so the two tasks never share them.
        This method does not change `self`.

        Args:
            on_date: The "YYYY-MM-DD" the task was finished. Blank means today.

        Returns:
            A new, incomplete Task whose due_date is one step (1 day for
            "daily", 7 for "weekly") after the base date, or None for any other
            recurrence or a one-off task.

        Example:
            A daily task due "2026-10-12" and completed that day comes back
            due "2026-10-13"; a weekly one comes back due "2026-10-19".
        """
        step = _NEXT_OCCURRENCE_DAYS.get(self.recurrence.strip().lower())
        if not self.is_recurring or step is None:
            return None
        completed_on = on_date or datetime.now().strftime(_DATE_FORMAT)
        base = max(completed_on, self.due_date)
        return replace(
            self,
            is_complete=False,
            due_date=_add_days(base, step),
            reminders=[replace(reminder, sent=False) for reminder in self.reminders],
        )

    def reset(self) -> None:
        """Clear completion and timing, ready for the next day."""
        self.is_complete = False
        self.scheduled_time = ""
        for reminder in self.reminders:
            reminder.sent = False

    def label(self) -> str:
        """Return a display name that includes the pet, when known."""
        return f"{self.name} for {self.pet_name}" if self.pet_name else self.name


@dataclass
class Pet:
    """An animal in the owner's care, along with the tasks it needs."""

    name: str
    species: str
    breed: str = ""
    age: int = 0
    medical_notes: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> Task:
        """Add a care task for this pet and return it."""
        task.pet_name = self.name
        self.tasks.append(task)
        return task

    def remove_task(self, name: str) -> bool:
        """Remove the named task. Return True if one was removed."""
        for index, task in enumerate(self.tasks):
            if task.name == name:
                del self.tasks[index]
                return True
        return False

    def complete_task(self, task: Task, on_date: str = "") -> Task | None:
        """Mark one of this pet's tasks done and store its next occurrence.

        Task.mark_complete() can build the next occurrence but cannot store
        it, because a Task does not know its Pet. This method does both, so
        callers should use it rather than calling task.mark_complete() alone.
        The finished task stays in `self.tasks` as a record of the work.

        Args:
            task: One of this pet's tasks.
            on_date: The "YYYY-MM-DD" the task was finished. Blank means today.

        Returns:
            The newly created task for a daily/weekly task (already added to
            this pet), else None.
        """
        next_task = task.mark_complete(on_date)
        if next_task is not None:
            self.add_task(next_task)
        return next_task

    def get_tasks_by_priority(self, level: Priority) -> list[Task]:
        """Return this pet's tasks at the given priority level."""
        return [task for task in self.tasks if task.priority is level]

    def create_daily_schedule(self, schedule: Schedule) -> Schedule:
        """Feed this pet's due tasks into the schedule and return it."""
        for task in self.tasks:
            if task.is_due_today(schedule.date) and not task.is_complete:
                schedule.add_task(task)
        return schedule


@dataclass
class Schedule:
    """One day's plan: what fits in the owner's available time, and what doesn't."""

    date: str
    start_time: str
    available_minutes: int
    candidate_tasks: list[Task] = field(default_factory=list)
    planned_tasks: list[Task] = field(default_factory=list)
    skipped_tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Offer a task to this schedule as a candidate for planning."""
        if task not in self.candidate_tasks:
            self.candidate_tasks.append(task)

    def schedule_tasks(self) -> list[Task]:
        """Fit candidate tasks into the available time by priority.

        Highest score first; among equals the shorter task wins, which fits more
        care into the same day at the cost of pushing long tasks later.
        """
        self.planned_tasks = []
        self.skipped_tasks = []
        remaining = self.available_minutes
        ordered = sorted(
            self.candidate_tasks,
            key=lambda task: (-task.priority_score(), task.duration_minutes, task.name),
        )
        for task in ordered:
            if task.is_complete:
                self.skipped_tasks.append(task)
            elif task.fits_in(remaining):
                self.planned_tasks.append(task)
                remaining -= task.duration_minutes
            else:
                self.skipped_tasks.append(task)
        return self.planned_tasks

    def generate_daily_plan(self) -> list[Task]:
        """Build the ordered plan for the day and return the planned tasks."""
        self.schedule_tasks()
        clock = self.start_time
        for task in self.planned_tasks:
            task.scheduled_time = clock
            clock = _add_minutes(clock, task.duration_minutes)
        return self.planned_tasks

    def sort_by_time(self, tasks: list[Task] | None = None) -> list[Task]:
        """Return tasks ordered by scheduled_time, earliest first.

        The sort key is a lambda that returns a pair:
        `(task.scheduled_time == "", task.scheduled_time)`. Python compares the
        pairs item by item, so the first item (False before True) puts every
        timed task ahead of the untimed ones, and the second orders the timed
        tasks by clock. Zero-padded "HH:MM" strings sort correctly as plain
        text ("07:05" < "09:00" < "14:30"), so no time parsing is needed.
        An unpadded time such as "7:30" would sort after "10:00".

        The sort is stable: tasks with the same time keep their input order.
        Runs in O(n log n) time.

        Args:
            tasks: The tasks to sort. Defaults to the candidate tasks.

        Returns:
            A new sorted list. The input list is left unchanged.
        """
        if tasks is None:
            tasks = self.candidate_tasks
        return sorted(
            tasks,
            key=lambda task: (task.scheduled_time == "", task.scheduled_time),
        )

    def filter_tasks(
        self,
        tasks: list[Task] | None = None,
        *,
        is_complete: bool | None = None,
        pet_name: str | None = None,
    ) -> list[Task]:
        """Return tasks matching the given completion status and/or pet name.

        Each filter left as None matches everything, so passing both narrows by
        both (logical AND) and passing neither returns every task. Runs in a
        single O(n) pass and keeps the input order, so it can be combined with
        sort_by_time() in either order.

        Args:
            tasks: The tasks to filter. Defaults to the candidate tasks.
            is_complete: Keep only finished (True) or unfinished (False) tasks.
                Keyword-only, so a bare positional True cannot be misread.
            pet_name: Keep only this pet's tasks. Matches ignore case.

        Returns:
            A new list of the matching tasks.

        Example:
            `schedule.filter_tasks(pet_name="Rex", is_complete=False)` returns
            Rex's unfinished tasks.
        """
        if tasks is None:
            tasks = self.candidate_tasks
        return [
            task
            for task in tasks
            if (is_complete is None or task.is_complete == is_complete)
            and (pet_name is None or task.pet_name.lower() == pet_name.lower())
        ]

    def detect_conflicts(self, tasks: list[Task] | None = None) -> list[str]:
        """Return a warning for each time slot claimed by more than one task.

        Lightweight on purpose: tasks clash only when they start at the same
        "HH:MM", not when their durations overlap. A 07:00 walk of 30 minutes
        and a 07:15 feed are therefore not reported.

        The method works in two passes. First it groups the tasks by start
        time in a dict, skipping tasks that are done, untimed, or not due on
        this schedule's date. It parses and re-formats each time, so "7:30"
        and "07:30" count as the same slot. Then it reports every slot holding
        two or more tasks, in clock order, saying whether they belong to the
        same pet or different pets. Runs in O(n) time, plus sorting the slots.

        It never raises: a task whose time (or the schedule's date) cannot be
        parsed gets a warning of its own and is left out of the check.

        Args:
            tasks: The tasks to check. Defaults to the candidate tasks.

        Returns:
            Warning strings, one per clashing slot or bad task. An empty list
            means no conflicts.

        Example:
            "WARNING: 2 tasks at 08:00, different pets: Thyroid pill for
            Mochi, Breakfast for Rex."
        """
        if tasks is None:
            tasks = self.candidate_tasks
        warnings: list[str] = []
        by_time: dict[str, list[Task]] = {}
        for task in tasks:
            if task.is_complete or not task.scheduled_time:
                continue
            try:
                if not task.is_due_today(self.date):
                    continue
                # Normalise so "7:30" and "07:30" land in the same slot.
                clock = datetime.strptime(task.scheduled_time, _TIME_FORMAT).strftime(_TIME_FORMAT)
            except ValueError:
                warnings.append(
                    f"WARNING: could not check {task.label()} — "
                    f"bad time {task.scheduled_time!r} or date {self.date!r}."
                )
                continue
            by_time.setdefault(clock, []).append(task)

        for clock in sorted(by_time):
            clashing = by_time[clock]
            if len(clashing) < 2:
                continue
            pets = {task.pet_name for task in clashing}
            if len(pets) > 1:
                scope = "different pets"
            else:
                scope = f"same pet ({clashing[0].pet_name})" if clashing[0].pet_name else "same pet"
            names = ", ".join(task.label() for task in clashing)
            warnings.append(f"WARNING: {len(clashing)} tasks at {clock}, {scope}: {names}.")
        return warnings

    def explain_plan(self) -> str:
        """Return a readable explanation of why each task was chosen or skipped."""
        header = (
            f"Plan for {self.date} starting {self.start_time} "
            f"({self.available_minutes} min available):"
        )
        if not self.planned_tasks and not self.skipped_tasks:
            return f"{header}\n  Nothing planned yet — call generate_daily_plan() first."

        lines = [header]
        for task in self.planned_tasks:
            lines.append(
                f"  {task.scheduled_time}  {task.label()} — {task.duration_minutes} min, "
                f"{task.priority.value} priority {task.category.value} "
                f"(score {task.priority_score()}), and it fit the time left."
            )
        for task in self.skipped_tasks:
            reason = (
                "already done"
                if task.is_complete
                else f"needs {task.duration_minutes} min, only {self.remaining_minutes()} left"
            )
            lines.append(f"  skipped   {task.label()} — {reason}.")
        lines.append(
            f"  Total planned {self.total_planned_minutes()} min; "
            f"{self.remaining_minutes()} min unused."
        )
        return "\n".join(lines)

    def total_planned_minutes(self) -> int:
        """Return the total duration of all planned tasks."""
        return sum(task.duration_minutes for task in self.planned_tasks)

    def remaining_minutes(self) -> int:
        """Return how much of the available time is still unused."""
        return max(0, self.available_minutes - self.total_planned_minutes())

    def send_reminders(self) -> list[str]:
        """Send reminders for every planned task and return the messages sent."""
        return [
            reminder.send()
            for task in self.planned_tasks
            for reminder in task.reminders
            if not reminder.sent
        ]


@dataclass
class User:
    """The pet owner: contact details, pets, and daily availability.

    The owner is the only object that can see across pets, so it is the owner —
    not the Schedule — that flattens tasks out of pet.tasks.
    """

    name: str
    email: str = ""
    phone_number: str = ""
    address: str = ""
    pets: list[Pet] = field(default_factory=list)
    schedules: list[Schedule] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> Pet:
        """Register a pet to this owner and return it."""
        self.pets.append(pet)
        return pet

    def get_pet(self, name: str) -> Pet:
        """Return the owner's pet with the given name."""
        for pet in self.pets:
            if pet.name == name:
                return pet
        raise KeyError(f"{self.name} has no pet named {name!r}")

    def get_all_tasks(self) -> list[Task]:
        """Return every task across every pet, flattened into one list."""
        return [task for pet in self.pets for task in pet.tasks]

    def get_due_tasks(self, date: str) -> list[Task]:
        """Return the unfinished tasks due on the given date, across all pets."""
        return [
            task
            for task in self.get_all_tasks()
            if task.is_due_today(date) and not task.is_complete
        ]

    def set_availability(self, date: str, start_time: str, minutes: int) -> Schedule:
        """Create a schedule for the given date and return it."""
        self.schedules = [existing for existing in self.schedules if existing.date != date]
        schedule = Schedule(date=date, start_time=start_time, available_minutes=minutes)
        self.schedules.append(schedule)
        return schedule

    def plan_day(self, date: str, start_time: str, minutes: int) -> Schedule:
        """Build and return a finished plan for one day. The usual entry point."""
        schedule = self.set_availability(date, start_time, minutes)
        for task in self.get_due_tasks(date):
            schedule.add_task(task)
        schedule.generate_daily_plan()
        return schedule


# The brief calls these Owner and Scheduler; the UML calls them User and
# Schedule. Same classes either way.
Owner = User
Scheduler = Schedule
