from django.core.management.base import BaseCommand
from apps.finance.models import BudgetHead, FunctionCode, AccountType

class Command(BaseCommand):
    help = 'Seed essential Budget Heads for Salary/Establishment'

    def handle(self, *args, **kwargs):
        # 1. Create Function Code (AD - Administration)
        func, _ = FunctionCode.objects.get_or_create(
            code='AD',
            defaults={'name': 'General Administration', 'description': 'Administration'}
        )
        
        # 2. Budget Heads Data
        heads_data = [
            # Object, Description
            ('A01101', 'Basic Pay of Officers'),
            ('A01151', 'Basic Pay of Other Staff'),
            ('A01201', 'Senior Post Allowance'),
            ('A01202', 'House Rent Allowance'),
            ('A01203', 'Conveyance Allowance'),
            ('A01217', 'Medical Allowance'),
            ('A01270', 'Other Allowances'),
            ('A01274', 'Adhoc Relief 2022'),
            ('A0122R', 'Adhoc Relief 2023'),
            ('A0122Y', 'Adhoc Relief 2024'),
            ('A01', 'Total Employees Related Expenses'), # Fallback
        ]
        
        count = 0
        for code, desc in heads_data:
            obj, created = BudgetHead.objects.get_or_create(
                tma_sub_object=code,
                defaults={
                    'pifra_object': code,
                    'tma_description': desc,
                    'pifra_description': desc,
                    'function': func,
                    'fund_id': 1,
                    'account_type': AccountType.EXPENDITURE,
                    'is_charged': False
                }
            )
            if created:
                count += 1
                self.stdout.write(f"Created {code} - {desc}")
        
        self.stdout.write(self.style.SUCCESS(f"Seeded {count} Budget Heads"))
