"""
Views for CoA Configuration at Provincial Level
Manages Department-Function-Head valid combinations
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, TemplateView
from django.views import View
from django.utils.translation import gettext_lazy as _

from apps.finance.models import GlobalHead, AccountType, BudgetHead, FunctionCode
from apps.budgeting.models import Department
from apps.users.permissions import SuperAdminRequiredMixin


class ConfigureDepartmentFunctionHeadView(LoginRequiredMixin, SuperAdminRequiredMixin, TemplateView):
    """
    Provincial Level: Configure valid Department-Function-Head combinations.
    
    This creates the lookup table that TMAs use during budget preparation.
    TMAs can only create BudgetHeads from these configured combinations.
    """
    template_name = 'finance/configure_dept_function_head.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        selected_dept = self.request.GET.get('department')
        selected_func = self.request.GET.get('function')
        account_type = self.request.GET.get('account_type')
        search = self.request.GET.get('search', '')
        
        # Base queryset
        global_heads = GlobalHead.objects.select_related(
            'minor', 'minor__major'
        ).prefetch_related(
            'applicable_departments',
            'applicable_functions'
        ).order_by('code')
        
        # Apply filters
        if account_type and account_type in dict(AccountType.choices):
            global_heads = global_heads.filter(account_type=account_type)
        
        if search:
            global_heads = global_heads.filter(
                Q(code__icontains=search) | Q(name__icontains=search)
            )
        
        # If department selected, show only heads applicable to that department
        if selected_dept:
            global_heads = global_heads.filter(
                Q(scope='UNIVERSAL') | Q(applicable_departments__id=selected_dept)
            ).distinct()
        
        # If function selected, filter further
        if selected_func:
            # Show universal heads OR heads assigned to this function
            global_heads = global_heads.filter(
                Q(applicable_functions__isnull=True) | Q(applicable_functions__id=selected_func)
            ).distinct()
        
        # Annotate with counts
        global_heads = global_heads.annotate(
            dept_count=Count('applicable_departments', distinct=True),
            func_count=Count('applicable_functions', distinct=True)
        )
        
        # Master data
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['functions'] = FunctionCode.objects.filter(is_active=True).order_by('code')
        context['account_types'] = AccountType.choices
        context['global_heads'] = global_heads[:100]  # Limit for performance
        
        # Selected filters
        context['selected_dept'] = selected_dept
        context['selected_func'] = selected_func
        context['selected_account_type'] = account_type
        context['search_query'] = search
        
        # Statistics
        if selected_dept and selected_func:
            # Count configured heads for this dept-func combination
            context['configured_count'] = global_heads.count()
            dept = Department.objects.get(pk=selected_dept) if selected_dept else None
            func = FunctionCode.objects.get(pk=selected_func) if selected_func else None
            context['selected_dept_obj'] = dept
            context['selected_func_obj'] = func
        
        context['total_global_heads'] = GlobalHead.objects.count()
        context['universal_heads'] = GlobalHead.objects.filter(scope='UNIVERSAL').count()
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle bulk assignment of departments and functions to global heads."""
        action = request.POST.get('action')
        
        if action == 'assign_to_department':
            # Assign selected heads to selected department(s)
            head_ids = request.POST.getlist('selected_heads')
            dept_ids = request.POST.getlist('departments')
            
            if not head_ids:
                messages.warning(request, 'No heads selected')
                return redirect(request.get_full_path())
            
            if not dept_ids:
                messages.warning(request, 'No departments selected')
                return redirect(request.get_full_path())
            
            # Update each head
            for head_id in head_ids:
                head = GlobalHead.objects.get(pk=head_id)
                head.scope = 'DEPARTMENTAL'
                head.save()
                # Add departments (don't replace, add to existing)
                head.applicable_departments.add(*dept_ids)
            
            messages.success(
                request, 
                f'Assigned {len(head_ids)} head(s) to {len(dept_ids)} department(s)'
            )
            
        elif action == 'assign_to_function':
            # Assign selected heads to selected function(s)
            head_ids = request.POST.getlist('selected_heads')
            func_ids = request.POST.getlist('functions')
            
            if not head_ids:
                messages.warning(request, 'No heads selected')
                return redirect(request.get_full_path())
            
            if not func_ids:
                messages.warning(request, 'No functions selected')
                return redirect(request.get_full_path())
            
            # Update each head
            for head_id in head_ids:
                head = GlobalHead.objects.get(pk=head_id)
                # Add functions (don't replace, add to existing)
                head.applicable_functions.add(*func_ids)
            
            messages.success(
                request, 
                f'Assigned {len(head_ids)} head(s) to {len(func_ids)} function(s)'
            )
            
        elif action == 'mark_universal':
            # Mark selected heads as universal (available to all dept-func combinations)
            head_ids = request.POST.getlist('selected_heads')
            
            if not head_ids:
                messages.warning(request, 'No heads selected')
                return redirect(request.get_full_path())
            
            GlobalHead.objects.filter(pk__in=head_ids).update(scope='UNIVERSAL')
            # Clear restrictions
            for head_id in head_ids:
                head = GlobalHead.objects.get(pk=head_id)
                head.applicable_departments.clear()
                head.applicable_functions.clear()
            
            messages.success(request, f'Marked {len(head_ids)} head(s) as Universal')
            
        elif action == 'remove_from_department':
            # Remove selected heads from selected department
            head_ids = request.POST.getlist('selected_heads')
            dept_ids = request.POST.getlist('departments')
            
            if not head_ids or not dept_ids:
                messages.warning(request, 'No heads or departments selected')
                return redirect(request.get_full_path())
            
            for head_id in head_ids:
                head = GlobalHead.objects.get(pk=head_id)
                head.applicable_departments.remove(*dept_ids)
            
            messages.success(
                request, 
                f'Removed {len(head_ids)} head(s) from {len(dept_ids)} department(s)'
            )
            
        elif action == 'remove_from_function':
            # Remove selected heads from selected function
            head_ids = request.POST.getlist('selected_heads')
            func_ids = request.POST.getlist('functions')
            
            if not head_ids or not func_ids:
                messages.warning(request, 'No heads or functions selected')
                return redirect(request.get_full_path())
            
            for head_id in head_ids:
                head = GlobalHead.objects.get(pk=head_id)
                head.applicable_functions.remove(*func_ids)
            
            messages.success(
                request, 
                f'Removed {len(head_ids)} head(s) from {len(func_ids)} function(s)'
            )
        
        return redirect(request.get_full_path())


class BudgetHeadDepartmentAssignmentView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """
    LEGACY DATA CLEANUP ONLY
    
    Assign departments to BudgetHeads that were created before department field was added.
    This is for migration/cleanup purposes only.
    """
    model = BudgetHead
    template_name = 'finance/budget_head_department_assignment.html'
    context_object_name = 'budget_heads'
    paginate_by = 100
    
    def get_queryset(self):
        queryset = BudgetHead.objects.select_related(
            'global_head', 'function', 'fund', 'department'
        ).order_by('global_head__code')
        
        # Filter options
        unmapped_only = self.request.GET.get('unmapped_only') == '1'
        function_id = self.request.GET.get('function')
        account_type = self.request.GET.get('account_type')
        dept_id = self.request.GET.get('department')
        
        if unmapped_only:
            queryset = queryset.filter(department__isnull=True)
        
        if function_id:
            queryset = queryset.filter(function_id=function_id)
        
        if account_type:
            queryset = queryset.filter(global_head__account_type=account_type)
            
        if dept_id:
            queryset = queryset.filter(department_id=dept_id)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['functions'] = FunctionCode.objects.filter(is_active=True).order_by('code')
        context['account_types'] = AccountType.choices
        
        context['unmapped_count'] = BudgetHead.objects.filter(department__isnull=True).count()
        context['total_count'] = BudgetHead.objects.count()
        context['mapped_count'] = context['total_count'] - context['unmapped_count']
        
        # Filter state
        context['unmapped_only'] = self.request.GET.get('unmapped_only') == '1'
        context['selected_function'] = self.request.GET.get('function', '')
        context['selected_account_type'] = self.request.GET.get('account_type', '')
        context['selected_department'] = self.request.GET.get('department', '')
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle department assignment."""
        action = request.POST.get('action')
        
        if action == 'assign_department':
            budget_head_ids = request.POST.getlist('selected_budget_heads')
            department_id = request.POST.get('department')
            
            if not budget_head_ids:
                messages.warning(request, 'No budget heads selected')
                return redirect(request.get_full_path())
            
            if not department_id:
                messages.warning(request, 'No department selected')
                return redirect(request.get_full_path())
            
            # Assign department
            BudgetHead.objects.filter(pk__in=budget_head_ids).update(department_id=department_id)
            
            dept = Department.objects.get(pk=department_id)
            messages.success(
                request, 
                f'Assigned {len(budget_head_ids)} budget head(s) to {dept.name}'
            )
        
        return redirect(request.get_full_path())


class DepartmentFunctionConfigurationMatrixView(LoginRequiredMixin, SuperAdminRequiredMixin, TemplateView):
    """
    NEW SIMPLIFIED APPROACH: Department-Function Configuration Matrix
    
    Displays a matrix showing all Department-Function combinations and their
    configuration status. Allows easy management of allowed global heads for
    each combination.
    
    This replaces the confusing dual-level access control system.
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
                        'allowed_global_heads'
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
            head_count=Count('allowed_global_heads')
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
    Configure allowed global heads for a specific Department-Function combination.
    
    This is the detailed configuration view where admin selects which global heads
    are valid for a specific dept-func pair.
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
        
        global_heads = GlobalHead.objects.select_related(
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
        global_heads = global_heads.filter(
            Q(applicable_functions__isnull=True) |
            Q(applicable_functions=function)
        ).distinct()
        
        # Get currently selected heads
        selected_head_ids = set(config.allowed_global_heads.values_list('id', flat=True))
        
        # Annotate each head with selection status
        heads_data = []
        for head in global_heads:
            heads_data.append({
                'head': head,
                'is_selected': head.id in selected_head_ids,
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
            config.allowed_global_heads.set(selected_head_ids)
            
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
