"""PawPal+ — pet care planning assistant.

Class skeleton generated from diagrams/uml_draft.mmd.
Attributes and method signatures only — no scheduling logic yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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


@dataclass
class Reminder:
    """A nudge attached to a task."""

    message: str
    remind_at: str
    recurring: bool = False
    sent: bool = False

    def send(self) -> str:
        """Deliver the reminder and return the text that was sent."""
        raise NotImplementedError

    def snooze(self, minutes: int) -> None:
        """Push remind_at back by the given number of minutes."""
        raise NotImplementedError


@dataclass
class Task:
    """A single unit of pet care work."""

    name: str
    category: TaskCategory
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    is_recurring: bool = False
    recurrence: str = ""
    scheduled_time: str = ""
    reminders: list[Reminder] = field(default_factory=list)

    def add_reminder(self, reminder: Reminder) -> Reminder:
        """Attach a reminder to this task and return it."""
        raise NotImplementedError

    def priority_score(self) -> int:
        """Return a numeric weight the scheduler can sort on."""
        raise NotImplementedError

    def fits_in(self, minutes_left: int) -> bool:
        """Return True if this task can finish within the time remaining."""
        raise NotImplementedError

    def is_due_today(self, date: str) -> bool:
        """Return True if the recurrence rule puts this task on the given date."""
        raise NotImplementedError


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
        raise NotImplementedError

    def remove_task(self, name: str) -> bool:
        """Remove the named task. Return True if one was removed."""
        raise NotImplementedError

    def get_tasks_by_priority(self, level: Priority) -> list[Task]:
        """Return this pet's tasks at the given priority level."""
        raise NotImplementedError

    def create_daily_schedule(self, schedule: Schedule) -> Schedule:
        """Feed this pet's due tasks into the schedule and return it."""
        raise NotImplementedError


@dataclass
class Schedule:
    """One day's plan: what fits in the owner's available time, and what doesn't."""

    date: str
    start_time: str
    available_minutes: int
    planned_tasks: list[Task] = field(default_factory=list)
    skipped_tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Offer a task to this schedule as a candidate for planning."""
        raise NotImplementedError

    def schedule_tasks(self) -> list[Task]:
        """Fit candidate tasks into the available time by priority."""
        raise NotImplementedError

    def generate_daily_plan(self) -> list[Task]:
        """Build the ordered plan for the day and return the planned tasks."""
        raise NotImplementedError

    def explain_plan(self) -> str:
        """Return a readable explanation of why each task was chosen or skipped."""
        raise NotImplementedError

    def total_planned_minutes(self) -> int:
        """Return the total duration of all planned tasks."""
        raise NotImplementedError

    def remaining_minutes(self) -> int:
        """Return how much of the available time is still unused."""
        raise NotImplementedError

    def send_reminders(self) -> list[str]:
        """Send reminders for every planned task and return the messages sent."""
        raise NotImplementedError


@dataclass
class User:
    """The pet owner: contact details, pets, and daily availability."""

    name: str
    email: str = ""
    phone_number: str = ""
    address: str = ""
    pets: list[Pet] = field(default_factory=list)
    schedules: list[Schedule] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> Pet:
        """Register a pet to this owner and return it."""
        raise NotImplementedError

    def get_pet(self, name: str) -> Pet:
        """Return the owner's pet with the given name."""
        raise NotImplementedError

    def set_availability(self, date: str, start_time: str, minutes: int) -> Schedule:
        """Create a schedule for the given date and return it."""
        raise NotImplementedError
