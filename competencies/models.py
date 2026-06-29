from django.conf import settings
from django.db import models


class Framework(models.Model):
    """Skill framework — each school follows one framework."""
    name      = models.CharField(max_length=100, unique=True)  # e.g. "FSL", "CSL+"
    prefix    = models.CharField(max_length=20, unique=True)   # e.g. "SP", "CSL-SP", "ABC-SP"
    is_fixed  = models.BooleanField(default=False, help_text='Fixed frameworks have read-only pillars (e.g. FSL)')
    order     = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


STAGE_CHOICES = [
    ('Foundational', 'Foundational — Class 1–2'),
    ('Preparatory',  'Preparatory — Class 3–5'),
    ('Middle',       'Middle — Class 6–8'),
    ('Secondary',    'Secondary — Class 9–12'),
]

STATUS_CHOICES = [
    ('Active', 'Active'),
    ('Draft',  'Draft'),
]

PILLAR_COLOR_CHOICES = [
    ('teal',   'Teal'),
    ('purple', 'Purple'),
    ('blue',   'Blue'),
    ('orange', 'Orange'),
    ('green',  'Green'),
    ('red',    'Red'),
    ('pink',   'Pink'),
    ('indigo', 'Indigo'),
    ('amber',  'Amber'),
]


class Pillar(models.Model):
    """Learning pillars — each belongs to a Framework."""
    name      = models.CharField(max_length=100)
    number    = models.CharField(max_length=10)
    color     = models.CharField(max_length=20, choices=PILLAR_COLOR_CHOICES)
    order     = models.PositiveSmallIntegerField(default=0)
    framework_ref = models.ForeignKey(Framework, on_delete=models.SET_NULL, related_name='pillars', null=True, blank=True)
    framework = models.CharField(max_length=10, default='FSL', blank=True)  # Legacy CharField — views use framework_ref
    is_kb     = models.BooleanField(
        default=False,
        help_text='Kaushal Bodh pillar — scores only, excluded from passport/profiling calculations'
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.number}. {self.name}"


class SubPillar(models.Model):
    """17 sub-pillars (SP1–SP17), each under a Pillar."""
    pillar    = models.ForeignKey(Pillar, on_delete=models.CASCADE, related_name='sub_pillars')
    sp_number = models.PositiveSmallIntegerField(unique=True)   # 1–17
    name      = models.CharField(max_length=150)

    class Meta:
        ordering = ['sp_number']

    def __str__(self):
        return f"{self.code}: {self.name}"

    @property
    def code(self):
        if self.pillar.is_kb:
            kb_sps = list(SubPillar.objects.filter(pillar=self.pillar).order_by('sp_number').values_list('id', flat=True))
            idx = kb_sps.index(self.id) + 1 if self.id in kb_sps else self.sp_number
            return f"KB{idx}"
        fw = self.pillar.framework_ref
        if fw and not fw.is_fixed:
            fw_sps = list(SubPillar.objects.filter(pillar__framework_ref=fw).order_by('sp_number').values_list('id', flat=True))
            idx = fw_sps.index(self.id) + 1 if self.id in fw_sps else self.sp_number
            prefix = fw.prefix
            # Ensure prefix ends with separator before number
            if not prefix.endswith('-') and not prefix.endswith('SP'):
                prefix = f"{prefix}-SP"
            return f"{prefix}{idx}"
        return f"SP{self.sp_number}"


class Competency(models.Model):
    """Individual competency under a SubPillar."""
    sub_pillar  = models.ForeignKey(SubPillar, on_delete=models.CASCADE, related_name='competencies')
    code        = models.CharField(max_length=20, unique=True)   # e.g. SP1.C3
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    stage       = models.CharField(max_length=20, choices=STAGE_CHOICES)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sub_pillar__sp_number', 'code']
        verbose_name_plural = 'Competencies'

    def __str__(self):
        return f"{self.code} — {self.name}"


class Profile(models.Model):
    """15 student skill profiles of the neoRiSE Skill Passport."""
    number = models.PositiveSmallIntegerField(unique=True)   # 1–15
    name   = models.CharField(max_length=100)
    primary_competencies   = models.ManyToManyField(
        Competency, related_name='primary_profiles',   blank=True)
    secondary_competencies = models.ManyToManyField(
        Competency, related_name='secondary_profiles', blank=True)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f"{self.number}. {self.name}"


PROJECT_TYPE_CHOICES = [
    ('Life Form',          'Life Form'),
    ('Machines & Materials', 'Machines & Materials'),
    ('Human Services',     'Human Services'),
    ('Plug In',            'Plug In'),
    ('Final Project',      'Final Project'),
]

ASSESSMENT_TYPE_CHOICES = [
    ('Written Assignment', 'Written Assignment'),
    ('Presentation',       'Presentation'),
    ('Peer Review',        'Peer Review'),
    ('Lab Report',         'Lab Report'),
]


class Project(models.Model):
    title           = models.CharField(max_length=200)
    project_type    = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES, default='Capstone')
    grade           = models.CharField(max_length=20, choices=STAGE_CHOICES)
    framework_ref   = models.ForeignKey(Framework, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    framework       = models.CharField(max_length=10, default='FSL', blank=True)  # Legacy
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Draft')
    sequence_number = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Order of this project in the year (1, 2, 3, 4). Used for Annual Passport — latest score wins.'
    )
    linked_project  = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='plugins',
        help_text='Only for Plug-In type: select the Project this Plug-In belongs to'
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Assessment(models.Model):
    project                  = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assessments')
    name                     = models.CharField(max_length=200)
    assessment_type          = models.CharField(max_length=30, choices=ASSESSMENT_TYPE_CHOICES, default='Written Assignment')
    placement_after_challenge = models.PositiveSmallIntegerField(blank=True, null=True, help_text='After Challenge #')
    output_descriptor        = models.TextField(blank=True)
    additional_instructions  = models.TextField(blank=True, help_text='Additional instructions for the teacher')
    rubric_file              = models.FileField(upload_to='rubrics/', blank=True, null=True)
    order                    = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.project.title} — {self.name}"


class AssessmentCompetency(models.Model):
    COMP_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('group',      'Group'),
    ]
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='competency_mappings')
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE, related_name='assessment_mappings')
    comp_type  = models.CharField(max_length=10, choices=COMP_TYPE_CHOICES, default='individual')
    order      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('assessment', 'competency')]


class StudentAssessmentFeedback(models.Model):
    student    = models.ForeignKey('student.Student', on_delete=models.CASCADE, related_name='assessment_feedbacks')
    assessment = models.ForeignKey('Assessment', on_delete=models.CASCADE, related_name='student_feedbacks')
    feedback   = models.TextField(blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('student', 'assessment')]

    def __str__(self):
        return f"{self.student} — {self.assessment} — feedback"


class StudentProjectFeedback(models.Model):
    student    = models.ForeignKey('student.Student', on_delete=models.CASCADE, related_name='project_feedbacks')
    project    = models.ForeignKey('Project', on_delete=models.CASCADE, related_name='student_feedbacks')
    feedback   = models.TextField(blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('student', 'project')]

    def __str__(self):
        return f"{self.student} — {self.project} — overall feedback"


class ScoreEntry(models.Model):
    student               = models.ForeignKey('student.Student', on_delete=models.CASCADE, related_name='score_entries')
    assessment_competency = models.ForeignKey(AssessmentCompetency, on_delete=models.CASCADE, related_name='scores')
    score                 = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Score 1–10')
    entered_by            = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('student', 'assessment_competency')]

    def __str__(self):
        return f"{self.student} — {self.assessment_competency} — {self.score}"


class ProjectReport(models.Model):
    student               = models.ForeignKey('student.Student', on_delete=models.CASCADE, related_name='project_reports')
    project               = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='reports')
    top_3_profiles        = models.JSONField(default=list)
    top_5_competencies    = models.JSONField(default=list)
    skills_to_work_on     = models.JSONField(default=list)
    all_competency_scores = models.JSONField(default=dict)
    generated_at          = models.DateTimeField(auto_now=True)
    is_outdated           = models.BooleanField(default=False)

    class Meta:
        unique_together = [('student', 'project')]

    def __str__(self):
        return f"{self.student} — {self.project} — Report"


# ==================== ESL PRODUCT (Program) ====================

class ESLProduct(models.Model):
    """ESL Product / Program — e.g. Future Skills Lab, CSL Plus, CSL Foundation."""
    name = models.CharField(max_length=200, verbose_name="Program Title")
    description = models.TextField(blank=True, verbose_name="Description of the Program")
    competencies_description = models.TextField(blank=True, verbose_name="Competencies", help_text="Competencies applicable at program level")
    applicable_grades = models.JSONField(default=list, blank=True, verbose_name="Grades Applicable", help_text='e.g. [1,2,6,7,8]')
    applicable_boards = models.JSONField(default=list, blank=True, verbose_name="Boards Applicable", help_text='e.g. ["CBSE","ICSE"]')
    program_document = models.FileField(upload_to='esl_products/', null=True, blank=True, verbose_name="Program Document (SKU/Concept Note/Brochure)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "ESL Product"
        verbose_name_plural = "ESL Products"

    def __str__(self):
        return self.name


class ProductProject(models.Model):
    """Project under an ESL Product — multiple projects per grade."""
    esl_product = models.ForeignKey(ESLProduct, on_delete=models.CASCADE, related_name='projects')
    project_number = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=200, verbose_name="Project Name")
    description = models.TextField(blank=True, verbose_name="Project Description")
    grade = models.CharField(max_length=5, blank=True, verbose_name="Grade")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['esl_product', 'grade', 'project_number']

    def __str__(self):
        return f"{self.esl_product.name} — Project {self.project_number}: {self.name}"


class ProjectSession(models.Model):
    """Session under a ProductProject."""
    product_project = models.ForeignKey(ProductProject, on_delete=models.CASCADE, related_name='sessions')
    session_number = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=200, verbose_name="Session Title")
    description = models.CharField(max_length=200, blank=True, verbose_name="Brief Session Descriptor")

    class Meta:
        ordering = ['product_project', 'session_number']

    def __str__(self):
        return f"Session {self.session_number}: {self.title}"


# ==================== ANNOUNCEMENTS ====================

class Announcement(models.Model):
    ANNOUNCEMENT_TYPE_CHOICES = [
        ('event', 'Event'),
        ('newsletter', 'Newsletter'),
        ('success_story', 'Student Success Story'),
    ]
    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPE_CHOICES)

    # Common
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Event fields
    esl_product = models.ForeignKey('ESLProduct', on_delete=models.SET_NULL, null=True, blank=True, related_name='announcements')
    applicable_schools = models.ManyToManyField('schools.School', blank=True, related_name='announcements')
    applicable_grades = models.JSONField(default=list, blank=True)
    event_name = models.CharField(max_length=200, blank=True)
    event_date = models.DateField(null=True, blank=True)
    event_description = models.TextField(blank=True)
    event_link = models.URLField(blank=True)
    publish_to = models.JSONField(default=list, blank=True, help_text='e.g. ["school","student","parent"]')

    # Newsletter fields
    newsletter_date = models.DateField(null=True, blank=True)
    newsletter_month = models.CharField(max_length=20, blank=True)
    newsletter_file = models.FileField(upload_to='newsletters/', null=True, blank=True)
    newsletter_weblink = models.URLField(blank=True)

    # Success Story fields
    story_student_name = models.CharField(max_length=100, blank=True)
    story_grade = models.CharField(max_length=10, blank=True)
    story_school = models.ForeignKey('schools.School', on_delete=models.SET_NULL, null=True, blank=True, related_name='success_stories')
    story_text = models.CharField(max_length=500, blank=True)
    story_photo_1 = models.ImageField(upload_to='success_stories/', null=True, blank=True)
    story_photo_2 = models.ImageField(upload_to='success_stories/', null=True, blank=True)
    story_youtube_link = models.URLField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_announcement_type_display()} — {self.event_name or self.story_student_name or 'Newsletter'}"


class RubricCriterion(models.Model):
    """Editable rubric grid (PPT slide 28). One row per competency of an assessment,
    with descriptor text for each of the 4 score bands. Complements (does not replace)
    Assessment.rubric_file."""
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='rubric_criteria')
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE, related_name='rubric_criteria')
    band1_text = models.TextField(blank=True, help_text='1-4 Not meeting expectations')
    band2_text = models.TextField(blank=True, help_text='4-7 Approaching expectation')
    band3_text = models.TextField(blank=True, help_text='7-9 Fully meeting expectation')
    band4_text = models.TextField(blank=True, help_text='9-10 Exceeding expectation')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('assessment', 'competency')]
        ordering = ['id']

    def __str__(self):
        return f"Rubric {self.assessment_id} / {self.competency.code}"
