"""
Seed sample competencies for the CSL+ framework.

CSL+ ships with its pillar / sub-pillar structure but no competencies, so the
Project → Assessment competency dropdown is empty for CSL+ projects. This command
fills each CSL+ sub-pillar with a few sample competencies.

Idempotent: a sub-pillar that already has competencies is left untouched, and
duplicate codes are skipped — safe to run more than once (e.g. on production).

Usage:
    python manage.py seed_csl_competencies
    python manage.py seed_csl_competencies --stage Middle   # default: Middle
    python manage.py seed_csl_competencies --framework CSL+  # default: CSL+
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from competencies.models import Framework, SubPillar, Competency

# 3 sample competencies per sub-pillar, keyed by sp_number (CSL+ sub-pillars = 18–34).
NAMES = {
    18: ["Self-Awareness", "Interest Identification", "Values Clarification"],
    19: ["Personality Development", "Effective Communication", "Public Speaking"],
    20: ["Social Awareness", "Community Engagement", "Networking"],
    21: ["Digital Literacy", "Media Analysis", "Data Interpretation"],
    22: ["Financial Planning", "Economic Reasoning", "Budgeting"],
    23: ["Environmental Awareness", "Sustainable Practices", "Climate Responsibility"],
    24: ["Systems Thinking", "IoT Fundamentals", "Automation Awareness"],
    25: ["Computational Thinking", "Coding Basics", "AI & ML Awareness"],
    26: ["Design Fundamentals", "Emerging Tech Awareness", "Prototyping"],
    27: ["Critical Analysis", "Problem Framing", "Solution Design"],
    28: ["Creative Ideation", "Innovation Mindset", "Original Thinking"],
    29: ["Teamwork", "Cooperative Learning", "Conflict Resolution"],
    30: ["Self-Regulation", "Empathy", "Emotional Awareness"],
    31: ["Empathize & Define", "Ideation", "Prototype & Test"],
    32: ["Opportunity Recognition", "Risk Taking", "Value Creation"],
    33: ["Global Awareness", "Cross-cultural Sensitivity", "Ethical Citizenship"],
    34: ["Adaptability", "Career Readiness", "Lifelong Learning"],
}


class Command(BaseCommand):
    help = "Seed sample competencies for the CSL+ framework (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--framework', default='CSL+', help='Framework name (default: CSL+)')
        parser.add_argument('--stage', default='Middle', help='Stage for seeded competencies (default: Middle)')

    @transaction.atomic
    def handle(self, *args, **options):
        fw_name = options['framework']
        stage = options['stage']

        fw = Framework.objects.filter(name=fw_name).first()
        if not fw:
            self.stderr.write(self.style.ERROR(f'Framework "{fw_name}" not found.'))
            return

        created, skipped = 0, 0
        sub_pillars = SubPillar.objects.filter(pillar__framework_ref=fw).order_by('sp_number')
        if not sub_pillars.exists():
            self.stderr.write(self.style.ERROR(f'No sub-pillars found for framework "{fw_name}".'))
            return

        for sp in sub_pillars:
            if sp.competencies.exists():
                skipped += sp.competencies.count()
                continue
            for i, name in enumerate(NAMES.get(sp.sp_number, []), start=1):
                code = f"{sp.code}.C{i}"
                if Competency.objects.filter(code=code).exists():
                    skipped += 1
                    continue
                Competency.objects.create(
                    sub_pillar=sp,
                    code=code,
                    name=name,
                    description=f"{name} under {sp.name}.",
                    stage=stage,
                    status='Active',
                )
                created += 1

        total = Competency.objects.filter(
            sub_pillar__pillar__framework_ref=fw, status='Active'
        ).count()
        self.stdout.write(self.style.SUCCESS(
            f'Done. Created={created}, Skipped={skipped}, '
            f'Total active {fw_name} competencies={total}.'
        ))
