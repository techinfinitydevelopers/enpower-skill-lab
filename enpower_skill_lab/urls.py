"""
URL configuration for enpower_skill_lab project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
# from . import views

urlpatterns = [
    
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('schools/', include('schools.urls')),
    # path('competencies/', include('competencies.urls')),
    # path('assessments/', include('assessments.urls')),
    # path('lms/', include('lms.urls')),
    # path('attendance/', include('attendance.urls')),
    # path('reports/', include('reports.urls')),
    path('super-admin/', include('superadmin.urls')),
    path('coordinator/', include('coordinator.urls')),
    path('school-admin/', include('school_admin.urls')),
    path('teacher/', include('teacher.urls')),
    path('parent/', include('parent.urls')),
    path('student/', include('student.urls')),
]

# static() only returns anything while DEBUG is on, and whitenoise covers
# STATIC_URL either way. MEDIA_URL is the gap: with DEBUG off and no nginx in
# front — which is the case on a container host — every uploaded school logo
# and profile photo would 404.
#
# Serving uploads through Django is not what you would do at scale, but this
# platform holds a few hundred small images for a few hundred users. Set
# SERVE_MEDIA=False wherever a real web server handles /media/ instead.
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    from django.views.static import serve
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
