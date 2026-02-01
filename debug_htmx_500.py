
import os
import django
import sys
# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

from apps.users.models import CustomUser
from apps.finance.views import load_budget_heads_options
from apps.budgeting.models import FiscalYear

def reproduce_500():
    print("--- Debugging HTMX 500 Error ---")
    
    # 1. Setup Request
    factory = RequestFactory()
    url = '/finance/ajax/load-budget-heads-options/?function=12&department=1&account_type=EXP'
    request = factory.get(url)
    
    # 2. Setup User (Organization context)
    # We need a user with an organization. Picking the first one found or a specific one.
    user = CustomUser.objects.filter(organization__isnull=False).first()
    if not user:
        print("No user with organization found. Cannot fully reproduce.")
        # Try creating a dummy user structure if needed, or just warn
        request.user = AnonymousUser()
    else:
        print(f"Using User: {user} | Org: {user.organization}")
        request.user = user

    # 3. Call the view function
    try:
        print("Calling load_budget_heads_options...")
        response = load_budget_heads_options(request)
        print(f"Success! Status Code: {response.status_code}")
        print(response.content.decode('utf-8')[:500]) # First 500 chars
    except Exception as e:
        print("\n!!! EXCEPTION CAUGHT !!!")
        print(f"Type: {type(e)}")
        print(f"Message: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    reproduce_500()
