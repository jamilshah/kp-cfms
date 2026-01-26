"""
Management command to seed initial Departments.
"""
from django.core.management.base import BaseCommand
from apps.budgeting.models import Department

INITIAL_DEPARTMENTS = [
    'Administration',
    'Finance',
    'Regulations',
    'Infrastructure / Engineering',
    'Water Supply',
    'Sanitation',
    'Planning',
    'Fire Brigade',
    'Parks & Slaughter House',
    'General',
    'Education',
    'Health'
]

class Command(BaseCommand):
    help = 'Seed initial Departments'

    def handle(self, *args, **kwargs):
        count = 0
        for name in INITIAL_DEPARTMENTS:
            obj, created = Department.objects.get_or_create(name=name)
            if created:
                count += 1
                self.stdout.write(f'Created: {name}')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {count} departments.'))
