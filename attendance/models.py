"""
ESL Dashboard — session / schedule / attendance / feedback models.

All models here are ADDITIVE (new app, isolated migrations). They reference
existing models via string FKs to avoid import cycles. Implements PPT slides:
  12-13 Timetable (Program Coordinator)
  14    Attendance (Thinking Coach)
  15    Daily session feedback (Thinking Coach)
  16    Weekly session feedback (Thinking Coach)
  17    Student project upload (Thinking Coach)
"""
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from enpower_skill_lab.academic_year import (
    academic_year_choices, current_academic_year)

GRADE_CHOICES = [(str(i), f'Grade {i}') for i in range(1, 13)]

# Generated around today rather than typed out. A hand-written list is a
# list that stops: this one ran out while the schools had moved on.
ACADEMIC_YEAR_CHOICES = academic_year_choices()

DAY_CHOICES = [
    ('mon', 'Monday'), ('tue', 'Tuesday'), ('wed', 'Wednesday'),
    ('thu', 'Thursday'), ('fri', 'Friday'), ('sat', 'Saturday'), ('sun', 'Sunday'),
]


# ============================================================
# SLIDE 12-13 — Timetable / Schedule (Program Coordinator)
# ============================================================
class Timetable(models.Model):
    """A schedule uploaded by the SRM (Program Coordinator) for a school class.
    Flow: select school -> assign thinking coach -> grade + division -> upload schedule."""
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='timetables')
    thinking_coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'role': 'THINKING_COACH'}, related_name='coach_timetables',
    )
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES)
    division = models.CharField(max_length=5)
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES, default=current_academic_year)
    program = models.CharField(max_length=50, blank=True, help_text='Program name (FSL / CSL plus / CSL foundation) — replaces "instrument"')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    schedule_file = models.FileField(upload_to='timetables/', blank=True, null=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_timetables',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Timetable {self.school_id} G{self.grade}{self.division} {self.academic_year}"


class TimetableSlot(models.Model):
    """Optional structured slot rows for a timetable (day/period/time/project)."""
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='slots')
    day_of_week = models.CharField(max_length=3, choices=DAY_CHOICES)
    period_number = models.PositiveSmallIntegerField(default=1)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    project = models.ForeignKey('competencies.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='timetable_slots')
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['day_of_week', 'period_number']


# ============================================================
# SLIDE 14 — Attendance (Thinking Coach)
# ============================================================
class AttendanceSession(models.Model):
    """One class-session on a date for which attendance is marked."""
    CLASS_STATUS_CHOICES = [
        ('held', 'Class Held'),
        ('cancelled', 'Class Cancelled'),
    ]
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='attendance_sessions')
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES)
    division = models.CharField(max_length=5)
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES, default=current_academic_year)
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    timetable = models.ForeignKey('Timetable', on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_sessions')
    class_status = models.CharField(max_length=10, choices=CLASS_STATUS_CHOICES, default='held')
    thinking_coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attendance_sessions',
    )
    project = models.ForeignKey('competencies.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_sessions')
    session_number = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = [('school', 'grade', 'division', 'date', 'session_number')]

    def __str__(self):
        return f"Attendance {self.school_id} G{self.grade}{self.division} {self.date}"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    CATEGORY_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
    ]
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey('student.Student', on_delete=models.CASCADE, related_name='attendance_records')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    # Optional A/B/C performance/engagement category the coach can tag per session.
    # Blank by default so it never affects existing present/absent behaviour.
    category = models.CharField(max_length=1, choices=CATEGORY_CHOICES, blank=True, default='')
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('session', 'student')]

    def __str__(self):
        return f"{self.student_id} - {self.status} ({self.session.date})"


# ============================================================
# SLIDE 15 — Daily Session Feedback (Thinking Coach)
# ============================================================
class DailySessionFeedback(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='daily_feedbacks')
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES)
    division = models.CharField(max_length=5)
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES, default=current_academic_year)
    date = models.DateField()
    project = models.ForeignKey('competencies.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_feedbacks')
    session_number = models.PositiveSmallIntegerField(null=True, blank=True)
    session_title = models.CharField(max_length=200, blank=True)
    session_description = models.TextField(blank=True)
    thinking_coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='daily_feedbacks',
    )
    # Ratings 1-5 (1=Poor .. 5=Excellent)
    rating_engagement = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_delivery_ease = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_resources = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    rating_time_management = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    is_project_completed = models.BooleanField(default=False, help_text='TC marks project complete once all sessions done')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Daily feedback {self.school_id} G{self.grade}{self.division} {self.date}"


class SessionPhoto(models.Model):
    """Class activity / project photos for a daily session (max 3 enforced in view)."""
    feedback = models.ForeignKey(DailySessionFeedback, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='session_photos/')
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ============================================================
# SLIDE 16 — Weekly Session Feedback (qualitative)
# ============================================================
class WeeklySessionFeedback(models.Model):
    thinking_coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='weekly_feedbacks',
    )
    school = models.ForeignKey('schools.School', on_delete=models.SET_NULL, null=True, blank=True, related_name='weekly_feedbacks')
    date_from = models.DateField()
    date_to = models.DateField()
    went_wrong = models.CharField(max_length=200, blank=True)
    went_well = models.CharField(max_length=200, blank=True)
    new_tried = models.CharField(max_length=200, blank=True)
    lab_issue = models.BooleanField(default=False)
    lab_issue_detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_from']

    def __str__(self):
        return f"Weekly feedback {self.thinking_coach_id} {self.date_from}..{self.date_to}"


# ============================================================
# SLIDE 17 — Student Project Upload (Thinking Coach, 3/grade/year)
# ============================================================
class StudentProjectUpload(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='student_project_uploads')
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES)
    division = models.CharField(max_length=5)
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES, default=current_academic_year)
    project = models.ForeignKey('competencies.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='student_uploads')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='student_projects/', blank=True, null=True, help_text='image/ppt/pdf/doc')
    video_link = models.URLField(blank=True)
    description = models.TextField(blank=True)
    students = models.ManyToManyField('student.Student', blank=True, related_name='project_uploads')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_student_uploads',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} (G{self.grade}{self.division})"

    PICTURE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.heic')

    @property
    def is_picture(self):
        """Can this be shown on the page, rather than linked to?

        Coaches upload photographs of the work far more often than documents,
        and a photograph behind a "View File" link looks to the reader like
        nothing arrived at all.
        """
        name = getattr(self.file, 'name', '') or ''
        return name.lower().endswith(self.PICTURE_SUFFIXES)


# ============================================================
# Project uploads: "has this person seen the new ones yet?"
# ============================================================
class ProjectUploadSeen(models.Model):
    """When a student or parent last looked at their project notifications.

    A coach uploads a project and tags the students who did it. Slide 47 asks
    for that to reach the student and the parent with a notification, and the
    bell could not carry it: Announcement targets a role, a programme, a school
    and a grade, never an individual, so "your project is up" would have gone
    to the whole year group instead of the two children who built it.

    The uploads themselves already know who they belong to, so all that was
    missing was a mark for how far each person had read. Anything newer than
    this is counted as new; opening the dashboard, which is where the projects
    are listed, moves the mark forward.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='project_upload_seen')
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Project Upload — Last Seen'
        verbose_name_plural = 'Project Uploads — Last Seen'

    def __str__(self):
        return f"{self.user} last saw uploads at {self.last_seen_at}"
