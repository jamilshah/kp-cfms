"""
Management command to create initial tax rate configuration.

Creates a default tax rate configuration for Tax Year 2025-26
with current FBR/KPRA rates.

Usage:
    python manage.py seed_tax_rates
"""
from django.core.management.base import BaseCommand
from decimal import Decimal
from datetime import date
from apps.expenditure.models_tax_config import TaxRateConfiguration


class Command(BaseCommand):
    help = 'Create initial tax rate configuration for Tax Year 2025-26'

    def handle(self, *args, **options):
        self.stdout.write('Creating initial tax rate configuration...')
        
        # Check if configuration already exists
        existing = TaxRateConfiguration.objects.filter(tax_year='2025-26').first()
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f'Tax rate configuration for 2025-26 already exists (ID: {existing.id}). '
                    f'Status: {"Active" if existing.is_active else "Inactive"}'
                )
            )
            return
        
        # Create new configuration
        config = TaxRateConfiguration.objects.create(
            tax_year='2025-26',
            effective_from=date(2025, 7, 1),
            effective_to=date(2026, 6, 30),
            is_active=True,
            
            # Income Tax Rates - Goods (Section 153)
            goods_filer_company=Decimal('0.0500'),        # 5.0%
            goods_filer_individual=Decimal('0.0550'),     # 5.5%
            goods_nonfiler_company=Decimal('0.1000'),     # 10%
            goods_nonfiler_individual=Decimal('0.1100'),  # 11%
            
            # Income Tax Rates - Services
            services_filer=Decimal('0.1500'),             # 15%
            services_nonfiler=Decimal('0.3000'),          # 30%
            
            # Income Tax Rates - Works Contracts
            works_filer_company=Decimal('0.0750'),        # 7.5%
            works_filer_individual=Decimal('0.0800'),     # 8.0%
            works_nonfiler_company=Decimal('0.1500'),     # 15%
            works_nonfiler_individual=Decimal('0.1600'),  # 16%
            
            # Sales Tax Withholding Rates
            sales_tax_goods_filer=Decimal('0.2000'),      # 20% (1/5th)
            sales_tax_goods_nonfiler=Decimal('1.0000'),   # 100% (whole)
            sales_tax_services_filer=Decimal('0.5000'),   # 50%
            sales_tax_services_nonfiler=Decimal('1.0000'), # 100%
            sales_tax_works=Decimal('1.0000'),            # 100% (always)
            
            # Other Rates
            stamp_duty_rate=Decimal('0.0100'),            # 1%
            standard_sales_tax_rate=Decimal('0.1800'),    # 18%
            
            notes=(
                'Initial tax rate configuration for FY 2025-26. '
                'Rates based on Income Tax Ordinance 2001 (Section 153), '
                'Sales Tax Act 1990, KP Sales Tax on Services Act 2022, '
                'and Stamp Act 1899 (Article 22A). '
                'Created by seed_tax_rates management command.'
            )
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Successfully created tax rate configuration for 2025-26 (ID: {config.id})'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'  Status: Active'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'  Effective: {config.effective_from} to {config.effective_to}'
            )
        )
        self.stdout.write('')
        self.stdout.write('Tax rates configured:')
        self.stdout.write(f'  - Goods (Filer Company): {config.goods_filer_company * 100}%')
        self.stdout.write(f'  - Services (Filer): {config.services_filer * 100}%')
        self.stdout.write(f'  - Works (Filer Company): {config.works_filer_company * 100}%')
        self.stdout.write(f'  - Stamp Duty: {config.stamp_duty_rate * 100}%')
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                'Tax rate configuration is now active and will be used for all tax calculations.'
            )
        )
