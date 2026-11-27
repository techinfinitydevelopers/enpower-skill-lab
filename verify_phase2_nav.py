"""Phase 2 small changes: the navigation, and the Class Performance filters.

Four menu changes and one filter, from the Phase 2 deck:

  * Thinking Coach "Dashboard" is now "Assessment", a dropdown
  * Score Entry moved under it; "Academics" is gone
  * Score Viewing removed -- "old version that is not relevant anymore"
  * School Admin "Class Overview" removed, page and dashboard card alike
  * Reports > Class Performance takes a Grade and Division filter

Two of these are removals, and a removal that only unlinks a page leaves it
reachable by typing the URL. Both are checked for 404, not for a missing link.

The filter is a filter, not an access rule. Score Entry restricts a coach to
the divisions they are timetabled for, because entering another class's
scores is wrong; this screen only reads, so an unfiltered view stays the
default. The check that matters is that the filter reaches the stat cards and
the competency averages too, not just the student table -- a page whose
heading count disagrees with its own table is worse than no filter.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_phase2_nav.py
"""

import datetime
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
from django.urls import NoReverseMatch, reverse

from competencies.models import (Assessment, AssessmentCompetency, Competency,
                                 Project, ScoreEntry)
from school_admin.models import SchoolAdmin
from schools.models import School
from student.models import Student
from teacher.models import Teacher
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
DOB = datetime.date(2014, 5, 1)
REPORTS = '/teacher/reports/'

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


def page(client, url):
    return client.get(url, follow=True).content.decode('utf-8', 'replace')


def status(client, url):
    return client.get(url).status_code


def stat_card(html, label):
    """The number printed under a stat card's label, or None."""
    m = re.search(
        r'<div class="ra-label">' + re.escape(label)
        + r'</div><div class="ra-value">(\d+)',
        html)
    return int(m.group(1)) if m else None


def table_names(html):
    """Student names in the Student Performance table."""
    body = html.split('Student Performance', 1)[-1]
    return set(re.findall(r'color:#1e1b4b;">(Zz[^<]*)</td>', body))


# ------------------------------------------------------------------ fixtures

def build():
    """One school, grades 6 and 7, mixed-case sections, a coach and a head."""
    school = School.objects.create(school_name='ZZ Nav School',
                                   school_code='ZZNAV')

    # Grade 6: A x3, b x2 (lower case on purpose). Grade 7: A x2.
    plan = [('6', 'A', 3), ('6', 'b', 2), ('7', 'A', 2)]
    made = {}
    for grade, division, count in plan:
        made[(grade, division.upper())] = [
            Student.objects.create(
                first_name=f'Zz{grade}{division}{i}', last_name='Pupil',
                school=school, student_class=grade, division=division,
                is_active=True, date_of_birth=DOB, enrollment_date=DOB,
                skill_lab_reg_id=f'ZZNAV-{grade}{division}-{i}')
            for i in range(count)]

    coach_user = U.objects.create_user(
        username='zz.nav.coach@example.com', email='zz.nav.coach@example.com',
        password=PASSWORD, role='THINKING_COACH', first_name='Zz',
        last_name='NavCoach')
    Teacher.objects.create(user=coach_user, full_name='Zz NavCoach',
                           official_email='zz.nav.coach@example.com',
                           school=school, is_active=True,
                           employee_id='ZZNAV-T1',
                           date_of_birth=DOB, joining_date=DOB)

    head_user = U.objects.create_user(
        username='zz.nav.head@example.com', email='zz.nav.head@example.com',
        password=PASSWORD, role='SCHOOL_ADMIN')
    SchoolAdmin.objects.create(user=head_user, school=school,
                               full_name='Zz NavHead',
                               email=head_user.email, phone='9000000009')

    # One score per student, so every figure on the reports page is non-zero
    # and a filter that fails to narrow is visible as an unchanged number.
    project = Project.objects.create(title='Zz Nav Project', grade='6',
                                     status='Active')
    assessment = Assessment.objects.create(project=project,
                                           name='Zz Nav Assessment',
                                           assessment_type='Written', order=1)
    competency = Competency.objects.first()
    if competency:
        mapping = AssessmentCompetency.objects.create(
            assessment=assessment, competency=competency,
            comp_type='individual', order=1)
        for group in made.values():
            for s in group:
                ScoreEntry.objects.create(student=s,
                                          assessment_competency=mapping,
                                          score=8, entered_by=coach_user)

    return school, made, coach_user, head_user


# --------------------------------------------------------------------- nav

def check_coach_nav(coach_user):
    print('\n1. the coach menu: Assessment in, Academics and Score Viewing out')
    client = sign_in(coach_user)
    html = page(client, '/teacher/dashboard/')

    check('the sidebar has an Assessment dropdown',
          'id="assessment-dropdown"' in html)
    check('Academics is gone', 'id="academics-dropdown"' not in html)
    check('Score Entry sits inside it', 'id="nav-score-entry"' in html)
    check('the dashboard page survives, as Overview',
          'id="nav-dashboard"' in html and '>Overview<' in html)
    check('no Score Viewing link is left', 'nav-score-viewing' not in html)

    check('the dashboard page itself still loads',
          status(client, '/teacher/dashboard/') in (200, 302))
    check('Score Entry still loads at its old address',
          status(client, '/teacher/academics/score-entry/') in (200, 302))
    return client


def check_score_viewing_gone(client):
    print('\n2. Score Viewing is removed, not merely unlinked')
    check('the page is gone', status(client, '/teacher/score-viewing/') == 404,
          status(client, '/teacher/score-viewing/'))
    try:
        reverse('teacher:score_viewing')
        check('its url name is gone too', False, 'still reversible')
    except NoReverseMatch:
        check('its url name is gone too', True)


def check_class_overview_gone(head_user):
    print('\n3. Class Overview is removed from the School Admin')
    client = sign_in(head_user)
    html = page(client, '/school-admin/dashboard/')

    check('no sidebar link', 'nav-class-overview' not in html)
    check('no dashboard card', 'class-overview-stats' not in html)
    check('the page is gone',
          status(client, '/school-admin/classes/overview/') == 404,
          status(client, '/school-admin/classes/overview/'))
    try:
        reverse('school_admin_class_overview')
        check('its url name is gone too', False, 'still reversible')
    except NoReverseMatch:
        check('its url name is gone too', True)

    check('Class Attendance was left alone',
          'nav-class-attendance' in html
          and status(client, '/school-admin/classes/attendance/') in (200, 302))


# ----------------------------------------------------------------- filters

def check_report_filters(client, made):
    print('\n4. Class Performance filters by grade and division')

    html = page(client, REPORTS)
    check('a Grade dropdown is offered', 'id="gradeFilter"' in html)
    check('a Division dropdown is offered', 'id="divisionFilter"' in html)
    check('both grades are listed',
          '<option value="6"' in html and '<option value="7"' in html)
    check('unfiltered, the whole school is counted',
          stat_card(html, 'Total Students') == 7,
          stat_card(html, 'Total Students'))

    html = page(client, REPORTS + '?grade=6')
    check('grade 6 narrows the count to five',
          stat_card(html, 'Total Students') == 5,
          stat_card(html, 'Total Students'))
    check('and the table holds those five', len(table_names(html)) == 5,
          len(table_names(html)))
    check('no grade 7 pupil is left in the table',
          not any(n.startswith('Zz7') for n in table_names(html)))
    check('the card says which grade it is counting',
          'in Grade 6' in html)

    html = page(client, REPORTS + '?grade=6&division=A')
    check('6-A narrows the count to three',
          stat_card(html, 'Total Students') == 3,
          stat_card(html, 'Total Students'))
    check('and the table holds those three', len(table_names(html)) == 3,
          len(table_names(html)))
    check('the card names the division too', 'in Grade 6-A' in html)

    # The sections were stored as 'b'. The dropdown offers 'B'.
    html = page(client, REPORTS + '?grade=6&division=B')
    check('a section stored lower-case is still found',
          stat_card(html, 'Total Students') == 2,
          stat_card(html, 'Total Students'))

    html = page(client, REPORTS + '?grade=9')
    check('a grade with no pupils is ignored, not an error',
          stat_card(html, 'Total Students') == 7,
          stat_card(html, 'Total Students'))
    html = page(client, REPORTS + '?grade=6&division=Z')
    check('a division that does not exist is ignored too',
          stat_card(html, 'Total Students') == 5,
          stat_card(html, 'Total Students'))


def check_filter_reaches_everything(client):
    """The figures above the table are computed server-side, so they have to
    move with the filter. A page that says 7 students over a table of 3 is
    the bug this guards."""
    print('\n5. the filter reaches the cards, not only the table')

    whole = page(client, REPORTS)
    narrow = page(client, REPORTS + '?grade=6&division=A')

    for label in ('Total Students', 'Students Assessed'):
        check(f'"{label}" follows the filter',
              stat_card(narrow, label) is not None
              and stat_card(narrow, label) < stat_card(whole, label),
              f'{stat_card(whole, label)} -> {stat_card(narrow, label)}')

    check('the table agrees with the Total Students card',
          len(table_names(narrow)) == stat_card(narrow, 'Total Students'),
          f'{len(table_names(narrow))} rows vs '
          f'{stat_card(narrow, "Total Students")} counted')


# ---------------------------------------------------------------------- run

def run():
    print('=' * 60)
    print('Phase 2 — navigation, and the Class Performance filters')
    print('=' * 60)

    try:
        with transaction.atomic():
            school, made, coach_user, head_user = build()
            client = check_coach_nav(coach_user)
            check_score_viewing_gone(client)
            check_class_overview_gone(head_user)
            check_report_filters(client, made)
            check_filter_reaches_everything(client)
            raise Rollback
    except Rollback:
        pass

    print('\nNothing survives')
    left = (School.objects.filter(school_code='ZZNAV').count()
            + Student.objects.filter(skill_lab_reg_id__startswith='ZZNAV').count()
            + U.objects.filter(username__startswith='zz.nav.').count()
            + Project.objects.filter(title='Zz Nav Project').count())
    check('no row this suite created survived', left == 0, left)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f.strip()}')


if __name__ == '__main__':
    run()
