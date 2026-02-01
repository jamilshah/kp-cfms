import os
import django
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import Voucher, JournalEntry, BankStatement, BankStatementLine
from apps.expenditure.models import Bill, Payment

def cleanup_transactions():
    print("--- STARTING TRANSACTION CLEANUP ---")
    
    # Order matters for foreign keys if not using CASCADE, but delete() handles it
    
    # 1. Expenditure
    print(f"Deleting {Payment.objects.count()} Payments...")
    Payment.objects.all().delete()
    
    print(f"Deleting {Bill.objects.count()} Bills...")
    Bill.objects.all().delete()
    
    # 2. Bank Reconciliation (Test statements)
    print(f"Deleting {BankStatement.objects.count()} Bank Statements...")
    BankStatement.objects.all().delete() # This should cascade to lines
    
    # 3. Finance / Ledger
    print(f"Deleting {Voucher.objects.count()} Vouchers...")
    # JournalEntry usually CASCADE deletes with Voucher
    Voucher.objects.all().delete()
    
    # Double check JournalEntries (orphans if any)
    orphans = JournalEntry.objects.count()
    if orphans > 0:
        print(f"Deleting {orphans} orphaned Journal Entries...")
        JournalEntry.objects.all().delete()

    print("\n--- CLEANUP COMPLETE ---")
    print(f"Vouchers remaining: {Voucher.objects.count()}")
    print(f"Bills remaining: {Bill.objects.count()}")

if __name__ == "__main__":
    cleanup_transactions()
