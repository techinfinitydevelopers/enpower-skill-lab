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

from verify_client import HttpsClient as Client
from accounts.models import User
from student.models import Student
from competencies.models import ProjectReport, Project

PASSWORD = 'SeedCheck!2026'
PASS, FAIL = [], []


class _ProbeDone(Exception):
    """Raised to roll back a probe that had to write to check itself."""


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
DUMMY_SEEN = []
BADLY_NESTED = []

# Invented copy that shipped inside templates instead of coming from a record.
# The Super Admin header carried a hardcoded badge of 4 and four of these --
# student notifications, on an admin screen, on a system with no data. Every
# page fetched below is checked, so the next one is caught on any screen
# rather than only where someone thought to look.
DUMMY_TEXT = (
    'Mathematics homework due by Friday',
    'Your Science test results are available',
    'History exam scheduled for next Monday',
    'Perfect Attendance badge',
    'Delhi Public School',
    'Lorem ipsum',
    'John Doe',
)


def fetch(client, url):
    r = client.get(url, follow=True)
    body = text_of(r.content.decode('utf-8', 'replace'))
    for marker in ('{#', '#}', '{% ', '{{ '):
        if marker in body:
            LEAKED.append((url, marker, body[max(0, body.find(marker) - 40):body.find(marker) + 80]))
            break
    for phrase in DUMMY_TEXT:
        if phrase in body:
            DUMMY_SEEN.append((url, phrase))
    # Nesting is checked on the raw markup, not the stripped text: an extra
    # </div> closes a wrapper early and moves the whole page, while every
    # other check here still passes.
    from verify_html import problems_in
    raw = r.content.decode('utf-8', 'replace')
    for problem in problems_in(raw):
        BADLY_NESTED.append((url, problem))
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
            ('/super-admin/skill-passport/profiles-competencies/', 'Tech Explorer'),
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

    check('no invented placeholder text on any page rendered above',
          not DUMMY_SEEN,
          '; '.join(f'{u}: {p!r}' for u, p in DUMMY_SEEN[:3]))
    for u, phrase in DUMMY_SEEN:
        print(f'     {u}  ->  {phrase!r}')

    check('every page rendered above is properly nested', not BADLY_NESTED,
          '; '.join(f'{u}: {p}' for u, p in BADLY_NESTED[:2]))
    for u, problem in BADLY_NESTED:
        print(f'     {u}  ->  {problem}')

    # ── the list screens are the same width as each other ───────────────
    # The parent list kept a 1600px centred container after the same cap had
    # been removed from its neighbours, so it rendered visibly narrower than
    # every other list and read as a broken page. Nothing server-side could
    # see that: the page returned 200 and contained everything it should.
    print('\nTHE LIST SCREENS ARE NOT CAPPED NARROWER THAN EACH OTHER')
    import re as _re

    capped = []
    for sheet in ('school-list', 'student-list', 'teacher-list',
                  'parent-list', 'pc-list', 'school-admin-list'):
        path = os.path.join(settings.BASE_DIR, 'static', 'css', 'superadmin',
                            f'{sheet}.css')
        if not os.path.exists(path):
            continue
        css = open(path, encoding='utf-8', errors='ignore').read()
        # Strip comments first: the cap is commented out on some of these and
        # a commented rule is not a rule.
        live = _re.sub(r'/\*.*?\*/', '', css, flags=_re.S)
        for block in _re.findall(r'\.[\w-]*(?:page|wrapper)[\w-]*\s*\{[^}]*\}', live):
            fixed = _re.search(r'max-width:\s*(\d+)px', block)
            if fixed and 'media' not in block:
                capped.append(f'{sheet}.css: {fixed.group(0)}')

    check('no list page container is pinned to a fixed pixel width',
          not capped, '; '.join(capped))

    # ── our toast does not share a name with Bootstrap's ────────────────
    # Bootstrap 5.3 ships `.toast:not(.show){display:none}`. That selector is
    # (0,2,0); a plain `.toast` rule of ours is (0,1,0), so Bootstrap wins
    # whichever stylesheet loads last. Our toasts carry no `.show`, so every
    # one of them sat in the DOM fully built and invisible -- which is why
    # adding a school looked like it had failed, and why the toast bug stayed
    # open from 24 August. Six of the seven role bases load Bootstrap.
    print(chr(10) + 'THE TOAST DOES NOT COLLIDE WITH BOOTSTRAP')
    import re as _re3

    _BOOTSTRAP_OWNS = ('toast', 'toast-container', 'toast-header', 'toast-body')
    _clashes = []
    for _root, _dirs, _files in os.walk(settings.BASE_DIR):
        if any(p in _root for p in ('venv', '.git', 'node_modules', 'staticfiles',
                                    'migrations', '__pycache__')):
            continue
        for _f in _files:
            if not _f.endswith(('.html', '.css', '.js')):
                continue
            _path = os.path.join(_root, _f)
            _text = open(_path, encoding='utf-8', errors='ignore').read()
            for _cls in _BOOTSTRAP_OWNS:
                # class="toast ..." in markup, or a bare .toast selector.
                if _re3.search(r'class="[^"]*(?<![\w-])' + _cls + r'(?![\w-])',
                               _text) or \
                   _re3.search(r'(?<![\w-])\.' + _cls + r'(?![\w-])', _text):
                    _clashes.append(
                        f'{os.path.relpath(_path, settings.BASE_DIR)}: .{_cls}')
    _damaged = []
    for _root, _dirs, _files in os.walk(settings.BASE_DIR):
        if any(p in _root for p in ('venv', '.git', 'node_modules',
                                    'staticfiles', '__pycache__')):
            continue
        for _f in _files:
            if not _f.endswith(('.html', '.css', '.js', '.py')):
                continue
            _p = os.path.join(_root, _f)
            _raw = open(_p, 'rb').read()
            if bytes([0]) in _raw or b'KEEP' + b'esl-' in _raw:
                _damaged.append(os.path.relpath(_p, settings.BASE_DIR))

    check('nothing uses a class name Bootstrap also styles', not _clashes,
          '; '.join(sorted(set(_clashes))[:3]))

    # A bulk rename I ran wrote its own sentinel into twelve files -- NUL
    # bytes and KEEP markers in the middle of class names and CSS variables.
    # The toast still rendered, so every page check passed; the success
    # colour just silently fell back to the base purple.
    check('no source file carries a NUL byte or a leftover rename marker',
          not _damaged, '; '.join(_damaged[:3]))

    # Success is green and error is red. These were purple on screen because
    # the variables they point at had been corrupted, which no amount of
    # rendering the page would have revealed.
    _toast_css = open(os.path.join(settings.BASE_DIR, 'static', 'css',
                                   'common', 'toast.css'),
                      encoding='utf-8', errors='ignore').read()
    for _kind, _hex in (('success', '#16a34a'), ('error', '#dc2626')):
        check(f'the {_kind} toast is defined as {_hex}',
              f'--esl-toast-{_kind}: {_hex}' in _toast_css)
        check(f'and its icon uses that colour, not a fallback',
              f'.esl-toast-{_kind} .esl-toast-icon {{ background: var(--esl-toast-{_kind}); }}' in _toast_css)

    # Both files changed twice while the URL stayed ?v=3, so browsers kept
    # serving the broken copy and the fix was invisible on screen even
    # though the server had it. Every page that loads them must ask for a
    # version, and the same one.
    _busted = []
    for _root, _dirs, _files in os.walk(settings.BASE_DIR):
        if any(p in _root for p in ('venv', '.git', 'node_modules',
                                    'staticfiles', '__pycache__')):
            continue
        for _f in _files:
            if not _f.endswith('.html'):
                continue
            _p = os.path.join(_root, _f)
            _txt = open(_p, encoding='utf-8', errors='ignore').read()
            for _asset in ('toast.css', 'toast.js'):
                for _m in _re3.finditer(
                        _re3.escape(_asset) + r"' %\}(\?v=(\d+))?", _txt):
                    if not _m.group(1):
                        _busted.append(
                            f'{os.path.relpath(_p, settings.BASE_DIR)}: {_asset} has no ?v=')
    check('every page asks for a versioned toast asset', not _busted,
          '; '.join(sorted(set(_busted))[:3]))

    # And it must sit clear of the sticky header, which it covered at 20px.
    _top = _re3.search(r'\.esl-toast-container \{[^}]*top:\s*(\d+)px',
                       _toast_css)
    check('the toast clears the header rather than covering it',
          _top is not None and int(_top.group(1)) >= 70,
          f'top: {_top.group(1)}px' if _top else 'no top found')

    # The sweep above only read class="..." attributes and CSS selectors, so
    # it missed two pages that build their toast in JavaScript:
    #     el.className = `toast toast-${t}`
    # Those stayed bare and Bootstrap kept hiding them -- on exactly the two
    # pages where the toast was first reported broken.
    _js_bare = []
    for _root, _dirs, _files in os.walk(settings.BASE_DIR):
        if any(p in _root for p in ('venv', '.git', 'node_modules',
                                    'staticfiles', '__pycache__')):
            continue
        for _f in _files:
            if not _f.endswith(('.html', '.js')):
                continue
            _p = os.path.join(_root, _f)
            _txt = open(_p, encoding='utf-8', errors='ignore').read()
            _quotes = '[' + chr(96) + chr(39) + chr(34) + ']'
            for _m in _re3.finditer(
                    r'className\s*=\s*' + _quotes + '([^' + chr(96)
                    + chr(39) + chr(34) + ']*)', _txt):
                for _word in _m.group(1).split():
                    _word = _word.split('$')[0].split('{')[0]
                    if _word == 'toast' or (_word.startswith('toast-')
                                            and 'esl-' not in _word):
                        _js_bare.append(
                            f'{os.path.relpath(_p, settings.BASE_DIR)}: className={_m.group(1)!r}')
    check('no script builds a toast with an unprefixed class', not _js_bare,
          '; '.join(sorted(set(_js_bare))[:2]))

    # The badge is our own circle. A glyph that is itself a circle draws a
    # second one inside the first, and two concentric circles make any
    # offset at all look like a centring bug -- which is exactly how it was
    # reported. A plain mark has nothing to be compared against.
    _ROUND_GLYPHS = ('check_circle', 'cancel', 'error_circle', 'info')
    _nested = []
    for _root, _dirs, _files in os.walk(settings.BASE_DIR):
        if any(p in _root for p in ('venv', '.git', 'node_modules',
                                    'staticfiles', '__pycache__',
                                    'skillpassport')):
            continue
        for _f in _files:
            if not _f.endswith(('.html', '.js')):
                continue
            _p = os.path.join(_root, _f)
            _txt = open(_p, encoding='utf-8', errors='ignore').read()
            if 'esl-toast-icon' not in _txt and 'ICONS' not in _txt:
                continue
            for _g in _ROUND_GLYPHS:
                if _re3.search(r"(success|error)'?\s*(%\}|:)\s*'?" + _g, _txt):
                    _nested.append(
                        f'{os.path.relpath(_p, settings.BASE_DIR)}: {_g}')
    check('the toast badge holds a plain mark, not a second circle',
          not _nested, '; '.join(sorted(set(_nested))[:2]))

    # And the glyph must sit on its own line box, or the icon font's leading
    # pushes it off the middle of the badge.
    check('the toast glyph has line-height 1 so flex can centre it',
          'line-height: 1;' in _toast_css
          and 'display: block;' in _toast_css)

    # ── adding a school says so, and shows you ──────────────────────────
    # It used to save the school, redirect silently to the dashboard, and
    # leave the user thinking nothing had happened.
    print(chr(10) + 'ADDING A SCHOOL TELLS YOU IT WORKED')
    from schools.models import School as _School

    _su = User.objects.filter(role='SUPER_ADMIN', is_active=True).first()
    _admin = login_as(_su) if _su else None
    if _admin:
        _School.objects.filter(school_code='ZZVP1').delete()
        _r = _admin.post('/super-admin/onboard-school/', {
            'schoolName': 'ZZ Verify School', 'schoolCode': 'ZZVP1',
            'board': 'cbse', 'schoolType': 'private', 'medium': 'english',
            'schoolEmail': 'zzvp1@example.com', 'schoolPhone': '9000000001',
            'principalName': 'P', 'principalPhone': '9000000002',
            'principalEmail': 'zzvp1p@example.com', 'branchAddress': 'A',
            'city': 'Mumbai', 'state': 'Maharashtra', 'pincode': '400001',
            'emergencyContactPerson': 'X', 'emergencyPhone': '9000000003',
        }, follow=True)
        _made = _School.objects.filter(school_code='ZZVP1').first()
        _html = _r.content.decode('utf-8', 'replace')
        _landed = _r.redirect_chain[-1][0] if _r.redirect_chain else ''

        check('the school is created', _made is not None)
        check('and you land on the school list, not the dashboard',
              'schools' in _landed and 'dashboard' not in _landed, _landed)
        check('with a success message', 'successfully onboarded' in _html)
        check('rendered in a toast Bootstrap will not hide',
              'esl-toast' in _html and 'class="toast' not in _html)

        # An icon font renders its ligature from the span's text, so
        # whitespace around the name is text too and the glyph stops sitting
        # in the middle of the badge. Read from the response, because the
        # template can look tidy and still emit it.
        _ico = _re3.search(
            r'<div class="esl-toast-icon">\s*<span[^>]*>(.*?)</span>',
            _html, _re3.S)
        check('the toast icon renders with no whitespace around its glyph',
              _ico is not None and _ico.group(1) == _ico.group(1).strip(),
              repr(_ico.group(1)) if _ico else 'no icon in the response')
        check('and the glyph is a plain mark',
              _ico is not None and _ico.group(1).strip() in
              ('check', 'close', 'warning', 'info'),
              _ico.group(1).strip() if _ico else '')

        # The one check that was missing every time. The base class was
        # renamed but the modifier is built from a template variable --
        # `toast-{{ message.tags }}` matched no literal, so the markup said
        # `esl-toast toast-success` while the stylesheet said
        # `.esl-toast-success`. The rule never applied and the icon kept the
        # base purple. Reading the rendered class against the real stylesheet
        # is the only thing that catches that.
        _rendered = _re3.search(r'<div class="(esl-toast [^"]*)"', _html)
        check('the toast carries a modifier class at all',
              _rendered is not None,
              '' if _rendered else 'no esl-toast element in the response')
        if _rendered:
            _classes = _rendered.group(1).split()
            _unstyled = [c for c in _classes if f'.{c}' not in _toast_css]
            check('every class on the rendered toast is one the stylesheet '
                  'actually defines', not _unstyled,
                  '' if not _unstyled else
                  f'{_unstyled} rendered but not styled -- the colour falls back')
        check('and the new school is visibly in the list',
              _made is not None and _made.school_name in _html,
              'seeing the row is what actually reassures')
        if _made:
            _made.delete()

    # ── the two dashboards name the same reports the same way ───────────
    # The parent side said "Project Reports" and "Annual Skill Report" while
    # the student side said "Skill Passport" and "Annual Passport" for the
    # same three reports. And Kaushal Bodh is a CSL report -- FSL records no
    # KB score at all (0 of 18 reports), so it opens empty there.
    print(chr(10) + 'STUDENT AND PARENT NAME THE REPORTS ALIKE')
    from competencies.models import Framework as _Fw
    from parent.models import Parent as _Par

    _WANTED = ('Project Report', 'Annual Skill Passport')
    _RETIRED = ('Skill Passport<', 'Annual Passport<', 'Project Reports<',
                'Annual Skill Report<')

    for _label, _profiling in (('FSL', True), ('CSL', False)):
        _fws = _Fw.objects.filter(has_profiling=_profiling)
        _pupil = (Student.objects.select_related('school__framework_ref', 'user')
                  .filter(user__isnull=False, school__framework_ref__in=_fws)
                  .first())
        if not _pupil:
            print(f'  ..    no {_label} student with a login')
            continue
        _fw = _pupil.school.framework_ref
        _c = login_as(_pupil.user)
        if not _c:
            check(f'{_label}: can sign in', False, _pupil.user.username)
            continue

        _side = _c.get('/student/dashboard/',
                       follow=True).content.decode('utf-8', 'replace')
        for _name in _WANTED:
            check(f'{_label} student sidebar says "{_name}"', _name in _side)
        _old = [o for o in _RETIRED if o in _side]
        check(f'{_label} student sidebar drops the old names', not _old,
              '; '.join(_old))

        # Kaushal Bodh follows the framework, in the opposite direction to
        # the passport: CSL yes, FSL no.
        check(f'{_label} student: Kaushal Bodh '
              f'{"shown" if not _profiling else "hidden"}',
              ('Kaushal Bodh Report' in _side) != _profiling,
              f'has_kaushal_bodh={_fw.has_kaushal_bodh}')
        _kb = _c.get('/student/reports/kaushal-bodh/')
        check(f'{_label} student: the KB url agrees with the sidebar',
              (_kb.status_code == 200) != _profiling,
              f'HTTP {_kb.status_code}')

        # The parent of that same child must read the same words, and get the
        # same answer about KB -- they were the two screens that disagreed.
        _mum = _Par.objects.filter(students=_pupil, user__isnull=False).first()
        if not _mum:
            print(f'  ..    no parent linked to that {_label} student')
            continue
        _pc = login_as(_mum.user)
        if not _pc:
            continue
        _pside = _pc.get('/parent/dashboard/',
                         follow=True).content.decode('utf-8', 'replace')
        for _name in _WANTED:
            check(f'{_label} parent sidebar says "{_name}"', _name in _pside)
        _oldp = [o for o in _RETIRED if o in _pside]
        check(f'{_label} parent sidebar drops the old names', not _oldp,
              '; '.join(_oldp))

    # The flag itself, so a framework added later does not silently inherit
    # the wrong answer.
    check('FSL has Kaushal Bodh switched off',
          not _Fw.objects.filter(has_profiling=True,
                                 has_kaushal_bodh=True).exists(),
          'FSL records no KB scores, so the report would open empty')
    check('the CSL frameworks keep it',
          not _Fw.objects.filter(has_profiling=False,
                                 has_kaushal_bodh=False).exists())

    # ── nothing sends a user to the old droplet's domain ────────────────
    # enpower.techinfinity.link still resolves, to the destroyed droplet's
    # IP, and has no MX record -- so an address there cannot receive mail
    # and a link there cannot load. A schedule page told people to write to
    # lbsupport@ on that domain to delete a schedule they could delete
    # themselves with the button next to it.
    print(chr(10) + 'NO PAGE POINTS AT THE DEAD DOMAIN')
    import re as _re2

    _guilty = []
    for _root, _dirs, _files in os.walk(settings.BASE_DIR):
        if any(p in _root for p in ('venv', '.git', 'node_modules', 'staticfiles')):
            continue
        for _f in _files:
            if not _f.endswith('.html'):
                continue
            _path = os.path.join(_root, _f)
            _text = open(_path, encoding='utf-8', errors='ignore').read()
            # A {% comment %} explaining why it was removed is not a link.
            _live = _re2.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}',
                             '', _text, flags=_re2.S)
            if 'techinfinity.link' in _live:
                _guilty.append(os.path.relpath(_path, settings.BASE_DIR))
    check('no template links to enpower.techinfinity.link', not _guilty,
          '; '.join(_guilty))

    # ---- Class List: the coach's own face, and a year list that keeps up ----
    # The column read the login's picture, which a coach never has, and fell
    # through to a stock-photo service -- so every row showed a stranger's
    # face. The year dropdowns were typed out by hand and stopped one year
    # short of the model, so the year the schools are actually in could not be
    # chosen.
    from django.core.files.base import ContentFile
    from django.db import transaction as _tx
    from schools.models import Class as _Class
    from teacher.models import Teacher as _Teacher

    print(chr(10) + 'CLASS LIST SHOWS THE COACH, NOT A STOCK PHOTO')
    _boss = User.objects.filter(role='SUPER_ADMIN', is_active=True).first()
    if not _boss:
        check('a Super Admin exists to read the class list with', False)
    else:
        _admin = login_as(_boss)

        def _markup(url):
            """Raw HTML. fetch() strips tags, and these checks read
            attributes -- an <option value> and an <img src>."""
            return _admin.get(url, follow=True).content.decode(
                'utf-8', 'replace')

        _body = _markup('/super-admin/classes/')
        check('the class list serves no stock-photo avatars',
              'i.pravatar.cc' not in _body)

        _years = set(_re2.findall(r'<option value="(\d{4}-\d{4})"', _body))
        _want = {v for v, _ in _Class.ACADEMIC_YEAR_CHOICES}
        check('every academic year the model offers is on the page',
              _want <= _years, 'missing ' + str(sorted(_want - _years)))

        _assigned = (_Class.objects.filter(thinking_coach__isnull=False)
                     .select_related('thinking_coach').first())
        if not _assigned:
            check('some class has a coach, to test the avatar with', False)
        else:
            _profile = _Teacher.objects.filter(
                user=_assigned.thinking_coach).first()
            if not _profile:
                check('that coach has a Teacher row, which is where the '
                      'photograph lives', False,
                      _assigned.thinking_coach.username)
            else:
                _had = _profile.profile_photo.name
                _path = None
                try:
                    with _tx.atomic():
                        _profile.profile_photo.save(
                            'zz_pages_probe.jpg',
                            ContentFile(b'probe, not a real image'), save=True)
                        _path = _profile.profile_photo.path
                        _shown = _markup('/super-admin/classes/')
                        check('a coach with a photograph has it shown',
                              _profile.profile_photo.url in _shown)
                        check('and no initials stand in for it',
                              _shown.count('teacher-avatar-initials')
                              < _body.count('teacher-avatar-initials'),
                              str(_body.count('teacher-avatar-initials')) +
                              ' -> ' + str(_shown.count('teacher-avatar-initials')))
                        raise _ProbeDone
                except _ProbeDone:
                    pass
                finally:
                    # The row rolls back; the file does not.
                    if _path:
                        try:
                            os.remove(_path)
                        except OSError:
                            pass
                _profile.refresh_from_db()
                check('the probe left the coach as it found them',
                      _profile.profile_photo.name == _had,
                      _profile.profile_photo.name)

    # ---- The year it actually is, and a target nobody invented -------------
    # Four model fields and two views each carried the literal '2025-2026', so
    # everything made after April 2026 was stamped a year behind: the Super
    # Admin's 2026-2027 filter found nothing and School Admin still read
    # 2025-2026. And the projects target was a flat 12 from the deck, so a
    # school with nothing set up read "0 of 12" -- a target nobody agreed to.
    import datetime as _dt

    from enpower_skill_lab.academic_year import current_academic_year
    from attendance.services import projects_completed, student_projects

    print(chr(10) + 'THE YEAR IT ACTUALLY IS')
    for _when, _want in ((_dt.date(2026, 3, 31), '2025-2026'),
                         (_dt.date(2026, 4, 1), '2026-2027'),
                         (_dt.date(2026, 6, 10), '2026-2027'),
                         (_dt.date(2027, 1, 15), '2026-2027'),
                         (_dt.date(2027, 4, 1), '2027-2028')):
        check(f'{_when} falls in {_want}',
              current_academic_year(_when) == _want,
              current_academic_year(_when))

    check('today has a year, and it is this one',
          current_academic_year() == current_academic_year(_dt.date.today()))

    # A default that is a string is a default that goes stale. These must be
    # callables, or we are back to stamping last year onto this year's rows.
    _hardcoded = []
    for _f in ('attendance/models.py', 'schools/models.py',
               'coordinator/views.py'):
        _src = open(os.path.join(settings.BASE_DIR, _f),
                    encoding='utf-8', errors='ignore').read()
        for _line in _src.splitlines():
            if 'academic_year' not in _line or _line.lstrip().startswith('#'):
                continue
            if _re2.search(r"=\s*'20\d\d-20\d\d'", _line):
                _hardcoded.append(f'{_f}: {_line.strip()[:70]}')
    check('no academic year is typed into a default', not _hardcoded,
          '; '.join(_hardcoded))

    # The Class List's dropdowns read the model, so the current year reaching
    # the page is the same question as the model knowing it.
    from schools.models import Class as _Cls

    check('the model offers the year we are actually in',
          current_academic_year() in {v for v, _ in _Cls.ACADEMIC_YEAR_CHOICES},
          str([v for v, _ in _Cls.ACADEMIC_YEAR_CHOICES]))

    print(chr(10) + 'THE PROJECTS TARGET IS A COUNT, NOT A CONSTANT')
    _pupil = (Student.objects.select_related('school', 'user')
              .filter(user__isnull=False, school__isnull=False, is_active=True)
              .first())
    if not _pupil:
        check('a student with a login exists to count projects for', False)
    else:
        _done, _total = projects_completed(_pupil)
        _real = len(student_projects(_pupil))
        check('the total is the projects the class actually has',
              _total == max(_real, _done), f'{_total} vs {_real}')
        check('it is never the flat 12 unless the class really has 12',
              _total != 12 or _real == 12, str(_total))

        _stu = login_as(_pupil.user)
        _body = _stu.get('/student/dashboard/', follow=True).content.decode(
            'utf-8', 'replace')
        _ring = _re2.search(r'stud-dash-chart-percent">(\d+)/(\d+)<', _body)
        check('the dashboard ring quotes that same total',
              bool(_ring) and int(_ring.group(2)) == _total,
              _ring.group(0) if _ring else '(ring not found)')
        check('no "of 12" is left on the page unless 12 is the real number',
              'of 12' not in _body or _real == 12)

        # A school with nothing set up must read 0 of 0, which is what the
        # client asked for: a target nobody has agreed to is worse than none.
        # Build the case rather than hunt for one: on a database where
        # every class has projects this check would quietly skip itself,
        # and 0 of 0 is the thing the client actually asked for.
        _zero = Student.objects.filter(pk=_pupil.pk).first()
        _zero.student_class = '99'          # in memory only, never saved
        check('a class with no projects has none to count',
              student_projects(_zero) == [])
        # The total collapses to what the student has actually finished,
        # never to an invented target. A student holding three reports
        # reads 3 of 3, not 3 of 0 and not 3 of 12.
        _reports = ProjectReport.objects.filter(
            student=_zero).values('project').distinct().count()
        check('its total falls back to work actually done',
              projects_completed(_zero) == (_reports, _reports),
              str(projects_completed(_zero)))
        check('the probe saved nothing',
              Student.objects.get(pk=_pupil.pk).student_class
              == _pupil.student_class)

        # And the case the client actually raised: a school with nothing
        # set up and a child who has finished nothing reads 0 of 0.
        # Made, not found: on a seeded database every student already has
        # reports, and this check would skip itself on the one case the
        # client actually raised.
        import datetime as _d2

        from django.db import transaction as _tx2

        try:
            with _tx2.atomic():
                _fresh = Student.objects.create(
                    first_name='ZZ', last_name='Fresh',
                    school=_pupil.school, date_of_birth=_d2.date(2014, 5, 1),
                    enrollment_date=_d2.date(2025, 6, 1),
                    student_class='99', division='Z', is_active=True,
                    skill_lab_reg_id='ZZ-PAGES-FRESH')
                check('nothing set up and nothing done reads 0 of 0',
                      projects_completed(_fresh) == (0, 0),
                      str(projects_completed(_fresh)))
                raise _ProbeDone
        except _ProbeDone:
            pass
        check('that probe student is gone',
              not Student.objects.filter(
                  skill_lab_reg_id='ZZ-PAGES-FRESH').exists())

    # ---- Class List: the Actions column does something ---------------------
    # All three buttons were markup only. Edit opened the drawer with every
    # field blank -- its handler carried a comment saying the data "would
    # typically" be fetched and then opened it anyway -- Update Class closed
    # the drawer and saved nothing, and View and Delete had no handler at all.
    # edit_class and delete_class existed the whole time with nothing wired to
    # them, so a Super Admin pressed Update and believed it had saved.
    from django.db import transaction as _tx3
    from schools.models import Class as _Cl2, School as _Sch2

    print(chr(10) + 'CLASS LIST ACTIONS REACH THE SERVER')
    _boss2 = User.objects.filter(role='SUPER_ADMIN', is_active=True).first()
    if not _boss2:
        check('a Super Admin exists to press the buttons', False)
    else:
        _ad = login_as(_boss2)

        _js = open(os.path.join(settings.BASE_DIR,
                                'static/js/superadmin/class-list.js'),
                   encoding='utf-8', errors='ignore').read()
        check('the edit handler no longer just opens an empty drawer',
              'would typically fetch data from the server' not in _js)
        for _needed, _what in (
                ('fillDrawerFrom', 'the drawer is filled from the row'),
                ('.view-class-btn', 'View has a handler'),
                ('.delete-class-btn', 'Delete has a handler'),
                ("$form.trigger('submit')", 'Update Class submits the form')):
            check(_what, _needed in _js)

        try:
            with _tx3.atomic():
                _sch = _Sch2.objects.first()
                _row = _Cl2.objects.create(
                    school=_sch, grade='6', division='A', class_name='Std 6A',
                    class_code='ZZ-PAGES-ACTIONS', academic_year='2026-2027',
                    total_sessions=48, is_active=True,
                    student_visibility=True, parent_visibility=False)

                _html = _ad.get('/super-admin/classes/',
                                follow=True).content.decode('utf-8', 'replace')
                _missing = [a for a in (
                    'data-class-id', 'data-school-id', 'data-grade',
                    'data-division', 'data-class-code', 'data-academic-year',
                    'data-coach-id', 'data-total-sessions', 'data-is-active',
                    'data-student-visibility', 'data-parent-visibility',
                    'data-delete-url') if a not in _html]
                check('the row carries everything the drawer needs',
                      not _missing, ', '.join(_missing))
                check('there is a delete form with a CSRF token',
                      'deleteClassForm' in _html
                      and 'csrfmiddlewaretoken' in _html)
                check('the edit form knows where to post',
                      'id="editClassForm"' in _html)

                _r = _ad.post(f'/super-admin/class/{_row.id}/edit/', {
                    'school': _sch.id, 'grade': '7', 'division': 'b',
                    'class_name': '', 'academic_year': '2026-2027',
                    'total_sessions': '30', 'thinking_coach': '',
                    'is_active': 'true', 'student_visibility': 'false',
                    'parent_visibility': 'true'}, follow=True)
                _row.refresh_from_db()
                check('editing actually saves',
                      (_row.grade, _row.division, _row.total_sessions)
                      == ('7', 'B', 30),
                      f'{_row.grade} {_row.division} {_row.total_sessions}')
                check('the class name follows grade and division',
                      _row.class_name == 'Std 7B', _row.class_name)
                check('the toggles are saved, not just drawn',
                      _row.student_visibility is False
                      and _row.parent_visibility is True)

                check('delete refuses a GET',
                      _ad.get(f'/super-admin/class/{_row.id}/delete/'
                              ).status_code == 405)
                _ad.post(f'/super-admin/class/{_row.id}/delete/', follow=True)
                check('and a POST removes the row',
                      not _Cl2.objects.filter(id=_row.id).exists())
                raise _ProbeDone
        except _ProbeDone:
            pass
        check('the probe class is gone',
              not _Cl2.objects.filter(class_code='ZZ-PAGES-ACTIONS').exists())

    restore_passwords()

    print(f'\n{"="*60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    try:
        run()
    finally:
        restore_passwords()
