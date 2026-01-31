# Generated manually on 2026-01-31
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('expenditure', '0002_make_budget_head_nullable'),
        ('finance', '0015_alter_budgethead_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BillLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(help_text='Line item description.', max_length=255, verbose_name='Description')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Amount')),
                ('bill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='expenditure.bill', verbose_name='Bill')),
                ('budget_head', models.ForeignKey(help_text='Expense head to charge.', on_delete=django.db.models.deletion.PROTECT, related_name='bill_lines', to='finance.budgethead', verbose_name='Budget Head')),
            ],
            options={
                'verbose_name': 'Bill Line',
                'verbose_name_plural': 'Bill Lines',
            },
        ),
    ]
