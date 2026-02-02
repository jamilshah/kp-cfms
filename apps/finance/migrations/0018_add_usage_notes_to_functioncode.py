# Generated migration to add usage_notes to FunctionCode

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0017_add_department_scope_to_globalhead'),
    ]

    operations = [
        # Add usage_notes to FunctionCode
        migrations.AddField(
            model_name='functioncode',
            name='usage_notes',
            field=models.TextField(
                blank=True,
                verbose_name='Usage Notes',
                help_text='Guidelines on what expenses should be recorded under this function (AGP/PIFRA compliance)'
            ),
        ),
        # Add is_default flag for marking default functions
        migrations.AddField(
            model_name='functioncode',
            name='is_default',
            field=models.BooleanField(
                default=False,
                verbose_name='Is Default',
                help_text='Mark as default function for its department'
            ),
        ),
    ]
