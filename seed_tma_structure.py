"""
Seed TMA Department-Function Mappings per tma_structure.md
Based on AGP/KP Accounts Rules requirements
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import Department
from apps.finance.models import FunctionCode

# Department codes and names
DEPARTMENTS = {
    'ADMN': 'Administration',
    'FIN': 'Finance',
    'REG': 'Regulation',
    'ENGR': 'Engineering (I&S)'
}

# Function mappings from tma_structure.md
FUNCTION_MAPPINGS = {
    'ADMN': {
        'default': '011103',
        'functions': [
            ('011103', 'Municipal Administration', 'TMO, Superintendent, Clerks, Office Utilities, Fuel'),
            ('011101', 'Executive & Legislative Organs', 'Council Budget: Nazim/Chairman Honoraria, Session Costs'),
            ('011110', 'General Commission Services', 'Legal expenses, Inquiry Committees'),
        ]
    },
    'FIN': {
        'default': '015101',
        'functions': [
            ('015101', 'Financial Management', 'TO Finance, Accountants, Bank Charges, Audit Fees'),
            ('074020', 'Public Debt Management', 'Interest payments on loans (if any)'),
        ]
    },
    'REG': {
        'default': '011205',
        'functions': [
            ('011205', 'Tax Management', 'Tax Superintendent, Inspectors, Printing of Challans'),
            ('041300', 'General Economic Affairs', 'Managing General Bus Stands, Shops, Rent Collection'),
            ('041302', 'Agriculture & Livestock', 'Managing Cattle Fairs (Mandi)'),
        ]
    },
    'ENGR': {
        'default': '045101',
        'functions': [
            ('045101', 'Roads & Streets', 'Paving streets, drains, road clearance'),
            ('063102', 'Water Supply', 'Tubewells, Water pipes, Electricity for pumps'),
            ('055101', 'Waste Management', 'Sanitation staff, Tractors, Fuel for Garbage trucks'),
            ('064101', 'Street Lights', 'Bulbs, Wire repair, Solar panels'),
            ('032102', 'Fire Protection', 'Fire Brigade staff and vehicles'),
            ('082120', 'Parks & Recreation', 'Gardeners (Malis), Plants, Park maintenance'),
            ('045102', 'Building Repair', 'Maintenance of the TMA Office building itself'),
        ]
    }
}


def seed_tma_structure():
    """Seed departments and function mappings"""
    
    print("=" * 80)
    print("SEEDING TMA STRUCTURE (AGP/PIFRA Compliant)")
    print("=" * 80)
    
    created_depts = 0
    updated_depts = 0
    created_functions = 0
    updated_functions = 0
    
    for dept_code, dept_name in DEPARTMENTS.items():
        print(f"\n{dept_code} - {dept_name}")
        print("-" * 80)
        
        # Create or update department
        try:
            dept = Department.objects.get(code=dept_code)
            # Update name if needed
            dept.name = dept_name
            dept.is_active = True
            dept.save()
            updated_depts += 1
            print(f"  ↻ Updated department: {dept_name}")
        except Department.DoesNotExist:
            # Try to find by name and update code
            try:
                dept = Department.objects.get(name=dept_name)
                dept.code = dept_code
                dept.is_active = True
                dept.save()
                updated_depts += 1
                print(f"  ↻ Updated department code: {dept_code}")
            except Department.DoesNotExist:
                # Create new department
                dept = Department.objects.create(
                    code=dept_code,
                    name=dept_name,
                    is_active=True
                )
                created_depts += 1
                print(f"  ✓ Created department: {dept_name}")
        
        # Get function mappings for this department
        mapping = FUNCTION_MAPPINGS[dept_code]
        default_func_code = mapping['default']
        functions_list = mapping['functions']
        
        # Clear existing function assignments
        dept.related_functions.clear()
        
        default_function = None
        
        # Create/update functions and assign to department
        for func_code, func_name, usage_notes in functions_list:
            func, func_created = FunctionCode.objects.get_or_create(
                code=func_code,
                defaults={
                    'name': func_name,
                    'usage_notes': usage_notes,
                    'is_default': (func_code == default_func_code)
                }
            )
            
            if func_created:
                created_functions += 1
                print(f"    + Created function: {func_code} - {func_name}")
            else:
                # Update existing function
                func.name = func_name
                func.usage_notes = usage_notes
                func.is_default = (func_code == default_func_code)
                func.save()
                updated_functions += 1
                print(f"    ↻ Updated function: {func_code} - {func_name}")
            
            # Add to department
            dept.related_functions.add(func)
            
            # Mark default function
            if func_code == default_func_code:
                default_function = func
                print(f"    ★ DEFAULT: {func_code}")
        
        # Set default function for department
        if default_function:
            dept.default_function = default_function
            dept.save()
            print(f"  ★ Default function set: {default_function.code} - {default_function.name}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Departments created: {created_depts}")
    print(f"Departments updated: {updated_depts}")
    print(f"Functions created: {created_functions}")
    print(f"Functions updated: {updated_functions}")
    print(f"\nTotal departments: {Department.objects.count()}")
    print(f"Total functions: {FunctionCode.objects.count()}")
    print("\n✓ TMA Structure seeded successfully!")
    print("=" * 80)


if __name__ == '__main__':
    seed_tma_structure()
