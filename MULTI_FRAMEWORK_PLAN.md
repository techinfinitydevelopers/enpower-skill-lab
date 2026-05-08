# Multi-Framework Development Plan

## Overview

The platform currently supports only the FSL (Foundational Skill Lab) framework with 5 pillars, 17 sub-pillars, and competency-based skill passport logic. Two major changes are required:

1. **Add Kaushal Bodh (KB) pillar to FSL** — a non-consequential competency layer for CDC compliance
2. **Add CSL+ framework support** — a simplified subset of FSL with no profiling/passport logic
3. **Make the platform multi-framework** — school-level framework selection during onboarding

---

## Phase 1: Kaushal Bodh (KB) in FSL

### What is KB?
- A 6th pillar added to the existing FSL framework
- Contains sub-pillars and competencies (initial list provided by client, but admin can also add more)
- Required for CDC compliance

### Editability
- Only this 6th pillar is editable (existing 5 pillars remain read-only)
- Admin can: rename the pillar, add/remove sub-pillars, add/remove competencies under sub-pillars

### Assessment Integration
- KB competencies can be selected alongside existing competencies when creating assessments
- Teacher enters marks (1-10 scale) for KB competencies in the same score entry grid
- Mixed assessments are supported (existing + KB competencies together)

### Calculation Rules
- KB competencies are **completely excluded** from all calculation logic:
  - No profile unlock contribution
  - No weightage calculation
  - No profile scoring
  - No passport impact
- Existing 5 pillar competencies continue with full calculation logic as-is (profiles, passport, everything unchanged)

### KB Report
- A **separate KB report** is generated per project
- Shows only KB competency marks (raw scores)
- Report format to be decided later
- This report is generated alongside the existing Skill Passport report

### FSL School Reports (per project)
1. **Skill Passport Report** — existing logic (profiles, top 3, competency scores) — KB excluded
2. **Kaushal Bodh Report** — KB marks only, no calculations

---

## Phase 2: CSL+ Framework

### What is CSL+?
- A simplified subset of FSL
- Fewer pillars, fewer sub-pillars, fewer competencies
- No skill profiling, no passport logic, no primary/secondary competency mapping

### Learning Pillars Page (CSL+)
- A **new fully editable** Learning Pillars page for CSL+
- Admin can: create/edit/delete pillars, sub-pillars, and competencies
- Completely independent from FSL's Learning Pillars
- Architecture should be generic enough to support any future framework (not just FSL/CSL+)

### Assessment & Scoring
- Same assessment logic as FSL (projects, assessments, competency mapping)
- Teacher enters marks on 1-10 scale (same score entry grid)
- No profiling step — no primary/secondary, no profile unlock, no weightage, no top 3 profiles

### CSL+ Reports (per project)
1. **Cumulative Score Report** — assessment-wise average scores + project total score
2. **Kaushal Bodh Report** — same as FSL, KB marks only (KB is present in CSL+ as well)

---

## Phase 3: School-Level Framework Selection

### School Onboarding
- New field `framework_type` added to School model (choices: FSL, CSL+, extensible for future)
- Super Admin selects framework when onboarding a school
- One school = one framework

### Impact on Projects
- Currently projects are shared across all schools (not school-specific)
- With framework selection at school level, projects need to be tagged with a framework
- Admin selects framework (FSL/CSL+) when creating a project
- Teachers only see projects matching their school's framework
- Competency picker shows only the relevant framework's pillars/competencies

### Future Extensibility
- Architecture must support creating entirely new frameworks from scratch
- Not hardcoded to FSL/CSL+ — any new framework can be created with custom pillars, sub-pillars, competencies
- Each framework has its own Learning Pillars configuration

---

## Existing Skill Passport Flow (Unchanged for FSL)

1. Admin creates Project → max 6 Assessments → competencies mapped per assessment
2. Teacher enters scores (1-10) per student per competency per assessment
3. Profile unlock: minimum 2 primary competencies assessed required
4. Weightage: secondary = 10% fixed each, remaining split equally among assessed primaries
5. Profile score = sum of (score × weight)
6. Top 3 profiles selected per project
7. Projects are fully isolated — no cross-project weightage, profile resets per project
8. Plug-In projects merge with parent project (average scores per competency)
9. Annual Passport = latest score per competency (by sequence_number)

**KB competencies are excluded from steps 3-9.**

---

## Architecture Notes

- KB pillar needs a flag/toggle to mark it as non-consequential (excluded from passport calculations)
- CSL+ framework needs its own separate Learning Pillars data (not shared with FSL)
- Report generation should check framework type and generate appropriate reports
- Score entry UI remains the same across all frameworks — only backend calculation logic differs

---

## Client Action Items (from meeting)
- ESL to provide CSL+ framework slide deck (pillars, sub-pillars, competencies)
- ESL to provide Kaushal Bodh competency list
- ESL to provide a 3rd dummy framework for testing generic architecture
- ESL to upload dummy student data for testing (using bulk import)

## Techinfinity Action Items
- Internal discussion on refactoring effort
- Prepare formal proposal with timeline and cost estimate
- Implement multi-framework architecture

---

*Based on ESL x Techinfinity meeting — April 15, 2026*
*Last updated: May 7, 2026*
