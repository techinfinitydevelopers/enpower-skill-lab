# ENpower Skill Lab — Additional Development

**Total: 30 hours** — 18 delivered, 12 approved and pending.

Everything below comes from the changes document and appears nowhere in the
reporting presentation. Work the presentation specifies — the Score Viewing
screens, the profiling engine, the school dashboard report panels, competency and
grade handling — is not included here, nor are fixes to any of it.

---

# Delivered — 18 hours

### 1. Thinking Coaches — School Admin · 2.5 hrs

A register of every Thinking Coach at the school: name, employee ID, designation,
specialisation, the classes each one runs, contact details and active status.

Class allocation is resolved live from class records rather than read from a
stored field, so the list always reflects the current teaching arrangement.

### 2. Thinking Coach Profile — School Admin · 2 hrs

A full profile for an individual coach across five sections:

- Contact — official email, mobile, alternate number, city and state
- Professional background — qualification, specialisation, years of experience,
  skill-training experience, grades taught, languages, training style,
  certifications
- Classes taught at the school, with academic year, sessions and status
- Onboarding status — ID proof, address proof, police verification, contract

Access is restricted so a principal cannot open a coach belonging to another
school.

### 3. Class Overview — School Admin · 3 hrs

Every class at the school with its assigned coach, active student count, sessions
actually held, academic year and status.

Sessions are counted from attendance that was genuinely marked rather than from
the timetable, so the figure reflects what took place.

The screen also identifies students sitting in a grade and division that has no
class record behind it. These carry no coach and no sessions and were previously
invisible to the school.

### 4. Class Attendance — School Admin · 3.5 hrs

Two linked views over the school's attendance.

**By class** — attendance percentage shown as a bar, with students present, total
marked, and how many sessions the figure rests on. Percentages are colour-coded,
and any class whose figure comes from fewer than three sessions is flagged.

**By session** — every session behind those percentages: date, class, coach,
project, present, absent and late counts, and whether the session went ahead or
was cancelled.

Filters for grade and division. A student marked late counts as attending, and
every percentage is shown beside its session count so a single day cannot read as
a term's record.

### 5. Event Calendar — Thinking Coach · 1.5 hrs

Events published for the coach's school and programme, as dated cards showing the
event name, date, description, applicable grades and a link to details. Dated
events appear first, undated last.

Filtered by school, programme and target role, so each coach sees only what was
published to Thinking Coaches at their school.

### 6. Kaushal Bodh pillar setting — Super Admin · 1.5 hrs

A tick box on both the Add Pillar form and the Edit Pillar window marking a
pillar as Kaushal Bodh.

Kaushal Bodh is handled differently across the whole system — reported on its own
and excluded from career matching — but that setting could not be reached from
any screen. A pillar created and named "Kaushal Bodh" therefore behaved as an
ordinary pillar: its scores fed into the Skill Passport while its own report
stayed empty, with nothing to explain why.

The setting is now visible, works on every framework, and is preserved when a
pillar is renamed or recoloured.

### 7. Scoring progress on Score Entry — Thinking Coach · 1.5 hrs

The Score Entry screen now reports how far scoring has progressed across the
whole project — for example *"3 of 4 assessments scored"* — and warns while any
assessment remains untouched.

The button that generates student reports sits directly below whichever
assessment is open, which made it read as applying to that assessment alone. It
applies to the entire project. Pressing it after the first assessment produced
reports built on a fraction of the scores, with nothing on screen to indicate it.

The figure updates the moment a score is entered or cleared, and counts only the
coach's own class — matching the students the reports actually cover.

### 8. Dashboard clean-up — all roles · 2 hrs

Every navigation entry across all six dashboards was checked against what
actually existed behind it. Nineteen led nowhere.

Removed as instructed:

| Dashboard | Removed |
|---|---|
| Super Admin | Assessment Completion Heatmap panel, Monitoring section (assessment monitoring, attendance monitoring, multi-school comparison), School Details link |
| Program Coordinator | Multi-School Comparison |
| Thinking Coach | Student Profile link — the same view is already reached from the student list |

Removed along with the supporting navigation code left behind. The remaining dead
entries were assessed and carried into the plan below rather than deleted.

Verified afterwards by loading each dashboard and confirming both that the removed
items are gone and that everything else still works.

### 9. Student GR number made optional · 0.5 hrs

The GR / admission number was compulsory on student records. Schools onboarding
mid-year frequently do not have it to hand, which blocked the record entirely.

It is now optional across the onboarding form and both bulk-import routes, while
still rejecting a genuine duplicate if one is supplied. Records without a number
save correctly and no longer clash with one another.

---

# Pending — 12 hours

Approved, not yet started.

### 10. Reports & Analytics — Super Admin · 7 hrs

Four report panels covering every school:

| Panel | Contents |
|---|---|
| Student distribution by grade | Bar chart, total students, key observations |
| Monthly attendance by grade | Month selector, bar chart, school average line |
| Project completion by grade | Bar chart, overall completion, key observations |
| Top 3 skill profiles by grade | Table listing three profiles per grade |

### 11. Reports — Program Coordinator · 3 hrs

The same panels, limited to the schools assigned to that coordinator.

Skill profile data is deliberately excluded, in line with the access rules that
place Skill Passport outside the Program Coordinator's remit.

### 12. Email templates · 1.5 hrs

Three templates covering the messages sent to School Admins, Program Coordinators
and Thinking Coaches:

- **Onboarding** — welcome message carrying login credentials
- **Announcement / event / newsletter** — update notification
- **Password reset** — reset confirmation with school and role

Expected volume is 150–200 emails per year.

### 13. Program Coordinator bank details made optional · 0.5 hrs

Bank account details are currently compulsory when onboarding a Program
Coordinator, blocking the record where those details are not yet available. To be
made optional.

---

# Summary

| | Hours |
|---|---|
| **Delivered** — 9 items | **18** |
| **Pending** — 4 items | **12** |
| **Total** | **30** |
