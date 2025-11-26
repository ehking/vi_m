from django.db import migrations, models


def ensure_generation_progress_column(apps, schema_editor):
    GeneratedVideo = apps.get_model("videos", "GeneratedVideo")
    connection = schema_editor.connection
    table_name = GeneratedVideo._meta.db_table
    existing_columns = {
        column.name for column in connection.introspection.get_table_description(connection.cursor(), table_name)
    }

    if "generation_progress" in existing_columns:
        return

    field = models.PositiveIntegerField(default=0, blank=True)
    field.set_attributes_from_name("generation_progress")
    schema_editor.add_field(GeneratedVideo, field)


class Migration(migrations.Migration):

    dependencies = [
        ("videos", "0003_alter_generatedvideo_generation_progress"),
    ]

    operations = [
        migrations.RunPython(ensure_generation_progress_column, migrations.RunPython.noop),
    ]
