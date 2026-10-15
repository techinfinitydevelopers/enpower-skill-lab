"""Letter grades: the bands, the coach's switch, and what reaches the report.

The client asked for a switch on the marks-entry screen between an average out
of ten and a letter grade, and for that choice to be what students and parents
then read. The bands came as ranges with hairline gaps between them, so the
first thing checked here is that every number on the scale has exactly one
answer.

The part worth being careful about: a Project carries no school. It is matched
to classes by grade and framework, so one Project -- and every Assessment under
it -- runs in every school on that framework. A switch stored on the Assessment
alone would have let a coach in one school rewrite what another school's
parents read on their own children's reports. That is checked directly: two
schools are given the same assessment, one turns grades on, and the other must
still see marks out of ten.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_grading.py
"""

import itertools
import os
import re

import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

import json

from django.contrib.auth import get_user_model
from django.db import transaction

from competencies.grading import (BANDS, grade_display_map, grade_for,
                                  shows_grade)
from competencies.models import (Assessment, AssessmentCompetency,
                                 AssessmentGradeDisplay, ProjectReport,
                                 ScoreEntry)
from parent.models import Parent
from schools.models import School
from student.models import Student
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'

PASS, FAIL = [], []

# Keeps every copied row's unique columns from colliding with the original.
STAMP = itertools.count(1)


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}'
          f'{("  — " + str(detail)) if detail else ""}')


class Rollback(Exception):
    """Raised once the checks are done, to undo everything they created."""


def sign_in(user):
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    client = Client()
    assert client.login(username=user.username, password=PASSWORD), \
        f'could not sign in as {user.username}'
    return client


# --------------------------------------------------------------- the bands

def check_bands():
    print('\n1. the bands the client sent')

    # Read straight off the client's table, including both sides of every
    # boundary it names.
    for score, expected in [
        (10, 'A+'), (9.5, 'A+'), (9.0, 'A+'),
        (8.9, 'A'), (8.0, 'A'), (7.0, 'A'),
        (6.9, 'B'), (6.0, 'B'), (5.0, 'B'),
        (4.9, 'C'), (4.0, 'C'), (3.0, 'C'),
        (2.9, 'D'), (1.0, 'D'), (0.0, 'D'),
    ]:
        check(f'{score} is {expected}', grade_for(score) == expected,
              grade_for(score))

    # The table reads "7 - 8.9" then "9 - 10", so 8.95 belongs to neither. The
    # bands are written as floors for that reason; nothing on the scale may
    # come back without a grade.
    gaps = [round(n / 100, 2) for n in range(0, 1001)]
    missing = [v for v in gaps if grade_for(v) is None]
    check('every value from 0.00 to 10.00 has a grade', not missing,
          missing[:5])

    # Grades must never go backwards as the score climbs.
    order = ['D', 'C', 'B', 'A', 'A+']
    ranks = [order.index(grade_for(v)) for v in gaps]
    check('the grade never falls as the score rises',
          all(b >= a for a, b in zip(ranks, ranks[1:])))

    # A blank is not a D. An unscored assessment has earned nothing, and
    # printing a D against it would be an accusation.
    check('no score means no grade, not a D', grade_for(None) is None,
          grade_for(None))
    check('nonsense means no grade', grade_for('not a number') is None)

    # The bands are declared best-first and read in order; shuffled, the first
    # match would win wrongly.
    check('the bands are declared from the top down',
          [floor for floor, _ in BANDS] == sorted(
              [floor for floor, _ in BANDS], reverse=True))


# ------------------------------------------------------- the coach's switch

def check_switch(teacher_user, assessment, other_school):
    print("\n2. the coach's switch")

    client = sign_in(teacher_user)

    body = client.get('/teacher/academics/score-entry/', follow=True).content.decode(
        'utf-8', 'replace')
    check('the switch is on the marks-entry page', 'gradeToggleWrap' in body)
    check('it offers both readings',
          'Out of 10' in body and '>Grade<' in body)
    check('the page knows the bands too, for drawing without a round trip',
          'function gradeFor' in body)
    check('score cells are not switched, because scores are typed in there',
          body.count('gradeMode') >= 3 and 'renderCell' in body)

    data = json.loads(client.get(
        f'/teacher/api/score-entry-data/?assessment_id={assessment.id}'
    ).content)
    check('the data says which way this school reads it',
          data.get('show_grade') is False, data.get('show_grade'))

    saved = json.loads(client.post(
        '/teacher/api/save-grade-display/',
        data=json.dumps({'assessment_id': assessment.id, 'show_grade': True}),
        content_type='application/json').content)
    check('the coach can turn grades on', saved.get('ok') is True, saved)

    data = json.loads(client.get(
        f'/teacher/api/score-entry-data/?assessment_id={assessment.id}'
    ).content)
    check('and the page is told so next time it loads',
          data.get('show_grade') is True, data.get('show_grade'))

    row = AssessmentGradeDisplay.objects.get(
        assessment=assessment, school=teacher_user.teacher_profile.school)
    check('the choice is recorded against a school, not just the assessment',
          row.school_id == teacher_user.teacher_profile.school_id)
    check('and against whoever made it', row.updated_by_id == teacher_user.id)

    # Turning it off must leave no doubt -- an absent row and a False row have
    # to mean the same thing.
    client.post('/teacher/api/save-grade-display/',
                data=json.dumps({'assessment_id': assessment.id,
                                 'show_grade': False}),
                content_type='application/json')
    check('turning it off does not just delete the row and forget',
          AssessmentGradeDisplay.objects.filter(
              assessment=assessment).count() == 1)
    check('and off reads as out of ten',
          shows_grade(assessment, teacher_user.teacher_profile.school) is False)

    client.post('/teacher/api/save-grade-display/',
                data=json.dumps({'assessment_id': assessment.id,
                                 'show_grade': True}),
                content_type='application/json')

    # The point of the school key.
    check("one school's choice does not reach another school",
          shows_grade(assessment, other_school) is False)

    check('a missing assessment is refused', json.loads(client.post(
        '/teacher/api/save-grade-display/',
        data=json.dumps({'assessment_id': 99999999, 'show_grade': True}),
        content_type='application/json').content).get('error') is not None)
    check('a malformed request is refused', client.post(
        '/teacher/api/save-grade-display/', data='{}',
        content_type='application/json').status_code == 400)
    check('it cannot be set by a GET', client.get(
        '/teacher/api/save-grade-display/').status_code == 405)

    # One query for a whole report, not one per card.
    with_map = grade_display_map([assessment.id],
                                 teacher_user.teacher_profile.school)
    check('the bulk lookup agrees with the single one',
          with_map.get(assessment.id) is True, with_map)
    check('an empty ask costs nothing', grade_display_map([], None) == {})


# ----------------------------------------------------------- what is read

def heading_value(html, css_class):
    found = re.search(r'class="' + css_class + r'"[^>]*>(.*?)</div>', html,
                      re.S)
    return re.sub(r'<[^>]+>', '', found.group(1)).strip() if found else None


def assessment_figures(html):
    """{assessment name: the figure printed against it} from the report.

    Slicing the page from the assessment's name was the obvious way and the
    wrong one: the section itself is headed "Assessment", so the slice started
    at the heading and every check then ran against a few characters of title.
    A card at a time, read from its own markup.
    """
    figures = {}
    for card in re.findall(r'<div class="asmt-card">(.*?)<div class="asmt-comps">',
                           html, re.S):
        name = re.search(r'<div class="asmt-name">(.*?)</div>', card, re.S)
        avg = re.search(r'<div class="asmt-avg[^"]*">(.*?)</div>', card, re.S)
        if not name:
            continue
        label = re.sub(r'<[^>]+>', '', name.group(1)).strip()
        label = label.split('. ', 1)[-1]          # drop the "1. " numbering
        figures[label] = re.sub(r'<[^>]+>', '', avg.group(1)).strip() if avg else None
    return figures


def check_report(student, parent, report, assessment, average):
    print('\n3. what the student and the parent read')

    expected = grade_for(average)
    urls = [
        ('student', sign_in(student.user),
         f'/student/reports/{report.project_id}/'),
        ('parent', sign_in(parent.user),
         f'/parent/child/{student.id}/reports/{report.project_id}/'),
    ]

    for who, client, url in urls:
        body = client.get(url, follow=True).content.decode('utf-8', 'replace')

        # The Overall Level card carries the grade instead of the mark, which
        # is what the user settled on: the number comes off the card entirely.
        check(f'{who}: the Overall Level card shows a grade',
              heading_value(body, 'stat-value') in
              ('A+', 'A', 'B', 'C', 'D'),
              heading_value(body, 'stat-value'))
        check(f'{who}: the card no longer says out of 10.0',
              'out of 10.0' not in body)
        # A letter cannot count up, and the counter used to write "0" over
        # whatever it found. It has to leave this card alone.
        check(f'{who}: the counter is told to skip it',
              "hasAttribute('data-target')" in body)

        # The assessment this school switched to grades.
        figures = assessment_figures(body)
        check(f'{who}: the report has a card for the graded assessment',
              assessment.name in figures, sorted(figures))
        check(f'{who}: it shows {expected}',
              figures.get(assessment.name) == expected,
              figures.get(assessment.name))
        check(f'{who}: and not the mark out of ten',
              '/10' not in (figures.get(assessment.name) or ''))

    return expected


def check_other_school_untouched(other_student, other_parent, other_report,
                                 assessment, average):
    print('\n4. the school that did not ask for grades')

    for who, user, url in [
        ('student', other_student.user,
         f'/student/reports/{other_report.project_id}/'),
        ('parent', other_parent.user,
         f'/parent/child/{other_student.id}/reports/{other_report.project_id}/'),
    ]:
        body = sign_in(user).get(url, follow=True).content.decode(
            'utf-8', 'replace')
        figures = assessment_figures(body)
        shown = figures.get(assessment.name)
        check(f'{who}: still reads the mark out of ten',
              shown == f'{average}/10', shown)
        check(f'{who}: and no letter reached it',
              shown not in ('A+', 'A', 'B', 'C', 'D'), shown)


# ------------------------------------------------------------------- setup

def clone(obj, **changes):
    """Copy a row rather than build one.

    Student, Parent and Teacher each carry a dozen required columns that have
    nothing to do with grading -- emergency contacts, enrolment dates, board.
    Filling them in here would be inventing a school record to test a label.
    Copying a real row keeps the shape honest and the suite short.
    """
    obj.pk = None
    obj._state.adding = True
    for field, value in changes.items():
        setattr(obj, field, value)

    # The copy carries the original's unique columns -- registration id, GR
    # number, employee id -- and the insert would collide on whichever one the
    # model happens to have. Clear or re-stamp every one the caller did not
    # set, rather than discovering them one failure at a time.
    for f in obj._meta.fields:
        if not f.unique or f.primary_key or f.name in changes:
            continue
        if f.null:
            setattr(obj, f.name, None)
        elif f.get_internal_type() in ('CharField', 'TextField'):
            setattr(obj, f.name, f'zz-{f.name}-{next(STAMP)}'[:f.max_length or 50])

    obj.save()
    return obj


def build_case():
    """Two schools running the same assessment, each with a scored child."""
    from competencies.models import Competency, Project
    from teacher.models import Teacher

    project = (Project.objects.filter(assessments__isnull=False)
               .distinct().first())
    assert project, 'no project with an assessment to work from'
    assessment = project.assessments.first()
    mappings = list(assessment.competency_mappings.all()[:2])
    if len(mappings) < 2:
        comps = list(Competency.objects.exclude(
            id__in=[m.competency_id for m in mappings])[:2 - len(mappings)])
        assert comps, 'no competencies seeded'
        mappings += [AssessmentCompetency.objects.create(
            assessment=assessment, competency=c, order=90 + i)
            for i, c in enumerate(comps)]

    schools = list(School.objects.all()[:2])
    assert len(schools) >= 2, 'need two schools to prove the separation'

    student_seed = Student.objects.first()
    parent_seed = Parent.objects.first()
    teacher_seed = Teacher.objects.first()
    assert student_seed and parent_seed and teacher_seed,         'need one of each to copy from'

    made = []
    for i, school in enumerate(schools):
        user = U.objects.create_user(
            username=f'zz-grade-stu-{i}', password=PASSWORD,
            role='STUDENT', first_name='Zz', last_name=f'Grade{i}')
        student = clone(
            Student.objects.get(pk=student_seed.pk),
            user=user, school=school, first_name='Zz',
            last_name=f'Grade{i}', student_class=project.grade,
            division='A', is_active=True, roll_number=f'ZZG{i}',
            skill_lab_reg_id=f'ZZ-GRADE-{i}-stu',
            school_email=f'zz-grade-stu-{i}@example.invalid')

        p_user = U.objects.create_user(
            username=f'zz-grade-par-{i}', password=PASSWORD, role='PARENT',
            first_name='Zz', last_name=f'Parent{i}')
        parent = clone(Parent.objects.get(pk=parent_seed.pk),
                       user=p_user, school=school, full_name=f'Zz Parent{i}')
        parent.students.set([student])

        # Two eights, so the average is 8.0 -- an A, and far from any boundary.
        for m in mappings[:2]:
            ScoreEntry.objects.create(
                student=student, assessment_competency=m, score=8)

        report = ProjectReport.objects.create(
            student=student, project=project,
            all_competency_scores=[
                {'competency_id': m.competency_id,
                 'competency_name': m.competency.name, 'score': 8}
                for m in mappings[:2]],
            top_3_profiles=[], top_5_competencies=[], skills_to_work_on=[])
        made.append((school, student, parent, report))

    coach_user = U.objects.create_user(
        username='zz-grade-coach', password=PASSWORD, role='THINKING_COACH',
        first_name='Zz', last_name='Coach')
    clone(Teacher.objects.get(pk=teacher_seed.pk), user=coach_user,
          school=schools[0], full_name='Zz Coach', employee_id='ZZ-GRADE-1',
          official_email='zz-grade-coach@example.invalid')
    return assessment, coach_user, made


def run():
    print('=' * 60)
    print('GRADES')
    print('=' * 60)

    check_bands()

    try:
        with transaction.atomic():
            assessment, coach, made = build_case()
            (school_a, student_a, parent_a, report_a) = made[0]
            (school_b, student_b, parent_b, report_b) = made[1]

            check_switch(coach, assessment, school_b)
            check_report(student_a, parent_a, report_a, assessment, 8.0)
            check_other_school_untouched(student_b, parent_b, report_b,
                                         assessment, 8.0)
            raise Rollback
    except Rollback:
        pass

    left = AssessmentGradeDisplay.objects.filter(
        updated_by__username='zz-grade-coach').count()
    check('nothing this suite created survived', left == 0, left)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    run()
