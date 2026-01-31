"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Quick script to run system code tests and configuration check.
-------------------------------------------------------------------------
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command
from io import StringIO


def main():
    print("=" * 80)
    print("KP-CFMS SYSTEM CODE TEST SUITE")
    print("=" * 80)
    
    # Step 1: Check current configuration
    print("\n[1/3] Checking current configuration...")
    print("-" * 80)
    call_command('check_system_codes')
    
    # Step 2: Run tests
    print("\n[2/3] Running comprehensive tests...")
    print("-" * 80)
    try:
        call_command('test', 'apps.finance.tests.test_system_codes', verbosity=2)
        print("✓ All tests passed!")
    except SystemExit as e:
        if e.code != 0:
            print("✗ Some tests failed. Review output above.")
            sys.exit(1)
    
    # Step 3: Final summary
    print("\n[3/3] Final verification...")
    print("-" * 80)
    call_command('check_system_codes')
    
    print("\n" + "=" * 80)
    print("✓ SYSTEM CODE TEST SUITE COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    main()
