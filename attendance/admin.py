from django.contrib import admin

from .models import (
    Timetable, TimetableSlot, AttendanceSession, AttendanceRecord,
    DailySessionFeedback, SessionPhoto, WeeklySessionFeedback, StudentProjectUpload,
)


class TimetableSlotInline(admin.TabularInline):
    model = TimetableSlot
    extra = 0


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('id', 'school', 'grade', 'division', 'academic_year', 'thinking_coach', 'is_active')
    list_filter = ('academic_year', 'grade', 'is_active')
    search_fields = ('school__school_name',)
    inlines = [TimetableSlotInline]


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'school', 'grade', 'division', 'date', 'thinking_coach', 'session_number')
    list_filter = ('academic_year', 'grade', 'date')
    inlines = [AttendanceRecordInline]


class SessionPhotoInline(admin.TabularInline):
    model = SessionPhoto
    extra = 0


@admin.register(DailySessionFeedback)
class DailySessionFeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'school', 'grade', 'division', 'date', 'session_number', 'is_project_completed')
    list_filter = ('academic_year', 'grade', 'is_project_completed', 'date')
    inlines = [SessionPhotoInline]


@admin.register(WeeklySessionFeedback)
class WeeklySessionFeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'thinking_coach', 'school', 'date_from', 'date_to', 'lab_issue')
    list_filter = ('lab_issue', 'date_from')


@admin.register(StudentProjectUpload)
class StudentProjectUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'school', 'grade', 'division', 'academic_year', 'created_by', 'created_at')
    list_filter = ('academic_year', 'grade')
    search_fields = ('title',)
    filter_horizontal = ('students',)
