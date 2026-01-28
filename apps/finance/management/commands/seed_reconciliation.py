"""
Seed Reconciliation Management Command
========================================

Creates sample bank statements and statement lines for testing
the bank reconciliation feature.

Usage:
    python manage.py seed_reconciliation [--org-id=1]
"""

from datetime import date, timedelta
from decimal import Decimal
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Organization, BankAccount
from apps.budgeting.models import FiscalYear
from apps.finance.models import BankStatement, BankStatementLine, JournalEntry


class Command(BaseCommand):
    help = 'Creates sample bank statements and lines for testing reconciliation'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id',
            type=int,
            default=1,
            help='Organization ID to create data for (default: 1)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing bank statements before creating new ones'
        )
    
    @transaction.atomic
    def handle(self, *args, **options):
        org_id = options['org_id']
        
        # Get organization
        try:
            organization = Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist:
            raise CommandError(f'Organization with ID {org_id} not found')
        
        self.stdout.write(f'Creating sample data for: {organization.name}')
        
        # Get or validate prerequisites
        bank_account = BankAccount.objects.filter(
            organization=organization,
            is_active=True
        ).first()
        
        if not bank_account:
            raise CommandError(
                'No active bank account found. '
                'Please create a bank account first using the admin.'
            )
        
        fiscal_year = FiscalYear.objects.filter(
            organization=organization,
            is_active=True
        ).first()
        
        if not fiscal_year:
            raise CommandError(
                'No active fiscal year found. '
                'Please create a fiscal year first.'
            )
        
        # Clear existing data if requested
        if options['clear']:
            deleted, _ = BankStatement.objects.filter(
                bank_account__organization=organization
            ).delete()
            self.stdout.write(f'Cleared {deleted} existing bank statements')
        
        # Create sample bank statement for current month
        today = date.today()
        month = today.month
        
        # Check if statement already exists
        existing = BankStatement.objects.filter(
            bank_account=bank_account,
            month=month,
            fiscal_year=fiscal_year
        ).first()
        
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f'Bank statement for {existing} already exists. '
                    'Use --clear to remove it first.'
                )
            )
            return
        
        # Create bank statement
        statement = BankStatement.objects.create(
            bank_account=bank_account,
            month=month,
            fiscal_year=fiscal_year,
            opening_balance=Decimal('500000.00'),
            closing_balance=Decimal('485250.00'),  # Will be calculated below
            status='draft',
            notes='Sample bank statement for testing reconciliation.'
        )
        
        self.stdout.write(f'Created bank statement: {statement}')
        
        # Get some existing journal entries for matching
        gl_entries = JournalEntry.objects.filter(
            voucher__organization=organization,
            head=bank_account.gl_code,
            is_reconciled=False
        ).select_related('voucher').order_by('-voucher__date')[:3]
        
        # Sample bank statement lines
        lines_data = []
        
        # Lines that match existing GL entries
        for i, entry in enumerate(gl_entries):
            if entry.credit > 0:
                # Payment in GL = Debit in bank (money going out)
                lines_data.append({
                    'date': entry.voucher.date,
                    'description': f'CHQ CLR - {entry.description[:30] if entry.description else "Payment"}',
                    'debit': entry.credit,  # GL credit = Bank debit
                    'credit': Decimal('0'),
                    'ref_no': entry.instrument_no or f'CHQ{100000 + i}',
                    'balance': Decimal('0'),  # Will be calculated
                })
            elif entry.debit > 0:
                # Receipt in GL = Credit in bank (money coming in)
                lines_data.append({
                    'date': entry.voucher.date,
                    'description': f'DEPOSIT - {entry.description[:30] if entry.description else "Receipt"}',
                    'debit': Decimal('0'),
                    'credit': entry.debit,  # GL debit = Bank credit
                    'ref_no': entry.instrument_no or f'DEP{100000 + i}',
                    'balance': Decimal('0'),
                })
        
        # Add a bank charge (exists in bank, not in GL)
        lines_data.append({
            'date': today - timedelta(days=5),
            'description': 'BANK CHARGES - ACCOUNT MAINTENANCE FEE',
            'debit': Decimal('500.00'),
            'credit': Decimal('0'),
            'ref_no': 'BC' + today.strftime('%Y%m'),
            'balance': Decimal('0'),
        })
        
        # Add an unknown deposit (exists in bank, not in GL)
        lines_data.append({
            'date': today - timedelta(days=3),
            'description': 'RTGS CREDIT - UNKNOWN SENDER',
            'debit': Decimal('0'),
            'credit': Decimal('25000.00'),
            'ref_no': 'RTGS' + str(random.randint(10000000, 99999999)),
            'balance': Decimal('0'),
        })
        
        # Sort by date
        lines_data.sort(key=lambda x: x['date'])
        
        # Calculate running balances
        running_balance = statement.opening_balance
        for line in lines_data:
            if line['debit'] > 0:
                running_balance -= line['debit']
            if line['credit'] > 0:
                running_balance += line['credit']
            line['balance'] = running_balance
        
        # Update closing balance
        statement.closing_balance = running_balance
        statement.save()
        
        # Create statement lines
        for line_data in lines_data:
            BankStatementLine.objects.create(
                statement=statement,
                **line_data
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {len(lines_data)} bank statement lines:\n'
                f'  - {len(gl_entries)} lines matching existing GL entries\n'
                f'  - 1 bank charge (unmatched)\n'
                f'  - 1 unknown deposit (unmatched)'
            )
        )
        
        # Summary
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(f'Bank Statement: {statement}')
        self.stdout.write(f'Bank Account: {bank_account.title}')
        self.stdout.write(f'Opening Balance: Rs. {statement.opening_balance:,.2f}')
        self.stdout.write(f'Closing Balance: Rs. {statement.closing_balance:,.2f}')
        self.stdout.write(f'Total Lines: {len(lines_data)}')
        self.stdout.write('=' * 50)
        
        self.stdout.write(
            self.style.SUCCESS(
                '\nTo test reconciliation:\n'
                f'1. Go to Finance > Bank Statements\n'
                f'2. Click on "{statement}"\n'
                f'3. Click "Reconcile" to open the workbench\n'
                f'4. Try "Auto Reconcile" to match items automatically\n'
                f'5. Manually match remaining items if needed'
            )
        )
