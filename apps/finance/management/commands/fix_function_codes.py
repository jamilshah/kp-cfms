from django.core.management.base import BaseCommand
from apps.finance.models import FunctionCode

class Command(BaseCommand):
    help = 'Fix Functional Classification Code descriptions'

    def handle(self, *args, **options):
        # Map Code -> Proper Name
        mapping = {
            'AD': 'General Administration',
            'FR': 'Fire & Rescue',
            'MK': 'Markets & Slaughter Houses',
            'PK': 'Parks & Recreation',
            'RS': 'Roads & Streets',
            'SD': 'Sanitation & Solid Waste',
            'SH': 'Slaughter House',
            'SL': 'Street Lights',
            'SW': 'Sewerage & Drainage',
            'UP': 'Urban Planning',
            'WS': 'Water Supply'
        }
        
        count = 0
        for code, name in mapping.items():
            updated = FunctionCode.objects.filter(code=code).update(name=name)
            if updated:
                self.stdout.write(f"Updated {code} -> {name}")
                count += 1
            else:
                self.stdout.write(self.style.WARNING(f"Code {code} not found, skipping."))
                
        self.stdout.write(self.style.SUCCESS(f"Successfully updated names for {count} function codes"))
