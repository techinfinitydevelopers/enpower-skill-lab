from django.urls import path
from . import views

app_name = 'coordinator'

urlpatterns = [
    path('dashboard/', views.coordinator_dashboard, name='coordinator_dashboard'),
    path('school-list/', views.school_list, name='school_list'),
    path('school/<int:school_id>/details/', views.school_detail, name='school_detail'),
    path('assign-coaches/', views.assign_coaches, name='assign_coaches'),
    path('coming-soon/', views.coming_soon, name='coming_soon'),
    # Bulk Upload (students & parents) — client issue #10
    path('bulk-upload/', views.bulk_upload_page, name='bulk_upload'),
    path('bulk-upload/<str:role>/sample/', views.download_sample_view, name='download_sample'),
    path('bulk-upload/<str:role>/', views.bulk_import_view, name='bulk_import'),
    path('timetable/', views.timetable_list, name='timetable_list'),
    path('timetable/upload/', views.timetable_upload, name='timetable_upload'),
    path('timetable/<int:pk>/', views.timetable_detail, name='timetable_detail'),
    path('timetable/<int:pk>/edit/', views.timetable_edit, name='timetable_edit'),
    path('timetable/<int:pk>/delete/', views.timetable_delete, name='timetable_delete'),
    path('profile/', views.coordinator_profile, name='coordinator_profile'),
    path('change-password/', views.coordinator_change_password, name='coordinator_change_password'),
    path('announcements/', views.coordinator_announcements, name='coordinator_announcements'),
    path('logout/', views.coordinator_logout, name='coordinator_logout'),
]
