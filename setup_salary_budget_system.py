"""
Setup Script: Salary Budget Management System

This script sets up the complete salary budget management system
including database migrations and initial data.

Run: python setup_salary_budget_system.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command
from django.db import connection
from decimal import Decimal


def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)


def print_step(step_num, text):
    print(f"\n[Step {step_num}] {text}")
    print("-" * 80)


def main():
    print_header("SALARY BUDGET MANAGEMENT SYSTEM - SETUP")
    print("This script will set up the complete salary budget tracking system")
    print("including database migrations and example data.")
    
    input("\nPress Enter to continue...")
    
    # Step 1: Create migrations
    print_step(1, "Creating database migrations")
    try:
        call_command('makemigrations', 'budgeting', interactive=False)
        print("✓ Migrations created successfully")
    except Exception as e:
        print(f"✗ Migration creation failed: {str(e)}")
        return
    
    # Step 2: Run migrations
    print_step(2, "Running database migrations")
    try:
        call_command('migrate', interactive=False)
        print("✓ Database migrated successfully")
    except Exception as e:
        print(f"✗ Migration failed: {str(e)}")
        return
    
    # Step 3: Verify models
    print_step(3, "Verifying database tables")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name IN (
                    'budgeting_department_salary_budget',
                    'budgeting_salary_bill_consumption'
                )
            """)
            tables = cursor.fetchall()
            
            if len(tables) == 2:
                print("✓ All required tables created:")
                for table in tables:
                    print(f"  - {table[0]}")
            else:
                print(f"✗ Expected 2 tables, found {len(tables)}")
    except Exception as e:
        print(f"✗ Verification failed: {str(e)}")
    
    # Step 4: Import Chart of Accounts (if not done)
    print_step(4, "Checking Chart of Accounts")
    try:
        from apps.finance.models import GlobalHead
        
        count = GlobalHead.objects.count()
        if count > 0:
            print(f"✓ Found {count} GlobalHead records")
        else:
            print("⚠ No GlobalHead records found")
            print("  Run: python manage.py import_coa --file=docs/tma_coa.csv --fund=GEN --function=<code>")
    except Exception as e:
        print(f"✗ Check failed: {str(e)}")
    
    # Step 5: Check employee data
    print_step(5, "Checking employee data")
    try:
        from apps.budgeting.models_employee import BudgetEmployee
        from apps.core.models import Department
        
        emp_count = BudgetEmployee.objects.filter(is_vacant=False).count()
        dept_count = Department.objects.filter(is_active=True).count()
        
        print(f"✓ Found {emp_count} active employees")
        print(f"✓ Found {dept_count} active departments")
        
        if emp_count == 0:
            print("⚠ No employees found - budget distribution will fail")
            print("  Add employees via Schedule of Establishment")
    except Exception as e:
        print(f"✗ Check failed: {str(e)}")
    
    # Step 6: Summary and next steps
    print_step(6, "Setup Complete - Next Steps")
    
    print("""
SETUP COMPLETED SUCCESSFULLY!

To use the salary budget management system:

1. Access the dashboard:
   URL: /budgeting/salary-budget/

2. Distribute initial budget:
   - Click "Distribute New Budget" button
   - Select fiscal year, fund, and account code
   - Enter total budget amount from provincial letter
   - System will allocate proportionally among departments

3. Monitor budget status:
   - Dashboard shows real-time utilization
   - Alerts at 80% (warning) and 90% (critical)
   - Click department names for detailed view

4. Bill approval workflow:
   - Bills automatically validated against department budgets
   - Approval blocked if insufficient budget
   - Budgets consumed upon approval
   - Budgets released upon cancellation

5. Export reports:
   - Click "Export" button for CSV download
   - View consumption history for audit trail

EXAMPLE COMMANDS:

# Distribute salary budget for Basic Pay
python manage.py distribute_salary_budget \\
    --fy=2025-26 \\
    --fund=GEN \\
    --account=A01151 \\
    --amount=942657799

# Dry run to preview distribution
python manage.py distribute_salary_budget \\
    --fy=2025-26 \\
    --fund=GEN \\
    --account=A01151 \\
    --amount=942657799 \\
    --dry-run

# View all commands
python manage.py --help

INTEGRATION WITH BILL APPROVAL:

Add to your bill approval view:

    from apps.budgeting.services_salary_budget import SalaryBillValidator
    
    # Validate before approval
    is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
    
    if is_valid:
        bill.status = 'APPROVED'
        bill.save()
        SalaryBillValidator.consume_budget_for_bill(bill)

See apps/expenditure/integration_salary_budget.py for complete examples.

    """)
    
    print_header("SETUP COMPLETE")
    print("The salary budget management system is ready to use!")
    print("="*80)


if __name__ == '__main__':
    main()
