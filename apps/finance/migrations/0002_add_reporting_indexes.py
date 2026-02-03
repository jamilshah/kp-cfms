"""
Performance optimization migration for financial reports.

Adds database indexes to improve query performance for ledger reports.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),  # Update this to your latest migration
    ]

    operations = [
        # Add index on JournalEntry for common query patterns
        migrations.AddIndex(
            model_name='journalentry',
            index=models.Index(
                fields=['budget_head', 'voucher'],
                name='je_budget_voucher_idx'
            ),
        ),
        # Add index for date-based filtering
        migrations.AddIndex(
            model_name='voucher',
            index=models.Index(
                fields=['date', 'is_posted'],
                name='voucher_date_posted_idx'
            ),
        ),
        # Add index for voucher number lookups
        migrations.AddIndex(
            model_name='voucher',
            index=models.Index(
                fields=['voucher_no'],
                name='voucher_no_idx'
            ),
        ),
    ]
