"""
DEMO ONLY — add a Kaushal Bodh pillar to FSL and score it, so the FSL side of the
KB behaviour can be looked at before deciding how strict it should be.

Note this deliberately contradicts the deck: slides 5 and 6 put KaushalBodh under
CSL+ and CSL Foundation, not FSL. It exists so the current rules can be seen in
action on an FSL student, not because FSL is supposed to carry KB.

Idempotent — re-running replaces the demo pillar and its scores.
Remove it with:  python seed_fsl_kb_demo.py --remove

Run with:  python seed_fsl_kb_demo.py [student_first_name]
"""

import os
import sys
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from competencies.models import (
    Framework, Pillar, SubPillar, Competency, Project, Assessment,
    AssessmentCompetency, ScoreEntry, RubricCriterion,
)
from competencies import engine
from student.models import Student

PILLAR_NAME = 'Kaushal Bodh'
SP_NUMBER_BASE = 18          # FSL uses 1-17; CSL frameworks start at 101 / 201

# (sub-pillar name, [(competency name, description, score for the demo student)])
KB_CONTENT = [
    ('Practical Skills', [
        ('Tool Handling',        'Selects and handles tools safely and correctly for the task', 9),
        ('Measurement Accuracy', 'Measures and marks accurately within the tolerance required', 7),
        ('Task Sequencing',      'Plans and follows the correct order of steps for a job',      8),
    ]),
    ('Workplace Awareness', [
        ('Safety Practices',  'Follows safety rules and spots hazards before starting work', 10),
        ('Team Coordination', 'Coordinates with others so work moves without clashes',        6),
        ('Time Discipline',   'Starts, paces and finishes work within the time given',        5),
    ]),
    ('Essential Values', [
        ('Responsibility',   'Takes ownership of the task and its outcome without prompting', 8),
        ('Respect for Work', 'Treats every kind of work and worker with dignity',             9),
    ]),
]


def remove():
    n = Pillar.objects.filter(framework_ref__name='FSL', name=PILLAR_NAME, is_kb=True).count()
    Pillar.objects.filter(framework_ref__name='FSL', name=PILLAR_NAME, is_kb=True).delete()
    print(f'Removed {n} demo KB pillar(s) from FSL (scores cascade with it)')
    return n


def run(first_name='Aarav'):
    fsl = Framework.objects.get(name='FSL')

    student = (Student.objects
               .filter(first_name__iexact=first_name, school__framework_ref=fsl)
               .first())
    if not student:
        print(f'No FSL student named {first_name!r}')
        return
    print(f'Student: {student.first_name} {student.last_name or ""}  grade '
          f'{student.student_class}{student.division}  [{fsl.name}]')

    remove()

    # 1. Pillar — is_kb=True is what every KB rule keys off, not the name
    max_order = Pillar.objects.filter(framework_ref=fsl).order_by('-order').first()
    pillar = Pillar.objects.create(
        name=PILLAR_NAME, number='06', color='amber',
        order=(max_order.order + 1) if max_order else 6,
        framework_ref=fsl, framework=fsl.name, is_kb=True,
    )
    print(f'\nCreated pillar "{pillar.name}"  is_kb={pillar.is_kb}')

    # 2. Sub-pillars + competencies. sp_number is globally unique; SubPillar.code
    #    renders KB pillars as KB1/KB2/KB3 from their order within the pillar.
    sp_num = SP_NUMBER_BASE
    created = []
    for idx, (sp_name, comps) in enumerate(KB_CONTENT, start=1):
        while SubPillar.objects.filter(sp_number=sp_num).exists():
            sp_num += 1
        sp = SubPillar.objects.create(pillar=pillar, sp_number=sp_num, name=sp_name)
        sp_num += 1
        for c_idx, (name, desc, score) in enumerate(comps, start=1):
            comp = Competency.objects.create(
                sub_pillar=sp, code=f'KB{idx}.C{c_idx}', name=name,
                description=desc, stage='Middle', status='Active',
            )
            created.append((comp, score))
        print(f'  {sp.code}  {sp.name:22} {len(comps)} competencies')

    # 3. Attach to the student's projects and score them
    projects = list(Project.objects.filter(grade=str(student.student_class),
                                           framework_ref=fsl)
                    .exclude(project_type='Plug In').order_by('sequence_number'))
    students = list(Student.objects.filter(student_class=str(student.student_class),
                                           school__framework_ref=fsl))
    print(f'\nAttaching to {len(projects)} project(s), scoring {len(students)} student(s)')

    n_scores = 0
    for p in projects:
        a = p.assessments.order_by('order').first()
        if not a:
            continue
        for comp, score in created:
            ac, _ = AssessmentCompetency.objects.get_or_create(
                assessment=a, competency=comp,
                defaults={'order': 50 + created.index((comp, score)), 'comp_type': 'individual'},
            )
            RubricCriterion.objects.get_or_create(
                assessment=a, competency=comp,
                defaults={'band1_text': 'Needs prompting at each step.',
                          'band2_text': 'Completes with occasional help.',
                          'band3_text': 'Completes accurately and independently.',
                          'band4_text': 'Completes and improves on the method.'},
            )
            for s in students:
                # Vary slightly per project so the annual "latest score wins"
                # rule has something to actually choose between.
                adj = (p.sequence_number or 1) - 2
                val = max(1, min(10, score + adj))
                ScoreEntry.objects.update_or_create(
                    student=s, assessment_competency=ac, defaults={'score': val})
                n_scores += 1
        print(f'  {p.title[:34]:36} -> assessment "{a.name}"')
    print(f'  {n_scores} score entries written')

    # 4. Regenerate
    for s in students:
        for p in projects:
            engine.generate_project_report(s, p)
    print('\nReports regenerated')

    # 5. Show what the student will now see
    report = student.project_reports.filter(project=projects[-1]).first()
    kb_ids = {c.id for c, _ in created}
    print(f'\nWhat {student.first_name} now sees on "{report.project.title}"')

    top5 = report.top_5_competencies or []
    print(f'  Top 5 Skills — {sum(1 for r in top5 if r["competency_id"] in kb_ids)} of 5 are KB')
    for r in top5:
        tag = 'KB' if r['competency_id'] in kb_ids else '  '
        print(f'      [{tag}] {r["competency_code"]:9} {r["competency_name"][:32]:34} {r["score"]}')

    allc = report.all_competency_scores or []
    vals = [r['score'] for r in allc]
    kb_vals = [r['score'] for r in allc if r['competency_id'] in kb_ids]
    non_kb = [r['score'] for r in allc if r['competency_id'] not in kb_ids]
    print(f'\n  Overall Level  = {round(sum(vals)/len(vals),1)}   '
          f'(without KB it would be {round(sum(non_kb)/len(non_kb),1)})')
    print(f'  KB competencies inside all-skills list : {len(kb_vals)} of {len(allc)}')

    work_on = report.skills_to_work_on or []
    print(f'  Skills to Work On — {sum(1 for r in work_on if r["competency_id"] in kb_ids)} of {len(work_on)} are KB')

    leaked = [p['profile_name'] for p in (report.top_3_profiles or [])
              if kb_ids & {int(k) for k in (p.get('weightage') or {})}]
    print(f'  Career matches    : {len(report.top_3_profiles or [])}   KB inside any of them: '
          f'{leaked or "NO"}')

    kb_rep = engine.build_kb_report(student)
    print(f'\n  Kaushal Bodh report — {kb_rep["count"]} competencies, overall {kb_rep["overall"]}')
    for g in kb_rep['groups']:
        print(f'      {g["name"]:34} avg {g["average"]}')
        for r in g['rows']:
            print(f'         {r["competency_code"]:9} {r["competency_name"][:28]:30} {r["score"]}')


if __name__ == '__main__':
    if '--remove' in sys.argv:
        remove()
    else:
        args = [a for a in sys.argv[1:] if not a.startswith('--')]
        run(args[0] if args else 'Aarav')
