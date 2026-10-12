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

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

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
