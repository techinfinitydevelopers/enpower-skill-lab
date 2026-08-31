from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.parent_dashboard, name='parent_dashboard'),
    path('profile/', views.parent_profile, name='parent_profile'),
    path('profile/update/', views.parent_profile_update, name='parent_profile_update'),
    path('child/<int:student_id>/reports/', views.parent_child_reports, name='parent_child_reports'),
    path('child/<int:student_id>/reports/<int:project_id>/', views.parent_child_report_detail, name='parent_child_report_detail'),
    path('child/<int:student_id>/passport/', views.parent_child_passport, name='parent_child_passport'),
    path('child/<int:student_id>/kaushal-bodh/', views.parent_child_kb_report, name='parent_child_kb_report'),
    path('announcements/', views.parent_announcements, name='parent_announcements'),
    path('events/', views.parent_events, name='parent_events'),
    path('newsletter/', views.parent_newsletter, name='parent_newsletter'),
    path('success-stories/', views.parent_success_stories, name='parent_success_stories'),
    path('projects/', views.parent_projects, name='parent_projects'),
    path('logout/', views.parent_logout, name='parent_logout'),
]
