import os, django, sys
sys.path.insert(0, 'd:/apps/jango/cfms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.test import Client
from apps.users.models import CustomUser

cnic='1111111111111'
pwd='TempPass1234'
print('User exists:', CustomUser.objects.filter(cnic=cnic).exists())
client=Client()
# First login
r=client.post('/admin/login/?next=/admin/', {'username':cnic,'password':pwd}, follow=True)
print('First login status:', r.status_code)
print('First redirect chain:', r.redirect_chain)
print('Session cookie present after first login:', 'sessionid' in client.cookies)
# Logout
r2=client.get('/admin/logout/', follow=True)
print('Logout status:', r2.status_code)
print('Session cookie present after logout:', 'sessionid' in client.cookies)
# Second login
r3=client.post('/admin/login/?next=/admin/', {'username':cnic,'password':pwd}, follow=True)
print('Second login status:', r3.status_code)
print('Second redirect chain:', r3.redirect_chain)
print('Session cookie present after second login:', 'sessionid' in client.cookies)
# Print small part of content to detect errors
print('Second login content snippet:', r3.content[:800])
