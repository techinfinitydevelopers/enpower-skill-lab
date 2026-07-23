"""Context processor that feeds the header bell-icon on the student and parent
dashboards with the announcements actually targeted to that user (PPT slide 8).

Exposes on every template:
  nav_announcements       - list of Announcement objects (latest first, max 8)
  nav_announcement_count  - how many (used for the bell badge)
"""


def nav_notifications(request):
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return {}

    role = getattr(user, 'role', None)
    anns = []
    try:
        if role == 'STUDENT':
            from student.views import announcements_for_student
            student = getattr(user, 'student_profile', None) or getattr(user, 'student', None)
            anns = announcements_for_student(student)
        elif role == 'PARENT':
            anns = _parent_announcements(user)
    except Exception:
        anns = []

    anns = sorted(anns, key=lambda a: a.created_at, reverse=True)[:8]
    return {'nav_announcements': anns, 'nav_announcement_count': len(anns)}


def _parent_announcements(user):
    """Announcements targeted to a parent's children (school + program + grade,
    publish-to includes 'parent' for events; empty targeting = all)."""
    from parent.models import Parent
    from competencies.models import Announcement
    try:
        parent = Parent.objects.get(user=user)
    except Parent.DoesNotExist:
        return []
    children = list(parent.students.filter(is_active=True).select_related('school'))
    if not children:
        return []
    school_ids = {c.school_id for c in children if c.school_id}
    programs = {c.school.skill_program for c in children if c.school and c.school.skill_program}
    grades = {str(c.student_class) for c in children}

    out = []
    for a in (Announcement.objects.filter(is_published=True)
              .prefetch_related('applicable_schools')):
        pt = a.publish_to or []
        if pt and 'parent' not in pt:
            continue
        if a.program and programs and a.program not in programs:
            continue
        sids = list(a.applicable_schools.values_list('id', flat=True))
        if sids and not (school_ids & set(sids)):
            continue
        ag = [str(g) for g in (a.applicable_grades or [])]
        if ag and not (grades & set(ag)):
            continue
        out.append(a)
    return out
