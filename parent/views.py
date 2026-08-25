from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.utils.timesince import timesince
from .models import Parent
from schools.models import Class
from teacher.models import Teacher
from competencies.models import ScoreEntry, StudentAssessmentFeedback, StudentProjectFeedback, Announcement
from attendance.services import (
    student_attendance_stats,
    projects_completed,
    sessions_completed,
    student_project_uploads,
)
import json


def _coach_for(child):
    """Name of the child's Thinking Coach, or '—'.

    The dashboard only looked this up through a Class row matching the child's
    school + grade + division. Schools that have not had their classes created
    have no such row — on production the child's school has zero Class records
    — so every parent saw "Thinking Coach: —" even though the school has a
    coach assigned. Falls back to the school's coaching staff.
    """
    def _name(user):
        teacher = Teacher.objects.filter(user=user).first()
        if teacher:
            return teacher.full_name
        return user.get_full_name() or user.username

    child_class = Class.objects.filter(
        school=child.school, grade=child.student_class,
        division=child.division, is_active=True,
    ).select_related('thinking_coach').first()
    if child_class and child_class.thinking_coach:
        return _name(child_class.thinking_coach)

    if not child.school:
        return '—'

    # No class row — fall back to a coach at the school. Prefer one who lists
    # this grade; otherwise use the only coach if there is exactly one.
    school_teachers = list(Teacher.objects.filter(school=child.school))
    grade = str(child.student_class)
    for t in school_teachers:
        taught = (t.grades_taught or '')
        if grade and grade in [g.strip() for g in taught.replace(';', ',').split(',')]:
            return t.full_name
    if len(school_teachers) == 1:
        return school_teachers[0].full_name

    return '—'


def _academic_performance(child):
    """(percent, score/10) from the child's generated project reports.

    The dashboard used to show a hardcoded 75% to every parent regardless of
    how their child was actually doing. This averages every competency score
    across all of the child's ProjectReports.

    Returns (0, None) when nothing has been scored yet, so the UI can say so
    instead of inventing a number.
    """
    from competencies.models import ProjectReport

    values = []
    for report in ProjectReport.objects.filter(student=child):
        values += [
            row['score'] for row in (report.all_competency_scores or [])
            if row.get('score') is not None
        ]
    if not values:
        return 0, None

    mean = sum(values) / len(values)
    return int(round(mean * 10)), round(mean, 1)


def _performance_rows(child, limit=6):
    """Per-competency rows for the Academic Performance card.

    The card rendered an empty <div id="performanceContainer"> — no template
    content and no JS ever filled it, so parents saw a heading with nothing
    under it. Uses the latest score per competency across the child's reports.
    """
    from competencies.models import ProjectReport

    latest = {}
    for report in ProjectReport.objects.filter(student=child).select_related('project').order_by(
            'project__sequence_number', 'project_id'):
        for row in (report.all_competency_scores or []):
            if row.get('score') is not None:
                latest[row.get('competency_id')] = row     # later project wins

    rows = []
    for row in sorted(latest.values(), key=lambda r: -r['score'])[:limit]:
        score = row['score']
        if score >= 8:
            badge, css = 'Excellent', 'excellent'
        elif score >= 6:
            badge, css = 'Good', 'good'
        else:
            badge, css = 'Needs attention', 'needs-attention'
        rows.append({
            'name': row.get('competency_name') or row.get('competency_code') or 'Competency',
            'score': score,
            'percent': int(round(score * 10)),
            'badge': badge,
            'badge_class': css,
            'bar_class': '' if score >= 6 else 'orange',
        })
    return rows


def _projects_progress(child):
    """(completed, total) projects for this child.

    Replaces attendance.services.projects_completed, which counted
    DailySessionFeedback rows flagged is_project_completed and compared them
    against a fixed DEFAULT_PROJECTS_PER_YEAR constant. A child could finish a
    project, have a full report generated, and still see "0 of 12".

    Completed = projects with a generated report. Total = projects actually
    available to the child's class, falling back to completed so the label can
    never read "3 of 0".
    """
    from competencies.models import ProjectReport

    completed = ProjectReport.objects.filter(student=child).values('project').distinct().count()
    total = len(_child_projects(child))
    return completed, max(total, completed)


def _sessions_attended(child):
    """How many class sessions the child actually attended.

    Replaces attendance.services.sessions_completed, which counted the coach's
    DailySessionFeedback forms — so real attendance could be marked all month
    and the parent would still be told "0 sessions".
    """
    from attendance.services import ATTENDED

    try:
        return child.attendance_records.filter(status__in=ATTENDED).count()
    except Exception:
        return 0


def _child_projects(child):
    """List of projects for the child's class in the current academic year.

    Source of truth is DailySessionFeedback (links a Project to a specific
    class). Returns latest-first list of dicts: name, description, completed.
    Safe defaults (empty list) when no data.
    """
    projects = []
    try:
        from attendance.models import DailySessionFeedback
        rows = (DailySessionFeedback.objects
                .filter(school=child.school,
                        grade=str(child.student_class),
                        division=child.division)
                .select_related('project')
                .order_by('-date'))
        seen = set()
        for r in rows:
            if not r.project or r.project_id in seen:
                continue
            seen.add(r.project_id)
            projects.append({
                'name': r.project.title,
                'description': (r.session_description or '').strip(),
                'completed': bool(r.is_project_completed),
            })
    except Exception:
        projects = []
    return projects


def is_parent(user):
    """Check if user is a parent"""
    return user.is_authenticated and hasattr(user, 'role') and user.role == 'PARENT'


@login_required
@user_passes_test(is_parent)
def parent_dashboard(request):
    """Parent dashboard view"""
    children_data = []

    try:
        parent = Parent.objects.get(user=request.user)
        children = parent.students.filter(is_active=True)

        for child in children:
            coach_name = _coach_for(child)

            # Build initials for avatar
            names = child.first_name.split()
            initials = (child.first_name[0] + child.last_name[0]).upper() if child.last_name else child.first_name[:2].upper()

            # Build recent activities for this child
            activities = []

            # Score entries
            scores = ScoreEntry.objects.filter(student=child).select_related(
                'assessment_competency__competency',
                'assessment_competency__assessment',
            ).order_by('-updated_at')[:5]
            for s in scores:
                comp_name = s.assessment_competency.competency.name if s.assessment_competency.competency else 'Unknown'
                assess_name = s.assessment_competency.assessment.name if s.assessment_competency.assessment else ''
                activities.append({
                    'type': 'score',
                    'icon': 'assignment_turned_in',
                    'color': 'blue',
                    'title': f'Score Recorded — {comp_name}',
                    'description': f'{assess_name} · Score: {s.score}/10',
                    'time': timesince(s.updated_at) + ' ago',
                    'timestamp': s.updated_at.isoformat(),
                })

            # Assessment feedback
            feedbacks = StudentAssessmentFeedback.objects.filter(student=child).select_related(
                'assessment',
            ).order_by('-updated_at')[:3]
            for f in feedbacks:
                activities.append({
                    'type': 'feedback',
                    'icon': 'comment',
                    'color': 'purple',
                    'title': f'Assessment Feedback',
                    'description': f'{f.assessment.name} — {f.feedback[:80]}' if f.feedback else f.assessment.name,
                    'time': timesince(f.updated_at) + ' ago',
                    'timestamp': f.updated_at.isoformat(),
                })

            # Project feedback
            proj_feedbacks = StudentProjectFeedback.objects.filter(student=child).select_related(
                'project',
            ).order_by('-updated_at')[:3]
            for pf in proj_feedbacks:
                activities.append({
                    'type': 'project_feedback',
                    'icon': 'rate_review',
                    'color': 'orange',
                    'title': f'Project Feedback — {pf.project.title}',
                    'description': pf.feedback[:80] if pf.feedback else 'Feedback received',
                    'time': timesince(pf.updated_at) + ' ago',
                    'timestamp': pf.updated_at.isoformat(),
                })

            # Sort by timestamp desc, limit to 5
            activities.sort(key=lambda x: x['timestamp'], reverse=True)
            activities = activities[:5]

            # --- Real KPI / module data (PPT slides 47, 49) ---
            attendance = student_attendance_stats(child)          # safe defaults built-in
            completed_projects, total_projects = _projects_progress(child)
            sessions_done = _sessions_attended(child)
            projects_list = _child_projects(child)
            academic_percent, academic_score = _academic_performance(child)
            performance_rows = _performance_rows(child)

            # Current module = latest active project name for the child's class.
            current_module = projects_list[0]['name'] if projects_list else '—'
            current_module_desc = projects_list[0]['description'] if projects_list else ''

            children_data.append({
                'id': child.id,
                'name': child.full_name,
                'first_name': child.first_name,
                'grade': f'Grade {child.student_class}',
                'grade_section': f'Grade {child.student_class} - Section {child.division}',
                'school': child.school.school_name if child.school else '—',
                'coach': coach_name,
                'initials': initials,
                'gender': getattr(child, 'gender', 'male'),
                'activities': activities,
                # KPIs (slide 47)
                'monthly_attendance': attendance.get('monthly_percent', 0),
                'attendance_percent': attendance.get('percent', 0),
                'projects_completed': completed_projects,
                'projects_total': total_projects,
                'projects_label': f'{completed_projects} of {total_projects}',
                'projects': projects_list,
                # Real academic performance, replacing a hardcoded 75% in the template
                'academic_percent': academic_percent,
                'academic_score': academic_score,
                'performance': performance_rows,
                # Module / sessions (slide 49)
                'current_module': current_module,
                'current_module_desc': current_module_desc,
                'sessions_completed': sessions_done,
            })
    except Parent.DoesNotExist:
        pass

    # Announcements (slide 48) — scoped to this parent via the shared targeting
    # helper (publish_to 'parent' + program + children's schools + grades).
    events, newsletters, success_stories = [], [], []
    try:
        from competencies.announcements import announcements_for_user
        events = sorted(
            announcements_for_user(request.user, 'event'),
            key=lambda a: (a.event_date is None, a.event_date, a.created_at),
            reverse=True,
        )[:20]
        newsletters = sorted(
            announcements_for_user(request.user, 'newsletter'),
            key=lambda a: a.created_at, reverse=True,
        )[:10]
        success_stories = sorted(
            announcements_for_user(request.user, 'success_story'),
            key=lambda a: a.created_at, reverse=True,
        )[:10]
    except Exception:
        pass

    context = {
        'children': children_data,
        'children_json': json.dumps(children_data),
        'has_children': len(children_data) > 0,
        'events': events,
        'newsletters': newsletters,
        'success_stories': success_stories,
    }
    return render(request, 'parent/dashboard.html', context)


@login_required
@user_passes_test(is_parent)
def parent_profile(request):
    """View for displaying parent profile"""
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        messages.error(request, 'Parent profile not found.')
        return redirect('parent_dashboard')

    context = {
        'parent': parent,
    }
    return render(request, 'parent/profile.html', context)


@login_required
@user_passes_test(is_parent)
def parent_profile_update(request):
    """View for updating parent profile"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Parent profile not found'})

    try:
        # Update profile fields
        parent.full_name = request.POST.get('full_name', parent.full_name)
        parent.mobile_number = request.POST.get('mobile_number', parent.mobile_number)
        parent.alternate_mobile = request.POST.get('alternate_mobile', '') or None
        parent.relation_to_student = request.POST.get('relation_to_student', parent.relation_to_student)
        parent.occupation = request.POST.get('occupation', '') or None
        parent.organization = request.POST.get('organization', '') or None

        # Handle profile photo upload
        if 'profile_photo' in request.FILES:
            parent.profile_photo = request.FILES['profile_photo']

        parent.save()

        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully',
            'reload': True
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@user_passes_test(is_parent)
def parent_change_password(request):
    """Parent change password view"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('parent_change_password')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'parent/change_password.html', {'form': form})


# ---------- Child reports (parents could not open these at all) ----------

def _child_or_404(request, student_id):
    """Fetch one of the requesting parent's own children, or 404.

    Scoping the lookup to `parent.students` is what stops a parent reading
    another family's report by changing the id in the URL.
    """
    parent = get_object_or_404(Parent, user=request.user)
    return get_object_or_404(parent.students, id=student_id)


@login_required
@user_passes_test(is_parent)
def parent_child_reports(request, student_id):
    """List a child's generated project reports, plus a link to the passport."""
    from competencies.models import ProjectReport

    child = _child_or_404(request, student_id)
    reports = (
        ProjectReport.objects.filter(student=child)
        .select_related('project')
        .order_by('project__sequence_number', 'project__title')
    )

    rows = []
    for r in reports:
        values = [c['score'] for c in (r.all_competency_scores or []) if c.get('score') is not None]
        rows.append({
            'project_id': r.project_id,
            'title': r.project.title,
            'category': r.project.project_type,
            'average': round(sum(values) / len(values), 1) if values else None,
            'competency_count': len(values),
            'generated_at': r.generated_at,
        })

    return render(request, 'parent/child-reports.html', {'child': child, 'reports': rows})


@login_required
@user_passes_test(is_parent)
def parent_child_report_detail(request, student_id, project_id):
    """One project report for the parent's child — same content the student sees."""
    from competencies.models import ProjectReport, Profile, StudentAssessmentFeedback
    from competencies.engine import attach_competency_descriptions, get_per_assessment_breakdown

    child = _child_or_404(request, student_id)
    report = get_object_or_404(ProjectReport, student=child, project_id=project_id)

    all_scores = report.all_competency_scores or []
    attach_competency_descriptions(all_scores, report.skills_to_work_on, report.top_5_competencies)

    def label(score):
        if score >= 8: return 'very_strong'
        if score >= 6: return 'strong'
        if score >= 4: return 'emerging'
        return 'skill_to_work_on'

    values = [c['score'] for c in all_scores if c.get('score') is not None]
    profiles = report.top_3_profiles or []
    prof_tags = {}
    prof_ids = [p['profile_id'] for p in profiles if p.get('profile_id')]
    if prof_ids:
        for pr in Profile.objects.filter(id__in=prof_ids).prefetch_related('primary_competencies'):
            prof_tags[pr.id] = [c.name for c in pr.primary_competencies.all()[:3]]
    for p in profiles:
        p['match_percent'] = int(round((p.get('score') or 0) * 10))
        p['tags'] = prof_tags.get(p.get('profile_id'), [])

    return render(request, 'parent/child-report-detail.html', {
        'child': child,
        'student': child,                     # shared passport partials read `student`
        'report': report,
        'very_strong': [c for c in all_scores if label(c['score']) == 'very_strong'],
        'strong':      [c for c in all_scores if label(c['score']) == 'strong'],
        'emerging':    [c for c in all_scores if label(c['score']) == 'emerging'],
        'feedbacks': StudentAssessmentFeedback.objects.filter(
            student=child, assessment__project_id=project_id
        ).select_related('entered_by').order_by('-updated_at'),
        'overall_score': round(sum(values) / len(values), 1) if values else 0,
        'best_match': profiles[0]['match_percent'] if profiles else 0,
        'assessment_breakdown': get_per_assessment_breakdown(child, report.project),
    })


@login_required
@user_passes_test(is_parent)
def parent_child_passport(request, student_id):
    """The child's Annual Skill Passport, as the student sees it."""
    from competencies.engine import (generate_annual_passport, get_annual_kb_scores,
                                     get_top_project, attach_competency_descriptions)
    from competencies.models import Profile
    from student.views import _build_passport_summary
    from django.utils import timezone

    child = _child_or_404(request, student_id)

    context = {
        'child': child, 'student': child, 'has_data': False,
        'top_3_profiles': [], 'top_5_competencies': [], 'skills_to_work_on': [],
        'all_competency_scores': [], 'very_strong': [], 'strong': [], 'emerging': [],
        'work_on': [], 'kb_scores': [], 'top_project': None, 'overall_score': 0,
        'attendance_percent': 0, 'summary_paragraphs': [],
        'academic_year': getattr(child, 'academic_year', '') or '',
        'issued_by': (child.school.school_name if child.school else 'ENpower Skill Lab'),
        'issue_date': timezone.now(),
    }

    try:
        context['attendance_percent'] = student_attendance_stats(child).get('percent') or 0
    except Exception:
        pass
    try:
        context['kb_scores'] = get_annual_kb_scores(child)
    except Exception:
        pass
    try:
        context['top_project'] = get_top_project(child)
    except Exception:
        pass

    try:
        data = generate_annual_passport(child)
    except Exception:
        data = None

    if data:
        all_scores = data.get('all_competency_scores') or []
        attach_competency_descriptions(all_scores, data.get('top_5_competencies'),
                                       data.get('skills_to_work_on'))

        def label(score):
            if score >= 8: return 'very_strong'
            if score >= 6: return 'strong'
            if score >= 4: return 'emerging'
            return 'work_on'

        values = [c['score'] for c in all_scores if c.get('score') is not None]
        overall = round(sum(values) / len(values), 1) if values else 0

        profiles = data.get('top_3_profiles') or []
        prof_tags = {}
        prof_ids = [p['profile_id'] for p in profiles if p.get('profile_id')]
        if prof_ids:
            for pr in Profile.objects.filter(id__in=prof_ids).prefetch_related('primary_competencies'):
                prof_tags[pr.id] = [c.name for c in pr.primary_competencies.all()[:3]]
        for p in profiles:
            p['match_percent'] = int(round((p.get('score') or 0) * 10))
            p['tags'] = prof_tags.get(p.get('profile_id'), [])

        very_strong = [c for c in all_scores if label(c['score']) == 'very_strong']
        strong      = [c for c in all_scores if label(c['score']) == 'strong']

        context.update({
            'has_data': True,
            'top_3_profiles': profiles,
            'top_5_competencies': data.get('top_5_competencies') or [],
            'skills_to_work_on': data.get('skills_to_work_on') or [],
            'all_competency_scores': all_scores,
            'very_strong': very_strong,
            'strong': strong,
            'emerging': [c for c in all_scores if label(c['score']) == 'emerging'],
            'work_on': [c for c in all_scores if label(c['score']) == 'work_on'],
            'overall_score': overall,
            'summary_paragraphs': _build_passport_summary(child, all_scores,
                                                          very_strong + strong, overall),
        })

    return render(request, 'parent/child-passport.html', context)


@login_required
def parent_logout(request):
    """Log the parent out.

    The header logout only did `window.location.href = '/login'`, which left the
    session intact — the user appeared to log out but was still signed in.
    """
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')
