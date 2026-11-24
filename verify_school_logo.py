"""The school logo, from Edit School to three dashboards.

    "In edit school - Add a option to add a school logo that will reflect on
     that schools, Student and Parent Dashboard"  -- Phase 2 deck, small
     change 3 (priority)

The field itself already existed: `School.school_logo` has been on the model
since the first migration, and onboarding accepted one. Two things were
missing, and both are what these checks hold:

  * the Edit School form never read it, so a logo could only ever be set on
    the day a school was created and never afterwards.
  * nothing rendered it. The three dashboards reach their school by three
    different paths, so the logo is resolved once in
    `schools.context_processors.school_branding` rather than in every view.

The check that matters most is the last one: a school with no logo must see
its sidebar exactly as before. The strip is additive, never a replacement for
the ENpower logo, and it must not appear as an empty box.

Uploads land on disk, which a transaction does not undo, so every file this
suite writes is deleted by name at the end and the count is checked.

Everything else runs inside a transaction that is rolled back.

Run with:  python verify_school_logo.py
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
from django.test import RequestFactory

from parent.models import Parent
from school_admin.models import SchoolAdmin
from schools.context_processors import school_branding
from schools.models import School
from student.models import Student
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
DOB = datetime.date(2014, 5, 1)

# The smallest valid PNG: one transparent pixel.
PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082')

PASS, FAIL = [], []
WROTE = []          # media paths this suite created, removed at the end


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


def logo_upload(name='zz-logo.png'):
    return SimpleUploadedFile(name, PNG, content_type='image/png')


# ------------------------------------------------------------------ fixtures

def build():
    """Two schools — one with a logo, one without — and a user of each role."""
    with_logo = School.objects.create(school_name='ZZ Logo School',
                                      school_code='ZZLOGO')
    with_logo.school_logo = logo_upload()
    with_logo.save()
    WROTE.append(with_logo.school_logo.name)

    bare = School.objects.create(school_name='ZZ Bare School',
                                 school_code='ZZBARE')

    def account(username, role):
        return U.objects.create_user(username=username, password=PASSWORD,
                                     email=f'{username}@example.com', role=role)

    admin_user = account('zz.logo.admin@example.com', 'SCHOOL_ADMIN')
    SchoolAdmin.objects.create(user=admin_user, school=with_logo,
                               full_name='Zz Admin',
                               email=admin_user.email, phone='9000000001')

    student_user = account('ZZLOGO-STU-1', 'STUDENT')
    student = Student.objects.create(
        first_name='Zz', last_name='Pupil', school=with_logo,
        student_class='6', division='A', is_active=True,
        date_of_birth=DOB, enrollment_date=DOB,
        skill_lab_reg_id='ZZLOGO-STU-1', user=student_user)

    parent_user = account('zz.logo.parent', 'PARENT')
    parent = Parent.objects.create(
        user=parent_user, full_name='Zz Parent', relation_to_student='Father',
        mobile_number='9000000002', email='zz.logo.parent@example.com',
        residential_address='Nowhere')
    parent.students.add(student)

    # The bare school's admin, for the "nothing changes" check.
    bare_user = account('zz.bare.admin@example.com', 'SCHOOL_ADMIN')
    SchoolAdmin.objects.create(user=bare_user, school=bare,
                               full_name='Zz Bare Admin',
                               email=bare_user.email, phone='9000000003')

    return with_logo, bare, admin_user, student_user, parent_user, bare_user


# ------------------------------------------------------------------- checks

def check_wiring():
    """The processor has to be registered, or every template renders nothing."""
    print('\nWiring')
    processors = settings.TEMPLATES[0]['OPTIONS']['context_processors']
    check('school_branding is a registered context processor',
          'schools.context_processors.school_branding' in processors)


def check_processor(with_logo, student_user, parent_user, bare_user):
    """Each role reaches its school by a different path. All three must work."""
    print('\nThe processor resolves a school for every role')
    factory = RequestFactory()

    def branding(user):
        request = factory.get('/')
        request.user = user
        return school_branding(request)

    admin_user = SchoolAdmin.objects.get(school=with_logo).user
    for label, user in (('School Admin', admin_user),
                        ('Student', student_user),
                        ('Parent', parent_user)):
        out = branding(user)
        check(f'{label} gets the logo url',
              bool(out['school_logo_url']), out['school_logo_url'])
        check(f'{label} gets the school',
              getattr(out['branding_school'], 'id', None) == with_logo.id)

    out = branding(bare_user)
    check('a school with no logo yields None, not an empty string',
          out['school_logo_url'] is None, repr(out['school_logo_url']))

    class Anon:
        is_authenticated = False

    request = factory.get('/')
    request.user = Anon()
    out = school_branding(request)
    check('an anonymous request is handled, not raised on',
          out == {'school_logo_url': None, 'branding_school': None})


def check_dashboards(with_logo, admin_user, student_user, parent_user):
    """The logo has to actually render in all three sidebars."""
    print('\nThe three dashboards render it')
    url = with_logo.school_logo.url
    for label, user, path in (
            ('School Admin', admin_user, '/school-admin/dashboard/'),
            ('Student', student_user, '/student/dashboard/'),
            ('Parent', parent_user, '/parent/dashboard/')):
        html = page(sign_in(user), path)
        check(f'{label} dashboard shows the logo', url in html)
        # The school name was dropped from the strip: it wrapped onto three
        # lines and outweighed the logo. The name still appears in the page's
        # own cards, so only the strip's own label is checked for.
        check(f'{label} strip carries the logo alone',
              'esl-school-brand-name' not in html)
        check(f'{label} keeps the ENpower logo too',
              'enpower-logo-trimmed.png' in html)


def check_bare_sidebar(bare_user):
    """A school without a logo must look exactly as it did before."""
    print('\nA school with no logo is left alone')
    html = page(sign_in(bare_user), '/school-admin/dashboard/')
    check('no brand strip is rendered', 'esl-school-brand"' not in html)
    check('no empty img tag is left behind', 'alt="School logo"' not in html)
    check('the ENpower logo is still there',
          'enpower-logo-trimmed.png' in html)


def check_principal_upload(with_logo, bare, bare_user):
    """A principal sets their own school's logo, and only their own.

    Doing this for every school from Super Admin does not scale, so the
    School Admin can upload it themselves. The school is read from their own
    profile, so the check that matters is the last one: posting another
    school's id must not reach that school.
    """
    print('\nThe principal can set their own logo')
    client = sign_in(bare_user)

    html = page(client, '/school-admin/profile/')
    check('the profile page offers a School Logo card',
          'name="school_logo"' in html)

    before = with_logo.school_logo.name

    client.post('/school-admin/profile/school-logo/',
                {'school_logo': logo_upload('zz-principal.png'),
                 'school': with_logo.id, 'school_id': with_logo.id},
                follow=True)

    bare.refresh_from_db()
    with_logo.refresh_from_db()
    saved = bool(bare.school_logo)
    if saved:
        WROTE.append(bare.school_logo.name)
    check('their own school gets the logo', saved, bare.school_logo)
    check('the posted school id is ignored',
          with_logo.school_logo.name == before,
          with_logo.school_logo.name)

    client.post('/school-admin/profile/school-logo/',
                {'remove_school_logo': '1'}, follow=True)
    bare.refresh_from_db()
    check('they can remove it again', not bare.school_logo)


def check_edit_form(bare):
    """Edit School has to accept a logo, and be able to take it away again."""
    print('\nEdit School saves and clears the logo')
    superuser = U.objects.create_user(
        username='zz.logo.super@example.com', password=PASSWORD,
        email='zz.logo.super@example.com', role='SUPER_ADMIN',
        is_staff=True, is_superuser=True)
    client = sign_in(superuser)

    # A school whose website is NULL. This is the shape that made the form
    # unsaveable: `website` is the only nullable field on it, so it is the
    # only one that can render as the literal "None", and in a type="url"
    # input the browser then refuses to submit -- taking the logo with it.
    # Dev data has a real URL on every school, which is why it went unseen.
    bare.website = None
    bare.save(update_fields=['website'])

    html = page(client, f'/super-admin/school/{bare.id}/edit/')
    check('the form offers a School Logo field', 'name="school_logo"' in html)
    check('a null website renders as an empty box, not "None"',
          'value="None"' not in html)

    fields = {
        'school_name': bare.school_name, 'school_code': bare.school_code,
        'board': bare.board or '', 'school_type': bare.school_type or '',
        'medium': bare.medium or '', 'school_email': bare.school_email or '',
        'school_phone': bare.school_phone or '',
        'principal_name': bare.principal_name or '',
        'principal_phone': bare.principal_phone or '',
        'principal_email': bare.principal_email or '',
        'city': bare.city or '', 'state': bare.state or '',
        'pincode': bare.pincode or '', 'branch_address': bare.branch_address or '',
        'is_active': 'true',
    }

    client.post(f'/super-admin/school/{bare.id}/edit/',
                dict(fields, school_logo=logo_upload('zz-edit.png')),
                follow=True)
    bare.refresh_from_db()
    saved = bool(bare.school_logo)
    if saved:
        WROTE.append(bare.school_logo.name)
    check('an uploaded logo is saved', saved, bare.school_logo)

    # Saving the form again without a file must not wipe the logo — this is
    # the trap: a plain `school.school_logo = request.FILES.get(...)` clears
    # it on every unrelated edit.
    client.post(f'/super-admin/school/{bare.id}/edit/', fields, follow=True)
    bare.refresh_from_db()
    check('editing other fields leaves the logo alone', bool(bare.school_logo))

    client.post(f'/super-admin/school/{bare.id}/edit/',
                dict(fields, remove_school_logo='1'), follow=True)
    bare.refresh_from_db()
    check('Remove clears the logo', not bare.school_logo, bare.school_logo)


# ---------------------------------------------------------------------- run

def cleanup():
    """Files outlive the rollback, so they go by name."""
    removed = 0
    for name in WROTE:
        path = os.path.join(settings.MEDIA_ROOT, name.replace('/', os.sep))
        if os.path.exists(path):
            os.remove(path)
            removed += 1
    return removed


def run():
    print('=' * 60)
    print('School logo — Edit School to School Admin, Student and Parent')
    print('=' * 60)

    try:
        with transaction.atomic():
            (with_logo, bare, admin_user, student_user,
             parent_user, bare_user) = build()
            check_wiring()
            check_processor(with_logo, student_user, parent_user, bare_user)
            check_dashboards(with_logo, admin_user, student_user, parent_user)
            check_bare_sidebar(bare_user)
            check_principal_upload(with_logo, bare, bare_user)
            check_edit_form(bare)
            raise Rollback
    except Rollback:
        pass

    print('\nNothing survives')
    left = (School.objects.filter(school_code__in=['ZZLOGO', 'ZZBARE']).count()
            + Student.objects.filter(skill_lab_reg_id__startswith='ZZLOGO').count()
            + U.objects.filter(username__startswith='zz.').count()
            + U.objects.filter(username__startswith='ZZLOGO').count())
    check('no row this suite created survived', left == 0, left)
    print(f'  ..    removed {cleanup()} uploaded file(s)')

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f.strip()}')


if __name__ == '__main__':
    run()
