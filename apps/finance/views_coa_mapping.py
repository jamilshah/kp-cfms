"""
Views for CoA Department Mapping Management

DEPRECATED: CoADepartmentMappingView removed as part of GlobalHead consolidation.
Access control now managed via DepartmentFunctionConfiguration.allowed_nam_heads.

BudgetHeadDepartmentAssignmentView also deprecated - departments now assigned 
automatically during bulk budget head creation from configuration.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, FormView
from django.utils.translation import gettext_lazy as _

from apps.finance.models import GlobalHead, AccountType, BudgetHead, FunctionCode
from apps.budgeting.models import Department
from apps.users.permissions import SuperAdminRequiredMixin


# ============================================================================
# DEPRECATED: CoADepartmentMappingView (removed 2026-02-10)
# ============================================================================
# This view managed GlobalHead.scope and applicable_departments fields.
# Replaced by DepartmentFunctionConfiguration.allowed_nam_heads which provides
# unified access control at the NAM Head level.
#
# Migration path: Use DepartmentFunctionConfigurationMatrixView instead.
# ============================================================================


class BudgetHeadDepartmentAssignmentView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """
    View for managing BudgetHead department assignments.
    Assigns each budget head to a specific department for filtering and access control.
    
    Updated to work with the new NAM CoA structure (nam_head/sub_head).
    """
    model = BudgetHead
    template_name = 'finance/budget_head_department_assignment.html'
    context_object_name = 'budget_heads'
    paginate_by = 100
    
    def get_queryset(self):
        queryset = BudgetHead.objects.select_related(
            'nam_head', 'sub_head', 'sub_head__nam_head',
            'function', 'department', 'fund'
        ).order_by('function__code', 'nam_head__code', 'sub_head__sub_code')
        
        # Filter by function
        function_id = self.request.GET.get('function')
        if function_id:
            queryset = queryset.filter(function_id=function_id)
        
        # Filter by account type (check both nam_head and sub_head's parent)
        account_type = self.request.GET.get('account_type')
        if account_type and account_type in dict(AccountType.choices):
            queryset = queryset.filter(
                Q(nam_head__account_type=account_type) |
                Q(sub_head__nam_head__account_type=account_type)
            )
        
        # Filter by department (including unmapped)
        dept_filter = self.request.GET.get('department')
        if dept_filter == 'UNMAPPED':
            queryset = queryset.filter(department__isnull=True)
        elif dept_filter:
            queryset = queryset.filter(department_id=dept_filter)
        
        # Search by code or name
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nam_head__code__icontains=search) | 
                Q(nam_head__name__icontains=search) |
                Q(sub_head__nam_head__code__icontains=search) |
                Q(sub_head__name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['functions'] = FunctionCode.objects.filter(is_active=True).order_by('code')
        context['account_types'] = AccountType.choices
        
        # Current filter values
        context['selected_function'] = self.request.GET.get('function', '')
        context['selected_account_type'] = self.request.GET.get('account_type', '')
        context['selected_department'] = self.request.GET.get('department', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        # Statistics
        context['total_heads'] = BudgetHead.objects.count()
        context['assigned_count'] = BudgetHead.objects.filter(department__isnull=False).count()
        context['unmapped_count'] = BudgetHead.objects.filter(department__isnull=True).count()
        
        # Unmapped functions summary
        unmapped_functions = BudgetHead.objects.filter(
            department__isnull=True
        ).values('function__code', 'function__name').annotate(
            count=Count('id')
        ).order_by('function__code')[:10]
        context['unmapped_functions'] = unmapped_functions
        
        # Build query string for pagination
        query_params = []
        for key, value in self.request.GET.items():
            if key != 'page' and value:
                query_params.append(f'{key}={value}')
        context['query_string'] = '&' + '&'.join(query_params) if query_params else ''
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle bulk assignment of departments to budget heads."""
        action = request.POST.get('action')
        
        if action == 'bulk_assign':
            head_ids = request.POST.getlist('selected_heads')
            department_id = request.POST.get('bulk_department')
            
            if head_ids and department_id:
                try:
                    department = Department.objects.get(id=department_id)
                    updated = BudgetHead.objects.filter(pk__in=head_ids).update(
                        department=department
                    )
                    messages.success(
                        request, 
                        f'Assigned {updated} budget head(s) to {department.name}'
                    )
                except Department.DoesNotExist:
                    messages.error(request, 'Invalid department selected')
            else:
                messages.warning(request, 'Please select budget heads and a department')
        
        elif action == 'assign_single':
            head_id = request.POST.get('head_id')
            department_id = request.POST.get('department')
            
            if head_id and department_id:
                try:
                    budget_head = BudgetHead.objects.get(pk=head_id)
                    department = Department.objects.get(id=department_id)
                    budget_head.department = department
                    budget_head.save()
                    messages.success(
                        request, 
                        f'{budget_head.code} assigned to {department.name}'
                    )
                except (BudgetHead.DoesNotExist, Department.DoesNotExist):
                    messages.error(request, 'Invalid budget head or department')
        
        return redirect(request.get_full_path())
