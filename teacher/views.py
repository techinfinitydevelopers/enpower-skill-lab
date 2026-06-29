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

    # Read-only rubric grid (PPT slide 28) — descriptor text per band per competency
    rubric_map = {rc.competency_id: rc for rc in assessment.rubric_criteria.all()}

    enriched = []
    rubric_rows = []
    for cm in competency_mappings:
        enriched.append({
            'code': cm.competency.code,
            'name': cm.competency.name,
            'description': cm.competency.description,
            'comp_type': cm.get_comp_type_display(),
            'weight': 'Primary' if cm.competency_id in primary_comp_ids else 'Secondary',
        })
        rc = rubric_map.get(cm.competency_id)
        if rc:
            rubric_rows.append({
                'code': cm.competency.code,
                'name': cm.competency.name,
                'band1': rc.band1_text,
                'band2': rc.band2_text,
                'band3': rc.band3_text,
                'band4': rc.band4_text,
            })

    context = {
        'assessment': assessment,
        'project': assessment.project,
        'competencies': enriched,
        'work_form': work_form,
        'rubric_rows': rubric_rows,
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


# ============================================================
# ESL Dashboard — Thinking Coach features (slides 14-17)
# Additive. Uses models in attendance/models.py. No model changes.
# ============================================================

def _teacher_school(user):
    """Return the teacher's assigned school (or None)."""
    tp = getattr(user, 'teacher_profile', None)
    return tp.school if tp else None


def _active_projects_for_teacher(user):
    """Active projects filtered by the teacher's school framework (if any)."""
    from competencies.models import Project
    qs = Project.objects.filter(status='Active').exclude(project_type='Plug In')
    school = _teacher_school(user)
    if school and getattr(school, 'framework_ref', None):
        qs = qs.filter(framework_ref=school.framework_ref)
    return qs.order_by('title')


def _class_students(school, grade, division):
    """Active students for a school + numeric grade + division."""
    qs = Student.objects.filter(
        student_class=str(grade),
        division=division,
        is_active=True,
    )
    if school:
        qs = qs.filter(school=school)
    return qs.order_by('first_name', 'last_name')


# ---------- SLIDE 14: Attendance (classroom + session based) ----------

def _teacher_timetables(user):
    """Distinct Timetables visible to this coach: own timetables + school's, de-duped."""
    from attendance.models import Timetable
    school = _teacher_school(user)
    q = Timetable.objects.filter(thinking_coach=user)
    if school:
        from django.db.models import Q
        q = Timetable.objects.filter(Q(thinking_coach=user) | Q(school=school))
    return q.distinct().order_by('grade', 'division', 'program')


def _classroom_label(tt):
    return f"{tt.program or '—'} {tt.grade} – {tt.division}"


def _classroom_dict(tt):
    return {
        'id': tt.id,
        'label': _classroom_label(tt),
        'program': tt.program or '',
        'grade': tt.grade,
        'division': tt.division,
    }


def _resolve_teacher_timetable(user, tt_id):
    """Return a Timetable the coach is allowed to see, or None."""
    from attendance.models import Timetable
    if not tt_id:
        return None
    try:
        tt = Timetable.objects.get(id=int(tt_id))
    except (Timetable.DoesNotExist, ValueError, TypeError):
        return None
    school = _teacher_school(user)
    if tt.thinking_coach_id == user.id:
        return tt
    if school and tt.school_id == school.id:
        return tt
    return None


def _generate_sessions(tt, cap=60):
    """Build session dicts (one per matching weekday date x slot) within the
    timetable date range. Returns [] defensively if range/slots are missing."""
    from datetime import timedelta
    if not tt or not tt.start_date or not tt.end_date or tt.end_date < tt.start_date:
        return []
    day_index = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
    day_short = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 4: 'FRI', 5: 'SAT', 6: 'SUN'}
    slots = list(tt.slots.all())
    if not slots:
        return []
    sessions = []
    cur = tt.start_date
    while cur <= tt.end_date:
        wd = cur.weekday()
        for slot in slots:
            if day_index.get(slot.day_of_week) != wd:
                continue
            st = slot.start_time
            time_label = st.strftime('%I:%M %p').lstrip('0') if st else ''
            sessions.append({
                'date': cur.isoformat(),
                'day_label': day_short[wd],
                'date_label': cur.strftime('%b %d, %Y'),
                'time_label': time_label,
                'start_time': st.strftime('%H:%M') if st else '',
                '_sort': (cur.isoformat(), st.strftime('%H:%M') if st else '00:00'),
            })
        cur += timedelta(days=1)
    sessions.sort(key=lambda s: s['_sort'])
    if len(sessions) > cap:
        sessions = sessions[:cap]
    for s in sessions:
        s.pop('_sort', None)
    return sessions


def _student_dict(s):
    initial = ((s.first_name or '').strip()[:1] or '?').upper()
    name = f"{s.first_name or ''} {s.last_name or ''}".strip()
    return {
        'id': s.id,
        'name': name,
        'roll': s.roll_number or '',
        'initial': initial,
    }


def _attendance_stats(records_map):
    total = len(records_map)
    present = sum(1 for v in records_map.values() if v == 'present')
    absent = sum(1 for v in records_map.values() if v in ('absent', 'late'))
    pct = round(present / total * 100) if total else 0
    return {'total': total, 'present': present, 'absent': absent, 'attendance_pct': pct}


@login_required
@user_passes_test(is_teacher)
def attendance_mark(request):
    """Student Attendance page (classroom + session based)."""
    classrooms = [_classroom_dict(tt) for tt in _teacher_timetables(request.user)]
    return render(request, 'teacher/attendance-mark.html', {'classrooms': classrooms})


@login_required
@user_passes_test(is_teacher)
def api_attendance_sessions(request):
    """AJAX GET: generated class sessions for a classroom (timetable)."""
    tt = _resolve_teacher_timetable(request.user, request.GET.get('classroom'))
    if not tt:
        return JsonResponse({'error': 'Classroom not found'}, status=404)
    sessions = _generate_sessions(tt)
    return JsonResponse({
        'sessions': sessions,
        'classroom': {
            'label': _classroom_label(tt),
            'program': tt.program or '',
            'grade': tt.grade,
            'division': tt.division,
            'count': len(sessions),
        },
    })


@login_required
@user_passes_test(is_teacher)
def api_attendance_students(request):
    """AJAX GET: students + existing records for a classroom + date.

    Backward compatible: accepts grade=&division=&date= (old callers)."""
    from attendance.models import AttendanceSession, AttendanceRecord

    tt = _resolve_teacher_timetable(request.user, request.GET.get('classroom'))
    date = request.GET.get('date', '').strip()

    if tt:
        school, grade, division = tt.school, tt.grade, tt.division
    else:
        grade = request.GET.get('grade', '').strip()
        division = request.GET.get('division', '').strip()
        if not (grade and division):
            return JsonResponse({'error': 'classroom (or grade+division) required'}, status=400)
        school = _teacher_school(request.user)

    if not date:
        return JsonResponse({'error': 'date required'}, status=400)

    students = list(_class_students(school, grade, division))
    student_dicts = [_student_dict(s) for s in students]

    session = AttendanceSession.objects.filter(
        school=school, grade=str(grade), division=division, date=date
    ).order_by('session_number', 'id').first()

    records = {}
    already_marked = False
    class_status = 'held'
    if session:
        class_status = session.class_status or 'held'
        for r in AttendanceRecord.objects.filter(session=session).values('student_id', 'status'):
            records[str(r['student_id'])] = r['status']
        already_marked = len(records) > 0

    # Effective status per student (existing or default present) for live stats.
    effective = {str(s['id']): records.get(str(s['id']), 'present') for s in student_dicts}
    stats = _attendance_stats(effective)

    time_label = ''
    if session and session.start_time:
        time_label = session.start_time.strftime('%I:%M %p').lstrip('0')

    return JsonResponse({
        'students': student_dicts,
        'records': records,
        'class_status': class_status,
        'already_marked': already_marked,
        'stats': stats,
        'time_label': time_label,
    })


@login_required
@user_passes_test(is_teacher)
def api_save_attendance(request):
    """AJAX POST: create/update AttendanceSession + AttendanceRecords.

    Body JSON: {classroom (timetable id), date, time(HH:MM optional),
    class_status('held'|'cancelled'), records:{student_id:'present'|'absent'}}.
    Backward compatible: accepts grade/division instead of classroom."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    from datetime import datetime
    from attendance.models import AttendanceSession, AttendanceRecord

    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid data'}, status=400)

    date = str(data.get('date', '')).strip()
    class_status = str(data.get('class_status', 'held')).strip()
    if class_status not in ('held', 'cancelled'):
        class_status = 'held'
    records = data.get('records', {}) or {}

    tt = _resolve_teacher_timetable(request.user, data.get('classroom'))
    if tt:
        school, grade, division = tt.school, tt.grade, tt.division
    else:
        grade = str(data.get('grade', '')).strip()
        division = str(data.get('division', '')).strip()
        school = _teacher_school(request.user)
        if not (grade and division):
            return JsonResponse({'error': 'classroom (or grade+division) required'}, status=400)

    if not date:
        return JsonResponse({'error': 'date required'}, status=400)
    if not school:
        return JsonResponse({'error': 'No school assigned to your profile'}, status=400)

    start_time = None
    time_str = str(data.get('time', '')).strip()
    if time_str:
        try:
            start_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            start_time = None

    defaults = {
        'thinking_coach': request.user,
        'class_status': class_status,
        'timetable': tt,
    }
    if start_time is not None:
        defaults['start_time'] = start_time

    session, _ = AttendanceSession.objects.update_or_create(
        school=school, grade=str(grade), division=division, date=date, session_number=None,
        defaults=defaults,
    )

    valid_statuses = {'present', 'absent', 'late'}
    saved = 0
    effective = {}
    for sid, status in records.items():
        if status not in valid_statuses:
            continue
        try:
            student = Student.objects.get(id=int(sid))
        except (Student.DoesNotExist, ValueError, TypeError):
            continue
        if school and student.school_id != school.id:
            continue
        AttendanceRecord.objects.update_or_create(
            session=session, student=student, defaults={'status': status},
        )
        effective[str(sid)] = status
        saved += 1

    return JsonResponse({
        'ok': True,
        'saved': saved,
        'session_id': session.id,
        'stats': _attendance_stats(effective),
    })


@login_required
@user_passes_test(is_teacher)
def attendance_list(request):
    """Summary list of attendance sessions for the teacher's school."""
    from attendance.models import AttendanceSession
    from django.db.models import Count, Q

    school = _teacher_school(request.user)
    sessions = AttendanceSession.objects.filter(school=school) if school else AttendanceSession.objects.none()
    sessions = sessions.select_related('project').annotate(
        total=Count('records'),
        present=Count('records', filter=Q(records__status='present')),
        absent=Count('records', filter=Q(records__status='absent')),
        late=Count('records', filter=Q(records__status='late')),
    ).order_by('-date')[:100]

    return render(request, 'teacher/attendance-list.html', {'sessions': sessions})


# ---------- SLIDE 15: Daily Session Feedback ----------

@login_required
@user_passes_test(is_teacher)
def daily_feedback(request):
    """Daily session feedback form + recent list."""
    from attendance.models import DailySessionFeedback, SessionPhoto, GRADE_CHOICES
    from competencies.models import Project

    school = _teacher_school(request.user)

    if request.method == 'POST':
        if not school:
            messages.error(request, 'No school assigned to your profile.')
            return redirect('teacher:daily_feedback')

        grade    = request.POST.get('grade', '').strip()
        division = request.POST.get('division', '').strip()
        date     = request.POST.get('date', '').strip()
        if not (grade and division and date):
            messages.error(request, 'Grade, division and date are required.')
            return redirect('teacher:daily_feedback')

        def _rating(name):
            v = request.POST.get(name, '').strip()
            if v.isdigit() and 1 <= int(v) <= 5:
                return int(v)
            return None

        def _intval(name):
            v = request.POST.get(name, '').strip()
            return int(v) if v.isdigit() else None

        project = None
        pid = request.POST.get('project') or None
        if pid:
            project = Project.objects.filter(id=pid).first()

        fb = DailySessionFeedback.objects.create(
            school=school,
            grade=grade,
            division=division,
            date=date,
            project=project,
            session_number=_intval('session_number'),
            session_title=request.POST.get('session_title', '').strip(),
            session_description=request.POST.get('session_description', '').strip(),
            thinking_coach=request.user,
            rating_engagement=_rating('rating_engagement'),
            rating_delivery_ease=_rating('rating_delivery_ease'),
            rating_resources=_rating('rating_resources'),
            rating_time_management=_rating('rating_time_management'),
            is_project_completed=request.POST.get('is_project_completed') == 'on',
        )

        # Up to 3 photos
        photos = request.FILES.getlist('photos')[:3]
        for img in photos:
            SessionPhoto.objects.create(feedback=fb, image=img)

        messages.success(request, 'Daily session feedback saved successfully.')
        return redirect('teacher:daily_feedback')

    recent = DailySessionFeedback.objects.filter(school=school) if school else DailySessionFeedback.objects.none()
    recent = recent.select_related('project').prefetch_related('photos').order_by('-date', '-created_at')[:20]

    context = {
        'grade_choices': GRADE_CHOICES,
        'projects': _active_projects_for_teacher(request.user),
        'recent': recent,
    }
    return render(request, 'teacher/daily-feedback.html', context)


# ---------- SLIDE 16: Weekly Session Feedback ----------

@login_required
@user_passes_test(is_teacher)
def weekly_feedback(request):
    """Weekly qualitative feedback form + recent list."""
    from attendance.models import WeeklySessionFeedback

    school = _teacher_school(request.user)

    if request.method == 'POST':
        date_from = request.POST.get('date_from', '').strip()
        date_to   = request.POST.get('date_to', '').strip()
        if not (date_from and date_to):
            messages.error(request, 'Date from and date to are required.')
            return redirect('teacher:weekly_feedback')

        WeeklySessionFeedback.objects.create(
            thinking_coach=request.user,
            school=school,
            date_from=date_from,
            date_to=date_to,
            went_wrong=request.POST.get('went_wrong', '').strip()[:200],
            went_well=request.POST.get('went_well', '').strip()[:200],
            new_tried=request.POST.get('new_tried', '').strip()[:200],
            lab_issue=request.POST.get('lab_issue') == 'yes',
            lab_issue_detail=request.POST.get('lab_issue_detail', '').strip(),
        )
        messages.success(request, 'Weekly session feedback saved successfully.')
        return redirect('teacher:weekly_feedback')

    recent = WeeklySessionFeedback.objects.filter(thinking_coach=request.user).order_by('-date_from')[:20]
    return render(request, 'teacher/weekly-feedback.html', {'recent': recent})


# ---------- SLIDE 17: Student Project Upload ----------

@login_required
@user_passes_test(is_teacher)
def student_project_upload(request):
    """Student project upload form + recent list."""
    from attendance.models import StudentProjectUpload, GRADE_CHOICES
    from competencies.models import Project

    school = _teacher_school(request.user)

    if request.method == 'POST':
        if not school:
            messages.error(request, 'No school assigned to your profile.')
            return redirect('teacher:student_project_upload')

        grade    = request.POST.get('grade', '').strip()
        division = request.POST.get('division', '').strip()
        title    = request.POST.get('title', '').strip()
        if not (grade and division and title):
            messages.error(request, 'Grade, division and title are required.')
            return redirect('teacher:student_project_upload')

        project = None
        pid = request.POST.get('project') or None
        if pid:
            project = Project.objects.filter(id=pid).first()

        upload = StudentProjectUpload.objects.create(
            school=school,
            grade=grade,
            division=division,
            project=project,
            title=title,
            video_link=request.POST.get('video_link', '').strip(),
            description=request.POST.get('description', '').strip(),
            created_by=request.user,
        )
        if 'file' in request.FILES:
            upload.file = request.FILES['file']
            upload.save()

        # Link selected students (must belong to teacher's school)
        student_ids = request.POST.getlist('students')
        if student_ids:
            valid = Student.objects.filter(id__in=student_ids, school=school)
            upload.students.set(valid)

        messages.success(request, 'Student project uploaded successfully.')
        return redirect('teacher:student_project_upload')

    recent = StudentProjectUpload.objects.filter(school=school) if school else StudentProjectUpload.objects.none()
    recent = recent.select_related('project').prefetch_related('students').order_by('-created_at')[:20]

    context = {
        'grade_choices': GRADE_CHOICES,
        'projects': _active_projects_for_teacher(request.user),
        'recent': recent,
    }
    return render(request, 'teacher/student-project-upload.html', context)


@login_required
@user_passes_test(is_teacher)
def api_class_students(request):
    """AJAX GET: active students for grade+division (for upload multiselect)."""
    grade    = request.GET.get('grade', '').strip()
    division = request.GET.get('division', '').strip()
    if not (grade and division):
        return JsonResponse({'students': []})
    school = _teacher_school(request.user)
    students = list(
        _class_students(school, grade, division)
        .values('id', 'first_name', 'last_name', 'student_class', 'division', 'gr_number')
    )
    return JsonResponse({'students': students})
