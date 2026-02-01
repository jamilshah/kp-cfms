
import os
import django
import sys

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.models import Bill, BillStatus
from apps.users.models import CustomUser

def debug_approval_access():
    print("--- Debugging TMO Approval Access ---")
    
    # 1. Get the latest modified bill
    bill = Bill.objects.order_by('-updated_at').first()
    if not bill:
        print("No bills found.")
        return
        
    print(f"\nTarget Bill #{bill.id}:")
    print(f"  Status: {bill.status} (Raw: '{bill.status}')")
    print(f"  Payee: {bill.payee.name}")
    print(f"  Verified Status Expected: {BillStatus.VERIFIED}")
    
    # 2. Find a TMO user
    tmo = CustomUser.objects.filter(roles__code='TMO').first()
    if not tmo:
        print("\nNo TMO user found!")
        # Try finding superuser
        tmo = CustomUser.objects.filter(is_superuser=True).first()
        print(f"Using Superuser: {tmo}")
    else:
        print(f"\nTesting with TMO User: {tmo.get_full_name()} ({tmo.email})")

    # 3. Simulate View Logic
    print("\nChecking Permissions:")
    is_approver = tmo.is_approver()
    is_superuser = tmo.is_superuser
    
    can_approve = (
        bill.status == BillStatus.VERIFIED and
        (is_approver or is_superuser)
    )
    
    print(f"  bill.status == BillStatus.VERIFIED: {bill.status == BillStatus.VERIFIED}")
    print(f"  user.is_approver(): {is_approver}")
    print(f"  user.is_superuser: {is_superuser}")
    print(f"  RESULT -> can_approve: {can_approve}")

    if not can_approve:
        print("\nFAILURE ANALYSIS:")
        if bill.status != BillStatus.VERIFIED:
            print("  -> Failed because bill is not VERIFIED.")
            print(f"     It is currently '{bill.status}'. Did the accountant verification step work?")
        if not (is_approver or is_superuser):
            print("  -> Failed because user is not an Approver/TMO.")

if __name__ == '__main__':
    debug_approval_access()
