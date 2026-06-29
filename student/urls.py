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
]
