"""
Data migration to populate system_code on NAMHead for automated workflows.
"""
from django.db import migrations


def populate_system_codes(apps, schema_editor):
    """
    Assign system codes to NAMHead entries for automated GL workflows.
    
    Maps NAM codes to SystemCode enums for:
    - AP (Accounts Payable)
    - AR (Accounts Receivable)  
    - TAX_IT (Income Tax Payable)
    - TAX_GST (Sales Tax Payable)
    - CLEARING_IT (Income Tax Withheld)
    - CLEARING_GST (Sales Tax Withheld)
    """
    NAMHead = apps.get_model('finance', 'NAMHead')
    
    # Map NAM codes to system codes
    system_code_mappings = {
        'G01101': 'AP',           # Accounts Payable / Cheque Clearing
        'F01603': 'AR',           # Accounts Receivable
        'G01204': 'TAX_IT',       # Income Tax Payable
        'G01205': 'TAX_GST',      # Sales Tax Payable
        'G01140': 'CLEARING_IT',  # Income Tax Withheld
        'G01145': 'CLEARING_GST', # Sales Tax Withheld
        'G05103': 'SYS_SUSPENSE', # Suspense Account
        'G05106': 'CLEARING_SEC', # Security/Retention Money
    }
    
    updated_count = 0
    for nam_code, sys_code in system_code_mappings.items():
        try:
            nam_head = NAMHead.objects.get(code=nam_code)
            nam_head.system_code = sys_code
            nam_head.save()
            updated_count += 1
            print(f"  ✓ Assigned {sys_code} to NAMHead {nam_code}")
        except NAMHead.DoesNotExist:
            print(f"  ⚠ NAMHead {nam_code} not found - skipping")
    
    print(f"\n  Total NAMHeads updated: {updated_count}")


def reverse_system_codes(apps, schema_editor):
    """Remove system codes from NAMHead."""
    NAMHead = apps.get_model('finance', 'NAMHead')
    NAMHead.objects.filter(system_code__isnull=False).update(system_code=None)


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0034_add_system_code_to_namhead'),
    ]

    operations = [
        migrations.RunPython(populate_system_codes, reverse_system_codes),
    ]
