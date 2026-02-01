"""
Management command to unlock a fiscal year.
"""
from django.core.management.base import BaseCommand
from apps.budgeting.models import FiscalYear


class Command(BaseCommand):
    help = 'Unlock a fiscal year to allow transactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=str,
            help='Fiscal year name (e.g., 2025-26)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Unlock all fiscal years',
        )

    def handle(self, *args, **options):
        year_name = options.get('year')
        unlock_all = options.get('all')

        if unlock_all:
            count = FiscalYear.objects.filter(is_locked=True).update(is_locked=False)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully unlocked {count} fiscal year(s)')
            )
        elif year_name:
            try:
                fy = FiscalYear.objects.get(year_name=year_name)
                fy.is_locked = False
                fy.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully unlocked fiscal year: {fy.year_name}')
                )
            except FiscalYear.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Fiscal year "{year_name}" not found')
                )
        else:
            # Show all fiscal years
            self.stdout.write('Available fiscal years:')
            for fy in FiscalYear.objects.all().order_by('-start_date'):
                status = 'LOCKED' if fy.is_locked else 'OPEN'
                self.stdout.write(f'  - {fy.year_name} ({fy.organization.name}) [{status}]')
            self.stdout.write('\nUsage:')
            self.stdout.write('  python manage.py unlock_fiscal_year --year "2025-26"')
            self.stdout.write('  python manage.py unlock_fiscal_year --all')
