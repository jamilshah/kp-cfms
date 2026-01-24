import os
import django
import sys

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def create_admin():
    """Create a default superuser."""
    cnic = '11111-1111111-1'
    email = 'admin@kp.gov.pk'
    password = 'admin'
    
    if not User.objects.filter(cnic=cnic).exists():
        print(f"Creating superuser ({cnic})...")
        User.objects.create_superuser(
            cnic=cnic,
            email=email,
            password=password,
            first_name='System',
            last_name='Admin'
        )
        print(f"Superuser created.\nLogin: {cnic}\nPassword: {password}")
    else:
        print("Superuser already exists.")

if __name__ == '__main__':
    create_admin()
