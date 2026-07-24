"""Central announcement-delivery helper.

Single source of truth for "which published announcements is this user allowed
to see", used by every role's dashboard/notification bell/announcements page so
targeting stays consistent.

Targeting rule (an empty field means "no restriction" / all):
  - publish_to : must contain the user's role-audience key (empty = all audiences)
  - program    : must match one of the user's school programs (empty = all programs)
  - applicable_schools : must overlap the user's school(s) (empty = all schools)
  - applicable_grades  : (student/parent only) must overlap the user's grade(s)

Super Admin selects publish_to (target roles) + schools + grades when creating
the announcement; this helper resolves the viewer's scope and filters.
"""

# role -> the publish_to audience keys that role accepts.
# 'school' is a legacy key kept so old announcements still reach school admins.
AUDIENCE_KEYS_BY_ROLE = {
    'STUDENT': {'student'},
    'PARENT': {'parent'},
    'THINKING_COACH': {'teacher'},
    'PROGRAM_COORDINATOR': {'coordinator'},
    'SCHOOL_ADMIN': {'school_admin', 'school'},
}

# roles whose visibility is bound to specific grades (others are staff = all grades)
_GRADE_BOUND_ROLES = {'STUDENT', 'PARENT'}


def _user_scope(user):
    """Return (school_ids:set, programs:set, grades:set) for the given user's role.

    Defensive: never raises — returns empty sets on any lookup failure so the
    caller degrades to "no matches" rather than a 500.
    """
    role = getattr(user, 'role', None)
    school_ids, programs, grades = set(), set(), set()
    try:
        if role == 'STUDENT':
            s = getattr(user, 'student_profile', None) or getattr(user, 'student', None)
            if s:
                if s.school_id:
                    school_ids.add(s.school_id)
                    if s.school and s.school.skill_program:
                        programs.add(s.school.skill_program)
                grades.add(str(s.student_class))

        elif role == 'PARENT':
            from parent.models import Parent
            parent = Parent.objects.filter(user=user).first()
            if parent:
                for child in parent.students.filter(is_active=True).select_related('school'):
                    if child.school_id:
                        school_ids.add(child.school_id)
                        if child.school and child.school.skill_program:
                            programs.add(child.school.skill_program)
                    grades.add(str(child.student_class))

        elif role == 'THINKING_COACH':
            from teacher.models import Teacher
            t = getattr(user, 'teacher_profile', None) or Teacher.objects.filter(user=user).first()
            if t and t.school_id:
                school_ids.add(t.school_id)
                if t.school and t.school.skill_program:
                    programs.add(t.school.skill_program)

        elif role == 'PROGRAM_COORDINATOR':
            from coordinator.models import ProgramCoordinator
            from schools.models import School
            pc = ProgramCoordinator.objects.filter(user=user).first()
            ids = set()
            if pc:
                ids = set(pc.schools_assigned.values_list('id', flat=True))
            if not ids:
                ids = set(School.objects.filter(srm=user).values_list('id', flat=True))
            school_ids |= ids
            for prog in School.objects.filter(id__in=ids).values_list('skill_program', flat=True):
                if prog:
                    programs.add(prog)

        elif role == 'SCHOOL_ADMIN':
            from school_admin.models import SchoolAdmin
            sa = SchoolAdmin.objects.filter(user=user).first()
            if sa and sa.school_id:
                school_ids.add(sa.school_id)
                if sa.school and sa.school.skill_program:
                    programs.add(sa.school.skill_program)
    except Exception:
        return set(), set(), set()

    return school_ids, programs, grades


def announcements_for_user(user, ann_type=None):
    """Published announcements targeted to `user`, filtered by role + scope.

    `ann_type` optionally narrows to one type (event/newsletter/success_story).
    Returns a list of Announcement objects (unsorted; callers sort as needed).
    """
    from competencies.models import Announcement

    role = getattr(user, 'role', None)
    audience_keys = AUDIENCE_KEYS_BY_ROLE.get(role)
    if not audience_keys:
        return []

    school_ids, programs, grades = _user_scope(user)
    grade_bound = role in _GRADE_BOUND_ROLES

    qs = Announcement.objects.filter(is_published=True).prefetch_related('applicable_schools')
    if ann_type:
        qs = qs.filter(announcement_type=ann_type)

    out = []
    for a in qs:
        # audience (target roles) — empty publish_to = everyone
        pt = a.publish_to or []
        if pt and not (audience_keys & set(pt)):
            continue
        # program — empty = all programs
        if a.program and programs and a.program not in programs:
            continue
        # schools — empty = all schools
        sids = list(a.applicable_schools.values_list('id', flat=True))
        if sids and not (school_ids & set(sids)):
            continue
        # grades — only restrict grade-bound roles (students/parents)
        if grade_bound:
            ag = [str(g) for g in (a.applicable_grades or [])]
            if ag and grades and not (grades & set(ag)):
                continue
        out.append(a)
    return out
