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

GRADE_CHOICES = [(str(i), f'Grade {i}') for i in range(1, 13)]

ACADEMIC_YEAR_CHOICES = [
    ('2023-2024', '2023-2024'),
    ('2024-2025', '2024-2025'),
    ('2025-2026', '2025-2026'),
    ('2026-2027', '2026-2027'),
]

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
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES, default='2025-2026')
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
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES, default='2025-2026')
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
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey('student.Student', on_delete=models.CASCADE, related_name='attendance_records')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
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
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES, default='2025-2026')
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
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES, default='2025-2026')
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
