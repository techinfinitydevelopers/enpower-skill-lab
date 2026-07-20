from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json


def is_student(user):
    """Check if user is a student"""
    return user.is_authenticated and hasattr(user, 'role') and user.role == 'STUDENT'


@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    """Student dashboard view (PPT slides 44-46) wired to real data."""
    from attendance.services import (
        student_attendance_stats, projects_completed, sessions_completed,
        student_project_uploads,
    )

    student = getattr(request.user, 'student_profile', None) or getattr(request.user, 'student', None)

    context = {
        'user': request.user,
        'student': student,
    }

    # Total registered students (real count) — always available.
    try:
        from student.models import Student
        context['total_registered_students'] = Student.objects.filter(is_active=True).count()
    except Exception:
        context['total_registered_students'] = 0

    # Published announcements targeted to this student (slide 8 targeting).
    try:
        events = announcements_for_student(student, 'event')
        events.sort(key=lambda a: (a.event_date is None, a.event_date))
        context['events'] = events[:5]
        newsletters = announcements_for_student(student, 'newsletter')
        newsletters.sort(key=lambda a: (a.newsletter_date or a.created_at.date()), reverse=True)
        context['newsletter'] = newsletters[0] if newsletters else None
        stories = announcements_for_student(student, 'success_story')
        stories.sort(key=lambda a: a.created_at, reverse=True)
        context['success_story'] = stories[0] if stories else None
    except Exception:
        context['events'] = []
        context['newsletter'] = None
        context['success_story'] = None

    if student:
        # Header info (slide 44)
        try:
            context['student_id'] = student.gr_number
        except Exception:
            context['student_id'] = None
        try:
            context['school_name'] = student.school.school_name if student.school else None
        except Exception:
            context['school_name'] = None
        try:
            context['program_name'] = student.school.get_skill_program_display() if student.school else None
        except Exception:
            context['program_name'] = None

        # Thinking coach name: school trainer_assigned, fall back to class coach, then assigned_trainer text.
        coach_name = None
        try:
            if student.school and student.school.trainer_assigned:
                coach_name = student.school.trainer_assigned.get_full_name() or student.school.trainer_assigned.username
        except Exception:
            coach_name = None
        if not coach_name:
            try:
                from schools.models import Class
                klass = Class.objects.filter(
                    school=student.school, grade=str(student.student_class), division=student.division
                ).select_related('thinking_coach').first()
                if klass and klass.thinking_coach:
                    coach_name = klass.thinking_coach.get_full_name() or klass.thinking_coach.username
            except Exception:
                coach_name = None
        if not coach_name:
            coach_name = getattr(student, 'assigned_trainer', None)
        context['thinking_coach'] = coach_name

        # Journey + attendance (slide 45)
        completed, total = projects_completed(student)
        context['projects_completed'] = completed
        context['projects_total'] = total
        context['attendance'] = student_attendance_stats(student)

        # Project completion report + uploads (slide 46)
        context['sessions_completed'] = sessions_completed(student)
        context['project_uploads'] = student_project_uploads(student)
    else:
        context['attendance'] = {
            'total_sessions': 0, 'attended': 0, 'percent': 0,
            'monthly_percent': 0, 'monthly_attended': 0, 'monthly_total': 0,
            'current_streak': 0, 'badge': None,
        }
        context['projects_completed'] = 0
        context['projects_total'] = 12
        context['sessions_completed'] = 0
        context['project_uploads'] = []

    # Badges grid (PPT slide 45 text): based on MONTHLY attendance %.
    context['badge_tiers'] = attendance_badge_tiers(context['attendance'].get('monthly_percent') or 0)

    return render(request, 'student/dashboard.html', context)


def attendance_badge_tiers(monthly_percent):
    """Star/Champion/Legend tiers (PPT slide 45), earned by MONTHLY attendance %.
    Cumulative: reaching a higher tier also marks the lower ones earned."""
    tiers = [
        {'name': 'Star',     'emoji': '\U0001F949', 'min': 90, 'max': 94,  'tagline': 'Showing up and staying committed.'},
        {'name': 'Champion', 'emoji': '\U0001F948', 'min': 95, 'max': 98,  'tagline': 'Consistency is the key to success.'},
        {'name': 'Legend',   'emoji': '\U0001F947', 'min': 99, 'max': 100, 'tagline': 'A model of dedication and reliability.'},
    ]
    for t in tiers:
        t['earned'] = monthly_percent >= t['min']
    return tiers


@login_required
@user_passes_test(is_student)
def student_profile(request):
    """Student profile view"""
    context = {
        'user': request.user,
    }
    return render(request, 'student/profile.html', context)


@login_required
@user_passes_test(is_student)
def student_reports(request):
    """Student skill passport reports page"""
    from competencies.models import ProjectReport
    student = getattr(request.user, 'student_profile', None) or getattr(request.user, 'student', None)
    reports = []
    if student:
        reports = ProjectReport.objects.filter(student=student).select_related('project').order_by('-project__sequence_number', '-generated_at')

    return render(request, 'student/reports.html', {'reports': reports})


@login_required
@user_passes_test(is_student)
def student_report_detail(request, project_id):
    from competencies.models import ProjectReport
    from django.shortcuts import get_object_or_404

    student = getattr(request.user, 'student_profile', None) or getattr(request.user, 'student', None)
    if not student:
        messages.error(request, 'Student profile not found.')
        return redirect('student:student_reports')

    report = get_object_or_404(ProjectReport, student=student, project_id=project_id)

    # Categorize competencies by score label
    all_scores = report.all_competency_scores or []

    def get_label(score):
        if score >= 8:   return 'very_strong'
        if score >= 6:   return 'strong'
        if score >= 4:   return 'emerging'
        return 'skill_to_work_on'

    very_strong = [c for c in all_scores if get_label(c['score']) == 'very_strong']
    strong      = [c for c in all_scores if get_label(c['score']) == 'strong']
    emerging    = [c for c in all_scores if get_label(c['score']) == 'emerging']

    # Get teacher feedback
    from competencies.models import StudentAssessmentFeedback
    feedbacks = StudentAssessmentFeedback.objects.filter(
        student=student,
        assessment__project_id=project_id
    ).select_related('entered_by').order_by('-updated_at')

    return render(request, 'student/report-detail.html', {
        'report':      report,
        'very_strong': very_strong,
        'strong':      strong,
        'emerging':    emerging,
        'feedbacks':   feedbacks,
    })


@login_required
@user_passes_test(is_student)
def student_annual_passport(request):
    """Annual Skill Passport — competency-level results for the student.

    Shows top competencies (categorised by score label), skills to work on,
    and the full competency score list. Profiles are shown lightly. No internal
    profile mechanics. Empty-state when no scores exist yet.
    """
    from competencies.engine import generate_annual_passport

    student = getattr(request.user, 'student_profile', None) or getattr(request.user, 'student', None)

    context = {
        'student': student,
        'has_data': False,
        'top_3_profiles': [],
        'top_5_competencies': [],
        'skills_to_work_on': [],
        'all_competency_scores': [],
        'very_strong': [],
        'strong': [],
        'emerging': [],
        'work_on': [],
    }

    data = None
    if student:
        try:
            data = generate_annual_passport(student)
        except Exception:
            import traceback
            traceback.print_exc()
            data = None

    if data:
        all_scores = data.get('all_competency_scores') or []

        def get_label(score):
            if score >= 8:
                return 'very_strong'
            if score >= 6:
                return 'strong'
            if score >= 4:
                return 'emerging'
            return 'work_on'

        context.update({
            'has_data': True,
            'top_3_profiles': data.get('top_3_profiles') or [],
            'top_5_competencies': data.get('top_5_competencies') or [],
            'skills_to_work_on': data.get('skills_to_work_on') or [],
            'all_competency_scores': all_scores,
            'very_strong': [c for c in all_scores if get_label(c['score']) == 'very_strong'],
            'strong': [c for c in all_scores if get_label(c['score']) == 'strong'],
            'emerging': [c for c in all_scores if get_label(c['score']) == 'emerging'],
            'work_on': [c for c in all_scores if get_label(c['score']) == 'work_on'],
        })

    return render(request, 'student/annual-passport.html', context)


def _student(request):
    return getattr(request.user, 'student_profile', None) or getattr(request.user, 'student', None)


def announcements_for_student(student, ann_type=None):
    """Published announcements targeted to this student (PPT slide 8 targeting):
    matches the student's program, applicable schools, applicable grades, and
    (for events) the publish-to audience. Empty targeting fields = 'all'."""
    from competencies.models import Announcement
    qs = Announcement.objects.filter(is_published=True).prefetch_related('applicable_schools')
    if ann_type:
        qs = qs.filter(announcement_type=ann_type)
    if not student:
        return []
    program = getattr(student.school, 'skill_program', None) if student.school else None
    grade = str(student.student_class)
    school_id = student.school_id

    out = []
    for a in qs:
        if a.program and program and a.program != program:
            continue
        sids = list(a.applicable_schools.values_list('id', flat=True))
        if sids and school_id not in sids:
            continue
        grades = [str(g) for g in (a.applicable_grades or [])]
        if grades and grade not in grades:
            continue
        pt = a.publish_to or []
        if pt and 'student' not in pt:
            continue
        out.append(a)
    return out


@login_required
@user_passes_test(is_student)
def student_badges(request):
    """Attendance badges page (PPT slide 45): Star/Champion/Legend by monthly attendance."""
    from attendance.services import student_attendance_stats

    student = _student(request)
    attendance = student_attendance_stats(student) if student else {
        'percent': 0, 'monthly_percent': 0, 'monthly_attended': 0, 'current_streak': 0, 'badge': None,
    }
    monthly = attendance.get('monthly_percent') or 0
    tiers = attendance_badge_tiers(monthly)

    return render(request, 'student/badges.html', {
        'student': student, 'attendance': attendance, 'tiers': tiers, 'monthly_percent': monthly,
    })


@login_required
@user_passes_test(is_student)
def student_event_calendar(request):
    """Events targeted to this student (PPT slide 46: event data from SA dashboard, slide 8)."""
    events = announcements_for_student(_student(request), 'event')
    events.sort(key=lambda a: (a.event_date is None, a.event_date))
    return render(request, 'student/event-calendar.html', {'events': events})


@login_required
@user_passes_test(is_student)
def student_newsletter(request):
    """Newsletters targeted to this student (PPT slide 46 / slide 8)."""
    newsletters = announcements_for_student(_student(request), 'newsletter')
    newsletters.sort(key=lambda a: (a.newsletter_date or a.created_at.date()), reverse=True)
    return render(request, 'student/newsletter.html', {'newsletters': newsletters})


@login_required
@user_passes_test(is_student)
def student_announcements(request):
    """All announcements targeted to this student — events, newsletters, success stories."""
    announcements = announcements_for_student(_student(request))
    announcements.sort(key=lambda a: a.created_at, reverse=True)
    return render(request, 'student/announcements.html', {'announcements': announcements})


@login_required
@user_passes_test(is_student)
@require_POST
def update_profile(request):
    """Update student profile data via AJAX"""
    try:
        data = json.loads(request.body)
        
        # Get student profile - handle both possible related names
        student = None
        if hasattr(request.user, 'student_profile'):
            student = request.user.student_profile
        elif hasattr(request.user, 'student'):
            student = request.user.student

        # Field mapping from JS field names to model field names
        field_mapping = {
            'fullName': None,  # Handle separately - split into first/last name
            'name': None,  # Handle separately
            'email': None,  # Handle separately - update user email
            'phone': 'student_mobile',
            'dob': 'date_of_birth',
            'gender': 'gender',
            'bloodGroup': 'blood_group',
            'address': 'address',
            'fatherName': None,  # Parent info not in student model
            'fatherOccupation': None,
            'fatherPhone': None,
            'motherName': None,
            'motherOccupation': None,
            'motherPhone': None,
            'nationality': 'nationality',
            'religion': None,  # Not in model
            'category': None,  # Not in model
            'previousSchool': 'previous_school',
            'emergencyName': 'emergency_name',
            'emergencyRelation': 'emergency_relationship',
            'emergencyPhone': 'emergency_mobile',
        }

        for key, value in data.items():
            if key == 'email':
                request.user.email = value
                request.user.save()
            elif key in ['fullName', 'name'] and value:
                # Split name into first and last name
                parts = value.strip().split(' ', 1)
                request.user.first_name = parts[0]
                request.user.last_name = parts[1] if len(parts) > 1 else ''
                request.user.save()
                if student:
                    student.first_name = parts[0]
                    student.last_name = parts[1] if len(parts) > 1 else ''
            elif key in field_mapping and field_mapping[key] and student:
                if hasattr(student, field_mapping[key]):
                    setattr(student, field_mapping[key], value)

        if student:
            student.save()
            
        return JsonResponse({'success': True, 'message': 'Profile updated successfully'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@user_passes_test(is_student)
@require_POST
def update_avatar(request):
    """Update student avatar via AJAX"""
    try:
        if 'avatar' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No file provided'}, status=400)

        avatar_file = request.FILES['avatar']
        
        # Get student profile - handle both possible related names
        student = None
        if hasattr(request.user, 'student_profile'):
            student = request.user.student_profile
        elif hasattr(request.user, 'student'):
            student = request.user.student
            
        if not student:
            return JsonResponse({'success': False, 'message': 'Student profile not found'}, status=400)
        
        # Use the correct field name from the model
        student.student_photo = avatar_file
        student.save()

        return JsonResponse({
            'success': True,
            'message': 'Avatar updated successfully',
            'avatar_url': student.student_photo.url
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
