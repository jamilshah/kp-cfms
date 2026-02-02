# Generated migration to add department and function to BudgetEmployee

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('budgeting', '0021_budgetemployee_expected_salary_increase_percentage'),
        ('finance', '0017_add_department_scope_to_globalhead'),
    ]

    operations = [
        # Make schedule field optional
        migrations.AlterField(
            model_name='budgetemployee',
            name='schedule',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='employees',
                to='budgeting.scheduleofestablishment',
                verbose_name='Schedule Entry',
                help_text='Optional: Link to establishment entry (for reporting only)'
            ),
        ),
        # Add department field
        migrations.AddField(
            model_name='budgetemployee',
            name='department',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='budget_employees',
                to='budgeting.department',
                verbose_name='Department',
                help_text='Department where employee works'
            ),
        ),
        # Add function field
        migrations.AddField(
            model_name='budgetemployee',
            name='function',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='budget_employees',
                to='finance.functioncode',
                verbose_name='Function',
                help_text='Function code for this employee (determines budget allocation)'
            ),
        ),
        # Add fiscal year field for better tracking
        migrations.AddField(
            model_name='budgetemployee',
            name='fiscal_year',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='budget_employees',
                to='budgeting.fiscalyear',
                verbose_name='Fiscal Year',
                help_text='Fiscal year for this employee record'
            ),
        ),
    ]
