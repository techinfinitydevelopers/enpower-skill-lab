from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib import messages

# Check if user is school admin
def is_school_admin(user):
    return user.is_authenticated and user.role == 'SCHOOL_ADMIN'

@login_required
@user_passes_test(is_school_admin)
def school_admin_dashboard(request):
    """School Admin Dashboard View (view-only, scoped to admin's own school).

    Wires PPT slides 50-51 to real per-grade data via attendance.services helpers.
    Additive only: no model/migration changes.
    """
    from .models import SchoolAdmin
    from attendance.services import (
        grade_wise_distribution,
        grade_wise_attendance,
        grade_wise_project_completion,
        grade_wise_top_profiles,
    )

    # Resolve the admin's own school. Guard if missing -> empty state, no crash.
    try:
        profile = SchoolAdmin.objects.select_related('school').get(user=request.user)
        school = profile.school
    except SchoolAdmin.DoesNotExist:
        profile = None
        school = None

    distribution = []
    attendance = []
    project_completion = []
    top_profiles = []
    total_students = 0

    if school is not None:
        distribution = grade_wise_distribution(school)
        attendance = grade_wise_attendance(school)
        project_completion = grade_wise_project_completion(school)
        top_profiles = grade_wise_top_profiles(school)
        total_students = sum(row['count'] for row in distribution)

    context = {
        'page_title': 'Dashboard',
        'school': school,
        'school_admin_profile': profile,
        'total_students': total_students,
        'grade_distribution': distribution,
        'grade_attendance': attendance,
        'grade_project_completion': project_completion,
        'grade_top_profiles': top_profiles,
    }
    return render(request, 'school_admin/dashboard.html', context)

@login_required
def school_admin_logout(request):
    """Logout view for school admin"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

@login_required
@user_passes_test(is_school_admin)
def school_admin_profile(request):
    """School Admin Profile View"""
    from .models import SchoolAdmin
    
    # Get profile for the user
    try:
        profile = SchoolAdmin.objects.get(user=request.user)
        school = profile.school
    except SchoolAdmin.DoesNotExist:
        profile = None
        school = None
    
    context = {
        'page_title': 'My Profile',
        'profile': profile,
        'school': school,
    }
    return render(request, 'school_admin/profile.html', context)

@login_required
@user_passes_test(is_school_admin)
def school_admin_profile_update(request):
    """School Admin Profile Update View"""
    if request.method == 'POST':
        from .models import SchoolAdmin
        
        try:
            profile = SchoolAdmin.objects.get(user=request.user)
            
            # Update profile fields
            profile.full_name = request.POST.get('full_name', profile.full_name)
            profile.phone = request.POST.get('phone', profile.phone)
            profile.gender = request.POST.get('gender', profile.gender)
            
            date_of_birth = request.POST.get('date_of_birth')
            if date_of_birth:
                profile.date_of_birth = date_of_birth
            
            # Handle profile photo upload
            if 'profile_photo' in request.FILES:
                profile.profile_photo = request.FILES['profile_photo']
            
            profile.save()
            messages.success(request, 'Profile updated successfully!')
        except SchoolAdmin.DoesNotExist:
            messages.error(request, 'Profile not found.')
        
    return redirect('school_admin_profile')

@login_required
@user_passes_test(is_school_admin)
def school_admin_change_password(request):
    """School Admin Change Password View"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # Validate current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('school_admin_change_password')

        # Validate new password
        if not new_password:
            messages.error(request, 'New password is required.')
            return redirect('school_admin_change_password')

        # Check password requirements
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return redirect('school_admin_change_password')

        # Validate confirm password
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('school_admin_change_password')

        # Check if new password is same as current
        if current_password == new_password:
            messages.error(request, 'New password must be different from current password.')
            return redirect('school_admin_change_password')

        try:
            # Update password
            request.user.set_password(new_password)
            request.user.save()

            # Update SchoolAdmin profile if exists
            from .models import SchoolAdmin
            from django.utils import timezone
            try:
                profile = SchoolAdmin.objects.get(user=request.user)
                profile.password_changed = True
                profile.last_password_change = timezone.now()

                # Activate account if it was pending (first login password change)
                if profile.account_status == 'pending':
                    profile.account_status = 'active'
                    profile.mark_first_login()

                profile.save()
            except SchoolAdmin.DoesNotExist:
                pass

            messages.success(request, 'Your password has been changed successfully!')

            # Keep user logged in after password change
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)

            return redirect('school_admin_change_password')

        except Exception as e:
            messages.error(request, f'Error changing password: {str(e)}')
            return redirect('school_admin_change_password')

    # GET request - render the change password page
    context = {
        'page_title': 'Change Password',
    }
    return render(request, 'school_admin/change_password.html', context)

@login_required
@user_passes_test(is_school_admin)
def school_admin_onboard_student(request):
    """View for school admin to onboard new students to their school"""
    from schools.models import School
    from .models import SchoolAdmin

    # Get the school admin's school
    try:
        school_admin_profile = SchoolAdmin.objects.get(user=request.user)
        school = school_admin_profile.school
    except SchoolAdmin.DoesNotExist:
        messages.error(request, 'School admin profile not found.')
        return redirect('school_admin_dashboard')

    if not school:
        messages.error(request, 'No school assigned to your account. Please contact the administrator.')
        return redirect('school_admin_dashboard')

    if request.method == 'POST':
        try:
            from student.models import Student
            from django.contrib.auth import get_user_model
            from django.core.mail import send_mail
            from django.conf import settings
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

            # Automatically assign to school admin's school
            student.school = school

            # A. Basic Information
            if 'student_photo' in request.FILES:
                student.student_photo = request.FILES['student_photo']
            student.first_name = request.POST.get('first_name', '')
            student.middle_name = request.POST.get('middle_name', '')
            student.last_name = request.POST.get('last_name', '')
            student.gender = request.POST.get('gender', '')
            date_of_birth = request.POST.get('date_of_birth', '')
            enrollment_date = request.POST.get('enrollment_date', '')
            gr_number = request.POST.get('gr_number', '')
            if not date_of_birth or not enrollment_date:
                messages.error(request, 'Date of birth and enrollment date are required')
                return redirect('school_admin_onboard_student')
            if not gr_number:
                messages.error(request, 'GR number is required')
                return redirect('school_admin_onboard_student')
            student.date_of_birth = date_of_birth
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
            student.gr_number = gr_number
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
            student.enrollment_date = enrollment_date
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
                return redirect('school_admin_onboard_student')

            # Generate temporary password
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

Welcome to ENpower Skill Lab! Your student account has been created successfully by {school.school_name}.

Here are your login credentials:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email: {email}
🔑 Temporary Password: {temp_password}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 Login URL: http://127.0.0.1:8000/login/

Skill Lab ID: {skill_lab_reg_id}
School: {school.school_name}
Class: {student.student_class} - {student.division}
Role: Student

⚠️ IMPORTANT: Please change your password after your first login for security purposes.

If you have any questions, please contact your teacher or the school administration.

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

            return redirect('school_admin_dashboard')

        except Exception as e:
            messages.error(request, f'Error adding student: {str(e)}')
            return redirect('school_admin_onboard_student')

    # GET request - render the onboarding form
    context = {
        'school': school,
        'page_title': 'Add New Student',
    }
    return render(request, 'school_admin/onboard-student.html', context)

@login_required
@user_passes_test(is_school_admin)
def school_admin_student_list(request):
    """View to display list of students for the school admin's school"""
    from student.models import Student
    from .models import SchoolAdmin
    import random

    # Get the school admin's school
    try:
        school_admin_profile = SchoolAdmin.objects.get(user=request.user)
        school = school_admin_profile.school
    except SchoolAdmin.DoesNotExist:
        messages.error(request, 'School admin profile not found.')
        return redirect('school_admin_dashboard')

    if not school:
        messages.error(request, 'No school assigned to your account. Please contact the administrator.')
        return redirect('school_admin_dashboard')

    # Get all students for this school only
    students = Student.objects.filter(school=school).order_by('-created_at')

    # Add badge colors for students without photos
    badge_colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#a855f7']
    for student in students:
        student.badge_color = random.choice(badge_colors)

    context = {
        'students': students,
        'school': school,
        'page_title': 'Student List',
    }
    return render(request, 'school_admin/students-list.html', context)


@login_required
@user_passes_test(is_school_admin)
def school_admin_onboard_parent(request):
    """View for school admin to onboard new parents to their school"""
    from schools.models import School
    from .models import SchoolAdmin
    from parent.models import Parent
    from student.models import Student
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings
    import secrets
    import string

    # Get the school admin's school
    try:
        school_admin_profile = SchoolAdmin.objects.get(user=request.user)
        school = school_admin_profile.school
    except SchoolAdmin.DoesNotExist:
        messages.error(request, 'School admin profile not found.')
        return redirect('school_admin_dashboard')

    if not school:
        messages.error(request, 'No school assigned to your account. Please contact the administrator.')
        return redirect('school_admin_dashboard')

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
                return redirect('school_admin_onboard_parent')

            # Generate temporary password
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

            # Link to students (ManyToMany relationship) - only students from this school
            student_ids = request.POST.getlist('students')
            linked_students = []
            if student_ids:
                students = Student.objects.filter(id__in=student_ids, school=school)
                parent.students.set(students)
                linked_students = [f"{s.first_name} {s.last_name}" for s in students]

            # Send welcome email with credentials
            try:
                email_subject = 'Welcome to ENpower Skill Lab - Your Login Credentials'
                students_text = ', '.join(linked_students) if linked_students else 'Not yet linked'
                email_body = f"""
Dear {parent.full_name},

Welcome to ENpower Skill Lab! Your parent account has been created successfully for {school.school_name}.

Here are your login credentials:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 Email: {email}
🔑 Temporary Password: {temp_password}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 Login URL: http://127.0.0.1:8000/login/

Parent ID: {parent.parent_id}
School: {school.school_name}
Linked Student(s): {students_text}
Role: Parent/Guardian

⚠️ IMPORTANT: Please change your password after your first login for security purposes.

You can use the parent portal to:
- Track your child's progress
- View attendance records
- Communicate with teachers
- Access reports and certificates

If you have any questions, please contact the school administration.

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

            return redirect('school_admin_dashboard')

        except Exception as e:
            messages.error(request, f'Error onboarding parent: {str(e)}')

    # GET request - pass only students from this school to template
    students = Student.objects.filter(school=school).order_by('first_name', 'last_name')
    context = {
        'students': students,
        'school': school,
    }
    return render(request, 'school_admin/onboard-parent.html', context)


@login_required
@user_passes_test(is_school_admin)
def school_admin_parent_list(request):
    """View to display list of all parents for this school"""
    from schools.models import School
    from .models import SchoolAdmin
    from parent.models import Parent
    import random

    # Get the school admin's school
    try:
        school_admin_profile = SchoolAdmin.objects.get(user=request.user)
        school = school_admin_profile.school
    except SchoolAdmin.DoesNotExist:
        messages.error(request, 'School admin profile not found.')
        return redirect('school_admin_dashboard')

    if not school:
        messages.error(request, 'No school assigned to your account. Please contact the administrator.')
        return redirect('school_admin_dashboard')

    # Get all parents for this school only (filter through students' school)
    parents = Parent.objects.filter(students__school=school).prefetch_related('students').distinct().order_by('-created_at')

    # Add badge color for each parent (initials and children are already properties in Parent model)
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#f97316', '#6366f1', '#ec4899', '#14b8a6']
    for parent in parents:
        # Assign badge color based on first character
        if parent.full_name:
            parent.badge_color = colors[ord(parent.full_name[0]) % len(colors)]
        else:
            parent.badge_color = random.choice(colors)

    context = {
        'parents': parents,
        'school': school,
        'total_parents': parents.count(),
        'active_parents': parents.filter(account_status='active').count(),
        'pending_parents': parents.filter(account_status='pending').count(),
    }
    return render(request, 'school_admin/parent-list.html', context)
