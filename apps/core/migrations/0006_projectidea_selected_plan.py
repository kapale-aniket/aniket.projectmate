# Generated manually for selected_plan on ProjectIdea

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_projectplan_projectplanperk"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectidea",
            name="selected_plan",
            field=models.ForeignKey(
                blank=True,
                help_text="Plan the student chose before submitting",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="idea_submissions",
                to="core.projectplan",
            ),
        ),
    ]
