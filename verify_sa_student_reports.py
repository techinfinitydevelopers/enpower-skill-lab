"""The principal opening one student's project report.

    "Provide access to individual student project reports by Grade, Section &
     Name - Add under reports"      -- Phase 2 deck, small change 13

The principal could already see grade-wise panels and download a workbook,
but not open the one report a parent rings them about.

Two things are worth more than the filters here.

**Scope.** A principal must reach their own school's children and no others.
The school comes from their own profile, so the check that matters is a
student id from another school returning 404 rather than that child's report.

**One rendering.** The student, the parent and the principal now share
`competencies.report_context`. Three copies of that assembly is how one child
ends up with two different reports, so the suite reads the same report
through two roles and compares the figures.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_sa_student_reports.py
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

from competencies.models import Project, ProjectReport
from school_admin.models import SchoolAdmin
from schools.models import School
from student.models import Student
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
DOB = datetime.date(2014, 5, 1)
LIST = '/school-admin/reports/students/'

def real_scores():
    """Three real competencies, scored.

    The report partial groups rows by sub-pillar and reads labels back from
    the live rows, so invented competencies render as nothing at all. Using
    real ones is also what production does.
    """
    from competencies.models import Competency

    rows = []
    for i, c in enumerate(Competency.objects.filter(status='Active')
                          .select_related('sub_pillar__pillar')[:3]):
        rows.append({'competency_id': c.id, 'code': c.code, 'name': c.name,
                     'score': [9, 7, 5][i]})
    return rows

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


def names_in_table(html):
    """First names in the Student column, which is the only Zz cell."""
    return {n.split()[0] for n in
            re.findall(r'font-weight:600;">(Zz[^<]*?)</td>', html)}


# ------------------------------------------------------------------ fixtures

def pupil(school, grade, division, tag):
    return Student.objects.create(
        first_name=f'Zz{tag}', last_name='Pupil', school=school,
        student_class=grade, division=division, is_active=True,
        date_of_birth=DOB, enrollment_date=DOB,
        skill_lab_reg_id=f'ZZSAR-{tag}')


def build():
    """One school with pupils across two grades, and a second school."""
    school = School.objects.create(school_name='ZZ SAR School',
                                   school_code='ZZSAR')
    other = School.objects.create(school_name='ZZ Other School',
                                  school_code='ZZSAR2')

    made = {
        '6A1': pupil(school, '6', 'A', '6A1'),
        '6A2': pupil(school, '6', 'A', '6A2'),
        # Stored lower case on purpose.
        '6b1': pupil(school, '6', 'b', '6b1'),
        '7A1': pupil(school, '7', 'A', '7A1'),
    }
    outsider = pupil(other, '6', 'A', 'OUT')

    head_user = U.objects.create_user(
        username='zz.sar.head@example.com', password=PASSWORD,
        role='SCHOOL_ADMIN', email='zz.sar.head@example.com')
    SchoolAdmin.objects.create(user=head_user, school=school,
                               full_name='Zz SarHead',
                               email=head_user.email, phone='9000000011')

    project = Project.objects.create(title='Zz SAR Project', grade='6',
                                     status='Active', sequence_number=1)
    scores = real_scores()
    report = ProjectReport.objects.create(
        student=made['6A1'], project=project,
        all_competency_scores=scores)

    # A report for the other school's child, so a leak would be visible.
    ProjectReport.objects.create(student=outsider, project=project,
                                 all_competency_scores=scores)

    return school, other, made, outsider, head_user, project, report


# -------------------------------------------------------------------- checks

def check_listing(client, made):
    print('\n1. the list, and its filters')
    html = page(client, LIST)
    check('the page loads', 'Student Reports' in html)
    check('every pupil of the school is listed',
          len(names_in_table(html)) == 4, sorted(names_in_table(html)))

    html = page(client, LIST + '?grade=6')
    check('grade 6 narrows it to three', len(names_in_table(html)) == 3,
          sorted(names_in_table(html)))
    check('the grade 7 pupil is out', 'Zz7A1' not in names_in_table(html))

    html = page(client, LIST + '?grade=6&division=A')
    check('6-A narrows it to two', len(names_in_table(html)) == 2,
          sorted(names_in_table(html)))

    html = page(client, LIST + '?grade=6&division=B')
    check('a section stored lower-case is still found',
          names_in_table(html) == {'Zz6b1'}, sorted(names_in_table(html)))

    html = page(client, LIST + '?name=6A2')
    check('searching by name finds the one',
          names_in_table(html) == {'Zz6A2'}, sorted(names_in_table(html)))

    html = page(client, LIST + '?name=ZZSAR-7A1')
    check('searching by registration id works too',
          names_in_table(html) == {'Zz7A1'}, sorted(names_in_table(html)))

    html = page(client, LIST + '?grade=9')
    check('a grade with nobody in it is ignored, not an error',
          len(names_in_table(html)) == 4, sorted(names_in_table(html)))


def check_no_leak(client, outsider):
    print('\n2. another school is out of reach')
    html = page(client, LIST)
    check('their pupil is not in the list', 'ZzOUT' not in html)

    code = status(client, f'{LIST}{outsider.id}/')
    check('their report list is a 404', code == 404, code)

    code = status(client,
                  f'{LIST}{outsider.id}/{ProjectReport.objects.filter(student=outsider).first().project_id}/')
    check('their report itself is a 404', code == 404, code)


def check_report_opens(client, made, project):
    print('\n3. the report opens, and says what it should')
    student = made['6A1']

    html = page(client, f'{LIST}{student.id}/')
    check('the student has a report listed', 'Zz SAR Project' in html)
    check('the average is shown', '7.0 / 10' in html, )

    html = page(client, f'{LIST}{student.id}/{project.id}/')
    check('the report renders', 'Zz SAR Project' in html)
    for row in real_scores():
        check(f'{row["name"]} is on it', row['name'] in html)
    check('the back link goes to this student, not the student site',
          f'{LIST}{student.id}/' in html)

    student_without = made['6A2']
    html = page(client, f'{LIST}{student_without.id}/')
    check('a student with no report says so, rather than erroring',
          'No reports have been generated' in html)
    check('and their report page is a 404',
          status(client, f'{LIST}{student_without.id}/{project.id}/') == 404)
    return html


def check_same_as_the_student_sees(client, made, project):
    """The principal and the student read one assembly, so the figures have
    to agree. Three renderings is how two of them drift."""
    print('\n4. the same report the student sees')
    student = made['6A1']

    student_user = U.objects.create_user(
        username='ZZSAR-6A1', password=PASSWORD, role='STUDENT',
        email='zz.sar.pupil@example.com')
    student.user = student_user
    student.save(update_fields=['user'])

    head_html = page(client, f'{LIST}{student.id}/{project.id}/')
    own_html = page(sign_in(student_user),
                    f'/student/reports/{project.id}/')

    wanted = [r['name'] for r in real_scores()]

    def present(html):
        return {n for n in wanted if n in html}

    check('both pages name the same competencies',
          present(head_html) == present(own_html)
          and len(present(head_html)) == len(wanted),
          f'{sorted(present(head_html))} vs {sorted(present(own_html))}')


def check_sidebar(client):
    print('\n5. it is in the menu, under Reports')
    html = page(client, '/school-admin/dashboard/')
    check('a Student Reports entry exists', 'nav-student-reports' in html)
    check('Download Reports is still there', 'nav-download-reports' in html)


# ---------------------------------------------------------------------- run

def run():
    print('=' * 60)
    print('School Admin — individual student project reports')
    print('=' * 60)

    try:
        with transaction.atomic():
            (school, other, made, outsider,
             head_user, project, report) = build()
            client = sign_in(head_user)
            check_listing(client, made)
            check_no_leak(client, outsider)
            check_report_opens(client, made, project)
            check_same_as_the_student_sees(client, made, project)
            check_sidebar(sign_in(head_user))
            raise Rollback
    except Rollback:
        pass

    print('\nNothing survives')
    left = (School.objects.filter(school_code__startswith='ZZSAR').count()
            + Student.objects.filter(skill_lab_reg_id__startswith='ZZSAR').count()
            + U.objects.filter(username__startswith='zz.sar.').count()
            + Project.objects.filter(title='Zz SAR Project').count())
    check('no row this suite created survived', left == 0, left)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f.strip()}')


if __name__ == '__main__':
    run()
