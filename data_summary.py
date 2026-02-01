import os
import django
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import Voucher, JournalEntry, BudgetHead
from apps.expenditure.models import Bill, Payment
from apps.core.models import BankAccount

def count_items():
    print("--- TRANSACTION DATA SUMMARY ---")
    print(f"Vouchers: {Voucher.objects.count()}")
    print(f"Journal Entries: {JournalEntry.objects.count()}")
    print(f"Bills: {Bill.objects.count()}")
    print(f"Payments: {Payment.objects.count()}")
    
    print("\n--- MASTER DATA SUMMARY ---")
    print(f"Bank Accounts: {BankAccount.objects.count()}")
    print(f"Budget Heads (Allocations/Account Links): {BudgetHead.objects.count()}")

if __name__ == "__main__":
    count_items()
