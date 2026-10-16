"""Which reports apply to the signed-in person's framework.

Four settings, all read the same way, all set from Manage Frameworks:

    show_annual_report   whether the annual report page exists at all
    annual_report_title  what it is called -- "Annual Skill Report" on CSL+,
                         "Annual Skill Passport" on FSL
    has_kaushal_bodh     the Kaushal Bodh report. CSL only -- FSL records no
                         KB scores at all, so the page opens empty there.
    has_profiling        career matching. It used to stand in for the annual
                         report as well; it cannot, because CSL+ wants that
                         report without career matches and CSL Foundation
                         wants no report at all.

A context processor because the sidebars render on every page of the student
and parent apps, and setting this per view is how eight of nine views end up
with it.

Students read their own school's framework. Parents read the framework of the
child the sidebar is currently showing, which the parent app already resolves.
"""


def _framework_of(school):
    return getattr(school, 'framework_ref', None) if school else None


DEFAULT_ANNUAL_TITLE = 'Annual Skill Passport'


def _flags(framework):
    """A framework with nothing recorded is treated as FSL, matching
    competencies.engine.profiling_enabled."""
    if framework is None:
        return {'show_annual_report': True,
                'annual_report_title': DEFAULT_ANNUAL_TITLE,
                'show_career_matches': True,
                'show_kaushal_bodh': False,
                'framework_name': None}
    return {
        'show_annual_report': bool(
            getattr(framework, 'show_annual_report', True)),
        'annual_report_title': (getattr(framework, 'annual_report_title', '')
                                or DEFAULT_ANNUAL_TITLE),
        'show_career_matches': bool(getattr(framework, 'has_profiling', False)),
        'show_kaushal_bodh': bool(getattr(framework, 'has_kaushal_bodh', True)),
        'framework_name': getattr(framework, 'name', None),
    }


def framework_flags(request):
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated):
        return {}

    role = getattr(user, 'role', None)

    if role == 'STUDENT':
        student = (getattr(user, 'student_profile', None)
                   or getattr(user, 'student', None))
        return _flags(_framework_of(getattr(student, 'school', None)))

    if role == 'PARENT':
        # The same child parent_sidebar picks, so the reports offered match
        # the child whose links the sidebar is building.
        from parent.models import Parent

        parent = Parent.objects.filter(user=user).first()
        if parent is None:
            return {}
        child = parent.students.filter(is_active=True).first()
        return _flags(_framework_of(getattr(child, 'school', None)))

    return {}
