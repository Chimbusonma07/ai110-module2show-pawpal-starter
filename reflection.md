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

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
