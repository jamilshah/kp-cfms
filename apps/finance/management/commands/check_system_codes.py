"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Management command to verify system code configuration and 
             show diagnostic information.
-------------------------------------------------------------------------
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from apps.finance.models import GlobalHead, BudgetHead, SystemCode


class Command(BaseCommand):
    help = 'Verify system code configuration and show diagnostic information.'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("SYSTEM CODE CONFIGURATION CHECK"))
        self.stdout.write("=" * 80)
        
        # Check GlobalHead system codes
        self.stdout.write("\n" + self.style.WARNING("1. GlobalHead System Codes:"))
        self.stdout.write("-" * 80)
        
        all_codes = [choice[0] for choice in SystemCode.choices]
        
        for code in all_codes:
            gh = GlobalHead.objects.filter(system_code=code).first()
            if gh:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ {code:20} → {gh.code:10} {gh.name[:50]}")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ {code:20} → NOT CONFIGURED")
                )
        
        # Check BudgetHead mappings
        self.stdout.write("\n" + self.style.WARNING("2. BudgetHead Mappings (for GL automation):"))
        self.stdout.write("-" * 80)
        
        critical_codes = [SystemCode.AP, SystemCode.AR, SystemCode.TAX_IT, SystemCode.TAX_GST]
        
        for code in critical_codes:
            budget_heads = BudgetHead.objects.filter(
                global_head__system_code=code,
                is_active=True
            )
            
            count = budget_heads.count()
            if count > 0:
                bh = budget_heads.first()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {code:20} → {count} BudgetHead(s) configured "
                        f"(Fund: {bh.fund.code}, Function: {bh.function.code})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ {code:20} → NO BUDGET HEAD CONFIGURED "
                        f"(GL automation will fail!)"
                    )
                )
        
        # Summary statistics
        self.stdout.write("\n" + self.style.WARNING("3. Summary Statistics:"))
        self.stdout.write("-" * 80)
        
        total_system_codes = len(all_codes)
        configured_global = GlobalHead.objects.filter(system_code__isnull=False).count()
        configured_budget = BudgetHead.objects.filter(
            global_head__system_code__isnull=False
        ).count()
        
        self.stdout.write(f"  Total System Codes Defined:       {total_system_codes}")
        self.stdout.write(f"  GlobalHeads with System Code:     {configured_global}")
        self.stdout.write(f"  BudgetHeads with System Code:     {configured_budget}")
        
        # Recommendations
        self.stdout.write("\n" + self.style.WARNING("4. Recommendations:"))
        self.stdout.write("-" * 80)
        
        if configured_global < total_system_codes:
            self.stdout.write(
                self.style.ERROR(
                    "  ⚠ Run: python manage.py assign_system_codes"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "  ✓ All GlobalHead system codes configured"
                )
            )
        
        missing_critical = []
        for code in critical_codes:
            if not BudgetHead.objects.filter(
                global_head__system_code=code,
                is_active=True
            ).exists():
                missing_critical.append(code)
        
        if missing_critical:
            self.stdout.write(
                self.style.ERROR(
                    f"  ⚠ Create BudgetHeads for: {', '.join(missing_critical)}"
                )
            )
            self.stdout.write(
                "    These are required for Bill/Payment/Revenue workflows."
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "  ✓ All critical BudgetHeads configured"
                )
            )
        
        self.stdout.write("\n" + "=" * 80)
        
        if configured_global == total_system_codes and not missing_critical:
            self.stdout.write(
                self.style.SUCCESS("✓ System code configuration is COMPLETE!")
            )
        else:
            self.stdout.write(
                self.style.ERROR("✗ System code configuration is INCOMPLETE!")
            )
        
        self.stdout.write("=" * 80)
