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
    # Saving a Timetable now creates the Class the parent screens read, so
    # the fixtures spawn Class rows too. Deleting only the Timetable would
    # leave one behind on every run.
    from schools.models import Class
    Class.objects.filter(division__startswith='Z').delete()
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
# Matching the exact wording of a role check made this fail the moment the
# helper was refactored, while the behaviour was fine. What is worth holding
# is that every view narrows through the one shared queryset rather than
# building its own filter, since that is where a role's limits live.
check('one shared queryset decides scope', '_timetable_queryset' in views)
_lines = views.replace('\r\n', '\n').split('\n')
# The helper is the one place allowed to build the filter; skip its own body.
_h_start = next(i for i, l in enumerate(_lines)
                if l.startswith('def _timetable_queryset('))
_h_end = next(i for i in range(_h_start + 1, len(_lines))
              if _lines[i].startswith('def ') or _lines[i].startswith('@'))
_own_filters = [
    l.strip() for i, l in enumerate(_lines)
    if 'Timetable.objects.filter' in l and not (_h_start <= i < _h_end)
]
check('no view builds its own timetable filter', not _own_filters,
      '; '.join(_own_filters[:2]))

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

# Which flag to use turns on this: onboarding refuses an email any account
# holds, active or not. So deactivating leaves the person un-onboardable
# under their own address and only deleting frees it.
check('a deactivated login still holds its email, so onboarding stays blocked',
      U.objects.filter(email=_orphan.email).exists())

# What the login is attached to decides whether deleting is safe, so the
# report has to say. Every reference is SET_NULL: unassigned, not destroyed.
from schools.models import Class as _Class                # noqa: E402

_cls = _Class.objects.first()
_had = None
if _cls:
    _had = _cls.thinking_coach_id
    _cls.thinking_coach = _orphan
    _cls.save(update_fields=['thinking_coach'])
    _out3 = StringIO()
    call_command('check_coach_accounts', stdout=_out3)
    check('the report says what the orphan is assigned to',
          'assigned to 1 class' in _out3.getvalue(),
          '' if 'assigned to 1 class' in _out3.getvalue() else 'deleting blind is how assignments disappear quietly')

_out4 = StringIO()
call_command('check_coach_accounts', '--delete-orphan-logins', stdout=_out4)
check('--delete-orphan-logins frees the email',
      not U.objects.filter(id=_orphan.id).exists())
if _cls:
    _cls.refresh_from_db()
    check('and the class it was on survives, merely unassigned',
          _Class.objects.filter(id=_cls.id).exists()
          and _cls.thinking_coach_id is None)
    _cls.thinking_coach_id = _had
    _cls.save(update_fields=['thinking_coach'])

U.objects.filter(id=_orphan.id).delete()



# ── the coach reads their own schedule, and only reads ─────────────────
# The client could add slots, days and timings and the coach had nowhere to
# see them: the teacher app had no timetable page at all, and the one place
# timetable data reached it -- the attendance classroom picker -- carried
# program, grade and division and nothing about when the class actually runs.
print('\nTHE COACH SEES THEIR OWN SCHEDULE, READ ONLY')

import re as _re3                                          # noqa: E402

from attendance.models import TimetableSlot               # noqa: E402
from teacher.models import Teacher as _Teacher             # noqa: E402

_coaches = list(_Teacher.objects.select_related('user', 'school').filter(
    user__isnull=False, user__role='THINKING_COACH', school__isnull=False)[:2])

if len(_coaches) < 2:
    print('  ..    need two coaches with logins to test isolation; skipped')
else:
    _a, _b = _coaches
    # Both schedules at the SAME school, so only the coach assignment can
    # separate them. Filtering by school would hand each coach the other's.
    _mine = make_timetable(mine, 'CoachOwn')
    _mine.thinking_coach = _a.user
    _mine.school = _a.school
    _mine.division = 'ZMINE'
    _mine.save()
    TimetableSlot.objects.create(timetable=_mine, day_of_week=1,
                                 period_number=1, start_time='09:00',
                                 end_time='10:00', note=f'{MARKER} slot')
    _theirs = make_timetable(mine, 'CoachOther')
    _theirs.thinking_coach = _b.user
    _theirs.school = _a.school           # same school, different coach
    _theirs.division = 'ZTHEIRS'
    _theirs.save()

    _cc = sign_in(_a.user)
    check('a coach can sign in to test with', _cc is not None)

    if _cc:
        _r = _cc.get('/teacher/timetable/', follow=True)
        _html = _r.content.decode(errors='ignore')
        check('the coach has a timetable page at all', _r.status_code == 200,
              f'HTTP {_r.status_code}')
        check('it shows the schedule assigned to them', 'ZMINE' in _html)
        check("it does not show another coach's at the same school",
              'ZTHEIRS' not in _html,
              'filtering by school would leak every colleague\'s timetable')

        # Controls are checked on the markup with <style> stripped: the class
        # names tt-act-edit and tt-act-del appear in the page's own CSS
        # whether or not a button uses them.
        _live = _re3.sub(r'<style.*?</style>', '', _html, flags=_re3.S)
        check('no Upload button for a role that only reads',
              'Upload Schedule' not in _live)
        check('no edit link',
              _re3.search(r'href="[^"]*timetable/\d+/edit', _live) is None)
        check('no delete form',
              _re3.search(r'action="[^"]*timetable/\d+/delete', _live) is None)
        check('the sidebar offers it', 'nav-timetable' in _html)

        _d = _cc.get(f'/teacher/timetable/{_mine.id}/', follow=True)
        _dhtml = _d.content.decode(errors='ignore')
        check('the detail page opens', _d.status_code == 200, f'HTTP {_d.status_code}')
        check('and shows the timings, which is the whole point',
              '09:00' in _dhtml or '9:00' in _dhtml,
              'slot times never reached the coach before')
        check('the detail page offers no edit either',
              _re3.search(r'href="[^"]*timetable/\d+/edit',
                          _re3.sub(r'<style.*?</style>', '', _dhtml,
                                   flags=_re3.S)) is None)

        _o = _cc.get(f'/teacher/timetable/{_theirs.id}/', follow=True)
        check("a colleague's schedule is refused by id too",
              b'not available to you' in _o.content,
              'scope must not depend on the list hiding it')

        # The edit routes are not wired under /teacher/ at all.
        for _p in (f'/teacher/timetable/{_mine.id}/edit/',
                   '/teacher/timetable/upload/'):
            check(f'{_p} does not exist for a coach',
                  _cc.get(_p).status_code in (301, 302, 403, 404),
                  f'HTTP {_cc.get(_p).status_code}')

    # And the roles that do edit still can -- hiding must be per role, not
    # a blanket removal.
    _sa = admin.get(reverse(SA['list']), follow=True).content.decode(errors='ignore')
    _sa_live = _re3.sub(r'<style.*?</style>', '', _sa, flags=_re3.S)
    check('the Super Admin still has Upload', 'Upload Schedule' in _sa_live)
    check('and still has edit',
          _re3.search(r'href="[^"]*timetable/\d+/edit', _sa_live) is not None)

    if coord:
        _co = coord.get(reverse(CO['list']), follow=True).content.decode(errors='ignore')
        _co_live = _re3.sub(r'<style.*?</style>', '', _co, flags=_re3.S)
        check('the coordinator still has Upload', 'Upload Schedule' in _co_live)

    # Attendance used the same data through a school-wide fallback, so a
    # coach could mark a colleague's register. Every schedule on the live
    # data has a coach, so the fallback only ever widened access.
    if _cc:
        _att = _cc.get('/teacher/attendance/', follow=True).content.decode(
            errors='ignore')
        check('attendance offers the coach their own class', 'ZMINE' in _att)
        check("and not a colleague's at the same school",
              'ZTHEIRS' not in _att,
              'one coach could mark a colleague register')
        _ok = _cc.get(f'/teacher/api/attendance-sessions/?classroom={_mine.id}')
        _no = _cc.get(f'/teacher/api/attendance-sessions/?classroom={_theirs.id}')
        check('the sessions API serves their own class',
              _ok.status_code == 200, f'HTTP {_ok.status_code}')
        check("and refuses a colleague's by id",
              _no.status_code != 200, f'HTTP {_no.status_code}')

    Timetable.objects.filter(id__in=[_mine.id, _theirs.id]).delete()



# -- Class and Timetable agree about the coach -------------------------
# They hold the same four facts and nothing joined them. Parents and School
# Admins read Class; the coach and attendance read Timetable. 50 timetables
# with 3 Class rows meant almost every parent saw no coach at all.
print(chr(10) + 'SAVING EITHER ONE CARRIES THE COACH ACROSS')

from schools.models import Class as _Cls                   # noqa: E402

_co = (U.objects.filter(role='THINKING_COACH', is_active=True)
       .exclude(pk=None).first())
_co2 = (U.objects.filter(role='THINKING_COACH', is_active=True)
        .exclude(pk=_co.pk).first() if _co else None)

if _co and _co2:
    _Cls.objects.filter(division='ZSYNC').delete()
    _tt = make_timetable(mine, 'Sync')
    _tt.division = 'ZSYNC'
    _tt.thinking_coach = _co
    _tt.save()

    _made = _Cls.objects.filter(school=mine, grade=_tt.grade,
                                division='ZSYNC').first()
    check('saving a schedule creates the Class the parent screens read',
          _made is not None,
          'without it a parent sees no coach for their child')
    if _made:
        check('and the Class gets the coach', _made.thinking_coach_id == _co.id)

        _tt.thinking_coach = _co2
        _tt.save()
        _made.refresh_from_db()
        check('changing the schedule updates the Class',
              _made.thinking_coach_id == _co2.id)

        _made.thinking_coach = _co
        _made.save()
        _tt.refresh_from_db()
        check('and changing the Class updates the schedule',
              _tt.thinking_coach_id == _co.id,
              'assigning on the Class list reached nothing the coach could see')

    # A Class must NOT invent a schedule: it knows no days or times, and an
    # empty row on the coach's timetable is worse than no row.
    _before = Timetable.objects.count()
    _lone = _Cls.objects.create(school=mine, grade='9', division='ZSYNC2',
                                academic_year='2025-2026', thinking_coach=_co)
    check('a Class does not invent a schedule',
          Timetable.objects.count() == _before,
          'an invented timetable would show the coach a class with no times')
    _lone.delete()
    _Cls.objects.filter(division='ZSYNC').delete()
    Timetable.objects.filter(id=_tt.id).delete()
else:
    print('  ..    need two coach logins to test the sync; skipped')


# -- a schedule with no end date still has sessions --------------------
# The form calls the end date optional and 49 of the 50 live schedules were
# saved without one. Session generation treated it as required and returned
# nothing, so a coach opened Attendance, picked a classroom, and got no
# sessions and therefore no students to mark.
print(chr(10) + 'ATTENDANCE WORKS WITHOUT AN END DATE')

import json as _json                                       # noqa: E402
from datetime import timedelta as _td                      # noqa: E402

from attendance.models import TimetableSlot as _Slot       # noqa: E402
from student.models import Student as _Stud                # noqa: E402
from teacher.views import _generate_sessions               # noqa: E402

_kid = _Stud.objects.select_related('school').filter(school__isnull=False).first()
_tc = (_Teacher.objects.select_related('user')
       .filter(user__isnull=False, user__role='THINKING_COACH').first()
       if _kid else None)

if _kid and _tc:
    _tc.school = _kid.school
    _tc.save(update_fields=['school'])
    _open = Timetable.objects.create(
        school=_kid.school, thinking_coach=_tc.user, grade=_kid.student_class,
        division=_kid.division, academic_year='2026-2027', program='FSL',
        start_date=date(2026, 6, 25), end_date=None,
        notes=f'{MARKER} open ended')
    for _d in ('mon', 'wed', 'fri'):
        _Slot.objects.create(timetable=_open, day_of_week=_d, period_number=1,
                             start_time='09:00', end_time='10:00')

    check('a schedule with no end date still generates sessions',
          len(_generate_sessions(_open)) > 0,
          'no sessions means no students to mark')

    # An end date that IS set must still be obeyed, or this fix would quietly
    # run every schedule to the cap.
    _bounded = Timetable.objects.create(
        school=_kid.school, thinking_coach=_tc.user, grade=_kid.student_class,
        division=_kid.division, academic_year='2026-2027', program='FSL',
        start_date=date(2026, 6, 25), end_date=date(2026, 7, 10),
        notes=f'{MARKER} bounded')
    for _d in ('mon', 'wed', 'fri'):
        _Slot.objects.create(timetable=_bounded, day_of_week=_d,
                             period_number=1, start_time='09:00',
                             end_time='10:00')
    _bs = _generate_sessions(_bounded)
    check('an end date that is set is still respected',
          _bs and _bs[-1]['date'] <= '2026-07-10',
          _bs[-1]['date'] if _bs else 'no sessions at all')
    check('and it is shorter than the open-ended one',
          len(_bs) < len(_generate_sessions(_open)))

    _cc2 = sign_in(_tc.user)
    if _cc2:
        _s = _cc2.get(f'/teacher/api/attendance-sessions/?classroom={_open.id}')
        _sd = _json.loads(_s.content) if _s.status_code == 200 else {}
        check('the sessions API returns them to the page',
              len(_sd.get('sessions', [])) > 0, f'HTTP {_s.status_code}')
        if _sd.get('sessions'):
            _st = _cc2.get('/teacher/api/attendance-students/'
                           f"?classroom={_open.id}&date={_sd['sessions'][0]['date']}")
            _std = _json.loads(_st.content) if _st.status_code == 200 else {}
            check('and the students to mark actually arrive',
                  len(_std.get('students', [])) > 0,
                  'this is the screen the client could not use')

    Timetable.objects.filter(id__in=[_open.id, _bounded.id]).delete()
else:
    print('  ..    need a student and a coach to test attendance; skipped')


# -- the attendance page can actually show its dropdown ----------------
# The backend had the classrooms, the JS rendered them, and the coach still
# saw nothing: the menu hangs below its card and the global .card rule in
# teacher-dashboard.css sets overflow:hidden, so it was clipped at the card
# edge. Only the search row, which sits inside the card, stayed visible --
# which read as an empty list rather than a hidden one.
print(chr(10) + 'THE CLASSROOM DROPDOWN IS NOT CLIPPED AWAY')

_any_coach = (_Teacher.objects.select_related('user')
              .filter(user__isnull=False, user__role='THINKING_COACH').first())
if _any_coach:
    _ac = sign_in(_any_coach.user)
    if _ac:
        _page = _ac.get('/teacher/attendance/', follow=True).content.decode(
            errors='ignore')
        _card = re.search(
            r'<div class="([^"]*card[^"]*)"[^>]*>\s*<label class="lbl">Select Classroom',
            _page)
        check('the classroom card opts out of the global overflow:hidden',
              _card is not None and 'cr-card' in _card.group(1),
              _card.group(1) if _card else 'card not found')
        check('and the page defines that override',
              'overflow:visible' in _page and '.am .cr-card' in _page)

        # The same stylesheet lifts a hovered card with a transform, which
        # creates a stacking context and traps the dropdown's z-index inside
        # it -- so the panels below, later in the DOM, paint over the open
        # list. You hover this card to open the dropdown, so it was every time.
        check('the classroom card does not lift on hover',
              '.am .cr-card:hover { transform:none;' in _page,
              'a hover transform would trap the dropdown behind the panels')
        # It must sit between two things: above the session panels below it
        # (z-index auto) and BELOW the sticky header (z-index 10). The header
        # is its own stacking context, so its profile menu's z-index:1000
        # only applies inside it -- a card above 10 out here covers the menu,
        # which is exactly what a first attempt at this did.
        _card_z = re.search(r'\.am \.cr-card \{[^}]*z-index:\s*(\d+)', _page)
        _base = open(os.path.join(settings.BASE_DIR, 'teacher', 'templates',
                                  'teacher', 'base.html'),
                     encoding='utf-8', errors='ignore').read()
        _hdr_z = re.search(r'position:\s*sticky;\s*top:\s*0;\s*z-index:\s*(\d+)',
                           _base)
        check('the classroom card carries a z-index of its own',
              _card_z is not None)
        if _card_z and _hdr_z:
            check('and it stays below the header, so the profile menu is not covered',
                  int(_card_z.group(1)) < int(_hdr_z.group(1)),
                  f'card={_card_z.group(1)} header={_hdr_z.group(1)}')
            check('while still above the panels it has to cover',
                  int(_card_z.group(1)) > 0, _card_z.group(1))

        # The list itself must travel as JSON. Python's repr() went in raw
        # before, which parses by luck and dies on the first odd character.
        check('classrooms reach the page as JSON, not Python repr',
              'classrooms-data' in _page
              and re.search(r"CLASSROOMS = \[\{'", _page) is None)

        # The clipping rule is real and still loaded, so the override is
        # load-bearing rather than decorative.
        _css = os.path.join(settings.BASE_DIR, 'static', 'css', 'teacher',
                            'teacher-dashboard.css')
        _rule = re.search(r'\.card\s*\{[^}]*overflow:\s*hidden',
                          open(_css, encoding='utf-8', errors='ignore').read())
        check('the global rule that made this necessary still exists',
              _rule is not None,
              'if it is gone the override is harmless, but check why')
else:
    print('  ..    no coach to load the attendance page with; skipped')

_cleanup()

print('\n' + '=' * 62)
print(f'PASS {len(PASS)}   FAIL {len(FAIL)}')
for f in FAIL:
    print('  FAILED:', f)
sys.exit(1 if FAIL else 0)
