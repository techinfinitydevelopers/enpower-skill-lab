"""Context available to every parent template."""


def parent_sidebar(request):
    """Expose the parent's first child so sidebar links can resolve.

    The sidebar lives in parent/base.html and is rendered on every parent page,
    but only the dashboard view supplies child data. Its "Student Performance
    Summary" and "Annual Skill Report" links were therefore left as href="#"
    and went nowhere. This gives the sidebar a child id to build real URLs
    from; the dashboard's JS then repoints them when a different child is
    selected.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or getattr(user, 'role', None) != 'PARENT':
        return {}

    try:
        from .models import Parent
        parent = Parent.objects.filter(user=user).first()
        if not parent:
            return {}
        child = parent.students.filter(is_active=True).first()
        if not child:
            return {}
        return {
            'sidebar_child_id': child.id,
            'sidebar_child_count': parent.students.filter(is_active=True).count(),
        }
    except Exception:
        return {}
