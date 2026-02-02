"""
Generated migration for salary bill support
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('expenditure', '0005_alter_bill_status'),
        ('finance', '0017_add_department_scope_to_globalhead'),
        ('budgeting', '0021_budgetemployee_expected_salary_increase_percentage'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='fund',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bills',
                to='finance.fund',
                verbose_name='Fund'
            ),
        ),
        migrations.AddField(
            model_name='bill',
            name='bill_type',
            field=models.CharField(
                choices=[
                    ('REGULAR', 'Regular Bill'),
                    ('SALARY', 'Monthly Salary'),
                ],
                default='REGULAR',
                max_length=20,
                verbose_name='Bill Type'
            ),
        ),
        migrations.AddField(
            model_name='bill',
            name='salary_month',
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name='Salary Month',
                help_text='Month (1-12) for salary bills'
            ),
        ),
        migrations.AddField(
            model_name='bill',
            name='salary_year',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Salary Year',
                help_text='Year for salary bills'
            ),
        ),
        migrations.AddField(
            model_name='bill',
            name='department',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bills',
                to='budgeting.department',
                verbose_name='Department'
            ),
        ),
    ]
