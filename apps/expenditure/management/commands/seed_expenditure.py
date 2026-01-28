"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to seed expenditure test data.
             Creates system budget heads, payees, allocations, and bills.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from datetime import date
from typing import Any
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.models import Organization, BankAccount
from apps.finance.models import BudgetHead, FunctionCode, Fund, AccountType
from apps.budgeting.models import FiscalYear, BudgetAllocation
from apps.expenditure.models import Payee, Bill, BillStatus
from apps.users.models import CustomUser


class Command(BaseCommand):
    """
    Management command to seed expenditure test data.
    
    This command creates:
    1. System Budget Heads (AP, TAX_IT, TAX_GST, AR)
    2. Sample Payees/Vendors
    3. Budget Allocations for testing
    4. Sample Draft Bills
    """
    
    help = 'Seeds expenditure module with test data for development and testing.'
    
    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--org',
            type=str,
            help='Organization name or DDO code to seed data for (optional).'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing expenditure data before seeding.'
        )
    
    @transaction.atomic
    def handle(self, *args, **options) -> None:
        self.stdout.write(self.style.NOTICE('Starting expenditure seed...'))
        
        # Get or create organization
        org = self._get_or_create_organization(options.get('org'))
        
        if options.get('clear'):
            self._clear_data(org)
        
        # Step 1: Ensure system budget heads exist
        self._create_system_budget_heads()
        
        # Step 2: Get or create fiscal year
        fiscal_year = self._get_or_create_fiscal_year(org)
        
        # Step 3: Create payees
        payees = self._create_payees(org)
        
        # Step 4: Create budget allocations
        allocation = self._create_budget_allocations(org, fiscal_year)
        
        # Step 5: Create sample bills
        self._create_sample_bills(org, fiscal_year, payees, allocation)
        
        self.stdout.write(self.style.SUCCESS(
            '\n✓ Expenditure seed completed successfully!\n'
            f'  Organization: {org.name}\n'
            f'  Fiscal Year: {fiscal_year.year_name}\n'
            f'  Payees: {len(payees)}\n'
            f'  Sample Bills: 2'
        ))
    
    def _get_or_create_organization(self, org_identifier: str = None) -> Organization:
        """Get or create an organization for seeding."""
        if org_identifier:
            org = Organization.objects.filter(
                name__icontains=org_identifier
            ).first() or Organization.objects.filter(
                ddo_code=org_identifier
            ).first()
            
            if not org:
                raise CommandError(f"Organization '{org_identifier}' not found.")
            return org
        
        # Try to get first active organization
        org = Organization.objects.filter(is_active=True).first()
        
        if not org:
            # Create a sample organization
            from apps.core.models import Division, District, Tehsil
            
            division, _ = Division.objects.get_or_create(
                name='Test Division',
                defaults={'code': 'TST'}
            )
            district, _ = District.objects.get_or_create(
                division=division,
                name='Test District',
                defaults={'code': 'TSD'}
            )
            tehsil, _ = Tehsil.objects.get_or_create(
                district=district,
                name='Test Tehsil',
                defaults={'code': 'TST-TSD-TESTTEH'}
            )
            org, created = Organization.objects.get_or_create(
                name='TMA Test Tehsil',
                defaults={
                    'tehsil': tehsil,
                    'org_type': 'TMA',
                    'ddo_code': 'TST-001',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  Created organization: {org.name}')
        
        return org
    
    def _create_system_budget_heads(self) -> None:
        """Create system budget heads for GL automation."""
        self.stdout.write('  Creating system budget heads...')
        
        # Get or create default fund
        fund, _ = Fund.objects.get_or_create(
            code='GEN',
            defaults={'name': 'General Fund', 'is_active': True}
        )
        
        # Get or create function code
        func, _ = FunctionCode.objects.get_or_create(
            code='AD',
            defaults={'name': 'Administration', 'is_active': True}
        )
        
        system_heads = [
            {
                'tma_sub_object': 'L02001-000',
                'pifra_object': 'L02001',
                'pifra_description': 'Accounts Payable - Creditors',
                'tma_description': 'Accounts Payable',
                'account_type': AccountType.LIABILITY,
                'system_code': 'AP',
                'is_system_head': True,
            },
            {
                'tma_sub_object': 'L02101-000',
                'pifra_object': 'L02101',
                'pifra_description': 'Tax Payable - Income Tax',
                'tma_description': 'Income Tax Withheld',
                'account_type': AccountType.LIABILITY,
                'system_code': 'TAX_IT',
                'is_system_head': True,
            },
            {
                'tma_sub_object': 'L02102-000',
                'pifra_object': 'L02102',
                'pifra_description': 'Tax Payable - GST',
                'tma_description': 'GST/Sales Tax Withheld',
                'account_type': AccountType.LIABILITY,
                'system_code': 'TAX_GST',
                'is_system_head': True,
            },
            {
                'tma_sub_object': 'A02001-000',
                'pifra_object': 'A02001',
                'pifra_description': 'Accounts Receivable - Debtors',
                'tma_description': 'Accounts Receivable',
                'account_type': AccountType.ASSET,
                'system_code': 'AR',
                'is_system_head': True,
            },
        ]
        
        for head_data in system_heads:
            head, created = BudgetHead.objects.update_or_create(
                tma_sub_object=head_data['tma_sub_object'],
                defaults={
                    **head_data,
                    'fund': fund,
                    'function': func,
                    'budget_control': False,
                    'posting_allowed': True,
                }
            )
            status = 'created' if created else 'updated'
            self.stdout.write(f'    {head_data["system_code"]}: {status}')
        
        # Create bank GL head if not exists
        bank_head, created = BudgetHead.objects.get_or_create(
            tma_sub_object='A01001-000',
            defaults={
                'pifra_object': 'A01001',
                'pifra_description': 'Cash at Bank',
                'tma_description': 'Bank Account - NBP',
                'account_type': AccountType.ASSET,
                'fund': fund,
                'function': func,
                'budget_control': False,
                'posting_allowed': True,
            }
        )
        if created:
            self.stdout.write('    Bank GL head: created')
    
    def _get_or_create_fiscal_year(self, org: Organization) -> FiscalYear:
        """Get or create the current operating fiscal year based on today's date."""
        today = timezone.now().date()
        
        # First, try to find a fiscal year that contains today's date
        # This is the "current operating year" for expenditure transactions
        fy = FiscalYear.objects.filter(
            organization=org,
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        if fy:
            self.stdout.write(f'  Using current operating fiscal year: {fy.year_name}')
            return fy
        
        # If no current operating year exists, create one based on today's date
        if today.month >= 7:
            start_year = today.year
        else:
            start_year = today.year - 1
        
        year_name = f"{start_year}-{str(start_year + 1)[2:]}"
        
        fy, created = FiscalYear.objects.get_or_create(
            organization=org,
            year_name=year_name,
            defaults={
                'start_date': date(start_year, 7, 1),
                'end_date': date(start_year + 1, 6, 30),
                'is_active': False,  # Don't auto-activate for budget entry
                'is_locked': False,
            }
        )
        
        if created:
            self.stdout.write(f'  Created fiscal year: {fy.year_name}')
        else:
            self.stdout.write(f'  Found fiscal year: {fy.year_name}')
        
        return fy
    
    def _create_payees(self, org: Organization) -> list:
        """Create sample payees/vendors."""
        self.stdout.write('  Creating payees...')
        
        payee_data = [
            {
                'name': 'M/S Construct Corp',
                'cnic_ntn': '1234567-8',
                'address': 'Industrial Area, Peshawar',
                'phone': '091-1234567',
                'bank_name': 'National Bank of Pakistan',
                'bank_account': '1234567890123',
            },
            {
                'name': 'Office Supplies Co.',
                'cnic_ntn': '7654321-0',
                'address': 'Saddar Road, Peshawar',
                'phone': '091-7654321',
                'bank_name': 'Habib Bank Limited',
                'bank_account': '9876543210987',
            },
            {
                'name': 'Tech Solutions Pvt Ltd',
                'cnic_ntn': '5555555-5',
                'address': 'University Town, Peshawar',
                'phone': '091-5555555',
                'email': 'info@techsolutions.pk',
                'bank_name': 'Allied Bank Limited',
                'bank_account': '5555566666777',
            },
        ]
        
        payees = []
        for data in payee_data:
            payee, created = Payee.objects.get_or_create(
                organization=org,
                name=data['name'],
                defaults={**data, 'is_active': True}
            )
            payees.append(payee)
            status = 'created' if created else 'exists'
            self.stdout.write(f'    {payee.name}: {status}')
        
        return payees
    
    def _create_budget_allocations(
        self, org: Organization, fiscal_year: FiscalYear
    ) -> BudgetAllocation:
        """Create budget allocations for testing."""
        self.stdout.write('  Creating budget allocations...')
        
        # Get or create stationery budget head
        fund = Fund.objects.filter(code='GEN').first()
        func = FunctionCode.objects.filter(code='AD').first()
        
        stationery_head, _ = BudgetHead.objects.get_or_create(
            tma_sub_object='A03901-000',
            defaults={
                'pifra_object': 'A03901',
                'pifra_description': 'Stationery',
                'tma_description': 'Stationery & Office Supplies',
                'account_type': AccountType.EXPENDITURE,
                'fund': fund,
                'function': func,
                'budget_control': True,
                'posting_allowed': True,
            }
        )
        
        # Create other expense heads
        other_heads = [
            ('A03902-000', 'A03902', 'POL', 'Petrol, Oil & Lubricants'),
            ('A03903-000', 'A03903', 'Repair', 'Repair & Maintenance'),
            ('A03801-000', 'A03801', 'Electricity', 'Electricity Charges'),
        ]
        
        for tma_sub, pifra, short_desc, full_desc in other_heads:
            BudgetHead.objects.get_or_create(
                tma_sub_object=tma_sub,
                defaults={
                    'pifra_object': pifra,
                    'pifra_description': short_desc,
                    'tma_description': full_desc,
                    'account_type': AccountType.EXPENDITURE,
                    'fund': fund,
                    'function': func,
                    'budget_control': True,
                    'posting_allowed': True,
                }
            )
        
        # Create allocation with released amount
        allocation, created = BudgetAllocation.objects.get_or_create(
            organization=org,
            fiscal_year=fiscal_year,
            budget_head=stationery_head,
            defaults={
                'original_allocation': Decimal('1000000.00'),
                'revised_allocation': Decimal('1000000.00'),
                'released_amount': Decimal('1000000.00'),
                'spent_amount': Decimal('0.00'),
            }
        )
        
        status = 'created' if created else 'exists'
        self.stdout.write(
            f'    A03901 Stationery: {status} (Released: Rs. 1,000,000)'
        )
        
        return allocation
    
    def _create_sample_bills(
        self, org: Organization, fiscal_year: FiscalYear,
        payees: list, allocation: BudgetAllocation
    ) -> None:
        """Create sample draft bills."""
        self.stdout.write('  Creating sample bills...')
        
        # Check if bills already exist
        existing_count = Bill.objects.filter(
            organization=org,
            fiscal_year=fiscal_year
        ).count()
        
        if existing_count >= 2:
            self.stdout.write(
                f'    {existing_count} bills already exist, skipping creation.'
            )
            return
        
        bills_data = [
            {
                'payee': payees[0],
                'budget_head': allocation.budget_head,
                'bill_date': timezone.now().date(),
                'bill_number': 'INV-2026-001',
                'description': 'Office furniture for conference room',
                'gross_amount': Decimal('50000.00'),
                'tax_amount': Decimal('3500.00'),  # 7% tax
            },
            {
                'payee': payees[1],
                'budget_head': allocation.budget_head,
                'bill_date': timezone.now().date(),
                'bill_number': 'INV-2026-002',
                'description': 'Monthly stationery supplies - January 2026',
                'gross_amount': Decimal('25000.00'),
                'tax_amount': Decimal('1750.00'),  # 7% tax
            },
        ]
        
        for data in bills_data:
            net_amount = data['gross_amount'] - data['tax_amount']
            bill, created = Bill.objects.get_or_create(
                organization=org,
                fiscal_year=fiscal_year,
                bill_number=data['bill_number'],
                defaults={
                    **data,
                    'net_amount': net_amount,
                    'status': BillStatus.DRAFT,
                }
            )
            status = 'created' if created else 'exists'
            self.stdout.write(
                f'    Bill {data["bill_number"]}: {status} '
                f'(Gross: Rs. {data["gross_amount"]})'
            )
        
        # Create a bank account for payments (if not exists)
        bank_gl = BudgetHead.objects.filter(tma_sub_object='A01001-000').first()
        if bank_gl:
            BankAccount.objects.get_or_create(
                organization=org,
                account_number='1234567890',
                defaults={
                    'bank_name': 'National Bank of Pakistan',
                    'branch_code': '0001',
                    'title': f'{org.name} - Current Account',
                    'gl_code': bank_gl,
                    'is_active': True,
                }
            )
            self.stdout.write('    Bank account: ready')
    
    def _clear_data(self, org: Organization) -> None:
        """Clear existing expenditure data for the organization."""
        self.stdout.write(self.style.WARNING('  Clearing existing data...'))
        
        from apps.expenditure.models import Payment
        
        Payment.objects.filter(organization=org).delete()
        Bill.objects.filter(organization=org).delete()
        Payee.objects.filter(organization=org).delete()
        
        self.stdout.write('    Cleared payments, bills, and payees.')
