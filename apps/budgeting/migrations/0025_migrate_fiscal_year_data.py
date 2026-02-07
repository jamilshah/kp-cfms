from django.db import migrations

def deduplicate_fiscal_years(apps, schema_editor):
    """
    Convert per-TMA FiscalYears to:
    1. Single Global FiscalYear per year_name
    2. BudgetProposal per TMA per year
    """
    FiscalYear = apps.get_model('budgeting', 'FiscalYear')
    BudgetProposal = apps.get_model('budgeting', 'BudgetProposal')
    
    # Models to re-point
    BudgetAllocation = apps.get_model('budgeting', 'BudgetAllocation')
    ScheduleOfEstablishment = apps.get_model('budgeting', 'ScheduleOfEstablishment')
    PensionEstimate = apps.get_model('budgeting', 'PensionEstimate')
    SupplementaryGrant = apps.get_model('budgeting', 'SupplementaryGrant')
    Reappropriation = apps.get_model('budgeting', 'Reappropriation')
    QuarterlyRelease = apps.get_model('budgeting', 'QuarterlyRelease')
    SAERecord = apps.get_model('budgeting', 'SAERecord')
    
    # Cross-app Dependencies
    Bill = apps.get_model('expenditure', 'Bill')
    Voucher = apps.get_model('finance', 'Voucher')
    RevenueDemand = apps.get_model('revenue', 'RevenueDemand')
    
    # Get all unique year names
    year_names = set(FiscalYear.objects.values_list('year_name', flat=True))
    
    for year_name in year_names:
        # Get all FY records for this year, order by ID to keep the oldest/first one
        fys = list(FiscalYear.objects.filter(year_name=year_name).order_by('id'))
        
        if not fys:
            continue
            
        # Keep the first one as the Global Master
        master_fy = fys[0]
        
        # Initialize new global fields on master
        master_fy.is_planning_active = False
        master_fy.is_revision_active = False
        master_fy.save()
        
        # Process ALL records (including master) to create BudgetProposals
        for fy in fys:
            if fy.organization_id:
                # Create Budget Proposal for this organization
                BudgetProposal.objects.get_or_create(
                    organization_id=fy.organization_id,
                    fiscal_year=master_fy,
                    defaults={
                        'status': fy.status,
                        'is_locked': fy.is_locked,
                        'sae_number': fy.sae_number,
                        'sanctioned_at': fy.sae_generated_at,
                    }
                )
            
            # If this is NOT the master FY, re-point everything to Master and delete
            if fy.id != master_fy.id:
                # Re-point related objects
                BudgetAllocation.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                ScheduleOfEstablishment.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                PensionEstimate.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                SupplementaryGrant.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                Reappropriation.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                QuarterlyRelease.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                SAERecord.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                
                # Re-point cross-app dependencies
                Bill.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                Voucher.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                RevenueDemand.objects.filter(fiscal_year=fy).update(fiscal_year=master_fy)
                
                # Delete the duplicate
                fy.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('budgeting', '0024_alter_fiscalyear_unique_together_and_more'),
        ('revenue', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(deduplicate_fiscal_years),
    ]
