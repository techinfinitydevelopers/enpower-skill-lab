"""
Make sure every CSL project actually assesses its framework's Kaushal Bodh
competencies.

`seed_projects.py` fills CSL projects from a rolling slice of the framework's
competency pool, and `competency_pool()` sorts KB last — so a project's slice can
miss KB entirely and the student's Kaushal Bodh report comes out empty even
though the framework carries a KB pillar. KB is the whole point of the CSL
frameworks (deck slides 5/6), so it should never be absent.

Idempotent — re-running just rewrites the scores.

Run with:  python seed_csl_kb_scores.py
"""

import os
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from competencies.models import (
    Framework, Competency, Project, AssessmentCompetency, ScoreEntry,
    RubricCriterion,
)
from competencies import engine
from student.models import Student

BANDS = {
    'band1_text': 'Needs prompting at each step.',
    'band2_text': 'Completes with occasional help.',
    'band3_text': 'Completes accurately and independently.',
    'band4_text': 'Completes and improves on the method.',
}


def run():
    total_scores = 0

    for fw in Framework.objects.filter(is_fixed=False):
        kb_comps = list(
            Competency.objects
            .filter(sub_pillar__pillar__framework_ref=fw,
                    sub_pillar__pillar__is_kb=True, status='Active')
            .select_related('sub_pillar')
            .order_by('sub_pillar__sp_number', 'code')
        )
        if not kb_comps:
            print(f'{fw.name}: no KB competencies, skipped')
            continue

        projects = list(Project.objects.filter(framework_ref=fw)
                        .exclude(project_type='Plug In')
                        .order_by('grade', 'sequence_number'))
        print(f'\n{fw.name} — {len(kb_comps)} KB competencies across {len(projects)} project(s)')

        for p in projects:
            assessment = p.assessments.order_by('order').first()
            if not assessment:
                continue

            students = list(Student.objects.filter(
                student_class=str(p.grade), school__framework_ref=fw))
            if not students:
                continue

            for i, comp in enumerate(kb_comps):
                ac, _ = AssessmentCompetency.objects.get_or_create(
                    assessment=assessment, competency=comp,
                    defaults={'order': 60 + i, 'comp_type': 'individual'},
                )
                RubricCriterion.objects.get_or_create(
                    assessment=assessment, competency=comp, defaults=BANDS)

                for s in students:
                    # Spread scores across the bands so the report shows
                    # Very Strong / Strong / Emerging rather than one flat value,
                    # and vary by project so "latest score wins" has a choice.
                    base = 4 + ((s.id + i) % 7)                  # 4-10
                    val = max(1, min(10, base + ((p.sequence_number or 1) - 2)))
                    ScoreEntry.objects.update_or_create(
                        student=s, assessment_competency=ac, defaults={'score': val})
                    total_scores += 1

            print(f'  g{p.grade:<3} {p.title[:34]:36} -> "{assessment.name}"  '
                  f'{len(students)} student(s)')

        for s in Student.objects.filter(school__framework_ref=fw):
            for p in projects:
                if str(p.grade) == str(s.student_class):
                    engine.generate_project_report(s, p)

    print(f'\n{total_scores} score entries written, reports regenerated')

    print('\nVerification — every CSL student should now have a KB report')
    for s in Student.objects.filter(
            school__framework_ref__is_fixed=False).select_related('school__framework_ref'):
        rep = engine.build_kb_report(s)
        fw = s.school.framework_ref.name
        if not rep:
            print(f'  EMPTY  {s.first_name} [{fw}]')
            continue
        groups = ', '.join(f'{g["name"].split(":")[0]} {g["average"]}' for g in rep['groups'])
        print(f'  OK     {s.first_name:8} [{fw:16}] {rep["count"]} competencies, '
              f'overall {rep["overall"]}  ({groups})')


if __name__ == '__main__':
    run()
