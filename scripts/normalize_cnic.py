"""
Script to normalize existing CNIC values in the database by stripping non-digits.
Run this once after updating the CustomUser model to auto-normalize CNIC.
"""
import os, django, sys, re
sys.path.insert(0, 'd:/apps/jango/cfms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()

from apps.users.models import CustomUser

users = CustomUser.objects.all()
updated = 0

for user in users:
    old_cnic = user.cnic
    normalized = re.sub(r'\D', '', old_cnic)
    
    if old_cnic != normalized:
        user.cnic = normalized
        try:
            user.save()
            print(f'Updated: {old_cnic} -> {normalized} ({user.email})')
            updated += 1
        except Exception as e:
            print(f'Error updating {old_cnic}: {e}')

print(f'\nTotal users updated: {updated}')
