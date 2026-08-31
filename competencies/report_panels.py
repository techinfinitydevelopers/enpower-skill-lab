"""
The four grade-wise report panels, computed for any set of schools.

Spec: presentation slide 52, "Data Representation Logic for Developer".

  1. Grade-wise student distribution   static, from onboarding data
  2. Monthly grade-wise attendance     changes monthly, from attendance records
  3. Project completion by grade       changes periodically
  4. Top 3 skill profiles by grade     from skill passport data

One module rather than three, because Super Admin (all schools), Program
Coordinator (mapped schools) and School Admin (one school) show the same panels
over different school sets. Every function takes the school queryset or ids so
the caller owns the scoping and cannot accidentally widen it.

Each panel returns bars already sized as percentages of the panel maximum, so a
template can draw the chart without arithmetic.
"""

from collections import Counter, defaultdict
from datetime import date


def _grade_key(g):
    """Sort grades numerically; anything non-numeric goes last."""
    return int(g) if str(g).isdigit() else 99


def _as_bars(counts, value_key='value', suffix=''):
    """Turn {grade: value} into sorted rows carrying a bar height in percent."""
    if not counts:
        return []
    top = max(counts.values()) or 1
    return [
        {
            'grade': g,
            value_key: counts[g],
            'height': int(round(counts[g] / top * 100)),
            'label': f'{counts[g]}{suffix}',
        }
        for g in sorted(counts, key=_grade_key)
    ]


def _insights(counts, noun, unit='', singular=None):
    """The two observations slide 52 shows beside each chart: highest and lowest.

    Nothing is said when every grade sits at the same value — "highest" and
    "lowest" would both be true of any grade and the reader learns nothing.
    """
    if len(counts) < 2 or len(set(counts.values())) == 1:
        return []
    hi = max(counts, key=lambda g: counts[g])
    lo = min(counts, key=lambda g: counts[g])

    def phrase(grade):
        n = counts[grade]
        word = singular if (singular and n == 1) else unit
        return f'{n}{word}'

    return [
        f'Grade {hi} has the highest {noun} ({phrase(hi)})',
        f'Grade {lo} has the lowest {noun} ({phrase(lo)})',
    ]


# ── 1. Grade-wise student distribution ──────────────────────────────────

def student_distribution(school_ids):
    from student.models import Student

    grades = (Student.objects
              .filter(school_id__in=school_ids, is_active=True)
              .exclude(student_class__in=['', None])
              .values_list('student_class', flat=True))
    counts = Counter(str(g).strip() for g in grades)

    return {
        'bars': _as_bars(dict(counts), 'students'),
        'total': sum(counts.values()),
        'insights': _insights(dict(counts), 'enrolment', ' students', ' student'),
    }


# ── 2. Monthly grade-wise attendance ────────────────────────────────────

def attendance_months(school_ids):
    """Months that actually have attendance, newest first, for the selector."""
    from attendance.models import AttendanceSession

    seen = {}
    for d in AttendanceSession.objects.filter(
            school_id__in=school_ids).values_list('date', flat=True):
        if d:
            seen.setdefault(d.strftime('%Y-%m'), d.strftime('%B %Y'))
    return [{'value': k, 'label': v} for k, v in sorted(seen.items(), reverse=True)]


def attendance_by_grade(school_ids, month=None):
    """Average attendance percentage per grade for one month.

    A student marked late was in the room, so late counts as attending.
    Each student contributes one figure per grade, so a grade with one
    heavily-marked student is not dragged by that student's session count.
    """
    from attendance.models import AttendanceRecord

    records = (AttendanceRecord.objects
               .filter(session__school_id__in=school_ids)
               .select_related('session'))
    if month:
        year, mon = month.split('-')
        records = records.filter(session__date__year=int(year),
                                 session__date__month=int(mon))

    per_grade = defaultdict(lambda: {'present': 0, 'total': 0})
    for r in records:
        g = str(r.session.grade).strip()
        per_grade[g]['total'] += 1
        if r.status in ('present', 'late'):
            per_grade[g]['present'] += 1

    percents = {
        g: int(round(v['present'] / v['total'] * 100))
        for g, v in per_grade.items() if v['total']
    }
    marked = sum(v['total'] for v in per_grade.values())
    present = sum(v['present'] for v in per_grade.values())

    return {
        'bars': _as_bars(percents, 'percent', '%'),
        'school_average': int(round(present / marked * 100)) if marked else None,
        'insights': _insights(percents, 'attendance', '%'),
        'records': marked,
    }


# ── 3. Project completion by grade ──────────────────────────────────────

def project_completion(school_ids):
    """Percentage of expected project reports that exist, per grade.

    Expected = students in the grade x projects running for that grade. A
    generated report is the signal that a project is finished for a student,
    which is the same signal the coach's Generate action produces.
    """
    from competencies.models import Project, ProjectReport
    from student.models import Student

    students = list(Student.objects
                    .filter(school_id__in=school_ids, is_active=True)
                    .values_list('id', 'student_class', 'school_id'))
    if not students:
        return {'bars': [], 'overall': None, 'insights': []}

    per_grade_students = Counter(str(g).strip() for _, g, _ in students)

    projects = Counter(
        str(g).strip() for g in Project.objects
        .exclude(project_type='Plug In')
        .filter(status='Active')
        .values_list('grade', flat=True)
    )

    done = Counter(
        str(g).strip() for g in ProjectReport.objects
        .filter(student_id__in=[s[0] for s in students])
        .values_list('student__student_class', flat=True)
    )

    percents, expected_total, done_total = {}, 0, 0
    for grade, n_students in per_grade_students.items():
        expected = n_students * projects.get(grade, 0)
        if not expected:
            continue
        got = min(done.get(grade, 0), expected)
        percents[grade] = int(round(got / expected * 100))
        expected_total += expected
        done_total += got

    return {
        'bars': _as_bars(percents, 'percent', '%'),
        'overall': int(round(done_total / expected_total * 100)) if expected_total else None,
        'insights': _insights(percents, 'completion', '%'),
    }


# ── 4. Top 3 skill profiles by grade ────────────────────────────────────

def top_profiles_by_grade(school_ids, top_n=3):
    """The profiles appearing most often across a grade's reports.

    Ranked by how many students the profile was matched to, then by the total
    strength of those matches — so a profile matched to five students beats one
    matched very strongly to a single student.
    """
    from competencies.models import ProjectReport

    reports = (ProjectReport.objects
               .filter(student__school_id__in=school_ids)
               .exclude(top_3_profiles=[])
               .values_list('student__student_class', 'student_id', 'top_3_profiles'))

    # (grade, profile) -> {students, score}
    tally = defaultdict(lambda: defaultdict(lambda: {'students': set(), 'score': 0.0}))
    for grade, student_id, profiles in reports:
        g = str(grade).strip()
        for p in (profiles or []):
            name = p.get('profile_name')
            if not name:
                continue
            entry = tally[g][name]
            entry['students'].add(student_id)
            entry['score'] += float(p.get('score') or 0)

    rows = []
    for g in sorted(tally, key=_grade_key):
        ranked = sorted(
            tally[g].items(),
            key=lambda kv: (-len(kv[1]['students']), -kv[1]['score'])
        )[:top_n]
        profiles = [
            {'name': name, 'students': len(v['students'])}
            for name, v in ranked
        ]
        rows.append({
            'grade': g,
            'profiles': profiles,
            # Blank cells so a grade with fewer than three profiles still lines
            # up with the rest of the table.
            'pad': range(max(0, top_n - len(profiles))),
        })
    return rows


# ── Everything at once ──────────────────────────────────────────────────

def build(school_ids, month=None, include_profiles=True):
    """All panels for a school set.

    `include_profiles=False` drops the skill-profile panel — the presentation's
    access matrix places Skill Passport outside the Program Coordinator's remit.
    """
    school_ids = list(school_ids)
    months = attendance_months(school_ids)
    if month is None and months:
        month = months[0]['value']

    data = {
        'distribution': student_distribution(school_ids),
        'attendance':   attendance_by_grade(school_ids, month),
        'completion':   project_completion(school_ids),
        'months':       months,
        'month':        month,
        'month_label':  next((m['label'] for m in months if m['value'] == month), None),
        'school_count': len(school_ids),
    }
    data['profiles'] = top_profiles_by_grade(school_ids) if include_profiles else None
    return data
