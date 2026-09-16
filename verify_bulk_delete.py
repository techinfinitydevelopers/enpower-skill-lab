"""
Check select-and-delete on the list screens.

  python verify_bulk_delete.py

This is the one feature in the app that destroys data on purpose, so the
checks are about what it refuses as much as what it does:

  a row the list does not show cannot be deleted by putting its id in the
  POST -- the ids are filtered through the list's own queryset;

  no other role can reach the endpoint, and neither can an anonymous caller;

  the preview reports the real cascade, because deleting a school takes its
  classes, its admins, its coaches and every student in it, and deleting a
  student takes every score entry and report they have;

  the login account goes with the profile. It did not before: School Admin
  and Coordinator deleted theirs, Student, Teacher and Parent did not, which
  left accounts that could still sign in with no profile behind them.

Everything it creates is its own; it deletes nothing that was already here.
"""

import atexit
import json
import os
import re
import sys
from datetime import date

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enpower_skill_lab.settings')
django.setup()

from django.conf import settings                          # noqa: E402

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

from django.contrib.auth import get_user_model            # noqa: E402

from enpower_skill_lab.bulk_delete import _registry       # noqa: E402
from verify_client import HttpsClient as Client           # noqa: E402

U = get_user_model()
PASS, FAIL = [], []
restore = {}
MARKER = 'zzbulkdel'
PASSWORD = 'BulkDel!2026'


def _cleanup():
    from schools.models import School
    from student.models import Student
    from teacher.models import Teacher
    Student.objects.filter(gr_number__startswith=MARKER).delete()
    Teacher.objects.filter(employee_id__startswith=MARKER).delete()
    School.objects.filter(school_code__startswith=MARKER.upper()).delete()
    U.objects.filter(username__startswith=MARKER).delete()
    for pk, password in list(restore.items()):
        U.objects.filter(pk=pk).update(password=password)
    restore.clear()


atexit.register(_cleanup)
_cleanup()


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}{("  - " + detail) if detail else ""}')


def sign_in(role):
    user = U.objects.filter(role=role, is_active=True).first()
    if not user:
        return None
    restore.setdefault(user.pk, U.objects.get(pk=user.pk).password)
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    c = Client()
    return c if c.login(username=user.username, password=PASSWORD) else None


admin = sign_in('SUPER_ADMIN')
assert admin, 'no Super Admin to test with'

registry = _registry()
print(f'\n  {len(registry)} lists registered: {", ".join(registry)}\n')


# ── fixtures of our own ─────────────────────────────────────────────────
def make_student(suffix, school=None):
    from student.models import Student
    user = U.objects.create_user(username=f'{MARKER}stu{suffix}',
                                 password=PASSWORD, role='STUDENT')
    return Student.objects.create(
        first_name='ZZ', last_name=f'Delcheck{suffix}',
        gender='Male', date_of_birth=date(2012, 1, 1),
        student_class='6', division='A', roll_number=str(suffix),
        academic_year='2025-26', school_board='CBSE',
        school_email=f'{MARKER}{suffix}@example.com',
        enrollment_date=date(2025, 6, 1), emergency_name='ZZ Contact',
        emergency_relationship='Parent', emergency_mobile='9000000000',
        gr_number=f'{MARKER}-{suffix}', skill_lab_reg_id=f'{MARKER}-{suffix}',
        user=user, school=school)


def make_school():
    return School.objects.create(
        school_name='ZZ Delcheck School', school_code=f'{MARKER.upper()}1',
        board='CBSE', school_type='Private', medium='English',
        school_email=f'{MARKER}school@example.com', school_phone='9000000001',
        principal_name='ZZ Principal', principal_phone='9000000002',
        principal_email=f'{MARKER}principal@example.com',
        branch_address='ZZ Address', city='Mumbai', state='Maharashtra',
        pincode='400001', emergency_contact_person='ZZ Contact',
        emergency_phone='9000000003')


from schools.models import School                          # noqa: E402
from student.models import Student                         # noqa: E402
from teacher.models import Teacher                         # noqa: E402

# ── the endpoint refuses everyone it should ─────────────────────────────
print('ACCESS')
victim = make_student('access')
anon = Client()
for path in (f'/bulk-delete/students/', '/bulk-delete/students/preview/'):
    r = anon.post(path, {'ids': [victim.id]})
    check(f'anonymous is refused {path}', r.status_code in (301, 302, 403, 404),
          f'HTTP {r.status_code}')

for role in ('THINKING_COACH', 'SCHOOL_ADMIN', 'PROGRAM_COORDINATOR',
             'PARENT', 'STUDENT'):
    c = sign_in(role)
    if not c:
        print(f'  ..    no {role} account on this database')
        continue
    r = c.post('/bulk-delete/students/', {'ids': [victim.id]})
    check(f'{role} is refused', r.status_code in (301, 302, 403, 404),
          f'HTTP {r.status_code}')
check('and the row they aimed at is still here',
      Student.objects.filter(id=victim.id).exists())

check('an unknown list key is refused',
      admin.post('/bulk-delete/not-a-list/', {'ids': [1]}).status_code != 200)
check('GET is refused',
      admin.get('/bulk-delete/students/').status_code != 200)

# ── the preview tells the truth ─────────────────────────────────────────
print('\nTHE PREVIEW')
from competencies.models import ScoreEntry                 # noqa: E402

scored = Student.objects.exclude(id=victim.id).filter(
    id__in=ScoreEntry.objects.values('student_id')).first()

r = admin.post('/bulk-delete/students/preview/',
               {'ids': [victim.id] + ([scored.id] if scored else [])})
check('preview responds 200', r.status_code == 200, f'HTTP {r.status_code}')
data = json.loads(r.content)
check('it counts the selection', data['count'] == (2 if scored else 1),
      str(data['count']))
check('it names the rows', bool(data['names']), str(data['names'])[:80])
check('it uses the plural when there is more than one',
      data['label'] == ('students' if scored else 'student'), data['label'])
check('it reports the login accounts that go with them',
      any(i['what'] == 'login account' for i in data['impact']),
      str(data['impact']))

if scored:
    real = ScoreEntry.objects.filter(student=scored).count()
    reported = next((i['count'] for i in data['impact']
                     if i['what'] == 'score entry'), 0)
    check('the score-entry count is the real one', reported == real,
          f'reported {reported}, actual {real}')

check('the preview destroys nothing',
      Student.objects.filter(id=victim.id).exists()
      and (not scored or Student.objects.filter(id=scored.id).exists()))

# ── an id outside the list cannot be smuggled in ────────────────────────
print('\nIDS ARE FILTERED THROUGH THE LIST, NOT TRUSTED')
coach_user = U.objects.filter(role='THINKING_COACH').first()
r = admin.post('/bulk-delete/students/preview/',
               {'ids': [victim.id, 999999999]})
check('a nonexistent id is dropped rather than counted',
      json.loads(r.content)['count'] == 1,
      str(json.loads(r.content)['count']))

teacher_row = Teacher.objects.first()
if teacher_row:
    r = admin.post('/bulk-delete/students/preview/', {'ids': [teacher_row.id]})
    counted = json.loads(r.content)['count']
    stray = Student.objects.filter(id=teacher_row.id).exists()
    check("a teacher's id on the students list matches only a student",
          counted == (1 if stray else 0), f'count={counted}')

r = admin.post('/bulk-delete/students/', {'ids': ['abc', '', 'null']})
check('junk ids delete nothing', json.loads(r.content)['deleted'] == 0,
      r.content.decode()[:90])
check('and say so', 'Nothing was selected' in json.loads(r.content)['message'])

# ── the delete, and the account behind it ───────────────────────────────
print('\nTHE DELETE TAKES THE LOGIN ACCOUNT WITH IT')
target = make_student('withuser')
uid = target.user_id
r = admin.post('/bulk-delete/students/', {'ids': [target.id]})
check('delete responds 200', r.status_code == 200, f'HTTP {r.status_code}')
out = json.loads(r.content)
check('it reports one deleted', out['deleted'] == 1, str(out))
check('the student is gone', not Student.objects.filter(id=target.id).exists())
check('the login account is gone too -- this is what leaked before',
      not U.objects.filter(id=uid).exists())

print('\nDELETING MANY AT ONCE')
batch = [make_student(f'b{i}') for i in range(4)]
ids = [s.id for s in batch]
uids = [s.user_id for s in batch]
r = admin.post('/bulk-delete/students/', {'ids': ids})
out = json.loads(r.content)
check('all four went', out['deleted'] == 4, str(out))
check('none is left behind', not Student.objects.filter(id__in=ids).exists())
check('no account is left behind', not U.objects.filter(id__in=uids).exists())
check('nothing failed', out['failed'] == 0, str(out.get('failures')))

# ── a school takes its people with it ───────────────────────────────────
print('\nA SCHOOL TAKES ITS PEOPLE WITH IT  (they were stranded before)')
school = make_school()
inside = [make_student(f's{i}', school=school) for i in range(3)]
inside_ids = [s.id for s in inside]
inside_uids = [s.user_id for s in inside]

r = admin.post('/bulk-delete/schools/preview/', {'ids': [school.id]})
data = json.loads(r.content)
reported = next((i['count'] for i in data['impact'] if i['what'] == 'student'), 0)
check('the preview counts the students inside', reported == 3, str(data['impact']))
check('and warns about their login accounts',
      any('login account' in i['what'] for i in data['impact']),
      str(data['impact']))

r = admin.post('/bulk-delete/schools/', {'ids': [school.id]})
check('the school is gone', not School.objects.filter(id=school.id).exists())
check('its students went with it, not into limbo',
      not Student.objects.filter(id__in=inside_ids).exists(),
      f'{Student.objects.filter(id__in=inside_ids).count()} stranded')
check('and so did their login accounts',
      not U.objects.filter(id__in=inside_uids).exists())

# ── the checkbox is actually on the page ────────────────────────────────
print('\nTHE CHECKBOX IS ON THE PAGE')
PAGES = {
    'schools':       '/super-admin/schools/',
    'students':      '/super-admin/students/',
    'teachers':      '/super-admin/teachers/',
    'parents':       '/super-admin/parents/',
    'coordinators':  '/super-admin/coordinators/',
    'school-admins': '/super-admin/school-admins/',
}
check('every registered list has a page here',
      set(PAGES) == set(registry),
      f'registry={sorted(registry)} pages={sorted(PAGES)}')

for key, url in PAGES.items():
    r = admin.get(url, follow=True)
    if r.status_code != 200:
        check(f'{key}: page loads', False, f'HTTP {r.status_code}')
        continue
    html = r.content.decode(errors='ignore')
    check(f'{key}: select-all checkbox present', 'class="bd-all"' in html)
    check(f'{key}: rows carry a checkbox with an id',
          re.search(r'class="bd-row" data-id="\d+"', html) is not None)
    check(f'{key}: the shared script is loaded', 'js/common/bulk-delete.js' in html)
    check(f'{key}: the stylesheet is loaded', 'css/common/bulk-delete.css' in html)
    check(f'{key}: it is initialised with this list\'s key',
          f"initBulkDelete({{ key: '{key}'" in html)

    # Every body row must have the same number of cells as the header, or the
    # new column pushes the table out of alignment -- the kind of break a
    # status-code check never sees.
    head = re.search(r'<thead.*?</thead>', html, re.S)
    rows = re.findall(r'<tbody.*?</tbody>', html, re.S)
    if head and rows:
        want = len(re.findall(r'<th[\s>]', head.group(0)))
        widths = set()
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', rows[0], re.S):
            if 'colspan' in row:
                continue
            cells = len(re.findall(r'<td[\s>]', row))
            if cells:
                widths.add(cells)
        check(f'{key}: every row has {want} cells, matching the header',
              not widths or widths == {want}, f'header={want} rows={sorted(widths)}')

# ── DataTables indices moved with the column ────────────────────────────
print('\nTHE SORTING CONFIG MOVED WITH THE COLUMN')
for path in ('static/js/superadmin/school-list.js',
             'static/js/common/student-list.js',
             'static/js/superadmin/teacher-list.js',
             'static/js/superadmin/pc-list.js',
             'static/js/superadmin/school-admin-list.js',
             'superadmin/templates/superadmin/parent-list.html'):
    text = open(os.path.join(settings.BASE_DIR, path),
                encoding='utf-8', errors='ignore').read()
    match = re.search(r'orderable:\s*false,\s*targets:\s*\[([^\]]*)\]', text)
    check(f'{os.path.basename(path)}: column 0 is not sortable',
          match is not None and match.group(1).strip().startswith('0'),
          match.group(1) if match else 'no targets found')

# ── the single-row delete behaves the same way ──────────────────────
# Two ways to delete the same row must not leave two different results.
print(chr(10) + 'ONE AT A TIME LEAVES NOTHING BEHIND EITHER')
single = make_student('single')
single_uid = single.user_id
r = admin.post(f'/super-admin/student/{single.id}/delete/', follow=True)
check('the single delete still works', r.status_code == 200, f'HTTP {r.status_code}')
check('the student is gone', not Student.objects.filter(id=single.id).exists())
check('and so is the login account -- it was not before',
      not U.objects.filter(id=single_uid).exists())

lone = make_school()
lone_student = make_student('lone', school=lone)
lone_uid = lone_student.user_id
admin.post(f'/super-admin/school/{lone.id}/delete/', follow=True)
check('deleting one school takes its student too',
      not Student.objects.filter(id=lone_student.id).exists())
check('and that student login account is gone too',
      not U.objects.filter(id=lone_uid).exists())


# -- ids as a JSON body -------------------------------------------------
# A select-all on the student list is 1290 ids. As form fields that is past
# DATA_UPLOAD_MAX_NUMBER_FIELDS (1000) and Django rejects the request before
# the view runs, so the ids travel as one JSON body instead.
print(chr(10) + 'A SELECT-ALL IS TOO BIG FOR FORM FIELDS')
from django.conf import settings as _s                     # noqa: E402

cap = _s.DATA_UPLOAD_MAX_NUMBER_FIELDS
check('the field cap is still low enough to matter', cap is not None and cap <= 1000,
      str(cap))

many = [str(n) for n in range(900000, 900000 + cap + 20)]
r = admin.post('/bulk-delete/students/', {'ids': many})
check(f'{len(many)} ids as form fields are rejected, as expected',
      r.status_code == 400, f'HTTP {r.status_code}')

r = admin.post('/bulk-delete/students/', json.dumps({'ids': many}),
               content_type='application/json')
check(f'the same {len(many)} ids as a JSON body go through',
      r.status_code == 200, f'HTTP {r.status_code}')
check('and match nothing, so nothing is deleted',
      json.loads(r.content)['deleted'] == 0, r.content.decode()[:80])

json_kid = make_student('jsonbody')
json_uid = json_kid.user_id
r = admin.post('/bulk-delete/students/preview/',
               json.dumps({'ids': [json_kid.id]}),
               content_type='application/json')
check('preview reads a JSON body too', json.loads(r.content)['count'] == 1,
      r.content.decode()[:80])
r = admin.post('/bulk-delete/students/', json.dumps({'ids': [json_kid.id]}),
               content_type='application/json')
check('a JSON delete removes the row',
      not Student.objects.filter(id=json_kid.id).exists())
check('and its login account', not U.objects.filter(id=json_uid).exists())

r = admin.post('/bulk-delete/students/', 'not json at all',
               content_type='application/json')
check('a body that is not JSON deletes nothing rather than erroring',
      r.status_code == 200 and json.loads(r.content)['deleted'] == 0,
      f'HTTP {r.status_code}')
r = admin.post('/bulk-delete/students/', {})
check('an empty form post deletes nothing rather than erroring',
      r.status_code == 200 and json.loads(r.content)['deleted'] == 0,
      f'HTTP {r.status_code}')

# -- the bulk path ------------------------------------------------------
# One transaction per row cannot finish a thousand rows inside the 60s
# worker timeout, so the delete runs as a handful of statements instead.
print(chr(10) + 'THE BULK PATH')
import enpower_skill_lab.bulk_delete as bd                 # noqa: E402

herd = [make_student(f'bulk{i}') for i in range(6)]
herd_ids = [s.id for s in herd]
herd_uids = [s.user_id for s in herd]

from django.db import connection, reset_queries            # noqa: E402

was_debug = _s.DEBUG
_s.DEBUG = True
reset_queries()
r = admin.post('/bulk-delete/students/', json.dumps({'ids': herd_ids}),
               content_type='application/json')
queries = len(connection.queries)
_s.DEBUG = was_debug

check('six rows delete in one request', json.loads(r.content)['deleted'] == 6,
      r.content.decode()[:90])
check('they are gone', not Student.objects.filter(id__in=herd_ids).exists())
check('their login accounts are gone',
      not U.objects.filter(id__in=herd_uids).exists())
# A per-row loop was several queries each; the point of the bulk path is
# that the query count stops tracking the row count.
check('it does not run a transaction per row', queries < 6 * 8,
      f'{queries} queries for 6 rows')

# -- the fallback names the row that would not go -----------------------
# When the bulk statement fails the whole batch rolls back, so the view
# retries one at a time. That is the only path that can say which row broke.
print(chr(10) + 'THE FALLBACK STILL NAMES THE ROW')
survivors = [make_student(f'fb{i}') for i in range(3)]
survivor_ids = [s.id for s in survivors]
survivor_uids = [s.user_id for s in survivors]

real_purge = bd.purge_people


def _explode(qs):
    raise RuntimeError('bulk path deliberately broken by the test')


bd.purge_people = _explode
try:
    r = admin.post('/bulk-delete/students/', json.dumps({'ids': survivor_ids}),
                   content_type='application/json')
finally:
    bd.purge_people = real_purge

out = json.loads(r.content)
check('a broken bulk path falls back instead of failing the request',
      r.status_code == 200, f'HTTP {r.status_code}')
check('and still deletes every row one at a time', out['deleted'] == 3, str(out))
check('nothing survives the fallback',
      not Student.objects.filter(id__in=survivor_ids).exists())
check('and no login account does either',
      not U.objects.filter(id__in=survivor_uids).exists())
check('the bulk path was put back', bd.purge_people is real_purge)

# -- the script can select past the page it is on -----------------------
print(chr(10) + 'SELECT ALL, NOT JUST THIS PAGE')
js = open(os.path.join(settings.BASE_DIR, 'static/js/common/bulk-delete.js'),
          encoding='utf-8').read()
check('it reads every row from DataTables, not just the DOM',
      "rows({ search: 'applied' })" in js)
check("a search narrows what 'select all' means",
      "search: 'applied'" in js and 'allIds' in js)
check('there is a select-all-rows control', 'bd-all-pages' in js)
check('the header checkbox still ticks only the page',
      "table.querySelectorAll('.bd-row')" in js)
check('ids are sent as JSON, not as one field each',
      "'Content-Type': 'application/json'" in js and 'JSON.stringify' in js)
check('the delete is batched so no request nears the worker timeout',
      'var BATCH' in js and 'batches' in js)
check('progress is counted, not animated',
      'bd-progress' in js and 'setInterval' not in js)

css = open(os.path.join(settings.BASE_DIR, 'static/css/common/bulk-delete.css'),
           encoding='utf-8').read()
for cls in ('bd-all-pages', 'bd-progress'):
    check(f'.{cls} is styled', f'.{cls}' in css)

_cleanup()

print('\n' + '=' * 62)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
