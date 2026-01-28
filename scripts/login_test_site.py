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
# First site login
r=client.post('/login/', {'username':cnic,'password':pwd}, follow=True, HTTP_HOST='127.0.0.1')
print('Site first login status:', r.status_code)
print('Site first redirect chain:', r.redirect_chain)
print('Session cookie present after first login:', 'sessionid' in client.cookies)
# Logout via site
r2=client.get('/logout/', follow=True, HTTP_HOST='127.0.0.1')
print('Site logout status:', r2.status_code)
print('Session cookie present after logout:', 'sessionid' in client.cookies)
# Second site login
r3=client.post('/login/', {'username':cnic,'password':pwd}, follow=True, HTTP_HOST='127.0.0.1')
print('Site second login status:', r3.status_code)
print('Site second redirect chain:', r3.redirect_chain)
print('Session cookie present after second login:', 'sessionid' in client.cookies)
print('Second login content snippet:', r3.content[:800])
