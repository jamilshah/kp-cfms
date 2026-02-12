"""
Management command to create essential system accounts for accrual accounting.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.finance.models import (
    MajorHead, MinorHead, NAMHead, BudgetHead, 
    Fund, FunctionCode, SystemCode, AccountType
)
from apps.budgeting.models import Department


class Command(BaseCommand):
    help = 'Creates essential system accounts (AP, AR, Tax accounts) for accrual accounting'

    def handle(self, *args, **options):
        self.stdout.write("Creating System Accounts for Accrual Accounting...")
        self.stdout.write("=" * 80)
        
        # Define essential system accounts
        SYSTEM_ACCOUNTS = [
            {
                'major': {'code': 'G01', 'name': 'Current Liabilities'},
                'minor': {'code': 'G011', 'name': 'Payables'},
                'nam': {'code': 'G01101', 'name': 'Accounts Payable', 'system_code': SystemCode.AP, 'account_type': AccountType.LIABILITY},
            },
            {
                'major': {'code': 'G01', 'name': 'Current Liabilities'},
                'minor': {'code': 'G012', 'name': 'Tax Payables'},
                'nam': {'code': 'G01204', 'name': 'Income Tax Payable', 'system_code': SystemCode.TAX_IT, 'account_type': AccountType.LIABILITY},
            },
            {
                'major': {'code': 'G01', 'name': 'Current Liabilities'},
                'minor': {'code': 'G012', 'name': 'Tax Payables'},
                'nam': {'code': 'G01205', 'name': 'Sales Tax/GST Payable', 'system_code': SystemCode.TAX_GST, 'account_type': AccountType.LIABILITY},
            },
            {
                'major': {'code': 'G01', 'name': 'Current Liabilities'},
                'minor': {'code': 'G011', 'name': 'Payables'},
                'nam': {'code': 'G01140', 'name': 'Income Tax Withheld (Clearing)', 'system_code': SystemCode.CLEARING_IT, 'account_type': AccountType.LIABILITY},
            },
            {
                'major': {'code': 'G01', 'name': 'Current Liabilities'},
                'minor': {'code': 'G011', 'name': 'Payables'},
                'nam': {'code': 'G01145', 'name': 'Sales Tax Withheld (Clearing)', 'system_code': SystemCode.CLEARING_GST, 'account_type': AccountType.LIABILITY},
            },
            {
                'major': {'code': 'F01', 'name': 'Current Assets'},
                'minor': {'code': 'F016', 'name': 'Receivables'},
                'nam': {'code': 'F01603', 'name': 'Accounts Receivable', 'system_code': SystemCode.AR, 'account_type': AccountType.ASSET},
            },
            {
                'major': {'code': 'G05', 'name': 'Control Accounts'},
                'minor': {'code': 'G051', 'name': 'Miscellaneous'},
                'nam': {'code': 'G05103', 'name': 'Suspense Account', 'system_code': SystemCode.SYS_SUSPENSE, 'account_type': AccountType.LIABILITY},
            },
        ]
        
        with transaction.atomic():
            for acc in SYSTEM_ACCOUNTS:
                # Create Major Head
                major, _ = MajorHead.objects.get_or_create(
                    code=acc['major']['code'],
                    defaults={
                        'name': acc['major']['name']
                    }
                )
                
                # Create Minor Head
                minor, _ = MinorHead.objects.get_or_create(
                    code=acc['minor']['code'],
                    defaults={
                        'name': acc['minor']['name'],
                        'major': major
                    }
                )
                
                # Create NAM Head with system_code
                account_type = acc['nam']['account_type']
                nam, created = NAMHead.objects.get_or_create(
                    code=acc['nam']['code'],
                    defaults={
                        'name': acc['nam']['name'],
                        'minor': minor,
                        'account_type': account_type,
                        'system_code': acc['nam']['system_code'],
                        'allow_direct_posting': True,
                        'is_active': True
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f"✓ Created NAMHead: {nam.code} - {nam.name} ({nam.system_code})"))
                else:
                    # Update system_code if not set
                    if not nam.system_code:
                        nam.system_code = acc['nam']['system_code']
                        nam.save()
                        self.stdout.write(self.style.WARNING(f"↻ Updated NAMHead: {nam.code} with system_code {nam.system_code}"))
                    else:
                        self.stdout.write(f"  Already exists: {nam.code} - {nam.name}")
                
                # Create BudgetHead for each system account
                fund = Fund.objects.filter(code='GEN').first()
                if not fund:
                    fund, _ = Fund.objects.get_or_create(code='GEN', defaults={'name': 'General Fund', 'is_active': True})
                
                function = FunctionCode.objects.filter(code='AD').first() or FunctionCode.objects.filter(is_active=True).first()
                department = Department.objects.filter(is_active=True).first()
                
                if fund and function and department:
                    bh, bh_created = BudgetHead.objects.get_or_create(
                        department=department,
                        fund=fund,
                        function=function,
                        nam_head=nam,
                        defaults={
                            'current_budget': 0,
                            'budget_control': False,  # System accounts don't need budget control
                            'posting_allowed': True,
                            'is_active': True
                        }
                    )
                    
                    if bh_created:
                        self.stdout.write(f"  → Created BudgetHead for {nam.code}")
        
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("✓ System accounts created successfully!"))
        self.stdout.write("\nYou can now:")
        self.stdout.write("  • Approve bills (will create AP and tax liabilities)")
        self.stdout.write("  • Post payments (will clear AP)")
        self.stdout.write("  • Raise revenue demands (will create AR)")
        self.stdout.write("  • View Pending Liabilities report")
