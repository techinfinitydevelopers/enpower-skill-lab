"""Session feedback for the people who have to act on it.

Thinking Coaches fill a Daily Session Feedback form (four 1-5 ratings, session
notes, photos, project-complete flag) and a Weekly one (what went wrong, what
went well, what was new, and whether the lab has a problem). Both were written
and then read by nobody: the coach saw their own last 20 entries, the Django
admin had them, and no other screen in the product mentioned them.

The weekly form is the reason this matters more than it looks. `lab_issue`
plus `lab_issue_detail` is a coach reporting that the lab is broken, and the
Coordinator who runs that school never saw it.

Same shape as the timetable pages: one set of views serving two roles, with
scope and chrome read from the signed-in user rather than the route, so the
two cannot drift apart. A Coordinator sees the schools assigned to them; a
Super Admin sees all of them. Nobody edits here -- the coach owns the record.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render

RATING_FIELDS = (
    ('rating_engagement', 'Engagement'),
    ('rating_delivery_ease', 'Ease of delivery'),
    ('rating_resources', 'Resources'),
    ('rating_time_management', 'Time management'),
)


def can_read_feedback(user):
    """Coordinator or Super Admin. A coach has their own pages already."""
    return (user.is_authenticated
            and getattr(user, 'role', None) in ('PROGRAM_COORDINATOR', 'SUPER_ADMIN'))


def feedback_schools(request):
    """Schools whose feedback this user may read.

    Decided from the signed-in user, never from the URL: the two roles share
    these views, so the path taken must not widen what comes back.
    """
    from schools.models import School

    if getattr(request.user, 'role', None) == 'SUPER_ADMIN':
        return School.objects.all()
    from coordinator.views import _coordinator_schools
    return _coordinator_schools(request)


def _chrome(request):
    """Base template and URL names, per role."""
    if getattr(request.user, 'role', None) == 'SUPER_ADMIN':
        prefix, base = 'superadmin_', 'superadmin/base.html'
        role_label, scope_label = 'Super Admin', 'every school'
    else:
        prefix, base = 'coordinator:', 'coordinator/base.html'
        role_label, scope_label = 'Program Coordinator', 'your assigned schools'
    return {
        'base_template': base,
        'role_label': role_label,
        'scope_label': scope_label,
        'urls': {name: f'{prefix}session_feedback_{name}'
                 for name in ('list', 'daily_detail', 'weekly_detail')},
    }


def _guard(request):
    if not can_read_feedback(request.user):
        raise PermissionDenied('This page is not available to your role')


def _daily_rows(request):
    from attendance.models import DailySessionFeedback

    school_ids = feedback_schools(request).values_list('id', flat=True)
    return (DailySessionFeedback.objects
            .filter(school_id__in=school_ids)
            .select_related('school', 'thinking_coach', 'project')
            .prefetch_related('photos')
            .order_by('-date', '-created_at'))


def _weekly_rows(request):
    from attendance.models import WeeklySessionFeedback

    school_ids = list(feedback_schools(request).values_list('id', flat=True))
    # A weekly row's school is nullable. One with no school is still the work
    # of a coach at one of these schools, so a Super Admin should see it
    # rather than have it vanish; a Coordinator should not, since there is
    # nothing tying it to their schools.
    qs = WeeklySessionFeedback.objects.filter(school_id__in=school_ids)
    if getattr(request.user, 'role', None) == 'SUPER_ADMIN':
        qs = WeeklySessionFeedback.objects.filter(
            Q(school_id__in=school_ids) | Q(school__isnull=True))
    return (qs.select_related('school', 'thinking_coach')
            .order_by('-date_from', '-created_at'))


def _coach_name(user):
    if not user:
        return '—'
    return user.get_full_name() or user.username


def _average(row):
    """Mean of whichever of the four ratings were answered, or None."""
    scores = [getattr(row, field) for field, _ in RATING_FIELDS]
    scores = [s for s in scores if s is not None]
    return round(sum(scores) / len(scores), 1) if scores else None


def session_feedback_list(request):
    """Daily and weekly feedback, in one page with two tabs."""
    _guard(request)

    daily = _daily_rows(request)
    weekly = _weekly_rows(request)

    # Filters. Everything is optional and narrows both tabs where it applies.
    school_id = (request.GET.get('school') or '').strip()
    coach_id = (request.GET.get('coach') or '').strip()
    lab_only = request.GET.get('lab') == '1'

    if school_id.isdigit():
        daily = daily.filter(school_id=int(school_id))
        weekly = weekly.filter(school_id=int(school_id))
    if coach_id.isdigit():
        daily = daily.filter(thinking_coach_id=int(coach_id))
        weekly = weekly.filter(thinking_coach_id=int(coach_id))
    if lab_only:
        weekly = weekly.filter(lab_issue=True)

    daily_rows = [{
        'obj': row,
        'coach': _coach_name(row.thinking_coach),
        'school': row.school.school_name if row.school else '—',
        'average': _average(row),
        'photos': row.photos.count(),
    } for row in daily[:300]]

    weekly_rows = [{
        'obj': row,
        'coach': _coach_name(row.thinking_coach),
        'school': row.school.school_name if row.school else '—',
    } for row in weekly[:300]]

    from accounts.models import User

    context = {
        'daily_rows': daily_rows,
        'weekly_rows': weekly_rows,
        'daily_total': daily.count(),
        'weekly_total': weekly.count(),
        'lab_issue_count': weekly.filter(lab_issue=True).count(),
        'schools': feedback_schools(request).order_by('school_name'),
        'coaches': User.objects.filter(
            role='THINKING_COACH', teacher_profile__isnull=False
        ).order_by('first_name', 'username'),
        'f_school': school_id,
        'f_coach': coach_id,
        'f_lab': lab_only,
        'active_tab': request.GET.get('tab') or 'daily',
        'rating_fields': RATING_FIELDS,
    }
    context.update(_chrome(request))
    return render(request, 'attendance/session-feedback-list.html', context)


def daily_feedback_detail(request, pk):
    """One daily session, with its ratings and photos."""
    _guard(request)

    row = _daily_rows(request).filter(pk=pk).first()
    if not row:
        raise PermissionDenied('That feedback is not available to you')

    context = {
        'row': row,
        'coach': _coach_name(row.thinking_coach),
        'average': _average(row),
        'ratings': [(label, getattr(row, field)) for field, label in RATING_FIELDS],
        'photos': list(row.photos.all()),
    }
    context.update(_chrome(request))
    return render(request, 'attendance/daily-feedback-detail.html', context)


def weekly_feedback_detail(request, pk):
    """One week's write-up, including any lab issue reported."""
    _guard(request)

    row = _weekly_rows(request).filter(pk=pk).first()
    if not row:
        raise PermissionDenied('That feedback is not available to you')

    context = {
        'row': row,
        'coach': _coach_name(row.thinking_coach),
    }
    context.update(_chrome(request))
    return render(request, 'attendance/weekly-feedback-detail.html', context)
