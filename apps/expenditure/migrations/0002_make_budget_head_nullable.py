# Generated manually on 2026-01-31
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('expenditure', '0001_initial'),
        ('finance', '0015_alter_budgethead_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bill',
            name='budget_head',
            field=models.ForeignKey(
                blank=True,
                help_text='Expense head to charge (legacy field, use BillLine for new bills).',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='legacy_bills',
                to='finance.budgethead',
                verbose_name='Budget Head'
            ),
        ),
    ]
