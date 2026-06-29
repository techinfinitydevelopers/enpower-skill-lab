from django.urls import path
from . import views

app_name = 'teacher'

urlpatterns = [
    path('dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('logout/', views.teacher_logout, name='teacher_logout'),
    path('profile/', views.teacher_profile, name='teacher_profile'),
    path('profile/update/', views.teacher_profile_update, name='teacher_profile_update'),
    path('change-password/', views.teacher_change_password, name='teacher_change_password'),
    path('students/', views.student_list, name='student_list'),
    path('students/<int:student_id>/', views.view_student, name='view_student'),
    path('lessons/', views.lesson_library, name='lesson_library'),
    path('lessons/add/', views.add_lesson, name='add_lesson'),
    path('lessons/<int:lesson_id>/', views.view_lesson, name='view_lesson'),
    path('lessons/<int:lesson_id>/edit/', views.edit_lesson, name='edit_lesson'),
    path('lessons/delete/', views.delete_lessons, name='delete_lessons'),
    path('assessment/<int:assessment_id>/', views.assessment_detail, name='assessment_detail'),
    path('academics/score-entry/', views.score_entry, name='score_entry'),
    path('api/assessments-by-project/', views.api_assessments_by_project, name='api_assessments_by_project'),
    path('api/score-entry-data/', views.api_score_entry_data, name='api_score_entry_data'),
    path('api/save-score/', views.api_save_score, name='api_save_score'),
    path('api/projects-by-grade/', views.api_projects_by_grade, name='api_projects_by_grade'),
    path('api/project-details/', views.api_project_details, name='api_project_details'),
    path('assessment/<int:assessment_id>/student/<int:student_id>/', views.student_score_detail, name='student_score_detail'),
    path('api/save-feedback/', views.api_save_feedback, name='api_save_feedback'),
    path('api/generate-report/', views.api_generate_report, name='api_generate_report'),
    path('api/save-project-feedback/', views.api_save_project_feedback, name='api_save_project_feedback'),

    # ESL Dashboard — Thinking Coach features (slides 14-17)
    path('attendance/', views.attendance_mark, name='attendance_mark'),
    path('attendance/list/', views.attendance_list, name='attendance_list'),
    path('api/attendance-sessions/', views.api_attendance_sessions, name='api_attendance_sessions'),
    path('api/attendance-students/', views.api_attendance_students, name='api_attendance_students'),
    path('api/save-attendance/', views.api_save_attendance, name='api_save_attendance'),
    path('daily-feedback/', views.daily_feedback, name='daily_feedback'),
    path('weekly-feedback/', views.weekly_feedback, name='weekly_feedback'),
    path('student-project-upload/', views.student_project_upload, name='student_project_upload'),
    path('api/class-students/', views.api_class_students, name='api_class_students'),
]
