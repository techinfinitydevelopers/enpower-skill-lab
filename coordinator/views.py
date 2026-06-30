from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Count
from schools.models import School, Class
from teacher.models import Teacher
from student.models import Student
from accounts.models import User
from attendance.models import Timetable, TimetableSlot, GRADE_CHOICES, ACADEMIC_YEAR_CHOICES, DAY_CHOICES
from django.utils import timezone
from operator import attrgetter
import json


def _coordinator_schools(request):
    """Return queryset of schools assigned to the requesting SRM (Program Coordinator).
    Prefer ProgramCoordinator.schools_assigned, fall back to School.srm filter."""
    try:
        coordinator = request.user.program_coordinator
        schools = coordinator.schools_assigned.all()
        if schools.exists():
            return schools
    except Exception:
        pass
    return School.objects.filter(srm=request.user)


def is_coordinator(user):
    """Check if user is a program coordinator"""
    return user.is_authenticated and hasattr(user, 'role') and user.role == 'PROGRAM_COORDINATOR'


@login_required
@user_passes_test(is_coordinator)
def coordinator_dashboard(request):
    """Coordinator dashboard view"""
    # Get coordinator profile and assigned schools
    try:
        coordinator = request.user.program_coordinator
        assigned_schools = coordinator.schools_assigned.all()
    except Exception:
        assigned_schools = School.objects.none()

    assigned_school_ids = assigned_schools.values_list('id', flat=True)

    # Dynamic counts
    total_schools = assigned_schools.count()
    total_teachers = Teacher.objects.filter(school_id__in=assigned_school_ids).count()
    total_students = Student.objects.filter(school_id__in=assigned_school_ids).count()

    # Schools with teacher/student/class counts for the table
    schools_with_counts = assigned_schools.annotate(
        teacher_count=Count('teachers', distinct=True),
        student_count=Count('students', distinct=True),
        class_count=Count('classes', distinct=True),
    ).order_by('-created_at')[:5]

    # Add initials for avatar display
    for school in schools_with_counts:
        words = school.school_name.split()
        school.initials = ''.join([w[0].upper() for w in words[:2]]) if words else '??'

    # School-wise summary (same data, add total_count for display)
    school_summary = list(schools_with_counts)
    max_students = 1
    for school in school_summary:
        school.total_count = school.teacher_count + school.student_count + school.class_count
        if school.student_count > max_students:
            max_students = school.student_count

    # Recent Activities — merge recent teachers, students, classes from assigned schools
    recent_teachers = Teacher.objects.filter(school_id__in=assigned_school_ids).order_by('-created_at')[:5]
    recent_students = Student.objects.filter(school_id__in=assigned_school_ids).order_by('-created_at')[:5]
    recent_classes = Class.objects.filter(school_id__in=assigned_school_ids).order_by('-created_at')[:5]

    activities = []
    for t in recent_teachers:
        t.activity_type = 'teacher'
        t.title = f'New Teacher Added'
        t.description = f'{t.full_name} joined as {t.get_designation_display() if hasattr(t, "get_designation_display") else t.designation}'
        t.school_name = t.school.school_name if t.school else '—'
        activities.append(t)

    for s in recent_students:
        s.activity_type = 'student'
        s.title = f'New Student Enrolled'
        s.description = f'{s.first_name} {s.last_name} enrolled in Class {s.student_class or "—"}'
        s.school_name = s.school.school_name if s.school else '—'
        activities.append(s)

    for c in recent_classes:
        c.activity_type = 'class'
        c.title = f'New Class Created'
        c.description = f'{c.class_name} — {c.academic_year}'
        c.school_name = c.school.school_name if c.school else '—'
        activities.append(c)

    activities.sort(key=attrgetter('created_at'), reverse=True)
    recent_activities = activities[:5]

    context = {
        'total_schools': total_schools,
        'total_teachers': total_teachers,
        'total_students': total_students,
        'pending_alerts': 0,
        'assigned_schools': schools_with_counts,
        'school_summary': school_summary,
        'max_students': max_students,
        'recent_activities': recent_activities,
    }
    return render(request, 'coordinator/dashboard.html', context)


@login_required
@user_passes_test(is_coordinator)
def coordinator_profile(request):
    """Coordinator profile view with update functionality"""
    if request.method == 'POST':
        try:
            # Get or create program coordinator profile
            coordinator = request.user.program_coordinator

            # Handle profile photo upload
            if request.FILES.get('profile_photo'):
                coordinator.profile_photo = request.FILES['profile_photo']

            # Update coordinator fields
            full_name = request.POST.get('full_name', '').strip()
            if full_name:
                coordinator.full_name = full_name
                # Also update user's first and last name
                name_parts = full_name.split(' ', 1)
                request.user.first_name = name_parts[0]
                request.user.last_name = name_parts[1] if len(name_parts) > 1 else ''

            # Update phone numbers
            mobile_number = request.POST.get('mobile_number', '').strip()
            if mobile_number:
                coordinator.mobile_number = mobile_number

            alternate_number = request.POST.get('alternate_number', '').strip()
            if alternate_number:
                coordinator.alternate_number = alternate_number
            else:
                coordinator.alternate_number = None

            # Update gender
            gender = request.POST.get('gender', '').strip()
            if gender:
                coordinator.gender = gender

            # Update date of birth
            date_of_birth = request.POST.get('date_of_birth', '').strip()
            if date_of_birth:
                coordinator.date_of_birth = date_of_birth

            # Update email
            email = request.POST.get('email', '').strip()
            if email:
                coordinator.official_email = email
                request.user.email = email

            # Save changes
            coordinator.save()
            request.user.save()

            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('coordinator:coordinator_profile')

        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
            return redirect('coordinator:coordinator_profile')

    return render(request, 'coordinator/profile.html')


@login_required
@user_passes_test(is_coordinator)
def coordinator_change_password(request):
    """Coordinator change password view"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)

            # Update last password change timestamp
            try:
                coordinator = request.user.program_coordinator
                coordinator.last_password_change = timezone.now()
                coordinator.save()
            except:
                pass  # Coordinator profile might not exist

            messages.success(request, 'Your password was successfully updated!')
            return redirect('coordinator:coordinator_profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'coordinator/change_password.html', {'form': form})


@login_required
def coordinator_logout(request):
    """Coordinator logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
@user_passes_test(is_coordinator)
def school_list(request):
    """School list view"""
    # Fetch only schools assigned to the requesting coordinator
    schools = _coordinator_schools(request).order_by('-created_at')

    context = {
        'schools': schools,
    }

    return render(request, 'coordinator/school-list.html', context)


# ============================================================
# TIMETABLE MANAGEMENT (PPT slides 12-13)
# ============================================================
def _day_label(code):
    """Map a day_of_week code (mon/tue/..) to its full name via DAY_CHOICES."""
    return dict(DAY_CHOICES).get(code, code)


def _fmt_time(t):
    """Format a TimeField as HH:MM, blank if None."""
    return t.strftime('%H:%M') if t else ''


@login_required
@user_passes_test(is_coordinator)
def timetable_list(request):
    """List timetables for the SRM's assigned schools, flattened to one row per slot."""
    assigned_schools = _coordinator_schools(request)
    school_ids = assigned_schools.values_list('id', flat=True)
    timetables = (
        Timetable.objects
        .filter(school_id__in=school_ids)
        .select_related('school', 'thinking_coach')
        .prefetch_related('slots')
        .order_by('-created_at')
    )

    rows = []
    for tt in timetables:
        teacher = ''
        if tt.thinking_coach:
            teacher = tt.thinking_coach.get_full_name() or tt.thinking_coach.username
        slots = list(tt.slots.all())
        if slots:
            for slot in slots:
                start = _fmt_time(slot.start_time)
                end = _fmt_time(slot.end_time)
                if start and end:
                    timings = f'{start} – {end}'
                elif start or end:
                    timings = start or end
                else:
                    timings = '—'
                rows.append({
                    'program': tt.program,
                    'grade': tt.grade,
                    'division': tt.division,
                    'day': _day_label(slot.day_of_week),
                    'timings': timings,
                    'start_date': tt.start_date,
                    'teacher': teacher,
                    'tt_id': tt.id,
                    'tt': tt,
                })
        else:
            rows.append({
                'program': tt.program,
                'grade': tt.grade,
                'division': tt.division,
                'day': '—',
                'timings': '—',
                'start_date': tt.start_date,
                'teacher': teacher,
                'tt_id': tt.id,
                'tt': tt,
            })

    context = {
        'rows': rows,
        'total_timetables': timetables.count(),
        'total_schools': assigned_schools.count(),
    }
    return render(request, 'coordinator/timetable-list.html', context)


def _save_slots(request, timetable):
    """Create TimetableSlot rows from posted slot_day/slot_period/slot_start/slot_end/slot_note."""
    days = request.POST.getlist('slot_day')
    periods = request.POST.getlist('slot_period')
    starts = request.POST.getlist('slot_start')
    ends = request.POST.getlist('slot_end')
    slot_notes = request.POST.getlist('slot_note')
    for i, day in enumerate(days):
        if not day:
            continue
        period = periods[i] if i < len(periods) and periods[i] else 1
        TimetableSlot.objects.create(
            timetable=timetable,
            day_of_week=day,
            period_number=period,
            start_time=(starts[i] if i < len(starts) and starts[i] else None),
            end_time=(ends[i] if i < len(ends) and ends[i] else None),
            note=(slot_notes[i] if i < len(slot_notes) else ''),
        )


@login_required
@user_passes_test(is_coordinator)
def timetable_detail(request, pk):
    """Read-only display of a full schedule. Scoped to coordinator's schools."""
    assigned_schools = _coordinator_schools(request)
    school_ids = assigned_schools.values_list('id', flat=True)
    timetable = (
        Timetable.objects
        .filter(id=pk, school_id__in=school_ids)
        .select_related('school', 'thinking_coach')
        .prefetch_related('slots')
        .first()
    )
    if not timetable:
        messages.error(request, 'Timetable not found or not in your assigned schools.')
        return redirect('coordinator:timetable_list')

    slot_rows = []
    for slot in timetable.slots.all():
        start = _fmt_time(slot.start_time)
        end = _fmt_time(slot.end_time)
        if start and end:
            timings = f'{start} – {end}'
        elif start or end:
            timings = start or end
        else:
            timings = '—'
        slot_rows.append({
            'day': _day_label(slot.day_of_week),
            'timings': timings,
            'note': slot.note,
        })

    context = {
        'timetable': timetable,
        'slot_rows': slot_rows,
    }
    return render(request, 'coordinator/timetable-detail.html', context)


@login_required
@user_passes_test(is_coordinator)
def timetable_edit(request, pk):
    """Edit an existing schedule. Reuses the create form (timetable-upload.html) in edit mode."""
    assigned_schools = _coordinator_schools(request)
    school_ids = assigned_schools.values_list('id', flat=True)
    timetable = (
        Timetable.objects
        .filter(id=pk, school_id__in=school_ids)
        .select_related('school', 'thinking_coach')
        .prefetch_related('slots')
        .first()
    )
    if not timetable:
        messages.error(request, 'Timetable not found or not in your assigned schools.')
        return redirect('coordinator:timetable_list')

    thinking_coaches = User.objects.filter(role='THINKING_COACH').order_by('first_name', 'username')

    if request.method == 'POST':
        school_id = request.POST.get('school', '').strip()
        coach_id = request.POST.get('thinking_coach', '').strip()
        grade = request.POST.get('grade', '').strip()
        division = request.POST.get('division', '').strip()
        academic_year = request.POST.get('academic_year', '').strip()
        program = request.POST.get('program', '').strip()
        start_date = request.POST.get('start_date', '').strip() or None
        end_date = request.POST.get('end_date', '').strip() or None
        notes = request.POST.get('notes', '').strip()
        schedule_file = request.FILES.get('schedule_file')

        if not school_id or not grade or not division:
            messages.error(request, 'School, grade and section are required.')
            return redirect('coordinator:timetable_edit', pk=pk)

        school = assigned_schools.filter(id=school_id).first()
        if not school:
            messages.error(request, 'Invalid school selection.')
            return redirect('coordinator:timetable_edit', pk=pk)

        coach = None
        if coach_id:
            coach = thinking_coaches.filter(id=coach_id).first()

        if not program:
            program = school.get_skill_program_display() if school.skill_program else ''

        try:
            timetable.school = school
            timetable.thinking_coach = coach
            timetable.grade = grade
            timetable.division = division
            timetable.academic_year = academic_year or '2025-2026'
            timetable.program = program
            timetable.start_date = start_date
            timetable.end_date = end_date
            if schedule_file:
                timetable.schedule_file = schedule_file
            timetable.notes = notes
            timetable.save()

            # Replace slots
            timetable.slots.all().delete()
            _save_slots(request, timetable)

            messages.success(request, 'Timetable updated successfully!')
            return redirect('coordinator:timetable_list')
        except Exception as e:
            messages.error(request, f'Error updating timetable: {str(e)}')
            return redirect('coordinator:timetable_edit', pk=pk)

    # GET — prefill the create form
    program_choices = [
        ('FSL', 'Future Skills Lab (FSL)'),
        ('CSL plus', 'CSL Plus'),
        ('CSL foundation', 'CSL Foundation'),
    ]
    existing_slots = [
        {
            'day': slot.day_of_week,
            'start': _fmt_time(slot.start_time),
            'end': _fmt_time(slot.end_time),
        }
        for slot in timetable.slots.all()
    ]
    context = {
        'editing': timetable,
        'editing_slots_json': json.dumps(existing_slots),
        'assigned_schools': assigned_schools,
        'thinking_coaches': thinking_coaches,
        'grade_choices': GRADE_CHOICES,
        'academic_year_choices': ACADEMIC_YEAR_CHOICES,
        'day_choices': DAY_CHOICES,
        'program_choices': program_choices,
    }
    return render(request, 'coordinator/timetable-upload.html', context)


@login_required
@user_passes_test(is_coordinator)
def timetable_delete(request, pk):
    """Delete a schedule (POST only). Scoped to coordinator's schools."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('coordinator:timetable_list')

    assigned_schools = _coordinator_schools(request)
    school_ids = assigned_schools.values_list('id', flat=True)
    timetable = Timetable.objects.filter(id=pk, school_id__in=school_ids).first()
    if not timetable:
        messages.error(request, 'Timetable not found or not in your assigned schools.')
        return redirect('coordinator:timetable_list')

    timetable.delete()
    messages.success(request, 'Timetable deleted successfully!')
    return redirect('coordinator:timetable_list')


@login_required
@user_passes_test(is_coordinator)
def timetable_upload(request):
    """Upload a schedule for a school class.
    Flow: select school -> assign thinking coach -> grade + division ->
    academic year -> program -> upload schedule file -> notes."""
    assigned_schools = _coordinator_schools(request)
    thinking_coaches = User.objects.filter(role='THINKING_COACH').order_by('first_name', 'username')

    if request.method == 'POST':
        school_id = request.POST.get('school', '').strip()
        coach_id = request.POST.get('thinking_coach', '').strip()
        grade = request.POST.get('grade', '').strip()
        division = request.POST.get('division', '').strip()
        academic_year = request.POST.get('academic_year', '').strip()
        program = request.POST.get('program', '').strip()
        start_date = request.POST.get('start_date', '').strip() or None
        end_date = request.POST.get('end_date', '').strip() or None
        notes = request.POST.get('notes', '').strip()
        schedule_file = request.FILES.get('schedule_file')

        # Validation
        if not school_id or not grade or not division:
            messages.error(request, 'School, grade and section are required.')
            return redirect('coordinator:timetable_upload')

        # Ensure the selected school belongs to this SRM
        school = assigned_schools.filter(id=school_id).first()
        if not school:
            messages.error(request, 'Invalid school selection.')
            return redirect('coordinator:timetable_upload')

        coach = None
        if coach_id:
            coach = thinking_coaches.filter(id=coach_id).first()

        # Auto-fill program from school's skill program if not provided
        if not program:
            program = school.get_skill_program_display() if school.skill_program else ''

        try:
            timetable = Timetable.objects.create(
                school=school,
                thinking_coach=coach,
                grade=grade,
                division=division,
                academic_year=academic_year or '2025-2026',
                program=program,
                start_date=start_date,
                end_date=end_date,
                schedule_file=schedule_file,
                notes=notes,
                created_by=request.user,
            )

            # Optional structured slot rows (additive nice-to-have)
            _save_slots(request, timetable)

            messages.success(request, 'Timetable uploaded successfully!')
            return redirect('coordinator:timetable_list')
        except Exception as e:
            messages.error(request, f'Error uploading timetable: {str(e)}')
            return redirect('coordinator:timetable_upload')

    program_choices = [
        ('FSL', 'Future Skills Lab (FSL)'),
        ('CSL plus', 'CSL Plus'),
        ('CSL foundation', 'CSL Foundation'),
    ]
    context = {
        'assigned_schools': assigned_schools,
        'thinking_coaches': thinking_coaches,
        'grade_choices': GRADE_CHOICES,
        'academic_year_choices': ACADEMIC_YEAR_CHOICES,
        'day_choices': DAY_CHOICES,
        'program_choices': program_choices,
    }
    return render(request, 'coordinator/timetable-upload.html', context)
