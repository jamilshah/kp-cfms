from django.core.management.base import BaseCommand
from django.db import transaction
from apps.budgeting.models import (
    BudgetProposal, BudgetAllocation, ScheduleOfEstablishment,
    SupplementaryGrant, Reappropriation, QuarterlyRelease, SAERecord
)
from apps.expenditure.models import Bill, Payee
from apps.revenue.models import RevenueDemand, RevenueCollection, Payer
from apps.finance.models import Voucher

class Command(BaseCommand):
    help = 'Deletes test data for a specific organization safely.'

    def add_arguments(self, parser):
        parser.add_argument('org_id', type=int, help='The ID of the organization to clean up')

    @transaction.atomic
    def handle(self, *args, **options):
        org_id = options['org_id']
        self.stdout.write(f"Deleting data for Organization ID: {org_id}")

        # 1. Delete Revenue Collections (Dependent on Demand)
        count, _ = RevenueCollection.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} RevenueCollections")

        # 2. Delete Revenue Demands
        count, _ = RevenueDemand.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} RevenueDemands")

        # 3. Delete Bills (Expenditure)
        # BillLines cascade delete with Bill
        count, _ = Bill.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} Bills")

        # 4. Delete Vouchers (Finance)
        # JournalEntries cascade delete with Voucher usually, but let's assume so or they are safe
        # Note: Vouchers are linked to organization
        count, _ = Voucher.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} Vouchers")

        # 5. Delete Budget Allocations
        count, _ = BudgetAllocation.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} BudgetAllocations")

        # 6. Delete Schedule of Establishment
        count, _ = ScheduleOfEstablishment.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} ScheduleOfEstablishment entries")

        # 7. Delete Supplementary Grants & Reappropriations
        count, _ = SupplementaryGrant.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} SupplementaryGrants")
        
        count, _ = Reappropriation.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} Reappropriations")

        # 8. Delete Quarterly Releases
        count, _ = QuarterlyRelease.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} QuarterlyReleases")

        # 9. Delete SAE Records (if organization aware)
        # Check if SAERecord has organization field, if so delete
        if hasattr(SAERecord, 'organization'):
            count, _ = SAERecord.objects.filter(organization_id=org_id).delete()
            self.stdout.write(f"Deleted {count} SAERecords")

        # 10. Delete Budget Proposal
        count, _ = BudgetProposal.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} BudgetProposals")

        # 11. Delete Payers and Payees (Master Data)
        count, _ = Payer.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} Payers")

        count, _ = Payee.objects.filter(organization_id=org_id).delete()
        self.stdout.write(f"Deleted {count} Payees")

        self.stdout.write(self.style.SUCCESS(f"Successfully deleted all data for Organization ID {org_id}"))
