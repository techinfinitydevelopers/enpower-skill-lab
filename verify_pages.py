"""
Render every report page through Django and assert the HTML actually contains
the seeded data.

A passing engine test only proves the numbers are right in the database. This
runs the real view + template stack and checks what a browser would receive —
catching context keys that were never passed, template typos and empty states.

It does NOT prove CSS/JS behaviour; that still needs a real browser.

Run with:  python verify_pages.py
"""

import atexit
import os
import re
from html import unescape
import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

# Client() sends Host: testserver, which the project's ALLOWED_HOSTS rejects
# with a 400 before any view runs.
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from django.test import Client
from accounts.models import User
from student.models import Student
from competencies.models import ProjectReport, Project

PASSWORD = 'SeedCheck!2026'
PASS, FAIL = [], []


def check(label, ok, detail=''):
    (PASS if ok else FAIL).append(f'{label}{("  — " + detail) if detail else ""}')
    print(f'  {"PASS" if ok else "FAIL"}  {label}{("  — " + detail) if detail else ""}')


def text_of(html):
    """Strip tags so assertions match visible text, not markup.

    Entities must be unescaped too — a competency called "Numeracy &
    Quantitative Reasoning" reaches the page as "&amp;" and would never match
    the name held in the database.
    """
    html = re.sub(r'<script.*?</script>', ' ', html, flags=re.S | re.I)
    html = re.sub(r'<style.*?</style>', ' ', html, flags=re.S | re.I)
    stripped = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', unescape(stripped))


# Original password hashes, restored once every request is done. Setting a known
# password is the only way to authenticate here, but leaving it set would
# silently break whatever credentials were handed out for manual testing.
# The restore cannot happen per-login: Django keeps an HMAC of the password in
# the session, so changing it mid-run logs the client straight back out.
_ORIGINAL_HASHES = {}


def login_as(user):
    _ORIGINAL_HASHES.setdefault(user.pk, user.password)
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    c = Client()
    ok = c.login(username=user.username, password=PASSWORD)
    if not ok:
        ok = c.login(email=user.email, password=PASSWORD)
    return (c if ok else None)


# Registered with atexit rather than called at the end. A crash part-way
# through used to leave a real account on the audit password -- which is
# exactly what happened when this suite hit a missing `git` binary inside
# the container and died before the restore line. atexit still runs when
# an exception propagates out.
def restore_passwords():
    for pk, pw_hash in _ORIGINAL_HASHES.items():
        User.objects.filter(pk=pk).update(password=pw_hash)
    if _ORIGINAL_HASHES:
        print(f'\n  restored original passwords for {len(_ORIGINAL_HASHES)} user(s)')
        _ORIGINAL_HASHES.clear()


atexit.register(restore_passwords)


# Pages whose visible text still contains template syntax. `{# ... #}` is a
# SINGLE-LINE comment in Django — spread it over two lines and the whole thing
# renders as text on the page. This has slipped through three times, so every
# fetched page is now checked automatically.
LEAKED = []


def fetch(client, url):
    r = client.get(url, follow=True)
    body = text_of(r.content.decode('utf-8', 'replace'))
    for marker in ('{#', '#}', '{% ', '{{ '):
        if marker in body:
            LEAKED.append((url, marker, body[max(0, body.find(marker) - 40):body.find(marker) + 80]))
            break
    return r.status_code, body, r.redirect_chain


def run():
    print('Rendering student pages')

    # An FSL student (career matches expected) and a CSL student (none expected)
    fsl = Student.objects.filter(school__framework_ref__is_fixed=True,
                                 project_reports__isnull=False).distinct().first()
    csl = Student.objects.filter(school__framework_ref__is_fixed=False,
                                 project_reports__isnull=False).distinct().first()

    for student, expect_profiles in [(fsl, True), (csl, False)]:
        if not student:
            check('student fixture found', False)
            continue
        user = getattr(student, 'user', None) or User.objects.filter(
            email=student.school_email).first()
        if not user:
            check(f'login user for {student.first_name}', False, 'no User row')
            continue

        client = login_as(user)
        if not client:
            check(f'login as {student.first_name}', False, user.username)
            continue

        fw = student.school.framework_ref.name
        label = f'{student.first_name} [{fw}]'
        report = student.project_reports.select_related('project').first()

        # 1. reports list
        code, body, _ = fetch(client, '/student/reports/')
        check(f'{label} reports list 200', code == 200, f'status {code}')
        check(f'{label} reports list shows a project',
              report.project.title[:20] in body, f'looking for {report.project.title[:20]!r}')

        # 2. project report detail
        code, body, _ = fetch(client, f'/student/reports/{report.project_id}/')
        check(f'{label} report detail 200', code == 200, f'status {code}')
        top = (report.top_5_competencies or [{}])[0].get('competency_name', '')
        check(f'{label} report shows top competency', bool(top) and top in body, top)
        check(f'{label} report shows a band label',
              any(b in body for b in ['Very Strong', 'Strong', 'Emerging', 'Skill to work on']))
        check(f'{label} report shows assessment breakdown', 'Assessment 1' in body)
        check(f'{label} report shows coach feedback', 'Clear effort on this output' in body)

        if expect_profiles:
            want = (report.top_3_profiles or [{}])[0].get('profile_name', '')
            check(f'{label} report shows career match', bool(want) and want in body, want)
            if report.common_strengths:
                cs = report.common_strengths[0]['competency_name']
                check(f'{label} report shows common strengths',
                      'Common Strengths' in body and cs in body, cs)
        else:
            check(f'{label} report has NO career matches',
                  'Your Top Career Matches' not in body)

        # 3. annual passport
        code, body, _ = fetch(client, '/student/reports/annual/')
        check(f'{label} annual passport 200', code == 200, f'status {code}')
        check(f'{label} passport shows skills', 'Your Top Skills' in body)
        check(f'{label} passport not empty-state',
              'No Passport Yet' not in body)
        if expect_profiles:
            check(f'{label} passport shows career matches',
                  'Your Top Career Matches' in body)
        else:
            check(f'{label} passport has NO career matches',
                  'Your Top Career Matches' not in body)

        # 4. Kaushal Bodh report
        code, body, _ = fetch(client, '/student/reports/kaushal-bodh/')
        check(f'{label} KB report 200', code == 200, f'status {code}')
        if not expect_profiles:      # CSL frameworks are the ones carrying KB
            check(f'{label} KB report has KB data',
                  'Practical Skills' in body or 'Workplace Awareness' in body)

    # 5. Parent view of the same child
    print('\nRendering parent pages')
    from parent.models import Parent
    parent = Parent.objects.filter(students__project_reports__isnull=False).distinct().first()
    if not parent:
        check('parent with a reported child exists', False)
    else:
        puser = getattr(parent, 'user', None)
        client = login_as(puser) if puser else None
        if not client:
            check('login as parent', False, str(puser))
        else:
            child = parent.students.filter(project_reports__isnull=False).first()
            rep = child.project_reports.select_related('project').first()
            code, body, _ = fetch(client, f'/parent/child/{child.id}/reports/')
            check(f'parent reports list 200 ({child.first_name})', code == 200, f'status {code}')
            check('parent reports list shows a project', rep.project.title[:20] in body)

            code, body, _ = fetch(client, f'/parent/child/{child.id}/reports/{rep.project_id}/')
            check('parent report detail 200', code == 200, f'status {code}')
            check('parent report shows top competency',
                  (rep.top_5_competencies or [{}])[0].get('competency_name', '') in body)
            check('parent report not redirected to login', 'Sign in' not in body[:400])

            code, body, _ = fetch(client, f'/parent/child/{child.id}/passport/')
            check('parent passport 200', code == 200, f'status {code}')
            check('parent passport shows skills', 'Your Top Skills' in body)

            code, body, _ = fetch(client, f'/parent/child/{child.id}/kaushal-bodh/')
            check('parent KB report 200', code == 200, f'status {code}')

    # Thinking Coach — Score Viewing, the four views on spec slide 14
    print('\nRendering teacher Score Viewing (slide 14)')
    from teacher.models import Teacher
    from competencies.models import ScoreEntry

    coach = next((t for t in Teacher.objects.select_related('school', 'user')
                  if t.school and ScoreEntry.objects.filter(student__school=t.school).exists()),
                 None)
    if not coach:
        check('a coach whose school has scores exists', False)
    else:
        client = login_as(coach.user)
        if not client:
            check('login as coach', False, str(coach.user))
        else:
            grade = str(Student.objects
                        .filter(school=coach.school, score_entries__isnull=False)
                        .values_list('student_class', flat=True).first())
            for key, label, columns in [
                ('project_wise',   'Project Wise',                        ['Assessed in', 'Score']),
                ('agg_competency', 'Agg Competency Wise',                 ['Aggregate', 'Sub-pillar']),
                ('percentile',     'Percentile Competency',               ['Class avg', 'Median', 'Spread']),
                ('comparative',    'Project Level Aggregate Comparative', ['Coverage', 'Class avg']),
            ]:
                code, body, _ = fetch(client, f'/teacher/score-viewing/?view={key}&grade={grade}')
                check(f'{label} 200', code == 200, f'status {code}')
                check(f'{label} renders its columns', all(c in body for c in columns))
                check(f'{label} has data (not an empty state)',
                      not any(m in body for m in ('No scores recorded', 'No projects',
                                                  'Nothing to aggregate')))
            # Score Entry: the Generate button is project-level but sits under
            # whichever assessment is open, so it must show project-wide progress.
            code, body, _ = fetch(client, '/teacher/academics/score-entry/')
            check('score entry 200', code == 200, f'status {code}')
            raw = client.get('/teacher/academics/score-entry/', follow=True).content.decode('utf-8', 'replace')
            check('score entry shows scoring progress', 'generateProgress' in raw)
            check('score entry warns when assessments are unscored', 'generateWarning' in raw)
            check('generate button says it covers all assessments',
                  'Generate Project Reports (all assessments)' in raw)

            # Event Calendar had a sidebar entry pointing at href="#" with no
            # view behind it; events published to coaches were unreachable.
            code, body, _ = fetch(client, '/teacher/events/')
            check('coach event calendar 200', code == 200, f'status {code}')
            check('coach event calendar renders its heading', 'Event Calendar' in body)

            code, body, _ = fetch(client, f'/teacher/score-viewing/?view=project_wise&grade={grade}')
            check('slide 14 "repeated competencies" note',
                  'Repeated competencies are aggregated' in body)
            check('slide 14 Generate Profile Report action', 'Generate Profile Report' in body)
            check('slide 14 Show Grade / Show Project filters',
                  'Show Grade' in body and 'Show Project' in body)

    # Super Admin pages — where the last leak actually showed up
    print('\nRendering super admin pages')
    admin = User.objects.filter(role='SUPER_ADMIN').first()
    client = login_as(admin) if admin else None
    if not client:
        check('login as super admin', False)
    else:
        for url, needle in [
            ('/super-admin/skill-passport/learning-pillars/',      'Learning Pillars'),
            ('/super-admin/skill-passport/profiles-competencies/', 'Research Scholar'),
            ('/super-admin/skill-passport/project-assessment/',    'Oral/Portfolio'),
        ]:
            code, body, _ = fetch(client, url)
            check(f'{url} 200', code == 200, f'status {code}')
            check(f'{url} shows {needle!r}', needle in body)

    print('\nTemplate syntax leaking into rendered text')
    check('no template syntax on any page rendered above', not LEAKED,
          '; '.join(f'{u} has {m}' for u, m, _ in LEAKED))
    for u, m, ctx in LEAKED:
        print(f'     {u}  ->  {m}\n     ...{ctx.strip()}...')

    restore_passwords()

    print(f'\n{"="*60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    try:
        run()
    finally:
        restore_passwords()
