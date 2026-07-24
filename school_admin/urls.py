from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.school_admin_dashboard, name='school_admin_dashboard'),
    path('logout/', views.school_admin_logout, name='school_admin_logout'),
    path('profile/', views.school_admin_profile, name='school_admin_profile'),
    path('profile/update/', views.school_admin_profile_update, name='school_admin_profile_update'),
    path('change-password/', views.school_admin_change_password, name='school_admin_change_password'),
    path('onboard-student/', views.school_admin_onboard_student, name='school_admin_onboard_student'),
    path('students/', views.school_admin_student_list, name='school_admin_student_list'),
    path('onboard-parent/', views.school_admin_onboard_parent, name='school_admin_onboard_parent'),
    path('parents/', views.school_admin_parent_list, name='school_admin_parent_list'),
    path('announcements/', views.school_admin_announcements, name='school_admin_announcements'),
]