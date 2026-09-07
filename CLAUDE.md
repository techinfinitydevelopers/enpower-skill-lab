# Enpower Skill Lab — Claude Context

## Project
Django-based EdTech platform for skill training labs using the **neoRiSE Competency Framework (Skill Passport)**.

- **Live URL:** www.enpowerskilllab.com (older droplet address enpower.techinfinity.link still resolves)
- **DB:** SQLite (dev)
- **Email:** Mailtrap (sandbox)
- **Auth model:** `accounts.User` with role-based access

## User Roles
| Role | App | Dashboard URL |
|------|-----|---------------|
| Super Admin | `superadmin/` | `/super-admin/dashboard/` |
| Program Coordinator | `coordinator/` | `/coordinator/dashboard/` |
| School Admin | `school_admin/` | `/school-admin/dashboard/` |
| Thinking Coach (Teacher) | `teacher/` | `/teacher/dashboard/` |
| Parent | `parent/` | `/parent/dashboard/` |
| Student | `student/` | `/student/dashboard/` |

## Key Apps
- `competencies/` — Core neoRiSE framework: Pillars, SubPillars, Competencies, Profiles, Projects, Assessments, ScoreEntry, StudentAssessmentFeedback
- `skillpassport/` — Static UI mockup screens (Screen-1 to Screen-11), not yet connected to Django views
- `lms/` — Lesson, LessonResource, LessonVideo
- `schools/` — School, Class models

## neoRiSE Skill Passport — Key Rules
- Score scale: **1–10** (confirmed)
- Max **6 assessments** per project
- Projects are **fully isolated** — no cross-project weightage
- Profile **resets** per project
- **Plug-In** projects merge with parent project (average scores per competency)
- **Annual Passport** = latest score per competency (by `sequence_number`)

### Profiling Engine (4 steps)
1. Profile unlock — need ≥2 primary competencies assessed
2. Weightage — secondary = 10% fixed each; remaining split equally among assessed primaries
3. Profile score = Σ(score × weight)
4. Top 3 profiles selected

## Current State
- Score entry working (teacher can enter scores per student per assessment-competency)
- `ScoreEntry.score` help_text says "1–4" in models.py but DB migration is correct (1–10) — fix help_text
- `Project` model missing `sequence_number` field — needed for annual passport ordering
- `ProjectReport` model does NOT exist yet — needs to be created
- Skill Passport UI screens not yet integrated with Django

## Pending / Next Steps
1. Fix `ScoreEntry` help_text (minor)
2. Add `sequence_number` to `Project` model
3. Create `ProjectReport` model
4. Build report generation engine (calculation logic from `SKILL_PASSPORT_LOGIC.md`)
5. Connect `skillpassport/` UI screens to Django views
6. Confirm: max competencies per assessment (likely 8–10), competency label thresholds

## Important Files
- `SKILL_PASSPORT_LOGIC.md` — Complete scoring & profiling logic documentation
- `competencies/models.py` — Core data models
- `superadmin/views.py` — Largest view file (2600+ lines)
- `teacher/views.py` — Score entry AJAX APIs
