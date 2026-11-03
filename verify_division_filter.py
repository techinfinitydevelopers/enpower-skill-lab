"""Score Entry, one division at a time.

    "Currently, TCs can select the grade, project, and assessment, but there
     is no option to filter students by division. As a result, all students
     across the selected grade appear together."  -- client, 30 Oct 2026

The filter is the small part. The screen showed a coach every student in the
grade at their school whether or not those classes were theirs, so the client
chose the stronger reading: a coach sees the divisions they are timetabled
for, which is the rule Attendance has always used. These checks hold the
access rule, not the dropdown.

Three things that would each make the filter a lie, so each has a check:

  * the stats cards are computed server-side over the whole grade. Filtering
    the table and not the cards puts two class sizes on one screen.
  * Generate Report loops over the student list the page last fetched, so a
    division-scoped table with an unscoped list would quietly build reports
    for another coach's class.
  * sections are free text. One school spelt it 'c' against a timetable
    holding 'C' and showed a coach an empty roster of 41 students, which is
    why every comparison here is case-insensitive.

And one that would take the screen away: a coach with no timetable for the
grade keeps seeing all of it, rather than being handed an empty page.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_division_filter.py
"""

import datetime
import json
import os
import re

import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.contrib.auth import get_user_model
from django.db import transaction

from attendance.models import Timetable
from competencies.models import (Assessment, AssessmentCompetency, Competency,
                                 Project, ScoreEntry)
from enpower_skill_lab.academic_year import current_academic_year
from schools.models import School
from student.models import Student
from teacher.models import Teacher
from teacher.views import _coach_divisions, _students_for_scoring
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
DOB = datetime.date(2014, 5, 1)
DATA = '/teacher/api/score-entry-data/'
DIVS = '/teacher/api/divisions-by-grade/'
PROJ = '/teacher/api/assessments-by-project/'

PASS, FAIL = [], []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}'
          f'{("  - " + str(detail)) if detail else ""}')


class Rollback(Exception):
    """Raised once the checks are done, to undo everything they created."""


def sign_in(user):
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    client = Client()
    assert client.login(username=user.username, password=PASSWORD), user.username
    return client


def get_json(client, url):
    return json.loads(client.get(url, follow=True).content.decode('utf-8'))


# ------------------------------------------------------------------ fixtures

def build():
    """One school, grade 6, divisions A/B/C, and a coach teaching A and B."""
    school = School.objects.create(school_name='ZZ Division School',
                                   school_code='ZZDIV')

    # Section case is deliberately mixed. 'c' here against 'C' on the
    # timetable is the exact shape that emptied a real roster.
    plan = {'A': 4, 'B': 3, 'c': 2}
    students = {}
    for division, count in plan.items():
        students[division.upper()] = [
            Student.objects.create(
                first_name=f'Zz{division}{i}', last_name='Pupil',
                school=school, student_class='6', division=division,
                is_active=True, date_of_birth=DOB, enrollment_date=DOB,
                skill_lab_reg_id=f'ZZDIV-{division}-{i}')
            for i in range(count)]

    coach_user = U.objects.create_user(
        username='zz.coach@example.com', email='zz.coach@example.com',
        password=PASSWORD, role='THINKING_COACH', first_name='Zz',
        last_name='Coach')
    Teacher.objects.create(user=coach_user, full_name='Zz Coach',
                           official_email='zz.coach@example.com',
                           school=school, is_active=True,
                           employee_id='ZZDIV-T1',
                           date_of_birth=DOB, joining_date=DOB)

    year = current_academic_year()
    for division in ('A', 'B'):
        Timetable.objects.create(school=school, thinking_coach=coach_user,
                                 grade='6', division=division,
                                 academic_year=year)

    project = Project.objects.create(title='Zz Division Project', grade='6',
                                     status='Active')
    assessment = Assessment.objects.create(project=project,
                                           name='Zz Assessment 1',
                                           assessment_type='Written', order=1)
    competency = Competency.objects.first()
    mapping = (AssessmentCompetency.objects.create(
        assessment=assessment, competency=competency, comp_type='Primary',
        order=1) if competency else None)

    return school, students, coach_user, project, assessment, mapping


# ---------------------------------------------------------------- the rule

def check_the_rule(coach, students):
    print('\n1. a coach reaches the divisions they teach, and no others')

    check('the timetable is what names them',
          _coach_divisions(coach, '6') == ['A', 'B'],
          _coach_divisions(coach, '6'))
    check('a grade they teach nothing in names none',
          _coach_divisions(coach, '9') == [], _coach_divisions(coach, '9'))

    qs, allowed, restricted = _students_for_scoring(coach, ['6'], '6')
    check('the rule is on', restricted)
    check('with no division picked they see A and B together',
          qs.count() == 7, qs.count())
    check('and never division C', not qs.filter(division__iexact='c').exists())

    qs, _, _ = _students_for_scoring(coach, ['6'], '6', 'A')
    check('picking A gives A', qs.count() == 4, qs.count())
    check('and they are the right four',
          set(qs.values_list('id', flat=True))
          == {s.id for s in students['A']})

    # C is a real division at the school, just not this coach's. Asking for it
    # by name must not reach it -- the dropdown is not the access rule.
    qs, _, _ = _students_for_scoring(coach, ['6'], '6', 'C')
    check('asking for C by name still gives only A and B',
          qs.count() == 7, qs.count())
    qs, _, _ = _students_for_scoring(coach, ['6'], '6', 'Z')
    check('a division that does not exist is ignored, not an error',
          qs.count() == 7, qs.count())


def check_case(coach, school):
    print('\n2. a section spelt in the other case is the same section')

    Timetable.objects.create(school=school, thinking_coach=coach, grade='6',
                             division='C', academic_year=current_academic_year())
    check('the timetable says C, the students say c',
          _coach_divisions(coach, '6') == ['A', 'B', 'C'],
          _coach_divisions(coach, '6'))

    qs, _, _ = _students_for_scoring(coach, ['6'], '6', 'C')
    check('and the two still find each other', qs.count() == 2, qs.count())
    qs, _, _ = _students_for_scoring(coach, ['6'], '6', 'c')
    check('typed either way', qs.count() == 2, qs.count())

    # Put it back, so the checks that follow see the coach as built.
    Timetable.objects.filter(thinking_coach=coach, division='C').delete()


def check_unassigned(school, students):
    print('\n3. a coach with no timetable keeps the screen')

    spare = U.objects.create_user(
        username='zz.spare@example.com', email='zz.spare@example.com',
        password=PASSWORD, role='THINKING_COACH')
    Teacher.objects.create(user=spare, full_name='Zz Spare',
                           official_email='zz.spare@example.com',
                           school=school, is_active=True,
                           employee_id='ZZDIV-T2',
                           date_of_birth=DOB, joining_date=DOB)

    qs, allowed, restricted = _students_for_scoring(spare, ['6'], '6')
    check('the rule is off for them', not restricted)
    check('they see the whole grade, as before', qs.count() == 9, qs.count())
    check('and the dropdown offers what the grade actually holds',
          allowed == ['A', 'B', 'C'], allowed)

    qs, _, _ = _students_for_scoring(spare, ['6'], '6', 'B')
    check('they can still narrow it', qs.count() == 3, qs.count())
    return spare


# ------------------------------------------------------- what the page does

def check_api(coach, assessment, project):
    print('\n4. the endpoints the page actually calls')

    client = sign_in(coach)

    divisions = get_json(client, f'{DIVS}?grade=6')
    check('the divisions endpoint lists A and B',
          divisions.get('divisions') == ['A', 'B'], divisions)
    check('and says the coach is restricted', divisions.get('restricted'))
    check('an unknown grade returns nothing rather than erroring',
          get_json(client, f'{DIVS}?grade=zz').get('divisions') == [])

    data = get_json(client, f'{DATA}?assessment_id={assessment.id}')
    check('with no division the table holds A and B',
          len(data['students']) == 7, len(data['students']))
    check('the stats card counts the same list',
          data['stats']['total_students'] == len(data['students']),
          data['stats']['total_students'])

    data = get_json(client, f'{DATA}?assessment_id={assessment.id}&division=A')
    check('with A it holds four', len(data['students']) == 4,
          len(data['students']))
    check('the card follows the table, not the grade',
          data['stats']['total_students'] == 4,
          data['stats']['total_students'])
    check('every row returned really is division A',
          all(s['division'].upper() == 'A' for s in data['students']),
          sorted({s['division'] for s in data['students']}))
    check('the endpoint hands the page its division list',
          data.get('divisions') == ['A', 'B'], data.get('divisions'))

    data = get_json(client, f'{DATA}?assessment_id={assessment.id}&division=C')
    check('asking for someone else\'s division over the wire gets nothing of theirs',
          len(data['students']) == 7, len(data['students']))
    return client


def check_progress(client, coach, project, assessment, mapping, students):
    print('\n5. the progress line counts the division it sits beside')

    if mapping is None:
        check('a competency to score with', False)
        return

    # Score division B only. A is untouched.
    for student in students['B']:
        ScoreEntry.objects.create(student=student,
                                  assessment_competency=mapping, score=8)

    both = get_json(client, f'{PROJ}?project_id={project.id}')
    check('across both divisions the assessment reads scored',
          both['assessments_scored'] == 1, both['assessments_scored'])

    b = get_json(client, f'{PROJ}?project_id={project.id}&division=B')
    check('for B it reads scored', b['assessments_scored'] == 1,
          b['assessments_scored'])

    a = get_json(client, f'{PROJ}?project_id={project.id}&division=A')
    check('for A it reads unscored, which is the whole point',
          a['assessments_scored'] == 0, a['assessments_scored'])

    # And the scores themselves must not leak across. The table for A should
    # show no marks at all.
    data = get_json(client, f'{DATA}?assessment_id={assessment.id}&division=A')
    check('A\'s table carries none of B\'s marks',
          not [v for v in data['scores'].values() if v is not None],
          list(data['scores'].values())[:4])
    check('and A\'s class average is empty rather than B\'s',
          data['stats']['class_avg'] is None, data['stats']['class_avg'])


def check_page(client):
    print('\n6. the control is on the page, in the order asked for')

    html = client.get('/teacher/academics/score-entry/',
                      follow=True).content.decode('utf-8', 'replace')
    check('the division dropdown is rendered', 'id="divisionSelect"' in html)
    check('it sits between Grade Level and Project',
          html.index('gradeSelect') < html.index('divisionSelect')
          < html.index('projectSelect'))
    check('and it is labelled Division', '>\n                        Division'
          in html or 'Division\n' in html)

    # The steps are numbered on screen; a stale number is a small lie that
    # makes the page read wrongly.
    for num, badge in ((2, 'step2Badge'), (3, 'step3Badge'), (4, 'step4Badge')):
        found = re.search(rf'id="{badge}"[^>]*>(\d+)<', html)
        check(f'{badge} reads {num}', found and found.group(1) == str(num),
              found and found.group(1))

    check('the row is laid out for four controls',
          'lg:grid-cols-4' in html)
    check('every fetch for students carries the division',
          'function dataUrl(' in html and '&division=' in html)
    check('so does the one for assessment progress',
          'function projectUrl(' in html)
    check('the student count card names the division it is showing',
          'statTotalScope' in html)
    check('and the empty state does too', 'noStudentsText' in html)
    check('a coach with no classes is told why they see everything',
          'No classes are assigned to you for this grade' in html)


def run():
    print('=' * 60)
    print('SCORE ENTRY, ONE DIVISION AT A TIME')
    print('=' * 60)

    try:
        with transaction.atomic():
            (school, students, coach, project,
             assessment, mapping) = build()
            check_the_rule(coach, students)
            check_case(coach, school)
            check_unassigned(school, students)
            client = check_api(coach, assessment, project)
            check_progress(client, coach, project, assessment, mapping,
                           students)
            check_page(client)
            raise Rollback
    except Rollback:
        pass

    left = (School.objects.filter(school_code='ZZDIV').count()
            + Student.objects.filter(skill_lab_reg_id__startswith='ZZDIV').count()
            + U.objects.filter(username__startswith='zz.').count()
            + Project.objects.filter(title='Zz Division Project').count())
    check('\n  nothing this suite created survived', left == 0, left)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f.strip()}')


if __name__ == '__main__':
    run()
