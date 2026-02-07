"""
Management command to populate AccountBalance summary table.

This command scans all posted vouchers and builds the AccountBalance summary table
for performance optimization. Run this once to initialize the table, then it will
be maintained automatically by Voucher.post_voucher().

Usage:
    python manage.py populate_account_balances
    python manage.py populate_account_balances --organization 1
    python manage.py populate_account_balances --fiscal-year 2025-26
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.finance.models import Voucher, AccountBalance, BudgetHead
from apps.budgeting.models import FiscalYear
from apps.core.models import Organization
from decimal import Decimal


class Command(BaseCommand):
    help = 'Populate AccountBalance summary table from existing vouchers'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--organization',
            type=int,
            help='Organization ID to process (default: all)'
        )
        parser.add_argument(
            '--fiscal-year',
            type=str,
            help='Fiscal year name (e.g., "2025-26", default: all)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing AccountBalance data before populating'
        )
    
    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("Populating AccountBalance Summary Table"))
        self.stdout.write("=" * 80)
        
        # Filter criteria
        organizations = Organization.objects.all()
        if options['organization']:
            organizations = organizations.filter(id=options['organization'])
        
        fiscal_years = FiscalYear.objects.all()
        if options['fiscal_year']:
            fiscal_years = fiscal_years.filter(year_name=options['fiscal_year'])
        
        # Clear existing data if requested
        if options['clear']:
            self.stdout.write(self.style.WARNING("\nClearing existing AccountBalance data..."))
            deleted_count = AccountBalance.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f"Deleted {deleted_count} records"))
        
        total_created = 0
        total_updated = 0
        
        for org in organizations:
            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(f"Organization: {org.name}")
            self.stdout.write(f"{'='*80}")
            
            for fy in fiscal_years:
                self.stdout.write(f"\n  Fiscal Year: {fy.year_name}")
                
                # Get all posted vouchers for this org and fiscal year
                vouchers = Voucher.objects.filter(
                    organization=org,
                    fiscal_year=fy,
                    is_posted=True
                ).prefetch_related('entries__budget_head')
                
                voucher_count = vouchers.count()
                self.stdout.write(f"    Found {voucher_count} posted vouchers")
                
                if voucher_count == 0:
                    continue
                
                # Group entries by month and budget head
                monthly_data = {}
                
                for voucher in vouchers:
                    month = voucher.date.month
                    
                    for entry in voucher.entries.all():
                        key = (month, entry.budget_head_id)
                        
                        if key not in monthly_data:
                            monthly_data[key] = {
                                'month': month,
                                'budget_head': entry.budget_head,
                                'total_debit': Decimal('0.00'),
                                'total_credit': Decimal('0.00')
                            }
                        
                        monthly_data[key]['total_debit'] += entry.debit
                        monthly_data[key]['total_credit'] += entry.credit
                
                # Create or update AccountBalance records
                with transaction.atomic():
                    for (month, head_id), data in monthly_data.items():
                        balance, created = AccountBalance.objects.get_or_create(
                            organization=org,
                            fiscal_year=fy,
                            budget_head=data['budget_head'],
                            month=month,
                            defaults={
                                'total_debit': data['total_debit'],
                                'total_credit': data['total_credit'],
                            }
                        )
                        
                        if created:
                            balance.calculate_closing_balance()
                            balance.save()
                            total_created += 1
                        else:
                            # Update existing
                            balance.total_debit = data['total_debit']
                            balance.total_credit = data['total_credit']
                            balance.calculate_closing_balance()
                            balance.save()
                            total_updated += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"    ✓ Created: {len([k for k in monthly_data if k])} balance records"
                    )
                )
        
        # Summary
        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(f"{'='*80}")
        self.stdout.write(f"Total created: {total_created}")
        self.stdout.write(f"Total updated: {total_updated}")
        self.stdout.write(f"Total processed: {total_created + total_updated}")
        self.stdout.write(f"\n{self.style.SUCCESS('✓ AccountBalance population completed!')}")
        self.stdout.write(f"{'='*80}\n")
