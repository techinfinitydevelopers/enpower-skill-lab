from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib import messages
from django.http import JsonResponse
from .models import Teacher
from student.models import Student
from lms.models import Lesson
import random


def is_teacher(user):
    """Check if user is a teacher/thinking coach"""
    return user.is_authenticated and hasattr(user, 'role') and user.role == 'THINKING_COACH'


@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    """Teacher dashboard view"""
    from competencies.models import STAGE_CHOICES

    teacher_profile = None
    if hasattr(request.user, 'teacher_profile'):
        teacher_profile = request.user.teacher_profile

    context = {
        'teacher_profile': teacher_profile,
        'stage_choices': STAGE_CHOICES,
    }
    return render(request, 'teacher/dashboard.html', context)


@login_required
@user_passes_test(is_teacher)
def api_projects_by_grade(request):
    """AJAX: return active projects for a given grade/stage, filtered by teacher's school framework"""
    from competencies.models import Project
    grade = request.GET.get('grade', '')
    if not grade:
        return JsonResponse({'projects': []})

    # Get teacher's school framework
    fw_obj = None
    if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
        school = request.user.teacher_profile.school
        if school and school.framework_ref:
            fw_obj = school.framework_ref

    qs = Project.objects.filter(grade=grade, status='Active')
    if fw_obj:
        qs = qs.filter(framework_ref=fw_obj)
    projects = list(
        qs
        .exclude(project_type='Plug In')
        .order_by('title')
        .values('id', 'title', 'project_type')
    )
    return JsonResponse({'projects': projects})


@login_required
@user_passes_test(is_teacher)
def api_project_details(request):
    """AJAX: return profiles and assessments for a project"""
    from competencies.models import Project, Profile
    project_id = request.GET.get('project_id', '')
    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Not found'}, status=404)

    assessments = list(
        project.assessments.order_by('order', 'id')
        .values('id', 'name', 'assessment_type', 'output_descriptor', 'placement_after_challenge')
    )

    # Profiles whose competencies are mapped to this project's assessments
    comp_ids = list(
        project.assessments
        .values_list('competency_mappings__competency_id', flat=True)
        .distinct()
    )
    comp_ids = [c for c in comp_ids if c is not None]

    if comp_ids:
        primary_ids = set(Profile.objects.filter(primary_competencies__id__in=comp_ids).values_list('id', flat=True))
        secondary_ids = set(Profile.objects.filter(secondary_competencies__id__in=comp_ids).values_list('id', flat=True))
        all_ids = primary_ids | secondary_ids
        profiles = list(Profile.objects.filter(id__in=all_ids).order_by('number').values('id', 'name', 'number'))
    else:
        profiles = []

    return JsonResponse({
        'project_type': project.project_type,
        'profiles': profiles,
        'assessments': assessments,
    })


@login_required
@user_passes_test(is_teacher)
def assessment_detail(request, assessment_id):
    """Assessment detail page for teacher"""
    from competencies.models import Assessment, Profile

    assessment = get_object_or_404(
        Assessment.objects.select_related('project'),
        id=assessment_id
    )

    # Get competency mappings with full competency + sub_pillar info
    competency_mappings = assessment.competency_mappings.select_related(
        'competency', 'competency__sub_pillar'
    ).order_by('order', 'id')

    # Determine Primary/Secondary weight for each competency
    comp_ids = [cm.competency_id for cm in competency_mappings]
    primary_comp_ids = set()
    if comp_ids:
        primary_comp_ids = set(
            Profile.objects.filter(primary_competencies__id__in=comp_ids)
            .values_list('primary_competencies__id', flat=True)
        )

    # Determine work form from comp types
    comp_types = set(cm.comp_type for cm in competency_mappings)
    if 'individual' in comp_types and 'group' in comp_types:
        work_form = 'Group & Individual'
    elif 'group' in comp_types:
        work_form = 'Group'
    elif 'individual' in comp_types:
        work_form = 'Individual'
    else:
        work_form = '—'

    enriched = []
    for cm in competency_mappings:
        enriched.append({
            'code': cm.competency.code,
            'name': cm.competency.name,
            'description': cm.competency.description,
            'comp_type': cm.get_comp_type_display(),
            'weight': 'Primary' if cm.competency_id in primary_comp_ids else 'Secondary',
        })

    context = {
        'assessment': assessment,
        'project': assessment.project,
        'competencies': enriched,
        'work_form': work_form,
    }
    return render(request, 'teacher/assessment-detail.html', context)


@login_required
@user_passes_test(is_teacher)
def score_entry(request):
    """Score Entry page"""
    from competencies.models import STAGE_CHOICES
    context = {'stage_choices': STAGE_CHOICES}
    return render(request, 'teacher/score-entry.html', context)


@login_required
@user_passes_test(is_teacher)
def api_assessments_by_project(request):
    """AJAX: return assessments for a project"""
    from competencies.models import Assessment
    project_id = request.GET.get('project_id', '')
    if not project_id:
        return JsonResponse({'assessments': []})
    assessments = list(
        Assessment.objects.filter(project_id=project_id)
        .order_by('order', 'id')
        .values('id', 'name', 'assessment_type')
    )
    return JsonResponse({'assessments': assessments})


@login_required
@user_passes_test(is_teacher)
def api_score_entry_data(request):
    """AJAX: return students + competencies + existing scores for an assessment"""
    from competencies.models import Assessment, ScoreEntry
    from student.models import Student

    assessment_id = request.GET.get('assessment_id', '')
    if not assessment_id:
        return JsonResponse({'error': 'assessment_id required'}, status=400)

    try:
        assessment = Assessment.objects.select_related('project').get(id=assessment_id)
    except (Assessment.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Not found'}, status=404)

    STAGE_TO_CLASSES = {
        'Foundational': ['1', '2'],
        'Preparatory':  ['3', '4', '5'],
        'Middle':       ['6', '7', '8'],
        'Secondary':    ['9', '10', '11', '12'],
    }
    grade = assessment.project.grade
    class_range = STAGE_TO_CLASSES.get(grade, [])

    teacher_obj = getattr(request.user, 'teacher_profile', None)
    students_qs = Student.objects.filter(
        student_class__in=class_range,
        attendance_status='active'
    )
    if teacher_obj and teacher_obj.school:
        students_qs = students_qs.filter(school=teacher_obj.school)

    students = list(
        students_qs.order_by('first_name', 'last_name')
        .values('id', 'first_name', 'last_name', 'student_class', 'division', 'gr_number')
    )

    comp_mappings = list(
        assessment.competency_mappings.select_related('competency')
        .order_by('order', 'id')
        .values('id', 'competency__code', 'competency__name', 'comp_type')
    )

    student_ids = [s['id'] for s in students]
    ac_ids      = [c['id'] for c in comp_mappings]
    scores_qs   = ScoreEntry.objects.filter(
        student_id__in=student_ids,
        assessment_competency_id__in=ac_ids
    ).values('student_id', 'assessment_competency_id', 'score')

    scores = {}
    scored_student_ids = set()
    for s in scores_qs:
        key = f"{s['student_id']}__{s['assessment_competency_id']}"
        scores[key] = s['score']
        if s['score'] is not None:
            scored_student_ids.add(s['student_id'])

    all_score_vals = [s['score'] for s in scores_qs if s['score'] is not None]
    class_avg = round(sum(all_score_vals) / len(all_score_vals), 1) if all_score_vals else None

    return JsonResponse({
        'assessment': {'id': assessment.id, 'name': assessment.name, 'type': assessment.assessment_type},
        'project':    {'id': assessment.project.id, 'title': assessment.project.title, 'grade': assessment.project.grade},
        'students':    students,
        'competencies': comp_mappings,
        'scores':      scores,
        'stats': {
            'total_students': len(students),
            'scored_count':   len(scored_student_ids),
            'class_avg':      class_avg,
        },
    })


@login_required
@user_passes_test(is_teacher)
def api_save_score(request):
    """AJAX POST: save a score entry"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    from competencies.models import ScoreEntry

    try:
        data     = json.loads(request.body)
        student_id = int(data['student_id'])
        ac_id      = int(data['assessment_competency_id'])
        score_val  = data.get('score')
        if score_val is not None and score_val != '':
            score_val = int(score_val)
            if not (1 <= score_val <= 10):
                return JsonResponse({'error': 'Score must be 1-10'}, status=400)
        else:
            score_val = None
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'error': 'Invalid data'}, status=400)

    entry, _ = ScoreEntry.objects.update_or_create(
        student_id=student_id,
        assessment_competency_id=ac_id,
        defaults={'score': score_val, 'entered_by': request.user}
    )
    return JsonResponse({'ok': True, 'score': entry.score})


@login_required
@user_passes_test(is_teacher)
def student_score_detail(request, assessment_id, student_id):
    """Individual student score entry for a specific assessment"""
    from competencies.models import Assessment, ScoreEntry, StudentAssessmentFeedback

    teacher_obj = getattr(request.user, 'teacher_profile', None)
    teacher_school = teacher_obj.school if teacher_obj else None

    assessment = get_object_or_404(
        Assessment.objects.select_related('project'),
        id=assessment_id
    )

    if teacher_school:
        student = get_object_or_404(Student, id=student_id, school=teacher_school)
    else:
        student = get_object_or_404(Student, id=student_id)

    comp_mappings = list(
        assessment.competency_mappings.select_related('competency', 'competency__sub_pillar')
        .order_by('order', 'id')
    )

    ac_ids = [cm.id for cm in comp_mappings]
    scores = {
        se.assessment_competency_id: se.score
        for se in ScoreEntry.objects.filter(student=student, assessment_competency_id__in=ac_ids)
    }

    try:
        feedback_obj = StudentAssessmentFeedback.objects.get(student=student, assessment=assessment)
        feedback_text = feedback_obj.feedback
    except StudentAssessmentFeedback.DoesNotExist:
        feedback_text = ''

    from competencies.models import StudentProjectFeedback
    try:
        proj_fb_obj = StudentProjectFeedback.objects.get(student=student, project=assessment.project)
        project_feedback_text = proj_fb_obj.feedback
    except StudentProjectFeedback.DoesNotExist:
        project_feedback_text = ''

    # Pre-pair each competency mapping with its score so template needs no custom filter
    comp_rows = [
        {'cm': cm, 'score': scores.get(cm.id)}
        for cm in comp_mappings
    ]

    context = {
        'student': student,
        'assessment': assessment,
        'project': assessment.project,
        'comp_rows': comp_rows,
        'scores_json': scores,
        'feedback_text': feedback_text,
        'project_feedback_text': project_feedback_text,
    }
    return render(request, 'teacher/student-score-detail.html', context)


@login_required
@user_passes_test(is_teacher)
def api_save_feedback(request):
    """AJAX POST: save teacher feedback for a student's assessment"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    from competencies.models import Assessment, StudentAssessmentFeedback

    try:
        data = json.loads(request.body)
        student_id    = int(data['student_id'])
        assessment_id = int(data['assessment_id'])
        feedback      = data.get('feedback', '').strip()
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'error': 'Invalid data'}, status=400)

    student    = get_object_or_404(Student, id=student_id)
    assessment = get_object_or_404(Assessment, id=assessment_id)

    StudentAssessmentFeedback.objects.update_or_create(
        student=student,
        assessment=assessment,
        defaults={'feedback': feedback, 'entered_by': request.user}
    )
    return JsonResponse({'ok': True})


@login_required
@user_passes_test(is_teacher)
def api_save_project_feedback(request):
    """AJAX POST: save teacher overall project feedback for a student"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    from competencies.models import Project, StudentProjectFeedback

    try:
        data       = json.loads(request.body)
        student_id = int(data['student_id'])
        project_id = int(data['project_id'])
        feedback   = data.get('feedback', '').strip()
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'error': 'Invalid data'}, status=400)

    student = get_object_or_404(Student, id=student_id)
    project = get_object_or_404(Project, id=project_id)

    StudentProjectFeedback.objects.update_or_create(
        student=student,
        project=project,
        defaults={'feedback': feedback, 'entered_by': request.user}
    )
    return JsonResponse({'ok': True})


def teacher_logout(request):
    """Logout view for teacher"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')


@login_required
@user_passes_test(is_teacher)
def teacher_profile(request):
    """Teacher Profile View"""
    
        
    # Get profile for the user
    try:
        profile = Teacher.objects.get(user=request.user)
    except Teacher.DoesNotExist:
        profile = None
    
    context = {
        'page_title': 'My Profile',
        'profile': profile,
    }
    return render(request, 'teacher/profile.html', context)


@login_required
@user_passes_test(is_teacher)
def teacher_profile_update(request):
    """Teacher Profile Update View"""
    
    if request.method == 'POST':
                
        try:
            profile = Teacher.objects.get(user=request.user)
            
            # Update profile fields
            profile.full_name = request.POST.get('full_name', profile.full_name)
            profile.mobile_number = request.POST.get('mobile_number', profile.mobile_number)
            profile.alternate_number = request.POST.get('alternate_number', profile.alternate_number)
            profile.gender = request.POST.get('gender', profile.gender)
            
            date_of_birth = request.POST.get('date_of_birth')
            if date_of_birth:
                profile.date_of_birth = date_of_birth
            
            # Handle profile photo upload
            if 'profile_photo' in request.FILES:
                profile.profile_photo = request.FILES['profile_photo']
            
            profile.save()
            messages.success(request, 'Profile updated successfully!')
        except Teacher.DoesNotExist:
            messages.error(request, 'Profile not found.')
        
    return redirect('teacher:teacher_profile')


@login_required
@user_passes_test(is_teacher)
def teacher_change_password(request):
    """Teacher Change Password View"""
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validate current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('teacher:teacher_change_password')
        
        # Validate new password
        if not new_password:
            messages.error(request, 'New password is required.')
            return redirect('teacher:teacher_change_password')
        
        # Check password requirements
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return redirect('teacher:teacher_change_password')
        
        # Validate confirm password
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('teacher:teacher_change_password')
        
        # Check if new password is same as current
        if current_password == new_password:
            messages.error(request, 'New password must be different from current password.')
            return redirect('teacher:teacher_change_password')
        
        try:
            # Update password
            request.user.set_password(new_password)
            request.user.save()
            
            # Update last_password_change in Teacher profile
            from django.utils import timezone
            try:
                teacher_profile = Teacher.objects.get(user=request.user)
                teacher_profile.last_password_change = timezone.now()
                teacher_profile.save()
            except Teacher.DoesNotExist:
                pass
            
            messages.success(request, 'Your password has been changed successfully!')
            
            # Keep user logged in after password change
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            return redirect('teacher:teacher_change_password')
            
        except Exception as e:
            messages.error(request, f'Error changing password: {str(e)}')
            return redirect('teacher:teacher_change_password')
    
    # GET request - render the change password page
    context = {
        'page_title': 'Change Password',
    }
    return render(request, 'teacher/change_password.html', context)


@login_required
@user_passes_test(is_teacher)
def student_list(request):
    """Teacher Student List View - Shows students from assigned school"""
    
    # Get teacher's assigned school
    teacher_school = None
    if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
        teacher_school = request.user.teacher_profile.school
    
    # Get students from teacher's assigned school
    if teacher_school:
        students = Student.objects.filter(school=teacher_school, is_active=True).order_by('first_name', 'last_name')
    else:
        students = Student.objects.none()
    
    # Add computed properties for template
    badge_colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#a855f7']
    students_with_extras = []
    for student in students:
        student.initials = (student.first_name[0] + student.last_name[0]).upper() if student.first_name and student.last_name else 'ST'
        student.student_id = student.gr_number or student.skill_lab_reg_id or f'STU{student.id}'
        student.class_name = f"Class {student.student_class}-{student.division}" if student.division else f"Class {student.student_class}"
        student.badge_color = random.choice(badge_colors)
        students_with_extras.append(student)
    
    context = {
        'page_title': 'Student List',
        'students': students_with_extras,
    }
    return render(request, 'teacher/student-list.html', context)


@login_required
@user_passes_test(is_teacher)
def view_student(request, student_id):
    """View individual student details"""
    
    # Get teacher's assigned school
    teacher_school = None
    if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
        teacher_school = request.user.teacher_profile.school
    
    # Get student - ensure they belong to teacher's school
    if teacher_school:
        student = get_object_or_404(Student, id=student_id, school=teacher_school)
    else:
        messages.error(request, 'No school assigned to your profile.')
        return redirect('teacher:student_list')
    
    # Add computed properties
    student.initials = (student.first_name[0] + student.last_name[0]).upper() if student.first_name and student.last_name else 'ST'
    student.student_id_display = student.gr_number or student.skill_lab_reg_id or f'STU{student.id}'
    student.class_name = f"Class {student.student_class}-{student.division}" if student.division else f"Class {student.student_class}"
    
    context = {
        'page_title': f'Student - {student.full_name}',
        'student': student,
    }
    return render(request, 'teacher/view-student.html', context)


@login_required
@user_passes_test(is_teacher)
def lesson_library(request):
    """Teacher Lesson Library View"""
    
    # Get teacher's assigned school
    teacher_school = None
    if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
        teacher_school = request.user.teacher_profile.school
    
    # Get lessons - filter by teacher's school if applicable
    if teacher_school:
        lessons = Lesson.objects.filter(applicable_schools=teacher_school).order_by('-created_at')
    else:
        lessons = Lesson.objects.all().order_by('-created_at')
    
    context = {
        'page_title': 'Lesson Library',
        'lessons': lessons,
    }
    return render(request, 'teacher/lesson-library.html', context)


@login_required
@user_passes_test(is_teacher)
def add_lesson(request):
    """Teacher Add Lesson View"""
    
    if request.method == 'POST':
        from lms.models import Lesson, LessonResource
        from schools.models import School
        import os
        
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

            # Get content data
            video_urls = request.POST.get('video_urls', '')
            article_content = request.POST.get('article_content', '')
            quiz_data = request.POST.get('quiz_data', '')
            
            # Debug logging
            print(f"DEBUG - video_urls: {video_urls[:100] if video_urls else 'None'}")
            print(f"DEBUG - article_content length: {len(article_content) if article_content else 0}")
            print(f"DEBUG - quiz_data: {quiz_data[:100] if quiz_data else 'None'}")
            
            # Determine primary_content_type based on actual content (not form value)
            # Priority: Video > Article > Quiz > Resources
            import json
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
                import re
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
            
            print(f"DEBUG - has_videos: {has_videos}, has_article: {has_article}, has_quiz: {has_quiz}, has_resources: {has_resources}")
            print(f"DEBUG - Final primary_content_type: {primary_content_type}")

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

            # Get teacher's school and assign to lesson
            teacher_school = None
            if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
                teacher_school = request.user.teacher_profile.school
            
            if teacher_school:
                lesson.applicable_schools.add(teacher_school)

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
            return redirect('teacher:lesson_library')

        except Exception as e:
            messages.error(request, f'Error creating lesson: {str(e)}')

    # GET request - render form
    from competencies.models import Competency as CompModel, SubPillar as SPModel
    context = {
        'competencies': CompModel.objects.filter(status='Active').select_related('sub_pillar').order_by('code'),
        'sub_pillars': SPModel.objects.all().select_related('pillar').order_by('sp_number'),
    }
    return render(request, 'teacher/add-lesson.html', context)


@login_required
@user_passes_test(is_teacher)
def view_lesson(request, lesson_id):
    """View individual lesson details"""
    from lms.models import LessonResource
    import json

    # Get teacher's assigned school
    teacher_school = None
    if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
        teacher_school = request.user.teacher_profile.school
    
    # Get lesson - ensure they can view it (either created by them or assigned to their school)
    if teacher_school:
        lesson = get_object_or_404(Lesson, id=lesson_id, applicable_schools=teacher_school)
    else:
        lesson = get_object_or_404(Lesson, id=lesson_id, created_by=request.user)
    
    resources = LessonResource.objects.filter(lesson=lesson)

    # Parse video URLs from JSON
    video_urls_list = []
    if lesson.video_urls:
        try:
            video_urls_list = json.loads(lesson.video_urls)
        except (json.JSONDecodeError, TypeError):
            pass

    context = {
        'page_title': f'Lesson - {lesson.title}',
        'lesson': lesson,
        'resources': resources,
        'video_urls_list': video_urls_list,
    }
    return render(request, 'teacher/view-lesson.html', context)


@login_required
@user_passes_test(is_teacher)
def edit_lesson(request, lesson_id):
    """Edit lesson"""
    
    # Get teacher's assigned school
    teacher_school = None
    if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
        teacher_school = request.user.teacher_profile.school
    
    # Get lesson - ensure they can edit it (either created by them or assigned to their school)
    if teacher_school:
        lesson = get_object_or_404(Lesson, id=lesson_id, applicable_schools=teacher_school)
    else:
        lesson = get_object_or_404(Lesson, id=lesson_id, created_by=request.user)
    
    if request.method == 'POST':
        # Apply same primary_content_type logic as add_lesson
        video_urls = request.POST.get('video_urls', '')
        article_content = request.POST.get('article_content', '')
        quiz_data = request.POST.get('quiz_data', '')
        
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
        
        lesson.title = request.POST.get('title', lesson.title).strip()
        lesson.description = request.POST.get('description', lesson.description).strip()
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
        lesson.applicable_grades = request.POST.get('applicable_grades', lesson.applicable_grades).strip()
        lesson.primary_content_type = primary_content_type
        lesson.status = request.POST.get('status', lesson.status)
        lesson.article_content = article_content
        lesson.video_urls = video_urls
        lesson.quiz_data = quiz_data
        
        if 'thumbnail' in request.FILES:
            lesson.thumbnail = request.FILES['thumbnail']

        lesson.save()

        # Handle new resource files
        import os
        from lms.models import LessonResource
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
        return redirect('teacher:lesson_library')

    # GET request - load existing resources
    from lms.models import LessonResource
    resources = LessonResource.objects.filter(lesson=lesson)

    from competencies.models import Competency as CompModel, SubPillar as SPModel
    context = {
        'page_title': f'Edit Lesson - {lesson.title}',
        'lesson': lesson,
        'resources': resources,
        'competencies': CompModel.objects.filter(status='Active').select_related('sub_pillar').order_by('code'),
        'sub_pillars': SPModel.objects.all().select_related('pillar').order_by('sp_number'),
    }
    return render(request, 'teacher/edit-lesson.html', context)


@login_required
@user_passes_test(is_teacher)
def delete_lessons(request):
    """Delete multiple lessons"""
    import json
    from django.http import JsonResponse
    
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        lesson_ids = data.get('lesson_ids', [])
        
        if not lesson_ids:
            return JsonResponse({'success': False, 'error': 'No lessons selected'})
        
        # Get teacher's assigned school
        teacher_school = None
        if hasattr(request.user, 'teacher_profile') and request.user.teacher_profile:
            teacher_school = request.user.teacher_profile.school
        
        # Delete only lessons they have access to
        if teacher_school:
            deleted_count = Lesson.objects.filter(
                id__in=lesson_ids, 
                applicable_schools=teacher_school
            ).delete()[0]
        else:
            deleted_count = Lesson.objects.filter(
                id__in=lesson_ids, 
                created_by=request.user
            ).delete()[0]
        
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} lesson(s) deleted successfully'
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@user_passes_test(is_teacher)
def api_generate_report(request):
    """AJAX POST: generate (or regenerate) a ProjectReport for a student + project."""

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    import json
    from competencies.models import Project
    from competencies.engine import generate_project_report

    try:
        data       = json.loads(request.body)
        student_id = int(data.get('student_id', 0))
        project_id = int(data.get('project_id', 0))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Invalid data'}, status=400)

    student = Student.objects.filter(id=student_id).first()
    project = Project.objects.filter(id=project_id).first()

    if not student or not project:
        return JsonResponse({'ok': False, 'error': 'Student or project not found'}, status=404)

    # Ensure teacher can only generate for students in their school
    teacher_profile = getattr(request.user, 'teacher_profile', None)
    if teacher_profile and student.school != teacher_profile.school:
        return JsonResponse({'ok': False, 'error': 'Student not in your school'}, status=403)

    report, error = generate_project_report(student, project)
    if error:
        return JsonResponse({'ok': False, 'error': error})

    return JsonResponse({
        'ok': True,
        'message': f'Report generated for {student.first_name} {student.last_name}',
        'report_id': report.id,
    })
