"""
Select rows on a list and delete them together.

Deleting one at a time was the only option, which on a list of a thousand
students is not an option at all. One registry, two views: a preview that
says exactly what is about to be destroyed, and the delete itself.

The preview exists because these deletions are not small. Removing a school
takes its classes and its school admins with it (CASCADE), and leaves its
students and teachers behind with no school at all (SET_NULL) -- so this
module deletes those explicitly rather than stranding them. Removing a
student takes every score entry, project report and feedback row they have.
Nothing on screen said so before.

It also fixes an inconsistency in the single-row deletes: School Admin and
Coordinator deleted the login account along with the profile, while Student,
Teacher and Parent did not -- leaving an account that could still sign in
with no profile behind it. Everything here removes both.

Each entry declares:

  roles     who may run it, checked against the signed-in user.
  label     singular/plural, for the messages.
  rows      the queryset the list shows; ids are filtered through it, so a
            key cannot be used to reach a row the page would not display.
  name      what to call one row in the report.
  impact    (description, count) pairs -- what goes with the selection.
"""

import json

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.http.request import RawPostDataException


# ── helpers ─────────────────────────────────────────────────────────────

def _student_name(s):
    return ' '.join(p for p in (s.first_name, getattr(s, 'last_name', '')) if p)


def delete_with_user(obj):
    """Remove a profile and the login account behind it.

    The FK is SET_NULL on Student, Teacher and Parent, so deleting the profile
    alone leaves a working login with nothing attached to it. On SchoolAdmin
    and Coordinator it is CASCADE, so deleting the user is enough -- but doing
    it in this order is correct either way.
    """
    user = getattr(obj, 'user', None)
    obj.delete()
    if user is not None:
        user.delete()


def purge_people(qs):
    """Delete these profiles and their login accounts in two statements.

    One transaction per row is fine for five rows and impossible for a
    thousand: the worker is killed at 60 seconds, which would leave the list
    half deleted. Django cascades in bulk here; only the login accounts need
    a second pass, because the FK that points at them is SET_NULL.
    """
    from django.contrib.auth import get_user_model

    user_ids = list(qs.filter(user__isnull=False).values_list('user_id', flat=True))
    count = qs.count()
    qs.delete()
    if user_ids:
        get_user_model().objects.filter(id__in=user_ids).delete()
    return count


def purge_schools(qs):
    """Delete these schools, taking their people rather than stranding them."""
    from school_admin.models import SchoolAdmin
    from student.models import Student
    from teacher.models import Teacher

    ids = list(qs.values_list('id', flat=True))
    for model in (Student, Teacher, SchoolAdmin):
        purge_people(model.objects.filter(school_id__in=ids))
    count = qs.count()
    qs.delete()
    return count


# ── impact: what a selection takes with it ──────────────────────────────

def _student_impact(qs):
    from competencies.models import (ProjectReport, ScoreEntry,
                                     StudentAssessmentFeedback,
                                     StudentProjectFeedback)
    from attendance.models import AttendanceRecord
    from parent.models import Parent

    ids = list(qs.values_list('id', flat=True))
    # A parent whose every child is in the selection is left with none. That
    # is worth saying out loud; it is not worth deleting them by surprise.
    orphaned = sum(1 for p in Parent.objects.prefetch_related('students')
                   .filter(students__in=ids).distinct()
                   if not {s.id for s in p.students.all()} - set(ids))
    return [
        ('login account', qs.filter(user__isnull=False).count()),
        ('score entry', ScoreEntry.objects.filter(student_id__in=ids).count()),
        ('project report', ProjectReport.objects.filter(student_id__in=ids).count()),
        ('assessment feedback',
         StudentAssessmentFeedback.objects.filter(student_id__in=ids).count()),
        ('project feedback',
         StudentProjectFeedback.objects.filter(student_id__in=ids).count()),
        ('attendance record',
         AttendanceRecord.objects.filter(student_id__in=ids).count()),
        ('parent left with no children', orphaned),
    ]


def _school_impact(qs):
    from schools.models import Class
    from school_admin.models import SchoolAdmin
    from student.models import Student
    from teacher.models import Teacher

    ids = list(qs.values_list('id', flat=True))
    students = Student.objects.filter(school_id__in=ids)
    rows = [
        ('class', Class.objects.filter(school_id__in=ids).count()),
        ('school admin', SchoolAdmin.objects.filter(school_id__in=ids).count()),
        ('thinking coach', Teacher.objects.filter(school_id__in=ids).count()),
        ('student', students.count()),
    ]
    rows += [(f'  {d}', n) for d, n in _student_impact(students) if n]
    return rows


def _simple_impact(qs):
    return [('login account', qs.filter(user__isnull=False).count())]


# ── deletion: how one row goes ──────────────────────────────────────────

def delete_school_and_its_people(school):
    """Take the school's people with it instead of stranding them.

    Classes and school admins are CASCADE and would go anyway, but their login
    accounts would not; students and teachers are SET_NULL and would survive
    with a null school, invisible on every list and still able to sign in.
    """
    from schools.models import School

    purge_schools(School.objects.filter(pk=school.pk))


# ── the registry ────────────────────────────────────────────────────────

def _registry():
    from coordinator.models import ProgramCoordinator
    from parent.models import Parent
    from school_admin.models import SchoolAdmin
    from schools.models import School
    from student.models import Student
    from teacher.models import Teacher

    return {
        'schools': {
            'roles': ('SUPER_ADMIN',),
            'label': ('school', 'schools'),
            'rows': lambda r: School.objects.all(),
            'name': lambda s: s.school_name,
            'impact': _school_impact,
            'delete': delete_school_and_its_people,
            'purge': purge_schools,
        },
        'students': {
            'roles': ('SUPER_ADMIN',),
            'label': ('student', 'students'),
            'rows': lambda r: Student.objects.all(),
            'name': _student_name,
            'impact': _student_impact,
            'delete': delete_with_user,
            'purge': purge_people,
        },
        'teachers': {
            'roles': ('SUPER_ADMIN',),
            'label': ('thinking coach', 'thinking coaches'),
            'rows': lambda r: Teacher.objects.all(),
            'name': lambda t: t.full_name,
            'impact': _simple_impact,
            'delete': delete_with_user,
            'purge': purge_people,
        },
        'parents': {
            'roles': ('SUPER_ADMIN',),
            'label': ('parent', 'parents'),
            'rows': lambda r: Parent.objects.all(),
            'name': lambda p: p.full_name,
            'impact': _simple_impact,
            'delete': delete_with_user,
            'purge': purge_people,
        },
        'coordinators': {
            'roles': ('SUPER_ADMIN',),
            'label': ('program coordinator', 'program coordinators'),
            'rows': lambda r: ProgramCoordinator.objects.all(),
            'name': lambda c: c.full_name,
            'impact': _simple_impact,
            'delete': delete_with_user,
            'purge': purge_people,
        },
        'school-admins': {
            'roles': ('SUPER_ADMIN',),
            'label': ('school admin', 'school admins'),
            'rows': lambda r: SchoolAdmin.objects.all(),
            'name': lambda a: a.full_name,
            'impact': _simple_impact,
            'delete': delete_with_user,
            'purge': purge_people,
        },
    }


# ── request plumbing ────────────────────────────────────────────────────

def _entry_for(request, key):
    entry = _registry().get(key)
    if entry is None:
        raise PermissionDenied('Unknown list')
    # Decided from the signed-in user. The key names the list; it does not
    # grant access to it.
    if getattr(request.user, 'role', None) not in entry['roles']:
        raise PermissionDenied('This action is not available to your role')
    return entry


def _selected(request, entry):
    """The requested ids, narrowed to rows this list actually shows."""
    raw = request.POST.getlist('ids') or request.POST.getlist('ids[]')
    if not raw:
        # A select-all sends one JSON body rather than one field per id:
        # DATA_UPLOAD_MAX_NUMBER_FIELDS is 1000, so a list of 1290 students
        # posted as form fields is rejected before any view sees it.
        try:
            raw = json.loads((request.body or b'{}').decode() or '{}').get('ids') or []
        except (ValueError, UnicodeDecodeError, AttributeError,
                RawPostDataException):
            raw = []
    ids = {int(v) for v in raw if str(v).strip().lstrip('-').isdigit()}
    return entry['rows'](request).filter(id__in=ids)


# ── the views ───────────────────────────────────────────────────────────

def preview(request, key):
    """What the selection would destroy, before anything is destroyed."""
    if request.method != 'POST':
        raise PermissionDenied('POST only')
    entry = _entry_for(request, key)
    qs = _selected(request, entry)
    count = qs.count()
    singular, plural = entry['label']

    return JsonResponse({
        'count': count,
        'label': singular if count == 1 else plural,
        'names': [entry['name'](obj) for obj in qs[:8]],
        'more': max(0, count - 8),
        'impact': [{'what': what, 'count': n}
                   for what, n in entry['impact'](qs) if n],
    })


def bulk_delete(request, key):
    """Delete the selection, reporting each row that would not go."""
    if request.method != 'POST':
        raise PermissionDenied('POST only')
    entry = _entry_for(request, key)
    ids = list(_selected(request, entry).values_list('id', flat=True))
    singular, plural = entry['label']

    def rows():
        return entry['rows'](request).filter(id__in=ids)

    deleted, failures = 0, []
    if ids:
        try:
            with transaction.atomic():
                deleted = entry['purge'](rows())
        except Exception:                              # noqa: BLE001
            # Something in the batch will not go, and the transaction took
            # the rest back with it. Retry one at a time -- slower, but the
            # only way to say which row is the problem, and that detail is
            # worth the queries exactly when something has gone wrong.
            deleted = 0
            for obj in list(rows()):
                name = entry['name'](obj)
                try:
                    with transaction.atomic():
                        entry['delete'](obj)
                    deleted += 1
                except Exception as exc:               # noqa: BLE001
                    failures.append({'name': name, 'reason': str(exc)[:200]})

    label = singular if deleted == 1 else plural
    if deleted and not failures:
        message = f'{deleted} {label} deleted.'
    elif deleted:
        message = f'{deleted} {label} deleted, {len(failures)} could not be.'
    else:
        message = f'Nothing was deleted; {len(failures)} could not be removed.' \
            if failures else 'Nothing was selected.'

    return JsonResponse({'deleted': deleted, 'failed': len(failures),
                         'failures': failures, 'message': message})
