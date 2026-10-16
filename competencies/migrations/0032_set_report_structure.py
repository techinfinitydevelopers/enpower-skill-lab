"""Set the report structure the client asked for, on 2026-10-16.

    CSL+              keep the annual report, call it "Annual Skill Report",
                      hide Kaushal Bodh ("do not delete it, as we may need it
                      in the future" -- so the flag, not the data).
    CSL Foundation    no annual report at all; Project Report and the Kaushal
                      Bodh annual report only.
    FSL               untouched. It is the shape the others are being matched
                      to.

Matched by name, and silent when a name is absent: a database without these
frameworks is not a broken one, and the Super Admin can set any of this from
Manage Frameworks afterwards.
"""

from django.db import migrations

WANTED = {
    'CSL+': {
        'show_annual_report': True,
        'annual_report_title': 'Annual Skill Report',
        'has_kaushal_bodh': False,
    },
    'CSL Foundation': {
        'show_annual_report': False,
        'has_kaushal_bodh': True,
    },
}


def apply_structure(apps, schema_editor):
    Framework = apps.get_model('competencies', 'Framework')
    for name, fields in WANTED.items():
        # Spelling drifts -- "CSL +" was typed with a space in one place.
        fw = (Framework.objects.filter(name__iexact=name).first()
              or Framework.objects.filter(
                  name__iexact=name.replace('+', ' +')).first())
        if fw is None:
            continue
        for field, value in fields.items():
            setattr(fw, field, value)
        fw.save(update_fields=list(fields))


def undo(apps, schema_editor):
    """Nothing to put back: the previous values were not a decision anybody
    made, they were the defaults the frameworks happened to carry."""


class Migration(migrations.Migration):

    dependencies = [
        ('competencies', '0031_framework_annual_report_title_and_more'),
    ]

    operations = [migrations.RunPython(apply_structure, undo)]
