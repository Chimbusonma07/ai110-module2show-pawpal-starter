# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:
Portion 1:
![alt text](image.png)
Portion 2:
![alt text](image-1.png)


## 🧪 Testing PawPal+

```bash
# Run the full test suite:
python -m pytest

# Run with coverage:
pytest --cov
```

Sample test output:
Confidence Level: 4
```
![alt text](image-2.png)
![alt text](image-3.png)
```

## 📐 Smarter Scheduling

All scheduling logic lives in [`pawpal_system.py`](pawpal_system.py). `Scheduler` and `Owner` are aliases for the UML's `Schedule` and `User` classes.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_time()`, `Scheduler.schedule_tasks()` | Sorts by clock time, earliest first. The day plan is ordered by priority, then duration |
| Filtering | `Scheduler.filter_tasks()`, `Task.is_due_today()`, `Task.fits_in()` | Filters by pet and/or completion status. Skips tasks not due today or that don't fit the time left |
| Conflict handling | `Scheduler.detect_conflicts()` | Warns when two or more tasks start at the same time, for the same pet or different pets |
| Recurring tasks | `Task.mark_complete()`, `Task.next_occurrence()`, `Pet.complete_task()` | Completing a daily or weekly task creates its next occurrence automatically |

### Sorting by time: `Scheduler.sort_by_time(tasks=None)`

Returns tasks ordered by `scheduled_time`, earliest first. The sort key is a lambda, `lambda task: _time_sort_key(task.scheduled_time)`, which returns the pair `(time_is_missing, "HH:MM")`:

- Each time is re-formatted zero-padded first, so `"7:30"` sorts as `"07:30"` (before `"10:00"`, not after it as plain text would). Once padded, `"HH:MM"` strings sort correctly as text (`"07:05" < "09:00" < "14:30"`).
- The first part of the key puts tasks with no time, or an unreadable one, **last** instead of first.
- Tasks with the same time keep their original order (the sort is stable).
- Returns a new list and leaves the input unchanged. Defaults to the schedule's candidate tasks.

The day plan uses a separate sort. `Scheduler.schedule_tasks()` orders tasks by `Task.priority_score()` (highest first), then shorter duration, then name, and fits as many as it can into the available minutes. Medication and vet tasks get a small score bonus that breaks ties within a priority level, but never lifts them above a higher priority.

### Filtering: `Scheduler.filter_tasks(tasks=None, *, is_complete=None, pet_name=None)`

Returns the tasks that match every filter you pass:

```python
schedule.filter_tasks(pet_name="Rex")                     # all of Rex's tasks
schedule.filter_tasks(is_complete=False)                  # unfinished tasks
schedule.filter_tasks(pet_name="Rex", is_complete=False)  # both at once
schedule.sort_by_time(schedule.filter_tasks(pet_name="Mochi"))  # filter, then sort
```

- A filter left as `None` is ignored, so passing neither returns every task.
- Pet names match regardless of case (`"rex"` finds Rex's tasks).
- The filters are keyword-only, so a bare `True` can't land in the wrong argument.
- One pass over the list that keeps the input order, so it combines with `sort_by_time()` in either order.

When building the day plan, the planner also filters automatically:

- `Owner.get_due_tasks()` uses `Task.is_due_today()` to drop tasks that are complete or not due on the date. It understands `daily`, `weekly`, `weekdays`, `weekends` and day lists such as `mon,wed,fri`, and nothing is due before its `due_date`.
- `Task.fits_in()` moves any task that doesn't fit the remaining time to `skipped_tasks`. `Scheduler.explain_plan()` then says why each one was skipped.

### Conflict detection: `Scheduler.detect_conflicts(tasks=None)`

Returns a list of warning strings, one for each time slot claimed by two or more tasks. An empty list means no conflicts.

```
WARNING: 2 tasks at 07:30, same pet (Mochi): Morning feed for Mochi, Brushing for Mochi.
WARNING: 2 tasks at 08:00, different pets: Thyroid pill for Mochi, Breakfast for Rex.
```

- **Lightweight by design:** tasks clash only when they **start at the same time**. Overlapping durations (a 30-minute walk at 07:00 and a feed at 07:15) are not flagged.
- **Two passes:** first it groups tasks by start time in a dictionary, then it reports every group with more than one task, in clock order.
- **Same pet or different pets:** each warning says which, and names every task involved.
- **What it skips:** tasks that are complete, have no time, or aren't due on the schedule's date. For example, today's finished Litter box and tomorrow's queued Litter box don't clash.
- **Times are normalized:** `"7:30"` and `"07:30"` count as the same slot.
- **It never crashes:** a bad time such as `"noon"` becomes its own warning instead of raising an error.

Run it **before** `generate_daily_plan()`. Planning gives each task its own back-to-back slot, so a generated plan never has conflicts. `main.py` prints these warnings in its **TIME CONFLICTS** section.

### Recurring tasks: `Task.mark_complete()`, `Task.next_occurrence()`, `Pet.complete_task()`

When a `daily` or `weekly` task is marked complete, a new copy is created for its next occurrence:

```python
next_feed = mochi.complete_task(feed, "2026-10-12")
next_feed.due_date   # "2026-10-13" (a weekly task would give "2026-10-19")
```

- **`Task.mark_complete(on_date)`** marks the task done and returns the next occurrence, or `None`. Calling it again on a finished task returns `None`, so a double-click can't queue two copies.
- **`Task.next_occurrence(on_date)`** builds the copy with `dataclasses.replace()`. It keeps the name, pet, duration, priority and preferred time, and gets fresh, unsent reminders.
  - The new `due_date` is 1 day (daily) or 7 days (weekly) after whichever is later: the completion date or the old due date. A task finished early still moves a full step ahead, and a late one never comes back due in the past.
- **`Pet.complete_task(task, on_date)`** marks the task done **and** adds the new copy to the pet's task list. A Task doesn't know which pet it belongs to, so use this instead of calling `mark_complete()` alone. The finished task stays on the list as a record.
- **`Task.due_date`** keeps the new copy out of plans until its day. A `weekly` task then repeats on that same weekday.

Only `daily` and `weekly` create a new copy. A `weekdays`, `weekends` or one-off task is simply marked done; `Task.reset()` makes it plannable again.

In the Streamlit app, ticking a task under **Mark tasks done** calls `Pet.complete_task()` with the plan's date and shows when the next one is due.

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
