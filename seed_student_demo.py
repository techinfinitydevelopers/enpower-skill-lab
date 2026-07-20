"""
Demo data for the STUDENT dashboard (PPT slides 44-46) — seeded onto student1.

Populates everything the student dashboard reads so the UI shows real values:
  - Attendance: 3 recent perfect weeks + one week with an absent
    -> Current Streak = 3 weeks (weekly perfect), Monthly attendance ~91% = Star badge
  - Every class project marked completed -> Journey "N of 12"
  - Announcements (as a Super Admin would add via "Add Announcement", slide 8):
    2 newsletters + 1 success story, targeted to program=fsl / grade 6.

Run:  venv\\Scripts\\python manage.py shell < seed_student_demo.py
Safe to re-run: uses get_or_create; attendance records are reset each run.
Assumes student1 exists (see seed_dummy.py / seed_data.py). Password: Test@123
"""
from datetime import date, timedelta
from student.models import Student
from attendance.models import AttendanceSession, AttendanceRecord, DailySessionFeedback
from competencies.models import Project, Announcement

s = Student.objects.get(user__username='student1')
school, grade, div = s.school, str(s.student_class), s.division
ay = (AttendanceSession.objects.filter(school=school).values_list('academic_year', flat=True).first()
      or '2025-2026')

# Clean slate for this student's attendance so results are deterministic.
AttendanceRecord.objects.filter(student=s).delete()

today = date(2026, 7, 20)                       # Monday
monday_this = today - timedelta(days=today.weekday())

# week offset -> statuses for Mon/Wed/Fri sessions.
# Weeks 0,1,2 perfect; week 3 has an absent -> breaks the weekly streak at 3.
plan = {
    0: ['present', 'present', 'present'],
    1: ['present', 'present', 'present'],
    2: ['present', 'present', 'present'],
    3: ['present', 'absent',  'present'],
}

n_sess = n_rec = 0
for w, statuses in plan.items():
    monday = monday_this - timedelta(weeks=w)
    for i, st in enumerate(statuses):
        d = monday + timedelta(days=i * 2)      # Mon, Wed, Fri
        sess, made = AttendanceSession.objects.get_or_create(
            school=school, grade=grade, division=div, date=d,
            defaults={'academic_year': ay, 'session_number': w * 3 + i + 1})
        n_sess += int(made)
        AttendanceRecord.objects.create(session=sess, student=s, status=st)
        n_rec += 1

# Mark every class project completed -> Journey "N of 12".
for p in Project.objects.all():
    fb, _ = DailySessionFeedback.objects.get_or_create(
        school=school, grade=grade, division=div, project=p,
        date=today, session_number=99,
        defaults={'is_project_completed': True, 'academic_year': ay,
                  'session_title': f'{p.title} wrap-up'})
    if not fb.is_project_completed:
        fb.is_project_completed = True
        fb.save()

# Announcements as a Super Admin would add them (slide 8) — targeted to fsl / grade 6.
Announcement.objects.get_or_create(
    announcement_type='newsletter', newsletter_month='July 2026',
    defaults=dict(is_published=True, program='fsl', applicable_grades=[5, 6],
                  newsletter_date=date(2026, 7, 15),
                  newsletter_weblink='https://example.com/newsletter-july'))
Announcement.objects.get_or_create(
    announcement_type='newsletter', newsletter_month='June 2026',
    defaults=dict(is_published=True, program='fsl', applicable_grades=[6],
                  newsletter_date=date(2026, 6, 10),
                  newsletter_weblink='https://example.com/newsletter-june'))
Announcement.objects.get_or_create(
    announcement_type='success_story', story_student_name='Aarav Sharma',
    defaults=dict(is_published=True, program='fsl', applicable_grades=[6], story_grade='6',
                  story_text='Built a solar-powered water purifier that won the district science fair.',
                  story_youtube_link='https://youtube.com/watch?v=demo'))

print('sessions +', n_sess, '| records created:', n_rec)
from attendance.services import student_attendance_stats, projects_completed
a = student_attendance_stats(s)
print('current_streak (weeks):', a['current_streak'])
print('monthly_percent:', a['monthly_percent'], '| monthly_attended:', a['monthly_attended'], '/', a['monthly_total'])
print('projects_completed:', projects_completed(s))
