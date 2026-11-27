"""Several files per project upload, and the student's My Projects page.

Two Phase 2 small changes that share the same data:

    "Under student project upload tab: create multiple file attachments for
     project uploads."                                   -- deck, change 5

    "Create a new section : My projects (shift 'view projects' under
     dashboard to this new tab) under 'Project report' tab. Display project
     files, photos, descriptions and documents."         -- deck, change 11

`StudentProjectUpload.file` held exactly one file, so a coach with six
photographs of the same build either picked the best one or made six uploads
of the same project. Files now live in `ProjectUploadFile` rows.

The check that matters most is the migration one. Every upload made before
today has its file on the old field, and the templates read the rows now, so
a migration that missed them would leave every past project showing nothing
at all. `attachments` is checked against a row whose file was never moved, to
prove the fallback holds.

The bell moved too. The dashboard used to list the uploads and so cleared the
notification; now My Projects lists them, and clearing it on the dashboard
would hide work the student never saw.

Everything runs inside a transaction that is rolled back. Uploaded files are
deleted by name at the end.

Run with:  python verify_project_files.py
"""

import datetime
import os

import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from attendance.models import ProjectUploadFile, StudentProjectUpload
from schools.models import School
from student.models import Student
from teacher.models import Teacher
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
DOB = datetime.date(2014, 5, 1)

PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082')
PDF = b'%PDF-1.4 zz test'

PASS, FAIL = [], []
WROTE = []


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


def png(name):
    return SimpleUploadedFile(name, PNG, content_type='image/png')


def pdf(name):
    return SimpleUploadedFile(name, PDF, content_type='application/pdf')


# ------------------------------------------------------------------ fixtures

def build():
    school = School.objects.create(school_name='ZZ Files School',
                                   school_code='ZZFILE')

    student_user = U.objects.create_user(
        username='ZZFILE-STU-1', password=PASSWORD, role='STUDENT',
        email='zz.files.student@example.com')
    student = Student.objects.create(
        first_name='Zz', last_name='Pupil', school=school,
        student_class='6', division='A', is_active=True,
        date_of_birth=DOB, enrollment_date=DOB,
        skill_lab_reg_id='ZZFILE-STU-1', user=student_user)

    coach_user = U.objects.create_user(
        username='zz.files.coach@example.com', password=PASSWORD,
        role='THINKING_COACH', email='zz.files.coach@example.com')
    Teacher.objects.create(user=coach_user, full_name='Zz FilesCoach',
                           official_email='zz.files.coach@example.com',
                           school=school, is_active=True,
                           employee_id='ZZFILE-T1',
                           date_of_birth=DOB, joining_date=DOB)

    # An upload shaped like the ones that already exist: its file sits on the
    # old single field and was never moved into a row.
    legacy = StudentProjectUpload.objects.create(
        school=school, grade='6', division='A', title='Zz Legacy Upload',
        description='Made before files had rows of their own',
        created_by=coach_user)
    legacy.file = png('zz-legacy.png')
    legacy.save()
    WROTE.append(legacy.file.name)
    legacy.students.add(student)

    return school, student, student_user, coach_user, legacy


# -------------------------------------------------------------------- checks

def check_legacy_fallback(legacy):
    print('\n1. an upload whose file was never moved still shows it')
    check('it has no rows', legacy.files.count() == 0, legacy.files.count())
    check('attachments falls back to the single field',
          len(legacy.attachments) == 1, len(legacy.attachments))
    check('and reports it as a picture',
          legacy.attachments[0].is_picture)


def check_coach_uploads_many(coach_user, school, student):
    print('\n2. a coach attaches several files at once')
    client = sign_in(coach_user)

    html = page(client, '/teacher/sessions/student-project-upload/')
    if 'name="files"' not in html:
        # The route differs between builds; find it rather than guess.
        html = page(client, '/teacher/student-project-upload/')
    check('the form takes more than one file',
          'name="files"' in html and 'multiple' in html)

    client.post('/teacher/student-project-upload/', {
        'grade': '6', 'division': 'A', 'title': 'Zz Multi Upload',
        'description': 'Three files',
        'files': [png('zz-one.png'), png('zz-two.png'), pdf('zz-three.pdf')],
        'students': [student.id],
    }, follow=True)

    made = StudentProjectUpload.objects.filter(
        school=school, title='Zz Multi Upload').first()
    check('the upload was created', made is not None)
    if not made:
        return None

    rows = list(made.files.all())
    for r in rows:
        WROTE.append(r.file.name)
    check('all three files were kept', len(rows) == 3, len(rows))
    check('their order is the order they were picked',
          [r.order for r in rows] == [0, 1, 2], [r.order for r in rows])
    check('two are pictures and one is not',
          len(made.photo_attachments) == 2
          and len(made.document_attachments) == 1,
          f'{len(made.photo_attachments)} photos, '
          f'{len(made.document_attachments)} documents')
    check('the student is tagged on it', made.students.filter(
        id=student.id).exists())
    return made


def check_my_projects(student_user, legacy, multi):
    print('\n3. My Projects shows the work, photos and documents alike')
    client = sign_in(student_user)

    code = client.get('/student/projects/').status_code
    check('the page exists', code in (200, 302), code)

    html = page(client, '/student/projects/')
    check('the heading is there', 'My Projects' in html)
    check('the legacy upload is listed', 'Zz Legacy Upload' in html)
    check('its description is shown',
          'Made before files had rows of their own' in html)
    check('its photo is rendered, not merely linked',
          legacy.attachments[0].file.url in html)

    if multi:
        check('the newer upload is listed too', 'Zz Multi Upload' in html)
        for row in multi.photo_attachments:
            check(f'photo {row.order + 1} is on the page', row.file.url in html)
        for row in multi.document_attachments:
            check('the document is linked', row.file.url in html)
        check('documents are labelled as documents', 'Document' in html)
    return client


def check_dashboard_moved(client, legacy):
    print('\n4. the dashboard points at it instead of listing it')
    html = page(client, '/student/dashboard/')
    check('the dashboard offers the way in', 'My Projects' in html)
    check('it links to the page', '/student/projects/' in html)

    # The title still appears, in the notification bell, which is right --
    # the bell is how a student learns something new arrived. What must be
    # gone is the inline listing, and the files are what prove it.
    check('the files are no longer rendered on the dashboard',
          legacy.attachments[0].file.url not in html)

    # And the bell has to lead somewhere real: it pointed at an anchor on the
    # dashboard that the move deleted.
    check('the bell points at My Projects, not a dead anchor',
          '#view-projects' not in html)


def check_sidebar(client):
    print('\n5. the sidebar carries it, beside Project Report')
    html = page(client, '/student/dashboard/')
    check('a My Projects entry is in the menu', 'nav-my-projects' in html)
    check('Project Report is still there', 'nav-reports' in html)


# ---------------------------------------------------------------------- run

def cleanup():
    removed = 0
    for name in WROTE:
        path = os.path.join(settings.MEDIA_ROOT, name.replace('/', os.sep))
        if os.path.exists(path):
            os.remove(path)
            removed += 1
    return removed


def run():
    print('=' * 60)
    print('Project uploads: several files, and the My Projects page')
    print('=' * 60)

    try:
        with transaction.atomic():
            school, student, student_user, coach_user, legacy = build()
            check_legacy_fallback(legacy)
            multi = check_coach_uploads_many(coach_user, school, student)
            client = check_my_projects(student_user, legacy, multi)
            check_dashboard_moved(client, legacy)
            check_sidebar(client)
            raise Rollback
    except Rollback:
        pass

    print('\nNothing survives')
    left = (School.objects.filter(school_code='ZZFILE').count()
            + StudentProjectUpload.objects.filter(
                title__startswith='Zz ').count()
            + ProjectUploadFile.objects.filter(
                file__startswith='student_projects/zz-').count()
            + U.objects.filter(username__startswith='zz.files.').count())
    check('no row this suite created survived', left == 0, left)
    print(f'  ..    removed {cleanup()} uploaded file(s)')

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f.strip()}')


if __name__ == '__main__':
    run()
