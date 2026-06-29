from django.urls import path
from . import views

app_name = 'coordinator'

urlpatterns = [
    path('dashboard/', views.coordinator_dashboard, name='coordinator_dashboard'),
    path('school-list/', views.school_list, name='school_list'),
    path('timetable/', views.timetable_list, name='timetable_list'),
    path('timetable/upload/', views.timetable_upload, name='timetable_upload'),
    path('timetable/<int:pk>/', views.timetable_detail, name='timetable_detail'),
    path('timetable/<int:pk>/edit/', views.timetable_edit, name='timetable_edit'),
    path('timetable/<int:pk>/delete/', views.timetable_delete, name='timetable_delete'),
    path('profile/', views.coordinator_profile, name='coordinator_profile'),
    path('change-password/', views.coordinator_change_password, name='coordinator_change_password'),
    path('logout/', views.coordinator_logout, name='coordinator_logout'),
]
