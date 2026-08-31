"""
Super Admin Reports & Analytics.

The four grade-wise panels from presentation slide 52, across every school, with
an optional filter down to one school. Skill Passport data is included — the
presentation's access matrix gives Super Admin the full picture.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

from competencies import report_panels
from .views import is_superadmin


@login_required
@user_passes_test(is_superadmin)
def platform_analytics(request):
    from schools.models import School

    schools = list(School.objects.order_by('school_name'))
    requested = (request.GET.get('school') or '').strip()
    selected = next((s for s in schools if str(s.id) == requested), None)

    scope = [selected.id] if selected else [s.id for s in schools]
    panels = report_panels.build(scope, month=(request.GET.get('month') or None))

    # Carried into the month selector so changing month keeps the school filter.
    carry = {'school': requested} if requested else {}

    return render(request, 'superadmin/platform-analytics.html', {
        'panels': panels,
        'schools': schools,
        'selected_school': selected,
        'carry_params': carry,
        'scope_label': selected.school_name if selected else f'All {len(schools)} schools',
    })
