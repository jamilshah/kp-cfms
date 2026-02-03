"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to create BudgetHeads for system-coded GlobalHeads
-------------------------------------------------------------------------
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.finance.models import BudgetHead, GlobalHead, Fund, FunctionCode, SystemCode


class Command(BaseCommand):
    help = 'Creates BudgetHeads for all system-coded GlobalHeads'

    def handle(self, *args, **options):
        self.stdout.write("Creating BudgetHeads for System Codes...")
        self.stdout.write("=" * 80)
        
        # Get default fund and function
        fund = Fund.objects.filter(is_active=True).first()
        if not fund:
            self.stdout.write(self.style.ERROR("No active Fund found. Please create a Fund first."))
            return
        
        function = FunctionCode.objects.filter(is_active=True).first()
        if not function:
            self.stdout.write(self.style.ERROR("No active FunctionCode found. Please create a FunctionCode first."))
            return
        
        self.stdout.write(f"Using Fund: {fund.code} - {fund.name}")
        self.stdout.write(f"Using Function: {function.code} - {function.name}")
        self.stdout.write("-" * 80)
        
        created_count = 0
        skipped_count = 0
        
        # Get all tagged GlobalHeads
        tagged_heads = GlobalHead.objects.filter(system_code__isnull=False)
        
        with transaction.atomic():
            for gh in tagged_heads:
                # Check if BudgetHead already exists
                existing = BudgetHead.objects.filter(
                    fund=fund,
                    function=function,
                    global_head=gh
                ).first()
                
                if existing:
                    self.stdout.write(f"[SKIP] {gh.code} - Already has BudgetHead")
                    skipped_count += 1
                    continue
                
                # Create BudgetHead
                budget_head = BudgetHead.objects.create(
                    fund=fund,
                    function=function,
                    global_head=gh,
                    is_active=True
                )

                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[OK] Created BudgetHead: {gh.code} - {gh.name} ({gh.system_code})"
                    )
                )
                created_count += 1
        
        # Summary
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("SUMMARY:"))
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write(self.style.SUCCESS("\n[OK] BudgetHead creation complete!"))
