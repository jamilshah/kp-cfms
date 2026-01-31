"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to ensure all System Code tagged Global Heads 
             exist with proper PIFRA codes for automated GL workflows.
-------------------------------------------------------------------------
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.finance.models import MajorHead, MinorHead, GlobalHead, SystemCode, AccountType


class Command(BaseCommand):
    help = 'Ensures all required System Code tagged Global Heads exist for automated GL posting.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created/updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        
        self.stdout.write("Checking and assigning System Codes...")
        self.stdout.write("=" * 80)
        
        # Define the required system accounts
        # Format: (SystemCode Enum, PIFRA Code, Name, Major Code, Major Name, Minor Code, Minor Name, Account Type)
        REQUIRED_ACCOUNTS = [
            # Suspense & Clearing Accounts
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
                SystemCode.CLEARING_IT, 'G01140', 'Income Tax Withheld',
                'G01', 'Current Liabilities',
                'G011', 'Tax Payables',
                AccountType.LIABILITY
            ),
            (
                SystemCode.CLEARING_GST, 'G01145', 'Sales Tax Withheld',
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
            # Accounts Payable & Receivable
            (
                SystemCode.AP, 'G02001', 'Accounts Payable - Creditors',
                'G02', 'Accounts Payable',
                'G020', 'Trade Creditors',
                AccountType.LIABILITY
            ),
            (
                SystemCode.AR, 'F01101', 'Accounts Receivable',
                'F01', 'Current Assets',
                'F011', 'Receivables',
                AccountType.ASSET
            ),
            # Tax Payable Accounts (for expenditure workflow)
            (
                SystemCode.TAX_IT, 'G02101', 'Income Tax Payable',
                'G02', 'Accounts Payable',
                'G021', 'Tax Payables',
                AccountType.LIABILITY
            ),
            (
                SystemCode.TAX_GST, 'G02102', 'GST/Sales Tax Payable',
                'G02', 'Accounts Payable',
                'G021', 'Tax Payables',
                AccountType.LIABILITY
            ),
        ]

        created_count = 0
        updated_count = 0
        verified_count = 0
        errors = []

        if not dry_run:
            transaction_context = transaction.atomic()
        else:
            from contextlib import nullcontext
            transaction_context = nullcontext()

        with transaction_context:
            for sys_code, gh_code, gh_name, maj_code, maj_name, min_code, min_name, acc_type in REQUIRED_ACCOUNTS:
                try:
                    # 1. Ensure Major Head exists
                    if dry_run:
                        major = MajorHead.objects.filter(code=maj_code).first()
                        if not major:
                            self.stdout.write(f"  Would create Major: {maj_code} - {maj_name}")
                        major = MajorHead(code=maj_code, name=maj_name)
                    else:
                        major, maj_created = MajorHead.objects.get_or_create(
                            code=maj_code,
                            defaults={'name': maj_name}
                        )
                        if maj_created:
                            self.stdout.write(f"  Created Major: {maj_code} - {maj_name}")

                    # 2. Ensure Minor Head exists
                    if dry_run:
                        minor = MinorHead.objects.filter(code=min_code).first()
                        if not minor:
                            self.stdout.write(f"  Would create Minor: {min_code} - {min_name}")
                        minor = MinorHead(code=min_code, name=min_name, major=major)
                    else:
                        minor, min_created = MinorHead.objects.get_or_create(
                            code=min_code,
                            defaults={
                                'name': min_name,
                                'major': major
                            }
                        )
                        if min_created:
                            self.stdout.write(f"  Created Minor: {min_code} - {min_name}")

                    # 3. Ensure Global Head exists or Update it
                    if dry_run:
                        global_head = GlobalHead.objects.filter(code=gh_code).first()
                        if not global_head:
                            self.stdout.write(
                                self.style.SUCCESS(f"✓ Would create: {gh_code} - {gh_name} ({sys_code})")
                            )
                            created_count += 1
                        elif global_head.system_code != sys_code:
                            self.stdout.write(
                                self.style.WARNING(f"⚠ Would update: {gh_code} → {sys_code} (currently: {global_head.system_code})")
                            )
                            updated_count += 1
                        else:
                            self.stdout.write(f"✓ Verified: {gh_code} is {sys_code}")
                            verified_count += 1
                    else:
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
                            self.stdout.write(
                                self.style.SUCCESS(f"✓ Created: {gh_code} - {gh_name} ({sys_code})")
                            )
                            created_count += 1
                        else:
                            # Update system code if missing or different
                            if global_head.system_code != sys_code:
                                global_head.system_code = sys_code
                                global_head.save()
                                self.stdout.write(
                                    self.style.WARNING(f"⚠ Updated: {gh_code} → {sys_code}")
                                )
                                updated_count += 1
                            else:
                                self.stdout.write(f"✓ Verified: {gh_code} is {sys_code}")
                                verified_count += 1

                except Exception as e:
                    error_msg = f"Error processing {sys_code} ({gh_code}): {str(e)}"
                    errors.append(error_msg)
                    self.stdout.write(self.style.ERROR(f"✗ {error_msg}"))

        # Summary
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS(f"SUMMARY:"))
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Verified: {verified_count}")
        
        if errors:
            self.stdout.write(self.style.ERROR(f"  Errors: {len(errors)}"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"    - {error}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN COMPLETE - No changes were made"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ All system codes configured successfully!"))
