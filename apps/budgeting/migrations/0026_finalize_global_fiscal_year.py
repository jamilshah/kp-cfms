from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('budgeting', '0025_migrate_fiscal_year_data'),
    ]

    operations = [
        # 4. Remove Unique Together Constraint (from Organization + YearName)
        migrations.AlterUniqueTogether(
            name='fiscalyear',
            unique_together=set(),
        ),

        # 5. Apply Unique Constraint to Year Name (Now that duplicates are gone)
        migrations.AlterField(
            model_name='fiscalyear',
            name='year_name',
            field=models.CharField(help_text='Display name for the fiscal year (e.g., "2026-27").', max_length=20, unique=True, verbose_name='Fiscal Year'),
        ),

        # 6. Remove Old Fields
        migrations.RemoveField(
            model_name='fiscalyear',
            name='is_active',
        ),
        migrations.RemoveField(
            model_name='fiscalyear',
            name='is_locked',
        ),
        migrations.RemoveField(
            model_name='fiscalyear',
            name='organization',
        ),
        migrations.RemoveField(
            model_name='fiscalyear',
            name='sae_generated_at',
        ),
        migrations.RemoveField(
            model_name='fiscalyear',
            name='sae_number',
        ),
        migrations.RemoveField(
            model_name='fiscalyear',
            name='status',
        ),
    ]
