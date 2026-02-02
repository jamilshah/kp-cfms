# Generated migration to add default_function to Department and usage_notes to FunctionCode

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('budgeting', '0022_add_employee_dept_function'),
        ('finance', '0017_add_department_scope_to_globalhead'),
    ]

    operations = [
        # Add default_function to Department
        migrations.AddField(
            model_name='department',
            name='default_function',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='default_for_departments',
                to='finance.functioncode',
                verbose_name='Default Function',
                help_text='Primary/default function for this department (auto-selected in forms)'
            ),
        ),
    ]
