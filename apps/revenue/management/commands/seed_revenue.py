"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to seed revenue test data.
             Creates AR system head, revenue heads, payers, and demands.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import Any, List
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.models import Organization, BankAccount
from apps.finance.models import BudgetHead, FunctionCode, Fund, AccountType, MajorHead, MinorHead, GlobalHead
from apps.budgeting.models import FiscalYear
from apps.revenue.models import Payer, RevenueDemand, RevenueCollection, DemandStatus
from apps.users.models import CustomUser


class Command(BaseCommand):
    """
    Management command to seed revenue test data.
    
    This command creates:
    1. Accounts Receivable system head (AR)
    2. Revenue budget heads (Shop Rent, Education Fee)
    3. Sample Payers
    4. Sample Revenue Demands
    """
    
    help = 'Seeds revenue module with test data for development and testing.'
    
    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--org',
            type=str,
            help='Organization name or DDO code to seed data for (optional).'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing revenue data before seeding.'
        )
    
    @transaction.atomic
    def handle(self, *args, **options) -> None:
        self.stdout.write(self.style.NOTICE('Starting revenue seed...'))
        
        # Get or create organization
        org = self._get_or_create_organization(options.get('org'))
        
        if options.get('clear'):
            self._clear_data(org)
        
        # Step 1: Ensure AR system head exists
        self._create_ar_system_head()
        
        # Step 2: Create revenue budget heads
        revenue_heads = self._create_revenue_heads()
        
        # Step 3: Get or create fiscal year (current operating year)
        fiscal_year = self._get_current_fiscal_year(org)
        
        # Step 4: Create payers
        payers = self._create_payers(org)
        
        # Step 5: Create sample demands
        demands = self._create_sample_demands(org, fiscal_year, payers, revenue_heads)
        
        self.stdout.write(self.style.SUCCESS(
            '\n✓ Revenue seed completed successfully!\n'
            f'  Organization: {org.name}\n'
            f'  Fiscal Year: {fiscal_year.year_name}\n'
            f'  Payers: {len(payers)}\n'
            f'  Revenue Heads: {len(revenue_heads)}\n'
            f'  Sample Demands: {len(demands)}'
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
            raise CommandError(
                "No active organization found. Run 'seed_expenditure' first or provide --org."
            )
        
        return org
    
    def _clear_data(self, org: Organization) -> None:
        """Clear existing revenue data for the organization."""
        self.stdout.write('  Clearing existing revenue data...')
        
        RevenueCollection.objects.filter(organization=org).delete()
        RevenueDemand.objects.filter(organization=org).delete()
        Payer.objects.filter(organization=org).delete()
        
        self.stdout.write(self.style.WARNING('  Existing revenue data cleared.'))
    
    def _create_ar_system_head(self) -> BudgetHead:
        """Create the Accounts Receivable system head."""
        self.stdout.write('  Creating AR system head...')
        
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
        
        # Create Master Data for AR (A01001)
        # Note: A01 is normally Employee Expenses, but legacy seed used A01001 for AR.
        # Look up AR by system_code since assign_system_codes already created it
        gh = GlobalHead.objects.filter(system_code='AR').first()
        if not gh:
            # Fallback: create if not exists
            major, _ = MajorHead.objects.get_or_create(
                code='A01', 
                defaults={'name': 'Employees Related Expenses'}
            )
            minor, _ = MinorHead.objects.get_or_create(
                code='A010', 
                major=major, 
                defaults={'name': 'Basic Pay'}
            )
            gh, _ = GlobalHead.objects.get_or_create(
                code='A01001', 
                minor=minor, 
                defaults={
                    'name': 'Accounts Receivable', 
                    'account_type': AccountType.ASSET, 
                    'system_code': 'AR'
                }
            )
        
        ar_head, created = BudgetHead.objects.get_or_create(
            global_head=gh,
            fund=fund,
            defaults={
                'function': func,
                'budget_control': False,
                'posting_allowed': True,
            }
        )
        
        if created:
            self.stdout.write(f'    ✓ Created: {ar_head.code} - {ar_head.name}')
        else:
            self.stdout.write(f'    ✓ Exists: {ar_head.code} - {ar_head.name}')
        
        return ar_head
    
    def _create_revenue_heads(self) -> List[BudgetHead]:
        """Create sample revenue budget heads."""
        self.stdout.write('  Creating revenue budget heads...')
        
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
        
        revenue_heads_data = [
            {'code': 'C03801', 'name': 'Rent of Immovable Property', 'minor_name': 'Rent from Building & Land'},
            {'code': 'C02813', 'name': 'Education Fee', 'minor_name': 'Education'},
            {'code': 'C04001', 'name': 'Water Rates', 'minor_name': 'Economic Services Receipts'},
        ]
        
        created_heads = []
        for data in revenue_heads_data:
            code = data['code']
            major_code = code[:3]
            minor_code = code[:4]
            
            # Create Master Data
            major, _ = MajorHead.objects.get_or_create(
                code=major_code,
                defaults={'name': f"Major Head {major_code}"}
            )
            minor, _ = MinorHead.objects.get_or_create(
                code=minor_code,
                major=major,
                defaults={'name': data.get('minor_name', f"Minor Head {minor_code}")}
            )
            gh, _ = GlobalHead.objects.get_or_create(
                code=code,
                minor=minor,
                defaults={'name': data['name'], 'account_type': AccountType.REVENUE}
            )
            
            head, created = BudgetHead.objects.get_or_create(
                global_head=gh,
                fund=fund,
                defaults={
                    'function': func,
                    'budget_control': False,
                    'posting_allowed': True,
                }
            )
            created_heads.append(head)
            if created:
                self.stdout.write(f'    ✓ Created: {head.code} - {head.name}')
            else:
                self.stdout.write(f'    ✓ Exists: {head.code} - {head.name}')
        
        return created_heads
    
    def _get_current_fiscal_year(self, org: Organization) -> FiscalYear:
        """Get the current operating fiscal year."""
        fiscal_year = FiscalYear.get_current_operating_year(org)
        
        if not fiscal_year:
            raise CommandError(
                "No fiscal year found for current date. Create a fiscal year first."
            )
        
        self.stdout.write(f'  Using fiscal year: {fiscal_year.year_name}')
        return fiscal_year
    
    def _create_payers(self, org: Organization) -> List[Payer]:
        """Create sample payers."""
        self.stdout.write('  Creating payers...')
        
        payers_data = [
            {
                'name': 'Ahmed Khan',
                'cnic_ntn': '17301-1234567-1',
                'contact_no': '0333-1234567',
                'address': 'Shop #1, Main Bazaar, Mardan',
            },
            {
                'name': 'Mohammad Ali Traders',
                'cnic_ntn': '1234567',  # NTN
                'contact_no': '0321-9876543',
                'address': '15-A Industrial Area, Peshawar',
            },
            {
                'name': 'Fatima Bibi',
                'cnic_ntn': '17301-7654321-2',
                'contact_no': '0345-5555555',
                'address': 'House #45, Gulberg Colony, Mardan',
            },
            {
                'name': 'Khyber Enterprises',
                'cnic_ntn': '7654321',  # NTN
                'contact_no': '0301-1112233',
                'address': 'Shop #10, Commercial Plaza, Swat',
            },
            {
                'name': 'Syed Zahir Shah',
                'cnic_ntn': '17301-9999999-1',
                'contact_no': '0312-4567890',
                'address': 'Mohalla Sadat, Tehsil Mardan',
            },
        ]
        
        created_payers = []
        for payer_data in payers_data:
            payer, created = Payer.objects.get_or_create(
                organization=org,
                name=payer_data['name'],
                defaults={
                    **payer_data,
                    'is_active': True,
                }
            )
            created_payers.append(payer)
            if created:
                self.stdout.write(f'    ✓ Created: {payer.name}')
            else:
                self.stdout.write(f'    ✓ Exists: {payer.name}')
        
        return created_payers
    
    def _create_sample_demands(
        self,
        org: Organization,
        fiscal_year: FiscalYear,
        payers: List[Payer],
        revenue_heads: List[BudgetHead]
    ) -> List[RevenueDemand]:
        """Create sample revenue demands."""
        self.stdout.write('  Creating sample demands...')
        
        today = date.today()
        
        demands_data = [
            {
                'payer': payers[0],  # Ahmed Khan
                'budget_head': revenue_heads[0],  # Shop Rent
                'amount': Decimal('25000.00'),
                'period_description': 'July 2025 Rent',
                'description': 'Monthly shop rent for Shop #1 - July 2025',
                'issue_date': today - timedelta(days=30),
                'due_date': today - timedelta(days=15),
                'status': DemandStatus.DRAFT,
            },
            {
                'payer': payers[1],  # Mohammad Ali Traders
                'budget_head': revenue_heads[0],  # Shop Rent
                'amount': Decimal('50000.00'),
                'period_description': 'Q3 2025 Rent',
                'description': 'Quarterly shop rent - Industrial Area',
                'issue_date': today - timedelta(days=45),
                'due_date': today - timedelta(days=10),
                'status': DemandStatus.DRAFT,
            },
            {
                'payer': payers[2],  # Fatima Bibi
                'budget_head': revenue_heads[1],  # Education Fee
                'amount': Decimal('5000.00'),
                'period_description': 'School Year 2025-26',
                'description': 'School fee for Municipal School admission',
                'issue_date': today - timedelta(days=20),
                'due_date': today + timedelta(days=10),
                'status': DemandStatus.DRAFT,
            },
        ]
        
        created_demands = []
        for i, demand_data in enumerate(demands_data, start=1):
            # Generate challan number
            challan_no = f"CHN-{fiscal_year.year_name.split('-')[0][-2:]}{i:04d}"
            
            demand, created = RevenueDemand.objects.get_or_create(
                organization=org,
                fiscal_year=fiscal_year,
                payer=demand_data['payer'],
                budget_head=demand_data['budget_head'],
                amount=demand_data['amount'],
                defaults={
                    'challan_no': challan_no,
                    'description': demand_data['description'],
                    'period_description': demand_data.get('period_description', ''),
                    'issue_date': demand_data['issue_date'],
                    'due_date': demand_data['due_date'],
                    'status': demand_data['status'],
                }
            )
            created_demands.append(demand)
            if created:
                self.stdout.write(
                    f'    ✓ Created: {demand.challan_no} - {demand.payer.name} - Rs. {demand.amount}'
                )
            else:
                self.stdout.write(
                    f'    ✓ Exists: {demand.challan_no} - {demand.payer.name} - Rs. {demand.amount}'
                )
        
        return created_demands
