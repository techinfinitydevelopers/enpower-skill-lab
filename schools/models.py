from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone
from django.conf import settings


class School(models.Model):
    """
    Comprehensive School model for Enpower Skill Lab platform.
    Captures all information from the school onboarding form.
    """
    
    # ==================== SCHOOL ADMIN ASSIGNMENT ====================
    school_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_school',
        limit_choices_to={'role': 'SCHOOL_ADMIN'},
        verbose_name="School Admin",
        help_text="Assign a School Admin to manage this school"
    )
    
    # ==================== A. SCHOOL BASIC INFORMATION ====================
    framework_ref = models.ForeignKey(
        'competencies.Framework',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='schools',
        verbose_name="Skill Framework",
        help_text="Select which skill framework this school follows"
    )
    framework_type = models.CharField(max_length=10, default='FSL', blank=True)  # Legacy
    school_name = models.CharField(
        max_length=200,
        verbose_name="School Name",
        help_text="Official name of the school"
    )
    school_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="School Code / UDISE Code",
        help_text="Unique identifier for the school"
    )
    
    BOARD_CHOICES = [
        ('cbse', 'CBSE'),
        ('icse', 'ICSE'),
        ('ib', 'IB'),
        ('state', 'State Board'),
        ('igcse', 'IGCSE'),
    ]
    board = models.CharField(
        max_length=20,
        choices=BOARD_CHOICES,
        verbose_name="School Board"
    )
    
    SCHOOL_TYPE_CHOICES = [
        ('private', 'Private'),
        ('government', 'Government'),
        ('trust', 'Trust'),
        ('aided', 'Aided'),
    ]
    school_type = models.CharField(
        max_length=20,
        choices=SCHOOL_TYPE_CHOICES,
        verbose_name="Type of School"
    )
    
    MEDIUM_CHOICES = [
        ('english', 'English'),
        ('hindi', 'Hindi'),
        ('marathi', 'Marathi'),
        ('regional', 'Regional Language'),
        ('bilingual', 'Bilingual'),
    ]
    medium = models.CharField(
        max_length=20,
        choices=MEDIUM_CHOICES,
        verbose_name="Medium of Instruction"
    )
    
    year_established = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1800), MaxValueValidator(2025)],
        verbose_name="Year of Establishment"
    )
    
    school_logo = models.ImageField(
        upload_to='school_logos/',
        null=True,
        blank=True,
        verbose_name="School Logo"
    )
    
    school_email = models.EmailField(
        verbose_name="School Email ID",
        help_text="Primary email for school communication"
    )
    
    phone_regex = RegexValidator(
        regex=r'^\d{10}$',
        message="Phone number must be 10 digits"
    )
    school_phone = models.CharField(
        max_length=10,
        validators=[phone_regex],
        verbose_name="School Contact Number"
    )
    
    website = models.URLField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Website URL"
    )
    
    principal_name = models.CharField(
        max_length=100,
        verbose_name="Admin / Principal Name"
    )
    principal_phone = models.CharField(
        max_length=10,
        validators=[phone_regex],
        verbose_name="Principal Contact Number"
    )
    principal_email = models.EmailField(
        verbose_name="Principal Email ID"
    )
    
    # ==================== B. SCHOOL BRANCH DETAILS ====================
    branch_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Branch Name",
        help_text="For schools with multiple units"
    )
    branch_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Branch Code"
    )
    branch_address = models.TextField(
        verbose_name="Branch Address"
    )
    city = models.CharField(
        max_length=100,
        verbose_name="City"
    )
    state = models.CharField(
        max_length=100,
        verbose_name="State"
    )
    pincode = models.CharField(
        max_length=6,
        validators=[RegexValidator(regex=r'^\d{6}$', message="Pincode must be 6 digits")],
        verbose_name="Pincode"
    )
    num_students = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Number of Students"
    )
    num_teachers = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Number of Teachers"
    )
    num_trainers = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Number of Skill Lab Trainers"
    )
    grades_available = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Grades Available",
        help_text="e.g., Pre-K to 12"
    )
    
    SHIFT_CHOICES = [
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('both', 'Both'),
    ]
    shift_details = models.CharField(
        max_length=20,
        choices=SHIFT_CHOICES,
        null=True,
        blank=True,
        verbose_name="Shift Details"
    )
    
    branch_coordinator_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Branch Coordinator Name"
    )
    branch_coordinator_phone = models.CharField(
        max_length=10,
        validators=[phone_regex],
        null=True,
        blank=True,
        verbose_name="Branch Coordinator Contact"
    )
    
    # ==================== C. INFRASTRUCTURE & FACILITY INFORMATION ====================
    CSL_AVAILABILITY_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
    ]
    csl_availability = models.CharField(
        max_length=10,
        choices=CSL_AVAILABILITY_CHOICES,
        null=True,
        blank=True,
        verbose_name="Composite Skill Lab Availability"
    )
    csl_rooms_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="CSL Rooms Count"
    )
    equipment_inventory = models.TextField(
        null=True,
        blank=True,
        verbose_name="Equipment Inventory",
        help_text="List major equipment"
    )
    computer_lab_details = models.TextField(
        null=True,
        blank=True,
        verbose_name="Computer Lab Details"
    )
    internet_details = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Internet Availability & Speed"
    )
    classroom_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Classroom Count"
    )
    sports_facilities = models.TextField(
        null=True,
        blank=True,
        verbose_name="Sports Facilities"
    )
    safety_measures = models.TextField(
        null=True,
        blank=True,
        verbose_name="Safety & Security Measures"
    )
    
    CCTV_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('partial', 'Partial'),
    ]
    cctv_coverage = models.CharField(
        max_length=20,
        choices=CCTV_CHOICES,
        null=True,
        blank=True,
        verbose_name="CCTV Coverage"
    )
    
    FIRE_SAFETY_CHOICES = [
        ('compliant', 'Compliant'),
        ('non-compliant', 'Non-Compliant'),
        ('pending', 'Pending'),
    ]
    fire_safety_status = models.CharField(
        max_length=20,
        choices=FIRE_SAFETY_CHOICES,
        null=True,
        blank=True,
        verbose_name="Fire Safety Status"
    )
    
    first_aid_availability = models.CharField(
        max_length=10,
        choices=CSL_AVAILABILITY_CHOICES,
        null=True,
        blank=True,
        verbose_name="First Aid Availability"
    )
    
    # ==================== D. ACADEMIC INFORMATION ====================
    total_students = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Total Students Enrolled"
    )
    class_wise_strength = models.TextField(
        null=True,
        blank=True,
        verbose_name="Class-wise Strength",
        help_text="e.g., Class 1: 60, Class 2: 55"
    )
    student_teacher_ratio = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Student-Teacher Ratio",
        help_text="e.g., 30:1"
    )
    curriculum_followed = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Curriculum Followed"
    )
    club_details = models.TextField(
        null=True,
        blank=True,
        verbose_name="Club/Activity Details"
    )
    skill_subjects = models.TextField(
        null=True,
        blank=True,
        verbose_name="Skill Subjects Offered (9th–12th)"
    )
    remedial_programs = models.TextField(
        null=True,
        blank=True,
        verbose_name="Remedial Programs Available"
    )
    
    # ==================== E. SKILL PROGRAM INFORMATION ====================
    SKILL_PROGRAM_CHOICES = [
        ('fsl', 'Future Skills Lab'),
        ('csl_plus_pc', 'CSL Plus with PC'),
        ('csl_plus_tc', 'CSL Plus with TC'),
        ('csl_foundation_pc', 'CSL Foundation with PC'),
        ('csl_foundation', 'CSL Foundation'),
    ]
    skill_program = models.CharField(
        max_length=20,
        choices=SKILL_PROGRAM_CHOICES,
        null=True,
        blank=True,
        verbose_name="Skill Program (ESL Product)",
        help_text="Select the ESL product assigned to this school"
    )
    program_academic_year = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Program Academic Year",
        help_text="e.g. 2026-27"
    )
    srm = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='srm_schools',
        limit_choices_to={'role': 'PROGRAM_COORDINATOR'},
        verbose_name="School Relationship Manager (SRM)",
        help_text="Assign a Program Coordinator as SRM"
    )
    trainer_assigned = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trainer_schools',
        limit_choices_to={'role': 'THINKING_COACH'},
        verbose_name="Trainer Assigned",
        help_text="Assign a Thinking Coach as trainer"
    )
    grade_wise_students = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Grade-wise Number of Students",
        help_text="JSON: {\"1\": 60, \"2\": 55, ...}"
    )

    # ==================== E-LEGACY. SKILL LAB INTEGRATION (kept for backward compat) ====================
    skill_lab_reg_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Skill Lab Registration ID"
    )
    skills_offered = models.TextField(
        null=True,
        blank=True,
        verbose_name="Skills Offered (List)"
    )
    batch_timings = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Batch Timings"
    )
    trainers_assigned = models.TextField(
        null=True,
        blank=True,
        verbose_name="Trainers Assigned"
    )
    lab_usage_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Lab Usage Hours / Week"
    )
    student_groups_linked = models.TextField(
        null=True,
        blank=True,
        verbose_name="Student Groups Linked"
    )

    CSL_INTEGRATION_CHOICES = [
        ('integrated', 'Integrated'),
        ('pending', 'Pending'),
        ('not-applicable', 'Not Applicable'),
    ]
    csl_integration_status = models.CharField(
        max_length=20,
        choices=CSL_INTEGRATION_CHOICES,
        null=True,
        blank=True,
        verbose_name="CSL or Kaushal Bodh Integration Status"
    )
    csl_project_list = models.TextField(
        null=True,
        blank=True,
        verbose_name="CSL Project List Selected"
    )

    assessment_system_linked = models.CharField(
        max_length=10,
        choices=CSL_AVAILABILITY_CHOICES,
        null=True,
        blank=True,
        verbose_name="Assessment & Reporting System Linked"
    )
    
    # ==================== F. FEES & COMMERCIAL INFORMATION ====================
    lab_fees_with_gst = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Lab Fees (with GST)",
        help_text="Total lab fees including GST"
    )
    program_fees_with_gst = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Program Fees (with GST)",
        help_text="Total program fees including GST"
    )

    PAYMENT_TERMS_CHOICES = [
        ('quarterly', 'Quarterly'),
        ('half_yearly', 'Half Yearly'),
        ('annual', 'Annual'),
    ]
    payment_terms = models.CharField(
        max_length=20,
        choices=PAYMENT_TERMS_CHOICES,
        null=True,
        blank=True,
        verbose_name="Payment Terms"
    )

    tce_sales_spoc_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="TCE Sales SPOC Name"
    )
    tce_sales_spoc_contact = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        verbose_name="TCE Sales SPOC Contact"
    )
    signed_agreement = models.FileField(
        upload_to='school_agreements/',
        null=True,
        blank=True,
        verbose_name="Signed TCE School Agreement"
    )
    go_live_certificate = models.FileField(
        upload_to='go_live_certs/',
        null=True,
        blank=True,
        verbose_name="Go-Live Certificate"
    )

    # ==================== F-LEGACY. ADMINISTRATIVE INFORMATION (kept for existing data) ====================
    billing_email = models.EmailField(
        null=True,
        blank=True,
        verbose_name="Billing Email"
    )
    gst_number = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        validators=[RegexValidator(
            regex=r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
            message="Invalid GST number format"
        )],
        verbose_name="GST Number"
    )

    PAYMENT_CHOICES = [
        ('bank-transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('upi', 'UPI'),
    ]
    payment_preferences = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        null=True,
        blank=True,
        verbose_name="Payment Preferences"
    )

    finance_contact = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Point of Contact for Finance"
    )
    admin_coordinator_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Administrative Coordinator Name"
    )
    admin_coordinator_phone = models.CharField(
        max_length=10,
        validators=[phone_regex],
        null=True,
        blank=True,
        verbose_name="Administrative Coordinator Phone"
    )
    academic_year_cycle = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Academic Year Cycle",
        help_text="e.g., April - March"
    )

    WORKSHOP_APPROVAL_CHOICES = [
        ('approved', 'Approved'),
        ('pending', 'Pending'),
        ('not-required', 'Not Required'),
    ]
    workshop_approval_status = models.CharField(
        max_length=20,
        choices=WORKSHOP_APPROVAL_CHOICES,
        null=True,
        blank=True,
        verbose_name="Approval Status for Workshops & Trainings"
    )

    digital_reports_consent = models.CharField(
        max_length=10,
        choices=CSL_AVAILABILITY_CHOICES,
        null=True,
        blank=True,
        verbose_name="Consent for Digital Reports"
    )
    
    # ==================== G. COMPLIANCE & DOCUMENTATION ====================
    affiliation_letter = models.FileField(
        upload_to='compliance_docs/affiliation/',
        null=True,
        blank=True,
        verbose_name="CBSE / Board Affiliation Letter"
    )
    fire_safety_cert = models.FileField(
        upload_to='compliance_docs/fire_safety/',
        null=True,
        blank=True,
        verbose_name="Fire Safety Certificate"
    )
    registration_cert = models.FileField(
        upload_to='compliance_docs/registration/',
        null=True,
        blank=True,
        verbose_name="School Registration Certificate"
    )
    trust_registration = models.FileField(
        upload_to='compliance_docs/trust/',
        null=True,
        blank=True,
        verbose_name="Trust Registration"
    )
    
    lab_safety_compliance = models.CharField(
        max_length=20,
        choices=FIRE_SAFETY_CHOICES,
        null=True,
        blank=True,
        verbose_name="Lab Safety Compliance"
    )
    
    VERIFICATION_CHOICES = [
        ('verified', 'All Verified'),
        ('partial', 'Partially Verified'),
        ('pending', 'Pending'),
    ]
    teacher_police_verification = models.CharField(
        max_length=20,
        choices=VERIFICATION_CHOICES,
        null=True,
        blank=True,
        verbose_name="Teacher Police Verification Status"
    )
    
    child_safety_policy = models.FileField(
        upload_to='compliance_docs/child_safety/',
        null=True,
        blank=True,
        verbose_name="Child Safety Policy (POSH / POCSO)"
    )
    insurance_docs = models.FileField(
        upload_to='compliance_docs/insurance/',
        null=True,
        blank=True,
        verbose_name="Insurance Documents"
    )
    
    # ==================== H. EMERGENCY INFORMATION ====================
    emergency_contact_person = models.CharField(
        max_length=100,
        verbose_name="Emergency Contact Person"
    )
    emergency_phone = models.CharField(
        max_length=10,
        validators=[phone_regex],
        verbose_name="Emergency Phone Number"
    )
    nearest_hospital = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Nearest Hospital Name"
    )
    
    EVACUATION_CHOICES = [
        ('documented', 'Documented'),
        ('in-progress', 'In Progress'),
        ('not-available', 'Not Available'),
    ]
    evacuation_plan = models.CharField(
        max_length=20,
        choices=EVACUATION_CHOICES,
        null=True,
        blank=True,
        verbose_name="Safety Protocols & Evacuation Plan"
    )
    
    # ==================== I. ADDITIONAL DATA ====================
    exceptions_for_school = models.TextField(
        null=True,
        blank=True,
        verbose_name="Exceptions for this School",
        help_text="Any special exceptions or notes for this school"
    )
    events_workshop_calendar = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Events & Workshop Calendar",
        help_text="List of events: [{\"date\": \"2026-08-15\", \"event\": \"Independence Day\"}, ...]"
    )
    notable_alumni = models.TextField(
        null=True,
        blank=True,
        verbose_name="Notable Alumni"
    )

    # I-LEGACY (kept for existing data)
    awards = models.TextField(
        null=True,
        blank=True,
        verbose_name="Awards & Recognitions"
    )
    performance_trends = models.TextField(
        null=True,
        blank=True,
        verbose_name="School Performance Trends"
    )
    social_media_links = models.TextField(
        null=True,
        blank=True,
        verbose_name="Social Media Links"
    )
    events_calendar = models.TextField(
        null=True,
        blank=True,
        verbose_name="Events & Workshops Calendar (Legacy)"
    )
    
    # ==================== SYSTEM FIELDS ====================
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active Status"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )
    onboarding_completed = models.BooleanField(
        default=False,
        verbose_name="Onboarding Completed"
    )
    
    class Meta:
        verbose_name = "School"
        verbose_name_plural = "Schools"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school_code']),
            models.Index(fields=['school_name']),
            models.Index(fields=['city', 'state']),
        ]
    
    def __str__(self):
        return f"{self.school_name} ({self.school_code})"
    
    def get_full_address(self):
        """Returns the complete address of the school"""
        return f"{self.branch_address}, {self.city}, {self.state} - {self.pincode}"
    
    def get_contact_info(self):
        """Returns primary contact information"""
        return {
            'email': self.school_email,
            'phone': self.school_phone,
            'principal': self.principal_name,
            'principal_email': self.principal_email,
        }


class Class(models.Model):
    """
    Class model for managing class divisions within schools.
    Each class is linked to a school and can have an assigned coach.
    """
    
    GRADE_CHOICES = [
        ('1', 'Standard 1'),
        ('2', 'Standard 2'),
        ('3', 'Standard 3'),
        ('4', 'Standard 4'),
        ('5', 'Standard 5'),
        ('6', 'Standard 6'),
        ('7', 'Standard 7'),
        ('8', 'Standard 8'),
        ('9', 'Standard 9'),
        ('10', 'Standard 10'),
        ('11', 'Standard 11'),
        ('12', 'Standard 12'),
    ]
    
    ACADEMIC_YEAR_CHOICES = [
        ('2023-2024', '2023-2024'),
        ('2024-2025', '2024-2025'),
        ('2025-2026', '2025-2026'),
        ('2026-2027', '2026-2027'),
    ]
    
    # ==================== SCHOOL RELATIONSHIP ====================
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='classes',
        verbose_name="School",
        help_text="School this class belongs to"
    )
    
    # ==================== CLASS DETAILS ====================
    grade = models.CharField(
        max_length=2,
        choices=GRADE_CHOICES,
        verbose_name="Grade / Standard",
        help_text="Grade level of the class"
    )
    
    division = models.CharField(
        max_length=5,
        verbose_name="Division",
        help_text="Division/Section of the class (e.g., A, B, C)"
    )
    
    class_name = models.CharField(
        max_length=50,
        verbose_name="Class Name",
        help_text="Auto-generated class name (e.g., Std 9A)"
    )
    
    class_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Class Code",
        help_text="Unique identifier for this class"
    )
    
    academic_year = models.CharField(
        max_length=9,
        choices=ACADEMIC_YEAR_CHOICES,
        default='2024-2025',
        verbose_name="Academic Year",
        help_text="Academic year for this class"
    )
    
    # ==================== COACH ASSIGNMENT ====================
    thinking_coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_classes',
        limit_choices_to={'role': 'TEACHER'},
        verbose_name="Thinking Coach",
        help_text="Assigned thinking coach for this class"
    )
    
    # ==================== PROGRAM CONFIGURATION ====================
    total_sessions = models.PositiveIntegerField(
        default=48,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="Total Sessions",
        help_text="Total number of sessions for this class"
    )
    
    # ==================== STATUS & VISIBILITY ====================
    is_active = models.BooleanField(
        default=True,
        verbose_name="Class Status",
        help_text="Whether this class is active"
    )
    
    student_visibility = models.BooleanField(
        default=True,
        verbose_name="Student Visibility",
        help_text="Show this class to assigned students"
    )
    
    parent_visibility = models.BooleanField(
        default=False,
        verbose_name="Parent Visibility",
        help_text="Show this class to connected parents"
    )
    
    # ==================== TRACKING & METADATA ====================
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_classes',
        verbose_name="Created By"
    )
    
    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        ordering = ['school', 'grade', 'division']
        unique_together = ['school', 'grade', 'division', 'academic_year']
        indexes = [
            models.Index(fields=['class_code']),
            models.Index(fields=['school', 'academic_year']),
        ]
    
    def __str__(self):
        return f"{self.class_name} - {self.school.school_name} ({self.academic_year})"
    
    def save(self, *args, **kwargs):
        # Auto-generate class name if not provided
        if not self.class_name:
            self.class_name = f"Std {self.grade}{self.division.upper()}"
        
        # Auto-generate class code if not provided
        if not self.class_code:
            import random
            year = self.academic_year.split('-')[0]
            random_id = random.randint(100, 999)
            self.class_code = f"CLS-{year}-{self.grade}{self.division.upper()}-{random_id:03d}"
        
        super().save(*args, **kwargs)
    
    @property
    def student_count(self):
        """Returns the number of students in this class"""
        return self.students.count() if hasattr(self, 'students') else 0
    
    def get_grade_display_short(self):
        """Returns short grade display (e.g., 'Grade 9')"""
        return f"Grade {self.grade}"
