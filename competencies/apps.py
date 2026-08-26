from django.apps import AppConfig


class CompetenciesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'competencies'

    def ready(self):
        # Registers the ScoreEntry -> ProjectReport.is_outdated signal.
        from . import signals  # noqa: F401
