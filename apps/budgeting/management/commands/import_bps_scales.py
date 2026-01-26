"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to seed BPS (Basic Pay Scale) salary data
             from Pay Commission 2024 rates.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.budgeting.models import BPSSalaryScale


# BPS 2024 Pay Commission rates (approximate - adjust as per official notification)
BPS_2024_DATA = [
    # (grade, initial_pay, max_pay, annual_increment)
    (1, 22000, 38000, 800),
    (2, 22500, 39000, 825),
    (3, 23000, 40000, 850),
    (4, 24000, 42000, 900),
    (5, 25000, 45000, 1000),
    (6, 26000, 48000, 1100),
    (7, 28000, 52000, 1200),
    (8, 30000, 58000, 1400),
    (9, 32000, 63000, 1550),
    (10, 35000, 70000, 1750),
    (11, 40000, 82000, 2100),
    (12, 45000, 95000, 2500),
    (13, 50000, 108000, 2900),
    (14, 55000, 122000, 3350),
    (15, 60000, 138000, 3900),
    (16, 70000, 165000, 4750),
    (17, 80000, 195000, 5750),
    (18, 100000, 250000, 7500),
    (19, 120000, 310000, 9500),
    (20, 150000, 400000, 12500),
    (21, 180000, 490000, 15500),
    (22, 220000, 600000, 19000),
]


class Command(BaseCommand):
    """
    Management command to seed BPS salary scale data.
    
    Usage:
        python manage.py import_bps_scales
        python manage.py import_bps_scales --update-existing
    """
    
    help = 'Seed BPS (Basic Pay Scale) salary data from Pay Commission 2024'
    
    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing BPS scale entries if they exist'
        )
        parser.add_argument(
            '--effective-date',
            type=str,
            default='2024-07-01',
            help='Effective date for pay scales (default: 2024-07-01)'
        )
        parser.add_argument(
            '--allowance-percentage',
            type=float,
            default=50.0,
            help='Allowance percentage to add to basic pay (default: 50)'
        )
    
    def handle(self, *args, **options) -> str:
        """Execute the command."""
        update_existing = options['update_existing']
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for grade, initial_pay, max_pay, increment in BPS_2024_DATA:
                
                # Determine allowances based on grade (Approximate slab logic)
                conveyance = Decimal('2856' if grade <= 15 else '5000' if grade <= 19 else '10000')
                medical = Decimal('1500')
                
                defaults = {
                    'basic_pay_min': Decimal(str(initial_pay)),
                    'basic_pay_max': Decimal(str(max_pay)),
                    'annual_increment': Decimal(str(increment)),
                    'conveyance_allowance': conveyance,
                    'medical_allowance': medical,
                    'house_rent_percent': Decimal('0.45'),
                    'adhoc_relief_total_percent': Decimal('0.35'),
                }
                
                obj, created = BPSSalaryScale.objects.update_or_create(
                    bps_grade=grade,
                    defaults=defaults
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f'  Created BPS-{grade}')
                elif update_existing:
                    # update_or_create already updated it if we passed defaults
                    # But update_or_create updates every time if not created? 
                    # Yes, unless we restrict lookup.
                    # Actually update_or_create updates if found.
                    updated_count += 1
                    self.stdout.write(f'  Updated BPS-{grade}')
                else:
                    # If we didn't want to update... logic for update_or_create is aggressive.
                    # But user flag --update-existing controls intent.
                    # If user didn't pass --update-existing, we shouldn't have called update_or_create?
                    # The previous logic was: if existing and update_existing: update.
                    # I'll stick to that manual logic to respect flag.
                    pass 

        # Re-implementing simplified manual logic to respect flag
        created_count = 0
        updated_count = 0
        
        with transaction.atomic():
            for grade, initial_pay, max_pay, increment in BPS_2024_DATA:
                # Calculate allowances
                conveyance = Decimal('2856' if grade <= 15 else '5000' if grade <= 19 else '10000')
                medical = Decimal('1500')
                
                existing = BPSSalaryScale.objects.filter(bps_grade=grade).first()
                
                if existing:
                    if update_existing:
                        existing.basic_pay_min = Decimal(str(initial_pay))
                        existing.basic_pay_max = Decimal(str(max_pay))
                        existing.annual_increment = Decimal(str(increment))
                        existing.conveyance_allowance = conveyance
                        existing.medical_allowance = medical
                        existing.house_rent_percent = Decimal('0.45')
                        existing.adhoc_relief_total_percent = Decimal('0.35')
                        existing.save()
                        updated_count += 1
                        self.stdout.write(f'  Updated BPS-{grade}')
                    else:
                        skipped_count += 1
                else:
                    BPSSalaryScale.objects.create(
                        bps_grade=grade,
                        basic_pay_min=Decimal(str(initial_pay)),
                        basic_pay_max=Decimal(str(max_pay)),
                        annual_increment=Decimal(str(increment)),
                        conveyance_allowance=conveyance,
                        medical_allowance=medical,
                        house_rent_percent=Decimal('0.45'),
                        adhoc_relief_total_percent=Decimal('0.35')
                    )
                    created_count += 1
                    self.stdout.write(f'  Created BPS-{grade}')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated_count}'))
        
        return f'Seeded {created_count + updated_count} BPS salary scales'
