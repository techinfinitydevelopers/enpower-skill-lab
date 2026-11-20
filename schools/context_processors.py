"""School branding available to every template.

The school logo has to appear on three different dashboards — School Admin,
Student and Parent — and on every page of each, because it sits in the
sidebar header that `base.html` renders. Passing it from each view would mean
touching dozens of views and forgetting one, so it is resolved once here.

Each role reaches its school by a different path:

* School Admin -> SchoolAdmin.school
* Student      -> Student.school
* Parent       -> the first active child's school

A parent with children in two schools is a real case. The first child's
school is used, the same child the sidebar already resolves in
`parent.context_processors.parent_sidebar`, so the two agree.

`school_logo_url` is None whenever there is no logo. Templates render the
school logo only when it is set, which keeps the sidebar exactly as it is for
every school that has not uploaded one.
"""


def school_branding(request):
    """Add `school_logo_url` and `branding_school` for the signed-in user."""
    empty = {'school_logo_url': None, 'branding_school': None}

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return empty

    role = getattr(user, 'role', None)
    school = None

    try:
        if role == 'SCHOOL_ADMIN':
            from school_admin.models import SchoolAdmin
            profile = (SchoolAdmin.objects
                       .select_related('school')
                       .filter(user=user)
                       .first())
            school = profile.school if profile else None

        elif role == 'STUDENT':
            from student.models import Student
            profile = (Student.objects
                       .select_related('school')
                       .filter(user=user)
                       .first())
            school = profile.school if profile else None

        elif role == 'PARENT':
            from parent.models import Parent
            parent = Parent.objects.filter(user=user).first()
            child = (parent.students
                     .select_related('school')
                     .filter(is_active=True)
                     .first()) if parent else None
            school = child.school if child else None
    except Exception:
        # Branding must never be the reason a page fails to render.
        return empty

    if not school:
        return empty

    logo = getattr(school, 'school_logo', None)
    url = None
    if logo:
        try:
            url = logo.url
        except ValueError:
            # FieldFile.url raises when the field holds no file.
            url = None

    return {'school_logo_url': url, 'branding_school': school}
