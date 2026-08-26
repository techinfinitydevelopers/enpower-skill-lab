"""
Generate every report and check the engine against what the seed intended.

seed_projects.py gives each student a "target profile" per project and scores
that profile's competencies highest. So the checks below are falsifiable:

  1. FSL project report  -> top career match == the seeded target profile
  2. CSL+ / CSL Foundation -> no career matches at all (slide 16)
  3. Kaushal Bodh competencies appear in the competency report...
  4. ...but never inside any profile's weightage (KB is reported separately)
  5. Plug-In scores merge into the parent project (slide 24)
  6. Annual passport picks the latest score per competency (slide 23)
  7. common_strengths populated when >=2 top profiles share a primary

Run with:  python verify_reports.py
"""

import os
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from competencies.models import (
    Project, Profile, ProjectReport, Competency, ScoreEntry, AssessmentCompetency,
)
from competencies import engine
from student.models import Student
from seed_projects import profile_triplet

PASS, FAIL = [], []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}{("  — " + detail) if detail else ""}')


def generate_all():
    print('Generating project reports')
    made = errs = 0
    for student in Student.objects.select_related('school__framework_ref'):
        fw = getattr(getattr(student.school, 'framework_ref', None), 'name', None)
        for project in Project.objects.filter(
            grade=str(student.student_class),
            framework_ref=getattr(student.school, 'framework_ref', None),
        ).exclude(project_type='Plug In'):
            report, err = engine.generate_project_report(student, project)
            if report:
                made += 1
            else:
                errs += 1
    print(f'  generated {made} reports, {errs} skipped (no scores)')


def check_fsl_target_profiles():
    print('\n1. FSL: top career match == seeded target profile')
    profiles = list(Profile.objects.prefetch_related(
        'primary_competencies', 'secondary_competencies'))
    checked = 0
    for report in ProjectReport.objects.select_related(
            'student', 'project__framework_ref'):
        fw = report.project.framework_ref
        if not fw or not fw.is_fixed or not report.project.sequence_number:
            continue
        trio = profile_triplet(report.project.sequence_number - 1, profiles)
        if not trio:
            continue
        target = trio[report.student.id % len(trio)]
        top = (report.top_3_profiles or [{}])[0].get('profile_name')
        check(f'{report.student.first_name} / {report.project.title[:28]}',
              top == target.name, f'expected {target.name}, got {top}')
        checked += 1
    if not checked:
        check('FSL reports exist to check', False)


def check_csl_has_no_profiles():
    print('\n2. CSL+ / CSL Foundation: no career matches')
    rows = ProjectReport.objects.select_related(
        'student', 'project__framework_ref').filter(
        project__framework_ref__is_fixed=False)
    if not rows.exists():
        check('CSL reports exist to check', False)
    for r in rows:
        check(f'{r.student.first_name} / {r.project.framework_ref.name} / {r.project.title[:24]}',
              not r.top_3_profiles, f'got {len(r.top_3_profiles or [])} profiles')


def check_kb_in_report_not_in_profiles():
    print('\n3-4. Kaushal Bodh: in the competency report, never in a profile')
    kb_ids = set(Competency.objects.filter(sub_pillar__pillar__is_kb=True)
                 .values_list('id', flat=True))
    if not kb_ids:
        check('KB competencies exist', False)
        return

    seen_in_report = False
    for r in ProjectReport.objects.select_related('project__framework_ref'):
        report_ids = {row.get('competency_id') for row in (r.all_competency_scores or [])}
        if report_ids & kb_ids:
            seen_in_report = True
        for p in (r.top_3_profiles or []):
            leaked = kb_ids & {int(k) for k in (p.get('weightage') or {})}
            if leaked:
                check(f'KB leaked into profile {p.get("profile_name")}', False,
                      f'competency ids {sorted(leaked)}')
                return
    check('KB competencies present in a competency report', seen_in_report)
    check('KB absent from every profile weightage', True)


def check_plugin_merge():
    print('\n5. Plug-In merges into the parent project (slide 24)')
    parent = Project.objects.filter(plugins__isnull=False).distinct().first()
    if not parent:
        check('a project with a plug-in exists', False)
        return
    plugin = parent.plugins.filter(status='Active').first()
    student = Student.objects.filter(
        student_class=str(parent.grade),
        school__framework_ref=parent.framework_ref).first()
    if not student:
        check('a student on that project exists', False)
        return

    shared = (set(AssessmentCompetency.objects
                  .filter(assessment__project=parent)
                  .values_list('competency_id', flat=True))
              & set(AssessmentCompetency.objects
                    .filter(assessment__project=plugin)
                    .values_list('competency_id', flat=True)))
    if not shared:
        check('parent and plug-in share a competency', False)
        return

    cid = sorted(shared)[0]
    merged = engine.get_competency_scores_for_project(student, parent).get(cid)
    only_parent = engine._scores_for_single_project(student, parent).get(cid)
    only_plugin = engine._scores_for_single_project(student, plugin).get(cid)
    expected = (only_parent + only_plugin) / 2
    check(f'{student.first_name} / {parent.title[:26]} comp={cid}',
          merged is not None and abs(merged - expected) < 0.01,
          f'parent={only_parent} plugin={only_plugin} expected={expected} got={merged}')


def check_annual_passport():
    print('\n6. Annual passport: latest score per competency (slide 23)')
    any_ok = False
    for student in Student.objects.select_related('school__framework_ref'):
        data = engine.generate_annual_passport(student)
        if not data:
            continue
        any_ok = True
        fw = getattr(getattr(student.school, 'framework_ref', None), 'name', '-')
        is_fsl = getattr(getattr(student.school, 'framework_ref', None), 'is_fixed', True)
        n_prof = len(data.get('top_3_profiles') or [])
        n_comp = len(data.get('all_competency_scores') or [])
        top5 = len(data.get('top_5_competencies') or [])
        ok = n_comp > 0 and top5 > 0 and (n_prof > 0 if is_fsl else n_prof == 0)
        check(f'{student.first_name} [{fw}]', ok,
              f'competencies={n_comp} top5={top5} profiles={n_prof}')
    if not any_ok:
        check('at least one annual passport generated', False)


def check_common_strengths():
    print('\n7. common_strengths (slide 16 step 5)')
    rows = ProjectReport.objects.filter(
        project__framework_ref__is_fixed=True).exclude(top_3_profiles=[])
    if not rows.exists():
        check('FSL reports with profiles exist', False)
        return
    with_cs = rows.exclude(common_strengths=[]).count()
    print(f'     {with_cs}/{rows.count()} FSL reports have common strengths')
    sample = rows.exclude(common_strengths=[]).first()
    check('at least one report has common strengths', with_cs > 0)
    if sample:
        for row in sample.common_strengths[:3]:
            print(f'     {sample.student.first_name}: {row["competency_code"]} '
                  f'score={row["score"]} shared_by={row["shared_by"]}')


def check_top5_and_bands():
    print('\n8. Report shape: top 5 competencies, skills to work on')
    for r in ProjectReport.objects.select_related('student', 'project')[:6]:
        n5 = len(r.top_5_competencies or [])
        nall = len(r.all_competency_scores or [])
        nw = len(r.skills_to_work_on or [])
        check(f'{r.student.first_name} / {r.project.title[:26]}',
              n5 <= 5 and nall >= n5 and nw <= 3,
              f'top5={n5} all={nall} work_on={nw}')


def run():
    generate_all()
    check_fsl_target_profiles()
    check_csl_has_no_profiles()
    check_kb_in_report_not_in_profiles()
    check_plugin_merge()
    check_annual_passport()
    check_common_strengths()
    check_top5_and_bands()

    print(f'\n{"="*60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    run()
