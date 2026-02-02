"""
Smart CoA Department Assignment Script
Intelligently assigns common/universal heads and department-specific heads
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import GlobalHead, AccountType
from apps.budgeting.models import Department

print("=" * 80)
print("Smart CoA Department Assignment")
print("=" * 80)

# Get all departments
departments = Department.objects.all()
print(f"\nAvailable Departments:")
for dept in departments:
    print(f"  {dept.id}: {dept.code} - {dept.name}")

# Create department lookup by ID
dept_by_name = {}
for dept in departments:
    if 'infrastructure' in dept.name.lower() or 'infra' in dept.name.lower():
        dept_by_name['Infrastructure'] = dept
    elif 'administration' in dept.name.lower() or 'admin' in dept.name.lower():
        dept_by_name['Administration'] = dept
    elif 'finance' in dept.name.lower():
        dept_by_name['Finance'] = dept
    elif 'regulation' in dept.name.lower():
        dept_by_name['Regulations'] = dept
    elif 'planning' in dept.name.lower():
        dept_by_name['Planning'] = dept

print(f"\nMapped departments: {list(dept_by_name.keys())}")

# Define universal heads (appear for all departments)
UNIVERSAL_PATTERNS = [
    ('A011', 'Salaries - All employee categories'),
    ('A012', 'Allowances - Common allowances'),
    ('A013', 'Office expenses - Supplies, utilities, rent'),
    ('A014', 'Travel & conveyance'),
    ('A015', 'Communication expenses'),
    ('A016', 'Repairs & maintenance - Office buildings'),
    ('A017', 'Utilities - Electricity, gas, water'),
]

# Define department-specific patterns
DEPARTMENT_PATTERNS = {
    'Infrastructure': [
        ('A045', 'Roads & Streets'),
        ('A046', 'Construction materials'),
        ('A055', 'Waste management'),
        ('A056', 'Sanitation'),
        ('A057', 'Water supply'),
        ('C03849', 'Malba/Road clearance charges'),
    ],
    'Regulations': [
        ('C02937', 'Building law fines'),
        ('C03841', 'Fees, fines'),
        ('A041', 'Economic affairs'),
    ],
    'Administration': [
        ('C02701', 'Building rent'),
        ('C03682', 'Government grants'),
        ('A081', 'Recreation services'),
    ],
    'Finance': [
        ('A015', 'Financial management'),
        ('C01', 'Tax revenues'),
    ],
}

# Step 1: Mark common salary and office expense heads as UNIVERSAL
print("\n[STEP 1] Marking common heads as UNIVERSAL...")
print("-" * 80)

universal_count = 0
for pattern, description in UNIVERSAL_PATTERNS:
    heads = GlobalHead.objects.filter(code__startswith=pattern)
    count = heads.count()
    if count > 0:
        heads.update(scope='UNIVERSAL')
        # Clear any existing department assignments
        for head in heads:
            head.applicable_departments.clear()
        print(f"  ✓ {pattern}*: {count} heads → UNIVERSAL ({description})")
        universal_count += count

print(f"\nTotal Universal heads: {universal_count}")

# Step 2: Assign department-specific heads
print("\n[STEP 2] Assigning department-specific heads...")
print("-" * 80)

dept_count = 0
for dept_name, patterns in DEPARTMENT_PATTERNS.items():
    print(f"\n{dept_name}:")
    dept_obj = dept_by_name.get(dept_name)
    
    if not dept_obj:
        print(f"  ⚠ Department not found, skipping...")
        continue
    
    for pattern, description in patterns:
        heads = GlobalHead.objects.filter(code__startswith=pattern).exclude(scope='UNIVERSAL')
        count = heads.count()
        if count > 0:
            heads.update(scope='DEPARTMENTAL')
            for head in heads:
                head.applicable_departments.add(dept_obj)
            print(f"  ✓ {pattern}*: {count} heads → {dept_obj.name} ({description})")
            dept_count += count

print(f"\nTotal Departmental heads assigned: {dept_count}")

# Step 3: Summary statistics
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_heads = GlobalHead.objects.count()
universal = GlobalHead.objects.filter(scope='UNIVERSAL').count()
departmental = GlobalHead.objects.filter(scope='DEPARTMENTAL').count()
departmental_with_depts = GlobalHead.objects.filter(
    scope='DEPARTMENTAL'
).exclude(applicable_departments=None).count()
unmapped = GlobalHead.objects.filter(
    scope='DEPARTMENTAL', applicable_departments=None
).count()

print(f"\nTotal CoA Heads:           {total_heads:,}")
print(f"  Universal:               {universal:,} ({universal/total_heads*100:.1f}%)")
print(f"  Departmental:            {departmental:,} ({departmental/total_heads*100:.1f}%)")
print(f"    - With departments:    {departmental_with_depts:,}")
print(f"    - Unmapped:            {unmapped:,}")

print(f"\n{'=' * 80}")
print("NEXT STEPS")
print("=" * 80)
print(f"""
1. Review the assignments at: /finance/coa-department-mapping/
2. Refine unmapped heads ({unmapped:,} remaining)
3. Test bill/demand creation - should now show filtered heads
4. Adjust mappings based on user feedback

The system is now configured with smart defaults!
""")
print("=" * 80)
