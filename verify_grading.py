"""Letter grades: the bands, what the coach sees, and what a family must not.

The client's reason, in their words: "The idea is to not let parents see the
actual score so they don't compare too much... So if possible the scores can
be recorded in the TCs entry area. But while showing in parents and students,
let's keep grades only."

That only holds if the number is gone from every page a parent or a student
can open. A report reading `A` in one place and `8/10` two sections down hands
the number straight back, so the central check here is not that grades appear
-- it is that no mark out of ten survives anywhere on those pages. Each page is
read as a human reads it: scripts and styles stripped out, tags removed, and
the remaining text searched for a mark.

The coach keeps the number. They enter marks and never grades, and the grade
is printed beside the average so they can see what it works out to.

Everything runs inside a transaction that is rolled back.

Run with:  python verify_grading.py
"""

import io
import itertools
import os
import re

import django

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'enpower_skill_lab.settings'
    django.setup()

from django.conf import settings

settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

import json

from django.contrib.auth import get_user_model
from django.db import transaction

from competencies.grading import BANDS, grade_for
from competencies.models import (Assessment, AssessmentCompetency,
                                 ProjectReport, ScoreEntry)
from parent.models import Parent
from schools.models import School
from student.models import Student
from verify_client import HttpsClient as Client

U = get_user_model()
PASSWORD = 'Zz!2026pw'

PASS, FAIL = [], []

# Keeps every copied row's unique columns from colliding with the original.
STAMP = itertools.count(1)


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


# --------------------------------------------------------------- the bands

def check_bands():
    print('\n1. the bands the client sent')

    # Read straight off the client's table, including both sides of every
    # boundary it names.
    for score, expected in [
        (10, 'A+'), (9.5, 'A+'), (9.0, 'A+'),
        (8.9, 'A'), (8.0, 'A'), (7.0, 'A'),
        (6.9, 'B'), (6.0, 'B'), (5.0, 'B'),
        (4.9, 'C'), (4.0, 'C'), (3.0, 'C'),
        (2.9, 'D'), (1.0, 'D'), (0.0, 'D'),
    ]:
        check(f'{score} is {expected}', grade_for(score) == expected,
              grade_for(score))

    # The table reads "7 - 8.9" then "9 - 10", so 8.95 belongs to neither. The
    # bands are written as floors for that reason; nothing on the scale may
    # come back without a grade.
    scale = [round(n / 100, 2) for n in range(0, 1001)]
    missing = [v for v in scale if grade_for(v) is None]
    check('every value from 0.00 to 10.00 has a grade', not missing,
          missing[:5])

    order = ['D', 'C', 'B', 'A', 'A+']
    ranks = [order.index(grade_for(v)) for v in scale]
    check('the grade never falls as the score rises',
          all(b >= a for a, b in zip(ranks, ranks[1:])))

    # A blank is not a D. An unscored competency has earned nothing, and
    # printing a D against it would be an accusation.
    check('no score means no grade, not a D', grade_for(None) is None,
          grade_for(None))
    check('nonsense means no grade', grade_for('not a number') is None)
    check('the bands are declared from the top down',
          [floor for floor, _ in BANDS] == sorted(
              [floor for floor, _ in BANDS], reverse=True))

    # The filter is what every family page actually calls.
    from django.template import Context, Template
    rendered = Template(
        '{% load grading_tags %}{{ a|grade }}|{{ b|grade }}|{{ c|grade }}'
    ).render(Context({'a': 8.5, 'b': None, 'c': 9}))
    check('the template filter prints the same letters',
          rendered == 'A|\u2014|A+', rendered)


# --------------------------------------------------- reading a page as read

TAGS = re.compile(r'<[^>]+>')
DROP = re.compile(r'<(script|style)\b.*?</\1>', re.S | re.I)
# A mark out of ten as a person would see it. The trailing guard keeps a date
# such as 15/10/2026 from reading as a score.
MARK = re.compile(r'(?<![\d/])\d{1,2}(?:\.\d+)?\s*/\s*10(?![\d/])')


def visible(html):
    """The page's text, as a reader sees it -- no scripts, no styles, no tags."""
    import html as html_mod
    text = DROP.sub(' ', html)
    text = TAGS.sub(' ', text)
    return html_mod.unescape(re.sub(r'\s+', ' ', text))


# Every place a score used to be printed. "out of ten" is not the only way a
# number escapes -- the KB card printed a bare `8.3` with the words underneath,
# and a search for marks would never have seen it. These are read by the class
# that holds them, and whatever is inside has to be a letter.
SCORE_SLOTS = re.compile(
    r'class="(cr-score|cs-score|asmt-avg|asmt-comp-score|workon-score|'
    r'topproj-num|sh-stat-value|section-badge)[^"]*"[^>]*>'
    r'(.*?)</(?:div|span)>', re.S)

GRADE_TEXT = re.compile(r'^(?:avg |grade |score )?(A\+|A|B|C|D|\u2014)$', re.I)

OVERALL_CARD = re.compile(
    r'stat-label">\s*Overall Level\s*</div>\s*'
    r'<div class="stat-value[^"]*"[^>]*>(.*?)</div>', re.S)


def score_slots(html):
    """[(class, what is printed there)] for every slot that used to hold a mark."""
    out = []
    for css, inner in SCORE_SLOTS.findall(html):
        text = re.sub(r'<[^>]+>', ' ', inner)
        text = re.sub(r'\s+', ' ', text).strip()
        out.append((css, text))
    return out


def numbers_in_slots(html):
    """The slots still printing something that is not a grade."""
    bad = []
    for css, text in score_slots(html):
        if not text:
            continue
        # The Top Match card is a percentage and the section badges carry
        # counts and dates; only the ones that can hold a score are judged.
        if css == 'section-badge' and not text.lower().startswith('avg'):
            continue
        if not GRADE_TEXT.match(text):
            bad.append(f'{css}={text}')

    for inner in OVERALL_CARD.findall(html):
        text = re.sub(r'\s+', ' ',
                      re.sub(r'<[^>]+>', ' ', inner)).strip()
        if text and not GRADE_TEXT.match(text):
            bad.append(f'Overall Level={text}')
    return bad


def marks_in(html):
    text = visible(html)
    found = MARK.findall(text)
    if re.search(r'out of 10', text, re.I):
        found.append('out of 10')
    return found


# -------------------------------------------------------- the coach's screen

def check_coach(teacher_user, assessment):
    print('\n2. the coach still has the numbers')

    client = sign_in(teacher_user)
    body = client.get('/teacher/academics/score-entry/',
                      follow=True).content.decode('utf-8', 'replace')

    check('the marks-entry page knows the bands',
          'function gradeFor' in body)
    check('the average prints the mark', 'a.avg.toFixed(1)' in body)
    check('and the grade it works out to, beneath it',
          '${gradeFor(a.avg)}' in body)
    check('the class average carries its grade too',
          "'Grade ' + gradeFor(parseFloat(avg))" in body)

    # The switch was built, then the client said the entry area keeps scores
    # and families keep grades -- which leaves nothing for a switch to do.
    for gone in ('gradeToggleWrap', 'setGradeMode', 'gradeMode',
                 'grade-mode-btn'):
        check(f'the abandoned switch left nothing behind: {gone}',
              gone not in body)
    check('and its endpoint is gone',
          client.post('/teacher/api/save-grade-display/',
                      data='{}', content_type='application/json'
                      ).status_code == 404)

    # Scores are typed into these cells. A letter cannot be typed back.
    check('score cells are still marks', '${score}/10' in body)

    data = json.loads(client.get(
        f'/teacher/api/score-entry-data/?assessment_id={assessment.id}'
    ).content)
    check('the data still carries real scores, not letters',
          all(isinstance(v, (int, float)) for v in data['scores'].values()),
          list(data['scores'].values())[:3])
    check('and the class average is still a number',
          data['stats']['class_avg'] is None
          or isinstance(data['stats']['class_avg'], (int, float)),
          data['stats']['class_avg'])


# -------------------------------------------------- what a family can open

def heading_value(html, css_class):
    found = re.search(r'class="' + css_class + r'"[^>]*>(.*?)</div>', html,
                      re.S)
    return re.sub(r'<[^>]+>', '', found.group(1)).strip() if found else None


def assessment_figures(html):
    """{assessment name: the figure printed against it} from the report.

    Slicing the page from the assessment's name was the obvious way and the
    wrong one: the section itself is headed "Assessment", so the slice started
    at the heading and every check then ran against a few characters of title.
    A card at a time, read from its own markup.
    """
    figures = {}
    for card in re.findall(
            r'<div class="asmt-card">(.*?)<div class="asmt-comps">', html,
            re.S):
        name = re.search(r'<div class="asmt-name">(.*?)</div>', card, re.S)
        avg = re.search(r'<div class="asmt-avg[^"]*">(.*?)</div>', card, re.S)
        if not name:
            continue
        label = re.sub(r'<[^>]+>', '', name.group(1)).strip()
        label = label.split('. ', 1)[-1]          # drop the "1. " numbering
        figures[label] = (re.sub(r'<[^>]+>', '', avg.group(1)).strip()
                          if avg else None)
    return figures


def family_pages(student, parent, report):
    return [
        ('student report', student.user,
         f'/student/reports/{report.project_id}/'),
        ('student passport', student.user, '/student/reports/annual/'),
        ('student reports list', student.user, '/student/reports/'),
        ('parent report', parent.user,
         f'/parent/child/{student.id}/reports/{report.project_id}/'),
        ('parent passport', parent.user,
         f'/parent/child/{student.id}/passport/'),
        ('parent reports list', parent.user,
         f'/parent/child/{student.id}/reports/'),
    ]


def check_family(student, parent, report, average):
    print('\n3. no mark survives on a page a family can open')

    for label, user, url in family_pages(student, parent, report):
        page = sign_in(user).get(url, follow=True)
        if page.status_code != 200:
            check(f'{label} opens', False, page.status_code)
            continue
        html = page.content.decode('utf-8', 'replace')
        found = marks_in(html)
        check(f'{label}: no mark out of ten anywhere', not found,
              sorted(set(found))[:6])
        left = numbers_in_slots(html)
        check(f'{label}: every score slot holds a letter', not left, left[:6])

    print('\n4. and the grade shown is the right one')
    expected = grade_for(average)
    for label, user, url in [('student', student.user,
                              f'/student/reports/{report.project_id}/'),
                             ('parent', parent.user,
                              f'/parent/child/{student.id}/reports/'
                              f'{report.project_id}/')]:
        html = sign_in(user).get(url, follow=True).content.decode(
            'utf-8', 'replace')
        figures = assessment_figures(html)
        scored = [v for v in figures.values() if v not in (None, '\u2014')]
        check(f'{label}: the scored assessment reads {expected}',
              scored and all(v == expected for v in scored), figures)
        check(f'{label}: unscored assessments stay blank, not D',
              'D' not in [v for v in figures.values()], figures)
        check(f'{label}: the Overall Level card shows a grade',
              heading_value(html, 'stat-value') in ('A+', 'A', 'B', 'C', 'D'),
              heading_value(html, 'stat-value'))


# ------------------------------------------- the pages real children have

def check_real_pages():
    """Sweep what is actually in the database, not only what this suite built.

    The case built above has one scored assessment and no annual passport, so
    its passport page is an empty state -- a page with no numbers on it passes
    "no mark survives" while proving nothing. These are real children with real
    scores behind them, and the KB report in particular is reachable no other
    way.
    """
    print('\n5. the same pages, on children who already have scores')

    from competencies.engine import build_kb_report

    reports = list(ProjectReport.objects
                   .select_related('student__user')
                   .filter(student__user__isnull=False)[:300])
    with_report = []
    seen = set()
    for rep in reports:
        if rep.student_id in seen:
            continue
        seen.add(rep.student_id)
        with_report.append(rep)
        if len(with_report) == 3:
            break
    check('there are real reports to read', bool(with_report),
          len(with_report))

    checked_passport = checked_kb = 0
    for rep in with_report:
        student = rep.student
        client = sign_in(student.user)
        who = student.skill_lab_reg_id or student.user.username

        html = client.get(f'/student/reports/{rep.project_id}/',
                          follow=True).content.decode('utf-8', 'replace')
        found = marks_in(html)
        check(f'{who}: report carries no mark', not found,
              sorted(set(found))[:6])
        left = numbers_in_slots(html)
        check(f'{who}: every score slot on the report holds a letter',
              not left, left[:6])
        check(f'{who}: and it does show grades',
              bool(re.search(r'class="asmt-avg[^"]*">\s*(A\+|A|B|C|D)\s*<',
                             html)) or 'asmt-avg' not in html)

        page = client.get('/student/reports/annual/', follow=True)
        html = page.content.decode('utf-8', 'replace')
        if 'spLevel' in html and 'comp-row' in html:
            checked_passport += 1
            found = marks_in(html)
            check(f'{who}: passport carries no mark', not found,
                  sorted(set(found))[:6])
            left = numbers_in_slots(html)
            check(f'{who}: every score slot on the passport holds a letter',
                  not left, left[:6])

        try:
            has_kb = bool(build_kb_report(student))
        except Exception:
            has_kb = False
        if has_kb:
            checked_kb += 1
            html = client.get('/student/reports/kaushal-bodh/',
                              follow=True).content.decode('utf-8', 'replace')
            found = marks_in(html)
            check(f'{who}: KB report carries no mark', not found,
                  sorted(set(found))[:6])

    # A page that was never reached cannot have been checked. Say so rather
    # than let a quiet zero read as a pass.
    check('at least one real passport was read with data on it',
          checked_passport > 0, checked_passport)

    kb_student = next(
        (s for s in Student.objects.filter(user__isnull=False)[:400]
         if _kb_safe(s)), None)
    if kb_student and checked_kb == 0:
        client = sign_in(kb_student.user)
        html = client.get('/student/reports/kaushal-bodh/',
                          follow=True).content.decode('utf-8', 'replace')
        found = marks_in(html)
        check('the KB report carries no mark', not found,
              sorted(set(found))[:6])
        left = numbers_in_slots(html)
        check('every score slot on the KB report holds a letter',
              not left, left[:6])
        check('and the KB report had something on it',
              'comp-row' in html or 'cr-score' in html)
    else:
        check('a KB report was read', checked_kb > 0 or kb_student is not None,
              checked_kb)


def _kb_safe(student):
    from competencies.engine import build_kb_report
    try:
        return bool(build_kb_report(student))
    except Exception:
        return False


# ------------------------------------------ the templates, not just the pages

# Every template a student or a parent can be shown. The report and passport
# partials are shared by both, which is the point of them.
FAMILY_TEMPLATES = [
    'student/templates/student/_report_body.html',
    'student/templates/student/_passport_body.html',
    'student/templates/student/_kb_body.html',
    'parent/templates/parent/child-reports.html',
]

# `{{ c.score }}`, `{{ g.average }}`, `{{ kb.overall }}` -- anything that puts a
# figure on the page.
FIGURE = re.compile(r'\{\{\s*[\w.]*\b(score|average|overall)\b[^}]*\}\}')


def in_attribute(text, match):
    """Is this figure inside a tag's attribute rather than on the page?

    `data-score` and `data-pct` drive the star rows and the bars; they are not
    printed and a reader never sees them. The raw score does stay in the page
    source that way -- worth knowing, but it is not what the client meant by
    parents seeing the score, and the visuals are built from it.
    """
    before = text[:match.start()]
    return before.rfind('<') > before.rfind('>')


def check_templates():
    """Read the templates as well as the pages they render.

    A page only proves the sections that had data behind them. Common
    Strengths is empty for most children in this database, so putting the mark
    back in that one block changed nothing any page could show -- the sweep
    passed with the leak sitting in the file. The source says what every child
    will see, including the ones whose sections are empty today.
    """
    print('\n6. and the templates they are rendered from')

    for path in FAMILY_TEMPLATES:
        text = io.open(path, encoding='utf-8').read()
        name = path.rsplit('/', 1)[-1]

        bare = [m.group(0) for m in FIGURE.finditer(text)
                if '|grade' not in m.group(0) and not in_attribute(text, m)]
        check(f'{name}: every figure is passed through |grade', not bare,
              bare[:4])

        # The words around the figure give it away as readily as the figure.
        leftovers = [line.strip()[:70]
                     for line in text.split('\n')
                     if ('/10' in line or 'out of 10' in line)
                     and not line.strip().startswith('{#')]
        check(f'{name}: nothing still says out of ten', not leftovers,
              leftovers[:3])

        check(f'{name}: the filter is loaded', 'grading_tags' in text)

    # The coach's screen is the one place the mark belongs.
    coach = io.open('teacher/templates/teacher/score-entry.html',
                    encoding='utf-8').read()
    check('the coach keeps the mark out of ten', '/10' in coach)
    check('and sees the grade beside it', 'gradeFor(' in coach)


def clone(obj, **changes):
    """Copy a row rather than build one.

    Student, Parent and Teacher each carry a dozen required columns that have
    nothing to do with grading -- emergency contacts, enrolment dates, board.
    Filling them in here would be inventing a school record to test a label.
    Copying a real row keeps the shape honest and the suite short.
    """
    obj.pk = None
    obj._state.adding = True
    for field, value in changes.items():
        setattr(obj, field, value)

    # The copy carries the original's unique columns -- registration id, GR
    # number, employee id -- and the insert would collide on whichever one the
    # model happens to have. Clear or re-stamp every one the caller did not
    # set, rather than discovering them one failure at a time.
    for f in obj._meta.fields:
        if not f.unique or f.primary_key or f.name in changes:
            continue
        if f.null:
            setattr(obj, f.name, None)
        elif f.get_internal_type() in ('CharField', 'TextField'):
            setattr(obj, f.name, f'zz-{f.name}-{next(STAMP)}'[:f.max_length or 50])

    obj.save()
    return obj


def build_case():
    """Two schools running the same assessment, each with a scored child."""
    from competencies.models import Competency, Project
    from teacher.models import Teacher

    project = (Project.objects.filter(assessments__isnull=False)
               .distinct().first())
    assert project, 'no project with an assessment to work from'
    assessment = project.assessments.first()
    mappings = list(assessment.competency_mappings.all()[:2])
    if len(mappings) < 2:
        comps = list(Competency.objects.exclude(
            id__in=[m.competency_id for m in mappings])[:2 - len(mappings)])
        assert comps, 'no competencies seeded'
        mappings += [AssessmentCompetency.objects.create(
            assessment=assessment, competency=c, order=90 + i)
            for i, c in enumerate(comps)]

    schools = list(School.objects.all()[:2])
    assert len(schools) >= 2, 'need two schools to prove the separation'

    student_seed = Student.objects.first()
    parent_seed = Parent.objects.first()
    teacher_seed = Teacher.objects.first()
    assert student_seed and parent_seed and teacher_seed,         'need one of each to copy from'

    made = []
    for i, school in enumerate(schools):
        user = U.objects.create_user(
            username=f'zz-grade-stu-{i}', password=PASSWORD,
            role='STUDENT', first_name='Zz', last_name=f'Grade{i}')
        student = clone(
            Student.objects.get(pk=student_seed.pk),
            user=user, school=school, first_name='Zz',
            last_name=f'Grade{i}', student_class=project.grade,
            division='A', is_active=True, roll_number=f'ZZG{i}',
            skill_lab_reg_id=f'ZZ-GRADE-{i}-stu',
            school_email=f'zz-grade-stu-{i}@example.invalid')

        p_user = U.objects.create_user(
            username=f'zz-grade-par-{i}', password=PASSWORD, role='PARENT',
            first_name='Zz', last_name=f'Parent{i}')
        parent = clone(Parent.objects.get(pk=parent_seed.pk),
                       user=p_user, school=school, full_name=f'Zz Parent{i}')
        parent.students.set([student])

        # Two eights, so the average is 8.0 -- an A, and far from any boundary.
        for m in mappings[:2]:
            ScoreEntry.objects.create(
                student=student, assessment_competency=m, score=8)

        report = ProjectReport.objects.create(
            student=student, project=project,
            all_competency_scores=[
                {'competency_id': m.competency_id,
                 'competency_name': m.competency.name, 'score': 8}
                for m in mappings[:2]],
            top_3_profiles=[], top_5_competencies=[], skills_to_work_on=[])
        made.append((school, student, parent, report))

    coach_user = U.objects.create_user(
        username='zz-grade-coach', password=PASSWORD, role='THINKING_COACH',
        first_name='Zz', last_name='Coach')
    clone(Teacher.objects.get(pk=teacher_seed.pk), user=coach_user,
          school=schools[0], full_name='Zz Coach', employee_id='ZZ-GRADE-1',
          official_email='zz-grade-coach@example.invalid')
    return assessment, coach_user, made


def run():
    print('=' * 60)
    print('GRADES')
    print('=' * 60)

    check_bands()

    try:
        with transaction.atomic():
            assessment, coach, made = build_case()
            (school_a, student_a, parent_a, report_a) = made[0]

            check_coach(coach, assessment)
            check_family(student_a, parent_a, report_a, 8.0)
            check_real_pages()
            raise Rollback
    except Rollback:
        pass

    check_templates()

    check('nothing this suite created survived',
          not U.objects.filter(username__startswith='zz-grade-').exists())

    print(f'\n{"=" * 60}\nPASS {len(PASS)}   FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  FAILED: {f}')


if __name__ == '__main__':
    run()
