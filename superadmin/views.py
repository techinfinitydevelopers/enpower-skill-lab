from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.db.models import Q
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from schools.models import School
from school_admin.models import SchoolAdmin
from .models import SuperAdmin
from competencies.models import Pillar, SubPillar, Competency, Profile, Project, Assessment, AssessmentCompetency, ESLProduct, Announcement
import json
import secrets
import string

# Helper function to check role
def is_superadmin(user):
    return user.is_authenticated and user.role == "SUPER_ADMIN"


# Test view for previewing toast messages (remove in production)
@login_required
@user_passes_test(is_superadmin)
def test_messages(request):
    """Test view to preview all toast notification types"""
    messages.success(request, 'This is a success message! Your operation completed successfully.')
    messages.error(request, 'This is an error message! Something went wrong.')
    messages.warning(request, 'This is a warning message! Please be careful.')
    messages.info(request, 'This is an info message! Here is some information for you.')
    return redirect('superadmin_dashboard')


@login_required
def superadmin_logout(request):
    """Logout view for super admin"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')  # Redirect to login page


@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    from teacher.models import Teacher
    from student.models import Student
    from parent.models import Parent
    from coordinator.models import ProgramCoordinator
    from lms.models import Lesson
    from schools.models import Class

    # Platform overview stats
    total_schools = School.objects.count()
    active_schools = School.objects.filter(is_active=True).count()
    total_teachers = Teacher.objects.count()
    total_students = Student.objects.count()
    total_parents = Parent.objects.count()
    total_coordinators = ProgramCoordinator.objects.count()
    total_school_admins = SchoolAdmin.objects.count()
    total_lessons = Lesson.objects.count()
    total_classes = Class.objects.count()

    # Active counts
    active_teachers = Teacher.objects.filter(is_active=True).count()
    active_students = Student.objects.filter(is_active=True).count()

    # Recently added schools (5)
    recent_schools = School.objects.order_by('-created_at')[:5]

    # Recent activities — mixed, sorted by created_at, limit 5 total
    from itertools import chain
    from operator import attrgetter

    recent_activity_schools = list(School.objects.order_by('-created_at')[:5])
    recent_activity_teachers = list(Teacher.objects.order_by('-created_at')[:5])
    recent_activity_students = list(Student.objects.order_by('-created_at')[:5])

    # Tag each item with its type for template rendering
    for item in recent_activity_schools:
        item.activity_type = 'school'
    for item in recent_activity_teachers:
        item.activity_type = 'teacher'
    for item in recent_activity_students:
        item.activity_type = 'student'

    all_activities = sorted(
        chain(recent_activity_schools, recent_activity_teachers, recent_activity_students),
        key=attrgetter('created_at'),
        reverse=True
    )[:5]

    context = {
        'total_schools': total_schools,
        'active_schools': active_schools,
        'total_teachers': total_teachers,
        'total_students': total_students,
        'total_parents': total_parents,
        'total_coordinators': total_coordinators,
        'total_school_admins': total_school_admins,
        'total_lessons': total_lessons,
        'total_classes': total_classes,
        'active_teachers': active_teachers,
        'active_students': active_students,
        'recent_schools': recent_schools,
        'recent_activities': all_activities,
    }
    return render(request, 'superadmin/dashboard.html', context)


@login_required
@user_passes_test(is_superadmin)
def bulk_upload_page(request):
    """Bulk Upload / Manage Users page — all roles in one place"""
    from teacher.models import Teacher
    from student.models import Student
    from parent.models import Parent
    from coordinator.models import ProgramCoordinator

    context = {
        'total_school_admins': SchoolAdmin.objects.count(),
        'total_teachers': Teacher.objects.count(),
        'total_students': Student.objects.count(),
        'total_parents': Parent.objects.count(),
        'total_coordinators': ProgramCoordinator.objects.count(),
    }
    return render(request, 'superadmin/bulk-upload.html', context)


@login_required
@user_passes_test(is_superadmin)
def onboard_school(request):
    """
    View to handle school onboarding form.
    Supports both GET (display form) and POST (submit form data).
    """
    if request.method == 'POST':
        try:
            # Get form data
            data = request.POST
            
            # Create school instance
            school = School()
            
            # A. School Basic Information
            from competencies.models import Framework as FW
            fw_name = data.get('frameworkType', 'FSL')
            school.framework_ref = FW.objects.filter(name=fw_name).first()
            school.school_name = data.get('schoolName')
            school.school_code = data.get('schoolCode')
            school.board = data.get('board')
            school.school_type = data.get('schoolType')
            school.medium = data.get('medium')
            school.year_established = data.get('yearEstablished') or None
            school.school_email = data.get('schoolEmail')
            school.school_phone = data.get('schoolPhone')
            school.website = data.get('website') or None
            school.principal_name = data.get('principalName')
            school.principal_phone = data.get('principalPhone')
            school.principal_email = data.get('principalEmail')
            
            # B. School Branch Details
            school.branch_name = data.get('branchName') or None
            school.branch_code = data.get('branchCode') or None
            school.branch_address = data.get('branchAddress')
            school.city = data.get('city')
            school.state = data.get('state')
            school.pincode = data.get('pincode')
            school.num_students = data.get('numStudents') or None
            school.num_teachers = data.get('numTeachers') or None
            school.num_trainers = data.get('numTrainers') or None
            school.grades_available = data.get('gradesAvailable') or None
            school.shift_details = data.get('shiftDetails') or None
            school.branch_coordinator_name = data.get('branchCoordinatorName') or None
            school.branch_coordinator_phone = data.get('branchCoordinatorPhone') or None
            
            # C. Infrastructure & Facility Information
            school.csl_availability = data.get('cslAvailability') or None
            school.csl_rooms_count = data.get('cslRoomsCount') or None
            school.equipment_inventory = data.get('equipmentInventory') or None
            school.computer_lab_details = data.get('computerLabDetails') or None
            school.internet_details = data.get('internetDetails') or None
            school.classroom_count = data.get('classroomCount') or None
            school.sports_facilities = data.get('sportsFacilities') or None
            school.safety_measures = data.get('safetyMeasures') or None
            school.cctv_coverage = data.get('cctvCoverage') or None
            school.fire_safety_status = data.get('fireSafetyStatus') or None
            school.first_aid_availability = data.get('firstAidAvailability') or None
            
            # D. Academic Information
            school.total_students = data.get('totalStudents') or None
            school.class_wise_strength = data.get('classWiseStrength') or None
            school.student_teacher_ratio = data.get('studentTeacherRatio') or None
            school.curriculum_followed = data.get('curriculumFollowed') or None
            school.club_details = data.get('clubDetails') or None
            school.skill_subjects = data.get('skillSubjects') or None
            school.remedial_programs = data.get('remedialPrograms') or None
            
            # E. Skill Program Information
            school.skill_program = data.get('skillProgram') or None
            school.program_academic_year = data.get('programAcademicYear') or None

            # Auto-set framework_ref based on skill_program selection
            sp = school.skill_program
            if sp == 'fsl':
                school.framework_ref = FW.objects.filter(name='FSL').first()
            elif sp in ('csl_plus_pc', 'csl_plus_tc'):
                school.framework_ref = FW.objects.filter(name='CSL+').first() or school.framework_ref
            elif sp in ('csl_foundation_pc', 'csl_foundation'):
                school.framework_ref = FW.objects.filter(name='CSL Foundation').first() or school.framework_ref

            srm_id = data.get('srmId')
            if srm_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                school.srm = User.objects.filter(id=srm_id, role='PROGRAM_COORDINATOR').first()

            trainer_id = data.get('trainerId')
            if trainer_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                school.trainer_assigned = User.objects.filter(id=trainer_id, role='THINKING_COACH').first()

            # Grade-wise students
            grade_students = {}
            for g in range(1, 13):
                val = data.get(f'grade_{g}_students')
                if val and val.strip():
                    try:
                        grade_students[str(g)] = int(val)
                    except ValueError:
                        pass
            school.grade_wise_students = grade_students
            
            # F. Fees & Commercial Information
            school.lab_fees_with_gst = data.get('labFeesWithGst') or None
            school.program_fees_with_gst = data.get('programFeesWithGst') or None
            school.payment_terms = data.get('paymentTerms') or None
            school.tce_sales_spoc_name = data.get('tceSalesSpocName') or None
            school.tce_sales_spoc_contact = data.get('tceSalesSpocContact') or None
            if 'signedAgreement' in request.FILES:
                school.signed_agreement = request.FILES['signedAgreement']
            if 'goLiveCertificate' in request.FILES:
                school.go_live_certificate = request.FILES['goLiveCertificate']
            
            # G. Compliance & Documentation - Handle file uploads
            if 'schoolLogo' in request.FILES:
                school.school_logo = request.FILES['schoolLogo']
            if 'affiliationLetter' in request.FILES:
                school.affiliation_letter = request.FILES['affiliationLetter']
            if 'fireSafetyCert' in request.FILES:
                school.fire_safety_cert = request.FILES['fireSafetyCert']
            if 'registrationCert' in request.FILES:
                school.registration_cert = request.FILES['registrationCert']
            if 'trustRegistration' in request.FILES:
                school.trust_registration = request.FILES['trustRegistration']
            if 'childSafetyPolicy' in request.FILES:
                school.child_safety_policy = request.FILES['childSafetyPolicy']
            if 'insuranceDocs' in request.FILES:
                school.insurance_docs = request.FILES['insuranceDocs']
            
            school.lab_safety_compliance = data.get('labSafetyCompliance') or None
            school.teacher_police_verification = data.get('teacherPoliceVerification') or None
            
            # H. Emergency Information
            school.emergency_contact_person = data.get('emergencyContactPerson')
            school.emergency_phone = data.get('emergencyPhone')
            school.nearest_hospital = data.get('nearestHospital') or None
            school.evacuation_plan = data.get('evacuationPlan') or None
            
            # I. Additional Information
            school.exceptions_for_school = data.get('exceptionsForSchool') or None
            school.notable_alumni = data.get('notableAlumni') or None

            # Events & Workshop Calendar (JSON)
            events_json = data.get('eventsWorkshopCalendar', '[]')
            try:
                school.events_workshop_calendar = json.loads(events_json) if events_json else []
            except (json.JSONDecodeError, TypeError):
                school.events_workshop_calendar = []
            
            # Mark onboarding as completed
            school.onboarding_completed = True
            
            # Save the school
            school.save()
            
            messages.success(request, f'School "{school.school_name}" has been successfully onboarded!')
            return redirect('superadmin_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error onboarding school: {str(e)}')
            from coordinator.models import ProgramCoordinator
            from teacher.models import Teacher
            return render(request, 'superadmin/onboard-school.html', {
                'frameworks': FW.objects.order_by('order').all(),
                'program_coordinators': ProgramCoordinator.objects.filter(is_active=True).select_related('user'),
                'thinking_coaches': Teacher.objects.filter(is_active=True).select_related('user'),
                'grade_list': list(range(1, 13)),
            })
    
    # GET request - display the form
    from competencies.models import Framework as FW
    from coordinator.models import ProgramCoordinator
    from teacher.models import Teacher
    return render(request, 'superadmin/onboard-school.html', {
        'frameworks': FW.objects.order_by('order').all(),
        'program_coordinators': ProgramCoordinator.objects.filter(is_active=True).select_related('user'),
        'thinking_coaches': Teacher.objects.filter(is_active=True).select_related('user'),
        'grade_list': list(range(1, 13)),
    })


@login_required
@user_passes_test(is_superadmin)
def school_list(request):
    """
    View to display list of all schools.
    """
    schools = School.objects.all().order_by('-created_at')
    
    # Add helper properties for each school
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']
    for school in schools:
        # Get initials from school name
        words = school.school_name.strip().split()
        if len(words) >= 2:
            school.initials = (words[0][0] + words[1][0]).upper()
        else:
            school.initials = school.school_name[:2].upper()
        
        # Assign badge color based on first character
        school.badge_color = colors[ord(school.school_name[0]) % len(colors)]
    
    context = {
        'schools': schools,
        'total_schools': schools.count(),
        'active_schools': schools.filter(is_active=True).count(),
    }
    return render(request, 'superadmin/school-list.html', context)


@login_required
@user_passes_test(is_superadmin)
def view_school(request, school_id):
    """
    View to display school details.
    """
    school = get_object_or_404(School, id=school_id)

    # Get initials and badge color
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']
    words = school.school_name.strip().split()
    if len(words) >= 2:
        school.initials = (words[0][0] + words[1][0]).upper()
    else:
        school.initials = school.school_name[:2].upper()
    school.badge_color = colors[ord(school.school_name[0]) % len(colors)]

    # SRM and Trainer display names
    srm_name = None
    if school.srm:
        from coordinator.models import ProgramCoordinator
        try:
            srm_name = ProgramCoordinator.objects.get(user=school.srm).full_name
        except ProgramCoordinator.DoesNotExist:
            srm_name = school.srm.get_full_name() or school.srm.username

    trainer_name = None
    if school.trainer_assigned:
        from teacher.models import Teacher
        try:
            trainer_name = Teacher.objects.get(user=school.trainer_assigned).full_name
        except Teacher.DoesNotExist:
            trainer_name = school.trainer_assigned.get_full_name() or school.trainer_assigned.username

    context = {
        'school': school,
        'srm_name': srm_name,
        'trainer_name': trainer_name,
    }
    return render(request, 'superadmin/view-school.html', context)


@login_required
@user_passes_test(is_superadmin)
def edit_school(request, school_id):
    """
    View to edit school details.
    """
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        try:
            data = request.POST

            # Update basic info
            school.school_name = data.get('school_name', school.school_name)
            school.school_code = data.get('school_code', school.school_code)
            school.board = data.get('board', school.board)
            school.school_type = data.get('school_type', school.school_type)
            school.medium = data.get('medium', school.medium)
            school.school_email = data.get('school_email', school.school_email)
            school.school_phone = data.get('school_phone', school.school_phone)
            school.website = data.get('website', school.website) or None
            school.principal_name = data.get('principal_name', school.principal_name)
            school.principal_phone = data.get('principal_phone', school.principal_phone)
            school.principal_email = data.get('principal_email', school.principal_email)

            # Update address
            school.city = data.get('city', school.city)
            school.state = data.get('state', school.state)
            school.pincode = data.get('pincode', school.pincode)
            school.branch_address = data.get('branch_address', school.branch_address)

            # Update status
            is_active = data.get('is_active', 'true')
            school.is_active = is_active == 'true'

            # E. Skill Program
            school.skill_program = data.get('skill_program') or None
            school.program_academic_year = data.get('program_academic_year') or None

            # Auto-set framework_ref from skill_program
            from competencies.models import Framework as FW
            sp = school.skill_program
            if sp == 'fsl':
                school.framework_ref = FW.objects.filter(name='FSL').first()
            elif sp in ('csl_plus_pc', 'csl_plus_tc'):
                school.framework_ref = FW.objects.filter(name='CSL+').first() or school.framework_ref
            elif sp in ('csl_foundation_pc', 'csl_foundation'):
                school.framework_ref = FW.objects.filter(name='CSL Foundation').first() or school.framework_ref

            srm_id = data.get('srm_id')
            if srm_id:
                User = get_user_model()
                school.srm = User.objects.filter(id=srm_id, role='PROGRAM_COORDINATOR').first()
            elif srm_id == '':
                school.srm = None

            trainer_id = data.get('trainer_id')
            if trainer_id:
                User = get_user_model()
                school.trainer_assigned = User.objects.filter(id=trainer_id, role='THINKING_COACH').first()
            elif trainer_id == '':
                school.trainer_assigned = None

            # Grade-wise students
            grade_students = {}
            for g in range(1, 13):
                val = data.get(f'grade_{g}_students')
                if val and val.strip():
                    try:
                        grade_students[str(g)] = int(val)
                    except ValueError:
                        pass
            school.grade_wise_students = grade_students

            # F. Fees & Commercial
            school.lab_fees_with_gst = data.get('lab_fees_with_gst') or None
            school.program_fees_with_gst = data.get('program_fees_with_gst') or None
            school.payment_terms = data.get('payment_terms') or None
            school.tce_sales_spoc_name = data.get('tce_sales_spoc_name') or None
            school.tce_sales_spoc_contact = data.get('tce_sales_spoc_contact') or None
            if 'signed_agreement' in request.FILES:
                school.signed_agreement = request.FILES['signed_agreement']
            if 'go_live_certificate' in request.FILES:
                school.go_live_certificate = request.FILES['go_live_certificate']

            # I. Additional Information
            school.exceptions_for_school = data.get('exceptions_for_school') or None
            school.notable_alumni = data.get('notable_alumni') or None

            events_json = data.get('events_workshop_calendar', '[]')
            try:
                school.events_workshop_calendar = json.loads(events_json) if events_json else []
            except (json.JSONDecodeError, TypeError):
                school.events_workshop_calendar = []

            school.save()
            messages.success(request, f'School "{school.school_name}" updated successfully!')
            return redirect('school_list')
        except Exception as e:
            messages.error(request, f'Error updating school: {str(e)}')

    from coordinator.models import ProgramCoordinator
    from teacher.models import Teacher

    context = {
        'school': school,
        'program_coordinators': ProgramCoordinator.objects.filter(is_active=True).select_related('user'),
        'thinking_coaches': Teacher.objects.filter(is_active=True).select_related('user'),
        'grade_list': list(range(1, 13)),
        'grade_wise_students_json': json.dumps(school.grade_wise_students or {}),
        'events_json': json.dumps(school.events_workshop_calendar or []),
    }
    return render(request, 'superadmin/edit-school.html', context)


@login_required
@user_passes_test(is_superadmin)
def delete_school(request, school_id):
    """
    View to delete a school.
    """
    school = get_object_or_404(School, id=school_id)
    school_name = school.school_name
    
    try:
        school.delete()
        messages.success(request, f'School "{school_name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting school: {str(e)}')
    
    return redirect('school_list')


@login_required
@user_passes_test(is_superadmin)
def search_schools(request):
    """
    AJAX endpoint to search schools by name, code, or city.
    Returns JSON response with matching schools and their assignment status.
    """
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'schools': []})

    # Search schools by name, code, or city
    schools = School.objects.filter(
        Q(school_name__icontains=query) |
        Q(school_code__icontains=query) |
        Q(city__icontains=query)
    ).values('id', 'school_name', 'school_code', 'city', 'state')[:10]  # Limit to 10 results

    # Convert to list and add assignment status
    schools_list = list(schools)
    for school in schools_list:
        # Check if this school already has an admin assigned
        has_admin = SchoolAdmin.objects.filter(school_id=school['id'], is_active=True).exists()
        school['has_admin'] = has_admin

    return JsonResponse({'schools': schools_list})


@login_required
@user_passes_test(is_superadmin)
def school_admin_list(request):
    """
    View to display list of all school admins.
    """
    school_admins = SchoolAdmin.objects.select_related('school').all().order_by('-created_at')

    # Add helper properties for each admin
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']
    for admin in school_admins:
        # Get initials from admin name
        words = admin.full_name.strip().split()
        if len(words) >= 2:
            admin.initials = (words[0][0] + words[1][0]).upper()
        else:
            admin.initials = admin.full_name[:2].upper()

        # Assign badge color based on first character
        admin.badge_color = colors[ord(admin.full_name[0]) % len(colors)]
        
        # Check if profile photo file actually exists
        admin.has_photo = bool(admin.profile_photo and admin.profile_photo.name)

    context = {
        'school_admins': school_admins,
        'total_admins': school_admins.count(),
        'active_admins': school_admins.filter(account_status='active').count(),
        'pending_admins': school_admins.filter(account_status='pending').count(),
    }
    return render(request, 'superadmin/school-admin-list.html', context)


@login_required
@user_passes_test(is_superadmin)
def view_school_admin(request, admin_id):
    """
    View to display school admin details.
    """
    admin = get_object_or_404(SchoolAdmin, id=admin_id)
    
    # Get initials and badge color
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']
    words = admin.full_name.strip().split()
    if len(words) >= 2:
        admin.initials = (words[0][0] + words[1][0]).upper()
    else:
        admin.initials = admin.full_name[:2].upper()
    admin.badge_color = colors[ord(admin.full_name[0]) % len(colors)]
    admin.has_photo = bool(admin.profile_photo and admin.profile_photo.name)
    
    context = {
        'admin': admin,
    }
    return render(request, 'superadmin/view-school-admin.html', context)


@login_required
@user_passes_test(is_superadmin)
def edit_school_admin(request, admin_id):
    """
    View to edit school admin details.
    """
    admin = get_object_or_404(SchoolAdmin, id=admin_id)
    schools = School.objects.all().order_by('school_name')
    
    if request.method == 'POST':
        try:
            data = request.POST
            
            # Update basic info
            admin.full_name = data.get('full_name', admin.full_name)
            admin.email = data.get('email', admin.email)
            admin.phone = data.get('phone', admin.phone)
            admin.gender = data.get('gender', admin.gender)
            
            # Update school assignment
            school_id = data.get('school')
            if school_id:
                admin.school_id = school_id
            
            # Update status
            admin.account_status = data.get('account_status', admin.account_status)
            is_active = data.get('is_active', 'true')
            admin.is_active = is_active == 'true'
            
            admin.save()
            messages.success(request, f'School Admin "{admin.full_name}" updated successfully!')
            return redirect('school_admin_list')
        except Exception as e:
            messages.error(request, f'Error updating school admin: {str(e)}')
    
    context = {
        'admin': admin,
        'schools': schools,
    }
    return render(request, 'superadmin/edit-school-admin.html', context)


@login_required
@user_passes_test(is_superadmin)
def delete_school_admin(request, admin_id):
    """
    View to delete a school admin.
    """
    admin = get_object_or_404(SchoolAdmin, id=admin_id)
    admin_name = admin.full_name
    
    try:
        # Also delete associated user if exists
        if admin.user:
            admin.user.delete()
        admin.delete()
        messages.success(request, f'School Admin "{admin_name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting school admin: {str(e)}')
    
    return redirect('school_admin_list')


@login_required
@user_passes_test(is_superadmin)
def onboard_school_admin(request):
    """
    View to handle school admin onboarding form.
    Supports both GET (display form) and POST (submit form data).
    """
    User = get_user_model()

    if request.method == 'POST':
        try:
            # Get form data
            data = request.POST

            # Check if school already has an admin
            school_id = data.get('school')
            existing_admin = SchoolAdmin.objects.filter(school_id=school_id, is_active=True).first()

            if existing_admin:
                school = School.objects.get(id=school_id)
                messages.error(
                    request,
                    f'This school "{school.school_name}" already has an assigned School Admin: {existing_admin.full_name} ({existing_admin.email}). Each school can only have one School Admin.'
                )
                schools = School.objects.all().order_by('school_name')
                return render(request, 'superadmin/onboard-school-admin.html', {'schools': schools})

            # Generate temporary password
            def generate_temp_password(length=12):
                """Generate a secure random password"""
                characters = string.ascii_letters + string.digits + "!@#$%"
                return ''.join(secrets.choice(characters) for _ in range(length))

            temp_password = generate_temp_password()

            # Create User account
            user = User.objects.create(
                username=data.get('email'),  # Use email as username
                email=data.get('email'),
                first_name=data.get('fullName').split()[0] if data.get('fullName') else '',
                last_name=' '.join(data.get('fullName').split()[1:]) if len(data.get('fullName', '').split()) > 1 else '',
                role='SCHOOL_ADMIN',
                is_active=True,
                password=make_password(temp_password)  # Hash the password
            )

            # Create SchoolAdmin profile
            school_admin = SchoolAdmin.objects.create(
                user=user,
                full_name=data.get('fullName'),
                email=data.get('email'),
                phone=data.get('phone'),
                gender=data.get('gender'),
                date_of_birth=data.get('dateOfBirth') if data.get('dateOfBirth') else None,
                address=data.get('address') if data.get('address') else None,
                city=data.get('city') if data.get('city') else None,
                state=data.get('state') if data.get('state') else None,
                pincode=data.get('pincode') if data.get('pincode') else None,
                school_id=data.get('school'),
                account_status='pending',
                is_active=True,
                temporary_password=make_password(temp_password),  # Store hashed temp password
                password_changed=False,
                created_by=request.user
            )

            # Print confirmation to terminal
            print("\n" + "="*80)
            print("✅ SCHOOL ADMIN CREATED SUCCESSFULLY")
            print("="*80)
            print(f"School Admin ID: {school_admin.id}")
            print(f"User ID: {user.id}")
            print(f"Full Name: {school_admin.full_name}")
            print(f"Email: {school_admin.email}")
            print(f"Username: {user.username}")
            print(f"Temporary Password: {temp_password}")
            print(f"School ID: {school_admin.school_id}")
            print(f"Account Status: {school_admin.account_status}")
            print("="*80 + "\n")

            # Handle profile photo upload
            if 'profilePhoto' in request.FILES:
                school_admin.profile_photo = request.FILES['profilePhoto']
                school_admin.save()

            # Send email with credentials
            try:
                school = School.objects.get(id=data.get('school'))
                email_subject = 'Welcome to Enpower Skill Lab - Your Admin Account'
                email_body = f"""
Dear {school_admin.full_name},

You have been registered as a School Administrator for {school.school_name}.

Your Login Credentials:
- Username: {user.email}
- Temporary Password: {temp_password}
- Login URL: {request.build_absolute_uri('/')[:-1]}/login/

IMPORTANT: Please change your password immediately after your first login for security reasons.

If you have any questions, please contact support.

Best regards,
Enpower Skill Lab Team
                """

                send_mail(
                    email_subject,
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [school_admin.email],
                    fail_silently=False,
                )

                messages.success(request, f'School Admin "{school_admin.full_name}" has been successfully onboarded! Credentials sent to {school_admin.email}.')
            except Exception as email_error:
                messages.warning(request, f'School Admin created but email failed to send: {str(email_error)}. Temporary password: {temp_password}')

            return redirect('superadmin_dashboard')

        except Exception as e:
            messages.error(request, f'Error onboarding school admin: {str(e)}')
            return render(request, 'superadmin/onboard-school-admin.html', {'schools': School.objects.all()})

    # GET request - display the form with list of schools
    schools = School.objects.all().order_by('school_name')
    context = {
        'schools': schools,
    }
    return render(request, 'superadmin/onboard-school-admin.html', context)


@login_required
@user_passes_test(is_superadmin)
def profile(request):
    """
    View to display the super admin profile page.
    """
    # Get or create SuperAdmin profile for the current user
    try:
        profile = SuperAdmin.objects.get(user=request.user)
    except SuperAdmin.DoesNotExist:
        profile = None

    context = {
        'profile': profile,
        'user': request.user,
    }
    return render(request, 'superadmin/profile.html', context)


@login_required
@user_passes_test(is_superadmin)
def profile_update(request):
    """
    View to handle super admin profile updates.
    """
    if request.method == 'POST':
        try:
            # Get or create SuperAdmin profile for the current user
            profile, created = SuperAdmin.objects.get_or_create(
                user=request.user,
                defaults={
                    'email': request.user.email,
                    'full_name': request.user.get_full_name() or request.user.username,
                    'phone': '',
                }
            )

            # Update profile fields from form data
            profile.full_name = request.POST.get('full_name', profile.full_name)
            profile.email = request.POST.get('email', profile.email)
            profile.phone = request.POST.get('phone', profile.phone)
            profile.alternate_phone = request.POST.get('alternate_phone', '')
            profile.gender = request.POST.get('gender', '')

            # Handle date of birth
            date_of_birth = request.POST.get('date_of_birth', '')
            if date_of_birth:
                profile.date_of_birth = date_of_birth

            # Handle profile photo upload
            if 'profile_photo' in request.FILES:
                profile.profile_photo = request.FILES['profile_photo']

            # Update last login time
            profile.last_login = timezone.now()

            # Save the profile
            profile.save()

            # Also update the User model
            request.user.email = profile.email
            if profile.full_name:
                name_parts = profile.full_name.split(maxsplit=1)
                request.user.first_name = name_parts[0]
                request.user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            request.user.save()

            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('superadmin_profile')

        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
            return redirect('superadmin_profile')

    # If not POST, redirect to profile page
    return redirect('superadmin_profile')


@login_required
@user_passes_test(is_superadmin)
def change_password(request):
    """
    View to handle password change for super admin.
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validate current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('superadmin_change_password')
        
        # Validate new password
        if not new_password:
            messages.error(request, 'New password is required.')
            return redirect('superadmin_change_password')
        
        # Check password requirements
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return redirect('superadmin_change_password')
        
        # Validate confirm password
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('superadmin_change_password')
        
        # Check if new password is same as current
        if current_password == new_password:
            messages.error(request, 'New password must be different from current password.')
            return redirect('superadmin_change_password')
        
        try:
            # Update password
            request.user.set_password(new_password)
            request.user.save()
            
            # Update last_password_change in SuperAdmin profile
            try:
                profile = SuperAdmin.objects.get(user=request.user)
                profile.last_password_change = timezone.now()
                profile.save()
            except SuperAdmin.DoesNotExist:
                pass
            
            # Send email notification
            try:
                send_mail(
                    subject='Password Changed - ENpower Skill Lab',
                    message=f'''Hello {request.user.get_full_name() or request.user.username},

Your password for ENpower Skill Lab Super Admin account has been changed successfully.

If you did not make this change, please contact the administrator immediately.

Date & Time: {timezone.now().strftime("%B %d, %Y at %I:%M %p")}

Best regards,
ENpower Skill Lab Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.user.email],
                    fail_silently=True,
                )
            except Exception as email_error:
                # Log email error but don't fail the password change
                print(f"Email notification failed: {email_error}")
            
            messages.success(request, 'Your password has been changed successfully. A confirmation email has been sent to your registered email address.')
            
            # Re-authenticate user to prevent logout
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            return redirect('superadmin_change_password')
            
        except Exception as e:
            messages.error(request, f'Error changing password: {str(e)}')
            return redirect('superadmin_change_password')
    
    # GET request - render the change password page
    return render(request, 'superadmin/change-password.html')


# Student Onboarding Views
@login_required
@user_passes_test(is_superadmin)
def onboard_student(request):
    """View for onboarding new students"""
    if request.method == 'POST':
        try:
            from student.models import Student
            import uuid
            from datetime import date
            import secrets
            import string
            # Generate unique skill lab registration ID
            year = date.today().year
            random_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            skill_lab_reg_id = f"SKILL{year}{random_str}"

            # Create student instance
            student = Student()

            # School Assignment
            school_id = request.POST.get('school', '')
            if school_id:
                from schools.models import School
                student.school = School.objects.get(id=school_id)

            # A. Basic Information
            if 'student_photo' in request.FILES:
                student.student_photo = request.FILES['student_photo']
            student.first_name = request.POST.get('first_name', '')
            student.middle_name = request.POST.get('middle_name', '')
            student.last_name = request.POST.get('last_name', '')
            student.gender = request.POST.get('gender', '')
            student.date_of_birth = request.POST.get('date_of_birth', '')
            student.nationality = request.POST.get('nationality', 'Indian')
            student.mother_tongue = request.POST.get('mother_tongue', '')
            student.blood_group = request.POST.get('blood_group', '')
            student.aadhar_number = request.POST.get('aadhar_number', '')

            # B. Academic Details
            student.school_name = request.POST.get('school_name', '')
            student.school_branch = request.POST.get('school_branch', '')
            student.student_class = request.POST.get('student_class', '')
            student.division = request.POST.get('division', '')
            student.roll_number = request.POST.get('roll_number', '')
            student.academic_year = request.POST.get('academic_year', '')
            student.gr_number = request.POST.get('gr_number', '')
            student.previous_school = request.POST.get('previous_school', '')
            student.stream = request.POST.get('stream', '')
            student.school_board = request.POST.get('school_board', '')

            # C. Contact Details
            student.student_mobile = request.POST.get('student_mobile', '')
            student.school_email = request.POST.get('school_email', '')
            student.personal_email = request.POST.get('personal_email', '')
            student.address = request.POST.get('address', '')

            # D. Skill Lab Specific Details
            student.skill_lab_reg_id = skill_lab_reg_id
            student.enrollment_date = request.POST.get('enrollment_date', '')
            student.skills_enrolled = request.POST.get('skills_enrolled', '')
            student.current_skill_level = request.POST.get('current_skill_level', '')
            student.assigned_trainer = request.POST.get('assigned_trainer', '')
            student.batch_timing = request.POST.get('batch_timing', '')
            student.learning_style = request.POST.get('learning_style', '')
            student.interests_aptitude = request.POST.get('interests_aptitude', '')
            student.preferred_language = request.POST.get('preferred_language', '')
            student.attendance_status = request.POST.get('attendance_status', 'active')

            # E. Health & Safety
            student.medical_conditions = request.POST.get('medical_conditions', '')
            student.allergies = request.POST.get('allergies', '')
            student.emergency_instructions = request.POST.get('emergency_instructions', '')
            student.doctor_name = request.POST.get('doctor_name', '')
            student.doctor_contact = request.POST.get('doctor_contact', '')
            student.physical_limitations = request.POST.get('physical_limitations', '')

            # F. Emergency Contact
            student.emergency_name = request.POST.get('emergency_name', '')
            student.emergency_relationship = request.POST.get('emergency_relationship', '')
            student.emergency_mobile = request.POST.get('emergency_mobile', '')
            student.emergency_alt_mobile = request.POST.get('emergency_alt_mobile', '')
            student.emergency_address = request.POST.get('emergency_address', '')

            # G. Family Details
            student.sibling_1_name = request.POST.get('sibling_1_name', '')
            student.sibling_1_class_school = request.POST.get('sibling_1_class_school', '')
            student.sibling_1_skill_lab_id = request.POST.get('sibling_1_skill_lab_id', '')
            student.sibling_2_name = request.POST.get('sibling_2_name', '')
            student.sibling_2_class_school = request.POST.get('sibling_2_class_school', '')
            student.sibling_2_skill_lab_id = request.POST.get('sibling_2_skill_lab_id', '')
            student.sibling_3_name = request.POST.get('sibling_3_name', '')
            student.sibling_3_class_school = request.POST.get('sibling_3_class_school', '')
            student.sibling_3_skill_lab_id = request.POST.get('sibling_3_skill_lab_id', '')

            # Set metadata
            student.created_by = request.user

            # Create User account for student login
            User = get_user_model()
            email = student.school_email
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                messages.error(request, f'A user with email {email} already exists.')
                return redirect('onboard_student')
            
            # Generate temporary password
            import secrets
            import string
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%') for _ in range(12))
            
            # Create User with STUDENT role
            user = User.objects.create_user(
                username=email,
                email=email,
                password=temp_password,
                first_name=student.first_name,
                last_name=student.last_name,
                is_active=True,
                role='STUDENT'
            )
            
            # Link user to student
            student.user = user

            # Save the student
            student.save()
            
            # Send welcome email with credentials
            try:
                email_subject = 'Welcome to ENpower Skill Lab - Your Login Credentials'
                email_body = f"""
Dear {student.full_name},

Welcome to ENpower Skill Lab! Your student account has been created successfully.

Here are your login credentials:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email: {email}
🔑 Temporary Password: {temp_password}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 Login URL: http://127.0.0.1:8000/login/

Skill Lab ID: {skill_lab_reg_id}
Class: {student.student_class} - {student.division}
Role: Student

⚠️ IMPORTANT: Please change your password after your first login for security purposes.

If you have any questions, please contact your teacher or the administration.

Best regards,
ENpower Skill Lab Team
                """
                
                send_mail(
                    email_subject,
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                messages.success(request, f'Student {student.full_name} added successfully! Credentials sent to {email}')
            except Exception as mail_error:
                messages.warning(request, f'Student added but email failed: {str(mail_error)}. Password: {temp_password}')
            
            return redirect('student_list')

        except Exception as e:
            messages.error(request, f'Error adding student: {str(e)}')
            return redirect('onboard_student')

    # GET request - render the onboarding form
    from schools.models import School
    schools = School.objects.filter(is_active=True).order_by('school_name')
    context = {
        'schools': schools
    }
    return render(request, 'superadmin/onboard-student.html', context)


@login_required
@user_passes_test(is_superadmin)
def student_list(request):
    """View to display list of all students"""
    from student.models import Student
    import random
    
    # Get all students
    students = Student.objects.all().order_by('-created_at')
    
    # Add badge colors for students without photos
    badge_colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#a855f7']
    for student in students:
        student.badge_color = random.choice(badge_colors)
    
    context = {
        'students': students
    }
    return render(request, 'superadmin/students-list.html', context)


@login_required
@user_passes_test(is_superadmin)
def view_student(request, student_id):
    """View to display student details"""
    from student.models import Student
    student = get_object_or_404(Student, id=student_id)
    context = {
        'student': student
    }
    return render(request, 'superadmin/view-student.html', context)


@login_required
@user_passes_test(is_superadmin)
def edit_student(request, student_id):
    """View to edit student details"""
    from student.models import Student
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        # Handle form submission for editing
        try:
            student.first_name = request.POST.get('first_name', student.first_name)
            student.middle_name = request.POST.get('middle_name', student.middle_name)
            student.last_name = request.POST.get('last_name', student.last_name)
            student.gender = request.POST.get('gender', student.gender)
            student.date_of_birth = request.POST.get('date_of_birth', student.date_of_birth)
            student.student_class = request.POST.get('student_class', student.student_class)
            student.division = request.POST.get('division', student.division)
            student.attendance_status = request.POST.get('attendance_status', student.attendance_status)
            student.save()
            
            messages.success(request, f'Student {student.full_name} updated successfully!')
            return redirect('student_list')
        except Exception as e:
            messages.error(request, f'Error updating student: {str(e)}')
    
    schools = School.objects.filter(is_active=True)
    context = {
        'student': student,
        'schools': schools
    }
    return render(request, 'superadmin/edit-student.html', context)


# Teacher Onboarding Views
@login_required
@user_passes_test(is_superadmin)
def onboard_teacher(request):
    """View for onboarding new teachers"""
    if request.method == 'POST':
        try:
            from teacher.models import Teacher
            from datetime import date
            import secrets
            import string

            # Get employee ID from form or generate new one
            employee_id = request.POST.get('employee_id', '')
            if not employee_id or employee_id == 'Auto-generated':
                year = date.today().year
                random_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                employee_id = f"EMP{year}{random_str}"

            # Create teacher instance
            teacher = Teacher()

            # School Assignment
            school_id = request.POST.get('school', '')
            if school_id:
                from schools.models import School
                teacher.school = School.objects.get(id=school_id)

            # A. Basic Information
            if 'profile_photo' in request.FILES:
                teacher.profile_photo = request.FILES['profile_photo']
            teacher.employee_id = employee_id
            teacher.full_name = request.POST.get('full_name', '')
            teacher.gender = request.POST.get('gender', '')
            teacher.date_of_birth = request.POST.get('date_of_birth', '')
            teacher.blood_group = request.POST.get('blood_group', '') or None
            teacher.nationality = request.POST.get('nationality', 'Indian')
            teacher.aadhar_number = request.POST.get('aadhar_number', '') or None
            teacher.pan_number = request.POST.get('pan_number', '') or None

            # B. Professional Details
            teacher.designation = request.POST.get('designation', '')
            teacher.qualification = request.POST.get('qualification', '')
            teacher.specialization = request.POST.get('specialization', '') or None
            teacher.total_experience = request.POST.get('total_experience', '')
            teacher.skill_training_experience = request.POST.get('skill_training_experience', '') or None
            teacher.previous_organizations = request.POST.get('previous_organizations', '') or None
            teacher.certifications = request.POST.get('certifications', '') or None
            teacher.languages_known = request.POST.get('languages_known', '') or None
            teacher.grades_taught = request.POST.get('grades_taught', '') or None
            teacher.training_style = request.POST.get('training_style', '') or None

            # C. Contact Information
            teacher.mobile_number = request.POST.get('mobile_number', '')
            teacher.alternate_number = request.POST.get('alternate_number', '') or None
            teacher.official_email = request.POST.get('official_email', '')
            teacher.personal_email = request.POST.get('personal_email', '') or None

            # D. Address Details
            teacher.current_address = request.POST.get('current_address', '')
            teacher.permanent_address = request.POST.get('permanent_address', '') or None
            teacher.city = request.POST.get('city', '')
            teacher.state = request.POST.get('state', '')
            teacher.pin_code = request.POST.get('pin_code', '')

            # E. Skill Lab Work Details
            teacher.skill_lab_center = request.POST.get('skill_lab_center', '') or None
            teacher.branch_location = request.POST.get('branch_location', '') or None
            teacher.batch_timings = request.POST.get('batch_timings', '') or None
            teacher.weekly_timetable = request.POST.get('weekly_timetable', '') or None
            teacher.student_groups = request.POST.get('student_groups', '') or None
            teacher.modules_assigned = request.POST.get('modules_assigned', '') or None
            teacher.active_classes = request.POST.get('active_classes', '') or None
            total_students = request.POST.get('total_students', '')
            teacher.total_students = int(total_students) if total_students else 0
            teacher.dashboard_role = request.POST.get('dashboard_role', '') or None
            teacher.joining_date = request.POST.get('joining_date', '')
            contract_end = request.POST.get('contract_end_date', '')
            teacher.contract_end_date = contract_end if contract_end else None
            teacher.employment_type = request.POST.get('employment_type', '')

            # F. Emergency Information
            teacher.emergency_contact_name = request.POST.get('emergency_contact_name', '')
            teacher.emergency_relation = request.POST.get('emergency_relation', '')
            teacher.emergency_mobile = request.POST.get('emergency_mobile', '')
            teacher.emergency_secondary = request.POST.get('emergency_secondary', '') or None
            teacher.health_notes = request.POST.get('health_notes', '') or None

            # G. Compliance & Documentation
            teacher.id_proof_submitted = request.POST.get('id_proof_submitted', '') or None
            teacher.address_proof_submitted = request.POST.get('address_proof_submitted', '') or None
            teacher.police_verification = request.POST.get('police_verification', '') or None
            teacher.contract_uploaded = request.POST.get('contract_uploaded', '') or None
            if 'passport_photo' in request.FILES:
                teacher.passport_photo = request.FILES['passport_photo']
            teacher.pan_aadhar_linked = request.POST.get('pan_aadhar_linked', '') or None
            if 'resume' in request.FILES:
                teacher.resume = request.FILES['resume']
            teacher.bank_details_submitted = request.POST.get('bank_details_submitted', '') or None
            teacher.ifsc_code = request.POST.get('ifsc_code', '') or None
            teacher.bank_account_number = request.POST.get('bank_account_number', '') or None
            teacher.bank_name = request.POST.get('bank_name', '') or None
            teacher.branch_name = request.POST.get('branch_name', '') or None
            if 'passbook_copy' in request.FILES:
                teacher.passbook_copy = request.FILES['passbook_copy']

            # H. Additional Optional Data
            teacher.hobbies = request.POST.get('hobbies', '') or None
            teacher.strength_areas = request.POST.get('strength_areas', '') or None
            teacher.improvement_areas = request.POST.get('improvement_areas', '') or None
            teacher.training_resources = request.POST.get('training_resources', '') or None
            teacher.achievements = request.POST.get('achievements', '') or None

            # Set metadata
            teacher.created_by = request.user

            # Create User account for teacher login
            User = get_user_model()
            email = teacher.official_email
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                messages.error(request, f'A user with email {email} already exists.')
                return redirect('onboard_teacher')
            
            # Generate temporary password
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%') for _ in range(12))
            
            # Create User with THINKING_COACH role
            user = User.objects.create_user(
                username=email,
                email=email,
                password=temp_password,
                first_name=teacher.full_name.split()[0] if teacher.full_name else '',
                last_name=' '.join(teacher.full_name.split()[1:]) if len(teacher.full_name.split()) > 1 else '',
                is_active=True,
                role='THINKING_COACH'
            )
            
            # Link user to teacher
            teacher.user = user

            # Save the teacher
            teacher.save()
            
            # Send welcome email with credentials
            try:
                email_subject = 'Welcome to ENpower Skill Lab - Your Login Credentials'
                email_body = f"""
Dear {teacher.full_name},

Welcome to ENpower Skill Lab! Your account has been created successfully.

Here are your login credentials:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email: {email}
🔑 Temporary Password: {temp_password}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 Login URL: http://127.0.0.1:8000/login/

Employee ID: {employee_id}
Role: Thinking Coach / Teacher

⚠️ IMPORTANT: Please change your password after your first login for security purposes.

If you have any questions, please contact the administration.

Best regards,
ENpower Skill Lab Team
                """
                
                send_mail(
                    email_subject,
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                messages.success(request, f'Teacher {teacher.full_name} added successfully! Credentials sent to {email}')
            except Exception as mail_error:
                messages.warning(request, f'Teacher added but email failed: {str(mail_error)}. Password: {temp_password}')
            
            return redirect('teacher_list')

        except Exception as e:
            messages.error(request, f'Error adding teacher: {str(e)}')
            return redirect('onboard_teacher')

    # GET request - render the onboarding form
    from schools.models import School
    schools = School.objects.filter(is_active=True).order_by('school_name')
    context = {
        'schools': schools
    }
    return render(request, 'superadmin/onboard-teacher.html', context)


@login_required
@user_passes_test(is_superadmin)
def teacher_list(request):
    """View to display list of all teachers"""
    from teacher.models import Teacher
    import random

    # Get all teachers
    teachers = Teacher.objects.all().order_by('-created_at')

    # Add badge colors for teachers without photos
    badge_colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#a855f7']
    for teacher in teachers:
        teacher.badge_color = random.choice(badge_colors)

    context = {
        'teachers': teachers
    }
    return render(request, 'superadmin/teachers-list.html', context)


@login_required
@user_passes_test(is_superadmin)
def view_teacher(request, teacher_id):
    """View to display teacher details"""
    from teacher.models import Teacher
    teacher = get_object_or_404(Teacher, id=teacher_id)
    
    # Add badge color
    badge_colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']
    teacher.badge_color = badge_colors[teacher.id % len(badge_colors)]
    
    context = {
        'teacher': teacher
    }
    return render(request, 'superadmin/view-teacher.html', context)


@login_required
@user_passes_test(is_superadmin)
def edit_teacher(request, teacher_id):
    """View to edit teacher details"""
    from teacher.models import Teacher
    teacher = get_object_or_404(Teacher, id=teacher_id)

    if request.method == 'POST':
        try:
            # Update basic info
            teacher.full_name = request.POST.get('full_name', teacher.full_name)
            teacher.gender = request.POST.get('gender', teacher.gender)
            dob = request.POST.get('date_of_birth', '')
            if dob:
                teacher.date_of_birth = dob
            teacher.blood_group = request.POST.get('blood_group', teacher.blood_group) or None
            teacher.nationality = request.POST.get('nationality', teacher.nationality)

            # Update professional details
            teacher.designation = request.POST.get('designation', teacher.designation)
            teacher.qualification = request.POST.get('qualification', teacher.qualification)
            teacher.total_experience = request.POST.get('total_experience', teacher.total_experience)
            teacher.employment_type = request.POST.get('employment_type', teacher.employment_type)

            # Update contact info
            teacher.mobile_number = request.POST.get('mobile_number', teacher.mobile_number)
            teacher.official_email = request.POST.get('official_email', teacher.official_email)
            teacher.city = request.POST.get('city', teacher.city)
            teacher.state = request.POST.get('state', teacher.state)

            # Update status
            teacher.attendance_status = request.POST.get('attendance_status', teacher.attendance_status)
            is_active = request.POST.get('is_active', 'true')
            teacher.is_active = is_active == 'true'

            teacher.save()

            messages.success(request, f'Teacher {teacher.full_name} updated successfully!')
            return redirect('teacher_list')
        except Exception as e:
            messages.error(request, f'Error updating teacher: {str(e)}')

    context = {
        'teacher': teacher
    }
    return render(request, 'superadmin/edit-teacher.html', context)


@login_required
@user_passes_test(is_superadmin)
def delete_teacher(request, teacher_id):
    """View to delete a teacher"""
    from teacher.models import Teacher
    teacher = get_object_or_404(Teacher, id=teacher_id)
    teacher_name = teacher.full_name
    
    try:
        teacher.delete()
        messages.success(request, f'Teacher "{teacher_name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting teacher: {str(e)}')
    
    return redirect('teacher_list')


@login_required
@user_passes_test(is_superadmin)
def delete_student(request, student_id):
    """View to delete a student"""
    from student.models import Student
    student = get_object_or_404(Student, id=student_id)
    student_name = f"{student.first_name} {student.last_name}"
    
    try:
        student.delete()
        messages.success(request, f'Student "{student_name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting student: {str(e)}')
    
    return redirect('student_list')


# ==================== PARENT VIEWS ====================

@login_required
@user_passes_test(is_superadmin)
def parent_list(request):
    """View to display list of all parents"""
    from parent.models import Parent
    parents = Parent.objects.prefetch_related('students').all().order_by('-created_at')

    # Add helper properties for each parent
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#f97316', '#6366f1', '#ec4899', '#14b8a6']
    for parent in parents:
        # Assign badge color based on first character
        parent.badge_color = colors[ord(parent.full_name[0]) % len(colors)]

    context = {
        'parents': parents,
        'total_parents': parents.count(),
        'active_parents': parents.filter(account_status='active').count(),
        'pending_parents': parents.filter(account_status='pending').count(),
    }
    return render(request, 'superadmin/parent-list.html', context)


@login_required
@user_passes_test(is_superadmin)
def onboard_parent(request):
    """View to handle parent onboarding form"""
    from parent.models import Parent

    if request.method == 'POST':
        try:
            data = request.POST
            
            # Create parent
            parent = Parent(
                # Primary Parent Details
                full_name=data.get('full_name', ''),
                relation_to_student=data.get('relation_to_student', ''),
                mobile_number=data.get('mobile_number', ''),
                alternate_mobile=data.get('alternate_mobile', '') or None,
                email=data.get('email', ''),
                occupation=data.get('occupation', '') or None,
                organization=data.get('organization', '') or None,
                education_level=data.get('education_level', '') or None,
                id_proof=data.get('id_proof', '') or None,
                
                # Secondary Parent Details
                secondary_full_name=data.get('secondary_full_name', '') or None,
                secondary_relation=data.get('secondary_relation', '') or None,
                secondary_mobile=data.get('secondary_mobile', '') or None,
                secondary_email=data.get('secondary_email', '') or None,
                secondary_occupation=data.get('secondary_occupation', '') or None,
                preferred_contact=data.get('preferred_contact', 'primary'),
                
                # Address
                residential_address=data.get('residential_address', ''),
                landmark=data.get('landmark', '') or None,
                city=data.get('city', ''),
                state=data.get('state', ''),
                pin_code=data.get('pin_code', ''),
                permanent_address=data.get('permanent_address', '') or None,
                
                # Communication Preferences
                contact_method=data.get('contact_method', 'whatsapp'),
                preferred_language=data.get('preferred_language', 'english'),
                dnd_timings=data.get('dnd_timings', '') or None,
                whatsapp_consent=data.get('whatsapp_consent', 'yes') == 'yes',
                photo_consent=data.get('photo_consent', 'yes') == 'yes',
                
                # Financial
                fee_category=data.get('fee_category', 'regular'),
                payment_mode=data.get('payment_mode', '') or None,
                billing_email=data.get('billing_email', '') or None,
                gst_number=data.get('gst_number', '') or None,
                
                # Emergency Contact
                emergency_name=data.get('emergency_name', ''),
                emergency_relation=data.get('emergency_relation', ''),
                emergency_phone=data.get('emergency_phone', ''),
                emergency_address=data.get('emergency_address', '') or None,
                
                # Parent Involvement
                meeting_availability=data.get('meeting_availability', '') or None,
                volunteer_interest=data.get('volunteer_interest', '') or None,
                parent_skills=data.get('parent_skills', '') or None,
                
                # Status
                account_status='pending',
                created_by=request.user,
            )
            
            # Handle profile photo
            if 'profile_photo' in request.FILES:
                parent.profile_photo = request.FILES['profile_photo']
            
            # Create User account for parent login
            User = get_user_model()
            email = parent.email
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                messages.error(request, f'A user with email {email} already exists.')
                return redirect('onboard_parent')
            
            # Generate temporary password
            import secrets
            import string
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%') for _ in range(12))
            
            # Create User with PARENT role
            user = User.objects.create_user(
                username=email,
                email=email,
                password=temp_password,
                first_name=parent.full_name.split()[0] if parent.full_name else '',
                last_name=' '.join(parent.full_name.split()[1:]) if len(parent.full_name.split()) > 1 else '',
                is_active=True,
                role='PARENT'
            )
            
            # Link user to parent
            parent.user = user
            
            parent.save()
            
            # Link to students (ManyToMany relationship)
            student_ids = request.POST.getlist('students')
            linked_students = []
            if student_ids:
                from student.models import Student
                students = Student.objects.filter(id__in=student_ids)
                parent.students.set(students)
                linked_students = [s.full_name for s in students]
            
            # Send welcome email with credentials
            try:
                email_subject = 'Welcome to ENpower Skill Lab - Your Login Credentials'
                students_text = ', '.join(linked_students) if linked_students else 'Not yet linked'
                email_body = f"""
Dear {parent.full_name},

Welcome to ENpower Skill Lab! Your parent account has been created successfully.

Here are your login credentials:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email: {email}
🔑 Temporary Password: {temp_password}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 Login URL: http://127.0.0.1:8000/login/

Parent ID: {parent.parent_id}
Linked Student(s): {students_text}
Role: Parent/Guardian

⚠️ IMPORTANT: Please change your password after your first login for security purposes.

You can use the parent portal to:
- Track your child's progress
- View attendance records
- Communicate with teachers
- Access reports and certificates

If you have any questions, please contact the administration.

Best regards,
ENpower Skill Lab Team
                """
                
                send_mail(
                    email_subject,
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                messages.success(request, f'Parent "{parent.full_name}" onboarded successfully! Credentials sent to {email}')
            except Exception as mail_error:
                messages.warning(request, f'Parent added but email failed: {str(mail_error)}. Password: {temp_password}')
            
            return redirect('parent_list')
            
        except Exception as e:
            messages.error(request, f'Error onboarding parent: {str(e)}')
    
    # GET request - pass students to template
    from student.models import Student
    students = Student.objects.all().order_by('first_name', 'last_name')
    context = {
        'students': students
    }
    return render(request, 'superadmin/onboard-parent.html', context)


@login_required
@user_passes_test(is_superadmin)
def view_parent(request, parent_id):
    """View to display parent details"""
    from parent.models import Parent
    parent = get_object_or_404(Parent, id=parent_id)

    # Assign badge color
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']
    parent.badge_color = colors[ord(parent.full_name[0]) % len(colors)]

    context = {
        'parent': parent,
    }
    return render(request, 'superadmin/view-parent.html', context)


@login_required
@user_passes_test(is_superadmin)
def edit_parent(request, parent_id):
    """View to edit parent details"""
    from parent.models import Parent
    parent = get_object_or_404(Parent, id=parent_id)

    if request.method == 'POST':
        try:
            data = request.POST
            
            # Update Primary Parent Details
            parent.full_name = data.get('full_name', parent.full_name)
            parent.relation_to_student = data.get('relation_to_student', parent.relation_to_student)
            parent.mobile_number = data.get('mobile_number', parent.mobile_number)
            parent.alternate_mobile = data.get('alternate_mobile', '') or None
            parent.email = data.get('email', parent.email)
            parent.occupation = data.get('occupation', '') or None
            parent.organization = data.get('organization', '') or None
            parent.education_level = data.get('education_level', '') or None
            parent.id_proof = data.get('id_proof', '') or None
            
            # Update Secondary Parent Details
            parent.secondary_full_name = data.get('secondary_full_name', '') or None
            parent.secondary_relation = data.get('secondary_relation', '') or None
            parent.secondary_mobile = data.get('secondary_mobile', '') or None
            parent.secondary_email = data.get('secondary_email', '') or None
            parent.secondary_occupation = data.get('secondary_occupation', '') or None
            parent.preferred_contact = data.get('preferred_contact', 'primary')
            
            # Update Address
            parent.residential_address = data.get('residential_address', parent.residential_address)
            parent.landmark = data.get('landmark', '') or None
            parent.city = data.get('city', parent.city)
            parent.state = data.get('state', parent.state)
            parent.pin_code = data.get('pin_code', parent.pin_code)
            parent.permanent_address = data.get('permanent_address', '') or None
            
            # Update Communication Preferences
            parent.contact_method = data.get('contact_method', parent.contact_method)
            parent.preferred_language = data.get('preferred_language', parent.preferred_language)
            parent.dnd_timings = data.get('dnd_timings', '') or None
            parent.whatsapp_consent = data.get('whatsapp_consent', 'yes') == 'yes'
            parent.photo_consent = data.get('photo_consent', 'yes') == 'yes'
            
            # Update Financial
            parent.fee_category = data.get('fee_category', parent.fee_category)
            parent.payment_mode = data.get('payment_mode', '') or None
            parent.billing_email = data.get('billing_email', '') or None
            parent.gst_number = data.get('gst_number', '') or None
            
            # Update Emergency Contact
            parent.emergency_name = data.get('emergency_name', parent.emergency_name)
            parent.emergency_relation = data.get('emergency_relation', parent.emergency_relation)
            parent.emergency_phone = data.get('emergency_phone', parent.emergency_phone)
            parent.emergency_address = data.get('emergency_address', '') or None
            
            # Update Parent Involvement
            parent.meeting_availability = data.get('meeting_availability', '') or None
            parent.volunteer_interest = data.get('volunteer_interest', '') or None
            parent.parent_skills = data.get('parent_skills', '') or None
            
            # Update Status
            parent.account_status = data.get('account_status', parent.account_status)
            parent.is_active = data.get('is_active', 'true') == 'true'
            
            # Handle profile photo
            if 'profile_photo' in request.FILES:
                parent.profile_photo = request.FILES['profile_photo']
            
            parent.save()
            
            messages.success(request, f'Parent "{parent.full_name}" updated successfully!')
            return redirect('parent_list')
            
        except Exception as e:
            messages.error(request, f'Error updating parent: {str(e)}')

    # Assign badge color
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']
    parent.badge_color = colors[ord(parent.full_name[0]) % len(colors)]

    context = {
        'parent': parent,
    }
    return render(request, 'superadmin/edit-parent.html', context)


@login_required
@user_passes_test(is_superadmin)
def delete_parent(request, parent_id):
    """View to delete a parent"""
    from parent.models import Parent
    parent = get_object_or_404(Parent, id=parent_id)
    parent_name = parent.full_name
    
    try:
        parent.delete()
        messages.success(request, f'Parent "{parent_name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting parent: {str(e)}')
    
    return redirect('parent_list')


# ==================== PROGRAM COORDINATOR VIEWS ====================

@login_required
@user_passes_test(is_superadmin)
def onboard_coordinator(request):
    """View to handle program coordinator onboarding form"""
    from coordinator.models import ProgramCoordinator
    
    if request.method == 'POST':
        try:
            data = request.POST
            files = request.FILES
            
            # Helper function to handle empty date strings
            def parse_date(date_str):
                if date_str and date_str.strip():
                    return date_str
                return None
            
            # Generate temporary password
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            
            # Get coordinator email
            coordinator_email = data.get('officialEmail', '')
            
            # Check if email already exists
            User = get_user_model()
            if User.objects.filter(email=coordinator_email).exists():
                messages.error(request, f'A user with email {coordinator_email} already exists.')
                schools = School.objects.filter(is_active=True).order_by('school_name')
                return render(request, 'superadmin/onboard-pc.html', {'schools': schools})
            
            # Create User account for the coordinator
            user = User.objects.create_user(
                username=coordinator_email,
                email=coordinator_email,
                password=temp_password,
                first_name=data.get('fullName', '').split()[0] if data.get('fullName') else '',
                last_name=' '.join(data.get('fullName', '').split()[1:]) if len(data.get('fullName', '').split()) > 1 else '',
                role='PROGRAM_COORDINATOR',
                phone_number=data.get('mobileNumber', ''),
            )
            
            # Create coordinator instance
            coordinator = ProgramCoordinator(
                user=user,  # Link to user
                # Basic Information
                full_name=data.get('fullName', ''),
                gender=data.get('gender', ''),
                date_of_birth=parse_date(data.get('dateOfBirth')),
                blood_group=data.get('bloodGroup', '') or None,
                nationality=data.get('nationality', 'Indian'),
                employee_id=data.get('employeeId', '').strip() or None,
                aadhar_number=data.get('aadharNumber', ''),
                pan_number=data.get('panNumber', '').upper(),
                
                # Professional Details
                designation=data.get('designation', ''),
                qualification=data.get('qualification', ''),
                specialization=data.get('specialization', ''),
                total_experience=data.get('totalExperience', ''),
                program_management_exp=data.get('programManagementExp', '') or None,
                education_exp=data.get('educationExp', '') or None,
                previous_organizations=data.get('previousOrganizations', '') or None,
                languages_known=data.get('languagesKnown', ''),
                certifications=data.get('certifications', '') or None,
                
                # Contact Information
                mobile_number=data.get('mobileNumber', ''),
                alternate_number=data.get('alternateNumber', '') or None,
                official_email=data.get('officialEmail', ''),
                personal_email=data.get('personalEmail', '') or None,
                
                # Address Details
                current_address=data.get('currentAddress', ''),
                permanent_address=data.get('permanentAddress', '') or None,
                city=data.get('city', ''),
                state=data.get('state', ''),
                pincode=data.get('pincode', ''),
                
                # Compliance & Documentation
                id_proof=data.get('idProof', '') or None,
                address_proof=data.get('addressProof', '') or None,
                police_verification=data.get('policeVerification') or 'Pending',
                passport_photo_uploaded=data.get('passportPhotoUploaded') or 'No',
                contract_uploaded=data.get('contractUploaded') or 'No',
                pan_aadhar_linked=data.get('panAadharLinked') or 'No',
                nda_signed=data.get('ndaSigned') or 'No',
                
                # Program & Work Assignment Details
                program_assigned=data.get('programAssigned', '') or None,
                zone_assigned=data.get('zoneAssigned', '') or None,
                branch_region=data.get('branchRegion', '') or None,
                reporting_manager=data.get('reportingManager', '') or None,
                login_role=data.get('loginRole', '') or None,
                joining_date=parse_date(data.get('joiningDate')),
                employment_type=data.get('employmentType', ''),
                contract_start_date=parse_date(data.get('contractStartDate')),
                contract_end_date=parse_date(data.get('contractEndDate')),
                
                # Bank & Payroll Details
                bank_name=data.get('bankName', ''),
                branch_name=data.get('branchName', ''),
                account_number=data.get('accountNumber', ''),
                ifsc_code=data.get('ifscCode', '').upper(),
                
                # Additional Optional Data
                strength_areas=data.get('strengthAreas', '') or None,
                hobbies=data.get('hobbies', '') or None,
                work_style=data.get('workStyle', '') or None,
                tools_comfortable=data.get('toolsComfortable', '') or None,
                achievements=data.get('achievements', '') or None,
                career_aspirations=data.get('careerAspirations', '') or None,
                
                # Metadata
                created_by=request.user,
            )
            
            # Handle file uploads
            if 'profilePhoto' in files:
                coordinator.profile_photo = files['profilePhoto']
            if 'resumeUpload' in files:
                coordinator.resume = files['resumeUpload']
            if 'bankProofUpload' in files:
                coordinator.bank_proof = files['bankProofUpload']
            
            coordinator.save()
            
            # Handle schools assignment (ManyToMany)
            school_ids = data.getlist('schools')
            if school_ids:
                # Filter to only valid integer IDs
                valid_ids = [int(sid) for sid in school_ids if sid.isdigit()]
                if valid_ids:
                    coordinator.schools_assigned.set(School.objects.filter(id__in=valid_ids))
            
            # Send email with credentials
            try:
                email_subject = 'Welcome to Enpower Skill Lab - Your Program Coordinator Account'
                email_body = f"""
Dear {coordinator.full_name},

You have been registered as a Program Coordinator at Enpower Skill Lab.

Your Login Credentials:
- Username: {user.email}
- Temporary Password: {temp_password}
- Login URL: {request.build_absolute_uri('/')[:-1]}/login/

IMPORTANT: Please change your password immediately after your first login for security reasons.

After logging in, you can access your dashboard at:
{request.build_absolute_uri('/')[:-1]}/coordinator/dashboard/

If you have any questions, please contact support.

Best regards,
Enpower Skill Lab Team
                """

                send_mail(
                    email_subject,
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [coordinator.official_email],
                    fail_silently=False,
                )

                messages.success(request, f'Program Coordinator "{coordinator.full_name}" onboarded successfully! Credentials sent to {coordinator.official_email}.')
            except Exception as email_error:
                messages.warning(request, f'Program Coordinator created but email failed to send: {str(email_error)}. Temporary password: {temp_password}')
            
            return redirect('superadmin_dashboard')
            
        except Exception as e:
            # If user was created but coordinator failed, delete the user
            if 'user' in locals():
                user.delete()
            messages.error(request, f'Error onboarding coordinator: {str(e)}')
    
    # GET request - pass schools to template
    schools = School.objects.filter(is_active=True).order_by('school_name')
    context = {
        'schools': schools
    }
    return render(request, 'superadmin/onboard-pc.html', context)


# ==================== PROGRAM COORDINATOR MANAGEMENT VIEWS ====================

@login_required
@user_passes_test(is_superadmin)
def coordinator_list(request):
    """View to display all program coordinators"""
    from coordinator.models import ProgramCoordinator
    
    coordinators = ProgramCoordinator.objects.all().order_by('-created_at')
    
    context = {
        'coordinators': coordinators,
    }
    return render(request, 'superadmin/pc-list.html', context)


@login_required
@user_passes_test(is_superadmin)
def view_coordinator(request, coordinator_id):
    """View to display coordinator details"""
    from coordinator.models import ProgramCoordinator
    
    coordinator = get_object_or_404(ProgramCoordinator, id=coordinator_id)
    
    context = {
        'coordinator': coordinator,
    }
    return render(request, 'superadmin/view-pc.html', context)


@login_required
@user_passes_test(is_superadmin)
def edit_coordinator(request, coordinator_id):
    """View to edit a coordinator"""
    from coordinator.models import ProgramCoordinator

    coordinator = get_object_or_404(ProgramCoordinator, id=coordinator_id)

    if request.method == 'POST':
        try:
            data = request.POST

            # Basic Information
            coordinator.full_name = data.get('fullName', coordinator.full_name)
            coordinator.gender = data.get('gender', coordinator.gender)
            if data.get('dateOfBirth'):
                coordinator.date_of_birth = data.get('dateOfBirth')
            coordinator.blood_group = data.get('bloodGroup') or None
            coordinator.nationality = data.get('nationality', coordinator.nationality)
            coordinator.aadhar_number = data.get('aadharNumber', coordinator.aadhar_number)
            coordinator.pan_number = data.get('panNumber', coordinator.pan_number)

            # Professional Details
            coordinator.designation = data.get('designation', coordinator.designation)
            coordinator.qualification = data.get('qualification', coordinator.qualification)
            coordinator.specialization = data.get('specialization', coordinator.specialization)
            coordinator.total_experience = data.get('totalExperience', coordinator.total_experience)
            coordinator.program_management_exp = data.get('programManagementExp') or None
            coordinator.education_exp = data.get('educationExp') or None
            coordinator.previous_organizations = data.get('previousOrganizations') or None
            coordinator.languages_known = data.get('languagesKnown', coordinator.languages_known)
            coordinator.certifications = data.get('certifications') or None

            # Contact Information
            coordinator.mobile_number = data.get('mobileNumber', coordinator.mobile_number)
            coordinator.alternate_number = data.get('alternateNumber') or None
            coordinator.official_email = data.get('officialEmail', coordinator.official_email)
            coordinator.personal_email = data.get('personalEmail') or None

            # Address Details
            coordinator.current_address = data.get('currentAddress', coordinator.current_address)
            coordinator.permanent_address = data.get('permanentAddress') or None
            coordinator.city = data.get('city', coordinator.city)
            coordinator.state = data.get('state', coordinator.state)
            coordinator.pincode = data.get('pincode', coordinator.pincode)

            # Compliance & Documentation
            coordinator.id_proof = data.get('idProof') or None
            coordinator.address_proof = data.get('addressProof') or None
            coordinator.police_verification = data.get('policeVerification') or 'Pending'
            coordinator.passport_photo_uploaded = data.get('passportPhotoUploaded') or 'No'
            coordinator.contract_uploaded = data.get('contractUploaded') or 'No'
            coordinator.pan_aadhar_linked = data.get('panAadharLinked') or 'No'
            coordinator.nda_signed = data.get('ndaSigned') or 'No'

            # Program & Work Assignment
            coordinator.program_assigned = data.get('programAssigned') or None
            coordinator.zone_assigned = data.get('zoneAssigned') or None
            coordinator.branch_region = data.get('branchRegion') or None
            coordinator.reporting_manager = data.get('reportingManager') or None
            coordinator.login_role = data.get('loginRole') or None
            if data.get('joiningDate'):
                coordinator.joining_date = data.get('joiningDate')
            coordinator.employment_type = data.get('employmentType', coordinator.employment_type)
            coordinator.contract_start_date = data.get('contractStartDate') or None
            coordinator.contract_end_date = data.get('contractEndDate') or None

            # Bank & Payroll
            coordinator.bank_name = data.get('bankName', coordinator.bank_name)
            coordinator.branch_name = data.get('branchName', coordinator.branch_name)
            coordinator.account_number = data.get('accountNumber', coordinator.account_number)
            coordinator.ifsc_code = data.get('ifscCode', coordinator.ifsc_code)

            # Additional Optional
            coordinator.strength_areas = data.get('strengthAreas') or None
            coordinator.hobbies = data.get('hobbies') or None
            coordinator.work_style = data.get('workStyle') or None
            coordinator.tools_comfortable = data.get('toolsComfortable') or None
            coordinator.achievements = data.get('achievements') or None
            coordinator.career_aspirations = data.get('careerAspirations') or None

            # Status
            coordinator.is_active = data.get('isActive') == 'true'

            # Profile photo
            if request.FILES.get('profilePhoto'):
                coordinator.profile_photo = request.FILES['profilePhoto']

            coordinator.save()

            # Update M2M schools
            school_ids = data.getlist('schools')
            coordinator.schools_assigned.set(school_ids)

            # Update linked user email if changed
            if coordinator.user and coordinator.user.email != coordinator.official_email:
                coordinator.user.email = coordinator.official_email
                coordinator.user.save()

            messages.success(request, f'Coordinator "{coordinator.full_name}" updated successfully!')
            return redirect('coordinator_list')

        except Exception as e:
            messages.error(request, f'Error updating coordinator: {str(e)}')

    schools = School.objects.filter(is_active=True).order_by('school_name')
    context = {
        'coordinator': coordinator,
        'schools': schools,
        'blood_group_choices': ProgramCoordinator.BLOOD_GROUP_CHOICES,
        'designation_choices': ProgramCoordinator.DESIGNATION_CHOICES,
        'specialization_choices': ProgramCoordinator.SPECIALIZATION_CHOICES,
        'employment_type_choices': ProgramCoordinator.EMPLOYMENT_TYPE_CHOICES,
        'work_style_choices': ProgramCoordinator.WORK_STYLE_CHOICES,
        'verification_status_choices': ProgramCoordinator.VERIFICATION_STATUS_CHOICES,
    }
    return render(request, 'superadmin/edit-pc.html', context)


@login_required
@user_passes_test(is_superadmin)
def delete_coordinator(request, coordinator_id):
    """View to delete a coordinator"""
    from coordinator.models import ProgramCoordinator
    
    if request.method == 'POST':
        coordinator = get_object_or_404(ProgramCoordinator, id=coordinator_id)
        coordinator_name = coordinator.full_name
        
        # Also delete the associated user if exists
        if coordinator.user:
            coordinator.user.delete()
        
        coordinator.delete()
        messages.success(request, f'Coordinator "{coordinator_name}" deleted successfully!')
    
    return redirect('coordinator_list')


# ==================== CLASS MANAGEMENT VIEWS ====================

@login_required
@user_passes_test(is_superadmin)
def class_list(request):
    """View to display all classes"""
    from schools.models import Class
    
    classes = Class.objects.select_related('school', 'thinking_coach').all()
    schools = School.objects.filter(is_active=True)
    
    # Get unique locations
    locations = School.objects.filter(is_active=True).values_list('city', flat=True).distinct()
    
    # Get coaches (teachers)
    User = get_user_model()
    coaches = User.objects.filter(role='TEACHER', is_active=True)
    
    # Grade choices for the edit drawer
    grade_choices = Class.GRADE_CHOICES
    
    context = {
        'classes': classes,
        'schools': schools,
        'locations': locations,
        'coaches': coaches,
        'grade_choices': grade_choices,
    }
    return render(request, 'superadmin/class-list.html', context)


@login_required
@user_passes_test(is_superadmin)
def add_class(request):
    """View to add a new class"""
    from schools.models import Class
    
    if request.method == 'POST':
        try:
            # Get form data
            school_id = request.POST.get('school')
            grade = request.POST.get('grade')
            division = request.POST.get('division', '').upper()
            academic_year = request.POST.get('academic_year')
            thinking_coach_id = request.POST.get('thinking_coach')
            total_sessions = request.POST.get('total_sessions', 48)
            is_active = request.POST.get('is_active') == 'on'
            student_visibility = request.POST.get('student_visibility') == 'on'
            parent_visibility = request.POST.get('parent_visibility') == 'on'
            
            # Get class name and code from hidden fields or generate
            class_name = request.POST.get('class_name') or f"Std {grade}{division}"
            class_code = request.POST.get('class_code')
            
            # Get school
            school = get_object_or_404(School, id=school_id)
            
            # Get thinking coach if provided
            thinking_coach = None
            if thinking_coach_id:
                from teacher.models import Teacher
                teacher = Teacher.objects.filter(id=thinking_coach_id).first()
                if teacher:
                    thinking_coach = teacher.user
            
            # Create class
            new_class = Class(
                school=school,
                grade=grade,
                division=division,
                class_name=class_name,
                academic_year=academic_year,
                thinking_coach=thinking_coach,
                total_sessions=int(total_sessions) if total_sessions else 48,
                is_active=is_active,
                student_visibility=student_visibility,
                parent_visibility=parent_visibility,
                created_by=request.user,
            )
            
            # Let the model generate the class code if not provided
            if class_code and class_code != 'CLS-YYYY-XX-001':
                new_class.class_code = class_code
            
            new_class.save()
            
            messages.success(request, f'Class "{new_class.class_name}" created successfully!')
            return redirect('class_list')
            
        except Exception as e:
            messages.error(request, f'Error creating class: {str(e)}')
    
    # GET request - render form
    schools = School.objects.filter(is_active=True)
    
    # Get teachers (thinking coaches) from Teacher model
    from teacher.models import Teacher
    # Get ALL teachers (remove filters to see everyone)
    coaches = Teacher.objects.all().select_related('user')
    
    # Debug: Print the coaches to console
    print(f"Found {coaches.count()} teachers:")
    for coach in coaches:
        print(f"  - ID: {coach.id}, Name: {coach.full_name}, User: {coach.user.username if coach.user else 'No User'}, User Active: {coach.user.is_active if coach.user else 'N/A'}")
    
    context = {
        'schools': schools,
        'coaches': coaches,
    }
    return render(request, 'superadmin/add-class.html', context)


@login_required
@user_passes_test(is_superadmin)
def edit_class(request, class_id):
    """View to edit a class (AJAX endpoint)"""
    from schools.models import Class
    
    class_obj = get_object_or_404(Class, id=class_id)
    
    if request.method == 'POST':
        try:
            # Update class data
            school_id = request.POST.get('school')
            if school_id:
                class_obj.school = get_object_or_404(School, id=school_id)
            
            class_obj.grade = request.POST.get('grade', class_obj.grade)
            class_obj.division = request.POST.get('division', class_obj.division).upper()
            class_obj.class_name = request.POST.get('class_name') or f"Std {class_obj.grade}{class_obj.division}"
            class_obj.academic_year = request.POST.get('academic_year', class_obj.academic_year)
            class_obj.total_sessions = int(request.POST.get('total_sessions', class_obj.total_sessions))
            
            # Update thinking coach
            thinking_coach_id = request.POST.get('thinking_coach')
            if thinking_coach_id:
                User = get_user_model()
                class_obj.thinking_coach = User.objects.filter(id=thinking_coach_id, role='TEACHER').first()
            else:
                class_obj.thinking_coach = None
            
            # Update visibility settings
            class_obj.is_active = request.POST.get('is_active') == 'true'
            class_obj.student_visibility = request.POST.get('student_visibility') == 'true'
            class_obj.parent_visibility = request.POST.get('parent_visibility') == 'true'
            
            class_obj.save()
            
            messages.success(request, f'Class "{class_obj.class_name}" updated successfully!')
            
        except Exception as e:
            messages.error(request, f'Error updating class: {str(e)}')
    
    return redirect('class_list')


@login_required
@user_passes_test(is_superadmin)
def delete_class(request, class_id):
    """View to delete a class"""
    from schools.models import Class
    
    class_obj = get_object_or_404(Class, id=class_id)
    class_name = class_obj.class_name
    
    try:
        class_obj.delete()
        messages.success(request, f'Class "{class_name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting class: {str(e)}')
    
    return redirect('class_list')


# ==================== LESSON MANAGEMENT VIEWS ====================

@login_required
@user_passes_test(is_superadmin)
def lesson_list(request):
    """View to display all lessons"""
    from lms.models import Lesson
    
    lessons = Lesson.objects.all()
    schools = School.objects.filter(is_active=True)
    
    context = {
        'lessons': lessons,
        'schools': schools,
    }
    return render(request, 'superadmin/lesson-list.html', context)


@login_required
@user_passes_test(is_superadmin)
def add_lesson(request):
    """View to add a new lesson"""
    from lms.models import Lesson, LessonResource
    import os

    if request.method == 'POST':
        try:
            # Get form data
            title = request.POST.get('title')
            description = request.POST.get('description')
            competency_id = request.POST.get('competency')
            level = request.POST.get('level', 'beginner')
            module_id = request.POST.get('module')
            applicable_grades = request.POST.get('applicable_grades')
            status = request.POST.get('status', 'draft')
            is_published = status == 'published'
            recommend_low_competency = request.POST.get('recommend_low_competency') == 'true'

            # Resolve FKs
            from competencies.models import Competency as CompModel, SubPillar as SPModel
            competency_obj = None
            module_obj = None
            if competency_id:
                try:
                    competency_obj = CompModel.objects.get(pk=competency_id)
                except CompModel.DoesNotExist:
                    pass
            if module_id:
                try:
                    module_obj = SPModel.objects.get(pk=module_id)
                except SPModel.DoesNotExist:
                    pass

            # Get content data
            video_urls = request.POST.get('video_urls', '')
            article_content = request.POST.get('article_content', '')
            quiz_data = request.POST.get('quiz_data', '')

            # Determine primary_content_type based on actual content (not form value)
            # Priority: Video > Article > Quiz > Resources
            import json
            import re
            has_videos = False
            has_article = False
            has_quiz = False
            has_resources = len(request.FILES.getlist('resources')) > 0

            # Check for videos
            if video_urls and video_urls.strip() and video_urls.strip() != '[]':
                try:
                    urls = json.loads(video_urls)
                    if isinstance(urls, list) and len(urls) > 0:
                        # Check if URLs are not empty strings
                        has_videos = any(url and url.strip() for url in urls)
                except json.JSONDecodeError:
                    # If JSON parsing fails but there's content, treat it as having videos
                    has_videos = True

            # Check for article content (more robust check)
            if article_content and article_content.strip():
                # Remove HTML tags for content check
                text_content = re.sub('<[^<]+?>', '', article_content)
                if text_content.strip() and text_content.strip() != '':
                    has_article = True

            # Check for quiz
            if quiz_data and quiz_data.strip() and quiz_data.strip() != '[]':
                try:
                    quiz = json.loads(quiz_data)
                    if isinstance(quiz, list) and len(quiz) > 0:
                        has_quiz = True
                except json.JSONDecodeError:
                    has_quiz = True

            # Set primary content type based on priority
            if has_videos:
                primary_content_type = 'video'
            elif has_article:
                primary_content_type = 'article'
            elif has_quiz:
                primary_content_type = 'quiz'
            elif has_resources:
                primary_content_type = 'mixed'
            else:
                primary_content_type = request.POST.get('primary_content_type', 'video')

            # Create lesson
            lesson = Lesson(
                title=title,
                description=description,
                competency=competency_obj,
                level=level,
                module=module_obj,
                applicable_grades=applicable_grades,
                status=status,
                is_published=is_published,
                recommend_low_competency=recommend_low_competency,
                primary_content_type=primary_content_type,
                video_urls=video_urls,
                article_content=article_content,
                quiz_data=quiz_data,
                created_by=request.user,
            )

            # Handle thumbnail upload
            if 'thumbnail' in request.FILES:
                lesson.thumbnail = request.FILES['thumbnail']

            lesson.save()

            # Handle applicable schools (M2M)
            school_id = request.POST.get('applicable_schools')
            if school_id:
                school = School.objects.filter(id=school_id).first()
                if school:
                    lesson.applicable_schools.add(school)

            # Handle resource files
            resource_files = request.FILES.getlist('resources')
            for resource_file in resource_files:
                # Get file extension
                file_extension = os.path.splitext(resource_file.name)[1].lower().replace('.', '')

                # Determine resource type
                resource_type_map = {
                    'pdf': 'pdf',
                    'doc': 'doc', 'docx': 'doc',
                    'ppt': 'ppt', 'pptx': 'ppt',
                    'xls': 'xls', 'xlsx': 'xls',
                }
                resource_type = resource_type_map.get(file_extension, 'other')

                # Create LessonResource
                LessonResource.objects.create(
                    lesson=lesson,
                    title=resource_file.name,
                    file=resource_file,
                    resource_type=resource_type,
                    file_size=resource_file.size
                )

            messages.success(request, f'Lesson "{lesson.title}" created successfully!')
            return redirect('lesson_list')

        except Exception as e:
            messages.error(request, f'Error creating lesson: {str(e)}')

    # GET request - render form
    schools = School.objects.filter(is_active=True)
    from competencies.models import Competency as CompModel, SubPillar as SPModel

    context = {
        'schools': schools,
        'competencies': CompModel.objects.filter(status='Active').select_related('sub_pillar').order_by('code'),
        'sub_pillars': SPModel.objects.all().select_related('pillar').order_by('sp_number'),
    }
    return render(request, 'superadmin/add-lessons.html', context)


@login_required
@user_passes_test(is_superadmin)
def view_lesson(request, lesson_id):
    """View to display a lesson in read-only mode"""
    from lms.models import Lesson, LessonResource, LessonVideo
    import json

    lesson = get_object_or_404(Lesson, id=lesson_id)
    resources = LessonResource.objects.filter(lesson=lesson)
    videos = LessonVideo.objects.filter(lesson=lesson)
    schools = School.objects.filter(is_active=True)

    # Parse video URLs from JSON
    video_urls_list = []
    if lesson.video_urls:
        try:
            video_urls_list = json.loads(lesson.video_urls)
        except (json.JSONDecodeError, TypeError):
            pass

    context = {
        'lesson': lesson,
        'resources': resources,
        'videos': videos,
        'video_urls_list': video_urls_list,
        'schools': schools,
        'view_mode': True,  # Flag for read-only mode
    }
    return render(request, 'superadmin/view-lesson.html', context)


@login_required
@user_passes_test(is_superadmin)
def edit_lesson(request, lesson_id):
    """View to edit a lesson"""
    from lms.models import Lesson, LessonResource, LessonVideo
    
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    if request.method == 'POST':
        try:
            lesson.title = request.POST.get('title', lesson.title)
            lesson.description = request.POST.get('description', lesson.description)
            lesson.level = request.POST.get('level', lesson.level)

            # Resolve FK for competency and module
            from competencies.models import Competency as CompModel, SubPillar as SPModel
            comp_id = request.POST.get('competency')
            mod_id = request.POST.get('module')
            if comp_id:
                try:
                    lesson.competency = CompModel.objects.get(pk=comp_id)
                except CompModel.DoesNotExist:
                    lesson.competency = None
            else:
                lesson.competency = None
            if mod_id:
                try:
                    lesson.module = SPModel.objects.get(pk=mod_id)
                except SPModel.DoesNotExist:
                    lesson.module = None
            else:
                lesson.module = None
            lesson.applicable_grades = request.POST.get('applicable_grades', lesson.applicable_grades)

            status = request.POST.get('status', lesson.status)
            lesson.status = status
            lesson.is_published = status == 'published'
            lesson.recommend_low_competency = request.POST.get('recommend_low_competency') == 'true'

            # Update content data
            video_urls = request.POST.get('video_urls', lesson.video_urls)
            article_content = request.POST.get('article_content', lesson.article_content)
            quiz_data = request.POST.get('quiz_data', lesson.quiz_data)

            # Determine primary_content_type based on actual content (same logic as add_lesson)
            import json
            import re
            has_videos = False
            has_article = False
            has_quiz = False
            has_resources = len(request.FILES.getlist('resources')) > 0

            # Check for videos
            if video_urls and video_urls.strip() and video_urls.strip() != '[]':
                try:
                    urls = json.loads(video_urls)
                    if isinstance(urls, list) and len(urls) > 0:
                        # Check if URLs are not empty strings
                        has_videos = any(url and url.strip() for url in urls)
                except json.JSONDecodeError:
                    # If JSON parsing fails but there's content, treat it as having videos
                    has_videos = True

            # Check for article content (more robust check)
            if article_content and article_content.strip():
                # Remove HTML tags for content check
                text_content = re.sub('<[^<]+?>', '', article_content)
                if text_content.strip() and text_content.strip() != '':
                    has_article = True

            # Check for quiz
            if quiz_data and quiz_data.strip() and quiz_data.strip() != '[]':
                try:
                    quiz = json.loads(quiz_data)
                    if isinstance(quiz, list) and len(quiz) > 0:
                        has_quiz = True
                except json.JSONDecodeError:
                    has_quiz = True

            # Set primary content type based on priority
            if has_videos:
                primary_content_type = 'video'
            elif has_article:
                primary_content_type = 'article'
            elif has_quiz:
                primary_content_type = 'quiz'
            elif has_resources:
                primary_content_type = 'mixed'
            else:
                primary_content_type = request.POST.get('primary_content_type', lesson.primary_content_type)

            lesson.primary_content_type = primary_content_type
            lesson.video_urls = video_urls
            lesson.article_content = article_content
            lesson.quiz_data = quiz_data

            if 'thumbnail' in request.FILES:
                lesson.thumbnail = request.FILES['thumbnail']

            lesson.save()
            
            # Handle applicable schools (M2M)
            school_id = request.POST.get('applicable_schools')
            lesson.applicable_schools.clear()
            if school_id:
                school = School.objects.filter(id=school_id).first()
                if school:
                    lesson.applicable_schools.add(school)

            # Handle new resource files
            import os
            resource_files = request.FILES.getlist('resources')
            for resource_file in resource_files:
                # Get file extension
                file_extension = os.path.splitext(resource_file.name)[1].lower().replace('.', '')

                # Determine resource type
                resource_type_map = {
                    'pdf': 'pdf',
                    'doc': 'doc', 'docx': 'doc',
                    'ppt': 'ppt', 'pptx': 'ppt',
                    'xls': 'xls', 'xlsx': 'xls',
                }
                resource_type = resource_type_map.get(file_extension, 'other')

                # Create LessonResource
                LessonResource.objects.create(
                    lesson=lesson,
                    title=resource_file.name,
                    file=resource_file,
                    resource_type=resource_type,
                    file_size=resource_file.size
                )

            messages.success(request, f'Lesson "{lesson.title}" updated successfully!')
            return redirect('lesson_list')
            
        except Exception as e:
            messages.error(request, f'Error updating lesson: {str(e)}')
    
    # GET request - render edit form with lesson data
    resources = LessonResource.objects.filter(lesson=lesson)
    videos = LessonVideo.objects.filter(lesson=lesson)
    schools = School.objects.filter(is_active=True)
    
    from competencies.models import Competency as CompModel, SubPillar as SPModel
    context = {
        'lesson': lesson,
        'resources': resources,
        'videos': videos,
        'schools': schools,
        'edit_mode': True,  # Flag for edit mode
        'competencies': CompModel.objects.filter(status='Active').select_related('sub_pillar').order_by('code'),
        'sub_pillars': SPModel.objects.all().select_related('pillar').order_by('sp_number'),
    }
    return render(request, 'superadmin/edit-lesson.html', context)


@login_required
@user_passes_test(is_superadmin)
def delete_lesson(request, lesson_id):
    """View to delete a lesson"""
    from lms.models import Lesson
    
    lesson = get_object_or_404(Lesson, id=lesson_id)
    lesson_title = lesson.title
    
    try:
        lesson.delete()
        messages.success(request, f'Lesson "{lesson_title}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting lesson: {str(e)}')
    
    return redirect('lesson_list')



# ─── Skill Passport: Learning Pillars ────────────────────────────────────────

@login_required
@user_passes_test(is_superadmin)
def learning_pillars(request):
    from competencies.models import Framework
    # Framework selector — accepts id or name
    fw_param = request.GET.get('fw', '')
    if fw_param.isdigit():
        active_fw_obj = Framework.objects.filter(id=fw_param).first()
    else:
        active_fw_obj = Framework.objects.filter(name=fw_param).first()
    if not active_fw_obj:
        active_fw_obj = Framework.objects.filter(is_fixed=True).first()
    is_csl = not active_fw_obj.is_fixed if active_fw_obj else False
    active_fw = active_fw_obj.name if active_fw_obj else 'FSL'

    # Active sub-pillar
    active_sp_param = request.GET.get('sp', '')

    pillars = Pillar.objects.prefetch_related('sub_pillars').filter(framework_ref=active_fw_obj)
    all_frameworks = Framework.objects.order_by('order').all()

    # Determine active sub-pillar
    sub_pillar = None
    if is_csl:
        # CSL+ uses sub-pillar ID
        if active_sp_param:
            try:
                sub_pillar = SubPillar.objects.get(id=active_sp_param, pillar__framework_ref=active_fw_obj)
            except (SubPillar.DoesNotExist, ValueError):
                pass
        if sub_pillar is None:
            sub_pillar = SubPillar.objects.filter(pillar__framework_ref=active_fw_obj).first()
    else:
        # Fixed framework (FSL) uses sp_number
        try:
            sp_num = int(active_sp_param) if active_sp_param else 1
        except (ValueError, TypeError):
            sp_num = 1
        sub_pillar = SubPillar.objects.filter(sp_number=sp_num, pillar__framework_ref=active_fw_obj).first()
        if sub_pillar is None:
            sub_pillar = SubPillar.objects.filter(pillar__framework_ref=active_fw_obj).first()

    competencies = sub_pillar.competencies.all() if sub_pillar else Competency.objects.none()
    is_kb_active = sub_pillar.pillar.is_kb if sub_pillar else False

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_competency':
            name   = request.POST.get('name', '').strip()
            desc   = request.POST.get('description', '').strip()
            stage  = request.POST.get('stage', '')
            status = request.POST.get('status', 'Active')
            if not name or not stage:
                messages.error(request, 'Name and Stage are required.')
            else:
                existing_count = sub_pillar.competencies.count()
                prefix = sub_pillar.code  # SP1, SP2... or KB1, KB2...
                code = f"{prefix}.C{existing_count + 1}"
                while Competency.objects.filter(code=code).exists():
                    existing_count += 1
                    code = f"{prefix}.C{existing_count + 1}"
                Competency.objects.create(
                    sub_pillar=sub_pillar, code=code,
                    name=name, description=desc, stage=stage, status=status,
                )
                messages.success(request, f'Competency "{code}" added successfully!')

        elif action == 'delete_competency':
            comp = get_object_or_404(Competency, id=request.POST.get('competency_id'), sub_pillar=sub_pillar)
            comp.delete()
            messages.success(request, 'Competency deleted.')

        elif action == 'edit_competency':
            comp   = get_object_or_404(Competency, id=request.POST.get('competency_id'), sub_pillar=sub_pillar)
            name   = request.POST.get('name', '').strip()
            desc   = request.POST.get('description', '').strip()
            stage  = request.POST.get('stage', '')
            status = request.POST.get('status', 'Active')
            if not name or not stage:
                messages.error(request, 'Name and Stage are required.')
            else:
                comp.name = name; comp.description = desc
                comp.stage = stage; comp.status = status
                comp.save()
                messages.success(request, f'Competency "{comp.code}" updated.')

        # Editable pillar actions (KB in FSL, or any CSL+ pillar)
        elif action == 'add_subpillar':
            p_id = request.POST.get('pillar_id')
            sp_name = request.POST.get('sp_name', '').strip()
            pillar_obj = get_object_or_404(Pillar, id=p_id)
            # Only allow for KB pillar (FSL) or any CSL+ pillar
            if not pillar_obj.is_kb and pillar_obj.framework_ref and pillar_obj.framework_ref.is_fixed:
                messages.error(request, 'Cannot add sub-pillars to this pillar.')
            elif not sp_name:
                messages.error(request, 'Sub-pillar name is required.')
            else:
                max_sp = SubPillar.objects.aggregate(models.Max('sp_number'))['sp_number__max'] or 17
                new_sp = SubPillar.objects.create(pillar=pillar_obj, sp_number=max_sp + 1, name=sp_name)
                messages.success(request, f'Sub-pillar "{sp_name}" added!')
                sp_param = new_sp.sp_number if not is_csl else new_sp.id
                return redirect(f"{request.path}?fw={active_fw_obj.id}&sp={sp_param}")

        elif action == 'edit_subpillar':
            sp_id = request.POST.get('sp_id')
            sp_name = request.POST.get('sp_name', '').strip()
            sp_obj = get_object_or_404(SubPillar, id=sp_id)
            if not sp_obj.pillar.is_kb and sp_obj.pillar.framework_ref and sp_obj.pillar.framework_ref.is_fixed:
                messages.error(request, 'This sub-pillar cannot be edited.')
            elif not sp_name:
                messages.error(request, 'Sub-pillar name is required.')
            else:
                sp_obj.name = sp_name
                sp_obj.save()
                messages.success(request, f'Sub-pillar renamed to "{sp_name}".')

        elif action == 'delete_subpillar':
            sp_id = request.POST.get('sp_id')
            sp_obj = get_object_or_404(SubPillar, id=sp_id)
            if not sp_obj.pillar.is_kb and sp_obj.pillar.framework_ref and sp_obj.pillar.framework_ref.is_fixed:
                messages.error(request, 'This sub-pillar cannot be deleted.')
            else:
                sp_obj.delete()
                messages.success(request, 'Sub-pillar deleted.')
                return redirect(f"{request.path}?fw={active_fw_obj.id}")

        elif action == 'rename_pillar':
            p_id = request.POST.get('pillar_id')
            pillar_obj = get_object_or_404(Pillar, id=p_id)
            if not pillar_obj.is_kb and pillar_obj.framework_ref and pillar_obj.framework_ref.is_fixed:
                messages.error(request, 'This pillar cannot be renamed.')
            else:
                new_name = request.POST.get('pillar_name', '').strip()
                if new_name:
                    pillar_obj.name = new_name
                    color = request.POST.get('pillar_color')
                    if color:
                        pillar_obj.color = color
                    pillar_obj.save()
                    messages.success(request, f'Pillar renamed to "{new_name}".')

        # CSL+ only: add/delete pillar
        elif action == 'add_pillar' and is_csl:
            name = request.POST.get('pillar_name', '').strip()
            color = request.POST.get('pillar_color', 'teal')
            if not name:
                messages.error(request, 'Pillar name is required.')
            else:
                max_order = Pillar.objects.filter(framework_ref=active_fw_obj).aggregate(models.Max('order'))['order__max'] or 0
                count = Pillar.objects.filter(framework_ref=active_fw_obj, is_kb=False).count()
                prefix = active_fw_obj.prefix.replace('-SP', '') if active_fw_obj.prefix.endswith('-SP') else active_fw_obj.prefix
                Pillar.objects.create(
                    name=name, number=f"{count + 1:02d}", color=color,
                    order=max_order + 1, framework_ref=active_fw_obj, is_kb=False,
                )
                messages.success(request, f'Pillar "{name}" added!')

        elif action == 'delete_pillar' and is_csl:
            p_id = request.POST.get('pillar_id')
            p_obj = get_object_or_404(Pillar, id=p_id, framework_ref=active_fw_obj)
            p_obj.delete()
            messages.success(request, 'Pillar deleted.')
            return redirect(f"{request.path}?fw=CSL")

        # Framework CRUD
        elif action == 'create_framework':
            fw_name = request.POST.get('name', '').strip()
            fw_prefix = request.POST.get('prefix', '').strip()
            if not fw_name or not fw_prefix:
                messages.error(request, 'Name and prefix are required.')
            elif Framework.objects.filter(name=fw_name).exists():
                messages.error(request, f'Framework "{fw_name}" already exists.')
            elif Framework.objects.filter(prefix=fw_prefix).exists():
                messages.error(request, f'Prefix "{fw_prefix}" already in use.')
            else:
                max_order = Framework.objects.aggregate(models.Max('order'))['order__max'] or 0
                new_fw = Framework.objects.create(name=fw_name, prefix=fw_prefix, is_fixed=False, order=max_order + 1)
                messages.success(request, f'Framework "{fw_name}" created!')
                return redirect(f"{request.path}?fw={new_fw.id}")

        elif action == 'edit_framework':
            fw_id = request.POST.get('fw_id')
            fw_obj = get_object_or_404(Framework, id=fw_id)
            if fw_obj.is_fixed:
                messages.error(request, 'Fixed frameworks cannot be edited.')
            else:
                fw_name = request.POST.get('name', '').strip()
                fw_prefix = request.POST.get('prefix', '').strip()
                if fw_name and fw_prefix:
                    fw_obj.name = fw_name
                    fw_obj.prefix = fw_prefix
                    fw_obj.save()
                    messages.success(request, f'Framework updated to "{fw_name}".')
                    return redirect(f"{request.path}?fw={fw_obj.id}")

        elif action == 'delete_framework':
            fw_id = request.POST.get('fw_id')
            fw_obj = get_object_or_404(Framework, id=fw_id)
            if fw_obj.is_fixed:
                messages.error(request, 'Fixed frameworks cannot be deleted.')
            else:
                fw_obj.delete()
                messages.success(request, 'Framework deleted.')
                return redirect(request.path)

        elif action == 'import_pillars':
            fw_id = request.POST.get('fw_id')
            source_id = request.POST.get('source_fw_id')
            fw_target = get_object_or_404(Framework, id=fw_id)
            source = get_object_or_404(Framework, id=source_id)
            if fw_target.is_fixed:
                messages.error(request, 'Cannot import into a fixed framework.')
            else:
                imported = 0
                max_sp = SubPillar.objects.aggregate(models.Max('sp_number'))['sp_number__max'] or 0
                for src_pillar in source.pillars.filter(is_kb=False):
                    max_order = Pillar.objects.filter(framework_ref=fw_target).aggregate(models.Max('order'))['order__max'] or 0
                    count = Pillar.objects.filter(framework_ref=fw_target, is_kb=False).count()
                    new_pillar = Pillar.objects.create(
                        name=src_pillar.name, number=f"{count + 1:02d}",
                        color=src_pillar.color, order=max_order + 1,
                        framework_ref=fw_target, is_kb=False,
                    )
                    for src_sp in src_pillar.sub_pillars.all():
                        max_sp += 1
                        SubPillar.objects.create(pillar=new_pillar, sp_number=max_sp, name=src_sp.name)
                    imported += 1
                messages.success(request, f'Imported {imported} pillars from "{source.name}" into "{fw_target.name}".')
                return redirect(f"{request.path}?fw={fw_target.id}")

        # Build redirect URL
        if sub_pillar:
            sp_param = sub_pillar.id if is_csl else sub_pillar.sp_number
            return redirect(f"{request.path}?fw={active_fw_obj.id}&sp={sp_param}")
        return redirect(f"{request.path}?fw={active_fw_obj.id}")

    context = {
        'pillars':        pillars,
        'sub_pillar':     sub_pillar,
        'competencies':   competencies,
        'active_fw':      active_fw,
        'active_fw_obj':  active_fw_obj,
        'all_frameworks': all_frameworks,
        'is_csl':         is_csl,
        'is_kb_active':   is_kb_active,
    }
    return render(request, 'superadmin/learning-pillars.html', context)


@login_required
@user_passes_test(is_superadmin)
def profiles_competencies(request):
    try:
        active_id = int(request.GET.get('profile', 1))
    except (ValueError, TypeError):
        active_id = 1

    profiles       = Profile.objects.prefetch_related('primary_competencies', 'secondary_competencies').all()
    active_profile = get_object_or_404(Profile, number=active_id)
    pillars        = Pillar.objects.prefetch_related('sub_pillars__competencies').filter(is_kb=False, framework_ref__is_fixed=True)
    all_comps      = Competency.objects.select_related('sub_pillar__pillar').filter(status='Active', sub_pillar__pillar__is_kb=False, sub_pillar__pillar__framework_ref__is_fixed=True).order_by('sub_pillar__sp_number', 'code')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_profile':
            primary_ids   = request.POST.getlist('primary_competencies')
            secondary_ids = request.POST.getlist('secondary_competencies')
            active_profile.primary_competencies.set(
                Competency.objects.filter(id__in=primary_ids)
            )
            active_profile.secondary_competencies.set(
                Competency.objects.filter(id__in=secondary_ids)
            )
            messages.success(request, f'Profile "{active_profile.name}" saved successfully!')

        elif action == 'rename_profile':
            new_name = request.POST.get('name', '').strip()
            if new_name:
                active_profile.name = new_name
                active_profile.save()
                messages.success(request, 'Profile renamed.')

        return redirect(f"{request.path}?profile={active_id}")

    context = {
        'profiles':       profiles,
        'active_profile': active_profile,
        'active_id':      active_id,
        'pillars':        pillars,
        'all_comps':      all_comps,
    }
    return render(request, 'superadmin/profiles-competencies.html', context)


@login_required
@user_passes_test(is_superadmin)
def project_assessment(request):
    try:
        active_id = int(request.GET.get('project', 0))
    except (ValueError, TypeError):
        active_id = 0

    projects = Project.objects.prefetch_related('assessments__competency_mappings__competency').all()

    active_project = None
    if active_id:
        active_project = get_object_or_404(Project, id=active_id)
    elif projects.exists():
        active_project = projects.first()
        active_id = active_project.id

    # Filter pillars/competencies by active project's framework (default FSL)
    from competencies.models import Framework
    active_fw_obj = active_project.framework_ref if active_project else Framework.objects.filter(is_fixed=True).first()
    if not active_fw_obj:
        active_fw_obj = Framework.objects.first()
    pillars   = Pillar.objects.prefetch_related('sub_pillars__competencies').filter(framework_ref=active_fw_obj)
    all_comps = Competency.objects.select_related('sub_pillar__pillar').filter(status='Active', sub_pillar__pillar__framework_ref=active_fw_obj).order_by('sub_pillar__sp_number', 'code')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_project':
            title        = request.POST.get('title', '').strip()
            project_type = request.POST.get('project_type', 'Life Form')
            grade        = request.POST.get('grade', '')
            framework_name = request.POST.get('framework', 'FSL')
            fw_obj = Framework.objects.filter(name=framework_name).first()
            seq_raw      = request.POST.get('sequence_number', '').strip()
            linked_id    = request.POST.get('linked_project', '').strip()
            if title and grade:
                linked = Project.objects.filter(id=linked_id).first() if linked_id else None
                seq    = int(seq_raw) if seq_raw.isdigit() else None
                p = Project.objects.create(
                    title=title, project_type=project_type, grade=grade,
                    framework_ref=fw_obj, sequence_number=seq, linked_project=linked
                )
                messages.success(request, f'Project "{p.title}" created!')
                return redirect(f"{request.path}?project={p.id}")
            else:
                messages.error(request, 'Title and Grade are required.')
                return redirect(request.path)

        elif action == 'save_project' and active_project:
            active_project.title        = request.POST.get('title', active_project.title).strip() or active_project.title
            active_project.project_type = request.POST.get('project_type', active_project.project_type)
            active_project.grade        = request.POST.get('grade', active_project.grade)
            fw_name = request.POST.get('framework', '')
            if fw_name:
                fw_save = Framework.objects.filter(name=fw_name).first()
                if fw_save:
                    active_project.framework_ref = fw_save
            active_project.status       = request.POST.get('status', active_project.status)
            seq_raw = request.POST.get('sequence_number', '').strip()
            active_project.sequence_number = int(seq_raw) if seq_raw.isdigit() else None
            linked_id = request.POST.get('linked_project', '').strip()
            active_project.linked_project  = Project.objects.filter(id=linked_id).first() if linked_id else None
            active_project.save()
            messages.success(request, 'Project saved!')

        elif action == 'add_assessment' and active_project:
            name            = request.POST.get('assessment_name', '').strip()
            assessment_type = request.POST.get('assessment_type', 'Written Assignment')
            if name:
                order = active_project.assessments.count()
                Assessment.objects.create(project=active_project, name=name, assessment_type=assessment_type, order=order)
                messages.success(request, f'Assessment "{name}" added!')
            else:
                messages.error(request, 'Assessment name is required.')

        elif action == 'save_assessment' and active_project:
            a = get_object_or_404(Assessment, id=request.POST.get('assessment_id'), project=active_project)
            a.name                    = request.POST.get('name', a.name).strip() or a.name
            a.assessment_type         = request.POST.get('assessment_type', a.assessment_type)
            a.output_descriptor       = request.POST.get('output_descriptor', '')
            a.additional_instructions = request.POST.get('additional_instructions', '')
            placement_raw = request.POST.get('placement_after_challenge', '').strip()
            a.placement_after_challenge = int(placement_raw) if placement_raw.isdigit() else None
            if request.FILES.get('rubric_file'):
                a.rubric_file = request.FILES['rubric_file']
            a.save()
            # Save competency mappings
            a.competency_mappings.all().delete()
            comp_ids   = request.POST.getlist('comp_id')
            comp_types = request.POST.getlist('comp_type')
            for i, (cid, ctype) in enumerate(zip(comp_ids, comp_types)):
                if cid:
                    try:
                        AssessmentCompetency.objects.create(
                            assessment=a,
                            competency=Competency.objects.get(id=cid),
                            comp_type=ctype or 'individual',
                            order=i
                        )
                    except Competency.DoesNotExist:
                        pass
            messages.success(request, f'Assessment "{a.name}" saved!')

        elif action == 'delete_assessment' and active_project:
            Assessment.objects.filter(id=request.POST.get('assessment_id'), project=active_project).delete()
            messages.success(request, 'Assessment deleted.')

        elif action == 'delete_project' and active_project:
            active_project.delete()
            messages.success(request, 'Project deleted.')
            return redirect(request.path)

        return redirect(f"{request.path}?project={active_id}")

    main_projects = Project.objects.exclude(project_type='Plug In').order_by('sequence_number', 'title')

    context = {
        'projects':        projects,
        'active_project':  active_project,
        'active_id':       active_id,
        'active_fw_obj':   active_fw_obj,
        'all_frameworks':  Framework.objects.order_by('order').all(),
        'pillars':         pillars,
        'all_comps':       all_comps,
        'main_projects':   main_projects,
    }
    return render(request, 'superadmin/project-assessment.html', context)


# ============================================================
# CUSTOM FRAMEWORK (CSL+) — Fully Editable Pillars
# ============================================================

@login_required
@user_passes_test(is_superadmin)
def custom_framework(request):
    """Fully editable Learning Pillars page for CSL+ framework."""

    # Active sub-pillar
    active_sp_id = request.GET.get('sp')  # Using ID since CSL+ sp_numbers may overlap later

    csl_pillars = Pillar.objects.prefetch_related('sub_pillars__competencies').filter(framework_ref__is_fixed=False)

    # Determine active sub-pillar
    sub_pillar = None
    competencies = Competency.objects.none()

    if active_sp_id:
        try:
            sub_pillar = SubPillar.objects.get(id=active_sp_id, pillar__framework_ref__is_fixed=False)
        except SubPillar.DoesNotExist:
            sub_pillar = None

    if sub_pillar is None:
        # Default to first CSL+ sub-pillar
        first_sp = SubPillar.objects.filter(pillar__framework_ref__is_fixed=False).first()
        sub_pillar = first_sp

    if sub_pillar:
        competencies = sub_pillar.competencies.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        # ── Pillar CRUD ──
        if action == 'add_pillar':
            name = request.POST.get('pillar_name', '').strip()
            color = request.POST.get('pillar_color', 'teal')
            if not name:
                messages.error(request, 'Pillar name is required.')
            else:
                max_order = Pillar.objects.filter(framework_ref__is_fixed=False).aggregate(models.Max('order'))['order__max'] or 0
                count = Pillar.objects.filter(framework_ref__is_fixed=False, is_kb=False).count()
                Pillar.objects.create(
                    name=name, number=f"{count + 1:02d}", color=color,
                    order=max_order + 1, framework_ref__is_fixed=False, is_kb=False,
                )
                messages.success(request, f'Pillar "{name}" added!')

        elif action == 'edit_pillar':
            p_id = request.POST.get('pillar_id')
            name = request.POST.get('pillar_name', '').strip()
            color = request.POST.get('pillar_color', 'teal')
            p_obj = get_object_or_404(Pillar, id=p_id, framework_ref__is_fixed=False)
            if name:
                p_obj.name = name
                p_obj.color = color
                p_obj.save()
                messages.success(request, f'Pillar renamed to "{name}".')

        elif action == 'delete_pillar':
            p_id = request.POST.get('pillar_id')
            p_obj = get_object_or_404(Pillar, id=p_id, framework_ref__is_fixed=False)
            p_name = p_obj.name
            p_obj.delete()
            messages.success(request, f'Pillar "{p_name}" deleted.')
            return redirect('custom_framework')

        # ── Sub-Pillar CRUD ──
        elif action == 'add_subpillar':
            p_id = request.POST.get('pillar_id')
            sp_name = request.POST.get('sp_name', '').strip()
            pillar_obj = get_object_or_404(Pillar, id=p_id, framework_ref__is_fixed=False)
            if not sp_name:
                messages.error(request, 'Sub-pillar name is required.')
            else:
                max_sp = SubPillar.objects.aggregate(models.Max('sp_number'))['sp_number__max'] or 17
                new_sp = SubPillar.objects.create(pillar=pillar_obj, sp_number=max_sp + 1, name=sp_name)
                messages.success(request, f'Sub-pillar "{sp_name}" added!')
                return redirect(f"{request.path}?sp={new_sp.id}")

        elif action == 'edit_subpillar':
            sp_id = request.POST.get('sp_id')
            sp_name = request.POST.get('sp_name', '').strip()
            sp_obj = get_object_or_404(SubPillar, id=sp_id, pillar__framework_ref__is_fixed=False)
            if sp_name:
                sp_obj.name = sp_name
                sp_obj.save()
                messages.success(request, f'Sub-pillar renamed to "{sp_name}".')

        elif action == 'delete_subpillar':
            sp_id = request.POST.get('sp_id')
            sp_obj = get_object_or_404(SubPillar, id=sp_id, pillar__framework_ref__is_fixed=False)
            sp_obj.delete()
            messages.success(request, 'Sub-pillar deleted.')
            return redirect('custom_framework')

        # ── Competency CRUD ──
        elif action == 'add_competency':
            if sub_pillar:
                name = request.POST.get('name', '').strip()
                desc = request.POST.get('description', '').strip()
                stage = request.POST.get('stage', '')
                status = request.POST.get('status', 'Active')
                if not name or not stage:
                    messages.error(request, 'Name and Stage are required.')
                else:
                    prefix = sub_pillar.code
                    existing_count = sub_pillar.competencies.count()
                    code = f"{prefix}.C{existing_count + 1}"
                    while Competency.objects.filter(code=code).exists():
                        existing_count += 1
                        code = f"{prefix}.C{existing_count + 1}"
                    Competency.objects.create(
                        sub_pillar=sub_pillar, code=code,
                        name=name, description=desc, stage=stage, status=status,
                    )
                    messages.success(request, f'Competency "{code}" added!')

        elif action == 'delete_competency':
            if sub_pillar:
                comp = get_object_or_404(Competency, id=request.POST.get('competency_id'), sub_pillar=sub_pillar)
                comp.delete()
                messages.success(request, 'Competency deleted.')

        elif action == 'edit_competency':
            if sub_pillar:
                comp = get_object_or_404(Competency, id=request.POST.get('competency_id'), sub_pillar=sub_pillar)
                name = request.POST.get('name', '').strip()
                desc = request.POST.get('description', '').strip()
                stage = request.POST.get('stage', '')
                status = request.POST.get('status', 'Active')
                if not name or not stage:
                    messages.error(request, 'Name and Stage are required.')
                else:
                    comp.name = name
                    comp.description = desc
                    comp.stage = stage
                    comp.status = status
                    comp.save()
                    messages.success(request, f'Competency "{comp.code}" updated.')

        sp_redirect = sub_pillar.id if sub_pillar else ''
        return redirect(f"{request.path}?sp={sp_redirect}" if sp_redirect else 'custom_framework')

    context = {
        'csl_pillars':  csl_pillars,
        'sub_pillar':   sub_pillar,
        'competencies': competencies,
    }
    return render(request, 'superadmin/custom-framework.html', context)


# ============================================================
# MANAGE FRAMEWORKS
# ============================================================

@login_required
@user_passes_test(is_superadmin)
def manage_frameworks(request):
    """CRUD page for skill frameworks."""
    from competencies.models import Framework

    frameworks = Framework.objects.order_by('order').all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            prefix = request.POST.get('prefix', '').strip()
            if not name or not prefix:
                messages.error(request, 'Name and prefix are required.')
            elif Framework.objects.filter(name=name).exists():
                messages.error(request, f'Framework "{name}" already exists.')
            elif Framework.objects.filter(prefix=prefix).exists():
                messages.error(request, f'Prefix "{prefix}" already in use.')
            else:
                max_order = Framework.objects.aggregate(models.Max('order'))['order__max'] or 0
                Framework.objects.create(name=name, prefix=prefix, is_fixed=False, order=max_order + 1)
                messages.success(request, f'Framework "{name}" created! Go to Learning Pillars to add pillars.')

        elif action == 'edit':
            fw_id = request.POST.get('fw_id')
            fw = get_object_or_404(Framework, id=fw_id)
            if fw.is_fixed:
                messages.error(request, 'Fixed frameworks cannot be edited.')
            else:
                name = request.POST.get('name', '').strip()
                prefix = request.POST.get('prefix', '').strip()
                if not name or not prefix:
                    messages.error(request, 'Name and prefix are required.')
                elif Framework.objects.filter(name=name).exclude(id=fw.id).exists():
                    messages.error(request, f'Framework "{name}" already exists.')
                elif Framework.objects.filter(prefix=prefix).exclude(id=fw.id).exists():
                    messages.error(request, f'Prefix "{prefix}" already in use.')
                else:
                    fw.name = name
                    fw.prefix = prefix
                    fw.save()
                    messages.success(request, f'Framework updated to "{name}".')

        elif action == 'delete':
            fw_id = request.POST.get('fw_id')
            fw = get_object_or_404(Framework, id=fw_id)
            if fw.is_fixed:
                messages.error(request, 'Fixed frameworks cannot be deleted.')
            else:
                fw_name = fw.name
                fw.delete()
                messages.success(request, f'Framework "{fw_name}" deleted.')

        elif action == 'import_pillars':
            fw_id = request.POST.get('fw_id')
            source_id = request.POST.get('source_fw_id')
            fw = get_object_or_404(Framework, id=fw_id)
            source = get_object_or_404(Framework, id=source_id)
            if fw.is_fixed:
                messages.error(request, 'Cannot import into a fixed framework.')
            else:
                imported = 0
                for src_pillar in source.pillars.filter(is_kb=False):
                    max_order = Pillar.objects.filter(framework_ref=fw).aggregate(models.Max('order'))['order__max'] or 0
                    count = Pillar.objects.filter(framework_ref=fw, is_kb=False).count()
                    new_pillar = Pillar.objects.create(
                        name=src_pillar.name, number=f"{count + 1:02d}",
                        color=src_pillar.color, order=max_order + 1,
                        framework_ref=fw, is_kb=False,
                    )
                    max_sp = SubPillar.objects.aggregate(models.Max('sp_number'))['sp_number__max'] or 0
                    for src_sp in src_pillar.sub_pillars.all():
                        max_sp += 1
                        SubPillar.objects.create(pillar=new_pillar, sp_number=max_sp, name=src_sp.name)
                    imported += 1
                messages.success(request, f'Imported {imported} pillars from "{source.name}" into "{fw.name}".')

        return redirect('manage_frameworks')

    context = {
        'frameworks': frameworks,
    }
    return render(request, 'superadmin/manage-frameworks.html', context)


# ─────────────────────────────────────────────
# ESL Products (Add ESL Product — Slide 7)
# ─────────────────────────────────────────────

BOARD_CHOICES_LIST = [
    ('CBSE', 'CBSE'), ('ICSE', 'ICSE'), ('IGCSE', 'IGCSE'),
    ('IB', 'IB'), ('State Board', 'State Board'), ('Other', 'Other'),
]


@login_required
@user_passes_test(is_superadmin)
def esl_products(request):
    """List all ESL Products."""
    from competencies.models import ESLProduct
    from django.db.models import Count
    products = ESLProduct.objects.annotate(
        project_count=Count('projects', distinct=True),
        session_count=Count('projects__sessions', distinct=True),
    ).order_by('-created_at')
    return render(request, 'superadmin/esl-products.html', {'products': products})


@login_required
@user_passes_test(is_superadmin)
def esl_product_add(request):
    """Add new ESL Product."""
    from competencies.models import ESLProduct, ProductProject, ProjectSession

    if request.method == 'POST':
        data = request.POST
        try:
            product = ESLProduct.objects.create(
                name=data.get('name', ''),
                description=data.get('description', ''),
                competencies_description=data.get('competencies_description', ''),
                applicable_grades=[int(g) for g in data.getlist('grades')],
                applicable_boards=data.getlist('boards'),
                status=data.get('status', 'Draft'),
            )
            if 'program_document' in request.FILES:
                product.program_document = request.FILES['program_document']
                product.save()

            # Save projects & sessions from JSON
            projects_json = data.get('projects_json', '[]')
            _save_product_projects(product, projects_json)

            messages.success(request, f'ESL Product "{product.name}" created successfully!')
            return redirect('esl_products')
        except Exception as e:
            messages.error(request, f'Error creating product: {str(e)}')

    return render(request, 'superadmin/esl-products.html', {
        'form_mode': 'add',
        'product': None,
        'grade_list': list(range(1, 13)),
        'board_choices': BOARD_CHOICES_LIST,
        'selected_grades': [],
        'selected_boards': [],
        'projects_json': '[]',
    })


@login_required
@user_passes_test(is_superadmin)
def esl_product_edit(request, product_id):
    """Edit ESL Product."""
    from competencies.models import ESLProduct, ProductProject, ProjectSession

    product = get_object_or_404(ESLProduct, id=product_id)

    if request.method == 'POST':
        data = request.POST
        try:
            product.name = data.get('name', product.name)
            product.description = data.get('description', '')
            product.competencies_description = data.get('competencies_description', '')
            product.applicable_grades = [int(g) for g in data.getlist('grades')]
            product.applicable_boards = data.getlist('boards')
            product.status = data.get('status', product.status)
            if 'program_document' in request.FILES:
                product.program_document = request.FILES['program_document']
            product.save()

            # Re-save projects & sessions
            projects_json = data.get('projects_json', '[]')
            _save_product_projects(product, projects_json)

            messages.success(request, f'ESL Product "{product.name}" updated successfully!')
            return redirect('esl_products')
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')

    # Build existing projects JSON for the form
    existing_projects = []
    for proj in product.projects.order_by('project_number'):
        sessions = []
        for sess in proj.sessions.order_by('session_number'):
            sessions.append({
                'session_number': sess.session_number,
                'title': sess.title,
                'description': sess.description,
            })
        existing_projects.append({
            'project_number': proj.project_number,
            'name': proj.name,
            'description': proj.description,
            'grade': proj.grade,
            'sessions': sessions,
        })

    return render(request, 'superadmin/esl-products.html', {
        'form_mode': 'edit',
        'product': product,
        'grade_list': list(range(1, 13)),
        'board_choices': BOARD_CHOICES_LIST,
        'selected_grades': product.applicable_grades or [],
        'selected_boards': product.applicable_boards or [],
        'projects_json': json.dumps(existing_projects),
    })


@login_required
@user_passes_test(is_superadmin)
def esl_product_delete(request, product_id):
    """Delete ESL Product."""
    from competencies.models import ESLProduct
    product = get_object_or_404(ESLProduct, id=product_id)
    name = product.name
    product.delete()
    messages.success(request, f'ESL Product "{name}" deleted.')
    return redirect('esl_products')


def _save_product_projects(product, projects_json_str):
    """Helper: save projects and sessions from JSON string."""
    from competencies.models import ProductProject, ProjectSession
    try:
        projects_data = json.loads(projects_json_str) if projects_json_str else []
    except (json.JSONDecodeError, TypeError):
        projects_data = []

    # Clear existing and recreate
    product.projects.all().delete()
    for proj_data in projects_data:
        if not proj_data.get('name', '').strip():
            continue
        proj = ProductProject.objects.create(
            esl_product=product,
            project_number=proj_data.get('project_number', 1),
            name=proj_data['name'].strip(),
            description=proj_data.get('description', ''),
            grade=proj_data.get('grade', ''),
        )
        for sess_data in proj_data.get('sessions', []):
            if not sess_data.get('title', '').strip():
                continue
            ProjectSession.objects.create(
                product_project=proj,
                session_number=sess_data.get('session_number', 1),
                title=sess_data['title'].strip(),
                description=sess_data.get('description', ''),
            )


# ─────────────────────────────────────────────
# Announcements
# ─────────────────────────────────────────────

@login_required
@user_passes_test(is_superadmin)
def announcements_list(request):
    """List all announcements."""
    announcements = Announcement.objects.all()
    return render(request, 'superadmin/announcements.html', {
        'announcements': announcements,
        'list_mode': True,
    })


@login_required
@user_passes_test(is_superadmin)
def announcement_add(request):
    """Add a new announcement."""
    if request.method == 'POST':
        try:
            ann_type = request.POST.get('announcement_type', 'event')
            ann = Announcement(announcement_type=ann_type)

            # Common fields for all types
            esl_id = request.POST.get('esl_product')
            if esl_id:
                ann.esl_product = ESLProduct.objects.filter(id=esl_id).first()
            ann.applicable_grades = [int(g) for g in request.POST.getlist('applicable_grades')]
            ann.is_published = request.POST.get('action') == 'publish'

            # Type-specific fields
            if ann_type == 'event':
                ann.event_name = request.POST.get('event_name', '')
                ann.event_date = request.POST.get('event_date') or None
                ann.event_description = request.POST.get('event_description', '')
                ann.event_link = request.POST.get('event_link', '')
                ann.publish_to = request.POST.getlist('publish_to')

            elif ann_type == 'newsletter':
                ann.newsletter_date = request.POST.get('newsletter_date') or None
                ann.newsletter_month = request.POST.get('newsletter_month', '')
                ann.newsletter_weblink = request.POST.get('newsletter_weblink', '')
                if 'newsletter_file' in request.FILES:
                    ann.newsletter_file = request.FILES['newsletter_file']

            elif ann_type == 'success_story':
                ann.story_student_name = request.POST.get('story_student_name', '')
                ann.story_grade = request.POST.get('story_grade', '')
                story_school_id = request.POST.get('story_school')
                if story_school_id:
                    ann.story_school = School.objects.filter(id=story_school_id).first()
                ann.story_text = request.POST.get('story_text', '')[:500]
                ann.story_youtube_link = request.POST.get('story_youtube_link', '')
                if 'story_photo_1' in request.FILES:
                    ann.story_photo_1 = request.FILES['story_photo_1']
                if 'story_photo_2' in request.FILES:
                    ann.story_photo_2 = request.FILES['story_photo_2']

            ann.save()
            # M2M after save
            school_ids = request.POST.getlist('applicable_schools')
            if school_ids:
                ann.applicable_schools.set(School.objects.filter(id__in=school_ids))

            messages.success(request, 'Announcement created successfully!')
            return redirect('announcements_list')
        except Exception as e:
            messages.error(request, f'Error creating announcement: {str(e)}')

    schools = School.objects.filter(is_active=True)
    esl_products = ESLProduct.objects.all()
    return render(request, 'superadmin/announcements.html', {
        'form_mode': 'add',
        'schools': schools,
        'esl_products': esl_products,
        'grade_list': list(range(1, 13)),
        'month_list': ['January','February','March','April','May','June','July','August','September','October','November','December'],
    })


@login_required
@user_passes_test(is_superadmin)
def announcement_edit(request, ann_id):
    """Edit an existing announcement."""
    ann = get_object_or_404(Announcement, id=ann_id)

    if request.method == 'POST':
        try:
            ann_type = ann.announcement_type

            if ann_type == 'event':
                esl_id = request.POST.get('esl_product')
                ann.esl_product = ESLProduct.objects.filter(id=esl_id).first() if esl_id else None
                ann.applicable_grades = [int(g) for g in request.POST.getlist('applicable_grades')]
                ann.event_name = request.POST.get('event_name', '')
                ann.event_date = request.POST.get('event_date') or None
                ann.event_description = request.POST.get('event_description', '')
                ann.event_link = request.POST.get('event_link', '')
                ann.publish_to = request.POST.getlist('publish_to')
                ann.is_published = request.POST.get('is_published') == 'on'
                ann.save()
                school_ids = request.POST.getlist('applicable_schools')
                ann.applicable_schools.set(School.objects.filter(id__in=school_ids))

            elif ann_type == 'newsletter':
                ann.newsletter_date = request.POST.get('newsletter_date') or None
                ann.newsletter_month = request.POST.get('newsletter_month', '')
                ann.newsletter_weblink = request.POST.get('newsletter_weblink', '')
                ann.is_published = request.POST.get('is_published') == 'on'
                if 'newsletter_file' in request.FILES:
                    ann.newsletter_file = request.FILES['newsletter_file']
                ann.save()

            elif ann_type == 'success_story':
                ann.story_student_name = request.POST.get('story_student_name', '')
                ann.story_grade = request.POST.get('story_grade', '')
                story_school_id = request.POST.get('story_school')
                ann.story_school = School.objects.filter(id=story_school_id).first() if story_school_id else None
                ann.story_text = request.POST.get('story_text', '')[:500]
                ann.story_youtube_link = request.POST.get('story_youtube_link', '')
                ann.is_published = request.POST.get('is_published') == 'on'
                if 'story_photo_1' in request.FILES:
                    ann.story_photo_1 = request.FILES['story_photo_1']
                if 'story_photo_2' in request.FILES:
                    ann.story_photo_2 = request.FILES['story_photo_2']
                ann.save()

            messages.success(request, 'Announcement updated successfully!')
            return redirect('announcements_list')
        except Exception as e:
            messages.error(request, f'Error updating announcement: {str(e)}')

    schools = School.objects.filter(is_active=True)
    esl_products = ESLProduct.objects.all()
    return render(request, 'superadmin/announcements.html', {
        'form_mode': 'edit',
        'ann': ann,
        'schools': schools,
        'esl_products': esl_products,
        'grade_list': list(range(1, 13)),
        'selected_schools': list(ann.applicable_schools.values_list('id', flat=True)) if ann.announcement_type == 'event' else [],
        'selected_grades': ann.applicable_grades or [],
        'selected_publish_to': ann.publish_to or [],
        'month_list': ['January','February','March','April','May','June','July','August','September','October','November','December'],
    })


@login_required
@user_passes_test(is_superadmin)
def announcement_delete(request, ann_id):
    """Delete an announcement."""
    ann = get_object_or_404(Announcement, id=ann_id)
    ann.delete()
    messages.success(request, 'Announcement deleted.')
    return redirect('announcements_list')


@login_required
@user_passes_test(is_superadmin)
def api_schools_by_product(request):
    """AJAX: return schools that have a skill_program matching the given ESL product."""
    product_id = request.GET.get('product_id', '')
    if not product_id:
        # No product selected — return all active schools
        schools = School.objects.filter(is_active=True).values('id', 'school_name')
        return JsonResponse({'schools': list(schools)})

    try:
        product = ESLProduct.objects.get(id=product_id)
    except ESLProduct.DoesNotExist:
        return JsonResponse({'schools': []})

    # Map product name to skill_program codes
    name_lower = product.name.lower()
    if 'future' in name_lower or 'fsl' in name_lower:
        codes = ['fsl']
    elif 'csl' in name_lower and 'plus' in name_lower:
        codes = ['csl_plus_pc', 'csl_plus_tc']
    elif 'csl' in name_lower and 'foundation' in name_lower:
        codes = ['csl_foundation_pc', 'csl_foundation']
    else:
        # Fallback — try exact match or return all
        codes = []

    if codes:
        schools = School.objects.filter(is_active=True, skill_program__in=codes).values('id', 'school_name')
    else:
        # No matching codes — no schools for this product
        schools = School.objects.none()

    return JsonResponse({'schools': list(schools)})
