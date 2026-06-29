exec(r'''
# ============================================================
# seed_rich.py — richer idempotent demo data for Shiv Vani PS
# Run: venv\Scripts\python manage.py shell < seed_rich.py
# Wrapped in exec(...) because manage.py shell reads line-by-line.
# Safe to re-run: uses get_or_create / filter().first() on natural keys.
# ============================================================
from datetime import date, time, timedelta

from accounts.models import User
from schools.models import School, Class
from student.models import Student
from attendance.models import (
    Timetable, TimetableSlot, AttendanceSession, AttendanceRecord,
    DailySessionFeedback, StudentProjectUpload,
)
from competencies.models import Project

AY = "2025-2026"
PROGRAM = "FSL"
ENROLL = date(2025, 4, 1)
TT_START = date(2026, 6, 1)
TT_END = date(2026, 7, 31)
SESSION_CUTOFF = date(2026, 6, 26)

summary = {"students": 0, "users": 0, "classes": 0, "timetables": 0,
           "slots": 0, "sessions": 0, "records": 0, "feedbacks": 0, "uploads": 0}
notes = []

school = School.objects.filter(school_code="SV001").first()
if not school:
    raise SystemExit("Base school SV001 not found -- run base seed first.")

teacher = User.objects.filter(username="teacher1").first()
coordinator = User.objects.filter(username="coordinator1").first()
bio = Project.objects.filter(title="Bio Conservation").first()
if not (teacher and coordinator):
    raise SystemExit("teacher1/coordinator1 users missing -- run base seed first.")

FIRST_NAMES = ["Aarav", "Diya", "Vivaan", "Ananya", "Aditya", "Isha",
               "Kabir", "Myra", "Reyansh", "Saanvi", "Arjun", "Tara"]
DOB_YEARS = [2014, 2015, 2016]

# ------------------------------------------------------------
# Helper: create one student (+ user) idempotently by gr_number/email
# ------------------------------------------------------------
def make_student(grade, div, n):
    gr_number = "SV-G{}{}-{}".format(grade, div, n)
    email = "stu.{}{}.{}@shivvani.test".format(grade, div, n)
    reg_id = "SKL-{}{}-{}".format(grade, div, n)

    # User account (username == school_email)
    user, u_created = User.objects.get_or_create(
        username=email,
        defaults={"email": email, "role": "STUDENT", "first_name": FIRST_NAMES[(n - 1) % len(FIRST_NAMES)]},
    )
    if u_created:
        user.set_password("Test@123")
        user.save()
        summary["users"] += 1

    fname = FIRST_NAMES[(n - 1) % len(FIRST_NAMES)]
    student, s_created = Student.objects.get_or_create(
        gr_number=gr_number,
        defaults=dict(
            first_name=fname,
            last_name="G{}{}".format(grade, div),
            gender="male" if n % 2 else "female",
            date_of_birth=date(DOB_YEARS[n % len(DOB_YEARS)], ((n * 2) % 12) + 1, ((n * 3) % 27) + 1),
            nationality="Indian",
            user=user,
            school=school,
            school_name=school.school_name,
            student_class=str(grade),
            division=div,
            roll_number=str(n),
            academic_year=AY,
            school_board="CBSE",
            school_email=email,
            skill_lab_reg_id=reg_id,
            enrollment_date=ENROLL,
            emergency_name="Guardian of " + fname,
            emergency_relationship="father" if n % 2 else "mother",
            emergency_mobile="9{:09d}".format(100000000 + int(grade) * 1000 + n),
            is_active=True,
            created_by=coordinator,
        ),
    )
    if s_created:
        summary["students"] += 1
    elif student.user_id is None:
        # backfill user link if a prior run created student without it
        student.user = user
        student.save(update_fields=["user"])
    return student


# ------------------------------------------------------------
# 1. STUDENTS — 6A (top up to 8), 6B (8), 7A (8)
# ------------------------------------------------------------
class_specs = [
    ("6", "A", 5, 8),   # already 4 (roll 1-4); add roll 5-8
    ("6", "B", 1, 8),
    ("7", "A", 1, 8),
]
class_students = {}
for grade, div, start_n, end_n in class_specs:
    students = []
    # collect ALL students for this class (existing + new) for attendance later
    for n in range(start_n, end_n + 1):
        students.append(make_student(grade, div, n))
    all_in_class = list(
        Student.objects.filter(school=school, student_class=str(grade), division=div).order_by("roll_number")
    )
    class_students[(grade, div)] = all_in_class

# ------------------------------------------------------------
# 2. schools.Class rows for 6B and 7A (6A already exists)
# ------------------------------------------------------------
for grade, div in [("6", "B"), ("7", "A")]:
    cls, created = Class.objects.get_or_create(
        school=school, grade=grade, division=div, academic_year=AY,
        defaults={"thinking_coach": teacher, "created_by": coordinator},
    )
    if created:
        summary["classes"] += 1
    elif cls.thinking_coach_id is None:
        cls.thinking_coach = teacher
        cls.save(update_fields=["thinking_coach"])

# ------------------------------------------------------------
# 3. TIMETABLES (classrooms) for 6B and 7A + slots
#    Use filter().first() to avoid MultipleObjectsReturned.
# ------------------------------------------------------------
SLOT_DEFS = [
    ("tue", 1, time(10, 0), time(11, 0)),
    ("thu", 2, time(11, 0), time(12, 0)),
]
timetables = {}
for grade, div in [("6", "B"), ("7", "A")]:
    tt = Timetable.objects.filter(school=school, grade=grade, division=div, academic_year=AY).first()
    if tt is None:
        tt = Timetable.objects.create(
            school=school, grade=grade, division=div, academic_year=AY,
            thinking_coach=teacher, program=PROGRAM,
            start_date=TT_START, end_date=TT_END,
            created_by=coordinator, is_active=True,
        )
        summary["timetables"] += 1
    else:
        # ensure fields populated for dropdown + session generation
        tt.thinking_coach = teacher
        tt.program = PROGRAM
        tt.start_date = TT_START
        tt.end_date = TT_END
        tt.is_active = True
        tt.created_by = tt.created_by or coordinator
        tt.save()
    timetables[(grade, div)] = tt

    for day, period, st, et in SLOT_DEFS:
        slot, s_created = TimetableSlot.objects.get_or_create(
            timetable=tt, day_of_week=day, period_number=period,
            defaults={"start_time": st, "end_time": et, "project": bio},
        )
        if s_created:
            summary["slots"] += 1

# ------------------------------------------------------------
# 4. ATTENDANCE for 6B and 7A
#    Idempotent: delete existing sessions for the class first, then rebuild.
# ------------------------------------------------------------
SLOT_WEEKDAYS = {"tue": 1, "thu": 3}  # Python weekday(): Mon=0
SLOT_TIMES = {"tue": time(10, 0), "thu": time(11, 0)}

for (grade, div), tt in timetables.items():
    students = class_students[(grade, div)]
    # idempotent reset
    AttendanceSession.objects.filter(
        school=school, grade=grade, division=div, academic_year=AY
    ).delete()

    # one "frequent absentee" student per class for variation
    absentee = students[0] if students else None
    absent_dates = set()

    cur = TT_START
    session_no = 0
    while cur <= SESSION_CUTOFF:
        for day, wd in SLOT_WEEKDAYS.items():
            if cur.weekday() != wd:
                continue
            session_no += 1
            sess = AttendanceSession.objects.create(
                school=school, grade=grade, division=div, academic_year=AY,
                date=cur, start_time=SLOT_TIMES[day], timetable=tt,
                class_status="held", thinking_coach=teacher,
                project=bio, session_number=session_no,
            )
            summary["sessions"] += 1
            for stu in students:
                status = "present"
                # make the absentee miss a few (every 3rd of their sessions)
                if absentee and stu.id == absentee.id and (session_no % 3 == 0):
                    status = "absent"
                    absent_dates.add(cur)
                AttendanceRecord.objects.create(session=sess, student=stu, status=status)
                summary["records"] += 1
        cur += timedelta(days=1)

# ------------------------------------------------------------
# 5. DailySessionFeedback + StudentProjectUpload per new class
# ------------------------------------------------------------
for idx, (grade, div) in enumerate([("6", "B"), ("7", "A")]):
    students = class_students[(grade, div)]
    fb, fb_created = DailySessionFeedback.objects.get_or_create(
        school=school, grade=grade, division=div, academic_year=AY,
        date=date(2026, 6, 2), session_number=1,
        defaults=dict(
            project=bio, session_title="Intro to Bio Conservation",
            session_description="Kickoff session for the conservation project.",
            thinking_coach=teacher,
            rating_engagement=4, rating_delivery_ease=4,
            rating_resources=3, rating_time_management=4,
            is_project_completed=(idx == 0),  # first class marks project completed
        ),
    )
    if fb_created:
        summary["feedbacks"] += 1

    upload, up_created = StudentProjectUpload.objects.get_or_create(
        school=school, grade=grade, division=div, academic_year=AY,
        title="Bio Conservation Showcase G{}{}".format(grade, div),
        defaults=dict(
            project=bio,
            description="Student project artifacts for Bio Conservation.",
            video_link="https://example.test/g{}{}-bio".format(grade, div),
            created_by=teacher,
        ),
    )
    if up_created:
        summary["uploads"] += 1
    if students:
        upload.students.set(students)

# ------------------------------------------------------------
# REPORT
# ------------------------------------------------------------
print("\\n=== SEED_RICH SUMMARY (created this run) ===")
for k, v in summary.items():
    print("  {:12s}: {}".format(k, v))
print("Note: new student logins use the school_email as username, password Test@123")
''')
