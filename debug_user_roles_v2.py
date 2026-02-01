
import os
import django
import sys

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import CustomUser

def check_user_roles(name_fragment):
    print(f"--- Checking Roles for User: {name_fragment} ---")
    
    users = CustomUser.objects.filter(first_name__icontains=name_fragment) | CustomUser.objects.filter(last_name__icontains=name_fragment)
    
    if not users.exists():
        print("No user found.")
        return

    for user in users:
        print(f"\nUser: {user.get_full_name()} ({user.email})")
        print(f"  Legacy Role Field: {user.role}")
        print("  RBAC Roles:")
        for role in user.roles.all():
            print(f"    - {role.name} ({role.code})")
            
        print(f"  is_checker(): {user.is_checker()}")
        print(f"  is_approver(): {user.is_approver()}")
        print(f"  is_superuser: {user.is_superuser}")

if __name__ == '__main__':
    check_user_roles('Naseer')
