from django.urls import path
from . import views

app_name = 'student'

urlpatterns = [
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('profile/', views.student_profile, name='student_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/avatar/', views.update_avatar, name='update_avatar'),
    path('reports/', views.student_reports, name='student_reports'),
    path('reports/annual/', views.student_annual_passport, name='student_annual_passport'),
    path('reports/<int:project_id>/', views.student_report_detail, name='student_report_detail'),
    path('badges/', views.student_badges, name='student_badges'),
    path('events/', views.student_event_calendar, name='student_event_calendar'),
    path('newsletter/', views.student_newsletter, name='student_newsletter'),
    path('announcements/', views.student_announcements, name='student_announcements'),
    path('change-password/', views.student_change_password, name='student_change_password'),
]
