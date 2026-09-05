# memory.md — Knowledge Base (frequently-referenced context)

> Org policy: this file stores durable knowledge from research/work sessions.
> Keep entries precise and file:line referenced. Append, don't delete history.

---

## [2026-07-24] teacher/ parent/ student/ apps — full read-only audit

### Models
- `teacher/models.py`: single model `Teacher` (teacher/models.py:6-200). OneToOne `user`->AUTH_USER_MODEL
  (related_name `teacher_profile`, teacher/models.py:79). FK `school`->schools.School (teacher/models.py:82).
  ~90 fields across Basic/Professional/Contact/Address/SkillLab/Emergency/Compliance/Optional sections.
  Properties: `age`, `initials`.
- `parent/models.py`: single model `Parent` (parent/models.py:6-198). `parent_id` auto-gen in `save()`
  (parent/models.py:174-179, format `P` + 5 random upper/digits). OneToOne `user` -> related_name
  `parent_profile` (parent/models.py:99). **M2M** `students` -> student.Student, related_name `parents`
  (parent/models.py:154) — one parent can have multiple children, one student multiple parents.
  Properties: `initials`, `children_names`, `children_grades`.
- `student/models.py`: single model `Student` (student/models.py:7-193). OneToOne `user` -> related_name
  `student_profile` (student/models.py:94). FK `school` (student/models.py:97). `gr_number`,
  `skill_lab_reg_id`, `school_email` all unique. Properties: `full_name`, `age`.

### URL namespacing inconsistency
- teacher/urls.py and student/urls.py both set `app_name` ('teacher', 'student').
- **parent/urls.py has NO `app_name`** — its URL names (`parent_dashboard`, `parent_profile`, etc.) live in
  the global namespace, referenced bare (e.g. `redirect('parent_dashboard')` at parent/views.py:263).
  Flagged as inconsistency; do not "fix" without checking all templates using `{% url 'parent_dashboard' %}`.

### teacher/views.py — score-entry AJAX APIs (critical path, all @login_required + @user_passes_test(is_teacher))
- `api_projects_by_grade` GET (teacher/views.py:34-59) — projects for grade+teacher's framework.
- `api_project_details` GET (teacher/views.py:62-98) — assessments + profiles for a project.
- `api_assessments_by_project` GET (teacher/views.py:180-193) — assessments for a project.
- `api_score_entry_data` GET (teacher/views.py:196-269) — **main data loader**: maps assessment.project.grade
  (STAGE value) -> numeric class range via hardcoded `STAGE_TO_CLASSES` dict, filters students by school when
  teacher_profile.school set, returns students+competencies+existing ScoreEntry scores+stats(class_avg etc).
- `api_save_score` POST (teacher/views.py:272-306) — validates score 1-10 or null, school-scope check (403 if
  mismatched, but SKIPPED if teacher has no school), `ScoreEntry.objects.update_or_create(student_id,
  assessment_competency_id, defaults={score, entered_by})`. unique_together enforced (student, assessment_competency).
- `api_save_feedback` POST (teacher/views.py:377-407) — StudentAssessmentFeedback update_or_create.
- `api_save_project_feedback` POST (teacher/views.py:410-440) — StudentProjectFeedback update_or_create.
- `api_generate_report` POST (teacher/views.py:1052-1090) — calls competencies.engine.generate_project_report;
  used by score-entry.html bulk button in an N-sequential-fetch loop (score-entry.html:624-681), not batched.
- Attendance block (teacher/views.py:1093-1602): api_attendance_sessions, api_attendance_students,
  api_save_attendance, api_class_students — Timetable/AttendanceSession/AttendanceRecord based, resolves
  classroom via `_resolve_teacher_timetable` (teacher/views.py:1153-1167) scoped to coach or coach's school.

### KNOWN GAP — school-scoping bypass when teacher has no school
Pattern `if teacher_profile and student.school != teacher_profile.school: return 403` appears in
api_score_entry_data, api_save_score, api_save_feedback, api_save_project_feedback, api_generate_report,
student_score_detail. When `teacher_profile.school is None` (allowed, FK nullable/SET_NULL), the check is
skipped entirely -> a school-less teacher account can read/write scores & feedback for ANY student matching
the grade range, not just their own school. Real access-control gap, not just defensive code.

### Duplicated logic
- add_lesson (teacher/views.py:686-735) and edit_lesson (teacher/views.py:882-927): near-identical ~50 line
  video/article/quiz content-type-priority detection blocks. Candidate for extraction to shared helper.
- Debug `print()` statements left in add_lesson (teacher/views.py:682-684, 734-735).

### Seed scripts (root level)
- `seed_data.py` — BASE seed, run first. Creates users incl. teacher1/student1-4/parent1-2 (pwd Test@123),
  School SV001 "Shiv Vani Public School", Class 6A, FSL Framework/Pillars/SubPillars/6 Competencies,
  2 Profiles, 2 Projects (Bio Conservation, Eco Build), 1 Assessment w/ 3 AssessmentCompetency mappings.
- `seed_dummy.py` — independent of seed_data.py. 3 schools (DUM01-03), 6 coaches, 3 coordinators, 3 school
  admins, classes/students — but leaves `School.trainer_assigned` / `Class.thinking_coach` NULL on purpose
  (for practicing assignment flows from dashboard).
- `seed_rich.py` — DEPENDS on seed_data.py (needs SV001, teacher1, coordinator1, "Bio Conservation" project;
  raises SystemExit otherwise). Wrapped in `exec(r'''...''')` for `manage.py shell < file` execution. Adds
  classes 6B/7A, Timetables+Slots, generates AttendanceSession/Record with one frequent-absentee student per
  class, DailySessionFeedback, StudentProjectUpload.
- `seed_student_demo.py` — DEPENDS on student1 (from seed_data.py). Rebuilds student1's attendance around a
  HARDCODED "today" = date(2026,7,20) to engineer a 3-week streak + ~91% monthly attendance (Star badge).
  Marks all Projects completed for student1's class. Creates 2 newsletter + 1 success_story Announcements.
  CAUTION: hardcoded date may produce stale/wrong "current" window math once real date diverges far from
  2026-07-20 — recheck attendance.services.student_attendance_stats() if dashboard numbers look off.
- Run order: seed_data.py -> (seed_rich.py) -> (seed_student_demo.py). seed_dummy.py is independent/parallel.

### Core competencies models referenced by teacher views (competencies/models.py)
- `Project` (competencies/models.py:145) — grade=STAGE_CHOICES value, framework_ref FK, sequence_number.
- `Assessment` (competencies/models.py:172) — FK project, assessment_type, order.
- `AssessmentCompetency` (competencies/models.py:189) — FK assessment+competency, comp_type (individual/group),
  unique_together(assessment, competency).
- `ScoreEntry` (competencies/models.py:232) — FK student + assessment_competency, score (1-10, PositiveSmallInt,
  nullable), unique_together(student, assessment_competency).
- `StudentAssessmentFeedback` / `StudentProjectFeedback` (competencies/models.py:204, 218) — per (student,
  assessment) / (student, project) unique feedback text.
- `ProjectReport` (competencies/models.py:246) — EXISTS (contradicts stale note in CLAUDE.md saying it
  "does NOT exist yet" — CLAUDE.md needs updating, see below).

### CLAUDE.md staleness note
Root CLAUDE.md ("Current State" section) says `ProjectReport` model does NOT exist yet and `Project` is
"missing sequence_number field" — BOTH are already present in competencies/models.py (ProjectReport class
at line 246; Project.sequence_number at line 152). CLAUDE.md needs a refresh pass.

---

## [2026-07-24] Core data layer — settings, accounts, competencies+engine, support apps

### Project config (enpower_skill_lab/)
- `settings.py`: SQLite (`db.sqlite3`), `AUTH_USER_MODEL='accounts.User'`, `DEBUG=True`, SECRET_KEY hardcoded (settings.py:24-27).
  Two custom context processors (settings.py:92-93): `school_admin.context_processors.school_admin_profile`,
  `competencies.context_processors.nav_notifications`. Email = Mailtrap SMTP sandbox, creds hardcoded (settings.py:165-172).
- `urls.py`: routes admin/, accounts(''), schools/, superadmin/, coordinator/, school_admin/, teacher/, parent/, student/.
  **`competencies`/`assessments`/`lms`/`attendance`/`reports` includes COMMENTED OUT (urls.py:28-32)** — pure data/service layers.

### accounts/
- `User(AbstractUser)` (models.py:4): roles SUPER_ADMIN, PROGRAM_COORDINATOR, SCHOOL_ADMIN, THINKING_COACH, PARENT, STUDENT.
- `login_view` (views.py:8-41): role checked AFTER authenticate(); mixed redirect(name)/redirect('/path/').

### competencies/ — heart (models.py 393 lines, 19 models)
- Framework(5), Pillar(45, is_kb flag), SubPillar(65, code property does DB queries each call), Competency(95),
  Profile(113, M2M primary/secondary), Project(145, **project_type default 'Capstone' invalid**, sequence_number EXISTS,
  linked_project self-FK), Assessment(172), AssessmentCompetency(189), StudentAssessmentFeedback(204),
  StudentProjectFeedback(218), ScoreEntry(232, help_text '1–10' CORRECT), ProjectReport(246, EXISTS), ESLProduct(265),
  ProductProject(286), ProjectSession(302), Announcement(318), RubricCriterion(375).
- admin.py registers only Pillar/SubPillar/Competency/Profile/Project/Assessment (ScoreEntry/ProjectReport NOT in admin).

### competencies/engine.py (351 lines) — matches SKILL_PASSPORT_LOGIC.md
Constants: SECONDARY_WEIGHT=0.10, MIN_PRIMARY_FOR_UNLOCK=2, TOP_PROFILES=3, TOP_COMPETENCIES=5.
- get_competency_scores_for_project(24), _scores_for_single_project(81, averages per comp), _merge_scores(108, plug-in),
  run_profiling_engine(132), _calculate_profile_score(162, unlock≥2 primary, weightage, Σscore×weight),
  build_report_data(210), generate_project_report(260, persists ProjectReport), get_annual_passport_scores(292,
  latest by sequence_number), generate_annual_passport(316, **does NOT persist**).
- NOT implemented: max assessments/comps enforcement; label thresholds (raw scores only).

### Support apps
- `assessments/`, `reports/`: EMPTY stubs. `attendance/` (models 222 lines, not URL-wired): Timetable, TimetableSlot,
  AttendanceSession, AttendanceRecord, DailySessionFeedback, SessionPhoto, WeeklySessionFeedback, StudentProjectUpload.
  services.py: teacher_default_class, attendance_badge, student_attendance_stats, grade_wise_* (school-admin dashboard).
- `lms/` (not URL-wired): Lesson/LessonResource/LessonVideo (video_urls/quiz_data = TextField JSON strings).
- `schools/` (models 925 lines): School (onboarding sections A–I), Class (auto class_code via random.randint, collision risk).
  views = dummy "Hello from school".

---

## [2026-07-24] Admin apps — superadmin, coordinator, school_admin

### Own models
- superadmin.SuperAdmin (OneToOne User), coordinator.ProgramCoordinator (OneToOne User, M2M schools_assigned,
  set_password helper), school_admin.SchoolAdmin (OneToOne User, FK School, account_status pending/active/suspended).

### superadmin/views.py (3859 lines, 67 fns) — section map
47-129 dashboard/bulk landing; 134-517 School CRUD; 520-547 search_schools AJAX; 549-799 School Admin CRUD;
804-964 own profile/pwd; 967-1531 Student CRUD; 1216-1531 Teacher CRUD (**bug 1483 attendance_status not on Teacher**);
1534-1849 Parent CRUD; 1851-2206 Coordinator CRUD; 2208-2380 Class CRUD (**debug print 2308-2311**);
2382-2765 Lesson CRUD (dup content-type detection); 2769-3018 learning_pillars (multi-action POST dispatch);
3021-3064 profiles_competencies; 3067-3194 project_assessment; 3197-3350 custom_framework (dup);
3353-3441 manage_frameworks (dup); 3444-3608 ESL Products; 3610-3777 Announcements CRUD + api_schools_by_product;
3779-3859 api_rubric_grid/api_save_rubric_grid.
- bulk_import.py (1390 lines): roles school_admin/teacher/student/parent/coordinator, .xlsx generation,
  per-row atomic, Student↔Parent soft-linking. Reused by coordinator (student/parent only).

### coordinator/views.py (772, app_name='coordinator')
- _coordinator_schools(19) scoping guard (schools_assigned, fallback srm=user). dashboard, profile/pwd (**bare except 196**),
  Timetable mgmt (232-563), assign_coaches, bulk_upload proxy, coming_soon.

### school_admin/views.py (661) + context_processors.py
- dashboard uses attendance.services grade_wise_*. change_password auto-activates pending + mark_first_login (164-167).
- onboard_student/parent = near-dup of superadmin but school auto-scoped. context_processors injects school_admin_profile.

### Cross-app duplication: onboard_student/parent (superadmin↔school_admin ~400 lines), Framework CRUD triplicated,
  lesson content-type detection. No unit tests anywhere.

---

## [2026-07-24] UI mockups, static, loose files, docs

### skillpassport/ — 100% STATIC, ZERO Django integration
- Tailwind CDN, Google Stitch-style placeholder images. Screens 1-8 = green SPA (hash router), 9-11 = purple standalone
  (real enpower branding + neoRiSE codes). Map: 1 Competency Mgmt, 2 Profile Setup, 3 Project&Assessment, 4 Teacher Score
  Dashboard, 5 Detailed Scoring, 6 Analytics, 7 Student Report, 8 Annual Passport, 9 Teacher Dashboard, 10 Assessment Detail,
  11 Student Passport home. Mockups use 1-4 scale; real system 1-10.

### static/ (WIRED): per-role css/js folders; only shared = common/toast.css + toast.js.

### Loose files: kunal.html/kunal2.html = DEAD. ppt_dump.txt = client PPT dump. Help.txt = deploy runbook.
  MULTI_FRAMEWORK_PLAN.md = active plan (KB 6th pillar, simplified CSL+, not implemented). deploy.sh = prod deploy.
  ⚠️ test_openrouter.py = DEAD but has HARDCODED live OpenRouter API key in plaintext — rotate + remove.

### SKILL_PASSPORT_LOGIC.md (17 sections) matches engine.py: 5 pillars→17 subpillars→competencies, 15 profiles,
  score 1-10, 4-step engine (unlock≥2 primary → weightage → Σscore×weight → top 3), annual = latest by sequence_number.

---

## [2026-07-24] ANNOUNCEMENT SYSTEM — full flow (super admin → student/parent) — VERIFIED FROM SOURCE

### Model: competencies.models.Announcement (models.py:318-372)
- `announcement_type`: event / newsletter / success_story.
- Common: `is_published` (draft vs published), `program` (fsl/csl_plus_pc/csl_plus_tc/csl_foundation_pc/csl_foundation,
  nullable), `applicable_grades` JSON (stored as ints), `applicable_schools` M2M→School, `publish_to` JSON (["school","student","parent"]).
- Event-only used fields: event_name/date/description/link + applicable_schools + publish_to.
- Newsletter fields: newsletter_date/month/file/weblink. Success story: story_student_name/grade/school/text/photo_1/photo_2/youtube.
- `esl_product` FK = DEPRECATED (kept for backward-compat; new ones use `program`).

### CREATE (Super Admin only) — superadmin/views.py:3616-3760
- announcements_list(3616), announcement_add(3627), announcement_edit(3690), announcement_delete(3755).
- `is_published = (request.POST.get('action') == 'publish')` → "Save Draft" vs "Publish" button.
- **IMPORTANT: publish_to is set ONLY for ann_type=='event' (views.py:3645). Newsletter & success_story leave
  publish_to=[] → treated as "all audiences".**
- applicable_schools M2M set from POST after save (unconditional in add:3669-3671; event-only in edit:3708-3709).
- `api_schools_by_product` (3765) AJAX: schools where School.skill_program == program (populates school picker).
- Template: superadmin/announcements.html (single template, list_mode/form_mode add|edit).

### DELIVERY / TARGETING — who actually sees announcements
Targeting rule everywhere: EMPTY field = "all" (no restriction); non-empty = must match.

- **STUDENT** — `student.views.announcements_for_student(student, ann_type=None)` (student/views.py:260-288).
  Filters published anns by: program==student.school.skill_program, applicable_schools (if set) contains student.school_id,
  applicable_grades (if set) contains str(student.student_class), publish_to (if set) contains 'student'.
  Pages: student_announcements(329, all), student_event_calendar(311, events), student_newsletter(320, newsletters).
- **PARENT** — TWO different code paths (INCONSISTENT):
  1. Bell/header: `competencies.context_processors._parent_announcements(user)` (context_processors.py:31-62) — checks
     publish_to contains 'parent', program, applicable_schools, applicable_grades (ALL FOUR, across children).
  2. Parent dashboard: `parent/views.py _scope_announcement` (parent/views.py:188-203) — checks ONLY publish_to
     contains 'parent' + applicable_schools. **Does NOT check program or grade** → dashboard shows looser set than bell.
- **HEADER BELL** — `nav_notifications` context processor (context_processors.py:10-28), registered settings.py:93.
  ONLY fires for role STUDENT and PARENT. Max 8, sorted by created_at desc. Count = bell badge.

### KEY GAPS (relevant before any announcement change)
1. **Teacher (THINKING_COACH), Coordinator, and School Admin have NO announcement consumer code** — they never
   see announcements anywhere, despite publish_to offering a "school" option. "school" audience is effectively dead.
2. **publish_to only saved for events** — newsletters/success_stories always go to BOTH student & parent (publish_to empty=all).
3. **Parent dashboard vs bell mismatch** — dashboard `_scope_announcement` ignores program+grade; bell `_parent_announcements`
   checks them. Same parent can see an event on dashboard that's absent from the bell.
4. applicable_grades stored as ints (add:3636 `int(g)`), compared as strings everywhere (str(grade)) — works but fragile.
5. All announcement delivery is READ-time filtered (no per-recipient records / read-receipts / notification table).

---

## [2026-07-24] STRUCTURED ONBOARDING IDs (student & parent) — slide 2 flow

### Format (from client slide "Student & parent onboarding flow")
`{SchoolInitials}-{StudentInitials}-{Grade}{Div}-{Day}{Month}-{YY}-{stu|par}`
Example: Shiv Vani / Riddhima Guruji / grade 6A / born 22 Feb / AY 2026 →
`SV-RG-6A-222-26-stu` (student) and `SV-RG-6A-222-26-par` (parent, shares child's base).
- School initials = first letter of first two words of school_name (fallback school_code).
- Student initials = first letter of first + last name.
- DOB part = day+month, no padding (22 Feb → "222").
- YY = last 2 digits of academic year (last 4-digit year in the string; "2025-2026" → "26").
- On collision a counter is inserted before the suffix: `SV-RG-6A-222-26-2-stu`.

### Helper: accounts/onboarding_ids.py (NEW — single source of truth)
- `build_id_base(school, first, last, class, div, dob, academic_year, fallback_school_name)` → base string.
- `student_id_for(...)` → unique `-stu` id (checks User.username + Student.skill_lab_reg_id).
- `generate_parent_id(base)` / `parent_id_from_student(student)` → unique `-par` id (derives base from the CHILD).
- dob accepts date or common string formats.

### The ID IS the login credential
- Student: `User.username = skill_lab_reg_id = structured id`; initial `password = same id` (changeable after login).
- Parent: `User.username = parent_id = structured id (-par)`; initial `password = same id`.
- Existing users (seeded/old) keep their email usernames — only NEW onboarded users get ID logins.

### Wired into ALL onboarding paths
- superadmin/bulk_import.py `_process_student` (username/password/reg_id) + `_process_parent`
  (parent id derived from first linked student; falls back to email+random if the student isn't imported yet).
- superadmin/views.py `onboard_student`, `onboard_parent` (resolve linked students first).
- school_admin/views.py `school_admin_onboard_student`, `school_admin_onboard_parent`.
- `_send_welcome_email` gained `login_id` param; all welcome emails now show "Login ID" = the structured id.
- Email uniqueness checks changed from `username=email` to `email=email` (guarded with `if email`), since
  username is no longer the email.

### Edge cases / notes
- Bulk parent imported BEFORE its student → parent keeps a fallback P##### id + email login (rare; recommend
  importing students first). Student-side auto-link by parent_email still works but does NOT upgrade that id.
- The old early `SKILL{year}{rand}` reg_id lines in the manual views are now overwritten before save (harmless).
- Migration `0023` (announcement help_text) is the only DB migration; ID work is code-only.
- Verified (rolled-back shell test): slide example matches exactly, login via ID/ID authenticates,
  collision inserts `-2-`, parent shares the child's base.

---

## [2026-09-05] Framework flags — `is_fixed` vs `has_profiling`

- `Framework.is_fixed` (competencies/models.py:9) means ONLY "pillars are read-only".
  It is also read by `SubPillar.code` (competencies/models.py:98-107) to pick the code
  scheme (`SP{n}` for fixed, `{prefix}{n}` otherwise) — changing it renames existing
  sub-pillar codes, so never flip it as a fix.
- `Framework.has_profiling` (added migration 0026) is the profiling/passport switch.
  Read by `competencies/engine.py:profiling_enabled()` and the annual-passport gate
  (~line 741), and by `superadmin/views.py` for `is_csl`, the Profiles & Competencies
  pillar/competency source, and the project-page default framework.
- Before this, both meanings sat on `is_fixed`. `manage_frameworks` and the
  learning-pillars framework-create both write `is_fixed=False`, so every
  client-created framework was silently score-only.

### Production state (checked 2026-09-05, Railway Postgres)
Frameworks: FSL(id=1, prefix `Skills`), CSL +(id=2), CSL Foundation(id=3) — all
`is_fixed=false`. FSL has 7 pillars / 9 sub-pillars / 15 competencies / 3 schools.
CSL+ and CSL Foundation are empty shells with 2 and 1 schools.
**0 projects, 0 profiles, 0 profile↔competency links platform-wide.**
The seeded FSL (prefix `SP`, `is_fixed=true`) is gone — client rebuilt all three by
hand after the 2026-09-01 Railway wipe. So profiling produces nothing until the 15
profiles and their primary/secondary competency mapping are entered.

### Railway DB access
`DATABASE_URL` uses `postgres.railway.internal` — private, does not resolve from a
laptop, and there is no `DATABASE_PUBLIC_URL` (TCP proxy off). Query production via
Railway dashboard → Postgres → **Console** tab, then `psql $DATABASE_URL`. The
Console opens a shell, not a SQL prompt.

See [[framework-profiling-flag]].

### Framework CRUD lives in two places (2026-09-05)
- **Gear icon on Learning Pillars** → `fwManageModal` (learning-pillars.html:736, 1099+).
  This is the UI the client actually uses. Its create/edit forms send only name and
  prefix — **no `has_profiling` checkbox**, so anything made here is score-only. Its
  `edit_framework` handler (superadmin/views.py:2902-2915) does not touch
  `has_profiling`, so renaming FSL there will not switch profiling off.
- **Standalone page** `/super-admin/skill-passport/manage-frameworks/` — nothing links
  to it (superadmin/urls.py:70); reachable by URL only. Kept deliberately as an
  internal/dev tool. This is the only place with the "Enable Skill Profiling &
  Passport" checkbox and the Profiling On / Score Only badges. To give a new
  framework profiling, edit it from here.

### [2026-09-05] Skill profiles — production has none, and no UI creates them
`superadmin/views.py:profiles_competencies` handles only `save_profile` (the
primary/secondary mapping) and `rename_profile`. There is **no create or delete
action**, so with 0 profiles in the DB the page sits on its empty state and the
Super Admin cannot get past it. Adding that UI is deliberately deferred.

`seed_profiles.py` cannot fill the gap: its 15 profiles map to the original
neoRiSE codes (`SP11.C3`, `SP8.C2`, ...), while the client's hand-built FSL has
9 sub-pillars and 15 competencies under `Skills-SP*` codes. Running it would
create 15 profiles with zero usable mappings.

Competency codes were frozen as `17 Skills-SP1.C1` because the framework's
`prefix` was `17 Skills` when they were created; `SubPillar.code` is a derived
property so it updated to `Skills-SP1`, but `Competency.code` is a stored
CharField (competencies/models.py:118) and did not. Client fixed the existing
rows by SQL on 2026-09-05. **The underlying bug remains: editing a framework's
prefix does not regenerate its competency codes.**
