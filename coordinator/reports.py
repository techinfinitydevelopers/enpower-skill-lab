"""
Program Coordinator Reports.

The grade-wise panels from presentation slide 52, restricted to the schools
mapped to this coordinator.

Skill Passport is deliberately absent. The presentation's access matrix marks it
"n/a" for the Program Coordinator, so the top-skill-profiles panel is not built
for this role — the panel template is told to omit it rather than the data being
fetched and hidden.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

from competencies import report_panels
from .views import is_coordinator


def _mapped_schools(user):
    """Schools this coordinator is responsible for.

    Falls back to schools where they are named as relationship manager, which is
    how older records were linked before `schools_assigned` existed.
    """
    from coordinator.models import ProgramCoordinator
    from schools.models import School

    pc = ProgramCoordinator.objects.filter(user=user).first()
    ids = set(pc.schools_assigned.values_list('id', flat=True)) if pc else set()
    if not ids:
        ids = set(School.objects.filter(srm=user).values_list('id', flat=True))
    return list(School.objects.filter(id__in=ids).order_by('school_name'))


@login_required
@user_passes_test(is_coordinator)
def coordinator_reports(request):
    schools = _mapped_schools(request.user)

    requested = (request.GET.get('school') or '').strip()
    selected = next((s for s in schools if str(s.id) == requested), None)
    scope = [selected.id] if selected else [s.id for s in schools]

    panels = report_panels.build(
        scope,
        month=(request.GET.get('month') or None),
        include_profiles=False,
    )

    return render(request, 'coordinator/reports.html', {
        'panels': panels,
        'schools': schools,
        'selected_school': selected,
        'carry_params': {'school': requested} if requested else {},
        'scope_label': (selected.school_name if selected
                        else f'{len(schools)} assigned school{"" if len(schools) == 1 else "s"}'),
        'hide_profiles': True,
    })
