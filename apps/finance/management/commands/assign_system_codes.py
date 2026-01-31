import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.finance.models import MajorHead, MinorHead, GlobalHead, SystemCode, AccountType

class Command(BaseCommand):
    help = 'Ensures required Global Heads exist and assigns System Codes to them.'

    def handle(self, *args, **options):
        self.stdout.write("Checking and assigning System Codes...")
        
        # Define the required system accounts
        # Format: (SystemCode Enum, PIFRA Code, Name, Major Code, Major Name, Minor Code, Minor Name, Account Type)
        REQUIRED_ACCOUNTS = [
            (
                SystemCode.SYS_SUSPENSE, 'G05101', 'Suspense Account',
                'G05', 'Suspense & Clearing',
                'G051', 'Suspense',
                AccountType.LIABILITY
            ),
            (
                SystemCode.CLEARING_CHQ, 'G01101', 'Cheque Clearing Account',
                'G01', 'Current Liabilities',
                'G011', 'Cheques Payable',
                AccountType.LIABILITY
            ),
            (
                SystemCode.CLEARING_IT, 'G01140', 'Income Tax Payable',
                'G01', 'Current Liabilities',
                'G011', 'Tax Payables', # Re-using minor code prefix but ensuring existence
                AccountType.LIABILITY
            ),
            (
                SystemCode.CLEARING_GST, 'G01145', 'Sales Tax Payable',
                'G01', 'Current Liabilities',
                'G011', 'Tax Payables',
                AccountType.LIABILITY
            ),
            (
                SystemCode.CLEARING_SEC, 'G01190', 'Security / Retention Money',
                'G01', 'Current Liabilities',
                'G011', 'Deposits',
                AccountType.LIABILITY
            ),
            (
                SystemCode.AR, 'F01101', 'Accounts Receivable',
                'F01', 'Current Assets',
                'F011', 'Receivables',
                AccountType.ASSET
            ),
        ]

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for sys_code, gh_code, gh_name, maj_code, maj_name, min_code, min_name, acc_type in REQUIRED_ACCOUNTS:
                
                # 1. Ensure Major Head exists
                major, _ = MajorHead.objects.get_or_create(
                    code=maj_code,
                    defaults={'name': maj_name}
                )

                # 2. Ensure Minor Head exists
                minor, _ = MinorHead.objects.get_or_create(
                    code=min_code,
                    defaults={
                        'name': min_name,
                        'major': major
                    }
                )

                # 3. Ensure Global Head exists or Update it
                global_head, created = GlobalHead.objects.get_or_create(
                    code=gh_code,
                    defaults={
                        'name': gh_name,
                        'minor': minor,
                        'account_type': acc_type,
                        'system_code': sys_code
                    }
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(f"Created: {gh_code} - {gh_name} ({sys_code})"))
                    created_count += 1
                else:
                    # Update system code if missing or different
                    if global_head.system_code != sys_code:
                        global_head.system_code = sys_code
                        # Also update name/minor if needed? strict PIFRA might say no, but for system fix-up yes.
                        # Let's simple check strictness: if it exists, we just TAG it. 
                        # We don't overwrite name/minor to avoid messing up existing manual setups 
                        # unless it's clearly wrong/empty. 
                        global_head.save()
                        self.stdout.write(self.style.WARNING(f"Updated: {gh_code} assigned to {sys_code}"))
                        updated_count += 1
                    else:
                        self.stdout.write(f"Verified: {gh_code} is {sys_code}")

        self.stdout.write(self.style.SUCCESS(f"\nDone. Created: {created_count}, Updated: {updated_count}"))
