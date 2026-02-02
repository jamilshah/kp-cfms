"""
Seed TMA structure with function-usage notes and department-function mappings
Based on tma_structure.md specifications

NOTE: Departments should already exist. This script only:
1. Seeds function codes with usage notes
2. Assigns functions to departments
3. Sets default functions for departments
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.budgeting.models import Department
from apps.finance.models import FunctionCode

# Function definitions with usage notes
FUNCTIONS = {
    # Administration Department
    '011103': {
        'name': 'Municipal Administration',
        'usage': 'Default. TMO, Superintendent, Clerks, Office Utilities, Fuel.',
    },
    '011101': {
        'name': 'Executive & Legislative Organs',
        'usage': 'Council Budget. Nazim/Chairman Honoraria, Session Costs.',
    },
    '011110': {
        'name': 'General Commission Services',
        'usage': 'Legal expenses, Inquiry Committees.',
    },
    
    # Finance Department
    '015101': {
        'name': 'Financial Management',
        'usage': 'Default. TO Finance, Accountants, Bank Charges, Audit Fees.',
    },
    '074020': {
        'name': 'Public Debt Management',
        'usage': 'Interest payments on loans (if any).',
    },
    
    # Regulation Department
    '011205': {
        'name': 'Tax Management',
        'usage': 'Default. Tax Superintendent, Inspectors, Printing of Challans.',
    },
    '041300': {
        'name': 'General Economic Affairs',
        'usage': 'Managing General Bus Stands, Shops, Rent Collection.',
    },
    '041302': {
        'name': 'Agriculture & Livestock',
        'usage': 'Managing Cattle Fairs (Mandi).',
    },
    '041310': {
        'name': 'Road Transport',
        'usage': 'Managing General Bus Stands (Adda) and Parking Stands. This is a huge revenue source.',
    },
    
    # Engineering Department
    '045101': {
        'name': 'Roads & Streets',
        'usage': 'Paving streets, drains, road clearance.',
    },
    '063102': {
        'name': 'Water Supply',
        'usage': 'Tubewells, Water pipes, Electricity for pumps.',
    },
    '055101': {
        'name': 'Waste Management',
        'usage': 'Sanitation staff, Tractors, Fuel for Garbage trucks.',
    },
    '064101': {
        'name': 'Street Lights',
        'usage': 'Bulbs, Wire repair, Solar panels.',
    },
    '032102': {
        'name': 'Fire Protection',
        'usage': 'Fire Brigade staff and vehicles.',
    },
    '082120': {
        'name': 'Parks & Recreation',
        'usage': 'Gardeners (Malis), Plants, Park maintenance.',
    },
    '045102': {
        'name': 'Building Repair',
        'usage': 'Maintenance of the TMA Office building itself.',
    },
    '055102': {
        'name': 'Sewerage Systems',
        'usage': 'Cleaning and repair of Drains (Nalis) and Sewerage lines. (Distinct from Solid Waste).',
    },
    '061101': {
        'name': 'Housing Development',
        'usage': 'If the TMA owns/develops Housing Schemes or Plazas.',
    },
    '062101': {
        'name': 'Community Development',
        'usage': 'Town Planning, Approval of Maps, Master Planning.',
    },
    '062201': {
        'name': 'Rural Development',
        'usage': 'Specific development schemes in rural union councils.',
    },
    '084103': {
        'name': 'Community Centers',
        'usage': 'Maintenance of Marriage Halls, Libraries, or Community Centers owned by TMA.',
    },
    '086101': {
        'name': 'Religious Affairs',
        'usage': 'Maintenance of Graveyards, Janazgahs, and Eid-Gahs.',
    },
    '091103': {
        'name': 'Primary Education',
        'usage': '(Rare) If the TMA runs its own primary schools (maintenance of school buildings).',
    },
}

# Department-Function mappings
DEPT_FUNCTION_MAP = {
    'ADMN': ['011103', '011101', '011110'],
    'FIN': ['015101', '074020'],
    'REG': ['011205', '041300', '041302', '041310'],
    'ENGR': ['045101', '063102', '055101', '064101', '032102', '082120', '045102', 
             '055102', '061101', '062101', '062201', '084103', '086101', '091103'],
    'CNCL': ['011101'],  # Tehsil Council (Nazim Secretariat)
}

# Default function for each department
DEFAULT_FUNCTIONS = {
    'ADMN': '011103',  # Municipal Administration
    'FIN': '015101',   # Financial Management
    'REG': '011205',   # Tax Management
    'ENGR': '045101',  # Roads & Streets
    'CNCL': '011101',  # Executive & Legislative Organs
}


def seed_functions():
    """Create or update function codes with usage notes"""
    print("\n" + "="*80)
    print("SEEDING FUNCTION CODES")
    print("="*80)
    
    created_count = 0
    updated_count = 0
    
    for code, info in FUNCTIONS.items():
        func, created = FunctionCode.objects.update_or_create(
            code=code,
            defaults={
                'name': info['name'],
                'usage_notes': info['usage']
            }
        )
        
        if created:
            created_count += 1
            print(f"  ✓ Created: {code} - {info['name']}")
        else:
            updated_count += 1
            print(f"  ↻ Updated: {code} - {info['name']}")
    
    print(f"\n✓ Created {created_count}, Updated {updated_count} functions")


def assign_functions_to_departments():
    """Assign functions to departments and set default functions"""
    print("\n" + "="*80)
    print("ASSIGNING FUNCTIONS TO DEPARTMENTS")
    print("="*80)
    
    for dept_code, function_codes in DEPT_FUNCTION_MAP.items():
        try:
            dept = Department.objects.get(code=dept_code)
            print(f"\n{dept_code} - {dept.name}")
            print("-" * 60)
            
            # Get function objects
            functions = FunctionCode.objects.filter(code__in=function_codes)
            
            # Assign functions
            dept.related_functions.set(functions)
            print(f"  ✓ Assigned {functions.count()} functions")
            
            # Set default function if specified
            if dept_code in DEFAULT_FUNCTIONS:
                default_code = DEFAULT_FUNCTIONS[dept_code]
                default_func = FunctionCode.objects.filter(code=default_code).first()
                if default_func:
                    dept.default_function = default_func
                    dept.save()
                    print(f"  ✓ Set default: {default_code} - {default_func.name}")
            
            # List assigned functions
            for func in functions:
                is_default = " (DEFAULT)" if dept.default_function_id == func.id else ""
                print(f"    • {func.code} - {func.name}{is_default}")
        
        except Department.DoesNotExist:
            print(f"  ⚠ WARNING: Department {dept_code} not found!")
            continue


def main():
    print("\n" + "="*80)
    print("TMA STRUCTURE SEEDING")
    print("Based on tma_structure.md (AGP/PIFRA Compliant)")
    print("="*80)
    
    # Seed functions with usage notes
    seed_functions()
    
    # Assign functions to departments
    assign_functions_to_departments()
    
    print("\n" + "="*80)
    print("✓ SEEDING COMPLETE")
    print("="*80)
    
    # Summary
    print("\nSummary:")
    for dept_code in DEPT_FUNCTION_MAP.keys():
        try:
            dept = Department.objects.get(code=dept_code)
            func_count = dept.related_functions.count()
            default = dept.default_function.code if dept.default_function else "None"
            print(f"  {dept_code}: {func_count} functions (default: {default})")
        except Department.DoesNotExist:
            print(f"  {dept_code}: NOT FOUND")


if __name__ == '__main__':
    main()
