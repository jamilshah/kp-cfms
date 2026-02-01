
import os
import django
import sys

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import CustomUser

def check_roles():
    print("--- Debugging User Roles ---")
    
    # Get the user "Accountant (Verifier)" - presumably the one who was logged in
    # or just list all users to find them
    users = CustomUser.objects.all()
    
    for user in users:
        print(f"\nUser: {user.get_full_name()} ({user.cnic})")
        print(f"Legacy 'role' field: {user.role}")
        
        roles = user.roles.all()
        print(f"New 'roles' M2M: {[r.name + ' (' + r.code + ')' for r in roles]}")
        
        print(f"is_checker: {user.is_checker()}")
        print(f"is_approver: {user.is_approver()}")
        print(f"is_finance_officer: {user.is_finance_officer()}")

if __name__ == '__main__':
    check_roles()
