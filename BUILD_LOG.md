# Build Log

Chronological record of completed tasks (per org policy: log after each completed task).

## OPEN — Toasts still not visible on the teacher scoring page (2026-08-24)

**Status: unresolved. Parked at the user's request.** Everything below is deployed and verified; the toast still does not appear on screen for the user.

Symptom: `showToast('TEST', 'success')` in the browser console returns
`<div class="toast toast-success closing" data-toast></div>` — **with no children** — and nothing renders. The element is created and auto-dismisses on schedule.

Ruled out (each checked, not assumed):
- Server markup — the page serves `fb-save-btn`, `notify()`, `saveStudentFeedback`, and the toast asset tags.
- Asset delivery — `toast.css` and `toast.js` both return 200; the served `toast.js` is byte-identical to the repo once CRLF/LF is normalised, and its `showToast()` does populate `innerHTML` with icon/title/message/close/progress.
- Script order — `toast.js` now loads before `{% block extra_js %}` in all six role base templates (it was after, in teacher + superadmin; fixed in `691f78b`).
- Silent failure paths — the `if (window.showToast)` guards were replaced with `notify()`, which falls back to building the toast itself and logs a warning. No warning appears in the user's console.
- Missing call sites — the grid's `saveScore()` genuinely had no toast, no else branch and no `.catch()`; added in `9c1fd3b`.
- CSS visibility — `.toast` was `opacity:0; translateX(120%)` and depended entirely on the `esl-toast-in` animation (keyframes had only `to`). Base state is now visible with the animation as decoration, plus a reduced-motion block (`5611155`).
- Browser HTML caching — `NoStoreHTMLMiddleware` added (`35b7400`); assets cache-busted to `?v=3`.

Leading hypothesis, **not yet confirmed**: a browser extension is stripping the children after creation. The user's console shows `content.js:13 FloatingButton ~ config: {disabledSites: Array(0), enable: true, hasToast: true, position: 501}` and heavy `wordSelectionTranslate.tsx` output. Our class name `.toast` is generic enough to collide with an extension that has its own toast feature.

Next step when resumed: reproduce in an Incognito window (extensions off). If the toast appears there, namespace the markup/CSS to `esl-toast-*` so nothing external can match it. If it does not appear there, the fault is ours and the empty-children behaviour needs to be traced live in the DOM.

Note on process: three "fixes" were announced as resolving this before the cause was actually known. Verification only ever showed that the code reached the page, which does not establish that the toast renders.

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

## 2026-08-26 — Deck cross-check, framework/profile/project seeding, engine steps 3-5
Reference: `Dashboard Slide.pptx` (24 slides). Everything below was checked against it.

### Engine (`competencies/engine.py`)
- Profiling steps 3, 4, 5 implemented (slide 16). Previously only 1-2 + a single ranking.
  - Step 3: narrow to the student's top `PROFILING_COMPETENCY_POOL = 6` competencies.
  - Step 4: shortlist `PROFILE_SHORTLIST_COUNT = 5` on the **primary-only** score.
  - Step 5: re-rank that shortlist on the full primary+secondary score -> top 3.
- `get_common_strengths()` added — primary competencies shared by >=2 reported profiles.
- KB rule changed: `get_competency_scores_for_project(include_kb=True)` by default;
  KB is now stripped inside `run_profiling_engine` only. KB shows in the competency
  report, never in profiles.
- `generate_annual_passport` now keys profiling off the **student's own** school
  framework. It previously did a global scan of all projects, so a CSL+ student
  could get career matches because some other school ran FSL.

### Models / migration `0025`
- `ProjectReport.common_strengths` JSONField added.
- `ASSESSMENT_TYPE_CHOICES` -> `[Presentation, Written, Oral/Portfolio]` (slide 8/9)
  with a data migration remapping the old labels (reversible).

### UI
- "What links these matches" block (common strengths) on report + passport, with CSS.
- Project-level coach feedback (`StudentProjectFeedback`) now rendered — teachers
  had been able to save it for a while but nothing displayed it.

### Seed + verification (new files at repo root)
- `seed_frameworks.py` — FSL 5 pillars/17 sub-pillars/68 comps; CSL+ 3/13/52 with
  KaushalBodh inside it; CSL Foundation 1/3/12. KB moved off FSL per slides 5/6.
- `seed_profiles.py` — 15 profiles x (3 primary + 2 secondary), deliberately
  overlapping so step 5 has common strengths to report.
- `seed_projects.py` — schools onto 3 frameworks, 32 projects incl. plug-ins,
  104 assessments, 407 mappings, 459 scores, 407 rubric rows, feedback.
- `verify_reports.py` — 46 assertions, all pass.
- `verify_pages.py` — 35 rendered-HTML assertions, all pass.

### Verified
- 46/46 engine + 35/35 page checks. FSL top career match == seeded target profile
  for all 18 FSL reports; CSL+/CSL Foundation reports carry 0 profiles; KB present
  in competency reports and absent from every profile weightage; plug-in scores
  average into the parent project.
- Rendered through the real view+template stack, not just the ORM. **Not** verified
  in a real browser (CSS/JS behaviour) — dev server left running on :8005.

### Follow-up same day — profiling pool 6 -> 10
Slide 16's prose says step 3 keeps the student's "top 5-6 competencies", but a
pool of 6 starves step 5 ("identify the top 3 profiles") — 11 of 18 FSL reports
unlocked only ONE profile. Slide 20's worked example lists ten codes under a
"(10)" header. Ten is the only reading where both steps hold, so
`PROFILING_COMPETENCY_POOL = 10`.

Measured across the 18 FSL reports:

    pool  profiles per report              common strengths
      5   18x one                          0/18
      6   11x one, 7x two                  7/18
      8   5x one, 8x two, 5x three         13/18
     10   5x two, 13x three                15/18
     12   18x three                        18/18

Re-verified after the change: 46/46 engine, 35/35 page.

### Follow-up — "Kaushal Bodh pillar" checkbox on Learning Pillars
`add_pillar` hardcoded `is_kb=False` in both view branches and no form exposed the
flag, so a pillar *named* "Kaushal Bodh" was an ordinary pillar: its competencies
flowed into the Skill Passport AND into career matches, while the KB report stayed
empty. This is the same shape as the earlier "KB1.C4 in Top 5" confusion, where the
name said KB but `is_kb` was False.

- Checkbox added to the Add Pillar form and the Edit Pillar modal.
- `add_pillar` / `rename_pillar` / `edit_pillar` now read `is_kb` from POST.
- `openLpEditPillar()` takes `isKb` so re-saving the modal cannot silently clear it.
- Success message spells out the consequence when the box is ticked.

Verified end to end through the real form: unchecked -> False, checked -> True,
toggle off/on via edit works; a scored is_kb competency under FSL then appeared in
the all-competency report, in Top 5, and in the KB report, and in NO profile.

### Fix — multi-line {# #} comments rendering as page text (third occurrence)
Four comments written earlier the same day spanned two lines each, so Django
printed them verbatim on the page: `_report_body.html` (x2), `_passport_body.html`,
`learning-pillars.html`. All collapsed to single-line `{# #}`; a full *.html scan
now reports zero.

Guard added so this cannot ship again: `verify_pages.py` `fetch()` flags any page
whose visible text contains `{#`, `#}`, `{% ` or `{{ `, and fails the run with the
URL plus surrounding text. Super Admin pages (Learning Pillars, Profiles &
Competencies, Project & Assessment) added to the suite for the same reason — the
leak surfaced there and nothing was rendering those pages. Suite is now 42 checks.

### Decisions taken 2026-08-26
- `PROFILING_COMPETENCY_POOL = 10` CONFIRMED by the product owner, settling
  slide 16's "top 5-6" prose against slide 20's ten-item worked example.
- Step-4 unlock stays slide 16 step 1's "at least 2 primary".
- Kaushal Bodh keeps Option A: in Top 5 / all skills / sub-pillar / Overall
  Level, out of profiles only. Reviewed on a real FSL report and accepted.

### PARKED — to discuss, do not implement
0. Slide 8/10 "Checklist for student output" — no such field on Assessment.
   Small: model field + migration + the Project & Assessment form.
1. Deck limits unenforced: slide 8 says max 6 assessments per project and max 8
   competencies per assessment. Nothing validates either, and seed_csl_kb_scores
   already put 12 KB competencies into an assessment holding 3. Confirm whether
   these are hard limits before enforcing.
1. Should "top 3 profiles" always be three? Currently shows however many unlock
   (13 of 18 FSL reports show 3, five show 2). Forcing three needs pool = 12 and
   admits ~40% matches.
2. Should students/parents see career-match profiles at all? Slide 15 says
   competency level only, profiles teacher-side (slide 14). Current build shows
   them to both. Options: keep / remove from student+parent / annual-only.

### Teacher Score Viewing — spec slide 14
New page at `/teacher/score-viewing/`, four views over the same scores:

    Student Level                 Class Level
      - Project Wise                - Percentile Competency
      - Agg Competency Wise         - Project Level Aggregate Comparative

- Project Wise: one block per project, every mapped competency listed even when
  unscored so "Pending [Add score]" stays visible and links to score entry.
- Agg Competency Wise: one row per competency across all projects, repeats
  averaged into a single figure with the contributing projects named.
- Percentile Competency: class spread per competency (p25 / median / p75, low,
  high) drawn as a bar, plus the selected student's own percentile marked on it.
  Each student contributes ONE aggregated figure per competency so a competency
  assessed twice can't weight that student twice.
- Project Level Aggregate Comparative: projects side by side with class average,
  spread and coverage (how much of the class is actually scored — a flattering
  average built on three students is labelled as such). Strongest/weakest tagged.

Also: "Repeated competencies to be aggregated" note, Show Grade / Show Project /
Student filters, and a Generate Profile Report button wired to the existing
api_generate_report.

Code lives in `teacher/score_views.py` rather than `teacher/views.py`, which was
already ~1700 lines. 15 assertions added to verify_pages.py — suite now 57.

### Fix — stale reports were invisible; Generate button read as per-assessment
Raised by the user: entering scores for Assessment 1 puts "Generate Reports for
All Students" directly below the table, which reads as an assessment-level
action. It is project-level, and pressing it early builds the report from a
fraction of the project.

Digging in found the worse half: `is_outdated` was only ever written as False
(engine.py) and never True, so the flag was dead. The UI for it already existed
— a banner on the student's report ("Scores changed after this report") and an
"outdated" tag on the coach's Score Viewing table — and neither had ever
appeared. A coach who generated after assessment 1 left students on a partial
report with nothing indicating it.

1. `competencies/signals.py` — post_save/post_delete on ScoreEntry marks the
   matching ProjectReport outdated. A signal, not a call inside score entry, so
   bulk import / admin / shell writes cannot miss it. Plug-In scores invalidate
   the PARENT project's report, since that is where they merge (slide 24).
2. `api_project_details` now returns assessments_total / assessments_scored and
   a per-assessment has_scores; the Generate block shows "N of M assessments
   scored" and warns when any are unscored.
3. Button relabelled "Generate Project Reports (all assessments)".

Verified: fresh report not outdated -> editing a score flags it -> regenerating
clears it -> deleting a score flags it; and the student-facing banner appears
and disappears with it. Suites now 49 engine / 61 page.

### Dashboard clean-up — "Clean up" tab of ESL dashboard Changes Document.docx
Removed tabs and widgets the client asked to drop. Almost all of them pointed at
static .html filenames that were never wired to a view, so they 404'd or did
nothing when clicked.

Super Admin
- dashboard: Assessment Completion Heatmap widget, LMS Usage Summary widget
- sidebar: School Details link, LMS Management dropdown, Monitoring dropdown
  (which took Assessment / Attendance / LMS Monitoring and Multi-school
  Comparison with it)
Program Coordinator
- sidebar: LMS Monitoring dropdown, Multi-School Comparison
Thinking Coach
- Student Profile removed — a dead href="#"; Student List already opens the same
  view via its eye icon
- Events: the "merge with announcements" row was first read as "replace the
  dropdown with one Announcements link". Wrong reading, reverted. The real
  problem was that Event Calendar had no page at all — a sidebar entry pointing
  at href="#", no URL, no view, no template — so events the Super Admin
  published to Thinking Coaches were only reachable buried in the Announcements
  list. Only Student and Parent had a working event page.
  Built `teacher_event_calendar` at /teacher/events/ using the same
  `announcements_for_user(user, 'event')` targeting every other role uses, and
  pointed both sidebar links at their real pages.

Also cleaned seven now-unreachable entries from the filename -> nav-id map in
static/js/superadmin/sup-admin-dash.js and re-ran collectstatic.

Verified by rendering each dashboard: 24 assertions covering both what must be
gone and what must survive, plus the merged Announcements page opening.

NOT done — the document's row reads "School Admin / Remove multi-school tab",
but School Admin has no such tab; the Multi-school entries live under Super
Admin and Coordinator and were removed there. Worth confirming that was meant.

### "Need to work on" tab — the three real bugs
From ESL dashboard Changes Document.docx. Items 4 (academic year locking), 11
(check tabs with other PC credentials) and 12 (parent credentials) were dropped
by the user.

**GR number was mandatory.** `gr_number = CharField(unique=True)` with no
blank/null. Now optional, stored as NULL rather than '' — `unique` permits many
NULLs but only one empty string, so '' would have rejected the second student
without one. Removed from the onboarding form's required set and from both
bulk-import required lists; the duplicate check now only fires on a supplied
value. Verified two students save with no GR number while a genuine duplicate is
still rejected.

**Bulk upload "not working" was the sample file.** The sample hardcoded
"Delhi Public School", which exists in no environment, so downloading the sample
and uploading it back failed every student / teacher / school-admin row with
"School ... not found". The school column now offers the real schools and the
example row uses one of them. Three further defects found on the way:
  - the inline dropdown list is capped near 255 chars by Excel, which silently
    truncated 8 schools to 7; long lists now live on a hidden sheet
  - the coordinator sample left the required `id_proof` blank, so its very first
    import always failed; any required cell left blank is now filled
  - both school-admin sample rows pointed at one school, and a school takes only
    one admin, so row 2 always failed; rows now spread across schools that are
    actually free, and never exceed that count
  - duplicate coordinator PAN/Aadhaar surfaced the raw
    "UNIQUE constraint failed: coordinator_programcoordinator.pan_number"
    instead of naming the field
  4 of 5 role samples now import cleanly; coordinator still reports its PAN as
  taken, which is correct — the placeholder PAN belongs to a coordinator seeded
  in Dec 2025.

**Parent onboarding "not submitting" was hidden required fields.** The form has
8 steps and hides all but the current one with `display: none`. Pressing Submit
on step 8 validates the whole form; an empty required field in a hidden step
cannot be focused, so the browser logs "not focusable" and refuses silently.
There was no submit handler at all, and `validateCurrentStep()` only checked
fields carrying a custom validator, not HTML5 `required`, so Next let users past
empty ones. `static/js/superadmin/stepped-form-submit.js` now reveals the step
holding the first invalid control and reports it there, and blocks Next on an
invalid step. Applied to onboard-parent and onboard-teacher, which share the
defect. Also stopped the student picker rendering "Name - 6 ()" now that GR
number can be blank.

### School Admin pages that had no URL, view or template
The changes document lists Thinking Coaches ("should be able to see TC profile"),
Class Overview and Class Attendance as not working. None of them existed - the
sidebar entries were href="#". Built in `school_admin/pages.py`, all read-only,
since School Admin is view-only per PPT slide 51.

- Thinking Coaches: coaches at this school with the classes each one runs
- TC profile: contact, professional detail, assigned classes, onboarding checks.
  Looked up scoped to the admin's school, so another school's coach is a 404
  rather than a blank page.
- Class Overview: coach, student count and sessions held per class. Students
  carry their own grade/division rather than a Class FK, so they are counted by
  that pair - which also surfaces grade/division pairs holding students with no
  Class record at all, listed separately as unregistered.
- Class Attendance: per-class percentage and the sessions behind it, filterable
  by grade and division. A late arrival counts as attending. The session count
  sits beside every percentage, because a class with one marked session
  otherwise reads the same as a class with thirty.

Verified with 23 assertions covering all four pages, the cross-school 404, and
the sidebar now linking to real URLs.

Not touched: Class Performance is also a dead href="#" but the document did not
list it.

### Remaining changes-document work completed
Shared report panels, the two report pages built on them, email templates, and
the last dead-navigation removals.

**`competencies/report_panels.py`** — the four grade-wise panels from slide 52,
computed for any set of schools. One module rather than three: Super Admin (all
schools), Program Coordinator (mapped) and School Admin (one) show the same
panels over different scopes, and every function takes the school ids so the
caller owns the scoping and cannot widen it by accident. Bars arrive sized as a
percentage of the panel maximum so templates draw charts without arithmetic.
Insights are suppressed when every grade holds the same value, where "highest"
and "lowest" would both be true of any grade.

**Super Admin — Reports & Analytics** at /super-admin/reports/analytics/, all
four panels with a school filter. The Settings section (System Settings,
T&C/Privacy, Billing) was hidden as agreed, Download Reports removed from the
sidebar, and two dashboard quick actions repointed — "Download Reports" led to
the student list and "Settings" to the profile page.

**Program Coordinator — Reports** at /coordinator/reports/, three panels scoped
to mapped schools. Top 3 Skill Profiles is not built for this role at all rather
than being fetched and hidden: slide 53 marks Skill Passport "n/a" for the
coordinator. Removed Teacher Performance, the whole Assessments section and
Download Reports, and deleted the dashboard's Teacher Performance Summary card,
which showed hardcoded figures ("42 teachers") with fixed bar widths.

**`competencies/emails.py`** — the three templates from the document's Email
Template tab, wording followed exactly: onboarding with credentials,
announcement/event/newsletter, and password reset. Placeholders are filled from
real records, and a missing value drops its line rather than sending "School:"
with nothing after it. Bulk import's welcome mail now goes through it.

**Coordinator bank details** are no longer required by the importer. The model
and the onboarding form already treated them as optional — only the two
bulk-import required-field lists still demanded them.

Verified: 23 assertions on the email templates and the blank-bank-details import,
plus the report pages checked for every panel, correct scoping, and the absence
of skill profiles for the coordinator. Suites unchanged at 49 / 63.

### School Admin reports, and the last dead navigation entries
Every dashboard now has zero dead navigation entries.

**Dashboard panels.** The School Admin dashboard already showed the four
grade-wise figures, but as plain tables from a second implementation in
`attendance/services.py`. It now renders the shared slide-52 component, so all
three reporting roles draw from one module and cannot drift apart. The old
helpers were used by nothing else.

**Download Reports** at /school-admin/reports/download/ shows the same four
panels with an Excel export — one sheet per panel, written from the same data
the screen renders, so the file and the page cannot disagree. Column widths are
sized from the longest value so nothing arrives as ####.

**Removed:** eight dead School Admin entries (Class Performance, Assessment
Reports, Class Assessment Summary, Student Attendance, Teacher Attendance,
Attendance Reports, School Reports, Student Reports), the Assessments and
Attendance sections left holding nothing, and Academic Year Locking from Super
Admin.

One mistake worth recording: the first attempt at removing the empty sections
used a regex whose `.*?` ran past a section boundary and took the working Users
section with it — Thinking Coaches, Student List and Parent List all vanished.
Caught by reading the diff, reverted with git, and redone by locating each
section from its toggle id and asserting the block contained exactly one anchor
before deleting.

Verified with 20 assertions covering the dashboard panels, the download page,
the workbook's four sheets and its contents, plus a full dead-link audit of all
six dashboards. Suites unchanged at 49 / 63 / 23.

### Still open (unchanged by this pass)
- Slide 14 teacher views: Class Level, Percentile Competency, Project Level
  Aggregate Comparative, Generate Profile Report — none exist.
- Slide 15 says students should see competency level only, **not** profiles;
  current build shows them. Product decision pending.
- Seeded competency/profile content is realistic dummy data, not the client's.
- Production not touched — all of the above is local only.
- Toast visibility bug (earlier) still OPEN.

---

## 2026-08-31 — Real email via ZeptoMail; Students and Parents excluded

**Commits:** `31f758c`, `a7ee384` — live on production.

### What changed
Mail was going to a Mailtrap sandbox with the credentials hardcoded in
`settings.py`, so nothing had ever reached a real inbox. SMTP settings now come
from the environment (`.env`, gitignored), defaulting to ZeptoMail, with
`.env.example` documenting every value.

Students and Parents are no longer emailed at all. Their login IDs are
system-generated and handed over by the school, and neither role can change its
own password. The rule is `settings.EMAIL_SUPPRESSED_ROLES` and it is enforced
in exactly one function, `competencies/emails.py::_send`.

To make the gate unavoidable, the six views that called `send_mail` directly now
call `send_raw`, which applies it. **No `send_mail` call remains anywhere outside
`competencies/emails.py`**, and the suite asserts that.

`normalise_role()` folds `'Student'`, `'STUDENT'` and `'Thinking Coach'` to one
form, because the bulk importer passes display labels while the views pass role
codes; without it the importer would have walked straight past the gate.

### Bugs this surfaced
- Three onboarding emails carried a `http://127.0.0.1:8000/login/` link. Harmless
  against a sandbox, useless the moment mail is real. Links now build from
  `settings.SITE_URL`.
- The Student and Parent success messages said "Credentials sent to ..." — now a
  lie. They show the login ID and password on screen instead, which is the only
  way the admin sees the password they have to hand over.
- No `EMAIL_TIMEOUT` was set, so a hung SMTP server would have held an onboarding
  request until gunicorn killed the worker. Now 20s.
- **DigitalOcean blocks outbound 25, 465 and 587.** The first production send sat
  until it timed out. ZeptoMail also answers on 2525, which is open; STARTTLS and
  AUTH both succeed there. The server's `.env` uses 2525, local uses 587.

### Who gets mail
| Role | Onboarding email |
|------|------------------|
| School Admin, Thinking Coach, Program Coordinator, Super Admin | sent |
| Student, Parent | suppressed and logged |

Both manual onboarding and bulk upload pass through the same gate.

### Verification
`verify_email.py` — 34 checks: configuration, the gate in every spelling the
callers use, the gate under a real `send_onboarding` call on the locmem backend,
no bypass, and the role named at each of the six call sites. 34/34 locally and on
the server, including a live send from each. Existing suites unchanged at 49 / 63.

### Still open
- ZeptoMail domain `enpowerskilllab.com` is verified; SPF/DKIM alignment not
  checked, so first real sends should be watched for spam placement.
- Announcement and password-reset templates exist in `competencies/emails.py` but
  nothing calls them yet — no flow is wired to either.
- Toast visibility bug still OPEN.

---

## 2026-08-31 (later) — Branded HTML emails

**Commit:** `9783ae2` — live on production.

Emails were going out as bare plain text. They now go as multipart/alternative:
the existing text stays as the fallback, with a table-based HTML version
alongside it.

Three templates extend one layout in `competencies/templates/emails/` —
`onboarding`, `announcement`, `password_reset`. The markup is deliberately old
fashioned (tables, inline styles, no shorthand properties) because mail clients
are. Colours follow the dashboard: `#5b1f6f` with the logo's gold as an accent
rule.

The logo is an **inline part** (`cid:enpowerlogo`), not a hosted URL, so it
renders with remote images blocked and survives the site moving to another
domain — which matters given the planned Railway move.
`static/assets/images/email-logo.png` is the brand logo at 400px **flattened
onto white**; transparency renders as black in some clients.
`mixed_subtype = 'related'` is what makes the cid resolve — without it the logo
arrives as a detached attachment.

Also fixed: the plain-text onboarding body said "log in using the above
credentials" with nothing to click. It now carries the login link.

### Verification
`verify_email.py` — 61 offline checks (was 34). Each template renders with no
leftover template syntax, keeps its text part, references the logo, and has an
attachment whose `Content-ID` matches the cid. A live run sends all three.
64/64 from the laptop and 64/64 from the droplet; both sets landed in Gmail's
Inbox, not spam. Other suites unchanged at 49 / 63.

### Still open
- Announcement and password-reset templates are built but **no flow calls
  them** — nothing sends an announcement email today.
- Toast visibility bug still OPEN.
