"""PawPal+ — pet care planning assistant.

Implements the design in diagrams/uml_draft.mmd.

Ownership runs User -> Pet -> Task -> Reminder. Schedule plans one day: the owner
flattens tasks across pets, hands them to a Schedule as candidates, and the
Schedule fits what it can into the available time and explains the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

        Recurring tasks accept "daily" (or blank), "weekdays", "weekends", or a
        comma-separated list like "mon,wed,fri". A one-off task is due only on
        the date it names, or on any date if it names none.
        """
        rule = self.recurrence.strip().lower()
        if not self.is_recurring:
            return rule in ("", date.strip().lower())
        if rule in ("", "daily"):
            return True
        if rule in _RECURRENCE_ALIASES:
            return _weekday_of(date) in _RECURRENCE_ALIASES[rule]
        days = {part.strip()[:3] for part in rule.split(",") if part.strip()}
        return _weekday_of(date) in days

    def mark_complete(self) -> None:
        """Mark this task done so it stops being planned."""
        self.is_complete = True

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
