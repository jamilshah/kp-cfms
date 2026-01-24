import os
import django
import uuid
import sys

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import Division, District, TMA
from apps.finance.models import FunctionCode, BudgetHead
from apps.users.models import CustomUser
from apps.budgeting.models import FiscalYear, BudgetAllocation, ScheduleOfEstablishment, QuarterlyRelease, SAERecord

def populate_uuids(model_class):
    """Populate public_id with unique UUIDs for all records."""
    model_name = model_class.__name__
    count = model_class.objects.count()
    print(f"Populating {model_name} ({count} records)...")
    
    updated = 0
    for obj in model_class.objects.all():
        # Regenerate UUID to ensure uniqueness (vs default reuse)
        obj.public_id = uuid.uuid4()
        obj.save(update_fields=['public_id'])
        updated += 1
        
    print(f"  Updated {updated} records.")

if __name__ == '__main__':
    print("Starting UUID population...")
    
    # Core
    populate_uuids(Division)
    populate_uuids(District)
    populate_uuids(TMA)
    
    # Finance
    populate_uuids(FunctionCode)
    populate_uuids(BudgetHead)
    
    # Users
    populate_uuids(CustomUser)
    
    # Budgeting
    populate_uuids(FiscalYear)
    populate_uuids(BudgetAllocation)
    populate_uuids(ScheduleOfEstablishment)
    populate_uuids(QuarterlyRelease)
    populate_uuids(SAERecord)
    
    print("Done!")
