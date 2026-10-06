"""A coach's upload must reach the child, the parent, and the bell.

Slide 47 point 6. The student half was built and the parent half was not --
`parent/views.py` imported `student_project_uploads` and never called it --
and nothing anywhere raised a notification, because `Announcement` targets a
role, a programme, a school and a grade, never one child.

The part that made it look broken rather than half-built: a coach uploads
photographs of the work, and the student's dashboard rendered them as a
"View File" link. To the reader that is indistinguishable from nothing having
arrived, which is how it was reported.

Everything here runs inside a transaction that is rolled back. The uploaded
file lands on disk outside that transaction, so it is removed by hand.

Run with:  python verify_project_uploads.py
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
from django.core.files.base import ContentFile
from django.db import transaction

from attendance.models import StudentProjectUpload
from attendance.services import student_project_uploads
from parent.models import Parent
from student.models import Student
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
PHOTO_TITLE = 'ZZ Upload Solar Car'
DOC_TITLE = 'ZZ Upload Write-up'
DRIFT_TITLE = 'ZZ Upload Filed In The Other Case'

PASS, FAIL = [], []
written_files = []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}'
          f'{("  — " + str(detail)) if detail else ""}')


class Rollback(Exception):
    """Raised once the checks are done, to undo everything they created."""


def attach(upload, filename, payload=b'\xff\xd8\xff\xe0 not really an image'):
    upload.file.save(filename, ContentFile(payload), save=True)
    written_files.append(upload.file.path)
    return upload


def make_upload(student, title, filename=None, division=None):
    upload = StudentProjectUpload.objects.create(
        school=student.school, grade=str(student.student_class),
        division=division if division is not None else student.division,
        title=title, description='Made by the class.')
    if filename:
        attach(upload, filename)
    return upload


def sign_in(user):
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    client = Client()
    assert client.login(username=user.username, password=PASSWORD), \
        f'could not sign in as {user.username}'
    return client


def check_picture_test():
    print('\n1. which files can be shown rather than linked')
    photo = StudentProjectUpload(file=None)
    for name, expected in (('photo.JPEG', True), ('photo.png', True),
                           ('clip.webp', True), ('report.pdf', False),
                           ('deck.pptx', False), ('', False)):
        photo.file.name = name
        check(f'{name or "(no file)"!r} is a picture: {expected}',
              photo.is_picture == expected)


def check_student_sees_it(student):
    print('\n2. the student\'s own dashboard')
    photo = make_upload(student, PHOTO_TITLE, 'zz_probe_photo.jpeg')
    photo.students.set([student])
    doc = make_upload(student, DOC_TITLE, 'zz_probe_doc.pdf')
    doc.students.set([student])

    body = sign_in(student.user).get(
        '/student/dashboard/', follow=True).content.decode(errors='ignore')
    check('the photo upload is listed', PHOTO_TITLE in body)
    check('the photo is shown as an image', f'<img src="{photo.file.url}"' in body)
    # Which files got an attach_file link: for each icon, walk back to the
    # href of the anchor it sits inside. Splitting the page on 'attach_file'
    # and searching the pieces looks equivalent and is not -- the first piece
    # is the whole page above the first icon, so the photo lands in it and the
    # check passes while testing nothing.
    linked = []
    for piece in body.split('attach_file')[:-1]:
        anchor = piece.rfind('<a ')
        if anchor == -1:
            continue
        start = piece.find('href="', anchor)
        if start == -1:
            continue
        start += len('href="')
        linked.append(piece[start:piece.find('"', start)])
    check('a picture gets no "View File" link',
          photo.file.url not in linked, linked)
    check('the document is the one that got the link',
          doc.file.url in linked, linked)
    check('the document upload is listed', DOC_TITLE in body)
    check('a document still gets a link', doc.file.url in body)
    check('a document is not rendered as an image',
          f'<img src="{doc.file.url}"' not in body)
    return photo


def check_bell(student, parent):
    print('\n3. the notification bell')
    # Read it on a page that is not the dashboard: the dashboard is what
    # clears the mark, so reading it there would hide what we are checking.
    body = sign_in(student.user).get(
        '/student/reports/', follow=True).content.decode(errors='ignore')
    check('the student\'s bell names the upload', PHOTO_TITLE in body)

    if parent is None:
        print('  (no parent with a login on this database)')
        return
    # Not the parent dashboard either: that page carries the project card as
    # well, so the title would be found there whether the bell worked or not.
    child = parent.students.filter(is_active=True).first()
    pbody = sign_in(parent.user).get(
        f'/parent/child/{child.id}/reports/',
        follow=True).content.decode(errors='ignore')
    check('the parent\'s bell names the upload', PHOTO_TITLE in pbody)


def check_parent_sees_it(parent, photo):
    print('\n4. the parent\'s dashboard')
    if parent is None:
        print('  (no parent with a login on this database)')
        return
    body = sign_in(parent.user).get(
        '/parent/dashboard/', follow=True).content.decode(errors='ignore')
    # Look inside the card, not at the whole page: the bell on this same page
    # also names the upload, so a page-wide search passes even with the
    # dashboard section removed, which is exactly what it must catch.
    start = body.find('id="view-projects"')
    check('the parent dashboard has a project card', start != -1)
    card = body[start:body.find('<!-- Main Content Grid -->', start)] if start != -1 else ''
    check('the upload is listed in that card', PHOTO_TITLE in card)
    check('the photo is shown as an image', f'<img src="{photo.file.url}"' in card)
    check('the document is listed too', DOC_TITLE in card)


def check_case_drift(student):
    print('\n5. an upload filed under the other case still arrives')
    # Nothing tagged, so this can only arrive through the whole-class fallback,
    # which is the path that lost an upload filed as '6 b' against a class
    # holding 'B'.
    other_case = (student.division.lower() if student.division.isupper()
                  else student.division.upper())
    make_upload(student, DRIFT_TITLE, division=other_case)
    # Make the untagged student rather than hunting for one, or the check
    # quietly skips itself on a database where every child is already tagged.
    loner = Student.objects.create(
        first_name='ZZ', last_name='Fallback', school=student.school,
        date_of_birth=datetime.date(2014, 5, 1),
        enrollment_date=datetime.date(2025, 6, 1),
        student_class=student.student_class, division=student.division,
        is_active=True, skill_lab_reg_id='ZZ-UPLOAD-FALLBACK')
    titles = [u.title for u in student_project_uploads(loner)]
    check(f'an upload filed as {other_case!r} reaches a class holding '
          f'{student.division!r}', DRIFT_TITLE in titles, titles[:3])


def check_form_normalises():
    print('\n6. the upload form settles the section before storing it')
    import inspect

    from teacher import views

    source = inspect.getsource(views.student_project_upload)
    check('the section is upper-cased on the way in',
          ".get('division', '').strip().upper()" in source)


def run():
    student = (Student.objects
               .select_related('school', 'user')
               .filter(user__isnull=False, school__isnull=False, is_active=True)
               .first())
    assert student, 'no student with a login to test with'
    parent = Parent.objects.filter(students=student, user__isnull=False).first()
    if parent is None:
        parent = Parent.objects.filter(user__isnull=False).first()

    print(f'  student: {student.full_name} ({student.skill_lab_reg_id})')
    print(f'  parent : {parent.user.username if parent else "(none)"}')

    try:
        with transaction.atomic():
            if parent and student not in parent.students.all():
                parent.students.add(student)
            check_picture_test()
            photo = check_student_sees_it(student)
            check_bell(student, parent)
            check_parent_sees_it(parent, photo)
            check_case_drift(student)
            check_form_normalises()
            raise Rollback
    except Rollback:
        pass
    finally:
        # The database rolls back; the filesystem does not.
        for path in written_files:
            try:
                os.remove(path)
            except OSError:
                pass

    left = StudentProjectUpload.objects.filter(
        title__in=(PHOTO_TITLE, DOC_TITLE, DRIFT_TITLE)).count()
    on_disk = sum(1 for p in written_files if os.path.exists(p))
    check('no upload rows survived', left == 0, left)
    check('no files were left on disk', on_disk == 0, on_disk)

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    run()
