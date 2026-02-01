"""
Test to verify the EmployeeSalaryListView context data generation
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from apps.budgeting.views_employee_salary import EmployeeSalaryListView
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware

# Create a test request
factory = RequestFactory()
request = factory.get('/budgeting/employee-salary/')

# Add session to request
middleware = SessionMiddleware(lambda x: None)
middleware.process_request(request)

# Add user to request (create a test user if needed)
try:
    user = User.objects.first()
    if user:
        request.user = user
    else:
        print("[WARN] No users found in database, creating test scenario without user")
        request.user = None
except:
    print("[WARN] Could not attach user to request")
    request.user = None

print("=" * 80)
print("Testing EmployeeSalaryListView Context Data")
print("=" * 80)

# Instantiate the view
view = EmployeeSalaryListView()
view.request = request
view.object_list = view.get_queryset()

try:
    context = view.get_context_data()
    
    print("\nContext Data Generated Successfully:")
    print(f"  total_employees: {context.get('total_employees', 'N/A')}")
    print(f"  total_monthly_cost: {context.get('total_monthly_cost', 'N/A')}")
    print(f"  total_annual_cost: {context.get('total_annual_cost', 'N/A')}")
    print(f"  total_projected_annual_cost: {context.get('total_projected_annual_cost', 'N/A')}")
    print(f"  total_annual_increase: {context.get('total_annual_increase', 'N/A')}")
    
    print("\n[PASS] View context data generation works correctly!")
    print("=" * 80)
    
except Exception as e:
    print(f"\n[FAIL] Error generating context data:")
    print(f"  {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
