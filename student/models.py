from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from schools.models import School


class Student(models.Model):
    """
    Student model for onboarding and managing student information
    """
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]

    STREAM_CHOICES = [
        ('science', 'Science'),
        ('commerce', 'Commerce'),
        ('arts', 'Arts/Humanities'),
        ('na', 'Not Applicable'),
    ]

    SCHOOL_BOARD_CHOICES = [
        ('CBSE', 'CBSE'),
        ('ICSE', 'ICSE'),
        ('SSC', 'SSC (State Board)'),
        ('IB', 'IB (International Baccalaureate)'),
        ('IGCSE', 'IGCSE'),
        ('other', 'Other'),
    ]

    SKILL_LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    LEARNING_STYLE_CHOICES = [
        ('visual', 'Visual'),
        ('auditory', 'Auditory'),
        ('kinesthetic', 'Kinesthetic'),
        ('mixed', 'Mixed'),
    ]

    LANGUAGE_CHOICES = [
        ('english', 'English'),
        ('hindi', 'Hindi'),
        ('marathi', 'Marathi'),
        ('other', 'Other'),
    ]

    ATTENDANCE_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on-leave', 'On Leave'),
    ]

    EMERGENCY_RELATIONSHIP_CHOICES = [
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('guardian', 'Guardian'),
        ('uncle', 'Uncle'),
        ('aunt', 'Aunt'),
        ('grandparent', 'Grandparent'),
        ('sibling', 'Sibling'),
        ('other', 'Other'),
    ]

    # A. Basic Information
    student_photo = models.ImageField(upload_to='students/photos/', blank=True, null=True)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=50, default='Indian')
    mother_tongue = models.CharField(max_length=50, blank=True, null=True)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    aadhar_number = models.CharField(max_length=14, blank=True, null=True)

    # User Account Link
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile')

    # B. School Assignment
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')

    # C. Academic Details
    school_name = models.CharField(max_length=200, blank=True, null=True)
    school_branch = models.CharField(max_length=100, blank=True, null=True)
    student_class = models.CharField(max_length=10)
    division = models.CharField(max_length=10)
    roll_number = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=20)
    # Optional: schools onboard mid-year and often don't have the admission
    # number to hand. Stored as NULL rather than '' when absent, because
    # `unique` would reject a second blank string but allows many NULLs.
    gr_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    previous_school = models.CharField(max_length=200, blank=True, null=True)
    stream = models.CharField(max_length=20, choices=STREAM_CHOICES, blank=True, null=True)
    school_board = models.CharField(max_length=20, choices=SCHOOL_BOARD_CHOICES)

    # C. Contact Details
    student_mobile = models.CharField(max_length=15, blank=True, null=True)
    school_email = models.EmailField(unique=True)
    personal_email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # D. Skill Lab Specific Details
    skill_lab_reg_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    enrollment_date = models.DateField()
    skills_enrolled = models.CharField(max_length=200, blank=True, null=True)
    current_skill_level = models.CharField(max_length=20, choices=SKILL_LEVEL_CHOICES, blank=True, null=True)
    assigned_trainer = models.CharField(max_length=100, blank=True, null=True)
    batch_timing = models.CharField(max_length=100, blank=True, null=True)
    learning_style = models.CharField(max_length=20, choices=LEARNING_STYLE_CHOICES, blank=True, null=True)
    interests_aptitude = models.CharField(max_length=200, blank=True, null=True)
    preferred_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, blank=True, null=True)
    attendance_status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default='active')
    practice_hours = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    certificates_earned = models.TextField(blank=True, null=True)
    badges_earned = models.TextField(blank=True, null=True)

    # E. Health & Safety
    medical_conditions = models.TextField(blank=True, null=True)
    allergies = models.TextField(blank=True, null=True)
    emergency_instructions = models.TextField(blank=True, null=True)
    doctor_name = models.CharField(max_length=100, blank=True, null=True)
    doctor_contact = models.CharField(max_length=15, blank=True, null=True)
    physical_limitations = models.TextField(blank=True, null=True)

    # F. Emergency Contact
    emergency_name = models.CharField(max_length=100)
    emergency_relationship = models.CharField(max_length=20, choices=EMERGENCY_RELATIONSHIP_CHOICES)
    emergency_mobile = models.CharField(max_length=15)
    emergency_alt_mobile = models.CharField(max_length=15, blank=True, null=True)
    emergency_address = models.TextField(blank=True, null=True)

    # G. Family Details (Optional)
    sibling_1_name = models.CharField(max_length=100, blank=True, null=True)
    sibling_1_class_school = models.CharField(max_length=100, blank=True, null=True)
    sibling_1_skill_lab_id = models.CharField(max_length=50, blank=True, null=True)

    sibling_2_name = models.CharField(max_length=100, blank=True, null=True)
    sibling_2_class_school = models.CharField(max_length=100, blank=True, null=True)
    sibling_2_skill_lab_id = models.CharField(max_length=50, blank=True, null=True)

    sibling_3_name = models.CharField(max_length=100, blank=True, null=True)
    sibling_3_class_school = models.CharField(max_length=100, blank=True, null=True)
    sibling_3_skill_lab_id = models.CharField(max_length=50, blank=True, null=True)

    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='students_created')

    class Meta:
        db_table = 'students'
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.gr_number}"

    @property
    def full_name(self):
        """Returns the full name of the student"""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        """Calculate age from date of birth"""
        from datetime import date
        today = date.today()
        if self.date_of_birth:
            age = today.year - self.date_of_birth.year
            if today.month < self.date_of_birth.month or (today.month == self.date_of_birth.month and today.day < self.date_of_birth.day):
                age -= 1
            return age
        return None
