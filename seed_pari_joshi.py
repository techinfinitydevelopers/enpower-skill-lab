"""
Full STUDENT-dashboard demo data for one student: **Pari Joshi**.

Populates EVERYTHING the student sidebar shows so the whole dashboard is live:
  Dashboard      - attendance streak, monthly-attendance badge, Journey N of 12,
                   events / newsletter / success story, View Projects
  Skill Passport - per-project ProjectReport (runs the profiling engine)
  Annual Passport- annual competency scores + top profiles (engine)
  Badges         - Star/Champion/Legend by monthly attendance
  Event Calendar - published events targeted to her program/grade
  Newsletter     - published newsletters
  Announcements  - all of the above combined

Login created:  username = pari.joshi   password = Test@123

Run:  venv\\Scripts\\python manage.py shell < seed_pari_joshi.py
Safe to re-run (get_or_create + deterministic attendance reset).
Requires the competency framework (projects / assessments / competencies /
profiles) to already exist — seed_data.py / the app setup creates these.
"""
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from schools.models import School, Class
from student.models import Student
from attendance.models import AttendanceSession, AttendanceRecord, DailySessionFeedback, StudentProjectUpload
from competencies.models import (
    Project, AssessmentCompetency, ScoreEntry, Announcement, Competency,
)
from competencies.engine import generate_project_report

User = get_user_model()
PWD = 'Test@123'

school = School.objects.filter(school_name__icontains='Shiv Vani').first() or School.objects.first()
GRADE, DIV = '6', 'A'
AY = (AttendanceSession.objects.filter(school=school).values_list('academic_year', flat=True).first()
      or '2025-2026')

# ── 1. User + Student "Pari Joshi" ──────────────────────────────────────────
u, _ = User.objects.get_or_create(
    username='pari.joshi',
    defaults={'role': 'STUDENT', 'email': 'pari.joshi@example.com',
              'first_name': 'Pari', 'last_name': 'Joshi', 'is_active': True})
u.set_password(PWD); u.role = 'STUDENT'; u.save()

pari, _ = Student.objects.get_or_create(
    gr_number='GR6PARI',
    defaults={'user': u, 'first_name': 'Pari', 'last_name': 'Joshi', 'gender': 'female',
              'date_of_birth': date(2013, 5, 12), 'nationality': 'Indian',
              'school': school, 'school_name': school.school_name,
              'student_class': GRADE, 'division': DIV, 'roll_number': '1',
              'academic_year': AY, 'school_board': 'CBSE',
              'school_email': 'pari.joshi@example.com', 'skill_lab_reg_id': 'SLPARI',
              'enrollment_date': date(2025, 6, 1), 'attendance_status': 'active',
              'emergency_name': 'Guardian', 'emergency_relationship': 'father',
              'emergency_mobile': '9000000001'})
# Ensure key fields even if the student already existed.
Student.objects.filter(pk=pari.pk).update(
    user=u, school=school, student_class=GRADE, division=DIV, is_active=True)
pari.refresh_from_db()

Class.objects.get_or_create(
    school=school, grade=GRADE, division=DIV, academic_year=AY,
    defaults={'class_name': f'Std {GRADE}{DIV}', 'is_active': True})

# ── 2. Attendance: weekly streak + monthly ~91% (Star badge) ────────────────
AttendanceRecord.objects.filter(student=pari).delete()
today = date(2026, 7, 20)
monday_this = today - timedelta(days=today.weekday())
plan = {0: ['present', 'present', 'present'],
        1: ['present', 'present', 'present'],
        2: ['present', 'present', 'present'],
        3: ['present', 'absent',  'present']}   # breaks streak at 3 weeks
for w, statuses in plan.items():
    monday = monday_this - timedelta(weeks=w)
    for i, st in enumerate(statuses):
        d = monday + timedelta(days=i * 2)
        sess, _ = AttendanceSession.objects.get_or_create(
            school=school, grade=GRADE, division=DIV, date=d,
            defaults={'academic_year': AY, 'session_number': w * 3 + i + 1})
        AttendanceRecord.objects.create(session=sess, student=pari, status=st)

# ── 3. Journey: mark every class project completed (N of 12) ────────────────
for p in Project.objects.all():
    DailySessionFeedback.objects.get_or_create(
        school=school, grade=GRADE, division=DIV, project=p, date=today, session_number=99,
        defaults={'is_project_completed': True, 'academic_year': AY,
                  'session_title': f'{p.title} wrap-up'})

# ── 4. Announcements (Super Admin "Add Announcement") for fsl / grade 6 ──────
Announcement.objects.get_or_create(
    announcement_type='event', event_name='Science Fair Competition',
    defaults=dict(is_published=True, program='fsl', applicable_grades=[5, 6],
                  event_date=date(2026, 8, 1), event_description='Annual inter-school science fair.',
                  event_link='https://example.com/science-fair'))
Announcement.objects.get_or_create(
    announcement_type='newsletter', newsletter_month='July 2026',
    defaults=dict(is_published=True, program='fsl', applicable_grades=[5, 6],
                  newsletter_date=date(2026, 7, 15), newsletter_weblink='https://example.com/nl-july'))
Announcement.objects.get_or_create(
    announcement_type='newsletter', newsletter_month='June 2026',
    defaults=dict(is_published=True, program='fsl', applicable_grades=[6],
                  newsletter_date=date(2026, 6, 10), newsletter_weblink='https://example.com/nl-june'))
Announcement.objects.get_or_create(
    announcement_type='success_story', story_student_name='Pari Joshi',
    defaults=dict(is_published=True, program='fsl', applicable_grades=[6], story_grade='6',
                  story_text='Designed an eco-friendly water filter showcased at the district fair.',
                  story_youtube_link='https://youtube.com/watch?v=demo'))

# ── 5. View Projects (StudentProjectUpload, slide 17) ───────────────────────
proj0 = Project.objects.first()
up, _ = StudentProjectUpload.objects.get_or_create(
    school=school, grade=GRADE, division=DIV, project=proj0, title='Eco Water Filter',
    defaults={'description': 'A low-cost water filter built from recycled materials.',
              'video_link': 'https://youtube.com/watch?v=demo'})
up.students.add(pari)

# ── 6. Scores → Skill Passport reports + Annual Passport ────────────────────
score_by_code = {'SP1.C1': 9, 'SP1.C2': 8, 'SP2.C1': 7, 'SP1.C3': 6, 'SP2.C2': 7}
coach = User.objects.filter(role='THINKING_COACH').first()
for ac in AssessmentCompetency.objects.select_related('competency'):
    sc = score_by_code.get(ac.competency.code, 8)
    ScoreEntry.objects.update_or_create(
        student=pari, assessment_competency=ac,
        defaults={'score': sc, 'entered_by': coach})

made = 0
for project in Project.objects.filter(status='Active'):
    report, err = generate_project_report(pari, project)
    if report:
        made += 1

# ── Summary ─────────────────────────────────────────────────────────────────
from attendance.services import student_attendance_stats, projects_completed
from competencies.models import ProjectReport
from competencies.engine import generate_annual_passport
a = student_attendance_stats(pari)
annual = generate_annual_passport(pari)
print('Pari Joshi seeded. login: pari.joshi / Test@123')
print('  attendance: streak', a['current_streak'], 'weeks | monthly', a['monthly_percent'], '% | badge',
      (a['badge'] or {}).get('name'))
print('  journey:', projects_completed(pari))
print('  skill-passport reports:', ProjectReport.objects.filter(student=pari).count())
print('  annual passport top competencies:', len((annual or {}).get('top_5_competencies', [])),
      '| top profiles:', len((annual or {}).get('top_3_profiles', [])))
print('  announcements (fsl/gr6) visible:',
      Announcement.objects.filter(is_published=True).count(), 'published total')
