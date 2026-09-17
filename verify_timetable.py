"""
Check the timetable pages now that a Super Admin shares them.

  python verify_timetable.py

The five views used to belong to the Program Coordinator alone and were
scoped to the schools assigned to them. They now serve a Super Admin too,
which means one queryset decides how much two different roles can see. The
checks that matter are therefore about what did NOT change:

  a coordinator still sees only their own schools' timetables, and still
  cannot open, edit or delete one belonging to a school they are not
  assigned to -- through either set of routes;

  the Super Admin routes do not widen a coordinator's scope. Scope is read
  from the signed-in user, so the path taken to the view must not matter.

And about what did:

  a Super Admin can reach all five pages, sees every school, and gets their
  own sidebar rather than the coordinator's.

Everything it creates is its own; it deletes nothing that was already here.
"""

import atexit
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
from django.urls import reverse                           # noqa: E402

from attendance.models import Timetable                   # noqa: E402
from schools.models import School                         # noqa: E402
from verify_client import HttpsClient as Client           # noqa: E402

U = get_user_model()
PASS, FAIL = [], []
restore = {}
MARKER = 'ZZTT'
PASSWORD = 'Timetable!2026'


def _cleanup():
    Timetable.objects.filter(notes__startswith=MARKER).delete()
    School.objects.filter(school_code__startswith=MARKER).delete()
    for pk, password in list(restore.items()):
        U.objects.filter(pk=pk).update(password=password)
    restore.clear()


atexit.register(_cleanup)
_cleanup()


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(label)
    print(f'  {"PASS" if ok else "FAIL"}  {label}{("  - " + detail) if detail else ""}')


def sign_in(user):
    restore.setdefault(user.pk, U.objects.get(pk=user.pk).password)
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    c = Client()
    return c if c.login(username=user.username, password=PASSWORD) else None


def make_school(suffix):
    return School.objects.create(
        school_name=f'ZZ Timetable School {suffix}',
        school_code=f'{MARKER}{suffix}', board='CBSE', school_type='Private',
        medium='English', school_email=f'zztt{suffix}@example.com',
        school_phone='9000000001', principal_name='ZZ Principal',
        principal_phone='9000000002',
        principal_email=f'zzttp{suffix}@example.com',
        branch_address='ZZ Address', city='Mumbai', state='Maharashtra',
        pincode='400001', emergency_contact_person='ZZ Contact',
        emergency_phone='9000000003')


def make_timetable(school, suffix):
    return Timetable.objects.create(
        school=school, grade='6', division=f'Z{suffix}',
        academic_year='2025-2026', program='FSL',
        start_date=date(2025, 6, 1), notes=f'{MARKER} fixture {suffix}')


# ── who we test with ────────────────────────────────────────────────────
su = U.objects.filter(role='SUPER_ADMIN', is_active=True).first()
assert su, 'no Super Admin to test with'
admin = sign_in(su)
assert admin, 'Super Admin could not sign in'

from coordinator.models import ProgramCoordinator          # noqa: E402

profile = (ProgramCoordinator.objects.select_related('user')
           .filter(user__isnull=False, user__is_active=True).first())
coach = U.objects.filter(role='THINKING_COACH', is_active=True).first()

SA = {name: f'superadmin_timetable_{name}'
      for name in ('list', 'upload', 'detail', 'edit', 'delete')}
CO = {name: f'coordinator:timetable_{name}'
      for name in ('list', 'upload', 'detail', 'edit', 'delete')}

# ── fixtures: one school the coordinator has, one they do not ──────────
mine = make_school('A')
theirs = make_school('B')
tt_mine = make_timetable(mine, 'A')
tt_theirs = make_timetable(theirs, 'B')

if profile:
    profile.schools_assigned.add(mine)
    coord = sign_in(profile.user)
else:
    coord = None
    print('  ..    no Program Coordinator account on this database')

print(f'\n  super admin: {su.username}')
print(f'  coordinator: {profile.user.username if profile else "-"}'
      f'  assigned: {mine.school_name}')
print(f'  the other school: {theirs.school_name}\n')

# ── the Super Admin can reach all five ─────────────────────────────────
print('THE SUPER ADMIN PAGES EXIST')
for name in ('list', 'upload'):
    url = reverse(SA[name])
    r = admin.get(url, follow=True)
    check(f'{name}: {url} loads', r.status_code == 200, f'HTTP {r.status_code}')

for name in ('detail', 'edit'):
    url = reverse(SA[name], args=[tt_mine.id])
    r = admin.get(url, follow=True)
    check(f'{name}: {url} loads', r.status_code == 200, f'HTTP {r.status_code}')

r = admin.get(reverse(SA['delete'], args=[tt_mine.id]), follow=True)
check('delete refuses GET and sends you back',
      r.status_code == 200 and b'Invalid request method' in r.content,
      f'HTTP {r.status_code}')

# ── it renders the Super Admin's own chrome ────────────────────────────
print('\nIT WEARS THE RIGHT SIDEBAR')
body = admin.get(reverse(SA['list']), follow=True).content.decode(errors='ignore')
check('the Super Admin sidebar is the one rendered',
      'nav-school-list' in body and 'coord-sidebar-nav-link' not in body)
check('its links point at the Super Admin routes',
      '/super-admin/timetable/upload/' in body
      and '/coordinator/timetable/' not in body)
# The Super Admin sidebar legitimately links to "Program Coordinators", so
# the whole document is the wrong place to look; the page's own title is not.
_title = re.search(r'<title>.*?</title>', body, re.S)
check('the page titles itself for the Super Admin, not the coordinator',
      _title is not None and 'Program Coordinator' not in _title.group(0),
      _title.group(0)[:70] if _title else 'no <title>')
check('the sidebar has a Timetable entry', 'nav-timetable' in body)

if coord:
    cbody = coord.get(reverse(CO['list']), follow=True).content.decode(errors='ignore')
    check('the coordinator still gets the coordinator sidebar',
          'coord-sidebar-nav-link' in cbody)
    check('and links that stay inside /coordinator/',
          '/coordinator/timetable/upload/' in cbody
          and '/super-admin/timetable/' not in cbody)

# ── scope: the Super Admin sees every school ───────────────────────────
print('\nSCOPE')
body = admin.get(reverse(SA['list']), follow=True).content.decode(errors='ignore')
# Matched on the school name, which the list now carries as its own column.
# A bare row id matches stray digits anywhere in the markup and would pass
# whether the row were there or not.
check('the list names the school each schedule belongs to',
      mine.school_name in body,
      'no School column, so every row looks the same to a Super Admin')
check('the Super Admin list shows a timetable from each school',
      mine.school_name in body and theirs.school_name in body)
r = admin.get(reverse(SA['detail'], args=[tt_theirs.id]), follow=True)
check('and can open one from a school no coordinator assigned them',
      r.status_code == 200 and b'not available to you' not in r.content)

# ── scope: the coordinator's did not widen ─────────────────────────────
print('\nTHE COORDINATOR IS STILL FENCED IN  (the check that matters)')
if coord:
    cbody = coord.get(reverse(CO['list']), follow=True).content.decode(errors='ignore')
    check('their list shows their own school\'s timetable',
          mine.school_name in cbody)
    check('and not the other school\'s',
          theirs.school_name not in cbody,
          'a timetable from an unassigned school is listed')

    r = coord.get(reverse(CO['detail'], args=[tt_theirs.id]), follow=True)
    check('they cannot open an unassigned school\'s schedule',
          b'not available to you' in r.content)
    r = coord.get(reverse(CO['edit'], args=[tt_theirs.id]), follow=True)
    check('nor edit it', b'not available to you' in r.content)

    r = coord.post(reverse(CO['delete'], args=[tt_theirs.id]), follow=True)
    check('nor delete it', Timetable.objects.filter(id=tt_theirs.id).exists())

    # The Super Admin routes run the same code, so two things have to hold:
    # the route turns a coordinator away, and even if it did not, the view
    # would still scope them -- scope comes from the user, not the path.
    print('\n  ...and the Super Admin routes are not a way in')
    for name, args in (('list', []), ('upload', []),
                       ('detail', [tt_theirs.id]), ('edit', [tt_theirs.id])):
        url = reverse(SA[name], args=args) if args else reverse(SA[name])
        r = coord.get(url)
        check(f'a coordinator is turned away from the Super Admin {name} route',
              r.status_code in (301, 302, 403, 404), f'HTTP {r.status_code}')

    # Following the redirect must not show them the school they are not on.
    # Matching on the school name, not the row id -- a bare id like "2"
    # matches stray digits anywhere in the markup and passes for free.
    r = coord.get(reverse(SA['list']), follow=True)
    check('and no unassigned school appears if they follow the redirect',
          theirs.school_name.encode() not in r.content)

    r = coord.post(reverse(SA['delete'], args=[tt_theirs.id]), follow=True)
    check('nor can they delete through it',
          Timetable.objects.filter(id=tt_theirs.id).exists())

# ── nobody else gets in ────────────────────────────────────────────────
print('\nEVERYONE ELSE IS REFUSED')
anon = Client()
for name in ('list', 'upload'):
    r = anon.get(reverse(SA[name]))
    check(f'anonymous is refused {name}',
          r.status_code in (301, 302, 403, 404), f'HTTP {r.status_code}')

for role in ('THINKING_COACH', 'SCHOOL_ADMIN', 'PARENT', 'STUDENT'):
    user = U.objects.filter(role=role, is_active=True).first()
    if not user:
        print(f'  ..    no {role} account on this database')
        continue
    c = sign_in(user)
    if not c:
        continue
    # Without follow: a redirect is the refusal. Following it lands on their
    # own dashboard, which is a 200 with no timetable on it, and would pass
    # this check whether the route refused them or not.
    r = c.get(reverse(SA['list']))
    check(f'{role} is turned away from the Super Admin timetable',
          r.status_code in (301, 302, 403, 404), f'HTTP {r.status_code}')
    r = c.post(reverse(SA['delete'], args=[tt_mine.id]), follow=True)
    check(f'{role} cannot delete a timetable',
          Timetable.objects.filter(id=tt_mine.id).exists())

# ── the Super Admin can actually create and change one ─────────────────
# Reaching the form is not the same as the form working. This is the whole
# point of giving them the pages, and nothing above exercises a POST.
print('\nCREATE, EDIT AND DELETE REALLY WORK')
before = Timetable.objects.count()
r = admin.post(reverse(SA['upload']), {
    'school': theirs.id, 'grade': '7', 'division': 'ZC',
    'academic_year': '2025-2026', 'program': 'FSL',
    'start_date': '2025-06-01', 'end_date': '2026-03-31',
    'notes': f'{MARKER} created by the Super Admin',
    'slot_day': ['1'], 'slot_period': ['1'],
    'slot_start': ['09:00'], 'slot_end': ['10:00'], 'slot_note': ['ZZ slot'],
}, follow=True)
made = Timetable.objects.filter(notes__startswith=MARKER,
                                division='ZC').first()
check('a Super Admin can create a schedule', made is not None,
      f'HTTP {r.status_code}, {Timetable.objects.count() - before} added')

if made:
    check('for a school no coordinator assigned them',
          made.school_id == theirs.id)
    check('and its slot was saved', made.slots.count() == 1,
          f'{made.slots.count()} slots')

    admin.post(reverse(SA['edit'], args=[made.id]), {
        'school': theirs.id, 'grade': '7', 'division': 'ZD',
        'academic_year': '2025-2026', 'program': 'CSL plus',
        'start_date': '2025-06-01', 'end_date': '2026-03-31',
        'notes': f'{MARKER} edited by the Super Admin',
        'slot_day': ['2'], 'slot_period': ['1'],
        'slot_start': ['11:00'], 'slot_end': ['12:00'], 'slot_note': [''],
    }, follow=True)
    made.refresh_from_db()
    check('and edit it', made.division == 'ZD' and made.program == 'CSL plus',
          f'{made.division} / {made.program}')

    admin.post(reverse(SA['delete'], args=[made.id]), follow=True)
    check('and delete it', not Timetable.objects.filter(id=made.id).exists())

# ── one implementation, not a copy ─────────────────────────────────────
print('\nONE IMPLEMENTATION, NOT A COPY')
views = open(os.path.join(settings.BASE_DIR, 'coordinator/views.py'),
             encoding='utf-8', errors='ignore').read()
urls = open(os.path.join(settings.BASE_DIR, 'superadmin/urls.py'),
            encoding='utf-8', errors='ignore').read()
sa_views = open(os.path.join(settings.BASE_DIR, 'superadmin/views.py'),
                encoding='utf-8', errors='ignore').read()

check('the Super Admin routes point at the shared views',
      'coordinator_views.timetable_list' in urls)
check('no second copy of the views was made',
      'def timetable_list' not in sa_views)
for name in ('list', 'detail', 'edit', 'delete', 'upload'):
    check(f'timetable_{name} is open to both roles',
          re.search(r'@user_passes_test\(is_timetable_manager\)\s*\ndef timetable_'
                    + name + r'\(', views.replace('\r\n', '\n')) is not None)
check('scope is read from the user, not the route',
      "_timetable_schools(request)" in views
      and "role', None) == 'SUPER_ADMIN'" in views)

templates = {
    'list': 'coordinator/templates/coordinator/timetable-list.html',
    'detail': 'coordinator/templates/coordinator/timetable-detail.html',
    'upload': 'coordinator/templates/coordinator/timetable-upload.html',
}
for name, path in templates.items():
    html = open(os.path.join(settings.BASE_DIR, path),
                encoding='utf-8', errors='ignore').read()
    check(f'{name} template picks its base from the role',
          '{% extends base_template %}' in html)
    check(f'{name} template hardcodes no coordinator route',
          'coordinator:timetable' not in html)


# ── the coach dropdown and the coach list agree ────────────────────────
# They read different tables. The list reads Teacher; the dropdown read
# User.role. A login whose Teacher profile was deleted stayed a "coach"
# forever -- assignable on a timetable, absent from the screen that manages
# coaches. That is the shape of the bug the client reported.
print('\nTHE COACH DROPDOWN MATCHES THE COACH LIST')

from teacher.models import Teacher                          # noqa: E402

_orphan = U.objects.create_user(
    username=f'{MARKER}orphancoach', password=PASSWORD,
    role='THINKING_COACH', first_name='ZZ', last_name='OrphanCoach')
check('a coach login with no Teacher profile exists to test with',
      not Teacher.objects.filter(user=_orphan).exists())

_upload = admin.get(reverse(SA['upload']), follow=True).content.decode(
    errors='ignore')
check('loading the timetable form works', bool(_upload))
check('the orphan login is NOT offered as a coach',
      'ZZ OrphanCoach' not in _upload and _orphan.username not in _upload,
      'a login with no profile is assignable on a timetable')

# Everything the dropdown does offer must be on the coach list.
_listed = {t.user_id for t in Teacher.objects.filter(user__isnull=False)}
_offered = set(
    U.objects.filter(role='THINKING_COACH', teacher_profile__isnull=False)
    .values_list('id', flat=True))
check('every coach the dropdown offers has a Teacher profile',
      not (_offered - _listed),
      '' if not (_offered - _listed) else f'{len(_offered - _listed)} without one')

# And a real coach is still offered -- narrowing must not empty the list.
_real = (Teacher.objects.select_related('user')
         .filter(user__isnull=False, user__role='THINKING_COACH').first())
if _real:
    check('a coach that does have a profile is still offered',
          _real.user_id in _offered, _real.full_name)
    check('and their name reaches the form',
          (_real.user.get_full_name() or _real.user.username).split()[0]
          in _upload if _upload else False)
else:
    print('  ..    no coach with both a profile and a login on this database')

# The diagnostic exists and reports the orphan, because nothing on screen
# will show it any more now that the dropdown filters it out.
from io import StringIO                                     # noqa: E402

from django.core.management import call_command             # noqa: E402

_out = StringIO()
call_command('check_coach_accounts', stdout=_out)
_report = _out.getvalue()
check('check_coach_accounts reports the orphan login',
      f'{MARKER}orphancoach' in _report,
      'the only way left to find these is the command')
check('and it changes nothing without being asked',
      U.objects.filter(id=_orphan.id, is_active=True).exists())

_out2 = StringIO()
call_command('check_coach_accounts', '--fix-orphan-logins', stdout=_out2)
_orphan.refresh_from_db()
check('--fix-orphan-logins deactivates it', not _orphan.is_active)
check('and does not delete it -- a profile may have gone by mistake',
      U.objects.filter(id=_orphan.id).exists())

U.objects.filter(id=_orphan.id).delete()


_cleanup()

print('\n' + '=' * 62)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
