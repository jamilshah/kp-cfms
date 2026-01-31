"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Views for System Admin module - Superuser dashboard,
             master data seeding, TMA provisioning, and user management.
-------------------------------------------------------------------------
"""
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.management import call_command
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, FormView, ListView, View, UpdateView, DeleteView, CreateView

from apps.core.models import Organization, District, Division
from apps.users.models import CustomUser, Role
from apps.users.permissions import SuperAdminRequiredMixin, TenantAdminRequiredMixin
from apps.budgeting.models import FiscalYear

from .forms import OrganizationForm, TenantAdminForm, UserForm, AssignRoleForm, RoleForm


class SystemDashboardView(LoginRequiredMixin, SuperAdminRequiredMixin, TemplateView):
    """
    System Admin Dashboard showing system-wide statistics.
    
    Displays:
    - Total TMAs/Organizations
    - Total Users
    - System Health indicators
    - Quick action buttons
    """
    template_name = 'system_admin/dashboard.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # Organization stats
        context['total_organizations'] = Organization.objects.count()
        context['active_organizations'] = Organization.objects.filter(is_active=True).count()
        
        # User stats
        context['total_users'] = CustomUser.objects.count()
        context['active_users'] = CustomUser.objects.filter(is_active=True).count()
        context['staff_users'] = CustomUser.objects.filter(is_staff=True).count()
        
        # Role distribution
        context['roles'] = Role.objects.annotate(
            user_count=Count('users')
        ).order_by('name')
        
        # Geographic distribution
        context['divisions'] = Division.objects.filter(is_active=True).count()
        context['districts'] = District.objects.filter(is_active=True).count()
        
        # Fiscal year status
        context['active_fiscal_year'] = FiscalYear.objects.filter(
            is_active=True
        ).first()
        context['total_fiscal_years'] = FiscalYear.objects.count()
        
        # Recent users
        context['recent_users'] = CustomUser.objects.order_by('-date_joined')[:5]
        
        # Organizations by type
        context['orgs_by_type'] = Organization.objects.values(
            'org_type'
        ).annotate(count=Count('id')).order_by('org_type')
        
        return context


class MasterDataSeedView(LoginRequiredMixin, SuperAdminRequiredMixin, TemplateView):
    """
    View for triggering master data seeding commands.
    
    Provides UI to run management commands for:
    - Seeding funds
    - Importing BPS scales
    - Seeding departments
    - Setting up fiscal year
    - Seeding roles
    """
    template_name = 'system_admin/master_data_seed.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # Available commands with descriptions
        context['commands'] = [
            {
                'name': 'seed_roles',
                'title': 'Seed System Roles',
                'description': 'Creates standard system roles (TMO, Accountant, Cashier, etc.)',
                'icon': 'bi-person-badge'
            },
            {
                'name': 'setup_funds',
                'title': 'Setup Fund Types',
                'description': 'Creates fund types (PUGF, Non-PUGF, Development, etc.)',
                'icon': 'bi-bank'
            },
            {
                'name': 'import_bps_scales',
                'title': 'Import BPS Scales',
                'description': 'Imports Basic Pay Scale data from CSV.',
                'icon': 'bi-table'
            },
            {
                'name': 'seed_departments',
                'title': 'Seed Departments',
                'description': 'Creates standard TMA departments and designations.',
                'icon': 'bi-building'
            },
            {
                'name': 'setup_fy',
                'title': 'Initialize Fiscal Year',
                'description': 'Creates a new fiscal year with proper date ranges.',
                'icon': 'bi-calendar3'
            },
            {
                'name': 'import_coa',
                'title': 'Import Chart of Accounts',
                'description': 'Imports budget heads from CoA.csv file.',
                'icon': 'bi-journal-text'
            },
            {
                'name': 'import_locations',
                'title': 'Import Locations',
                'description': 'Imports Divisions, Districts, and TMAs from CSV.',
                'icon': 'bi-geo-alt'
            },
        ]
        
        # Add funds, functions, and departments for CoA import modal
        from apps.finance.models import Fund, FunctionCode
        from apps.budgeting.models import Department
        context['funds'] = Fund.objects.filter(is_active=True).order_by('code')
        context['functions'] = FunctionCode.objects.filter(is_active=True).order_by('code')
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        
        return context
    
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Handle command execution."""
        command_name = request.POST.get('command')
        
        # Map of allowed commands and their management command names
        allowed_commands = {
            'seed_roles': 'seed_roles',
            'setup_funds': 'setup_funds',
            'import_bps_scales': 'import_bps_scales',
            'seed_departments': 'seed_departments',
            'setup_fy': 'setup_fy',
            'import_coa': 'import_coa',
            'import_locations': 'import_locations',
            'migrate_roles': 'migrate_roles',
        }
        
        if command_name not in allowed_commands:
            messages.error(request, f'Unknown command: {command_name}')
            return redirect('system_admin:master_data_seed')
        
        try:
            # Handle import_coa with extra parameters
            if command_name == 'import_coa':
                fund_code = request.POST.get('fund', 'GEN')
                function_code = request.POST.get('function')
                department_id = request.POST.get('department')
                skip_budget_heads = request.POST.get('skip_budget_heads') == 'on'
                
                # Prepare arguments
                kwargs = {
                    'fund': fund_code,
                    'skip_budget_heads': skip_budget_heads
                }
                
                if function_code:
                    kwargs['function'] = function_code
                
                if department_id:
                    kwargs['department_id'] = department_id
                
                call_command(allowed_commands[command_name], **kwargs)
                
                if skip_budget_heads:
                    messages.success(request, f'Successfully imported Master Data (GlobalHeads only).')
                elif department_id:
                    messages.success(request, f'Successfully imported CoA for Fund={fund_code} and selected Department.')
                else:
                    messages.success(request, f'Successfully imported CoA for Fund={fund_code}, Function={function_code}.')
            else:
                call_command(allowed_commands[command_name])
                messages.success(request, f'Successfully executed: {command_name}')
        except Exception as e:
            messages.error(request, f'Error executing {command_name}: {str(e)}')
        
        return redirect('system_admin:master_data_seed')


class ProvisionOrganizationView(LoginRequiredMixin, SuperAdminRequiredMixin, FormView):
    """
    View for provisioning new Organizations (TMAs).
    
    Creates a new TMA with proper configuration.
    """
    template_name = 'system_admin/provision_tma.html'
    form_class = OrganizationForm
    success_url = reverse_lazy('system_admin:organization_list')
    
    def form_valid(self, form):
        organization = form.save()
        messages.success(
            self.request,
            f'Organization "{organization.name}" created successfully.'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Provision New TMA'
        return context


class OrganizationListView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """List all organizations."""
    model = Organization
    template_name = 'system_admin/organization_list.html'
    context_object_name = 'organizations'
    paginate_by = 25
    
    def get_queryset(self):
        return Organization.objects.select_related(
            'tehsil', 'tehsil__district', 'tehsil__district__division'
        ).annotate(
            user_count=Count('users')
        ).order_by('tehsil__district__division__name', 'tehsil__district__name', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.core.models import Tehsil
        context['tehsils'] = Tehsil.objects.filter(is_active=True).order_by('name')
        return context


class CreateTenantAdminView(LoginRequiredMixin, SuperAdminRequiredMixin, FormView):
    """
    View for creating TMA Admin users.
    
    Creates a user and assigns TMO or Admin role.
    """
    template_name = 'system_admin/user_create.html'
    form_class = TenantAdminForm
    
    def get_success_url(self):
        return reverse_lazy('system_admin:tenant_user_list', kwargs={'org_pk': self.kwargs['org_pk']})
    
    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs['org_pk'])
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.get_organization()
        return kwargs
    
    def form_valid(self, form):
        user = form.save(commit=False)
        user.organization = self.get_organization()
        user.save()
        
        # Assign roles
        roles = form.cleaned_data.get('roles', [])
        if roles:
            user.roles.set(roles)
        
        messages.success(
            self.request,
            f'Admin user "{user.get_full_name()}" created for {user.organization}.'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create TMA Admin'
        context['organization'] = self.get_organization()
        return context


class SystemUserListView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """List all users across the system (Super Admin only)."""
    model = CustomUser
    template_name = 'system_admin/system_user_list.html'
    context_object_name = 'users'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = CustomUser.objects.select_related('organization').prefetch_related('roles')
        
        # Filter by organization if provided
        org_id = self.request.GET.get('organization')
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        
        # Filter by role if provided
        role_id = self.request.GET.get('role')
        if role_id:
            queryset = queryset.filter(roles__id=role_id)
        
        return queryset.order_by('first_name', 'last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations'] = Organization.objects.filter(is_active=True)
        context['roles'] = Role.objects.all()
        context['selected_org'] = self.request.GET.get('organization', '')
        context['selected_role'] = self.request.GET.get('role', '')
        return context


class RoleListView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """List all roles."""
    model = Role
    template_name = 'system_admin/role_list.html'
    context_object_name = 'roles'
    
    def get_queryset(self):
        return Role.objects.annotate(
            user_count=Count('users')
        ).order_by('name')


# ============================================================
# TMA Admin Views (for managing users within an organization)
# ============================================================

class TenantUserListView(LoginRequiredMixin, TenantAdminRequiredMixin, ListView):
    """
    List users within a specific organization.
    
    Accessible by Super Admins or TMA Admins (for their own TMA).
    """
    model = CustomUser
    template_name = 'system_admin/tenant_user_list.html'
    context_object_name = 'users'
    paginate_by = 25
    
    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs['org_pk'])
    
    def get_queryset(self):
        organization = self.get_organization()
        
        # Non-superusers can only view their own organization
        if not self.request.user.is_superuser and self.request.user.organization != organization:
            return CustomUser.objects.none()
        
        return CustomUser.objects.filter(
            organization=organization
        ).prefetch_related('roles').order_by('first_name', 'last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organization'] = self.get_organization()
        context['roles'] = Role.objects.all()
        return context


class TenantUserCreateView(LoginRequiredMixin, TenantAdminRequiredMixin, FormView):
    """Create a new user within the TMA."""
    template_name = 'system_admin/tenant_user_form.html'
    form_class = UserForm
    
    def get_success_url(self):
        return reverse_lazy('system_admin:tenant_user_list', kwargs={'org_pk': self.kwargs['org_pk']})
    
    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs['org_pk'])
    
    def form_valid(self, form):
        user = form.save(commit=False)
        user.organization = self.get_organization()
        
        # Set password if provided
        password1 = form.cleaned_data.get('password1')
        if password1:
            user.set_password(password1)
        
        user.save()
        
        # Assign roles
        roles = form.cleaned_data.get('roles', [])
        if roles:
            user.roles.set(roles)
        
        messages.success(self.request, f'User "{user.get_full_name()}" created.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create User'
        context['organization'] = self.get_organization()
        context['is_edit'] = False
        return context


class TenantUserEditView(LoginRequiredMixin, TenantAdminRequiredMixin, FormView):
    """Edit an existing user within the TMA."""
    template_name = 'system_admin/tenant_user_form.html'
    form_class = UserForm
    
    def get_success_url(self):
        return reverse_lazy('system_admin:tenant_user_list', kwargs={'org_pk': self.kwargs['org_pk']})
    
    def get_organization(self):
        return get_object_or_404(Organization, pk=self.kwargs['org_pk'])
    
    def get_user_instance(self):
        return get_object_or_404(
            CustomUser, 
            pk=self.kwargs['pk'],
            organization_id=self.kwargs['org_pk']
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_user_instance()
        kwargs['is_edit'] = True
        return kwargs
    
    def form_valid(self, form):
        user = form.save()
        
        # Update roles
        roles = form.cleaned_data.get('roles', [])
        if roles:
            user.roles.set(roles)
        
        messages.success(self.request, f'User "{user.get_full_name()}" updated.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit User'
        context['organization'] = self.get_organization()
        context['is_edit'] = True
        return context


class AssignRoleView(LoginRequiredMixin, TenantAdminRequiredMixin, FormView):
    """
    View for assigning roles to a specific user.
    """
    template_name = 'system_admin/assign_role.html'
    form_class = AssignRoleForm
    
    def get_success_url(self):
        target_user = self.get_target_user()
        if target_user.organization:
            return reverse_lazy('system_admin:tenant_user_list', kwargs={'org_pk': target_user.organization.pk})
        return reverse_lazy('system_admin:system_user_list')
    
    def get_target_user(self):
        return get_object_or_404(CustomUser, pk=self.kwargs['pk'])
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        target_user = self.get_target_user()
        kwargs['initial'] = {'roles': target_user.roles.all()}
        return kwargs
    
    def form_valid(self, form):
        target_user = self.get_target_user()
        roles = form.cleaned_data['roles']
        
        # Clear existing roles and assign new ones
        target_user.roles.clear()
        target_user.roles.add(*roles)
        
        messages.success(
            self.request,
            f'Roles updated for {target_user.get_full_name()}.'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['target_user'] = self.get_target_user()
        context['roles'] = Role.objects.all()
        return context




class RoleCreateView(LoginRequiredMixin, SuperAdminRequiredMixin, CreateView):
    """Create a new role."""
    model = Role
    form_class = RoleForm
    template_name = 'system_admin/role_form.html'
    success_url = reverse_lazy('system_admin:role_list')
    
    def form_valid(self, form):
        form.instance.is_system_role = False
        # Generate code from name if not provided (though code isn't in form, so we might need to handle this)
        # For now, let's assume auto-generation or we need to add 'code' to the form for creation only.
        # Actually RoleForm only has name/description.
        # Let's auto-generate code from name.
        import re
        name = form.cleaned_data['name']
        code = re.sub(r'[^A-Z0-9]', '_', name.upper())
        form.instance.code = code
        
        messages.success(self.request, f'Role "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class RoleUpdateView(LoginRequiredMixin, SuperAdminRequiredMixin, UpdateView):
    """Update role details."""
    model = Role
    form_class = RoleForm
    template_name = 'system_admin/role_form.html'
    success_url = reverse_lazy('system_admin:role_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Role "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class RoleDeleteView(LoginRequiredMixin, SuperAdminRequiredMixin, DeleteView):
    """Delete a role (System roles cannot be deleted)."""
    model = Role
    template_name = 'system_admin/role_confirm_delete.html'
    success_url = reverse_lazy('system_admin:role_list')
    
    def dispatch(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system_role:
            messages.error(request, 'System roles cannot be deleted.')
            return redirect('system_admin:role_list')
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Role deleted successfully.')
        return super().delete(request, *args, **kwargs)
