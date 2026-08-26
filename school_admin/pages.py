"""
School Admin pages whose sidebar entries were dead links (href="#").

The changes document lists Thinking Coaches ("should be able to see TC profile"),
Class Overview and Class Attendance as not working — none of them had a URL, a
view or a template.

School Admin is view-only per PPT slide 51 (the principal), so every page here
reads; nothing writes.
"""

from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .models import SchoolAdmin
from .views import is_school_admin


def _school_or_redirect(request):
    """The admin's school, or (None, redirect) with a message explaining why."""
    try:
        profile = SchoolAdmin.objects.select_related('school').get(user=request.user)
    except SchoolAdmin.DoesNotExist:
        messages.error(request, 'School admin profile not found.')
        return None, redirect('school_admin_dashboard')
    if not profile.school:
        messages.error(request, 'No school assigned to your account. Please contact the administrator.')
        return None, redirect('school_admin_dashboard')
    return profile.school, None


# ── Thinking Coaches ────────────────────────────────────────────────────

@login_required
@user_passes_test(is_school_admin)
def teacher_list(request):
    """Coaches attached to this school, with the classes each one runs."""
    from schools.models import Class
    from teacher.models import Teacher

    school, bail = _school_or_redirect(request)
    if bail:
        return bail

    coaches = list(
        Teacher.objects.filter(school=school)
        .select_related('user')
        .order_by('full_name')
    )

    # Classes per coach, so the list says what each of them actually teaches
    classes = defaultdict(list)
    for c in Class.objects.filter(school=school, thinking_coach__isnull=False):
        classes[c.thinking_coach_id].append(f'{c.grade}{c.division}')

    rows = []
    for t in coaches:
        assigned = sorted(classes.get(t.user_id, []) + classes.get(t.id, []))
        rows.append({
            'coach': t,
            'classes': assigned,
            'email': t.official_email or (t.user.email if t.user else ''),
        })

    return render(request, 'school_admin/teachers-list.html', {
        'school': school,
        'rows': rows,
        'page_title': 'Thinking Coaches',
    })


@login_required
@user_passes_test(is_school_admin)
def view_teacher(request, teacher_id):
    """Read-only profile of one coach. Scoped to the admin's own school."""
    from schools.models import Class
    from teacher.models import Teacher

    school, bail = _school_or_redirect(request)
    if bail:
        return bail

    # Scoped lookup rather than a filter afterwards, so another school's coach
    # is a 404 instead of a blank page.
    coach = get_object_or_404(
        Teacher.objects.select_related('user', 'school'), id=teacher_id, school=school)

    assigned = Class.objects.filter(school=school).filter(
        thinking_coach__in=[x for x in (coach.user_id, coach.id) if x]
    ).order_by('grade', 'division')

    return render(request, 'school_admin/view-teacher.html', {
        'school': school,
        'coach': coach,
        'classes': assigned,
        'page_title': coach.full_name or 'Thinking Coach',
    })


# ── Classes ─────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_school_admin)
def class_overview(request):
    """One row per class: its coach, how many students, sessions held so far."""
    from attendance.models import AttendanceSession
    from schools.models import Class
    from student.models import Student

    school, bail = _school_or_redirect(request)
    if bail:
        return bail

    classes = list(
        Class.objects.filter(school=school)
        .select_related('thinking_coach')
        .order_by('grade', 'division')
    )

    # Students are stored with their own grade/division rather than a Class FK,
    # so they're counted by that pair.
    head_count = defaultdict(int)
    for grade, division in Student.objects.filter(
            school=school, is_active=True).values_list('student_class', 'division'):
        head_count[(str(grade), str(division))] += 1

    sessions_held = defaultdict(int)
    for grade, division in AttendanceSession.objects.filter(
            school=school, class_status='held').values_list('grade', 'division'):
        sessions_held[(str(grade), str(division))] += 1

    rows = []
    for c in classes:
        key = (str(c.grade), str(c.division))
        rows.append({
            'klass': c,
            'students': head_count.get(key, 0),
            'sessions_held': sessions_held.get(key, 0),
            'coach': c.thinking_coach,
        })

    # Classes a student sits in that have no Class row yet would otherwise be
    # invisible to the principal, so they're listed as unregistered.
    known = {(str(c.grade), str(c.division)) for c in classes}
    orphans = [
        {'grade': g, 'division': d, 'students': n}
        for (g, d), n in sorted(head_count.items()) if (g, d) not in known
    ]

    return render(request, 'school_admin/class-overview.html', {
        'school': school,
        'rows': rows,
        'orphans': orphans,
        'total_students': sum(head_count.values()),
        'page_title': 'Class Overview',
    })


@login_required
@user_passes_test(is_school_admin)
def class_attendance(request):
    """Attendance per class, and the sessions behind it.

    A class-level percentage on its own hides a class where only one session was
    ever marked, so the session count is reported alongside.
    """
    from attendance.models import AttendanceRecord, AttendanceSession

    school, bail = _school_or_redirect(request)
    if bail:
        return bail

    grade = (request.GET.get('grade') or '').strip()
    division = (request.GET.get('division') or '').strip()

    sessions = (AttendanceSession.objects.filter(school=school)
                .select_related('thinking_coach', 'project')
                .order_by('-date', 'session_number'))
    if grade:
        sessions = sessions.filter(grade=grade)
    if division:
        sessions = sessions.filter(division=division)
    sessions = list(sessions)

    records = (AttendanceRecord.objects
               .filter(session__in=sessions)
               .select_related('student', 'session'))

    per_session = defaultdict(lambda: {'present': 0, 'absent': 0, 'late': 0})
    per_class = defaultdict(lambda: {'present': 0, 'total': 0, 'sessions': set()})
    for r in records:
        s = r.session
        per_session[s.id][r.status] = per_session[s.id].get(r.status, 0) + 1
        key = (str(s.grade), str(s.division))
        per_class[key]['total'] += 1
        # 'late' still counts as attending — the student was in the room.
        if r.status in ('present', 'late'):
            per_class[key]['present'] += 1
        per_class[key]['sessions'].add(s.id)

    class_rows = []
    for (g, d), agg in sorted(per_class.items()):
        total = agg['total']
        class_rows.append({
            'grade': g, 'division': d,
            'present': agg['present'], 'total': total,
            'sessions': len(agg['sessions']),
            'percent': int(round(agg['present'] / total * 100)) if total else 0,
        })

    session_rows = []
    for s in sessions:
        counts = per_session.get(s.id, {})
        marked = sum(counts.values())
        present = counts.get('present', 0) + counts.get('late', 0)
        session_rows.append({
            'session': s,
            'present': present,
            'absent': counts.get('absent', 0),
            'late': counts.get('late', 0),
            'marked': marked,
            'percent': int(round(present / marked * 100)) if marked else None,
        })

    grades = sorted(
        {str(s.grade) for s in AttendanceSession.objects.filter(school=school)},
        key=lambda g: int(g) if g.isdigit() else 99)
    divisions = sorted({str(s.division) for s in AttendanceSession.objects.filter(school=school)})

    overall_present = sum(r['present'] for r in class_rows)
    overall_total = sum(r['total'] for r in class_rows)

    return render(request, 'school_admin/class-attendance.html', {
        'school': school,
        'class_rows': class_rows,
        'session_rows': session_rows[:60],
        'session_total': len(session_rows),
        'grades': grades, 'divisions': divisions,
        'grade': grade, 'division': division,
        'overall_percent': int(round(overall_present / overall_total * 100)) if overall_total else None,
        'page_title': 'Class Attendance',
    })
