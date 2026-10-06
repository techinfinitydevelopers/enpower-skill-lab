"""Project uploads in the notification bell, for students and their parents.

Slide 47 point 6 asks for a coach's upload to reach the student and the parent
with a notification. The existing bell could not carry it: `Announcement`
targets a role, a programme, a school and a grade, never one child, so "your
project is up" would have gone to the whole year group rather than the two
students who built the thing.

The uploads already know who they belong to -- the coach tags them -- so the
only missing piece was how far each person had read. `ProjectUploadSeen` holds
that mark, and anything newer counts as new.

Exposed on every template:
    nav_project_uploads      the latest uploads for this person, newest first
    nav_project_upload_count how many of those they have not seen
"""

from django.utils import timezone

MAX_SHOWN = 5


def _students_for(user):
    """The children whose uploads this person should be told about."""
    role = getattr(user, 'role', None)

    if role == 'STUDENT':
        student = (getattr(user, 'student_profile', None)
                   or getattr(user, 'student', None))
        return [student] if student else []

    if role == 'PARENT':
        from parent.models import Parent

        parent = Parent.objects.filter(user=user).first()
        if parent is None:
            return []
        return list(parent.students.filter(is_active=True))

    return []


def uploads_for(user):
    """Latest project uploads for whoever this is, newest first.

    A parent with two children sees both children's, which is why this
    de-duplicates: one upload tagged to two siblings is one notification.
    """
    students = _students_for(user)
    if not students:
        return []

    from .services import student_project_uploads

    seen, rows = set(), []
    for student in students:
        for upload in student_project_uploads(student):
            if upload.pk in seen:
                continue
            seen.add(upload.pk)
            rows.append(upload)

    rows.sort(key=lambda u: u.created_at, reverse=True)
    return rows[:MAX_SHOWN]


def unseen_count(user, uploads):
    """How many of these the person has not looked at.

    No mark yet means they have never opened the dashboard, so everything is
    new -- which is the right answer for someone signing in for the first time
    after their coach uploaded something.
    """
    from .models import ProjectUploadSeen

    row = ProjectUploadSeen.objects.filter(user=user).first()
    if row is None or row.last_seen_at is None:
        return len(uploads)
    return sum(1 for u in uploads if u.created_at > row.last_seen_at)


def mark_seen(user):
    """Called from the dashboard, which is where the uploads are listed."""
    from .models import ProjectUploadSeen

    if not (user and getattr(user, 'is_authenticated', False)):
        return
    ProjectUploadSeen.objects.update_or_create(
        user=user, defaults={'last_seen_at': timezone.now()})


def project_upload_notifications(request):
    """Context processor. Never raises -- a bell that 500s is worse than a
    bell that is empty."""
    # Always both keys, for every caller. The bell adds this count to the
    # announcement one, and a filter *argument* that resolves to nothing
    # raises rather than falling back to the empty string the way a filter's
    # input does -- so an absent key takes the whole page down, not just the
    # badge.
    empty = {'nav_project_uploads': [], 'nav_project_upload_count': 0}

    user = getattr(request, 'user', None)
    if not (user and getattr(user, 'is_authenticated', False)):
        return empty
    if getattr(user, 'role', None) not in ('STUDENT', 'PARENT'):
        return empty

    try:
        uploads = uploads_for(user)
        return {'nav_project_uploads': uploads,
                'nav_project_upload_count': unseen_count(user, uploads)}
    except Exception:
        return empty
