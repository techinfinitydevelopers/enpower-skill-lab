# BUILD_LOG.md

Chronological record of completed tasks (per org policy: log after each completed task).

---

## 2026-07-24 — Read-only audit: teacher/, parent/, student/ apps

**Task:** Full line-by-line research pass (no code changes) across teacher/, parent/, student/ apps —
models.py, views.py, urls.py, admin.py, templatetags/, templates listing, plus root seed scripts
(seed_data.py, seed_dummy.py, seed_rich.py, seed_student_demo.py).

**Scope covered:**
- teacher/models.py (Teacher, 1 model, ~90 fields), parent/models.py (Parent, 1 model + M2M to Student),
  student/models.py (Student, 1 model).
- teacher/urls.py (30 routes, app_name='teacher'), parent/urls.py (4 routes, NO app_name — flagged),
  student/urls.py (11 routes, app_name='student').
- teacher/admin.py, parent/admin.py, student/admin.py.
- teacher/templatetags/teacher_extras.py (single `get_item` filter).
- Template directory listings for all 3 apps; deep read of teacher/templates/teacher/score-entry.html (724
  lines, full client-side AJAX flow for score entry).
- teacher/views.py read in full (1602 lines) — every endpoint documented, including all AJAX/API endpoints
  for score entry, attendance, feedback, report generation.
- parent/views.py (327 lines) and student/views.py (438 lines) read in full.
- All 4 root seed scripts read in full (822 lines total).

**Findings (see memory.md for full detail):**
1. parent/urls.py missing `app_name` — inconsistent with teacher/student apps.
2. School-scoping bypass in teacher/views.py score/feedback/report endpoints when teacher_profile.school
   is None (access-control gap, not by design).
3. Duplicated content-type-detection logic between add_lesson/edit_lesson in teacher/views.py.
4. Debug print() statements left in teacher/views.py::add_lesson.
5. seed_student_demo.py hardcodes "today" as 2026-07-20 — will go stale over time.
6. Root CLAUDE.md is stale: claims ProjectReport model and Project.sequence_number don't exist — both do.

**Outcome:** No files modified (read-only task as instructed). Findings written to memory.md (knowledge
base) for future reference before any code changes are made to these apps.
