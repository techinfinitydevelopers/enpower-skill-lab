from django.urls import path
from . import views
from . import pages
from . import reports

# Spec slide 51: "Remove user onboarding feature from school admin (this id is
# given to principals. Only view access. No inputs)". The onboarding routes are
# gone so the pages cannot be reached by typing the URL either.
urlpatterns = [
    path('dashboard/', views.school_admin_dashboard, name='school_admin_dashboard'),
    path('logout/', views.school_admin_logout, name='school_admin_logout'),
    path('profile/', views.school_admin_profile, name='school_admin_profile'),
    path('profile/update/', views.school_admin_profile_update, name='school_admin_profile_update'),
    path('change-password/', views.school_admin_change_password, name='school_admin_change_password'),
    path('students/', views.school_admin_student_list, name='school_admin_student_list'),
    path('parents/', views.school_admin_parent_list, name='school_admin_parent_list'),
    # Pages whose sidebar links were dead (changes document, 'Need to work on')
    path('thinking-coaches/', pages.teacher_list, name='school_admin_teacher_list'),
    path('thinking-coaches/<int:teacher_id>/', pages.view_teacher, name='school_admin_view_teacher'),
    path('classes/overview/', pages.class_overview, name='school_admin_class_overview'),
    path('classes/attendance/', pages.class_attendance, name='school_admin_class_attendance'),
    path('reports/download/', reports.download_reports, name='school_admin_download_reports'),
    path('announcements/', views.school_admin_announcements, name='school_admin_announcements'),
]