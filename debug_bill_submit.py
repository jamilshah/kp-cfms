
import os
import django
import sys
import traceback

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.expenditure.models import Bill
from apps.users.models import CustomUser

def debug_submit():
    print("--- Debugging Bill Submission Error ---")
    
    # 1. Get the problematic bill (ID 9 from user report)
    try:
        bill = Bill.objects.get(pk=9)
        print(f"Found Bill #{bill.id}: {bill}")
    except Bill.DoesNotExist:
        print("Bill #9 not found. Picking last bill.")
        bill = Bill.objects.last()
        if not bill:
            print("No bills found.")
            return

    # 2. Get a user
    user = CustomUser.objects.first()
    if not user:
        print("No user found.")
        return
    print(f"Using User: {user}")

    # Reset to Draft for testing
    if bill.status != 'DRAFT':
        print(f"Resetting bill '{bill.status}' to DRAFT...")
        bill.status = 'DRAFT'
        bill.save()

    # 3. Simulate Submit
    try:
        print("Attempting bill.submit()...")
        bill.submit(user)
        print("Success!")
    except Exception:
        print("\n!!! EXCEPTION CAUGHT !!!")
        traceback.print_exc()

if __name__ == '__main__':
    debug_submit()
