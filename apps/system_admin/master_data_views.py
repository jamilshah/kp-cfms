"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Master Data CRUD views with CSV template download support.
-------------------------------------------------------------------------
"""
import csv
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View

from apps.core.models import Division, District, Tehsil, Organization
from apps.finance.models import Fund, BudgetHead
from apps.budgeting.models import Department, DesignationMaster, BPSSalaryScale
from apps.users.models import Role
from apps.users.permissions import SuperAdminRequiredMixin


# =============================================================================
# CSV Template Download Views
# =============================================================================

class CSVTemplateDownloadView(LoginRequiredMixin, SuperAdminRequiredMixin, View):
    """Base view for downloading CSV templates."""
    
    filename = 'template.csv'
    headers = []
    sample_rows = []
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.filename}"'
        
        writer = csv.writer(response)
        writer.writerow(self.headers)
        for row in self.sample_rows:
            writer.writerow(row)
        
        return response


class LocationsTemplateView(CSVTemplateDownloadView):
    """Download CSV template for Divisions, Districts, and Tehsils."""
    filename = 'locations_template.csv'
    headers = ['division_name', 'district_name', 'tehsil_name', 'is_active']
    sample_rows = [
        ['Peshawar', 'Peshawar', 'Peshawar City', 'TRUE'],
        ['Peshawar', 'Peshawar', 'Peshawar Rural', 'TRUE'],
        ['Peshawar', 'Charsadda', 'Charsadda', 'TRUE'],
        ['Hazara', 'Abbottabad', 'Abbottabad', 'TRUE'],
        ['Hazara', 'Abbottabad', 'Havelian', 'TRUE'],
    ]


class FundsTemplateView(CSVTemplateDownloadView):
    """Download CSV template for Funds."""
    filename = 'funds_template.csv'
    headers = ['name', 'code', 'fund_type', 'description', 'is_active']
    sample_rows = [
        ['Provincial Unified General Fund', 'PUGF', 'PUGF', 'Provincial salary funding', 'TRUE'],
        ['Local Fund', 'LOCAL', 'NON_PUGF', 'TMA own source revenue', 'TRUE'],
        ['Development Fund', 'DEV', 'DEVELOPMENT', 'Capital projects', 'TRUE'],
        ['Deposit Fund', 'DEP', 'DEPOSIT', 'Security deposits', 'TRUE'],
    ]


class DepartmentsTemplateView(CSVTemplateDownloadView):
    """Download CSV template for Departments."""
    filename = 'departments_template.csv'
    headers = ['name', 'code', 'is_active']
    sample_rows = [
        ['General Administration', 'GA', 'TRUE'],
        ['Finance & Accounts', 'FA', 'TRUE'],
        ['Engineering', 'ENG', 'TRUE'],
        ['Public Health', 'PH', 'TRUE'],
        ['Water Supply', 'WS', 'TRUE'],
    ]


class DesignationsTemplateView(CSVTemplateDownloadView):
    """Download CSV template for Designations."""
    filename = 'designations_template.csv'
    headers = ['name', 'bps_scale', 'post_type', 'is_active']
    sample_rows = [
        ['Tehsil Municipal Officer', '17', 'PUGF', 'TRUE'],
        ['TO Finance', '16', 'PUGF', 'TRUE'],
        ['Accountant', '14', 'PUGF', 'TRUE'],
        ['Junior Clerk', '7', 'LOCAL', 'TRUE'],
        ['Naib Qasid', '2', 'LOCAL', 'TRUE'],
    ]


class BPSScalesTemplateView(CSVTemplateDownloadView):
    """Download CSV template for BPS Salary Scales."""
    filename = 'bps_scales_template.csv'
    headers = ['grade', 'basic_pay_min', 'basic_pay_max', 'increment', 'effective_date']
    sample_rows = [
        ['1', '17500', '30500', '650', '2024-07-01'],
        ['2', '17600', '31000', '670', '2024-07-01'],
        ['7', '20000', '45000', '1250', '2024-07-01'],
        ['17', '80000', '180000', '5000', '2024-07-01'],
    ]


class BudgetHeadsTemplateView(CSVTemplateDownloadView):
    """
    Download CSV template for Chart of Accounts (PIFRA Format).
    
    This template matches the format expected by the `import_coa` command.
    Structure: Major Object -> Minor Object -> Detailed Object
    """
    filename = 'pifra_chart_of_accounts_template.csv'
    # Row 2 headers (Code/Description alternating)
    headers = ['Code', 'Description', 'Code', 'Description', 'Code', 'Description']
    sample_rows = [
        ['A01', 'Employee Related Expenses', 'A011', 'Pay', 'A01101', 'Basic Pay (Officers)'],
        ['A01', 'Employee Related Expenses', 'A011', 'Pay', 'A01102', 'Personal Pay (Officers)'],
        ['A01', 'Employee Related Expenses', 'A011', 'Pay', 'A01151', 'Basic Pay (Other Staff)'],
        ['A03', 'Operating Expenses', 'A031', 'Utilities', 'A03101', 'Electricity'],
        ['A03', 'Operating Expenses', 'A031', 'Utilities', 'A03102', 'Gas'],
        ['C01', 'Tax Revenue', 'C011', 'Property Tax', 'C01101', 'Urban Property Tax'],
        ['C03', 'Non-Tax Revenue', 'C038', 'Other Revenue', 'C03880', 'Miscellaneous Revenue'],
    ]
    
    def get(self, request, *args, **kwargs):
        """Override to include 2-row header format."""
        from django.http import HttpResponse
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.filename}"'
        
        writer = csv.writer(response)
        # Row 1: Category headers (Major Object, Minor Object, Detailed Object)
        writer.writerow(['Major Object', '', 'Minor Object', '', 'Detailed Object', ''])
        # Row 2: Column headers (Code, Description alternating)
        writer.writerow(self.headers)
        # Data rows
        for row in self.sample_rows:
            writer.writerow(row)
        
        return response


class RolesTemplateView(CSVTemplateDownloadView):
    """Download CSV template for Roles."""
    filename = 'roles_template.csv'
    headers = ['name', 'code', 'description', 'is_system_role']
    sample_rows = [
        ['Super Administrator', 'SUPER_ADMIN', 'Full system access', 'TRUE'],
        ['Tehsil Municipal Officer', 'TMO', 'TMA approver', 'TRUE'],
        ['Dealing Assistant', 'DEALING_ASSISTANT', 'Data entry maker', 'TRUE'],
    ]


class OrganizationsTemplateView(CSVTemplateDownloadView):
    """Download CSV template for Organizations."""
    filename = 'organizations_template.csv'
    headers = ['name', 'tehsil_name', 'org_type', 'ddo_code', 'pla_account_no', 'is_active']
    sample_rows = [
        ['TMA Peshawar City', 'Peshawar City', 'TMA', 'DDO-PSH-001', 'PLA-001', 'TRUE'],
        ['TMA Abbottabad', 'Abbottabad', 'TMA', 'DDO-ABT-001', 'PLA-002', 'TRUE'],
    ]


# =============================================================================
# Division CRUD Views
# =============================================================================

class DivisionListView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """List all divisions."""
    model = Division
    template_name = 'system_admin/master_data/division_list.html'
    context_object_name = 'divisions'
    paginate_by = 25
    
    def get_queryset(self):
        return Division.objects.annotate(
            district_count=models.Count('districts')
        ).order_by('name')


class DivisionCreateView(LoginRequiredMixin, SuperAdminRequiredMixin, CreateView):
    """Create a new division."""
    model = Division
    template_name = 'system_admin/master_data/division_form.html'
    fields = ['name', 'code', 'is_active']
    success_url = reverse_lazy('system_admin:division_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Division "{form.instance.name}" created successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Division'
        context['is_edit'] = False
        return context


class DivisionUpdateView(LoginRequiredMixin, SuperAdminRequiredMixin, UpdateView):
    """Update a division."""
    model = Division
    template_name = 'system_admin/master_data/division_form.html'
    fields = ['name', 'code', 'is_active']
    success_url = reverse_lazy('system_admin:division_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Division "{form.instance.name}" updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Division'
        context['is_edit'] = True
        return context


class DivisionDeleteView(LoginRequiredMixin, SuperAdminRequiredMixin, DeleteView):
    """Delete a division."""
    model = Division
    template_name = 'system_admin/master_data/confirm_delete.html'
    success_url = reverse_lazy('system_admin:division_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Division "{self.object.name}" deleted.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['item_type'] = 'Division'
        context['item_name'] = self.object.name
        context['cancel_url'] = reverse_lazy('system_admin:division_list')
        return context


# =============================================================================
# District CRUD Views
# =============================================================================

class DistrictListView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """List all districts."""
    model = District
    template_name = 'system_admin/master_data/district_list.html'
    context_object_name = 'districts'
    paginate_by = 25
    
    def get_queryset(self):
        return District.objects.select_related('division').annotate(
            tehsil_count=models.Count('tehsils')
        ).order_by('division__name', 'name')


class DistrictCreateView(LoginRequiredMixin, SuperAdminRequiredMixin, CreateView):
    """Create a new district."""
    model = District
    template_name = 'system_admin/master_data/district_form.html'
    fields = ['name', 'code', 'division', 'is_active']
    success_url = reverse_lazy('system_admin:district_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'District "{form.instance.name}" created successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add District'
        context['is_edit'] = False
        return context


class DistrictUpdateView(LoginRequiredMixin, SuperAdminRequiredMixin, UpdateView):
    """Update a district."""
    model = District
    template_name = 'system_admin/master_data/district_form.html'
    fields = ['name', 'code', 'division', 'is_active']
    success_url = reverse_lazy('system_admin:district_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'District "{form.instance.name}" updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit District'
        context['is_edit'] = True
        return context


class DistrictDeleteView(LoginRequiredMixin, SuperAdminRequiredMixin, DeleteView):
    """Delete a district."""
    model = District
    template_name = 'system_admin/master_data/confirm_delete.html'
    success_url = reverse_lazy('system_admin:district_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'District "{self.object.name}" deleted.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['item_type'] = 'District'
        context['item_name'] = self.object.name
        context['cancel_url'] = reverse_lazy('system_admin:district_list')
        return context


# =============================================================================
# Tehsil CRUD Views
# =============================================================================

class TehsilListView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """List all tehsils."""
    model = Tehsil
    template_name = 'system_admin/master_data/tehsil_list.html'
    context_object_name = 'tehsils'
    paginate_by = 25
    
    def get_queryset(self):
        return Tehsil.objects.select_related(
            'district', 'district__division'
        ).order_by('district__division__name', 'district__name', 'name')


class TehsilCreateView(LoginRequiredMixin, SuperAdminRequiredMixin, CreateView):
    """Create a new tehsil."""
    model = Tehsil
    template_name = 'system_admin/master_data/tehsil_form.html'
    fields = ['name', 'code', 'district', 'is_active']
    success_url = reverse_lazy('system_admin:tehsil_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Tehsil "{form.instance.name}" created successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Tehsil'
        context['is_edit'] = False
        return context


class TehsilUpdateView(LoginRequiredMixin, SuperAdminRequiredMixin, UpdateView):
    """Update a tehsil."""
    model = Tehsil
    template_name = 'system_admin/master_data/tehsil_form.html'
    fields = ['name', 'code', 'district', 'is_active']
    success_url = reverse_lazy('system_admin:tehsil_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Tehsil "{form.instance.name}" updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Tehsil'
        context['is_edit'] = True
        return context


class TehsilDeleteView(LoginRequiredMixin, SuperAdminRequiredMixin, DeleteView):
    """Delete a tehsil."""
    model = Tehsil
    template_name = 'system_admin/master_data/confirm_delete.html'
    success_url = reverse_lazy('system_admin:tehsil_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Tehsil "{self.object.name}" deleted.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['item_type'] = 'Tehsil'
        context['item_name'] = self.object.name
        context['cancel_url'] = reverse_lazy('system_admin:tehsil_list')
        return context
