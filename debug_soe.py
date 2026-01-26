import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import ScheduleOfEstablishment, FiscalYear, PostType, EstablishmentStatus, ApprovalStatus
from apps.finance.models import BudgetHead
from apps.core.models import Organization

def debug():
    print("Debugging ScheduleOfEstablishment creation...")
    
    fy = FiscalYear.objects.filter(year_name="2026-27").first()
    if not fy:
        print("Fiscal Year 2026-27 not found!")
        return
        
    salary_head = BudgetHead.objects.filter(pifra_object__startswith='A01', is_active=True).first()
    if not salary_head:
        print("Salary Head not found!")
        # Use any head
        salary_head = BudgetHead.objects.first()

    department = "Sanitation"
    designation = "Sanitary Inspector Debug"
    bps = 14
    post_type = PostType.LOCAL  # Testing LOCAL
    
    print(f"Attempting to create: {designation} ({post_type})")
    
    try:
        obj, created = ScheduleOfEstablishment.objects.get_or_create(
            fiscal_year=fy,
            department=department,
            designation_name=designation,
            bps_scale=bps,
            defaults={
                'post_type': post_type,
                'sanctioned_posts': 1,
                'occupied_posts': 0,
                'annual_salary': Decimal('300000'),
                'budget_head': salary_head,
                'establishment_status': EstablishmentStatus.SANCTIONED,
                'approval_status': ApprovalStatus.DRAFT,
            }
        )
        print(f"Success! Created: {created}, ID: {obj.id}")
        
    except Exception as e:
        print(f"Failed with error: {e}")
        # Print full traceback
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug()
