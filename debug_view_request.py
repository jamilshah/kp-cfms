
import os
import django
import sys
from django.test import RequestFactory

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.views import BillDetailView
from apps.expenditure.models import Bill
from apps.users.models import CustomUser

def debug_view_logic():
    print("--- Debugging BillDetailView Logic ---")
    
    # 1. Get Bill and User
    bill = Bill.objects.get(pk=9) # Assuming ID 9 is our target
    tmo = CustomUser.objects.filter(roles__code='TMO').first()
    
    print(f"Simulating request for Bill #{bill.id} ({bill.status}) by User {tmo.get_full_name()}")
    
    # 2. Create Request
    factory = RequestFactory()
    request = factory.get(f'/expenditure/bills/{bill.id}/')
    request.user = tmo
    
    # 3. Instantiate View
    view = BillDetailView()
    view.request = request
    view.object = bill
    view.kwargs = {'pk': bill.id}
    
    # 4. Call get_context_data
    # This should trigger our print statements
    context = view.get_context_data()
    
    print("\n--- Context Results ---")
    print(f"can_approve: {context.get('can_approve')}")
    print(f"can_verify: {context.get('can_verify')}")

if __name__ == '__main__':
    debug_view_logic()
