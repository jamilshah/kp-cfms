"""
Smart assignment of GlobalHeads to departments based on code patterns.

This script assigns GlobalHeads to departments based on their code prefixes and names:
- A01* (Salaries) → All departments (UNIVERSAL) - Already done
- A02, A03, A04, A05, A06, A07 (Admin expenses) → All departments (UNIVERSAL)
- C* (Revenue) → Regulations department only
- D* (Development) → Infrastructure department
- Water/Sewage codes → Infrastructure & Services
- Road/Transport codes → Infrastructure & Services
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import GlobalHead
from apps.budgeting.models import Department

# Get departments
try:
    admin = Department.objects.get(code='ADM')
    finance = Department.objects.get(code='FIN')
    infra = Department.objects.get(code='IS')
    planning = Department.objects.get(code='PLN')
    regulation = Department.objects.get(code='REG')
except Department.DoesNotExist as e:
    print(f"ERROR: Department not found: {e}")
    exit(1)

print("=" * 80)
print("SMART ASSIGNMENT OF GLOBALHEADS TO DEPARTMENTS")
print("=" * 80)

# Counter
universal_count = 0
departmental_count = 0
skipped = 0

# Get all heads that aren't already marked as departmental
heads = GlobalHead.objects.filter(scope='UNIVERSAL').order_by('code')

for head in heads:
    code = head.code.upper()
    name = head.name.upper()
    
    # SKIP: Salary heads (A01*) - already universal
    if code.startswith('A01'):
        skipped += 1
        continue
    
    # KEEP UNIVERSAL: Common admin expenses (A02-A09) - used by all departments
    if code.startswith(('A02', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09')):
        universal_count += 1
        print(f"✓ UNIVERSAL: {code} - {name[:50]}")
        continue
    
    # KEEP UNIVERSAL: Revenue heads (C*) - NOT used in Bills, keep as universal
    if code.startswith('C'):
        universal_count += 1
        print(f"✓ UNIVERSAL: {code} - {name[:50]} (Revenue - not in Bills)")
        continue
    
    # KEEP UNIVERSAL: Development heads (D*) - typically not in regular Bills
    if code.startswith('D'):
        universal_count += 1
        print(f"✓ UNIVERSAL: {code} - {name[:50]} (Development)")
        continue
    
    # DEPARTMENTAL: Water/Sewage → Infrastructure
    if any(x in name for x in ['WATER', 'SEWAGE', 'SANITATION', 'DRAINAGE']):
        head.scope = 'DEPARTMENTAL'
        head.save()
        head.applicable_departments.set([infra])
        departmental_count += 1
        print(f"→ INFRA:       {code} - {name[:50]}")
        continue
    
    # DEPARTMENTAL: Road/Transport → Infrastructure
    if any(x in name for x in ['ROAD', 'TRANSPORT', 'TRAFFIC', 'HIGHWAY', 'STREET']):
        head.scope = 'DEPARTMENTAL'
        head.save()
        head.applicable_departments.set([infra])
        departmental_count += 1
        print(f"→ INFRA:       {code} - {name[:50]}")
        continue
    
    # DEPARTMENTAL: Licenses/Fines → Regulations
    if any(x in name for x in ['LICENSE', 'FINE', 'PERMIT', 'CERTIFICATE', 'REGISTRATION']):
        head.scope = 'DEPARTMENTAL'
        head.save()
        head.applicable_departments.set([regulation])
        departmental_count += 1
        print(f"→ REGULATION:  {code} - {name[:50]}")
        continue
    
    # DEFAULT: Keep as universal if no pattern matches
    universal_count += 1
    print(f"✓ UNIVERSAL: {code} - {name[:50]} (no pattern match)")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Universal (kept):        {universal_count}")
print(f"Departmental (assigned): {departmental_count}")
print(f"Skipped (A01*):          {skipped}")
print(f"Total heads:             {universal_count + departmental_count + skipped}")
print("=" * 80)
