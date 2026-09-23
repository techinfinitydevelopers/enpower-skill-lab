"""Keep Timetable and Class agreeing about who the coach is.

They are two tables holding the same four facts -- school, grade, division,
academic year -- plus a coach, and nothing connected them. Different screens
read different ones:

    Class      the parent's "who teaches my child", the School Admin's
               "what does this coach teach"
    Timetable  the coach's own schedule, and attendance

So a coordinator filling in 50 timetables left parents seeing "-" for the
coach, because the Class rows those screens read had never been created. And
a Super Admin assigning a coach on the Class list changed nothing the coach
could see.

Rather than ask anyone to enter it twice, saving either one now carries the
coach across.

Direction matters. A Timetable holds everything a Class needs, so saving one
creates the Class outright. A Class holds nothing about *when* a class runs,
so it never creates a Timetable -- an invented schedule with no days or times
would show up on the coach's timetable as an empty row, which is worse than
the Class simply not having a schedule yet. It only updates a Timetable that
already exists.

The loop between the two is broken by writing with queryset .update(), which
does not fire post_save.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _match(model, timetable_or_class):
    """The rows in `model` describing the same class as this object."""
    obj = timetable_or_class
    if not obj.school_id or not obj.grade or not obj.division:
        return model.objects.none()
    return model.objects.filter(
        school_id=obj.school_id,
        grade=obj.grade,
        division=obj.division,
        academic_year=obj.academic_year,
    )


@receiver(post_save, sender='attendance.Timetable',
          dispatch_uid='timetable_syncs_class')
def timetable_syncs_class(sender, instance, **kwargs):
    """A saved schedule gives its class a Class row, and its coach."""
    from schools.models import Class

    try:
        existing = _match(Class, instance)
        if not existing.exists():
            if not (instance.school_id and instance.grade and instance.division):
                return
            # Class.save() fills in class_name and class_code itself.
            Class.objects.create(
                school_id=instance.school_id,
                grade=instance.grade,
                division=instance.division,
                academic_year=instance.academic_year,
                thinking_coach_id=instance.thinking_coach_id,
            )
            return
        if instance.thinking_coach_id:
            # .update() rather than .save(): it writes without firing
            # post_save, which is what stops the two signals calling each
            # other back and forth.
            existing.update(thinking_coach_id=instance.thinking_coach_id)
    except Exception:                                  # noqa: BLE001
        # Never let this break the save that triggered it. A schedule that
        # stored fine but could not mirror itself is a reporting gap; a
        # schedule that would not save at all is a broken screen.
        logger.exception('Could not sync Timetable %s onto a Class', instance.pk)


@receiver(post_save, sender='schools.Class',
          dispatch_uid='class_syncs_timetable')
def class_syncs_timetable(sender, instance, **kwargs):
    """A coach assigned on the Class list reaches the coach's own screens.

    Only ever updates. Creating a Timetable here would invent a schedule
    nobody set the times for.
    """
    from attendance.models import Timetable

    if not instance.thinking_coach_id:
        return
    try:
        _match(Timetable, instance).exclude(
            thinking_coach_id=instance.thinking_coach_id
        ).update(thinking_coach_id=instance.thinking_coach_id)
    except Exception:                                  # noqa: BLE001
        logger.exception('Could not sync Class %s onto a Timetable', instance.pk)
