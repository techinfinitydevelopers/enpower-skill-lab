"""Give every existing upload's file a row of its own.

`StudentProjectUpload.file` held one file. Phase 2 moves files to
`ProjectUploadFile` so a coach can attach several, and the templates read the
rows rather than the field. Without this step every project uploaded before
today would render with no file at all.

Additive and reversible: the original `file` field is not touched, so the
reverse simply removes the rows this created and nothing is lost either way.
"""

from django.db import migrations


def copy_files_into_rows(apps, schema_editor):
    StudentProjectUpload = apps.get_model('attendance', 'StudentProjectUpload')
    ProjectUploadFile = apps.get_model('attendance', 'ProjectUploadFile')

    made = []
    for upload in StudentProjectUpload.objects.exclude(file='').exclude(file=None):
        # Guard against a re-run leaving two rows for the same file.
        if ProjectUploadFile.objects.filter(upload=upload).exists():
            continue
        made.append(ProjectUploadFile(upload=upload, file=upload.file.name,
                                      order=0))
    ProjectUploadFile.objects.bulk_create(made, batch_size=200)


def drop_rows(apps, schema_editor):
    ProjectUploadFile = apps.get_model('attendance', 'ProjectUploadFile')
    ProjectUploadFile.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0007_projectuploadfile'),
    ]

    operations = [
        migrations.RunPython(copy_files_into_rows, drop_rows),
    ]
