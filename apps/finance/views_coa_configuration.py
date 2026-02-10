"""
Views for CoA Configuration at Provincial Level
Manages Department-Function-Head valid combinations
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, TemplateView
from django.views import View
from django.utils.translation import gettext_lazy as _
import logging

from apps.finance.models import NAMHead, AccountType, BudgetHead, FunctionCode
from apps.budgeting.models import Department
from apps.users.permissions import SuperAdminRequiredMixin

logger = logging.getLogger(__name__)


class DepartmentFunctionConfigurationMatrixView(LoginRequiredMixin, SuperAdminRequiredMixin, TemplateView):
    """
    Department-Function Configuration Matrix - PRIMARY ACCESS CONTROL INTERFACE
    
    This is the RECOMMENDED interface for managing CoA access control.
    
    Displays a matrix showing all Department-Function combinations and their
    configuration status. Allows easy management of allowed NAM heads for
    each combination via DepartmentFunctionConfiguration.
    
    This is the single source of truth for access control, replacing:
        - GlobalHead.scope and applicable_departments (DEPRECATED)
        - NAMHead.scope and applicable_departments (DEPRECATED)
    
    All access control is now centralized in DepartmentFunctionConfiguration.allowed_nam_heads.
    """
    template_name = 'finance/dept_func_config_matrix.html'
    
    def get_context_data(self, **kwargs):
        from apps.finance.models import DepartmentFunctionConfiguration
        
        context = super().get_context_data(**kwargs)
        
        # Get all active departments and functions
        departments = Department.objects.filter(is_active=True).order_by('name')
        functions = FunctionCode.objects.filter(is_active=True).order_by('code')
        
        # Build matrix data: {dept_id: {func_id: config_or_none}}
        matrix = {}
        for dept in departments:
            matrix[dept.id] = {}
            for func in functions:
                # Try to get existing configuration
                try:
                    config = DepartmentFunctionConfiguration.objects.prefetch_related(
                        'allowed_nam_heads'
                    ).get(department=dept, function=func)
                    matrix[dept.id][func.id] = {
                        'config': config,
                        'head_count': config.get_head_count(),
                        'status': config.get_completion_status(),
                        'is_complete': config.is_complete(),
                        'is_locked': config.is_locked,
                    }
                except DepartmentFunctionConfiguration.DoesNotExist:
                    matrix[dept.id][func.id] = {
                        'config': None,
                        'head_count': 0,
                        'status': 'Not Configured',
                        'is_complete': False,
                        'is_locked': False,
                    }
        
        # Calculate statistics
        total_combinations = departments.count() * functions.count()
        configured_count = DepartmentFunctionConfiguration.objects.count()
        complete_count = DepartmentFunctionConfiguration.objects.annotate(
            head_count=Count('allowed_nam_heads')
        ).filter(head_count__gte=10).count()
        
        context['departments'] = departments
        context['functions'] = functions
        context['matrix'] = matrix
        context['total_combinations'] = total_combinations
        context['configured_count'] = configured_count
        context['complete_count'] = complete_count
        context['completion_percentage'] = round((complete_count / total_combinations * 100) if total_combinations > 0 else 0, 1)
        
        return context


class DepartmentFunctionConfigurationDetailView(LoginRequiredMixin, SuperAdminRequiredMixin, TemplateView):
    """
    Configure allowed NAM heads for a specific Department-Function combination.
    
    This is the PRIMARY and RECOMMENDED interface for access control configuration.
    
    This view manages DepartmentFunctionConfiguration.allowed_nam_heads, which is
    the single source of truth for access control (replacing deprecated scope fields).
    
    Purpose:
        Admin selects which NAM heads are valid for a specific dept-func pair.
        This configuration is then used throughout the system for filtering and validation.
    """
    template_name = 'finance/dept_func_config_detail.html'
    
    def get_context_data(self, **kwargs):
        from apps.finance.models import DepartmentFunctionConfiguration
        
        context = super().get_context_data(**kwargs)
        
        dept_id = kwargs.get('dept_id')
        func_id = kwargs.get('func_id')
        
        department = get_object_or_404(Department, pk=dept_id, is_active=True)
        function = get_object_or_404(FunctionCode, pk=func_id, is_active=True)
        
        # Get or create configuration
        config, created = DepartmentFunctionConfiguration.objects.get_or_create(
            department=department,
            function=function,
            defaults={'notes': 'Created via configuration interface'}
        )
        
        # Get all global heads with annotation of whether they're selected
        search = self.request.GET.get('search', '')
        account_type = self.request.GET.get('account_type', '')
        
        global_heads = NAMHead.objects.select_related(
            'minor', 'minor__major'
        ).order_by('code')
        
        # Apply filters
        if search:
            global_heads = global_heads.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )
        
        if account_type:
            global_heads = global_heads.filter(account_type=account_type)
        
        # Filter by function applicability
        # NOTE: The applicable_functions field on NAMHead is deprecated.
        # We show all heads here and let DepartmentFunctionConfiguration control access.
        # This maintains backward compatibility while new configurations use only allowed_nam_heads.
        global_heads = global_heads.annotate(
            func_restriction_count=Count('applicable_functions')
        ).filter(
            Q(func_restriction_count=0) |  # No restrictions = universal (deprecated field)
            Q(applicable_functions=function)  # Or specifically assigned (deprecated field)
        ).distinct()
        
        # Get currently selected heads
        selected_head_ids = set(config.allowed_nam_heads.values_list('id', flat=True))
        
        # Annotate each head with selection status and sub-head count
        heads_data = []
        for head in global_heads:
            sub_heads_count = head.sub_heads.filter(is_active=True).count()
            heads_data.append({
                'head': head,
                'is_selected': head.id in selected_head_ids,
                'sub_heads_count': sub_heads_count,
                'major_name': head.minor.major.name if head.minor and head.minor.major else '',
                'minor_name': head.minor.name if head.minor else '',
            })
        
        context['department'] = department
        context['function'] = function
        context['config'] = config
        context['heads_data'] = heads_data
        context['selected_count'] = len(selected_head_ids)
        context['account_types'] = AccountType.choices
        context['search'] = search
        context['account_type'] = account_type
        
        return context
    
    def post(self, request, *args, **kwargs):
        from apps.finance.models import DepartmentFunctionConfiguration
        
        dept_id = kwargs.get('dept_id')
        func_id = kwargs.get('func_id')
        
        department = get_object_or_404(Department, pk=dept_id, is_active=True)
        function = get_object_or_404(FunctionCode, pk=func_id, is_active=True)
        
        config, created = DepartmentFunctionConfiguration.objects.get_or_create(
            department=department,
            function=function
        )
        
        action = request.POST.get('action')
        
        if action == 'update_heads':
            # Update allowed heads
            selected_head_ids = request.POST.getlist('selected_heads')
            config.allowed_nam_heads.set(selected_head_ids)
            
            messages.success(
                request,
                f'Updated configuration: {len(selected_head_ids)} heads allowed for {department.name} - {function.code}'
            )
        
        elif action == 'lock_config':
            config.is_locked = True
            config.save()
            messages.success(request, f'Configuration locked for {department.name} - {function.code}')
        
        elif action == 'unlock_config':
            config.is_locked = False
            config.save()
            messages.success(request, f'Configuration unlocked for {department.name} - {function.code}')
        
        elif action == 'update_notes':
            notes = request.POST.get('notes', '')
            config.notes = notes
            config.save()
            messages.success(request, 'Notes updated')
        
        return redirect(reverse_lazy('finance:dept_func_config_detail', kwargs={
            'dept_id': dept_id,
            'func_id': func_id
        }))
