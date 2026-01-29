from django.core.management.base import BaseCommand
from apps.finance.models import FunctionCode  # Adjust import if model is in 'budgeting'

class Command(BaseCommand):
    help = 'Seed Standard KP TMA Function Codes (PIFRA Element 3)'

    def handle(self, *args, **kwargs):
        # Format: (Code, Description)
        functions = [
            # --- 01 General Public Service ---
            ('011101', 'Executive & Legislative Organs (Nazim/Chairman)'),
            ('011103', 'Municipal Administration (TMO/Chief Officer)'),
            ('011108', 'Local Government Board'),
            ('011205', 'Tax Management (Octroi/Tax Branch)'),
            ('015101', 'Financial Management (Accounts Branch)'),
            
            # --- 03 Public Order & Safety ---
            ('032102', 'Fire Protection (Fire Brigade)'),
            
            # --- 04 Economic Affairs ---
            ('041300', 'General Economic Affairs (Markets/Plazas)'),
            ('041302', 'Agriculture & Livestock (Cattle Fair/Mandi)'),
            ('041310', 'Road Transport (Bus Stands/Adda)'),
            ('045101', 'Roads & Streets (Infrastructure Works)'),
            ('045102', 'Building Maintenance (TMA Buildings)'),
            
            # --- 05 Environment Protection ---
            ('055101', 'Waste Management (Sanitation/Solid Waste)'),
            ('055102', 'Sewerage Systems'),
            
            # --- 06 Housing & Amenities ---
            ('061101', 'Housing Development (Housing Schemes)'),
            ('062101', 'Community Development (Town Planning/Maps)'),
            ('062201', 'Rural Development'),
            ('063102', 'Water Supply (Tube Wells/Pipes)'),
            ('064101', 'Street Lights'),
            
            # --- 08 Recreation & Culture ---
            ('081101', 'Recreational Services (Sports Grounds)'),
            ('082120', 'Parks & Gardens'),
            ('084103', 'Community Centers (Libraries/Halls)'),
            ('086101', 'Religious Affairs (Eid Gah/Graveyards)'),
        ]

        self.stdout.write(f"Seeding {len(functions)} functions...")

        for code, desc in functions:
            obj, created = FunctionCode.objects.get_or_create(
                code=code,
                defaults={'name': desc, 'description': desc}
            )
            if created:
                self.stdout.write(f"Created: {code} - {desc}")
            else:
                self.stdout.write(f"Exists: {code}")

        self.stdout.write(self.style.SUCCESS("Function Codes Seeded Successfully!"))