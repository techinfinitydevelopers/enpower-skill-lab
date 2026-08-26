"""
Build a clean demo set for a client walkthrough: one FSL school and one CSL
school, each with a coach, three named students, a parent, and full report data
including Kaushal Bodh.

The seeded data already covers both frameworks, but not in a shape you would put
in front of a client — students called "Stud31 Dummy", no parent accounts, and
no KB scores on the FSL side. This tidies exactly that, without touching any
other school.

Idempotent. Run with:  python seed_demo_accounts.py
"""

import os
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.db import transaction

from accounts.models import User
from competencies import engine
from competencies.models import (
    AssessmentCompetency, Competency, Pillar, Project, RubricCriterion,
    ScoreEntry, SubPillar,
)
from parent.models import Parent
from schools.models import School
from student.models import Student
from teacher.models import Teacher

PASSWORD = 'Enpower@2026'

# (preferred school name fragment, [student names], parent name). The school is
# picked by data richness if the hint doesn't match — environments differ, and a
# hardcoded name silently produces nothing.
DEMO = {
    'FSL': ('Blue Valley',
            [('Aarav', 'Sharma'), ('Diya', 'Patel'), ('Kabir', 'Nair')],
            'Meena Sharma'),
    'CSL': ('Delhi International',
            [('Ishaan', 'Rao'), ('Anaya', 'Verma'), ('Vihaan', 'Shah')],
            'Rohit Rao'),
}


def pick_school(is_fixed, hint):
    """Best demo school for a framework family: most scored students in one grade."""
    from collections import Counter

    best = None
    for school in School.objects.filter(
            framework_ref__isnull=False,
            framework_ref__is_fixed=is_fixed).select_related('framework_ref'):
        students = Student.objects.filter(
            school=school, score_entries__isnull=False).distinct()
        if not students:
            continue
        per_grade = Counter(str(s.student_class) for s in students if s.student_class)
        if not per_grade:
            continue
        grade, count = per_grade.most_common(1)[0]
        # A name hint wins ties so the same school is picked run to run.
        rank = (count, hint.lower() in school.school_name.lower())
        if best is None or rank > best[0]:
            best = (rank, school, grade)
    return (best[1], best[2]) if best else (None, None)

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

PARENT_DEFAULTS = {
    'relation_to_student': 'mother',
    'preferred_contact': 'primary',
    'residential_address': '12 Nehru Road',
    'city': 'Mumbai', 'state': 'Maharashtra', 'pin_code': '400001',
    'contact_method': 'whatsapp', 'preferred_language': 'english',
    'whatsapp_consent': True, 'photo_consent': True,
    'fee_category': 'regular',
    'emergency_name': 'Family contact', 'emergency_relation': 'guardian',
    'emergency_phone': '9820000000',
    'account_status': 'active', 'is_active': True,
}


def rename_students(school, grade, names):
    """Give the demo students presentable names."""
    students = list(Student.objects.filter(school=school, student_class=grade,
                                           score_entries__isnull=False)
                    .distinct().order_by('id'))
    for student, (first, last) in zip(students, names):
        if (student.first_name, student.last_name) != (first, last):
            student.first_name, student.last_name = first, last
            student.save(update_fields=['first_name', 'last_name'])
        user = User.objects.filter(email=student.school_email).first()
        if user and (user.first_name, user.last_name) != (first, last):
            user.first_name, user.last_name = first, last
            user.save(update_fields=['first_name', 'last_name'])
    return students


def ensure_kb_for_framework(framework, grade):
    """Make sure this framework has a Kaushal Bodh pillar with competencies.

    FSL is seeded without one (the deck puts KB under the CSL frameworks), so a
    client looking at an FSL student would find an empty KB report and no way to
    tell whether that is correct or broken.
    """
    pillar = Pillar.objects.filter(framework_ref=framework, is_kb=True).first()
    if not pillar:
        last = Pillar.objects.filter(framework_ref=framework).order_by('-order').first()
        pillar = Pillar.objects.create(
            name='Kaushal Bodh', number='06', color='amber',
            order=(last.order + 1) if last else 6,
            framework_ref=framework, framework=framework.name, is_kb=True)
        print(f'    created Kaushal Bodh pillar under {framework.name}')

    if pillar.sub_pillars.exists():
        return list(Competency.objects.filter(sub_pillar__pillar=pillar))

    sp_number = (SubPillar.objects.order_by('-sp_number').first().sp_number or 0) + 1
    made = []
    prefix = '' if framework.is_fixed else f'{framework.prefix}-'
    for idx, (sp_name, comps) in enumerate(KB_CONTENT, start=1):
        sub = SubPillar.objects.create(pillar=pillar, sp_number=sp_number, name=sp_name)
        sp_number += 1
        for c_idx, (name, desc, _) in enumerate(comps, start=1):
            code = f'{prefix}KB{idx}.C{c_idx}'
            if Competency.objects.filter(code=code).exists():
                code = f'{framework.prefix}-KB{idx}.C{c_idx}'
            made.append(Competency.objects.create(
                sub_pillar=sub, code=code, name=name, description=desc,
                stage='Middle', status='Active'))
    print(f'    added {len(made)} KB competencies to {framework.name}')
    return made


def score_kb(students, projects, kb_comps):
    """Attach KB competencies to each project's first assessment and score them."""
    wanted = {name: score for _, comps in KB_CONTENT for name, _, score in comps}
    written = 0
    for project in projects:
        assessment = project.assessments.order_by('order').first()
        if not assessment:
            continue
        for order, comp in enumerate(kb_comps):
            mapping, _ = AssessmentCompetency.objects.get_or_create(
                assessment=assessment, competency=comp,
                defaults={'order': 70 + order, 'comp_type': 'individual'})
            RubricCriterion.objects.get_or_create(
                assessment=assessment, competency=comp,
                defaults={'band1_text': 'Needs prompting at each step.',
                          'band2_text': 'Completes with occasional help.',
                          'band3_text': 'Completes accurately and independently.',
                          'band4_text': 'Completes and improves on the method.'})
            base = wanted.get(comp.name, 7)
            for offset, student in enumerate(students):
                # Vary per student and per project so the class spread and the
                # annual "latest score wins" rule both have something to show.
                value = max(1, min(10, base - offset + ((project.sequence_number or 1) - 2)))
                ScoreEntry.objects.update_or_create(
                    student=student, assessment_competency=mapping,
                    defaults={'score': value})
                written += 1
    return written


def ensure_coach(school):
    coach = Teacher.objects.filter(school=school).select_related('user').first()
    if not coach:
        coach = Teacher.objects.filter(school__isnull=True).select_related('user').first()
        if coach:
            coach.school = school
            coach.save(update_fields=['school'])
    if coach and coach.user:
        coach.user.set_password(PASSWORD)
        coach.user.save(update_fields=['password'])
    return coach


def ensure_parent(student, full_name):
    """One parent account linked to the first demo student."""
    parent = Parent.objects.filter(students=student).first()
    if not parent:
        username = f'{student.skill_lab_reg_id or student.id}-par'
        email = f'{username.lower()}@demo.enpower'.replace(' ', '')
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.create_user(
                username=username, email=email, password=PASSWORD,
                first_name=full_name.split()[0], last_name=full_name.split()[-1],
                role='PARENT')
        parent = Parent.objects.create(
            user=user, full_name=full_name, email=email,
            mobile_number='9820000001', **PARENT_DEFAULTS)
        parent.students.add(student)
    if parent.user:
        parent.user.set_password(PASSWORD)
        parent.user.save(update_fields=['password'])
    return parent


@transaction.atomic
def build(label):
    hint, names, parent_name = DEMO[label]
    school, grade = pick_school(is_fixed=(label == 'FSL'), hint=hint)
    if not school:
        print(f'{label}: no school with scored students')
        return None
    framework = school.framework_ref
    print(f'\n{label} — {school.school_name}  [{framework.name}]  grade {grade}')

    students = rename_students(school, grade, names)
    if not students:
        print('    no scored students in that grade')
        return None
    print(f'    students: {", ".join(s.first_name + " " + (s.last_name or "") for s in students)}')

    projects = list(Project.objects.filter(grade=grade, framework_ref=framework)
                    .exclude(project_type='Plug In').order_by('sequence_number'))

    kb_comps = ensure_kb_for_framework(framework, grade)
    written = score_kb(students, projects, kb_comps)
    print(f'    {written} KB score entries across {len(projects)} project(s)')

    for student in students:
        for project in projects:
            engine.generate_project_report(student, project)

    coach = ensure_coach(school)
    parent = ensure_parent(students[0], parent_name)

    for student in students:
        user = User.objects.filter(email=student.school_email).first()
        if user:
            user.set_password(PASSWORD)
            user.save(update_fields=['password'])

    return {'label': label, 'school': school, 'framework': framework,
            'grade': grade, 'students': students, 'coach': coach, 'parent': parent,
            'projects': projects}


def report(block):
    if not block:
        return
    label, school = block['label'], block['school']
    print(f'\n{"="*74}')
    print(f'{label}  —  {school.school_name}   [{block["framework"].name}]   Grade {block["grade"]}')
    print(f'{"="*74}')
    if block['coach'] and block['coach'].user:
        print(f'  COACH    {block["coach"].user.username:30} role: Thinking Coach')
    for s in block['students']:
        u = User.objects.filter(email=s.school_email).first()
        rep = s.project_reports.select_related('project').order_by('project__sequence_number')
        kb = engine.build_kb_report(s)
        top = next((p['profile_name'] for r in rep for p in (r.top_3_profiles or [])), None)
        print(f'  STUDENT  {(u.username if u else "-"):30} role: Student   '
              f'{s.first_name} {s.last_name or ""}')
        print(f'           reports={rep.count()}  career matches={"yes: " + top if top else "none (CSL)"}  '
              f'KB report={kb["count"] if kb else 0} competencies')
    if block['parent'] and block['parent'].user:
        kids = ', '.join(c.first_name for c in block['parent'].students.all())
        print(f'  PARENT   {block["parent"].user.username:30} role: Parent    child: {kids}')


if __name__ == '__main__':
    print(f'Building demo accounts — password for all: {PASSWORD}')
    blocks = [build('FSL'), build('CSL')]
    for b in blocks:
        report(b)
    print(f'\nPassword for every account above: {PASSWORD}')
