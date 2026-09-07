# ENpower Skill Lab — Additional Development

Work completed on the dashboards beyond the reporting presentation.

The list is split into two parts. **Part A** covers screens that appear nowhere in
the presentation at all. **Part B** covers work where the presentation mentions
the subject in passing — a single line or a column in a table — but does not
describe a screen, so the screen had to be designed and built from scratch.

---

# Part A — Not covered in the presentation

These three screens have no counterpart anywhere in the deck.

## 1. Thinking Coaches — School Admin

The principal can now see every Thinking Coach working at their school in one
place: name, employee ID, designation and specialisation, which classes each
coach runs, contact details, and whether the coach is currently active.

Clicking a name opens that coach's full profile.

The presentation covers Thinking Coaches in three ways — the coordinator assigns
them to a school, the coach has their own dashboard, and the student's dashboard
shows their coach's name. It does not give the principal any view of coaching
staff. The access table in the presentation lists what each role can see —
school data, student data, timetable, attendance, curriculum, session feedback
and skill passport. Coaching staff is not one of them.

## 2. Thinking Coach Profile — School Admin

A complete profile for an individual coach, covering:

- **Contact** — official email, mobile, alternate number, city and state
- **Professional background** — qualification, specialisation, years of
  experience, skill-training experience, grades taught, languages spoken,
  training style and certifications
- **Classes** — every class this coach runs at the school, with academic year,
  number of sessions and current status
- **Onboarding status** — ID proof, address proof, police verification and
  contract

A principal can only open profiles for coaches at their own school. Attempting to
open a coach from a different school is refused.

## 3. Event Calendar — Thinking Coach

Coaches can now see the events published for their school and programme, laid out
as a calendar of dated cards with the event name, date, description, the grades
it applies to, and a link to further details. Undated events are listed at the
end.

Each coach sees only what was published to Thinking Coaches at their school.

The presentation describes an event calendar for the **student** dashboard and
events on the **parent** dashboard, and describes the Super Admin creating events.
It does not give the Thinking Coach a calendar.

---

# Part B — Mentioned in passing, screen built from scratch

For each of these, the presentation names the subject but gives no screen design,
no layout and no fields. The line from the presentation is quoted so the position
is clear.

## 4. Class Overview — School Admin

**What the presentation says:** *"Grade-wise student distribution — static —
school onboarding data"* — one line, describing a bar chart of student numbers
per grade for the school dashboard.

**What was built:** a full class register for the school. Every class is listed
with its assigned Thinking Coach, how many active students it holds, how many
sessions have actually taken place, the academic year and its status.

Sessions are counted from attendance that was genuinely marked, rather than from
the timetable, so the number reflects what really happened.

The screen also flags a gap the school could not previously see: groups of
students sitting in a grade and division that has no class record behind it.
These have no coach and no sessions attached, and are listed separately so the
principal knows they exist.

## 5. Class Attendance — School Admin

**What the presentation says:** *"Monthly gradewise student attendance — changes
monthly"* on the school dashboard, and an access table marking attendance as
visible to the School Admin.

**What was built:** a full attendance screen with two views.

**By class** — attendance percentage for each class shown as a bar, with the
number of students present, the total marked, and how many sessions the figure
comes from. Percentages are colour-coded, and any class whose figure rests on
fewer than three sessions is flagged.

**By session** — every individual session behind those percentages: the date,
which class, which coach, which project, how many were present, absent and late,
and whether the session went ahead or was cancelled.

Filters for grade and division sit at the top.

Two decisions shape the numbers. A student marked late is counted as attending,
because they were in the room. And every percentage is shown next to its session
count — without that, a class with one marked session looks identical to a class
with thirty, and a single day would read as a term's attendance record.

## 6. Kaushal Bodh pillar setting — Super Admin

**What the presentation says:** the Learning Pillars screens show *"Option to add
Pillars"*, and Kaushal Bodh appears among the pillars on those screens.

**What was built:** a **"Kaushal Bodh pillar"** tick box on both the Add Pillar
form and the Edit Pillar window.

Kaushal Bodh is handled differently from other pillars throughout the system —
its scores are reported on their own and are kept out of career matching. Until
now that difference was set behind the scenes and could not be reached from the
screen, so a pillar created and named "Kaushal Bodh" still behaved as an ordinary
pillar: its scores fed into the Skill Passport and its own report stayed empty,
with nothing on screen explaining why.

The tick box makes that setting visible and changeable, on every framework. It
also carries the existing setting into the edit window, so renaming or
recolouring a pillar no longer resets it by accident.

## 7. Scoring progress on Score Entry — Thinking Coach

**What the presentation says:** the score-viewing screen shows *"Pending [Add
score]"* against competencies that have not been scored.

**What was built:** the Score Entry screen now shows how far scoring has got
across the **whole project** — for example *"3 of 4 assessments scored"* — and
warns while any assessment is still untouched.

The button that generates student reports sits directly below whichever
assessment is open, which made it read as though it applied to that assessment
alone. It applies to the entire project. Pressing it after the first assessment
produced reports built on a quarter of the project's scores, with nothing on
screen to indicate that.

The figure updates the moment a score is entered or cleared, and counts only the
coach's own class, matching the students the reports actually cover.

---

# Still to be built

Approved, not yet started.

## 8. Reports & Analytics — Super Admin

Four report panels covering every school:

| Panel | What it shows |
|---|---|
| Student distribution by grade | Bar chart, total students, key observations |
| Monthly attendance by grade | Month selector, bar chart, school average line |
| Project completion by grade | Bar chart, overall completion, key observations |
| Top 3 skill profiles by grade | Table listing three profiles per grade |

## 9. Download Reports — Super Admin

The same four panels with a full Excel download — one sheet per panel — so the
figures can be taken away as a file.

## 10. Reports — Program Coordinator

The same panels, limited to the schools assigned to that coordinator.

Top 3 Skill Profiles is deliberately left out. The presentation's access table
marks Skill Passport data as not applicable to the Program Coordinator, so
including it would go against the specification.

---

# Who sees what

Every screen above follows the access rules set out in the presentation.

| Role | Sees |
|---|---|
| Super Admin | All schools |
| Program Coordinator | Only the schools assigned to them |
| Thinking Coach | Their own school |
| School Admin / Principal | Their own school, view only — no data entry |

---
