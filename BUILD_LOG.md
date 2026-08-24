# Build Log

Chronological record of completed tasks (per org policy: log after each completed task).

## 2026-08-24 — Aug-11 meeting changes: 8 implemented, 3 verified, 6 flagged

Worked from the Aug-11 Google Meet summary. Implemented the unambiguous items, verified the "confirm this" ones, left the ambiguous/blocked ones untouched (listed at the bottom with the reason).

### Implemented
- **Competency dropdowns show full descriptions** (`superadmin/templates/superadmin/project-assessment.html`). Both the server-rendered `<option>` list and the JS-built `buildCompSelect` rows now render `CODE — Name · Description`, plus a `title=` tooltip. `COMP_OPTIONS` carries a new `desc` field.
- **Per-student average on the scoring grid** (`teacher/templates/teacher/score-entry.html`). New "Average" column; `studentAvg()` averages only the competencies actually scored for that student (so a half-scored student isn't dragged down by unscored ones) and shows `n/total scored` underneath. Recomputes live on each score save via `refreshStudentAvg()`.
- **Inline per-student feedback box on the scoring grid.** New "Feedback" column with a 1-row textarea that expands to 3 on focus and saves on blur to the existing `api_save_feedback`. `api_score_entry_data` now returns a `feedback` map so boxes render pre-filled. Skips the round-trip when text is unchanged.
- **Per-assessment breakdown on the student project report.** New `get_per_assessment_breakdown()` in `competencies/engine.py` — one entry per assessment in order, with per-competency scores, assessment average and `scored/total`. Includes plug-in project assessments (they merge into the parent) and keeps unscored assessments visible as "Not scored yet" rather than hiding them. Rendered as a new "Assessment by Assessment" card grid in `report-detail.html`.
- **Full competency descriptions on student-facing reports.** `build_report_data` / `generate_annual_passport` now store `competency_desc`. Added `attach_competency_descriptions()` which backfills the field at render time in one query — **reports generated before this change display correctly without being regenerated**. Wired into both `student_report_detail` and `student_annual_passport`; descriptions render on the report card, the skills-to-work-on list and the annual passport.
- **Kaushal Bodh now reported separately on the annual passport** — this was the "verify, fix if missing" item and it *was* missing. The engine supported `include_kb=True` but nothing in `student/` ever called it, so KB scores surfaced nowhere. Added `get_annual_kb_scores()` (same latest-project-wins rule as the passport) and a distinct KB section on `annual-passport.html` with an explicit note that these scores are not part of the passport calculation. Verified end-to-end with a temporary KB score: section renders, and the KB competency stays out of `all_competency_scores`.
- **Program Coordinator bank details are now optional.** `bank_name`, `branch_name`, `account_number`, `ifsc_code` → `blank=True, null=True` (migration `coordinator/0002`). Dropped `required` + the `*` markers on `onboard-pc.html` and `edit-pc.html`, marked the section "(optional)", `view-pc.html` shows `—` when empty, and the create view stores `None` instead of `''`.

### Verified (no code change needed)
- **KB excluded from the Skill Passport calculation** — confirmed. `_exclude_kb_scores` runs by default; a direct test showed zero KB competency ids leaking into the passport score set.
- **"Generate Report" is cumulative** — confirmed. `generate_project_report` → `build_report_data` aggregates every assessment in the project and `update_or_create`s the single `ProjectReport`.
- **Attendance badges exist and were kept** — `student/templates/student/badges.html` renders monthly-attendance tiers.

### Testing
`manage.py check` clean, `makemigrations --check` reports no changes, all migrations applied. Swept every parameterless page for all six roles while logged in as each: **86/86 pages, zero 5xx** (super admin 33, coordinator 11, school admin 10, thinking coach 17, parent 4, student 11).

### Grade field → individual grades (done after user confirmed single-grade + dummy data)
User chose: one individual grade per project, dropdown listing plain numbers `1, 2, 3 … 12` (not "Grade 1", not stage ranges). Confirmed existing projects are all dummy, so the narrowing side effect was accepted.

- `competencies/models.py`: added `GRADE_CHOICES = [(str(i), str(i)) for i in range(1, 13)]`, `DEFAULT_PROGRAM_GRADES = ['6','7','8','9']`, and `STAGE_TO_GRADES` (kept for the migration and for any legacy stage value still arriving). `Project.grade` now uses `GRADE_CHOICES` instead of `STAGE_CHOICES`. `STAGE_CHOICES` itself stays — `Competency.stage` still uses it.
- Migration `competencies/0024_project_grade_individual`: `RunPython` collapses each stage to the lowest grade of that stage (Foundational→1, Preparatory→3, Middle→6, Secondary→9) **before** the `AlterField`, with a working reverse that maps grades back to stages. Applied: 8 projects converted (1→`1`, 3→`3`×3, 6→`6`×3, 9→`9`).
- `teacher/views.py`: student filtering in `api_score_entry_data` no longer expands a stage into a class range — it uses `[project.grade]`, falling back through `STAGE_TO_GRADES` if a legacy stage value is seen. `teacher_dashboard` and `score_entry` now pass `grade_choices` instead of `stage_choices`.
- Templates: the two hardcoded 4-option stage dropdowns in `project-assessment.html` (create + edit) now loop `grade_choices`; `teacher/dashboard.html` and `teacher/score-entry.html` grade selects likewise. Display spots that would otherwise render a bare number now read `Grade 6` (project list tag, project subtitle, scoring breadcrumb).
- `superadmin/views.py` `project_assessment` passes `grade_choices` + `default_program_grades`.

**Verified:** dropdown renders exactly `1, 2, …, 12`; no `Foundational — Class` options remain anywhere; filtering proven positively by temporarily repointing a project's grade — grade 8 returned exactly the two class-8 students, grade 5 the one class-5 student, grade 7 the one class-7 student, then reverted. (The first negative test returned 0 students only because no student in the DB is in class 6.)

**Known consequence, accepted:** a project now shows only its one grade's students in the scoring grid, where a `Middle` project previously showed grades 6–8. Existing scores are untouched in the DB; they just aren't listed under a project whose grade no longer matches. Real projects will need their grade set deliberately.

### NOT done — needs a decision or is blocked
- **Save Feedback bug — could not reproduce.** `api_save_feedback` returns `{"ok": true}` and the row persists; the `saveFeedback()` JS, `saveStatus` element and both feedback forms (`daily-feedback.html` enctype/csrf, `weekly-feedback.html`) are all correct. Most likely cause on prod: a Thinking Coach whose `teacher_profile` or `school` is unset gets a 403 "No teacher profile" and the UI just shows a failure toast. All six local teachers have both, so it can't be reproduced here. Needs the specific coach account it failed for.
- **Program-based project visibility / auto-assign FSL projects** — assignment mechanics not specified (per-school? per-student? on project create or on school onboard? what happens to already-created projects?).
- **Kaushal Bodh competencies into Learning Pillars** — blocked on Ritu's final list.
- **Annual passport top-project + work-firm-category highlight** — blocked on the reference image.
- **Three top career matches** — profiling already returns top 3; the meeting asked to *confirm the logic*, which needs a product decision on the "sufficient data" threshold (currently unlock needs ≥2 primary competencies).
- **Parent self-onboarding via Student ID** — largest item, needs model work, and the security model needs a call first: a Student ID is shared (report cards, teachers, classmates), so anyone who knows it can claim the parent account before the real parent does. Forced password change on first login doesn't close that window.

## 2026-08-24 — Local repo switched to company remote + production audit

### Root cause of "local looks in sync but server has more commits"
Local clone was wired to the **personal fork** `iamKunaaal/enpower-skill-lab`, while production pulls from the **org repo** `techinfinitydevelopers/enpower-skill-lab`. `git ls-remote` from local reported "in sync" because it was querying the wrong repo. Local was 34 commits behind the real main.

### Remote switch (done)
- Safety tag `backup-before-company-switch-e30c615` created on the old local tip.
- `origin` renamed to `personal`; `origin` now points at `techinfinitydevelopers/enpower-skill-lab`.
- Local edit to `.claude/settings.local.json` stashed (`stash@{0}`) — upstream also modified that file.
- Fast-forward `e30c615..ac220b4` — clean, no merge, no conflicts. 110 files, +10857/-1531. Local now 61 commits, tracking `origin/main`.
- Local DB backed up to `db_backup_before_pull_20260824.sqlite3`, then 9 pending migrations applied (attendance 0001-0004, competencies 0021-0023, parent 0002, schools 0009). `manage.py check` clean.
- Dev server on :8005 verified — `/login/` 200, `/student/dashboard/` 302.
- Test student login: `aaravjoshi1768033944@yahoo.com` / `Student@123` (id 9, password reset locally). Note: `accounts.User.role` values are UPPERCASE (`STUDENT`, `THINKING_COACH`, …).

### Production server access
Root password was lost. Recovered via DigitalOcean **Web Console** (DOTTY agent grants a passwordless root shell) instead of "Reset root password", avoiding a droplet reboot and site downtime. Local pubkey `kunal@Lenovo` appended to `/root/.ssh/authorized_keys`; key-based SSH to `root@68.183.93.246` now works.

### Production audit — clean
Server HEAD == `origin/main` (0 ahead / 0 behind), no working-tree drift on tracked files, `git fsck` clean, all migrations applied, `makemigrations --check` reports no changes, `manage.py check` 0 issues, `db.sqlite3` correctly gitignored, SSL valid to 2026-10-10, gunicorn + nginx active, disk 20%.

### Production audit — OPEN ISSUES (nothing changed on server; needs decision)
CRITICAL
1. `DEBUG = True` in production (`settings.py:27`, set in `664d6ed`). **Verified publicly exploitable** — `GET /audit-check-nonexistent-xyz` returns a 3940-byte Django debug 404 leaking ~16 internal URL patterns; any 500 exposes full traceback with local variables. Bots actively probing (`103.153.183.69`, `195.178.110.102` hitting `/signin`, `/signup`, `/register`, `/auth/callback`, `/admin`).
2. `SECRET_KEY` committed to GitHub (`settings.py:24`, still `django-insecure-` auto-generated). Anyone with it can forge session cookies for any user including super admin.
3. Mailtrap `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` committed in plaintext (`settings.py:170-171`). No `.env` file exists — all secrets hardcoded.

HIGH
4. `ufw` inactive — all ports open.
5. No DB backup automation (no root crontab). Only a manual `db_backup_before_backfill_20260807_082803.sqlite3` from 2026-08-07. DO panel backup status unverified.
6. HTTPS not enforced — `SECURE_SSL_REDIRECT`, HSTS, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` all unset.
7. Gunicorn runs as `User=root`.

MEDIUM
8. Ubuntu 25.10 is **EOL** — no further security updates; 26.04 LTS available.
9. Pending kernel restart on the droplet.
10. SQLite + 3 gunicorn workers — write-lock contention risk as usage grows.
11. 959MB RAM, ~375MB available, no swap.
12. `/admin` throws `RuntimeError: APPEND_SLASH` on POST (bot-triggered, minor).

## 2026-07-29 — Fix: teacher score-entry hides projects with NULL framework_ref
- Teacher Score Entry project dropdown filtered `framework_ref=school.framework_ref`, which EXCLUDES super-admin projects whose framework_ref is NULL (only legacy `framework` CharField set). Reproduced: NULL-framework_ref FSL/Middle project hidden from FSL teacher.
- Fixed `api_projects_by_grade` + `_teacher_projects` (teacher/views.py) to match `Q(framework_ref=fw) | Q(framework_ref__isnull=True, framework=fw.name)`. Verified: previously-hidden project now shows; real projects intact. check clean.

## 2026-07-29 — CSL+ competencies + seed management command
- Diagnosed "assessment competency dropdown empty for CSL+" = CSL+ framework has full pillar/sub-pillar scaffold (5 pillars, 17 sub-pillars) but 0 competencies. Code is fine (verified end-to-end via Playwright: accordion toggle, dropdown options, add-row, save-fix all work; FSL shows 6 comps).
- Added management command `competencies/management/commands/seed_csl_competencies.py` — idempotent, seeds 3 sample competencies per CSL+ sub-pillar (51 total), Active, stage=Middle. Run on prod: `python manage.py seed_csl_competencies`.
- Seeded locally: 51 CSL+ active competencies.

## 2026-07-29 — Fix IntegrityError on Project-Assessment save
- superadmin project_assessment / save_assessment: duplicate competency in POST caused UNIQUE(assessment,competency) IntegrityError on AssessmentCompetency. Fixed by de-duping comp_ids (skip already-seen) + wrapping delete+recreate in transaction.atomic. views.py ~3167.
- Reported on PROD (enpower.techinfinity.link); fix is in repo — needs deploy.

## 2026-07-29 — Built + connected Teacher Reports & Analytics (Screen-6)
- Only genuinely-missing skillpassport feature built (rest of 11 mockups already have live connected versions; not duplicated).
- New: `reports_analytics` view (teacher/views.py) — real data: class average, per-competency averages, per-student performance, scoped to teacher's school (read-only). URL `teacher/reports/`. Template `teacher/reports-analytics.html` (Bootstrap, teacher app style, 3 anchor sections).
- Wired the 3 previously-dead teacher sidebar links (Class Performance / Competency Reports / Student Reports) to this page (were href=#). No existing functionality changed — purely additive.
- Verified via Playwright (teacher1 / Shiv Vani): 200, Total 24 / Assessed 4 / Class Avg 8.0/10 / 3 competency bars / student table. manage.py check clean.
- Updated client doc (Client_Page_Report_CORRECTED_2026-07-29.docx): teacher Class Performance / Competency Reports / Student Reports now "Working" (14 items work, 2 not built).

## 2026-07-29 — Client page-connectivity report (plain language, code-verified)
- Generated `Client_Page_Report_CORRECTED_2026-07-29.docx` (python-docx). Plain-language, colour-coded, per-role tables.
- Verified claims against actual code/templates/URLs (not the old SIDEBAR_AUDIT). KEY correction: added "Built but not linked" category distinct from "Not built yet".
- Built-but-not-linked (design/page exists, no menu link): skillpassport Screen-1..11 (HTML files exist, no urls.py/views.py); school_admin Onboard Student + Onboard Parent (views+URLs+templates exist, sidebar links commented out base.html:247-251); teacher Student Profile (view-student.html works via Student List, sidebar shortcut is href=#); coordinator School Details (school-detail.html + school_detail URL exist, sidebar mislinks to school_list).
- Corrected: teacher's 5 report/event items are dead href=# (NOT "Coming Soon" — teacher has no coming-soon.html). Coordinator's 9 ARE real Coming Soon (coming-soon.html exists).
- Truly not built (no template/view): superadmin 11 (monitoring/analytics/settings/billing), school_admin 12 (classes/assessment/attendance/reports groups), parent 3 (switch-student/perf-summary/annual-report).
- Gen script: scratchpad/gen_client_report.py.

## 2026-07-28 — Passport max-width + server restart
- Content stretched full-width on large screens (no max-width). Added `max-width:1080px; margin:0 auto` to `.sp2` (shared partial) → both annual + report-detail now centered/constrained.
- Dev server had entered a broken state after rapid template autoreloads (serving 404 on annual). Restarted fresh with `--noreload` (stable for viewing; manual restart needed for future edits).

## 2026-07-28 — Report Detail fixes (empty avatar + stretched card)
- BUG: passport avatar blank because `student_report_detail` view didn't pass `student` to context (template uses `student.first_name`). Fixed by adding `'student': student`.
- Single career-match card stretched full-width/tall (flex-grow with 1 profile). Changed `.profile-card` to `flex:1 1 240px; max-width:340px` + profiles-row `justify-content:flex-start`. Verified via Playwright: avatar="SK", card=340px.

## 2026-07-28 — Report Detail page → skill2 design + shared partials
- Applied skill2 playful UI to `student/report-detail.html` (per-project Skill Passport detail). Kept ALL existing fields: top_3_profiles→Top Career Matches (enriched match% + primary-competency tags in view), all_competency_scores→Skills Report Card, skills_to_work_on section, teacher feedback→Coach's Feedback. Header stats: Overall Level (mean /10) + Top Match (best profile %).
- Refactored to DRY: extracted skill2 CSS→`student/_passport_styles.html` and JS→`student/_passport_scripts.html`; both annual-passport.html and report-detail.html `{% include %}` them. Added extra classes (workon-card, fb-item, sp-grid2, outdated-note).
- `student_report_detail` view: added overall_score, best_match, profile enrichment (match_percent + tags via Profile.primary_competencies).
- Verified via Playwright @1440w: both pages 200, detail shows header/career-matches/report-card/work-on/feedback correctly (project "Bio Conservation", 8.0/10, 69% match). manage.py check clean.

## 2026-07-28 — Skill Passport header fixes (post-revamp)
- Header card content overflow: root cause = global `.student-header { height:80px }` (student dashboard's header bar) leaking into the new card via shared class name. Card stuck at 80px, avatar+stat cards spilled out. Fixed by adding `height:auto; min-height:0; width:auto` to `.sp2 .student-header` (my selector is more specific, wins). Verified via Playwright: header now 203px @1440w, all children contained, no overflow.
- Earlier vertical clip: replaced decorative `::before` circle with layered radial background + `overflow:visible`; made student-info a compact flex-column.
- Header 3rd chip changed to calendar + academic year (mockup match), was "Skill Passport".
- Year-in-Review: fixed contradictory focus para (was listing strengths as "work on" for high scorers). Now focus lists only score<6 competencies, else positive "no major gaps" line.
- LESSON: mockup reused generic class names (.student-header, .avatar, .stat-card, .btn) that collide with student layout CSS — scope future embedded mockups fully or set explicit height/width to block leaks.

## 2026-07-28 — Student Annual Skill Passport UI revamp
- Replaced `student/annual-passport.html` with client mockup (Downloads/skill2.html) — playful Nunito/Fredoka design: animated header, career-match cards, skills report card w/ stars+bars, auto Year-in-Review, confetti.
- Fully wired to real data (not static): name/initials/grade/division/skill_lab_reg_id/academic_year; overall level = mean of competency scores (1–10); attendance % from `attendance.services.student_attendance_stats`; top_3_profiles enriched with match% (score×10) + primary-competency tags; competency rows from all_competency_scores.
- Decisions: page = Annual Passport; scale kept 1–10 (relabeled UI, not converted); Year-in-Review auto-generated from data via new `_build_passport_summary()` in student/views.py.
- CSS scoped under `.sp2` + keyframes prefixed `sp-`, buttons `.sp-btn` (base has `.btn`). Mockup navbar dropped (base has header/sidebar).
- Verified: render test client → 200, overall 8.0/10, attendance 92%, career-matches + report-card present. `manage.py check` clean.

## 2026-07-28 — Fixed all HIGH bugs
- H1 Superadmin GET-deletes: added `@require_POST` to 9 delete views (delete_school/school_admin/teacher/student/parent/class/lesson, esl_product_delete, announcement_delete) + converted 7 GET `<a>` delete links to POST forms with `{% csrf_token %}` (school/school-admin/teacher/student/parent lists, lesson-list, esl-products). announcement already POST; delete_class had no UI link.
- H2 Superadmin blank dates: `date_of_birth`/`enrollment_date`/`joining_date` now `POST.get(...) or None` (onboard_student 1003/1029, onboard_teacher 1254/1296).
- H3 Superadmin orphan User: wrapped create_user + profile.save() in `transaction.atomic()` for onboard_student/teacher/parent (added `transaction` import).
- H4 Teacher no-profile bypass: changed `if teacher_profile and ...` → deny when profile/school missing, on api_save_score, api_save_feedback, api_save_project_feedback, api_generate_report.
- H5 Teacher: validate `assessment_competency_id` exists before ScoreEntry write.
- H6 Teacher: added `@login_required` to teacher_logout.
- H7 Coordinator: bulk_import_view now gates each row's `school_name` against `_coordinator_schools()` — rows outside coordinator's schools fail with "School not assigned to you".
- Verified: `py_compile` OK on 3 view files; `manage.py check` → 0 issues.
- NOT done (out of scope of "HIGH"): CRITICAL leaked OpenRouter key, MED prod hardening, cascade-User-delete on superadmin deletes.

## 2026-07-28 — Full project + all-roles scan
- 6 parallel agents scanned all role apps (views + page bodies) + core models/config. Read-only, no code changed.
- CRITICAL: live OpenRouter API key committed at `test_openrouter.py:3` — rotate + purge history.
- HIGH (all still open from 07-27): superadmin 9 GET-deletes / '' to NOT NULL DateField / orphan User; teacher no-profile ownership bypass + ac_id IDOR + logout no @login_required; coordinator cross-tenant bulk import.
- MED: settings.py not prod-hardened (DEBUG, hardcoded SECRET_KEY + Mailtrap creds, no SSL); superadmin deletes don't cascade User; coordinator global coach dropdown.
- Broken pages: superadmin 11 hardcoded .html sidebar links, parent 10 dead JS nav links, skillpassport Screen-1..11 still unwired. 36/36 role page bodies render OK.
- CLAUDE.md "Current State" is STALE — all 3 model gaps already fixed in migration 0011 (ScoreEntry help_text 1–10, Project.sequence_number, ProjectReport all exist).
- Full detail: memory `esl-audit-2026-07-28.md`.

## 2026-07-27 — All-roles audit
- Ran read-only audit of all 6 roles (superadmin, coordinator, school_admin, teacher, parent, student) via 5 parallel agents.
- Result: 5 HIGH, 9 MEDIUM, several LOW findings. No code changed.
- HIGH: (H1) 9 superadmin delete views accept GET → CSRF-bypass delete; (H2) superadmin onboard_student/teacher crash on blank DOB/date; (H3) orphaned User on onboarding failure; (H4) coordinator bulk-import cross-tenant write (school resolved by name globally); (H5) teacher write-APIs bypassed when coach has no profile/school.
- Verified CLEAN: parent/student no IDOR, school_admin + coordinator dashboard scoping, AUTH decorators.
- Full detail: memory `esl-audit-2026-07-27.md`.

## 2026-07-27 — Sidebar navigation scan (all roles)
- 6 parallel agents scanned every sidebar link per role (URL→view→template on disk).
- Result doc: `SIDEBAR_AUDIT.md`. ~45 non-opening items.
- Student: fully clean (8/8). School Admin worst (14 dead stubs). Super Admin 11 dead, Coordinator 9 coming-soon + 1 mislink, Teacher 5 placeholder + 1 dead, Parent 4 dead + Announcements/Events anchor dup.
- No BROKEN URL / MISSING VIEW cases — every wired {% url %} resolves; issues are unbuilt `href="#"`/hardcoded-.html links and coming-soon stubs.

## 2026-07-24 — Feature: structured student & parent onboarding IDs (slide 2 flow)
- Replaced random `SKILL{year}{rand}` ids with the client's structured, human-readable onboarding ID (`SV-RG-6A-222-26-stu` / `-par`), used as login username + initial password across every onboarding entry point.
- NEW `accounts/onboarding_ids.py` — ID generator (build_id_base, student_id_for, generate_parent_id, parent_id_from_student).
- `superadmin/bulk_import.py`, `superadmin/views.py`, `school_admin/views.py` — onboarding paths use structured ids; parent id derived from first linked student; welcome emails show Login ID.
- Verified: `manage.py check` clean; shell test produced `SV-RG-6A-222-26-stu`/`-par`, collision → `-2-`, parent shares child base.

## 2026-07-24 — Feature: role-based announcement delivery (all 5 roles) + notification bell
- NEW `competencies/announcements.py` delivery helper; `nav_notifications` context processor now serves all roles; superadmin announcement add/edit save publish_to + schools + grades for all types; teacher/coordinator/school_admin got announcements view+url+template; bells rewired to dynamic data.
- Verified: `manage.py check` clean + rolled-back scoping shell test PASS.

## 2026-07-24 — Read-only audit: teacher/, parent/, student/ apps
- Full line-by-line research pass (no code changes) across the 3 apps + root seed scripts.
- Findings: parent/urls.py missing app_name; teacher score/feedback/report school-scoping bypass when profile.school None; duplicated content-type logic; debug prints; seed_student_demo hardcodes 2026-07-20; CLAUDE.md stale re ProjectReport/sequence_number.
- Outcome: no files modified; findings in memory.
