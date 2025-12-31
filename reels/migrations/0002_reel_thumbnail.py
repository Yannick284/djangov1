from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("reels", "0002_category_add_color"),  # <= NOM EXACT
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "reels_category" DROP COLUMN IF EXISTS "color";',
                    reverse_sql=migrations.RunSQL.noop,
                )
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="category",
                    name="color",
                )
            ],
        )
    ]