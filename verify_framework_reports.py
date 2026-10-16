"""Which reports each framework shows, and who can change that.

The client, on 2026-10-16:

    CSL+              "Keep the reporting structure the same as FSL. Hide the
                      Kaushal Bodh report for now. Please do not delete it, as
                      we may need it in the future. Change the title Annual
                      Skill Passport to Annual Skill Report."
    CSL Foundation    "Remove the Annual Skill Passport. The reports should
                      include only: Project Report, Kaushal Bodh Annual
                      Report."

Three things are checked, in that order of importance:

1. A student and a parent are offered exactly the reports their framework
   says, under the right name -- read off the rendered sidebar, not the flag.
2. A report that is switched off cannot be reached by its URL either. Hiding a
   link does nothing about a bookmark or a link mailed last term.
3. Nothing is deleted when a report is hidden. "Do not delete it" is the part
   that cannot be undone if it is got wrong.

And the Super Admin can set all of it from Manage Frameworks, so none of this
needs a deploy next time.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_framework_reports.py
"""

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

from competencies.engine import build_kb_report, get_annual_kb_scores
from competencies.models import Framework
from parent.models import Parent
from student.models import Student
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'
MANAGE_URL = '/super-admin/skill-passport/manage-frameworks/'

PASS, FAIL = [], []


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


def text_of(html):
    html = re.sub(r'<(script|style)\b.*?</\1>', ' ', html, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def sidebar_reports(body, title):
    """Which report links the page offers, by the words a reader would see."""
    names = ['Project Report', title, 'Kaushal Bodh Report']
    return [n for n in names if n in body]


# ------------------------------------------------- what the client asked for

WANTED = {
    'FSL': {
        'annual': True, 'title': 'Annual Skill Passport', 'kb': False,
    },
    'CSL+': {
        'annual': True, 'title': 'Annual Skill Report', 'kb': False,
    },
    'CSL Foundation': {
        'annual': False, 'title': None, 'kb': True,
    },
}


def framework(name):
    return (Framework.objects.filter(name__iexact=name).first()
            or Framework.objects.filter(
                name__iexact=name.replace('+', ' +')).first())


def check_settings():
    print('\n1. the frameworks are set the way the message reads')

    for name, want in WANTED.items():
        fw = framework(name)
        if fw is None:
            check(f'{name} exists', False)
            continue
        check(f'{name}: annual report {"on" if want["annual"] else "off"}',
              fw.show_annual_report == want['annual'], fw.show_annual_report)
        check(f'{name}: Kaushal Bodh {"on" if want["kb"] else "off"}',
              fw.has_kaushal_bodh == want['kb'], fw.has_kaushal_bodh)
        if want['title']:
            check(f'{name}: the report is called "{want["title"]}"',
                  fw.annual_report_title == want['title'],
                  fw.annual_report_title)

    # The two settings used to be one. CSL+ wants the annual report without
    # career matching, which a single flag cannot say.
    csl = framework('CSL+')
    if csl:
        check('CSL+ keeps its annual report without career matching',
              csl.show_annual_report and not csl.has_profiling,
              f'annual={csl.show_annual_report} profiling={csl.has_profiling}')


# ------------------------------------------------------- what a family sees

def a_student_of(framework_name):
    fw = framework(framework_name)
    if fw is None:
        return None
    return (Student.objects.filter(school__framework_ref=fw,
                                   user__isnull=False, is_active=True)
            .first())


def check_family_sees(framework_name):
    fw = framework(framework_name)
    student = a_student_of(framework_name)
    if student is None:
        check(f'{framework_name}: a student to read it as', False)
        return

    want = WANTED[framework_name]
    title = fw.annual_report_title
    expected = ['Project Report']
    if want['annual']:
        expected.append(title)
    if want['kb']:
        expected.append('Kaushal Bodh Report')

    client = sign_in(student.user)
    body = text_of(client.get('/student/dashboard/', follow=True)
                   .content.decode('utf-8', 'replace'))
    offered = sidebar_reports(body, title)
    check(f'{framework_name}: the student is offered {expected}',
          offered == expected, offered)

    # The old name must be gone where it was renamed, or both are on the page
    # and the rename did nothing.
    if want['annual'] and title != 'Annual Skill Passport':
        check(f'{framework_name}: the old name is not still there too',
              'Annual Skill Passport' not in body)

    # A link that is not shown must not be reachable either.
    page = client.get('/student/reports/annual/', follow=True)
    landed = page.redirect_chain[-1][0] if page.redirect_chain else ''
    if want['annual']:
        check(f'{framework_name}: the annual report opens', not landed, landed)
    else:
        check(f'{framework_name}: the annual report URL is refused too',
              'dashboard' in landed, landed or 'it opened')

    page = client.get('/student/reports/kaushal-bodh/', follow=True)
    landed = page.redirect_chain[-1][0] if page.redirect_chain else ''
    if want['kb']:
        check(f'{framework_name}: the KB report opens', not landed, landed)
    else:
        check(f'{framework_name}: the KB report URL is refused too',
              'dashboard' in landed, landed or 'it opened')

    # The parent is shown the same set. They share the templates; they do not
    # share the context, which is where this last went wrong.
    parent = Parent.objects.filter(students=student,
                                   user__isnull=False).first()
    if parent is None:
        return
    body = text_of(sign_in(parent.user).get('/parent/dashboard/', follow=True)
                   .content.decode('utf-8', 'replace'))
    offered = sidebar_reports(body, title)
    check(f'{framework_name}: the parent is offered the same',
          offered == expected, offered)


# --------------------------------------------------- nothing was thrown away

def check_nothing_deleted():
    print('\n3. hiding a report deletes nothing')

    for name in ('CSL+', 'FSL'):
        fw = framework(name)
        if fw is None:
            continue
        from competencies.models import Competency, Pillar

        kb_pillars = Pillar.objects.filter(framework_ref=fw, is_kb=True)
        comps = Competency.objects.filter(
            sub_pillar__pillar__in=kb_pillars).count()
        check(f'{name}: its Kaushal Bodh pillar is still there',
              kb_pillars.exists(), kb_pillars.count())
        check(f'{name}: and its KB competencies are still there', comps > 0,
              comps)

    # The report builds the moment the switch goes back on.
    student = a_student_of('CSL+')
    if student:
        fw = framework('CSL+')
        fw.has_kaushal_bodh = True
        fw.save(update_fields=['has_kaushal_bodh'])
        page = sign_in(student.user).get('/student/reports/kaushal-bodh/',
                                         follow=True)
        check('CSL+: switching Kaushal Bodh back on returns the report',
              not page.redirect_chain, page.redirect_chain)
        fw.has_kaushal_bodh = False
        fw.save(update_fields=['has_kaushal_bodh'])

    # CSL Foundation is the one place KB is really used; its scores must be
    # readable still.
    kid = a_student_of('CSL Foundation')
    if kid:
        rows = get_annual_kb_scores(kid)
        check('CSL Foundation: the KB scores are still readable', bool(rows),
              len(rows))
        report = build_kb_report(kid)
        check('and the annual KB report still builds',
              report is not None and report.get('groups'),
              (report or {}).get('count'))


# -------------------------------------------- the Super Admin can set it all

def check_manage_page():
    print('\n4. the Super Admin can change all of it without a deploy')

    boss = U.objects.filter(role='SUPER_ADMIN', is_active=True).first()
    if boss is None:
        check('a Super Admin to sign in as', False)
        return
    client = sign_in(boss)

    page = client.get(MANAGE_URL, follow=True)
    body = page.content.decode('utf-8', 'replace')
    check('the page opens', page.status_code == 200, page.status_code)
    for field in ('show_annual_report', 'annual_report_title',
                  'has_kaushal_bodh', 'has_profiling'):
        check(f'it offers {field}', f'name="{field}"' in body)
    check('and it says Project Report is always on',
          'always on' in body)

    fw = framework('CSL Foundation')
    if fw is None:
        return

    # Turn the annual report on, with a name, and read it back.
    client.post(MANAGE_URL, {
        'action': 'edit', 'fw_id': fw.id, 'name': fw.name,
        'prefix': fw.prefix, 'show_annual_report': 'on',
        'annual_report_title': 'Zz Annual Trial',
        'has_kaushal_bodh': 'on',
    }, follow=True)
    fw.refresh_from_db()
    check('a change made on the page is saved',
          fw.show_annual_report and fw.annual_report_title == 'Zz Annual Trial',
          f'{fw.show_annual_report} {fw.annual_report_title!r}')

    kid = a_student_of('CSL Foundation')
    if kid:
        body = text_of(sign_in(kid.user).get('/student/dashboard/',
                                             follow=True)
                       .content.decode('utf-8', 'replace'))
        check('and the student sees it under the new name straight away',
              'Zz Annual Trial' in body)

    # And off again, which is where the client left it.
    client = sign_in(boss)
    client.post(MANAGE_URL, {
        'action': 'edit', 'fw_id': fw.id, 'name': fw.name,
        'prefix': fw.prefix, 'has_kaushal_bodh': 'on',
    }, follow=True)
    fw.refresh_from_db()
    check('and turning it off again sticks', not fw.show_annual_report)

    # FSL is a fixed framework: its pillars are protected, its reports are not.
    fsl = framework('FSL')
    if fsl and fsl.is_fixed:
        before_name, before_prefix = fsl.name, fsl.prefix
        client.post(MANAGE_URL, {
            'action': 'edit', 'fw_id': fsl.id, 'name': 'Zz Renamed',
            'prefix': 'ZZX', 'show_annual_report': 'on',
            'annual_report_title': 'Zz Fixed Trial',
        }, follow=True)
        fsl.refresh_from_db()
        check('a fixed framework can still have its reports renamed',
              fsl.annual_report_title == 'Zz Fixed Trial',
              fsl.annual_report_title)
        check('but its name is left alone', fsl.name == before_name, fsl.name)
        check('and its prefix too', fsl.prefix == before_prefix, fsl.prefix)


def run():
    print('=' * 60)
    print('WHICH REPORTS EACH FRAMEWORK SHOWS')
    print('=' * 60)

    try:
        with transaction.atomic():
            check_settings()

            print('\n2. what a student and a parent are actually offered')
            for name in WANTED:
                check_family_sees(name)

            check_nothing_deleted()
            check_manage_page()
            raise Rollback
    except Rollback:
        pass

    # The rollback has to have put the client's settings back.
    fw = framework('CSL Foundation')
    check('nothing this suite changed survived',
          fw is not None and not fw.show_annual_report
          and fw.annual_report_title != 'Zz Annual Trial',
          getattr(fw, 'annual_report_title', None))

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    run()
