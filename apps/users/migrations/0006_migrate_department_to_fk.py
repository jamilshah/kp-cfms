# Generated manually to handle CharField to ForeignKey conversion

from django.db import migrations, models
import django.db.models.deletion


def migrate_department_data(apps, schema_editor):
    """
    Migrate department text values to ForeignKey relationships.
    Match department names to Department model instances.
    """
    CustomUser = apps.get_model('users', 'CustomUser')
    Department = apps.get_model('budgeting', 'Department')
    
    # Get all users with department text
    users_with_dept = CustomUser.objects.exclude(department='').exclude(department__isnull=True)
    
    print(f"\nMigrating {users_with_dept.count()} users with department assignments...")
    
    migrated_count = 0
    unmatched_count = 0
    unmatched_names = set()
    
    for user in users_with_dept:
        dept_text = user.department.strip()
        if not dept_text:
            continue
        
        # Try to find matching department by name (case-insensitive)
        try:
            dept = Department.objects.get(name__iexact=dept_text)
            user.department_new = dept
            user.save(update_fields=['department_new'])
            migrated_count += 1
        except Department.DoesNotExist:
            # Try partial match
            dept_matches = Department.objects.filter(name__icontains=dept_text)
            if dept_matches.count() == 1:
                user.department_new = dept_matches.first()
                user.save(update_fields=['department_new'])
                migrated_count += 1
            else:
                unmatched_count += 1
                unmatched_names.add(dept_text)
                print(f"  WARNING: No match for department '{dept_text}' (user: {user.cnic})")
        except Department.MultipleObjectsReturned:
            unmatched_count += 1
            unmatched_names.add(dept_text)
            print(f"  WARNING: Multiple matches for '{dept_text}' (user: {user.cnic})")
    
    print(f"  ✓ Migrated: {migrated_count} users")
    if unmatched_count > 0:
        print(f"  ⚠ Unmatched: {unmatched_count} users")
        print(f"  Unmatched department names: {', '.join(sorted(unmatched_names))}")
        print(f"  These users will have no department assigned. You can fix this manually later.")


def reverse_migrate(apps, schema_editor):
    """Reverse migration - copy ForeignKey back to CharField."""
    CustomUser = apps.get_model('users', 'CustomUser')
    
    for user in CustomUser.objects.filter(department_new__isnull=False):
        user.department = user.department_new.name
        user.save(update_fields=['department'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_alter_customuser_role_role_customuser_roles'),
        ('budgeting', '0028_alter_budgetallocation_options'),
    ]

    operations = [
        # Step 1: Add new ForeignKey field (nullable)
        migrations.AddField(
            model_name='customuser',
            name='department_new',
            field=models.ForeignKey(
                blank=True,
                help_text='Department/wing this user belongs to for access control.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='users_new',
                to='budgeting.department',
                verbose_name='Department'
            ),
        ),
        # Step 2: Migrate data from CharField to ForeignKey
        migrations.RunPython(migrate_department_data, reverse_migrate),
        # Step 3: Remove old CharField
        migrations.RemoveField(
            model_name='customuser',
            name='department',
        ),
        # Step 4: Rename new field to original name
        migrations.RenameField(
            model_name='customuser',
            old_name='department_new',
            new_name='department',
        ),
    ]
