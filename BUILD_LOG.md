# Build Log

Chronological record of completed tasks (per org policy: log after each completed task).

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
