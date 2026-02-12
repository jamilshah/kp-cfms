"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Description: Seed NAM Chart of Accounts with clean 5-level hierarchy
             Fresh implementation - no migration needed
-------------------------------------------------------------------------

Usage:
    python manage.py shell < scripts/seed_nam_coa_structure.py
    
    OR
    
    python manage.py shell
    >>> exec(open('scripts/seed_nam_coa_structure.py').read())
"""

import os
import sys
import django

# Setup Django environment
if __name__ == '__main__':
    # Add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from apps.finance.models import MajorHead, MinorHead, NAMHead, SubHead, AccountType


def seed_master_coa():
    """
    Seed master CoA structure with PIFRA standard accounts.
    
    This creates a sample structure following the document:
    Level 1: Classification (A/C/G/K)
    Level 2: Major Head (A01, A12)
    Level 3: Minor Head (A011, A120)
    Level 4: NAM Head (A01101, A12001)
    Level 5: Sub-Head (A12001-01, A12001-02)
    """
    
    print("🚀 Starting NAM CoA Structure Seeding...")
    print("=" * 70)
    
    # ========================================================================
    # LEVEL 1 & 2: MAJOR HEADS
    # ========================================================================
    print("\n📊 Creating Major Heads (Level 2)...")
    
    # Expenditure Major Heads
    a01, created = MajorHead.objects.get_or_create(
        code='A01',
        defaults={
            'name': 'Employee Related Expenses',
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a01.code} - {a01.name}")
    
    a03, created = MajorHead.objects.get_or_create(
        code='A03',
        defaults={
            'name': 'Operating Expenses',
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a03.code} - {a03.name}")
    
    a12, created = MajorHead.objects.get_or_create(
        code='A12',
        defaults={
            'name': 'Physical Assets',
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a12.code} - {a12.name}")
    
    # Revenue Major Heads
    c01, created = MajorHead.objects.get_or_create(
        code='C01',
        defaults={
            'name': 'Tax Revenue',
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {c01.code} - {c01.name}")
    
    c03, created = MajorHead.objects.get_or_create(
        code='C03',
        defaults={
            'name': 'Non-Tax Revenue',
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {c03.code} - {c03.name}")
    
    # ========================================================================
    # LEVEL 3: MINOR HEADS
    # ========================================================================
    print("\n📊 Creating Minor Heads (Level 3)...")
    
    # Expenditure Minor Heads
    a011, created = MinorHead.objects.get_or_create(
        code='A011',
        defaults={
            'name': 'Pay',
            'major': a01
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a011.code} - {a011.name}")
    
    a012, created = MinorHead.objects.get_or_create(
        code='A012',
        defaults={
            'name': 'Allowances',
            'major': a01
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a012.code} - {a012.name}")
    
    a033, created = MinorHead.objects.get_or_create(
        code='A033',
        defaults={
            'name': 'Utilities',
            'major': a03
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a033.code} - {a033.name}")
    
    a120, created = MinorHead.objects.get_or_create(
        code='A120',
        defaults={
            'name': 'Roads & Bridges',
            'major': a12
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a120.code} - {a120.name}")
    
    # Revenue Minor Heads
    c038, created = MinorHead.objects.get_or_create(
        code='C038',
        defaults={
            'name': 'Property Income',
            'major': c03
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {c038.code} - {c038.name}")
    
    # ========================================================================
    # LEVEL 4: NAM HEADS (Official Reporting Heads)
    # ========================================================================
    print("\n📊 Creating NAM Heads (Level 4 - Official Reporting)...")
    
    # Salary NAM Heads
    a01101, created = NAMHead.objects.get_or_create(
        code='A01101',
        defaults={
            'name': 'Basic Pay - Officers',
            'minor': a011,
            'account_type': AccountType.EXPENDITURE,
            'scope': 'UNIVERSAL',
            'allow_direct_posting': True,
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a01101.code} - {a01101.name}")
    
    a01151, created = NAMHead.objects.get_or_create(
        code='A01151',
        defaults={
            'name': 'Basic Pay - Other Staff',
            'minor': a011,
            'account_type': AccountType.EXPENDITURE,
            'scope': 'UNIVERSAL',
            'allow_direct_posting': True,
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a01151.code} - {a01151.name}")
    
    a01210, created = NAMHead.objects.get_or_create(
        code='A01210',
        defaults={
            'name': 'House Rent Allowance',
            'minor': a012,
            'account_type': AccountType.EXPENDITURE,
            'scope': 'UNIVERSAL',
            'allow_direct_posting': True,
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a01210.code} - {a01210.name}")
    
    # Utilities NAM Heads
    a03303, created = NAMHead.objects.get_or_create(
        code='A03303',
        defaults={
            'name': 'Electricity',
            'minor': a033,
            'account_type': AccountType.EXPENDITURE,
            'scope': 'UNIVERSAL',
            'allow_direct_posting': True,
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a03303.code} - {a03303.name}")
    
    a03304, created = NAMHead.objects.get_or_create(
        code='A03304',
        defaults={
            'name': 'Water Charges',
            'minor': a033,
            'account_type': AccountType.EXPENDITURE,
            'scope': 'UNIVERSAL',
            'allow_direct_posting': True,
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a03304.code} - {a03304.name}")
    
    # Physical Assets NAM Head (with sub-heads)
    a12001, created = NAMHead.objects.get_or_create(
        code='A12001',
        defaults={
            'name': 'Roads',
            'minor': a120,
            'account_type': AccountType.EXPENDITURE,
            'scope': 'UNIVERSAL',
            'allow_direct_posting': True,  # Will be auto-disabled when sub-heads created
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {a12001.code} - {a12001.name}")
    
    # Revenue NAM Head
    c03880, created = NAMHead.objects.get_or_create(
        code='C03880',
        defaults={
            'name': 'Rent of Buildings & Shops',
            'minor': c038,
            'account_type': AccountType.REVENUE,
            'scope': 'UNIVERSAL',
            'allow_direct_posting': True,
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {c03880.code} - {c03880.name}")
    
    # ========================================================================
    # LEVEL 5: SUB-HEADS (Internal Breakdown)
    # ========================================================================
    print("\n📊 Creating Sub-Heads (Level 5 - Internal Breakdown)...")
    
    # Roads Sub-Heads (for granular tracking)
    roads_sub1, created = SubHead.objects.get_or_create(
        nam_head=a12001,
        sub_code='01',
        defaults={
            'name': 'PCC Streets',
            'description': 'Portland Cement Concrete streets construction and maintenance',
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {roads_sub1.code} - {roads_sub1.name}")
    
    roads_sub2, created = SubHead.objects.get_or_create(
        nam_head=a12001,
        sub_code='02',
        defaults={
            'name': 'Shingle Roads',
            'description': 'Shingle/gravel road construction and maintenance',
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {roads_sub2.code} - {roads_sub2.name}")
    
    roads_sub3, created = SubHead.objects.get_or_create(
        nam_head=a12001,
        sub_code='03',
        defaults={
            'name': 'Tough Tiles',
            'description': 'Interlocking pavers and tough tiles',
            'is_active': True
        }
    )
    print(f"  {'✓ Created' if created else '  Exists'}: {roads_sub3.code} - {roads_sub3.name}")
    
    # Verify parent NAM head posting status updated
    a12001.refresh_from_db()
    print(f"\n  ℹ️  NAM Head {a12001.code} allow_direct_posting: {a12001.allow_direct_posting}")
    print(f"      (Should be False since sub-heads exist)")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    print("✅ NAM CoA Structure Seeding Complete!")
    print("=" * 70)
    
    print(f"\n📈 Summary:")
    print(f"  • Major Heads: {MajorHead.objects.count()}")
    print(f"  • Minor Heads: {MinorHead.objects.count()}")
    print(f"  • NAM Heads (Level 4): {NAMHead.objects.count()}")
    print(f"  • Sub-Heads (Level 5): {SubHead.objects.count()}")
    
    print(f"\n🔍 Breakdown by Account Type:")
    for acc_type in AccountType:
        count = NAMHead.objects.filter(account_type=acc_type).count()
        print(f"  • {acc_type.label}: {count} NAM heads")
    
    print(f"\n🌳 Hierarchy Verification:")
    print(f"  • NAM Heads with sub-heads: {NAMHead.objects.filter(allow_direct_posting=False).count()}")
    print(f"  • NAM Heads allowing direct posting: {NAMHead.objects.filter(allow_direct_posting=True).count()}")
    
    print("\n💡 Next Steps:")
    print("  1. Create Departments in admin")
    print("  2. Create Functions (AD, WS, SW, etc.)")
    print("  3. Create Fund (General, Development)")
    print("  4. Create BudgetHeads linking Dept + Function + Fund + (NAM|SubHead)")
    print("  5. Run migrations: python manage.py makemigrations && python manage.py migrate")
    print("\n" + "=" * 70)


if __name__ == '__main__':
    seed_master_coa()
