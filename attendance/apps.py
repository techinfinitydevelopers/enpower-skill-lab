from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'

    def ready(self):
        # Registered here so it holds for every path that saves a schedule:
        # the coordinator form, the Super Admin form, the admin, a shell.
        # A view-level call would only cover the paths someone remembered.
        from . import signals  # noqa: F401
