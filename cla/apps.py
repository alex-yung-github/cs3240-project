from django.apps import AppConfig


class ClaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cla'

    # imports cla.signals module registers the signal handler
    def ready(self):
        import cla.signals