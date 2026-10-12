# PawPal+ Project Reflection

## 1. System Design
Three core actions:
- User should be able to add a pet
- User should be able to set reminders: recurring/one-time
- There should be a section dedicated to info on the pet eg medical history, name, breed/species, allergies, likes and dislikes, etc
**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?
- Answer: I included seven classes: User, Pet, Task, Reminder, and Schedule, plus two enumerations, Priority and TaskCategory. 
- User represents the owner — their contact details, the pets they own, and the daily availability they set. 
- Pet holds the animal's details and medical notes and owns the list of care tasks it needs. 
- Task is a single unit of care work that knows its own category, duration, priority, and recurrence, so it can answer whether it fits in the time remaining and whether it is due on a given date.
- Reminder attaches to a task to send or snooze its nudge.
- Schedule is where the planning happens: it holds one day's available time and sorts candidate tasks into planned_tasks and skipped_tasks, which is what lets it explain why each task was chosen or left out. 
- I made Priority and TaskCategory enums so that urgency and care type come from a fixed set of values instead of free-text strings.


**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.
- ANSWER: Yes, at first I wanted to have one class for Tasks and Schedules but Claude suggested to have separate classes plus some new enums to keep from overbearing.
---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?
- ANSWER: My scheduler weighs five things:
- **Time available.** The owner sets `available_minutes` for the day, and `Task.fits_in()` checks a task's duration against what is left. This is the only hard limit — everything else is a ranking.
- **Priority.** LOW/MEDIUM/HIGH becomes a number in `priority_score()`, weighted ×10, and that is the main sort key.
- **Care category.** MEDICATION and VET tasks get +5. That is enough to break a tie inside one priority level but never enough to jump a level — a HIGH walk scores 30 and a MEDIUM pill scores 25, so the owner's own judgment still wins.
- **Whether the task is due at all.** `is_due_today()` filters by recurrence first, so a "weekends" nail trim is never even a candidate on a Monday.
- **Completion status.** Anything already marked `is_complete` is skipped.
- How I decided: time had to come first because it is the only genuinely physical constraint — a morning has a fixed number of free minutes and no ranking can change that. Priority came next because it is the owner telling the system what matters, and I did not want my own category rules to overrule them. Category ended up as a tie-breaker only, because "the cat's thyroid pill matters more than a play session" is true at equal priority but should not beat something the owner explicitly marked HIGH.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?
- ANSWER: The scheduler is **greedy, not optimal**. It sorts by score once and fills the day from the top, never looking ahead. That means a big high-priority task can eat the whole budget and starve several small ones. I saw this happen in testing: a 60-minute HIGH vet checkup consumed a 60-minute window and pushed out a 5-minute medication and a 10-minute feed, even though those two together would have cost 15 minutes. A knapsack-style optimiser would have packed that day better.
- Why it is still reasonable here: one of the project requirements was that the plan **explains itself**, and greedy gives a one-sentence reason for every single task — "it ranked 35 and it fit the time left," or "it needed 45 minutes and only 35 were free." An optimiser produces a better-packed day that nobody can argue with, because the reason any one task got dropped is buried in the solver. For a pet owner glancing at their morning, a plan they can understand and override is worth more than a plan that is mathematically tighter.
- There is a smaller tradeoff inside the sort too: among tasks with equal scores I put the **shorter one first**, which fits more care into the same day but keeps pushing long tasks like the evening walk toward the end.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?
- ANSWER: I used Claude at nearly every stage, but for different things each time:
- **Design brainstorming** — turning my scenario notes into a UML draft, and splitting Task and Schedule into separate classes.
- **Scaffolding** — generating the class skeleton straight from `uml_draft.mmd`, so the code and the diagram started out agreeing with each other.
- **Implementation** — filling in the method bodies, the demo script, and the tests.
- **Research** — I asked it to investigate `st.session_state` before I wired up the UI, rather than guessing at how Streamlit persists objects.
- The prompts that worked best had one of two shapes. First, **pointing at a real file instead of describing it** — "based on your UML in `diagrams/uml_draft.mmd`" produced a skeleton that matched my design, where a vague description would have produced something generic. Second, **asking a design question rather than ordering code** — when I asked "how *should* the Scheduler retrieve all tasks from the Owner's pets?" I got the reasoning (the Owner is the only class that can see across pets, so it should do the flattening) and not just a block of code I would have pasted without understanding. The weakest prompts were the ones where I just said "make it work."

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?
- ANSWER: The clearest one was over a class that did not exist. In my first draft of section 1a I had written that my design included a "Task Scheduler" class. When I asked Claude to describe my UML, it pushed back and pointed out that there was no such class in `uml_draft.mmd` — the scheduling logic lived inside `Schedule`, and I had also left `Reminder` off my list entirely. That forced a real decision rather than a copy-paste: either I add a genuine `TaskScheduler` class and move `schedule_tasks()`, `generate_daily_plan()` and `explain_plan()` into it, or I keep the behaviour in `Schedule` and fix my written answer. I chose to keep `Schedule`, because splitting it would have left `Schedule` as a bag of data with no behaviour of its own, and my count of seven classes was right either way.
- How I verified things in general: I ran the code rather than trusting the explanation. `python main.py` showed me a real plan, and that output is where I actually *saw* the starvation tradeoff I describe in 2b — a five-minute pill being dropped for a long vet visit is obvious in printed output and invisible in a description. `pytest` gave me a pass/fail I could check myself. One verification caught a genuine problem: the tests passed when run from the project root and failed with `ModuleNotFoundError: No module named 'pawpal_system'` when run from anywhere else, which is why there is now a `pytest.ini` setting `pythonpath`. "It works on my machine, run this exact way" is not the same as "it works," and I only learned the difference by trying it the other way.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?
- ANSWER: The suite in `tests/test_pawpal.py` has 25 tests, grouped around the three features that make the scheduler "smart":
- **Sorting.** `sort_by_time()` puts scrambled tasks in clock order, puts tasks with no time last (a blank string would otherwise sort *first*), keeps tasks with the same time in their original order, handles an empty list, and never changes the list it was given. One test checks that an unpadded `"7:30"` sorts before `"10:00"`.
- **Recurrence.** Completing a daily task creates a new task due the next day, and a weekly one comes back seven days later on the same weekday only. The date maths survives the end of a month, the end of a year and leap years (Feb 28 → Feb 29 in 2028, but → Mar 1 in 2027). Early and late completions both land on a sensible date, and completing the same task twice never creates two copies. One end-to-end test checks the new copy shows up in *tomorrow's* plan and not today's.
- **Conflict detection.** Tasks at the same time are flagged, and the warning says whether they belong to the same pet or different pets. Three tasks in one slot give one warning, unique times give none, and finished, untimed or not-due tasks are ignored. A bad time like `"noon"` produces a warning instead of a crash.
- Why they mattered: these are the places where the code makes a decision the owner can't see. If sorting is wrong, the list just *looks* slightly off and nobody notices. If recurrence is wrong, a daily medication quietly stops coming back, which is the worst failure this app could have. The tests also found two real bugs. An unpadded `"7:30"` sorted after `"10:00"` because times were compared as text. And a badly formatted date in `mark_complete()` marked the task done *before* failing, so the next occurrence was lost for good. I first wrote both tests as expected failures (`xfail`) to record the bugs, then fixed the code, and now all 25 pass. Neither bug showed up in `main.py`, because the demo only ever used tidy input.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?
- ANSWER: **4 out of 5.** I'm confident in the parts that are tested: sorting, filtering, recurrence and conflict detection all have tests that check the hard cases, not just the happy path, and I've run both `main.py` and the Streamlit app to see the results with my own eyes. It isn't a 5 because of things I *know* the tests don't cover:
- **Preferred times get overwritten.** `generate_daily_plan()` replaces each planned task's preferred time with its slot. After planning, the original time is gone, so conflict checks and sorting work on the slot times instead. I'd test that preferred times survive planning, which really means adding a separate `preferred_time` field first.
- **Plans that run past midnight.** A plan starting at 23:30 with 60 free minutes would give its last task a time like `"00:20"`, and `sort_by_time()` would then put it *first*.
- **Identical tasks entered twice.** `Schedule.add_task()` treats two tasks with the same details as one task, so a "Walk, Rex, 08:00" entered twice is planned once and never flagged as a conflict. I'd decide whether that is a feature or a bug, and test whichever it is.
- **Overlapping durations.** Conflict detection only compares start times on purpose, so a 30-minute walk at 07:00 and a feed at 07:15 pass silently. If I made it smarter, the first tests would cover back-to-back tasks (ending exactly when the next starts), which must *not* count as a clash.
- **The Streamlit UI itself.** I checked it by driving it with Streamlit's `AppTest`, but that isn't saved as a test, so a future change to `app.py` could break the filters or the "Mark tasks done" flow without any test failing.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?
- ANSWER: The way the plan **explains itself**. Every planned task comes with a reason ("high priority feeding, score 30, and it fit the time left"), and every skipped task says what it needed ("needs 45 min, only 30 left"). That was the requirement I cared most about, and it shaped the design: it's why I kept the greedy scheduler instead of an optimiser (see 2b). I'm also happy with how small the "smart" features stayed. Sorting, filtering and conflict detection are each one short method on `Scheduler` that works on any list of tasks, so the CLI demo, the Streamlit page and the tests all use exactly the same code instead of three slightly different copies.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?
- ANSWER: The biggest thing is splitting **`scheduled_time` into two fields**. Right now one field means both "when the owner would like to do this" and "the slot the plan gave it", and planning overwrites the first with the second. That one shortcut causes most of the rough edges I listed in 4b: conflict warnings disappear after you generate a plan, and the Streamlit page has to save them separately just to keep explaining them. A `preferred_time` that planning never touches would also let the scheduler actually *use* the preference, putting the 07:30 feed at 07:30 instead of just wherever it falls in the queue.
- Smaller things:
  - Let `weekdays` and `weekends` tasks roll forward when completed, the way `daily` and `weekly` do.
  - Make conflict detection notice overlapping durations, not just identical start times.
  - Give the app a way to edit or delete a task. Right now the only fix for a typo is to add the task again.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
- ANSWER: **A passing test suite only tells you about the cases you thought of.** My first tests all passed, and so did the demo, because I only ever gave them sensible input. Things changed when I asked a different question: "what are the edge cases for a scheduler with sorting and recurrence?" Within one round, that turned up two real bugs, the unpadded-time sort and the lost recurrence. The same lesson applies to working with AI: it's very good at writing code that works for the example in front of it, and it's just as fast at finding where that code breaks *if you ask it to look*. The useful habit wasn't trusting or distrusting the AI. It was keeping two separate questions, "build this" and "now try to break it", and never letting the first stand in for the second. On the design side, keeping the UML up to date with the code (`diagrams/uml_final.mmd`) showed me the same thing: relationships I'd added without thinking, like a Task creating its own next occurrence, only became obvious once I had to draw them.
