"""
Tax Withholding Smoke Test

Verifies that the tax calculation engine works correctly with the active
tax rate configuration.
"""
import logging
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.expenditure.models_tax_config import TaxRateConfiguration
from apps.expenditure.services_tax import TaxCalculator
from apps.expenditure.models import Payee, Bill, PayeeTaxStatus, PayeeEntityType, TransactionType

class Command(BaseCommand):
    help = 'Smoke test for Tax Withholding System logic'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== TAX WITHHOLDING SMOKE TEST ===\n'))
        
        # 1. Check Active Configuration
        self.stdout.write('1. Checking Tax Rate Configuration...')
        config = TaxRateConfiguration.get_active_config()
        
        if not config:
            self.stdout.write(self.style.WARNING('   ⚠ No active configuration found.'))
            self.stdout.write('   Run: python manage.py seed_tax_rates')
            return
        else:
            self.stdout.write(self.style.SUCCESS(f'   ✓ Active configuration: {config.tax_year}'))
            self.stdout.write(f'     Effective: {config.effective_from} to {config.effective_to or "Indefinite"}')

        # 2. Initialize Calculator
        self.stdout.write('\n2. Initializing Tax Calculator...')
        try:
            calculator = TaxCalculator()
            self.stdout.write(self.style.SUCCESS('   ✓ Calculator initialized with active config'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Failed to initialize: {e}'))
            return

        # 3. Create Test Payees
        self.stdout.write('\n3. Creating Test Payees...')
        test_payees = []
        
        try:
            # Filer Company
            payee1, _ = Payee.objects.get_or_create(
                name='Test Vendor - Filer Company',
                defaults={
                    'tax_status': PayeeTaxStatus.ACTIVE_FILER,
                    'entity_type': PayeeEntityType.COMPANY,
                    'cnic_ntn': '1234567-8'  # NTN format
                }
            )
            test_payees.append(('Filer Company', payee1))
            
            # Non-Filer Individual
            payee2, _ = Payee.objects.get_or_create(
                name='Test Vendor - Non-Filer Individual',
                defaults={
                    'tax_status': PayeeTaxStatus.NON_FILER,
                    'entity_type': PayeeEntityType.INDIVIDUAL,
                    'cnic_ntn': '12345-1234567-1'  # CNIC format
                }
            )
            test_payees.append(('Non-Filer Individual', payee2))
            
            self.stdout.write(self.style.SUCCESS(f'   ✓ Created {len(test_payees)} test payees'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Failed to create payees: {e}'))
            return

        # 4. Test Scenarios
        self.stdout.write('\n4. Running Tax Calculation Tests...')
        
        scenarios = [
            {
                'name': 'Goods Supply - Filer Company',
                'payee': payee1,
                'transaction_type': TransactionType.GOODS,
                'gross_amount': Decimal('100000.00'),
                'sales_tax_invoice': Decimal('18000.00'),
                'expected_it_rate': config.goods_filer_company,
                'expected_st_rate': config.sales_tax_goods_filer
            },
            {
                'name': 'Services - Non-Filer Individual',
                'payee': payee2,
                'transaction_type': TransactionType.SERVICES,
                'gross_amount': Decimal('50000.00'),
                'sales_tax_invoice': None,  # Will use standard 18%
                'expected_it_rate': config.services_nonfiler,
                'expected_st_rate': config.sales_tax_services_nonfiler
            },
            {
                'name': 'Works Contract - Filer Company',
                'payee': payee1,
                'transaction_type': TransactionType.WORKS,
                'gross_amount': Decimal('200000.00'),
                'sales_tax_invoice': Decimal('36000.00'),
                'expected_it_rate': config.works_filer_company,
                'expected_st_rate': config.sales_tax_works
            }
        ]

        failures = 0
        for sc in scenarios:
            self.stdout.write(f'\n   Testing: {sc["name"]}')
            self.stdout.write(f'   Gross Amount: Rs {sc["gross_amount"]:,.2f}')
            
            # Create temporary bill
            bill = Bill(
                payee=sc['payee'],
                transaction_type=sc['transaction_type'],
                gross_amount=sc['gross_amount']
            )
            
            try:
                # Calculate taxes
                result = calculator.calculate_taxes(
                    bill=bill,
                    sales_tax_invoice_amount=sc['sales_tax_invoice']
                )
                
                # Calculate expected values
                expected_it = sc['gross_amount'] * sc['expected_it_rate']
                
                if sc['sales_tax_invoice']:
                    expected_st = sc['sales_tax_invoice'] * sc['expected_st_rate']
                else:
                    # Standard 18% sales tax
                    expected_st = (sc['gross_amount'] * config.standard_sales_tax_rate) * sc['expected_st_rate']
                
                expected_stamp = Decimal('0.00')
                if sc['transaction_type'] == TransactionType.WORKS:
                    expected_stamp = sc['gross_amount'] * config.stamp_duty_rate
                
                # Verify results
                it_match = abs(result['income_tax'] - expected_it) < Decimal('0.01')
                st_match = abs(result['sales_tax'] - expected_st) < Decimal('0.01')
                stamp_match = abs(result['stamp_duty'] - expected_stamp) < Decimal('0.01')
                
                if it_match and st_match and stamp_match:
                    self.stdout.write(self.style.SUCCESS('   ✓ PASS'))
                    self.stdout.write(f'     Income Tax: Rs {result["income_tax"]:,.2f} ({sc["expected_it_rate"]:.2%})')
                    self.stdout.write(f'     Sales Tax WH: Rs {result["sales_tax"]:,.2f}')
                    if result['stamp_duty'] > 0:
                        self.stdout.write(f'     Stamp Duty: Rs {result["stamp_duty"]:,.2f}')
                    self.stdout.write(f'     Total Tax: Rs {result["total_tax"]:,.2f}')
                    self.stdout.write(f'     Net Payable: Rs {result["net_amount"]:,.2f}')
                else:
                    self.stdout.write(self.style.ERROR('   ✗ FAIL - Calculation mismatch'))
                    if not it_match:
                        self.stdout.write(f'     Income Tax: Expected Rs {expected_it:,.2f}, Got Rs {result["income_tax"]:,.2f}')
                    if not st_match:
                        self.stdout.write(f'     Sales Tax: Expected Rs {expected_st:,.2f}, Got Rs {result["sales_tax"]:,.2f}')
                    if not stamp_match:
                        self.stdout.write(f'     Stamp Duty: Expected Rs {expected_stamp:,.2f}, Got Rs {result["stamp_duty"]:,.2f}')
                    failures += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ✗ FAIL - Exception: {e}'))
                failures += 1

        # 5. Summary
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== TEST SUMMARY ==='))
        total_tests = len(scenarios)
        passed = total_tests - failures
        
        if failures == 0:
            self.stdout.write(self.style.SUCCESS(f'✓ ALL {total_tests} TESTS PASSED'))
            self.stdout.write('\nTax withholding system is working correctly! 🎉')
        else:
            self.stdout.write(self.style.ERROR(f'✗ {failures}/{total_tests} TESTS FAILED'))
            self.stdout.write('\nPlease review the tax configuration and calculation logic.')
        
        self.stdout.write('')
