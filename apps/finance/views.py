"""
Views for the Finance module.
"""
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.db import models, transaction
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from typing import Dict, Any
import re
import csv
import io
import logging
from hashlib import md5

logger = logging.getLogger(__name__)

from apps.users.permissions import AdminRequiredMixin, MakerRequiredMixin, CheckerRequiredMixin, SuperAdminRequiredMixin
from apps.finance.models import (
    BudgetHead, Fund, ChequeBook, ChequeLeaf, LeafStatus,
    Voucher, JournalEntry, NAMHead, SubHead, FunctionCode, MinorHead
)
from apps.finance.forms import BudgetHeadForm, ChequeBookForm, ChequeLeafCancelForm, VoucherForm
from apps.core.models import BankAccount
from apps.budgeting.models import FiscalYear, Department
from django.views.generic import TemplateView


class CoAManagementHubView(LoginRequiredMixin, SuperAdminRequiredMixin, TemplateView):
    """
    Centralized Chart of Accounts Management Hub.
    Provides an intuitive workflow for setting up and managing CoA.
    """
    template_name = 'finance/coa_management_hub.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Step 1: Master Data Statistics
        context['departments_count'] = Department.objects.filter(is_active=True).count()
        context['functions_count'] = FunctionCode.objects.filter(is_active=True).count()
        context['global_heads_count'] = NAMHead.objects.count()  # Updated for new structure
        context['universal_global_heads'] = NAMHead.objects.filter(scope='UNIVERSAL').count()
        context['departmental_global_heads'] = NAMHead.objects.filter(scope='RESTRICTED').count()
        
        # Step 2: Budget Head Statistics
        context['budget_heads_total'] = BudgetHead.objects.filter(is_active=True).count()
        context['budget_heads_mapped'] = BudgetHead.objects.filter(is_active=True, department__isnull=False).count()
        context['budget_heads_unmapped'] = BudgetHead.objects.filter(is_active=True, department__isnull=True).count()
        context['sub_heads_count'] = BudgetHead.objects.filter(is_active=True, sub_head__isnull=False).count()  # Updated: count budget heads with sub-head FK
        
        # Step 3: Department Coverage
        dept_stats = []
        for dept in Department.objects.filter(is_active=True).order_by('name')[:10]:
            dept_stats.append({
                'name': dept.name,
                'budget_heads': BudgetHead.objects.filter(department=dept, is_active=True).count(),
                'functions': dept.related_functions.filter(is_active=True).count(),
            })
        context['department_stats'] = dept_stats
        
        # Completion indicators
        total_budget_heads = BudgetHead.objects.filter(is_active=True).count()
        if total_budget_heads > 0:
            context['mapping_percentage'] = int((context['budget_heads_mapped'] / total_budget_heads) * 100)
        else:
            context['mapping_percentage'] = 0
        
        # Calculate stroke-dashoffset for progress ring (circumference = 326.73)
        circumference = 326.73
        context['progress_offset'] = circumference - (circumference * context['mapping_percentage'] / 100)
            
        # Workflow status
        context['step1_complete'] = (context['departments_count'] > 0 and 
                                     context['functions_count'] > 0 and 
                                     context['global_heads_count'] > 0)
        context['step2_ready'] = context['step1_complete']
        context['step3_needed'] = context['budget_heads_unmapped'] > 0
        
        return context


class FundListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all funds."""
    model = Fund
    template_name = 'finance/setup_fund_list.html'
    context_object_name = 'funds'
    ordering = ['code']


class FundCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new fund."""
    model = Fund
    fields = ['code', 'name', 'description', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['code'].widget.attrs.update({'class': 'form-control'})
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add New Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context


class FundUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update fund."""
    model = Fund
    fields = ['code', 'name', 'description', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['code'].widget.attrs.update({'class': 'form-control', 'readonly': 'readonly'})
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context


class FundDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete fund."""
    model = Fund
    template_name = 'budgeting/setup_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Delete Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context

class BudgetHeadListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all Budget Heads (Chart of Accounts) with tree structure and filtering.
    
    OPTIMIZATION STRATEGY:
    - select_related: fund, function, nam_head, sub_head + sub_head__nam_head (for hierarchical access)
    - Efficient major/minor heads query using database-level distinct
    - Pagination to avoid loading all items in memory at once
    - Cached lookups for filter options
    
    NOTE: Updated for NAM CoA structure - handles both nam_head and sub_head.
    """
    model = BudgetHead
    template_name = 'finance/budget_head_list.html'
    context_object_name = 'budget_heads'
    ordering = ['function__code']
    paginate_by = 50  # Paginate to improve performance

    def get_queryset(self):
        from django.db.models import Q
        
        # CRITICAL: Include select_related for all ForeignKey relationships
        # to avoid N+1 queries in the template
        qs = super().get_queryset().select_related(
            'fund',
            'function',
            'nam_head',
            'nam_head__minor',
            'sub_head',
            'sub_head__nam_head',
            'sub_head__nam_head__minor',
        )
        
        # Apply filters
        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(
                Q(nam_head__isnull=False, nam_head__name__icontains=query) |
                Q(nam_head__isnull=False, nam_head__code__icontains=query) |
                Q(sub_head__isnull=False, sub_head__name__icontains=query) |
                Q(sub_head__isnull=False, sub_head__sub_code__icontains=query) |
                Q(sub_head__isnull=False, sub_head__nam_head__code__icontains=query)
            )
        
        # Account type filter - works via NAMHead or SubHead->NAMHead
        account_type = self.request.GET.get('account_type')
        if account_type:
            qs = qs.filter(
                Q(nam_head__isnull=False, nam_head__account_type=account_type) |
                Q(sub_head__isnull=False, sub_head__nam_head__account_type=account_type)
            )
        
        # Fund filter
        fund_id = self.request.GET.get('fund')
        if fund_id:
            qs = qs.filter(fund_id=fund_id)
        
        # Function filter
        function_id = self.request.GET.get('function')
        if function_id:
            qs = qs.filter(function_id=function_id)

        # Department filter
        department_id = self.request.GET.get('department')
        if department_id:
            qs = qs.filter(department_id=department_id)
        
        # Active status filter
        is_active = self.request.GET.get('is_active')
        if is_active:
            qs = qs.filter(is_active=is_active == 'true')
        
        # Fund type filter
        fund_type = self.request.GET.get('fund_type')
        if fund_type:
            qs = qs.filter(fund_type=fund_type)
        
        # Major head filter (first 3 characters) - check both paths
        major_head = self.request.GET.get('major_head')
        if major_head:
            qs = qs.filter(
                Q(nam_head__isnull=False, nam_head__code__startswith=major_head) |
                Q(sub_head__isnull=False, sub_head__nam_head__code__startswith=major_head)
            )
        
        # Minor head filter (first 4 characters) - check both paths
        minor_head = self.request.GET.get('minor_head')
        if minor_head:
            qs = qs.filter(
                Q(nam_head__isnull=False, nam_head__code__startswith=minor_head) |
                Q(sub_head__isnull=False, sub_head__nam_head__code__startswith=minor_head)
            )
        
        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        from apps.finance.models import Fund, FunctionCode, AccountType, FundType
        from apps.budgeting.models import Department
        from django.db.models import F
        
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Chart of Accounts Management')
        
        # Cache filter options using select_for_update would be better in production
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['funds'] = Fund.objects.filter(is_active=True).order_by('code')
        
        # Filter functions based on selected department if applicable
        functions_qs = FunctionCode.objects.filter(is_active=True)
        department_id = self.request.GET.get('department')
        if department_id:
            try:
                dept = Department.objects.get(id=department_id)
                functions_qs = functions_qs.filter(id__in=dept.related_functions.all())
            except Department.DoesNotExist:
                pass
            
        context['functions'] = functions_qs.order_by('code')
        context['account_types'] = AccountType.choices
        context['fund_types'] = FundType.choices
        
        # Count unmapped budget heads (no department assigned)
        context['unmapped_count'] = BudgetHead.objects.filter(department__isnull=True).count()
        
        # OPTIMIZED: Get unique major and minor heads using database-level distinct
        # Updated for NAM CoA: collect codes from both nam_head and sub_head->nam_head
        nam_head_codes = BudgetHead.objects.filter(
            nam_head__isnull=False
        ).values_list('nam_head__code', flat=True).distinct()
        
        sub_head_codes = BudgetHead.objects.filter(
            sub_head__isnull=False
        ).values_list('sub_head__nam_head__code', flat=True).distinct()
        
        all_codes = list(set(list(nam_head_codes) + list(sub_head_codes)))
        
        major_heads = set()
        minor_heads = set()
        
        for code in all_codes:
            if code and len(code) >= 3:
                major = code[:3]  # First 3 chars (e.g., A01, B02, G05)
                major_heads.add(major)
            if code and len(code) >= 4:
                minor = code[:4]  # First 4 chars (e.g., A011, B013, G021)
                minor_heads.add(minor)
        
        context['major_heads'] = sorted(major_heads)
        context['minor_heads'] = sorted(minor_heads)
        
        # Build Grouped Structure (Function -> BudgetHeads)
        # NOTE: With pagination, only builds tree for current page items
        heads = list(context['budget_heads'])
        tree_list = []
        
        current_function_code = None
        
        for head in heads:
            func_code = head.function.code if head.function else 'None'
            
            # Start a new group if function changes
            if func_code != current_function_code:
                current_function_code = func_code
                tree_list.append({
                    'obj': head.function,
                    'level': 0,
                    'is_leaf': False,
                    'is_group_header': True,
                    'parent_code': None,
                    'has_children': True,
                    'group_name': f"{head.function.code} - {head.function.name}"
                })
            
            # Add the BudgetHead
            tree_list.append({
                'obj': head,
                'level': 1,
                'is_leaf': True,
                'is_group_header': False,
                'parent_code': func_code,
                'has_children': False
            })
            
        context['tree_nodes'] = tree_list
        return context


class BudgetHeadCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new Budget Head."""
    model = BudgetHead
    form_class = BudgetHeadForm
    template_name = 'finance/budget_head_form.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def get_form_kwargs(self):
        """Pass request and mode parameter to form."""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['mode'] = self.request.GET.get('mode', '')
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _('Budget Head created successfully.'))
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mode = self.request.GET.get('mode', '')
        if mode == 'subhead':
            context['page_title'] = _('Create Sub-Head')
        else:
            context['page_title'] = _('Add New Budget Head')
        context['back_url'] = self.success_url
        context['is_subhead_mode'] = mode == 'subhead'
        return context


class BudgetHeadUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update Budget Head."""
    model = BudgetHead
    form_class = BudgetHeadForm
    template_name = 'finance/budget_head_form.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def form_valid(self, form):
        messages.success(self.request, _('Budget Head updated successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Edit Budget Head')
        context['back_url'] = self.success_url
        return context

    def get_form_kwargs(self):
        """Pass request to form to check for superuser status."""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class BudgetHeadDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete Budget Head."""
    model = BudgetHead
    template_name = 'finance/budget_head_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _('Budget Head deleted successfully.'))
        return super().delete(request, *args, **kwargs)


class SubHeadCSVTemplateView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Download CSV template for bulk sub-head creation.
    
    CSV Format:
    - NAM Head Code: Full NAM code (e.g., A12001, L01101)
    - Sub Code: 2-digit code (01, 02, 03, etc.)
    - Name: Descriptive name for the sub-head
    - Description: Optional detailed description
    - Active: Y or N
    """
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="subhead_import_template.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'NAM Head Code',
            'Sub Code',
            'Name',
            'Description',
            'Active (Y/N)'
        ])
        
        # Write example rows with actual NAM head codes
        writer.writerow([
            'A12001',
            '01',
            'PCC Streets',
            'Portland Cement Concrete Streets',
            'Y'
        ])
        writer.writerow([
            'A12001',
            '02',
            'Shingle Roads',
            'Shingle road construction and maintenance',
            'Y'
        ])
        writer.writerow([
            'L01101',
            '01',
            'Qualification Pay',
            'Additional qualification allowances',
            'Y'
        ])
        
        return response


class SubHeadCSVImportView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Import sub-heads from CSV file.
    
    Expected CSV columns:
    1. NAM Head Code (e.g., A12001, L01101)
    2. Sub Code (01, 02, 03, etc.)
    3. Name
    4. Description (optional)
    5. Active (Y/N)
    """
    def get(self, request):
        return render(request, 'finance/subhead_csv_import.html')
    
    def post(self, request):
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, 'Please select a CSV file to upload.')
            return redirect('finance:subhead_csv_import')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('finance:subhead_csv_import')
        
        try:
            # Read CSV
            decoded_file = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(decoded_file))
            
            created_count = 0
            updated_count = 0
            error_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Extract and clean data
                    nam_code = row.get('NAM Head Code', '').strip()
                    sub_code = row.get('Sub Code', '').strip()
                    name = row.get('Name', '').strip()
                    description = row.get('Description', '').strip()
                    active_str = row.get('Active (Y/N)', 'Y').strip().upper()
                    
                    # Validate required fields
                    if not nam_code:
                        errors.append(f"Row {row_num}: NAM Head Code is required")
                        error_count += 1
                        continue
                    
                    if not sub_code:
                        errors.append(f"Row {row_num}: Sub Code is required")
                        error_count += 1
                        continue
                    
                    if not name:
                        errors.append(f"Row {row_num}: Name is required")
                        error_count += 1
                        continue
                    
                    # Validate sub_code format (2 digits)
                    if not sub_code.isdigit() or len(sub_code) != 2:
                        errors.append(f"Row {row_num}: Sub Code must be 2 digits (e.g., 01, 02)")
                        error_count += 1
                        continue
                    
                    # Find NAM Head
                    try:
                        nam_head = NAMHead.objects.get(code=nam_code)
                    except NAMHead.DoesNotExist:
                        errors.append(f"Row {row_num}: NAM Head '{nam_code}' not found")
                        error_count += 1
                        continue
                    
                    # Parse active flag
                    is_active = active_str in ['Y', 'YES', '1', 'TRUE']
                    
                    # Create or update SubHead
                    sub_head, created = SubHead.objects.update_or_create(
                        nam_head=nam_head,
                        sub_code=sub_code,
                        defaults={
                            'name': name,
                            'description': description,
                            'is_active': is_active,
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
            
            # Display results
            if created_count > 0:
                messages.success(request, f'Successfully created {created_count} sub-head(s).')
            
            if updated_count > 0:
                messages.info(request, f'Updated {updated_count} existing sub-head(s).')
            
            if error_count > 0:
                messages.warning(request, f'Failed to process {error_count} row(s). See details below.')
                for error in errors[:10]:  # Show first 10 errors
                    messages.error(request, error)
                if len(errors) > 10:
                    messages.error(request, f'... and {len(errors) - 10} more errors.')
            
            if created_count == 0 and updated_count == 0 and error_count == 0:
                messages.warning(request, 'No data was processed. Please check your CSV file.')
            
            return redirect('finance:subhead_list')
        
        except Exception as e:
            messages.error(request, f'Error processing CSV file: {str(e)}')
            return redirect('finance:subhead_csv_import')


class GlobalHeadCSVTemplateView(LoginRequiredMixin, SuperAdminRequiredMixin, View):
    """
    Download CSV template for bulk 5-level CoA import.
    
    Template includes all 5 levels:
    - Level 1: Classification (A/C/G/K)
    - Level 2: Major Head
    - Level 3: Minor Head  
    - Level 4: NAM Head
    - Level 5: Sub-Head (optional)
    """
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="coa_5level_import_template.csv"'
        
        writer = csv.writer(response)
        # Write header with all 5 levels
        writer.writerow([
            # Level 2: Major Head
            'Major Code', 'Major Name', 'Classification',
            # Level 3: Minor Head
            'Minor Code', 'Minor Name',
            # Level 4: NAM Head
            'NAM Code', 'NAM Name', 'Account Type', 'Scope',
            # Level 5: Sub-Head (Optional)
            'Sub Code', 'Sub Name', 'Sub Description',
            # Control Fields
            'Allow Direct Posting'
        ])
        
        # Write example rows
        # Example 1: Complete hierarchy with sub-head
        writer.writerow([
            'A01', 'Employee Related Expenses', 'A',
            'A011', 'Pay of Officers/Officials',
            'A01101', 'Basic Pay - Officers', 'EXP', 'UNIVERSAL',
            '01', 'Officers Grade 17+', 'Officers Grade 17 and above',
            'N'  # No direct posting when sub-heads exist
        ])
        
        # Example 2: NAM head without sub-head (can be posted directly)
        writer.writerow([
            'A01', 'Employee Related Expenses', 'A',
            'A011', 'Pay of Officers/Officials',
            'A01102', 'Personal Pay', 'EXP', 'UNIVERSAL',
            '', '', '',  # No sub-head
            'Y'  # Allow direct posting
        ])
        
        # Example 3: Revenue head
        writer.writerow([
            'C03', 'Services', 'C',
            'C038', 'Services - Other',
            'C03880', 'TMA Other Non-tax Revenues', 'REV', 'UNIVERSAL',
            '', '', '',
            'Y'
        ])
        
        # Example 4: Another sub-head for first NAM head
        writer.writerow([
            'A01', 'Employee Related Expenses', 'A',
            'A011', 'Pay of Officers/Officials',
            'A01101', 'Basic Pay - Officers', 'EXP', 'UNIVERSAL',
            '02', 'Officers Grade 16-', 'Officers Grade 16 and below',
            'N'
        ])
        
        return response


class GlobalHeadCSVImportView(LoginRequiredMixin, SuperAdminRequiredMixin, View):
    """
    Import 5-level CoA hierarchy from CSV file.
    
    Features:
    - Pre-validates all data before any database changes
    - Reports errors with row numbers
    - Atomic transaction - all or nothing
    - Creates/updates all 5 levels in correct order
    """
    template_name = 'finance/global_head_csv_import.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        from apps.finance.models import (
            MajorHead, MinorHead, NAMHead, SubHead, AccountType
        )
        
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, _('Please upload a CSV file.'))
            return redirect('finance:global_head_csv_import')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, _('Please upload a valid CSV file.'))
            return redirect('finance:global_head_csv_import')
        
        # Parse CSV
        try:
            decoded_file = csv_file.read().decode('utf-8-sig').splitlines()  # utf-8-sig removes BOM
        except UnicodeDecodeError:
            messages.error(request, _('File encoding error. Please ensure the file is UTF-8 encoded.'))
            return redirect('finance:global_head_csv_import')
        
        reader = csv.DictReader(decoded_file)
        
        # Validate headers
        expected_headers = [
            'Major Code', 'Major Name', 'Classification',
            'Minor Code', 'Minor Name',
            'NAM Code', 'NAM Name', 'Account Type', 'Scope',
            'Sub Code', 'Sub Name', 'Sub Description',
            'Allow Direct Posting'
        ]
        actual_headers = reader.fieldnames if reader.fieldnames else []
        
        # Check for header mismatch
        missing_headers = [h for h in expected_headers if h not in actual_headers]
        if missing_headers:
            messages.error(
                request,
                f'CSV header mismatch. Missing columns: {", ".join(missing_headers)}. '
                f'Please download the template and ensure column headers match exactly.'
            )
            return render(request, self.template_name, {
                'errors': [
                    f'Expected headers: {", ".join(expected_headers)}',
                    f'Your headers: {", ".join(actual_headers)}',
                    'Download the template to get the correct format.'
                ],
                'error_count': 1
            })
        
        # Validation phase - collect all errors before processing
        errors = []
        validated_rows = []
        row_num = 1  # Start at 1 (header row)
        
        # Track what we'll create to avoid duplicates within the file
        major_codes_seen = {}
        minor_codes_seen = {}
        nam_codes_seen = {}
        sub_codes_seen = {}
        
        for row in reader:
            row_num += 1
            row_errors = []
            
            try:
                # Extract and validate all fields
                major_code = row.get('Major Code', '').strip()
                major_name = row.get('Major Name', '').strip()
                classification = row.get('Classification', '').strip().upper()
                
                minor_code = row.get('Minor Code', '').strip()
                minor_name = row.get('Minor Name', '').strip()
                
                nam_code = row.get('NAM Code', '').strip()
                nam_name = row.get('NAM Name', '').strip()
                account_type = row.get('Account Type', '').strip().upper()
                scope = row.get('Scope', '').strip().upper()
                
                sub_code = row.get('Sub Code', '').strip()
                sub_name = row.get('Sub Name', '').strip()
                sub_description = row.get('Sub Description', '').strip()
                
                allow_posting = row.get('Allow Direct Posting', 'Y').strip().upper()
                
                # Validate required fields for Level 2 (Major)
                if not major_code:
                    row_errors.append('Major Code is required')
                elif len(major_code) != 3:
                    row_errors.append(f'Major Code must be exactly 3 characters (got: {major_code})')
                
                if not major_name:
                    row_errors.append('Major Name is required')
                
                if classification not in ['A', 'C', 'G', 'K']:
                    row_errors.append(f'Classification must be A, C, G, or K (got: {classification})')
                
                # Validate classification matches major code
                if major_code and classification and not major_code.upper().startswith(classification.upper()):
                    row_errors.append(f'Major Code {major_code} must start with Classification {classification}')
                
                # Validate Level 3 (Minor)
                if not minor_code:
                    row_errors.append('Minor Code is required')
                elif len(minor_code) != 4:
                    row_errors.append(f'Minor Code must be exactly 4 characters (got: {minor_code})')
                elif not minor_code.startswith(major_code[:3]):
                    row_errors.append(f'Minor Code {minor_code} must start with Major Code {major_code}')
                
                if not minor_name:
                    row_errors.append('Minor Name is required')
                
                # Validate Level 4 (NAM)
                if not nam_code:
                    row_errors.append('NAM Code is required')
                elif len(nam_code) < 5:
                    row_errors.append(f'NAM Code must be at least 5 characters (got: {nam_code})')
                elif not nam_code.startswith(minor_code[:4]):
                    row_errors.append(f'NAM Code {nam_code} must start with Minor Code {minor_code}')
                
                if not nam_name:
                    row_errors.append('NAM Name is required')
                
                if account_type not in ['EXP', 'REV', 'AST', 'LIA', 'EQT']:
                    row_errors.append(f'Account Type must be EXP, REV, AST, LIA, or EQT (got: {account_type})')
                
                if scope not in ['UNIVERSAL', 'RESTRICTED']:
                    row_errors.append(f'Scope must be UNIVERSAL or RESTRICTED (got: {scope})')
                
                # Validate Level 5 (Sub-Head) - optional but if provided must be valid
                if sub_code:
                    if len(sub_code) != 2:
                        row_errors.append(f'Sub Code must be exactly 2 characters if provided (got: {sub_code})')
                    if not sub_name:
                        row_errors.append('Sub Name is required when Sub Code is provided')
                    if allow_posting == 'Y':
                        row_errors.append('Allow Direct Posting must be N when Sub-Heads exist')
                
                # Check for duplicates within file
                if major_code:
                    if major_code in major_codes_seen:
                        if major_codes_seen[major_code] != (major_name, classification):
                            row_errors.append(f'Duplicate Major Code {major_code} with different details')
                    else:
                        major_codes_seen[major_code] = (major_name, classification)
                
                if minor_code:
                    if minor_code in minor_codes_seen:
                        if minor_codes_seen[minor_code] != minor_name:
                            row_errors.append(f'Duplicate Minor Code {minor_code} with different name')
                    else:
                        minor_codes_seen[minor_code] = minor_name
                
                if nam_code:
                    if nam_code in nam_codes_seen:
                        if nam_codes_seen[nam_code] != nam_name:
                            row_errors.append(f'Duplicate NAM Code {nam_code} with different name')
                    else:
                        nam_codes_seen[nam_code] = nam_name
                
                if sub_code and nam_code:
                    sub_key = f'{nam_code}-{sub_code}'
                    if sub_key in sub_codes_seen:
                        if sub_codes_seen[sub_key] != sub_name:
                            row_errors.append(f'Duplicate Sub-Head {sub_key} with different name')
                    else:
                        sub_codes_seen[sub_key] = sub_name
                
                # If no errors, add to validated rows
                if not row_errors:
                    validated_rows.append({
                        'major_code': major_code,
                        'major_name': major_name,
                        'classification': classification,
                        'minor_code': minor_code,
                        'minor_name': minor_name,
                        'nam_code': nam_code,
                        'nam_name': nam_name,
                        'account_type': account_type,
                        'scope': scope,
                        'sub_code': sub_code,
                        'sub_name': sub_name,
                        'sub_description': sub_description,
                        'allow_posting': allow_posting == 'Y',
                    })
                else:
                    errors.append(f'Row {row_num}: {"; ".join(row_errors)}')
            
            except Exception as e:
                errors.append(f'Row {row_num}: Unexpected error - {str(e)}')
        
        # If validation errors exist, show them and don't proceed
        if errors:
            messages.error(request, f'Validation failed with {len(errors)} error(s). No data was imported.')
            return render(request, self.template_name, {
                'errors': errors,
                'error_count': len(errors)
            })
        
        # Import phase - atomic transaction
        try:
            with transaction.atomic():
                success_stats = {
                    'majors_created': 0,
                    'minors_created': 0,
                    'nams_created': 0,
                    'subs_created': 0,
                }
                
                for row_data in validated_rows:
                    # Level 2: Create or get Major Head (classification is implicit in code)
                    major, created = MajorHead.objects.get_or_create(
                        code=row_data['major_code'],
                        defaults={
                            'name': row_data['major_name']
                        }
                    )
                    if created:
                        success_stats['majors_created'] += 1
                    
                    # Level 3: Create or get Minor Head
                    minor, created = MinorHead.objects.get_or_create(
                        code=row_data['minor_code'],
                        defaults={
                            'name': row_data['minor_name'],
                            'major': major
                        }
                    )
                    if created:
                        success_stats['minors_created'] += 1
                    
                    # Level 4: Create or get NAM Head
                    nam, created = NAMHead.objects.get_or_create(
                        code=row_data['nam_code'],
                        defaults={
                            'name': row_data['nam_name'],
                            'minor': minor,
                            'account_type': row_data['account_type'],
                            'scope': row_data['scope'],
                            'allow_direct_posting': row_data['allow_posting']
                        }
                    )
                    if created:
                        success_stats['nams_created'] += 1
                    
                    # Level 5: Create Sub-Head if provided
                    if row_data['sub_code']:
                        sub, created = SubHead.objects.get_or_create(
                            nam_head=nam,
                            sub_code=row_data['sub_code'],
                            defaults={
                                'name': row_data['sub_name'],
                                'description': row_data['sub_description']
                            }
                        )
                        if created:
                            success_stats['subs_created'] += 1
                            # Disable direct posting on parent NAM head
                            if nam.allow_direct_posting:
                                nam.allow_direct_posting = False
                                nam.save(update_fields=['allow_direct_posting'])
                
                # Success message with statistics
                messages.success(
                    request,
                    f"Successfully imported: "
                    f"{success_stats['majors_created']} Major Heads, "
                    f"{success_stats['minors_created']} Minor Heads, "
                    f"{success_stats['nams_created']} NAM Heads, "
                    f"{success_stats['subs_created']} Sub-Heads"
                )
                
        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')
            return redirect('finance:global_head_csv_import')
        
        return redirect('finance:coa_hub')


@method_decorator(csrf_protect, name='dispatch')
class BudgetHeadToggleStatusView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Toggle the active status of a Budget Head via AJAX.
    """
    
    def post(self, request, pk):
        head = get_object_or_404(BudgetHead, pk=pk)
        
        # Toggle status
        head.is_active = not head.is_active
        head.save_with_user(request.user)
        
        return JsonResponse({
            'success': True,
            'is_active': head.is_active,
            'message': _('Status updated successfully.')
        })



# ============================================================================
# Cheque Book Management Views
# ============================================================================

class ChequeBookListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """
    List all cheque books grouped by Bank Account.
    
    Shows: Bank, Book No, Range, Total Leaves, Available Leaves.
    """
    model = ChequeBook
    template_name = 'finance/chequebook_list.html'
    context_object_name = 'chequebooks'
    
    def get_queryset(self):
        """Filter by user's organization."""
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        qs = ChequeBook.objects.select_related('bank_account').order_by(
            'bank_account__title', '-issue_date'
        )
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Cheque Book Management')
        
        # Group by bank account
        grouped = {}
        for book in context['chequebooks']:
            bank = book.bank_account
            if bank.pk not in grouped:
                grouped[bank.pk] = {
                    'bank': bank,
                    'books': []
                }
            grouped[bank.pk]['books'].append(book)
        
        context['grouped_books'] = grouped
        return context


class ChequeBookCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """
    Create a new Cheque Book.
    
    Automatically generates ChequeLeaf records on save.
    """
    model = ChequeBook
    form_class = ChequeBookForm
    template_name = 'finance/chequebook_form.html'
    success_url = reverse_lazy('budgeting:setup_chequebooks')
    
    def get_form_kwargs(self):
        """Pass organization to form."""
        kwargs = super().get_form_kwargs()
        user = self.request.user
        kwargs['organization'] = getattr(user, 'organization', None)
        return kwargs
    
    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        leaf_count = self.object.total_leaves
        messages.success(
            self.request,
            _(f'Cheque Book "{self.object.book_no}" created with {leaf_count} leaves.')
        )
        return response
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Register New Cheque Book')
        context['back_url'] = self.success_url
        return context


class ChequeBookDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """
    View details of a Cheque Book including all leaves.
    
    Allows cancelling individual leaves.
    """
    model = ChequeBook
    template_name = 'finance/chequebook_detail.html'
    context_object_name = 'chequebook'
    
    def get_queryset(self):
        """Filter by user's organization."""
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        qs = ChequeBook.objects.select_related('bank_account')
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Cheque Book: {self.object.book_no}"
        context['leaves'] = self.object.leaves.all().order_by('id')
        context['cancel_form'] = ChequeLeafCancelForm()
        context['leaf_statuses'] = LeafStatus
        return context


@method_decorator(csrf_protect, name='dispatch')
class ChequeLeafCancelView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Cancel a cheque leaf (mark as void).
    """
    
    def post(self, request, pk, leaf_pk):
        """Process leaf cancellation."""
        book = get_object_or_404(ChequeBook, pk=pk)
        leaf = get_object_or_404(ChequeLeaf, pk=leaf_pk, book=book)
        
        form = ChequeLeafCancelForm(request.POST)
        if form.is_valid():
            try:
                reason = form.cleaned_data['reason']
                leaf.mark_cancelled(reason)
                messages.success(
                    request,
                    _(f'Cheque leaf {leaf.leaf_number} has been cancelled.')
                )
            except Exception as e:
                messages.error(request, str(e))
        else:
            messages.error(request, _('Please provide a reason for cancellation.'))
        
        return HttpResponseRedirect(reverse('budgeting:setup_chequebook_detail', kwargs={'pk': pk}))


@method_decorator(csrf_protect, name='dispatch')
class ChequeLeafDamageView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Mark a cheque leaf as damaged.
    """
    
    def post(self, request, pk, leaf_pk):
        """Process leaf damage marking."""
        book = get_object_or_404(ChequeBook, pk=pk)
        leaf = get_object_or_404(ChequeLeaf, pk=leaf_pk, book=book)
        
        form = ChequeLeafCancelForm(request.POST)
        if form.is_valid():
            try:
                reason = form.cleaned_data['reason']
                leaf.mark_damaged(reason)
                messages.success(
                    request,
                    _(f'Cheque leaf {leaf.leaf_number} has been marked as damaged.')
                )
            except Exception as e:
                messages.error(request, str(e))
        else:
            messages.error(request, _('Please provide a reason.'))
        
        return HttpResponseRedirect(reverse('budgeting:setup_chequebook_detail', kwargs={'pk': pk}))


# ============================================================================
# Bank Reconciliation Views
# ============================================================================

from apps.finance.models import BankStatement, BankStatementLine, JournalEntry, StatementStatus
from apps.finance.forms import (
    BankStatementForm, BankStatementLineForm, ManualMatchForm, StatementUploadForm
)
from apps.finance.services_reconciliation import (
    ReconciliationEngine, parse_bank_statement_csv
)
from django.http import JsonResponse
from django.db import transaction


class BankStatementListView(LoginRequiredMixin, ListView):
    """
    List all bank statements for reconciliation.
    """
    model = BankStatement
    template_name = 'finance/statement_list.html'
    context_object_name = 'statements'
    paginate_by = 20
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs.select_related('bank_account', 'year').order_by('-year__start_date', '-month')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Bank Statements')
        return context


class BankStatementCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new bank statement and optionally upload CSV.
    """
    model = BankStatement
    form_class = BankStatementForm
    template_name = 'finance/statement_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = getattr(self.request.user, 'organization', None)
        return kwargs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Create Bank Statement')
        context['upload_form'] = StatementUploadForm()
        return context
    
    def form_valid(self, form):
        """Save statement and process CSV if uploaded."""
        statement = form.save(commit=False)
        statement.created_by = self.request.user
        statement.save()
        
        # Check if CSV file was uploaded with the statement
        if statement.file:
            try:
                content = statement.file.read().decode('utf-8')
                lines_created, errors = parse_bank_statement_csv(content, statement)
                
                if lines_created > 0:
                    messages.success(
                        self.request,
                        _(f'Statement created with {lines_created} lines imported from CSV.')
                    )
                
                if errors:
                    for error in errors[:5]:  # Show first 5 errors
                        messages.warning(self.request, error)
                    if len(errors) > 5:
                        messages.warning(
                            self.request,
                            _(f'... and {len(errors) - 5} more errors.')
                        )
            except Exception as e:
                messages.warning(
                    self.request,
                    _(f'Statement created but CSV import failed: {str(e)}')
                )
        else:
            messages.success(self.request, _('Bank statement created successfully.'))
        
        return HttpResponseRedirect(
            reverse('finance:statement_detail', kwargs={'pk': statement.pk})
        )
    
    def get_success_url(self):
        return reverse('finance:statement_list')


class BankStatementDetailView(LoginRequiredMixin, DetailView):
    """
    View statement details and reconciliation status.
    """
    model = BankStatement
    template_name = 'finance/statement_detail.html'
    context_object_name = 'statement'
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs.select_related('bank_account', 'year')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Statement: {self.object}"
        context['lines'] = self.object.lines.all().order_by('date', 'id')
        context['line_form'] = BankStatementLineForm()
        context['upload_form'] = StatementUploadForm()
        
        # Get reconciliation summary
        engine = ReconciliationEngine(self.object)
        context['brs_summary'] = engine.get_brs_summary()
        
        return context


@method_decorator(csrf_protect, name='dispatch')
class BankStatementUploadCSVView(LoginRequiredMixin, View):
    """
    Upload and parse CSV file for an existing statement.
    """
    
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        # Check organization access
        org = getattr(request.user, 'organization', None)
        if org and statement.bank_account.organization != org:
            messages.error(request, _('Access denied.'))
            return HttpResponseRedirect(reverse('finance:statement_list'))
        
        if statement.is_locked:
            messages.error(request, _('Cannot modify a locked statement.'))
            return HttpResponseRedirect(
                reverse('finance:statement_detail', kwargs={'pk': pk})
            )
        
        form = StatementUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                csv_file = form.cleaned_data['csv_file']
                content = csv_file.read().decode('utf-8')
                lines_created, errors = parse_bank_statement_csv(content, statement)
                
                if lines_created > 0:
                    messages.success(
                        request,
                        _(f'{lines_created} lines imported from CSV.')
                    )
                
                if errors:
                    for error in errors[:5]:
                        messages.warning(request, error)
                    if len(errors) > 5:
                        messages.warning(
                            request,
                            _(f'... and {len(errors) - 5} more errors.')
                        )
            except Exception as e:
                messages.error(request, _(f'CSV import failed: {str(e)}'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        
        return HttpResponseRedirect(
            reverse('finance:statement_detail', kwargs={'pk': pk})
        )


@method_decorator(csrf_protect, name='dispatch')
class BankStatementAddLineView(LoginRequiredMixin, View):
    """
    Add a single line to a statement.
    """
    
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        if statement.is_locked:
            messages.error(request, _('Cannot modify a locked statement.'))
            return HttpResponseRedirect(
                reverse('finance:statement_detail', kwargs={'pk': pk})
            )
        
        form = BankStatementLineForm(request.POST)
        if form.is_valid():
            line = form.save(commit=False)
            line.statement = statement
            line.save()
            messages.success(request, _('Statement line added.'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        return HttpResponseRedirect(
            reverse('finance:statement_detail', kwargs={'pk': pk})
        )


class ReconciliationWorkbenchView(LoginRequiredMixin, DetailView):
    """
    Two-column reconciliation workbench.
    
    Left: Unreconciled GL entries (Cash Book)
    Right: Unreconciled Bank Statement lines
    """
    model = BankStatement
    template_name = 'finance/reconciliation_workbench.html'
    context_object_name = 'statement'
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs.select_related('bank_account', 'year')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Reconciliation: {self.object}"
        
        engine = ReconciliationEngine(self.object)
        
        # Get unreconciled items for both sides
        context['gl_entries'] = engine.get_unreconciled_gl_entries()
        context['statement_lines'] = engine.get_unreconciled_statement_lines()
        context['brs_summary'] = engine.get_brs_summary()
        context['match_form'] = ManualMatchForm()
        
        return context


@method_decorator(csrf_protect, name='dispatch')
class AutoReconcileView(LoginRequiredMixin, View):
    """
    Trigger automatic reconciliation.
    """
    
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        if statement.is_locked:
            messages.error(request, _('Cannot reconcile a locked statement.'))
            return HttpResponseRedirect(
                reverse('finance:reconciliation_workbench', kwargs={'pk': pk})
            )
        
        try:
            engine = ReconciliationEngine(statement)
            result = engine.auto_reconcile()
            
            messages.success(
                request,
                _(f'Auto-reconciliation complete: {result.matched_count} items matched. '
                  f'{result.unmatched_statement_lines} statement lines and '
                  f'{result.unmatched_gl_entries} GL entries remain unmatched.')
            )
        except Exception as e:
            messages.error(request, _(f'Auto-reconciliation failed: {str(e)}'))
        
        return HttpResponseRedirect(
            reverse('finance:reconciliation_workbench', kwargs={'pk': pk})
        )


@method_decorator(csrf_protect, name='dispatch')
class ManualMatchView(LoginRequiredMixin, View):
    """
    Manually match selected items.
    """
    
    @transaction.atomic
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        if statement.is_locked:
            return JsonResponse({
                'success': False,
                'error': 'Statement is locked.'
            })
        
        form = ManualMatchForm(request.POST)
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'error': 'Invalid form data.'
            })
        
        try:
            engine = ReconciliationEngine(statement)
            matched = engine.manual_match(
                form.cleaned_data['statement_line_ids'],
                form.cleaned_data['journal_entry_ids']
            )
            
            return JsonResponse({
                'success': True,
                'matched_count': matched,
                'message': f'{matched} items matched successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@method_decorator(csrf_protect, name='dispatch')
class UnmatchLineView(LoginRequiredMixin, View):
    """
    Unmatch a statement line.
    """
    
    def post(self, request, pk, line_pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        line = get_object_or_404(BankStatementLine, pk=line_pk, statement=statement)
        
        if statement.is_locked:
            messages.error(request, _('Cannot unmatch items in a locked statement.'))
        else:
            try:
                line.unmatch()
                messages.success(request, _('Item unmatched successfully.'))
            except Exception as e:
                messages.error(request, str(e))
        
        return HttpResponseRedirect(
            reverse('finance:reconciliation_workbench', kwargs={'pk': pk})
        )


@method_decorator(csrf_protect, name='dispatch')
class LockStatementView(LoginRequiredMixin, View):
    """
    Lock a statement after reconciliation is complete.
    """
    
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        try:
            statement.lock()
            messages.success(request, _('Statement locked successfully.'))
        except Exception as e:
            messages.error(request, str(e))
        
        return HttpResponseRedirect(
            reverse('finance:statement_detail', kwargs={'pk': pk})
        )


class BRSSummaryView(LoginRequiredMixin, DetailView):
    """
    Bank Reconciliation Statement summary view.
    """
    model = BankStatement
    template_name = 'finance/brs_summary.html'
    context_object_name = 'statement'
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs.select_related('bank_account', 'year')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"BRS: {self.object}"
        
        engine = ReconciliationEngine(self.object)
        context['brs'] = engine.get_brs_summary()
        
        return context


# =========================================================================
# Manual Journal Vouchers (Phase 10: General Journal)
# =========================================================================

class VoucherListView(LoginRequiredMixin, ListView):
    """
    List all vouchers (auto-generated and manual).
    
    Filter by:
    - Voucher Type (JV, PV, RV)
    - Date Range
    - Posted Status
    """
    model = Voucher
    template_name = 'finance/voucher_list.html'
    context_object_name = 'vouchers'
    paginate_by = 25
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        from django.db.models import Prefetch
        
        # Optimized queryset with prefetch
        qs = Voucher.objects.filter(organization=org).select_related(
            'fiscal_year', 'fund', 'posted_by', 'created_by',
            'reversed_by', 'reversed_by_voucher'
        ).prefetch_related(
            Prefetch(
                'entries',
                queryset=JournalEntry.objects.select_related(
                    'budget_head', 
                    'budget_head__global_head',
                    'budget_head__function'
                ).order_by('id')
            )
        )
        
        # Filter by voucher type
        voucher_type = self.request.GET.get('type')
        if voucher_type:
            qs = qs.filter(voucher_type=voucher_type)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        
        # Filter by posted status
        status = self.request.GET.get('status')
        if status == 'posted':
            qs = qs.filter(is_posted=True)
        elif status == 'draft':
            qs = qs.filter(is_posted=False)
        
        return qs.order_by('-date', '-voucher_no')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'General Journal'
        context['filter_type'] = self.request.GET.get('type', '')
        context['filter_date_from'] = self.request.GET.get('date_from', '')
        context['filter_date_to'] = self.request.GET.get('date_to', '')
        context['filter_status'] = self.request.GET.get('status', '')
        return context


class VoucherCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """
    Create a manual Journal Voucher with multiple lines.
    
    Requires Dealing Assistant (Maker) role.
    Uses formset for journal entries with dynamic add/remove.
    Validates that Sum(Debit) == Sum(Credit).
    """
    model = Voucher
    template_name = 'finance/voucher_form.html'
    form_class = VoucherForm
    
    def get_success_url(self):
        return reverse('finance:voucher_detail', kwargs={'pk': self.object.pk})
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = getattr(self.request.user, 'organization', None)
        return kwargs
    
    def get_context_data(self, **kwargs):
        from django.forms import inlineformset_factory
        from apps.finance.forms import JournalEntryForm
        
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create Journal Voucher'
        
        JournalEntryFormSet = inlineformset_factory(
            Voucher,
            JournalEntry,
            form=JournalEntryForm,
            extra=0,
            can_delete=True,
            min_num=2,
            validate_min=True
        )
        
        if self.request.POST:
            context['formset'] = JournalEntryFormSet(
                self.request.POST,
                instance=self.object,
                form_kwargs={'organization': getattr(self.request.user, 'organization', None)}
            )
        else:
            context['formset'] = JournalEntryFormSet(
                instance=self.object,
                form_kwargs={'organization': getattr(self.request.user, 'organization', None)}
            )
        
        return context
    
    def form_valid(self, form):
        from django.forms import inlineformset_factory
        from apps.finance.forms import JournalEntryForm
        from decimal import Decimal
        
        context = self.get_context_data()
        formset = context['formset']
        
        # Validate formset
        if not formset.is_valid():
            return self.form_invalid(form)
        
        # Use atomic transaction
        with transaction.atomic():
            # Set organization
            user = self.request.user
            org = getattr(user, 'organization', None)
            
            form.instance.organization = org
            # voucher_type is now set from the form (JV or CV)
            form.instance.created_by = user
            
            # Determine fiscal year from date
            try:
                fiscal_year = FiscalYear.objects.filter(
                    start_date__lte=form.instance.date,
                    end_date__gte=form.instance.date
                ).first()
                
                if not fiscal_year:
                    messages.error(self.request, _('No fiscal year found for the selected date.'))
                    return self.form_invalid(form)
                    
                form.instance.fiscal_year = fiscal_year
            except Exception as e:
                messages.error(self.request, _('Error determining fiscal year: ') + str(e))
                return self.form_invalid(form)
            
            # Generate voucher number based on voucher type
            # Format: JV-YYYY-NNN or CV-YYYY-NNN
            voucher_type = form.instance.voucher_type
            year = fiscal_year.start_date.year
            # Lock the table to prevent race conditions
            last_voucher_no = Voucher.objects.filter(
                organization=org,
                fiscal_year=fiscal_year,
                voucher_type=voucher_type
            ).select_for_update().aggregate(
                max_no=models.Max('voucher_no')
            )['max_no']
            
            if last_voucher_no:
                match = re.search(r'-(\d+)$', last_voucher_no)
                if match:
                    next_num = int(match.group(1)) + 1
                else:
                    next_num = 1
            else:
                next_num = 1
            
            form.instance.voucher_no = f"{voucher_type}-{year}-{next_num:04d}"
            
            # Save voucher
            self.object = form.save()
            
            # Save formset
            formset.instance = self.object
            formset.save()
            
            # Calculate totals
            total_debit = Decimal('0.00')
            total_credit = Decimal('0.00')
            
            for entry in self.object.entries.all():
                total_debit += entry.debit
                total_credit += entry.credit
            
            # Validate balance
            # Validate balance
            if total_debit != total_credit:
                transaction.set_rollback(True)
                messages.error(
                    self.request,
                    _('Voucher is not balanced. Debit: {}, Credit: {}').format(
                        total_debit, total_credit
                    )
                )
                return self.form_invalid(form)
            
            if total_debit == Decimal('0.00'):
                transaction.set_rollback(True)
                messages.error(self.request, _('Voucher has no entries or all amounts are zero.'))
                return self.form_invalid(form)
            
            messages.success(self.request, _('Journal Voucher created successfully.'))
            return HttpResponseRedirect(self.get_success_url())


class VoucherDetailView(LoginRequiredMixin, DetailView):
    """
    Display voucher header and journal entries.
    
    Shows:
    - Voucher header info
    - Table of journal entries (Dr/Cr)
    - Post button if status is DRAFT
    """
    model = Voucher
    template_name = 'finance/voucher_detail.html'
    context_object_name = 'voucher'
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        return Voucher.objects.filter(organization=org).select_related(
            'fiscal_year', 'fund', 'posted_by', 'created_by'
        ).prefetch_related('entries__budget_head')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Voucher: {self.object.voucher_no}"
        context['entries'] = self.object.entries.all().select_related('budget_head')
        context['total_debit'] = self.object.get_total_debit()
        context['total_credit'] = self.object.get_total_credit()
        context['is_balanced'] = self.object.is_balanced()
        return context


@method_decorator(csrf_protect, name='dispatch')
class PostVoucherView(LoginRequiredMixin, CheckerRequiredMixin, View):
    """Post a voucher to the General Ledger."""
    
    def post(self, request, pk):
        user = request.user
        org = getattr(user, 'organization', None)
        
        logger.info(
            f"Voucher posting attempt - User: {user.username}, "
            f"Org: {org.code if org else 'None'}, Voucher PK: {pk}"
        )
        
        voucher = get_object_or_404(
            Voucher.objects.filter(organization=org),
            pk=pk
        )
        
        if voucher.is_posted:
            logger.warning(
                f"Attempted to post already posted voucher - "
                f"Voucher: {voucher.voucher_no}, User: {user.username}"
            )
            messages.warning(request, _('Voucher is already posted.'))
            return redirect('finance:voucher_detail', pk=pk)
        
        if not voucher.is_balanced():
            logger.error(
                f"Attempted to post unbalanced voucher - "
                f"Voucher: {voucher.voucher_no}, "
                f"Debit: {voucher.get_total_debit()}, "
                f"Credit: {voucher.get_total_credit()}"
            )
            messages.error(
                request,
                _('Cannot post unbalanced voucher. Debit: {}, Credit: {}').format(
                    voucher.get_total_debit(),
                    voucher.get_total_credit()
                )
            )
            return redirect('finance:voucher_detail', pk=pk)
        
        try:
            with transaction.atomic():
                voucher.post_voucher(user)
                logger.info(
                    f"Voucher posted successfully - "
                    f"Voucher: {voucher.voucher_no}, User: {user.username}"
                )
                messages.success(request, _('Voucher posted successfully.'))
        except Exception as e:
            logger.error(
                f"Error posting voucher - "
                f"Voucher: {voucher.voucher_no}, User: {user.username}, "
                f"Error: {str(e)}",
                exc_info=True
            )
            messages.error(request, _('Error posting voucher: ') + str(e))
        
        return redirect('finance:voucher_detail', pk=pk)


@method_decorator(csrf_protect, name='dispatch')
class UnpostVoucherView(LoginRequiredMixin, CheckerRequiredMixin, View):
    """
    Reverse a posted voucher by creating a reversal voucher.
    
    This implements professional accounting practice:
    - Does NOT delete or modify posted transactions
    - Creates a new REVERSAL voucher with swapped Dr/Cr
    - Maintains complete audit trail
    - Both vouchers remain in the system
    
    Only allowed if:
    - Voucher is currently posted
    - Voucher has not already been reversed
    - User has permission to unpost
    """
    
    def post(self, request, pk):
        user = request.user
        org = getattr(user, 'organization', None)
        
        voucher = get_object_or_404(
            Voucher.objects.filter(organization=org),
            pk=pk
        )
        
        # Check if already reversed
        if voucher.is_reversed:
            messages.warning(
                request, 
                _('Voucher has already been reversed. See reversal voucher: {}').format(
                    voucher.reversed_by_voucher.voucher_no
                )
            )
            return redirect('finance:voucher_detail', pk=pk)
        
        # Check if unposted
        if not voucher.is_posted:
            messages.warning(request, _('Voucher is not posted.'))
            return redirect('finance:voucher_detail', pk=pk)
        
        try:
            with transaction.atomic():
                reason = request.POST.get('reason', '').strip()
                
                # Validate reason is provided
                if not reason:
                    messages.error(
                        request, 
                        _('Reversal reason is required for audit compliance.')
                    )
                    return redirect('finance:voucher_detail', pk=pk)
                
                # Create reversal voucher
                reversal_voucher = voucher.unpost_voucher(user=user, reason=reason)
                
                messages.success(
                    request, 
                    _('Voucher reversed successfully. Reversal voucher {} created.').format(
                        reversal_voucher.voucher_no
                    )
                )
                
                # Redirect to the reversal voucher to show what was created
                return redirect('finance:voucher_detail', pk=reversal_voucher.pk)
                
        except Exception as e:
            messages.error(request, _('Error reversing voucher: ') + str(e))
        
        return redirect('finance:voucher_detail', pk=pk)


# ============================================================================
# AJAX Views for Dynamic Filtering
# ============================================================================

from django.shortcuts import render
from apps.finance.models import FunctionCode, AccountType
from apps.budgeting.models import Department


def load_functions(request):
    """
    AJAX view to load functions filtered by department.
    Used by VoucherForm header filters and BudgetHeadForm.
    Returns HTML with function options including default and usage notes.
    """
    department_id = request.GET.get('department')
    functions = FunctionCode.objects.none()
    default_id = None
    
    if department_id:
        try:
            dept = Department.objects.get(id=department_id)
            functions = dept.related_functions.all().order_by('code')
            default_id = dept.default_function_id if dept.default_function else None
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
    
    # Determine which template to use based on context
    # Budget head form uses global_head, expenditure uses budget_head
    template = request.GET.get('template', 'expenditure')
    if template == 'finance':
        template_path = 'finance/partials/function_options.html'
    else:
        template_path = 'expenditure/partials/function_options.html'
            
    return render(request, template_path, {
        'functions': functions,
        'default_id': default_id
    })


def load_global_heads(request):
    """
    HTMX view to load NAMHead options filtered by selected function.
    Returns HTML with option elements for the nam_head select field.
    
    Filters NAMHeads to show:
    - Universal heads (no applicable_functions specified)
    - Function-specific heads (where applicable_functions includes the selected function)
    
    NOTE: This view is deprecated with the new NAM CoA structure.
    Consider updating forms to use HierarchicalBudgetHeadWidget instead.
    """
    from django.db.models import Q
    
    function_id = request.GET.get('function')
    nam_heads = NAMHead.objects.none()
    
    if function_id:
        try:
            function = FunctionCode.objects.get(id=function_id)
            # Filter: Universal heads OR heads applicable to this function
            nam_heads = NAMHead.objects.filter(
                Q(applicable_functions__isnull=True) |  # Universal heads
                Q(applicable_functions=function)  # Function-specific heads
            ).select_related('minor__major').distinct().order_by('code')
        except (ValueError, TypeError, FunctionCode.DoesNotExist):
            pass
    
    return render(request, 'finance/partials/global_head_options.html', {
        'global_heads': nam_heads  # Keep template variable name for compatibility
    })



def _generate_cache_key(prefix, **params):
    """
    Helper function to generate consistent cache keys.
    
    Args:
        prefix: Cache key prefix (e.g., 'smart_search', 'budget_heads')
        **params: Key-value pairs to include in cache key
    
    Returns:
        str: Generated cache key with 5-minute TTL convention
    """
    # Sort params for consistent key generation
    param_str = '_'.join(f"{k}:{v}" for k, v in sorted(params.items()) if v)
    # Use MD5 hash for long parameter strings
    param_hash = md5(param_str.encode()).hexdigest()[:12]
    return f"cfms_{prefix}_{param_hash}"


def invalidate_budget_head_cache(org_id=None):
    """
    Invalidate all cached budget head search results.
    
    Args:
        org_id: Optional organization ID. If provided, only invalidates cache for that org.
                If None, clears all budget head caches (use with caution).
    
    This should be called when:
    - BudgetHead is created/updated/deleted
    - DepartmentFunctionConfiguration is modified
    - BudgetAllocation changes significantly
    """
    if org_id:
        # For now, we'll use a simple pattern-based cache clearing
        # In production, consider using cache tags or Redis patterns
        logger.info(f"Cache invalidation requested for org {org_id}")
        # Since LocMemCache doesn't support pattern deletion,
        # we rely on TTL expiration or manual clear_all
        # For Redis, you could use: cache.delete_pattern(f"cfms_*_org:{org_id}_*")
    else:
        logger.warning("Clearing ALL budget head cache - use sparingly!")
        # This is a nuclear option - clears everything
        # cache.clear()  # Commented out for safety
    
    return True


def load_budget_heads_options(request):
    """
    AJAX view to load budget head options filtered by department and/or function.
    
    NEW BEHAVIOR (after CoA restructuring):
    - Filters by department FK directly on BudgetHead (not via function anymore)
    - When both department AND function are provided: uses the most precise filter
    - Returns only heads for the specific department-function combination
    - CACHED for 5 minutes to improve performance
    
    Returns options as a script that updates all budget_head selects in the formset.
    """
    department_id = request.GET.get('department')
    function_id = request.GET.get('function')
    account_type = request.GET.get('account_type')
    
    # Get user organization for cache key
    user = request.user
    org = getattr(user, 'organization', None)
    org_id = org.id if org else 'none'
    
    # Check cache first
    cache_key = _generate_cache_key(
        'budget_heads_options',
        org=org_id,
        dept=department_id or '',
        func=function_id or '',
        acct=account_type or ''
    )
    
    cached_response = cache.get(cache_key)
    if cached_response:
        logger.debug(f"Cache HIT for {cache_key}")
        return cached_response
    
    logger.debug(f"Cache MISS for {cache_key}")
    department = None
    
    # Base queryset - all posting-allowed heads, exclude salary heads
    budget_heads = BudgetHead.objects.filter(
        posting_allowed=True,
        is_active=True
    ).exclude(
        global_head__code__startswith='A01'
    ).select_related(
        'global_head',
        'global_head__minor',
        'global_head__minor__major',
        'function',
        'department'
    ).order_by('global_head__code')
    
    if account_type:
        budget_heads = budget_heads.filter(global_head__account_type=account_type)
    
    # PRIMARY FILTER: Use department + function together for most precise results
    if department_id and function_id:
        try:
            department = Department.objects.get(id=department_id)
            # Use the new department FK directly for precise filtering
            budget_heads = budget_heads.filter(
                department_id=department_id,
                function_id=function_id
            )
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
    # Filter by function only (fallback - try to find department from budget heads)
    elif function_id:
        try:
            budget_heads = budget_heads.filter(function_id=function_id)
            # Get department for display - try from budget head's department first
            first_head = budget_heads.first()
            if first_head and first_head.department:
                department = first_head.department
            else:
                # Fallback: Try to find via M2M (legacy behavior)
                function = FunctionCode.objects.get(id=function_id)
                dept_with_function = Department.objects.filter(related_functions=function).first()
                if dept_with_function:
                    department = dept_with_function
        except (ValueError, TypeError, FunctionCode.DoesNotExist):
            pass
    # Filter by department only
    elif department_id:
        try:
            department = Department.objects.get(id=department_id)
            # Use the new department FK directly
            budget_heads = budget_heads.filter(department=department)
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
    
    # Filter by allocation (only show heads with budget)
    try:
        user = request.user
        org = getattr(user, 'organization', None)
        if org:
            from django.apps import apps
            from django.db.models import Exists, OuterRef
            
            FiscalYear = apps.get_model('budgeting', 'FiscalYear')
            BudgetAllocation = apps.get_model('budgeting', 'BudgetAllocation')
            
            # Get current operating fiscal year
            fy = FiscalYear.get_current_operating_year()
            if fy:
                has_allocation = BudgetAllocation.objects.filter(
                    organization=org,
                    fiscal_year=fy,
                    budget_head=OuterRef('pk')
                )
                
                budget_heads = budget_heads.annotate(
                    has_allocation=Exists(has_allocation)
                ).filter(has_allocation=True)
    except Exception as e:
        print(f"ERROR in load_budget_heads_options: {e}")
        # Fallback: don't filter by allocation if error occurs
        pass
    
    print(f"DEBUG: load_budget_heads_options params - Dept: {department_id}, Function: {function_id}, Type: {account_type}")
    print(f"DEBUG: Returning {budget_heads.count()} budget heads")
    
    response = render(request, 'finance/partials/budget_head_formset_options.html', {
        'budget_heads': budget_heads,
        'department': department
    })
    
    # Cache the response for 5 minutes (300 seconds)
    cache.set(cache_key, response, 300)
    logger.debug(f"Cached budget_heads_options: {cache_key}")
    
    return response


def load_existing_subheads(request):
    """
    AJAX view to fetch existing sub-heads for a given NAM head.
    Used in SubHead admin to show what sub-codes are already taken.
    
    Returns HTML snippet showing existing sub-heads and suggesting next available code.
    
    NOTE: Updated for NAM CoA structure.
    """
    nam_head_id = request.GET.get('nam_head')
    
    existing_subheads = []
    next_available_code = '01'
    
    if nam_head_id:
        try:
            existing_subheads = SubHead.objects.filter(
                nam_head_id=nam_head_id,
                is_active=True
            ).select_related('nam_head').order_by('sub_code')
            
            # Find next available sub-code
            used_codes = [sh.sub_code for sh in existing_subheads]
            for code_num in range(1, 100):
                suggested_code = f'{code_num:02d}'
                if suggested_code not in used_codes:
                    next_available_code = suggested_code
                    break
        except (ValueError, TypeError):
            pass
    
    return render(request, 'finance/partials/existing_subheads.html', {
        'existing_subheads': existing_subheads,
        'next_available_code': next_available_code
    })


def budget_head_search_api(request):
    """
    AJAX API endpoint for Select2 to search budget heads dynamically.
    
    Returns JSON with results paginated for efficient loading of large datasets.
    Supports search by code, name, and filtering by account_type and function.
    """
    search_term = request.GET.get('q', '').strip()
    account_type = request.GET.get('account_type', '').strip()
    function_id = request.GET.get('function_id', '').strip()
    page = int(request.GET.get('page', 1))
    page_size = 30  # Results per page
    
    # Base queryset - only postable, active budget heads
    budget_heads = BudgetHead.objects.filter(
        posting_allowed=True,
        is_active=True
    ).select_related(
        'nam_head',
        'nam_head__minor',
        'sub_head',
        'sub_head__nam_head',
        'function'
    )
    
    # Filter by function if specified (most important filter to avoid duplicates)
    if function_id:
        budget_heads = budget_heads.filter(function_id=function_id)
    
    # Filter by account type if specified
    if account_type:
        budget_heads = budget_heads.filter(
            models.Q(nam_head__account_type=account_type) |
            models.Q(sub_head__nam_head__account_type=account_type)
        )
    
    # Search by code or name
    if search_term:
        budget_heads = budget_heads.filter(
            models.Q(nam_head__code__icontains=search_term) |
            models.Q(nam_head__name__icontains=search_term) |
            models.Q(sub_head__nam_head__code__icontains=search_term) |
            models.Q(sub_head__nam_head__name__icontains=search_term) |
            models.Q(sub_head__local_description__icontains=search_term) |
            models.Q(function__code__icontains=search_term)
        )
    
    # Order by code for consistent results
    budget_heads = budget_heads.order_by('nam_head__code', 'sub_head__sub_code', 'function__code')
    
    # Pagination
    total_count = budget_heads.count()
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_results = budget_heads[start_idx:end_idx]
    
    # Format results for Select2
    results = []
    for bh in page_results:
        # Get code and name from nam_head or sub_head
        if bh.sub_head:
            code = bh.sub_head.code
            name = bh.sub_head.local_description or bh.sub_head.nam_head.name
            account_type_val = bh.sub_head.nam_head.account_type
        elif bh.nam_head:
            code = bh.nam_head.code
            name = bh.nam_head.name
            account_type_val = bh.nam_head.account_type
        else:
            continue
        
        # Format display text: "CODE - Name (Function)"
        display_text = f"{code} - {name}"
        if bh.function:
            display_text += f" ({bh.function.code})"
        
        results.append({
            'id': bh.id,
            'text': display_text,
            'code': code,
            'account_type': account_type_val
        })
    
    # Return Select2 format
    return JsonResponse({
        'results': results,
        'pagination': {
            'more': end_idx < total_count
        }
    })


def smart_budget_head_search_api(request):
    """
    Enhanced API endpoint for Smart Budget Head Selection Widget.
    
    Returns comprehensive budget head information including:
    - Budget availability
    - Category grouping (Salary, Operating, Assets, etc.)
    - Recently used heads
    - Favorite heads
    - Current utilization percentage
    
    This powers the modern, user-friendly budget head selection interface.
    CACHED for 5 minutes to improve performance.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"smart_budget_head_search_api called by {request.user}, params: {request.GET}")
    
    from decimal import Decimal
    from apps.finance.models import BudgetHeadFavorite, BudgetHeadUsageHistory,  DepartmentFunctionConfiguration
    from apps.budgeting.models import FiscalYear, BudgetAllocation
    
    # Get parameters
    search_term = request.GET.get('q', '').strip()
    department_id = request.GET.get('department_id', '').strip()
    function_id = request.GET.get('function_id', '').strip()
    account_type = request.GET.get('account_type', '').strip()
    include_favorites = request.GET.get('include_favorites', 'true') == 'true'
    include_recently_used = request.GET.get('include_recently_used', 'true') == 'true'
    page = int(request.GET.get('page', 1))
    page_size = 20
    
    user = request.user
    org = getattr(user, 'organization', None)
    
    if not org:
        logger.warning(f"User {user.username} has no organization assigned")
        return JsonResponse({
            'results': [{
                'id': '',
                'text': '⚠️ Your account is not assigned to any organization. Contact your administrator.',
                'disabled': True
            }],
            'favorites': [],
            'recently_used': [],
            'pagination': {'more': False, 'total': 0, 'page': 1}
        })
    
    # Check cache for main results (excluding user-specific favorites/recently_used)
    # Cache key includes all query parameters except user-specific flags
    cache_key = _generate_cache_key(
        'smart_search',
        org=org.id,
        dept=department_id,
        func=function_id,
        acct=account_type,
        q=search_term,
        page=page
    )
    
    # Try to get cached main results
    cached_main_results = cache.get(cache_key)
    
    if cached_main_results:
        logger.debug(f"Cache HIT for smart_search: {cache_key}")
        results = cached_main_results['results']
        pagination_info = cached_main_results['pagination']
    else:
        logger.debug(f"Cache MISS for smart_search: {cache_key}")
        
        # Get current fiscal year
        fiscal_year = FiscalYear.get_current_operating_year()
        if not fiscal_year:
            return JsonResponse({'error': 'No active fiscal year'}, status=400)
        
        # Base queryset - use DepartmentFunctionConfiguration for filtering
        budget_heads = BudgetHead.objects.filter(
            posting_allowed=True,
            is_active=True
        ).select_related(
            'nam_head',
            'nam_head__minor',
            'nam_head__minor__major',
            'sub_head',
            'sub_head__nam_head',
            'sub_head__nam_head__minor',
            'sub_head__nam_head__minor__major',
            'function',
            'department',
            'fund'
        )
        
        # Filter by department and function if provided
        if department_id and function_id:
            try:
                config = DepartmentFunctionConfiguration.objects.get(
                    department_id=department_id,
                    function_id=function_id
                )
                # Get allowed NAM head IDs
                allowed_head_ids = list(config.allowed_nam_heads.values_list('id', flat=True))
                
                # If configuration exists but has no allowed heads, show all (permissive during transition)
                if allowed_head_ids:
                    budget_heads = budget_heads.filter(
                        department_id=department_id,
                        function_id=function_id
                    ).filter(
                        Q(nam_head_id__in=allowed_head_ids) |
                        Q(sub_head__nam_head_id__in=allowed_head_ids)
                    )
                    logger.debug(f"Using DepartmentFunctionConfiguration with {len(allowed_head_ids)} allowed NAM heads")
                else:
                    # Config exists but empty - show all for this dept/func during transition
                    logger.warning(f"DepartmentFunctionConfiguration exists but has no allowed_nam_heads for dept={department_id}, func={function_id}")
                    budget_heads = budget_heads.filter(
                        department_id=department_id,
                        function_id=function_id
                    )
            except DepartmentFunctionConfiguration.DoesNotExist:
                logger.warning(f"No DepartmentFunctionConfiguration found for dept={department_id}, func={function_id}")
                # Fallback to basic filtering - show all budget heads for this dept/func
                budget_heads = budget_heads.filter(
                    department_id=department_id,
                    function_id=function_id
                )
        elif function_id:
            budget_heads = budget_heads.filter(function_id=function_id)
        elif department_id:
            budget_heads = budget_heads.filter(department_id=department_id)
        
        # Filter by account type
        if account_type:
            budget_heads = budget_heads.filter(
                Q(nam_head__account_type=account_type) |
                Q(sub_head__nam_head__account_type=account_type)
            )
        
        # Search filter
        if search_term:
            budget_heads = budget_heads.filter(
                Q(nam_head__code__icontains=search_term) |
                Q(nam_head__name__icontains=search_term) |
                Q(sub_head__nam_head__code__icontains=search_term) |
                Q(sub_head__nam_head__name__icontains=search_term) |
                Q(sub_head__local_description__icontains=search_term)
            )
        
        # Order by code (NAM head code, then sub-head code if applicable)
        budget_heads = budget_heads.order_by('nam_head__code', 'sub_head__sub_code')
        
        # Pagination
        total_count = budget_heads.count()
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_results = budget_heads[start_idx:end_idx]
        
        logger.debug(f"Found {total_count} budget heads for dept={department_id}, func={function_id}, search='{search_term}'")
        
        # Build results with enhanced information
        results = []
        for bh in page_results:
            # Get budget allocation
            try:
                allocation = BudgetAllocation.objects.get(
                    organization=org,
                    fiscal_year=fiscal_year,
                    budget_head=bh
                )
                allocated_amount = float(allocation.revised_allocation)
                utilized_amount = float(allocation.spent_amount)
                available_amount = float(allocation.get_available_budget())
                utilization_percentage = float((allocation.spent_amount / allocation.revised_allocation * 100) if allocation.revised_allocation > 0 else 0)
            except BudgetAllocation.DoesNotExist:
                allocated_amount = 0.0
                utilized_amount = 0.0
                available_amount = 0.0
                utilization_percentage = 0.0
            
            # Get code and name from nam_head or sub_head
            if bh.sub_head:
                code = bh.sub_head.code  # Property that returns nam_head.code + sub_code
                name = bh.sub_head.local_description or bh.sub_head.nam_head.name
                account_type = bh.sub_head.nam_head.account_type
            elif bh.nam_head:
                code = bh.nam_head.code
                name = bh.nam_head.name
                account_type = bh.nam_head.account_type
            else:
                # Shouldn't happen, but handle gracefully
                continue
            
            # Categorize budget head
            if code.startswith('A01'):
                category = 'Salary'
            elif code.startswith(('A03', 'A04')):
                category = 'Operating'
            elif code.startswith('C'):
                category = 'Assets'
            elif code.startswith('D'):
                category = 'Liabilities'
            else:
                category = 'Other'
            
            results.append({
                'id': bh.id,
                'code': code,
                'name': name,
                'display_text': f"{code} - {name}",
                'category': category,
                'account_type': account_type,
                'function_code': bh.function.code if bh.function else '',
                'department_name': bh.department.name if bh.department else '',
                'budget': {
                    'allocated': allocated_amount,
                    'utilized': utilized_amount,
                    'available': available_amount,
                    'utilization_percentage': utilization_percentage,
                    'has_budget': allocated_amount > 0,
                    'is_over_budget': available_amount < 0,
                },
                'is_favorite': False,  # Will be updated below if needed
            })
        
        pagination_info = {
            'more': end_idx < total_count,
            'total': total_count,
            'page': page,
        }
        
        # Cache the main results for 5 minutes (300 seconds)
        cache.set(cache_key, {
            'results': results,
            'pagination': pagination_info
        }, 300)
        logger.debug(f"Cached smart_search results: {cache_key}")
    
    # Update favorites flag in results (user-specific, not cached)
    if include_favorites:
        favorite_ids = set(BudgetHeadFavorite.objects.filter(
            user=user,
            organization=org
        ).values_list('budget_head_id', flat=True))
        
        for result in results:
            result['is_favorite'] = result['id'] in favorite_ids
    
    # Get favorites if requested
    favorites = []
    if include_favorites and page == 1:
        favorite_heads = BudgetHeadFavorite.objects.filter(
            user=user,
            organization=org
        ).select_related(
            'budget_head__nam_head',
            'budget_head__sub_head__nam_head'
        ).order_by('-created_at')[:5]
        
        for fav in favorite_heads:
            bh = fav.budget_head
            if bh.sub_head:
                code = bh.sub_head.code
                name = bh.sub_head.local_description or bh.sub_head.nam_head.name
            elif bh.nam_head:
                code = bh.nam_head.code
                name = bh.nam_head.name
            else:
                continue
            
            favorites.append({
                'id': bh.id,
                'code': code,
                'name': name,
            })
    
    # Get recently used if requested
    recently_used = []
    if include_recently_used and page == 1:
        recent_usage = BudgetHeadUsageHistory.objects.filter(
            user=user,
            organization=org
        ).select_related(
            'budget_head__nam_head',
            'budget_head__sub_head__nam_head'
        ).order_by('-last_used')[:5]
        
        for usage in recent_usage:
            bh = usage.budget_head
            if bh.sub_head:
                code = bh.sub_head.code
                name = bh.sub_head.local_description or bh.sub_head.nam_head.name
            elif bh.nam_head:
                code = bh.nam_head.code
                name = bh.nam_head.name
            else:
                continue
            
            recently_used.append({
                'id': bh.id,
                'code': code,
                'name': name,
                'usage_count': usage.usage_count,
            })
    
    return JsonResponse({
        'results': results,
        'favorites': favorites,
        'recently_used': recently_used,
        'pagination': {
            'more': pagination_info.get('more', False),
            'total': pagination_info.get('total', 0),
            'page': pagination_info.get('page', 1),
        },
        'debug_info': {
            'department_id': department_id,
            'function_id': function_id,
            'search_term': search_term,
            'total_count': pagination_info.get('total', 0),
        } if request.GET.get('debug') == '1' else None
    })


def toggle_budget_head_favorite(request):
    """
    API endpoint to add/remove a budget head from user's favorites.
    
    Method: POST
    Parameters:
        - budget_head_id: ID of the budget head
        - action: 'add' or 'remove'
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    from apps.finance.models import BudgetHeadFavorite
    import json
    
    try:
        data = json.loads(request.body)
        budget_head_id = data.get('budget_head_id')
        action = data.get('action')
        
        user = request.user
        org = getattr(user, 'organization', None)
        
        if not org:
            return JsonResponse({'error': 'No organization context'}, status=400)
        
        if action == 'add':
            BudgetHeadFavorite.objects.get_or_create(
                user=user,
                budget_head_id=budget_head_id,
                organization=org
            )
            return JsonResponse({'success': True, 'message': 'Added to favorites'})
        
        elif action == 'remove':
            BudgetHeadFavorite.objects.filter(
                user=user,
                budget_head_id=budget_head_id,
                organization=org
            ).delete()
            return JsonResponse({'success': True, 'message': 'Removed from favorites'})
        
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def record_budget_head_usage(request):
    """
    API endpoint to record budget head usage for recently used tracking.
    
    Method: POST
    Parameters:
        - budget_head_id: ID of the budget head used
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    from apps.finance.models import BudgetHeadUsageHistory
    import json
    
    try:
        data = json.loads(request.body)
        budget_head_id = data.get('budget_head_id')
        
        user = request.user
        org = getattr(user, 'organization', None)
        
        if not org:
            return JsonResponse({'error': 'No organization context'}, status=400)
        
        budget_head = BudgetHead.objects.get(id=budget_head_id)
        BudgetHeadUsageHistory.record_usage(user, budget_head, org)
        
        return JsonResponse({'success': True, 'message': 'Usage recorded'})
    
    except BudgetHead.DoesNotExist:
        return JsonResponse({'error': 'Budget head not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

