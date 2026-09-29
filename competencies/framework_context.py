"""Which reports apply to the signed-in person's framework.

Two rules, in opposite directions, and both read the same way:

    has_profiling     career matching, the Skill Passport idea. FSL only.
    has_kaushal_bodh  the Kaushal Bodh report. CSL only -- FSL records no
                      KB scores at all, so the page opens empty there.

A context processor because the sidebars render on every page of the student
and parent apps, and setting this per view is how eight of nine views end up
with it.

Students read their own school's framework. Parents read the framework of the
child the sidebar is currently showing, which the parent app already resolves.
"""


def _framework_of(school):
    return getattr(school, 'framework_ref', None) if school else None


def _flags(framework):
    """A framework with nothing recorded is treated as FSL, matching
    competencies.engine.profiling_enabled."""
    if framework is None:
        return {'show_skill_passport': True, 'show_kaushal_bodh': False,
                'framework_name': None}
    return {
        'show_skill_passport': bool(getattr(framework, 'has_profiling', False)),
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
