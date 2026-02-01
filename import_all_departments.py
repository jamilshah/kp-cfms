#!/usr/bin/env python
"""
Bulk import CoA for all departments with their related functions.
This creates BudgetHeads for each function in each department.
"""
import os
import sys
import django
from django.core.management import call_command

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import Department

def main():
    print("=" * 80)
    print("BULK COA IMPORT FOR ALL DEPARTMENTS")
    print("=" * 80)
    
    fund_code = 'GEN'  # Change if needed
    coa_file = 'docs/tma_coa.csv'
    
    print(f"\nImporting from: {coa_file}")
    print(f"Target Fund: {fund_code}")
    print("\n" + "-" * 80)
    
    departments = Department.objects.prefetch_related('related_functions').filter(is_active=True)
    total_depts = departments.count()
    total_functions = sum(d.related_functions.count() for d in departments)
    
    print(f"Found {total_depts} active departments with {total_functions} total functions")
    print("-" * 80)
    
    # Confirm before proceeding
    response = input("\nProceed with import? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Import cancelled.")
        return
    
    print("\n" + "=" * 80)
    print("STARTING IMPORT...")
    print("=" * 80 + "\n")
    
    total_created = 0
    total_errors = 0
    
    for dept in departments:
        functions = dept.related_functions.all()
        
        if functions.count() == 0:
            print(f"\n⚠️  Skipping {dept.name} - no related functions")
            continue
        
        print(f"\n{'=' * 80}")
        print(f"DEPARTMENT: {dept.name}")
        print(f"Functions: {functions.count()}")
        print('=' * 80)
        
        try:
            # Call the import_coa command
            call_command(
                'import_coa',
                file=coa_file,
                fund=fund_code,
                department_id=str(dept.id),
                verbosity=1
            )
            
            # Count how many were created for this department
            from apps.finance.models import BudgetHead
            dept_count = sum(
                BudgetHead.objects.filter(function=func).count() 
                for func in functions
            )
            total_created += dept_count
            
            print(f"\n✓ Successfully imported for {dept.name}")
            print(f"  Total BudgetHeads: {dept_count}")
            
        except Exception as e:
            total_errors += 1
            print(f"\n✗ Error importing for {dept.name}: {str(e)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("IMPORT SUMMARY")
    print("=" * 80)
    print(f"Departments processed: {total_depts}")
    print(f"Total BudgetHeads created: {total_created}")
    print(f"Errors: {total_errors}")
    print("=" * 80)
    
    if total_errors == 0:
        print("\n✓ All imports completed successfully!")
    else:
        print(f"\n⚠️  {total_errors} department(s) had errors. Check logs above.")

if __name__ == '__main__':
    main()
