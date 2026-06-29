"""
Shared read-only helpers that turn Phase-1 raw data (attendance, daily feedback,
student project uploads) + the existing profiling engine into the numbers the
Student / Parent / School-Admin dashboards display (PPT slides 44-53).

Everything here is defensive: missing data returns safe defaults (0 / [] / None),
never raises, so a dashboard never crashes on an empty DB.
"""
from datetime import date

from django.db.models import Count

# Number of projects a student is expected to complete in a year (PPT: "1 of 3").
DEFAULT_PROJECTS_PER_YEAR = 3

# Attendance status values counted as "attended".
ATTENDED = ('present', 'late')


def teacher_default_class(user, on_date=None):
    """Auto-fill source for a teacher's Attendance page (PPT: Timetable -> Attendance link).
    Resolution order: active Timetable (Coordinator) -> assigned Class -> School.trainer_assigned.
    Returns dict(grade, division, school_id, academic_year, program, project_id, source).
    Never raises — missing data returns blank defaults."""
    on_date = on_date or date.today()
    out = {'grade': '', 'division': '', 'school_id': None, 'academic_year': '',
           'program': '', 'project_id': None, 'source': None}

    # 1. Timetable uploaded by the Coordinator for this coach
    try:
        from .models import Timetable
        tt = (Timetable.objects.filter(thinking_coach=user, is_active=True)
              .order_by('-created_at').first())
        if tt:
            out.update(grade=tt.grade, division=tt.division, school_id=tt.school_id,
                       academic_year=tt.academic_year, program=tt.program, source='timetable')
            day_map = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            slot = (tt.slots.filter(day_of_week=day_map[on_date.weekday()])
                    .exclude(project__isnull=True).first())
            if slot and slot.project_id:
                out['project_id'] = slot.project_id
            return out
    except Exception:
        pass

    # 2. Class assigned to this coach
    try:
        from schools.models import Class
        cl = (Class.objects.filter(thinking_coach=user, is_active=True)
              .order_by('-created_at').first())
        if cl:
            out.update(grade=cl.grade, division=cl.division, school_id=cl.school_id,
                       academic_year=cl.academic_year, source='class')
            return out
    except Exception:
        pass

    # 3. Fallback: school where this coach is the assigned trainer (no class detail)
    try:
        from schools.models import School
        sc = School.objects.filter(trainer_assigned=user).first()
        if sc:
            out.update(school_id=sc.id, source='school')
    except Exception:
        pass
    return out


def attendance_badge(percent):
    """PPT slide 45 badges. Returns dict(name, emoji, tagline) or None."""
    if percent is None:
        return None
    if percent >= 99:
        return {'name': 'Legend', 'emoji': '\U0001F947', 'tagline': 'A model of dedication and reliability.'}
    if percent >= 95:
        return {'name': 'Champion', 'emoji': '\U0001F948', 'tagline': 'Consistency is the key to success.'}
    if percent >= 90:
        return {'name': 'Star', 'emoji': '\U0001F949', 'tagline': 'Showing up and staying committed.'}
    return None


def _pct(part, whole):
    return round(part / whole * 100) if whole else 0


def student_attendance_stats(student):
    """Overall + monthly attendance %, current streak, badge for one student."""
    try:
        records = list(student.attendance_records.select_related('session').all())
    except Exception:
        records = []
    total = len(records)
    attended = sum(1 for r in records if r.status in ATTENDED)
    percent = _pct(attended, total)

    today = date.today()
    month_records = [r for r in records if r.session and r.session.date
                     and r.session.date.year == today.year and r.session.date.month == today.month]
    month_total = len(month_records)
    month_attended = sum(1 for r in month_records if r.status in ATTENDED)
    monthly_percent = _pct(month_attended, month_total)

    # current streak = consecutive most-recent sessions attended
    ordered = sorted([r for r in records if r.session and r.session.date],
                     key=lambda r: r.session.date, reverse=True)
    streak = 0
    for r in ordered:
        if r.status in ATTENDED:
            streak += 1
        else:
            break

    return {
        'total_sessions': total,
        'attended': attended,
        'percent': percent,
        'monthly_percent': monthly_percent,
        'current_streak': streak,
        'badge': attendance_badge(percent),
    }


def _class_filter(student):
    return dict(school=student.school, grade=str(student.student_class), division=student.division)


def projects_completed(student):
    """(completed_count, total) of distinct projects completed for the student's class."""
    from .models import DailySessionFeedback
    try:
        completed = (DailySessionFeedback.objects
                     .filter(is_project_completed=True, **_class_filter(student))
                     .values('project').distinct().count())
    except Exception:
        completed = 0
    return completed, DEFAULT_PROJECTS_PER_YEAR


def sessions_completed(student):
    """How many session-feedbacks the TC has logged for the student's class."""
    from .models import DailySessionFeedback
    try:
        return DailySessionFeedback.objects.filter(**_class_filter(student)).count()
    except Exception:
        return 0


def student_project_uploads(student):
    """Project uploads tagged to the student (slide 17) — for 'View Projects'."""
    try:
        qs = student.project_uploads.all()
        if qs.exists():
            return list(qs)
        # fall back to class-level uploads if none tagged individually
        from .models import StudentProjectUpload
        return list(StudentProjectUpload.objects.filter(**_class_filter(student)))
    except Exception:
        return []


def student_top_profiles(student):
    """Latest top-3 profiles from the most recent ProjectReport (engine output)."""
    try:
        report = student.project_reports.order_by('-generated_at').first()
        if report and report.top_3_profiles:
            return report.top_3_profiles
    except Exception:
        pass
    return []


# ---------------- School-admin aggregates (slide 50-53) ----------------

def grade_wise_distribution(school):
    """[{'grade': '6', 'count': n}, ...] active students per grade."""
    from student.models import Student
    try:
        rows = (Student.objects.filter(school=school, is_active=True)
                .values('student_class').annotate(count=Count('id')).order_by('student_class'))
        return [{'grade': r['student_class'], 'count': r['count']} for r in rows if r['student_class']]
    except Exception:
        return []


def grade_wise_attendance(school, year=None, month=None):
    """[{'grade','percent'}] average attendance % per grade (this month by default)."""
    from .models import AttendanceRecord
    today = date.today()
    year = year or today.year
    month = month or today.month
    try:
        recs = (AttendanceRecord.objects
                .filter(session__school=school, session__date__year=year, session__date__month=month)
                .select_related('session'))
        per_grade = {}
        for r in recs:
            g = r.session.grade
            per_grade.setdefault(g, [0, 0])
            per_grade[g][1] += 1
            if r.status in ATTENDED:
                per_grade[g][0] += 1
        return [{'grade': g, 'percent': _pct(a, t)} for g, (a, t) in sorted(per_grade.items())]
    except Exception:
        return []


def grade_wise_project_completion(school):
    """[{'grade','completed','total'}] distinct completed projects per grade."""
    from .models import DailySessionFeedback
    try:
        rows = (DailySessionFeedback.objects
                .filter(school=school, is_project_completed=True)
                .values('grade', 'project').distinct())
        per_grade = {}
        for r in rows:
            per_grade.setdefault(r['grade'], set()).add(r['project'])
        return [{'grade': g, 'completed': len(p), 'total': DEFAULT_PROJECTS_PER_YEAR}
                for g, p in sorted(per_grade.items())]
    except Exception:
        return []


def grade_wise_top_profiles(school):
    """[{'grade', 'profiles': [names...]}] most common top profiles per grade."""
    from student.models import Student
    try:
        out = {}
        students = Student.objects.filter(school=school, is_active=True)
        for s in students:
            g = s.student_class
            for p in student_top_profiles(s):
                name = p.get('name') if isinstance(p, dict) else str(p)
                if not name:
                    continue
                out.setdefault(g, {})
                out[g][name] = out[g].get(name, 0) + 1
        result = []
        for g, counts in sorted(out.items()):
            top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]
            result.append({'grade': g, 'profiles': [t[0] for t in top]})
        return result
    except Exception:
        return []
