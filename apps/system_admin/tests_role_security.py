"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Tests for role assignment security and TMA Admin role.
-------------------------------------------------------------------------
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import Group

from apps.users.models import CustomUser, Role
from apps.core.models import Organization, Tehsil, District, Division


class RoleAssignmentSecurityTestCase(TestCase):
    """Test suite for role assignment security features."""
    
    def setUp(self):
        """Set up test data."""
        # Create test roles
        self.super_admin_role = Role.objects.create(
            code='SUPER_ADMIN',
            name='Super Administrator',
            description='Full system access',
            group=Group.objects.create(name='Super Administrator'),
            is_system_role=True
        )
        
        self.tma_admin_role = Role.objects.create(
            code='TMA_ADMIN',
            name='TMA Administrator',
            description='TMA system administrator',
            group=Group.objects.create(name='TMA Administrator'),
            is_system_role=True
        )
        
        self.tmo_role = Role.objects.create(
            code='TMO',
            name='Tehsil Municipal Officer',
            description='TMA approver',
            group=Group.objects.create(name='Tehsil Municipal Officer'),
            is_system_role=True
        )
        
        self.accountant_role = Role.objects.create(
            code='ACCOUNTANT',
            name='Accountant',
            description='Checker role',
            group=Group.objects.create(name='Accountant'),
            is_system_role=True
        )
        
        # Create test organization
        division = Division.objects.create(name='Test Division', code='TD')
        district = District.objects.create(
            division=division,
            name='Test District',
            code='TDT'
        )
        tehsil = Tehsil.objects.create(
            district=district,
            name='Test Tehsil',
            code='TTL'
        )
        self.organization = Organization.objects.create(
            name='Test TMA',
            tehsil=tehsil,
            org_type='TMA'
        )
        
        # Create Provincial Super Admin (no organization)
        self.super_admin = CustomUser.objects.create_user(
            cnic='1234512345671',
            email='superadmin@test.com',
            first_name='Super',
            last_name='Admin',
            password='testpass123',
            is_superuser=True,
            is_staff=True
        )
        self.super_admin.roles.add(self.super_admin_role)
        
        # Create TMA Admin user (with organization)
        self.tma_admin = CustomUser.objects.create_user(
            cnic='1234512345672',
            email='tmaadmin@test.com',
            first_name='TMA',
            last_name='Admin',
            password='testpass123',
            organization=self.organization
        )
        self.tma_admin.roles.add(self.tma_admin_role)
        
        # Create TMO user (with organization)
        self.tmo_user = CustomUser.objects.create_user(
            cnic='1234512345673',
            email='tmo@test.com',
            first_name='Test',
            last_name='TMO',
            password='testpass123',
            organization=self.organization
        )
        self.tmo_user.roles.add(self.tmo_role)
        
        self.client = Client()
    
    def test_tma_admin_role_exists(self):
        """Test that TMA_ADMIN role can be created."""
        self.assertIsNotNone(self.tma_admin_role)
        self.assertEqual(self.tma_admin_role.code, 'TMA_ADMIN')
        self.assertTrue(self.tma_admin_role.is_system_role)
    
    def test_is_tma_admin_helper(self):
        """Test the is_tma_admin() helper method."""
        self.assertTrue(self.tma_admin.is_tma_admin())
        self.assertFalse(self.tmo_user.is_tma_admin())
        self.assertFalse(self.super_admin.is_tma_admin())
    
    def test_super_admin_cannot_assign_super_admin_role_via_form(self):
        """Test that TMA Admin cannot assign SUPER_ADMIN role via form validation."""
        from apps.system_admin.forms import UserForm
        
        form_data = {
            'cnic': '12345-1234567-4',
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'roles': [self.super_admin_role.pk],
            'is_active': True,
        }
        
        # TMA Admin tries to assign SUPER_ADMIN role
        form = UserForm(data=form_data, request_user=self.tma_admin)
        
        # Role should be filtered out from queryset, causing "not one of available choices" error
        self.assertFalse(form.is_valid())
        # The error message will be about invalid choice since queryset filters it out
        self.assertIn('roles', form.errors)
    
    def test_tmo_cannot_assign_super_admin_role_via_form(self):
        """Test that TMO cannot assign SUPER_ADMIN role via form validation."""
        from apps.system_admin.forms import TenantAdminForm
        
        form_data = {
            'cnic': '12345-1234567-5',
            'email': 'another@test.com',
            'first_name': 'Another',
            'last_name': 'User',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'roles': [self.super_admin_role.pk],
            'is_active': True,
        }
        
        # TMO tries to assign SUPER_ADMIN role
        form = TenantAdminForm(
            data=form_data,
            organization=self.organization,
            request_user=self.tmo_user
        )
        
        # Role should be filtered out from queryset, causing "not one of available choices" error
        self.assertFalse(form.is_valid())
        self.assertIn('roles', form.errors)
    
    def test_super_admin_can_assign_super_admin_role(self):
        """Test that Provincial Super Admin CAN assign SUPER_ADMIN role."""
        from apps.system_admin.forms import UserForm
        
        form_data = {
            'cnic': '1234512345676',
            'email': 'newsuperadmin@test.com',
            'first_name': 'New',
            'last_name': 'SuperAdmin',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'roles': [self.super_admin_role.pk],
            'is_active': True,
        }
        
        # Super Admin assigns SUPER_ADMIN role (should succeed)
        form = UserForm(data=form_data, request_user=self.super_admin)
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_tma_admin_can_assign_other_roles(self):
        """Test that TMA Admin CAN assign non-SUPER_ADMIN roles."""
        from apps.system_admin.forms import UserForm
        
        form_data = {
            'cnic': '1234512345677',
            'email': 'accountant@test.com',
            'first_name': 'Test',
            'last_name': 'Accountant',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'roles': [self.accountant_role.pk, self.tmo_role.pk],
            'is_active': True,
        }
        
        # TMA Admin assigns other roles (should succeed)
        form = UserForm(data=form_data, request_user=self.tma_admin)
        self.assertTrue(form.is_valid(), form.errors)
    
    def test_role_queryset_filtered_for_non_superusers(self):
        """Test that role queryset excludes SUPER_ADMIN for non-superusers."""
        from apps.system_admin.forms import UserForm
        
        # TMA Admin sees filtered roles
        form = UserForm(request_user=self.tma_admin)
        role_ids = list(form.fields['roles'].queryset.values_list('id', flat=True))
        self.assertNotIn(self.super_admin_role.pk, role_ids)
        self.assertIn(self.tma_admin_role.pk, role_ids)
        self.assertIn(self.tmo_role.pk, role_ids)
        
        # Super Admin sees all roles
        form_super = UserForm(request_user=self.super_admin)
        role_ids_super = list(form_super.fields['roles'].queryset.values_list('id', flat=True))
        self.assertIn(self.super_admin_role.pk, role_ids_super)
    
    def test_assign_role_form_filtered_for_non_superusers(self):
        """Test that AssignRoleForm excludes SUPER_ADMIN for non-superusers."""
        from apps.system_admin.forms import AssignRoleForm
        
        # TMA Admin sees filtered roles
        form = AssignRoleForm(request_user=self.tma_admin)
        role_ids = list(form.fields['roles'].queryset.values_list('id', flat=True))
        self.assertNotIn(self.super_admin_role.pk, role_ids)
        
        # Super Admin sees all roles
        form_super = AssignRoleForm(request_user=self.super_admin)
        role_ids_super = list(form_super.fields['roles'].queryset.values_list('id', flat=True))
        self.assertIn(self.super_admin_role.pk, role_ids_super)
    
    def test_tenant_admin_required_mixin_allows_tma_admin(self):
        """Test that TenantAdminRequiredMixin allows TMA_ADMIN role."""
        from apps.users.permissions import TenantAdminRequiredMixin
        from django.http import HttpRequest
        from django.views import View
        
        class TestView(TenantAdminRequiredMixin, View):
            pass
        
        view = TestView()
        request = HttpRequest()
        request.user = self.tma_admin
        view.request = request
        
        self.assertTrue(view.test_func())
    
    def test_tenant_admin_required_mixin_allows_tmo(self):
        """Test that TenantAdminRequiredMixin still allows TMO role."""
        from apps.users.permissions import TenantAdminRequiredMixin
        from django.http import HttpRequest
        from django.views import View
        
        class TestView(TenantAdminRequiredMixin, View):
            pass
        
        view = TestView()
        request = HttpRequest()
        request.user = self.tmo_user
        view.request = request
        
        self.assertTrue(view.test_func())
    
    def test_tenant_admin_required_mixin_allows_super_admin(self):
        """Test that TenantAdminRequiredMixin allows Provincial Super Admin."""
        from apps.users.permissions import TenantAdminRequiredMixin
        from django.http import HttpRequest
        from django.views import View
        
        class TestView(TenantAdminRequiredMixin, View):
            pass
        
        view = TestView()
        request = HttpRequest()
        request.user = self.super_admin
        view.request = request
        
        self.assertTrue(view.test_func())
    
    def test_default_role_for_tenant_admin_is_tma_admin(self):
        """Test that default role for TenantAdminForm is TMA_ADMIN."""
        from apps.system_admin.forms import TenantAdminForm
        
        form = TenantAdminForm(organization=self.organization, request_user=self.super_admin)
        initial_roles = form.fields['roles'].initial
        self.assertIn(self.tma_admin_role.pk, initial_roles)


class RoleAssignmentViewTestCase(TestCase):
    """Test suite for role assignment views with security checks."""
    
    def setUp(self):
        """Set up test data."""
        # Create test roles
        self.super_admin_role = Role.objects.create(
            code='SUPER_ADMIN',
            name='Super Administrator',
            description='Full system access',
            group=Group.objects.create(name='Super Administrator'),
            is_system_role=True
        )
        
        self.tma_admin_role = Role.objects.create(
            code='TMA_ADMIN',
            name='TMA Administrator',
            description='TMA system administrator',
            group=Group.objects.create(name='TMA Administrator'),
            is_system_role=True
        )
        
        self.tmo_role = Role.objects.create(
            code='TMO',
            name='Tehsil Municipal Officer',
            description='TMA approver',
            group=Group.objects.create(name='Tehsil Municipal Officer'),
            is_system_role=True
        )
        
        # Create test organization
        division = Division.objects.create(name='Test Division', code='TD')
        district = District.objects.create(
            division=division,
            name='Test District',
            code='TDT'
        )
        tehsil = Tehsil.objects.create(
            district=district,
            name='Test Tehsil',
            code='TTL'
        )
        self.organization = Organization.objects.create(
            name='Test TMA',
            tehsil=tehsil,
            org_type='TMA'
        )
        
        # Create Provincial Super Admin
        self.super_admin = CustomUser.objects.create_user(
            cnic='1234512345671',
            email='superadmin@test.com',
            first_name='Super',
            last_name='Admin',
            password='testpass123',
            is_superuser=True,
            is_staff=True
        )
        self.super_admin.roles.add(self.super_admin_role)
        
        # Create TMA Admin
        self.tma_admin = CustomUser.objects.create_user(
            cnic='1234512345672',
            email='tmaadmin@test.com',
            first_name='TMA',
            last_name='Admin',
            password='testpass123',
            organization=self.organization
        )
        self.tma_admin.roles.add(self.tma_admin_role)
        
        # Create regular user for role assignment tests
        self.regular_user = CustomUser.objects.create_user(
            cnic='1234512345673',
            email='regular@test.com',
            first_name='Regular',
            last_name='User',
            password='testpass123',
            organization=self.organization
        )
        
        self.client = Client()
    
    def test_tma_admin_cannot_create_user_with_super_admin_role_via_view(self):
        """Test that TMA Admin cannot create user with SUPER_ADMIN via view."""
        self.client.login(cnic='1234512345672', password='testpass123')
        
        url = reverse('system_admin:tenant_user_create', kwargs={'org_pk': self.organization.pk})
        data = {
            'cnic': '12345-1234567-8',
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'roles': [self.super_admin_role.pk],
            'is_active': True,
        }
        
        response = self.client.post(url, data)
        
        # Could be redirect (if role silently ignored) or 200 with errors
        # Either way, verify role was NOT assigned
        if response.status_code == 302:
            # If it redirected, check no user was created with SUPER_ADMIN
            created_user = CustomUser.objects.filter(cnic='1234512345678').first()
            if created_user:
                self.assertFalse(created_user.roles.filter(code='SUPER_ADMIN').exists())
        else:
            # Form had validation errors
            self.assertEqual(response.status_code, 200)
    
    def test_super_admin_can_create_user_with_super_admin_role_via_view(self):
        """Test that Provincial Super Admin CAN create user with SUPER_ADMIN via view."""
        self.client.login(cnic='1234512345671', password='testpass123')
        
        url = reverse('system_admin:tenant_user_create', kwargs={'org_pk': self.organization.pk})
        data = {
            'cnic': '12345-1234568-1',
            'email': 'newsuperadmin@test.com',
            'first_name': 'New',
            'last_name': 'SuperAdmin',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'roles': [self.super_admin_role.pk],
            'is_active': True,
        }
        
        response = self.client.post(url, data)
        
        # Should succeed and redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify user was created with SUPER_ADMIN role
        new_user = CustomUser.objects.get(cnic='1234512345681')
        self.assertTrue(new_user.roles.filter(code='SUPER_ADMIN').exists())
    
    def test_tma_admin_cannot_assign_super_admin_role_via_assign_role_view(self):
        """Test that TMA Admin cannot assign SUPER_ADMIN via AssignRoleView."""
        self.client.login(cnic='1234512345672', password='testpass123')
        
        url = reverse('system_admin:assign_role', kwargs={'pk': self.regular_user.pk})
        data = {
            'roles': [self.super_admin_role.pk],
        }
        
        response = self.client.post(url, data)
        
        # Could be redirect or error - either way verify role NOT assigned
        # Verify role was NOT assigned regardless of response
        self.regular_user.refresh_from_db()
        self.assertFalse(self.regular_user.roles.filter(code='SUPER_ADMIN').exists())


class RoleModelTestCase(TestCase):
    """Test suite for Role model and related functionality."""
    
    def test_role_code_enum_includes_tma_admin(self):
        """Test that RoleCode enum includes TMA_ADMIN."""
        from apps.users.models import RoleCode
        
        self.assertTrue(hasattr(RoleCode, 'TMA_ADMIN'))
        self.assertEqual(RoleCode.TMA_ADMIN.value, 'TMA_ADMIN')
        self.assertEqual(RoleCode.TMA_ADMIN.label, 'TMA Administrator')
