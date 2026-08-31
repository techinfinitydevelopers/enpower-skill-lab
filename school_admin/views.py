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
    from competencies import report_panels

    # Resolve the admin's own school. Guard if missing -> empty state, no crash.
    try:
        profile = SchoolAdmin.objects.select_related('school').get(user=request.user)
        school = profile.school
    except SchoolAdmin.DoesNotExist:
        profile = None
        school = None

    # The four grade-wise panels (presentation slide 52), from the shared
    # component every role's report screens use, scoped to this one school.
    panels = report_panels.build([school.id], month=(request.GET.get('month') or None)) if school else None
    total_students = panels['distribution']['total'] if panels else 0


    context = {
        'page_title': 'Dashboard',
        'school': school,
        'school_admin_profile': profile,
        'total_students': total_students,
        'panels': panels,
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


@login_required
@user_passes_test(is_school_admin)
def school_admin_announcements(request):
    """Announcements targeted to this School Admin (scoped to their school)."""
    from competencies.announcements import announcements_for_user
    announcements = announcements_for_user(request.user)
    announcements.sort(key=lambda a: a.created_at, reverse=True)
    return render(request, 'school_admin/announcements.html', {'announcements': announcements})
