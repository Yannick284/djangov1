from django.db import migrations


def set_site(apps, schema_editor):
    """Le « site » Django (utilisé par allauth dans les e-mails) s'appelait example.com : on y met le vrai nom."""
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(pk=1, defaults={"domain": "yannickwahl.fr", "name": "Yannick Wahl"})


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0012_comments_projects"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [migrations.RunPython(set_site, migrations.RunPython.noop)]
