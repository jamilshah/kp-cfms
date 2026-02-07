from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0022_globalhead_applicable_functions'),
    ]

    operations = [
        # Update Voucher Permissions and Options
        migrations.AlterModelOptions(
            name='voucher',
            options={
                'ordering': ['-date', '-voucher_no'],
                'permissions': [
                    ('can_post_voucher', 'Can post vouchers to GL'),
                    ('can_reverse_voucher', 'Can reverse posted vouchers')
                ],
                'verbose_name': 'Voucher',
                'verbose_name_plural': 'Vouchers'
            },
        ),
        
        # BudgetHead Indexes
        migrations.AddIndex(
            model_name='budgethead',
            index=models.Index(
                fields=['fund', 'is_active'], 
                name='finance_bh_fund_active_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='budgethead',
            index=models.Index(
                fields=['posting_allowed', 'is_active'], 
                name='finance_bh_posting_active_idx'
            ),
        ),
        
        # Voucher Indexes
        migrations.AddIndex(
            model_name='voucher',
            index=models.Index(
                fields=['organization', 'date', 'is_posted'], 
                name='finance_v_org_date_posted_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='voucher',
            index=models.Index(
                fields=['is_reversed', 'reversed_at'], 
                name='finance_v_reversed_idx'
            ),
        ),
        
        # JournalEntry Indexes
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(
                fields=['budget_head', 'is_reconciled'], 
                name='finance_je_bh_reconciled_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(
                fields=['voucher', 'budget_head'], 
                name='finance_je_voucher_bh_idx'
            ),
        ),
    ]
