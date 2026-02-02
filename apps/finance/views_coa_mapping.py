"""
Views for CoA Department Mapping Management
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, FormView
from django.utils.translation import gettext_lazy as _

from apps.finance.models import GlobalHead, AccountType
from apps.budgeting.models import Department
from apps.users.permissions import SuperAdminRequiredMixin


class CoADepartmentMappingView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """
    View for managing GlobalHead department mappings.
    Allows Super Admin to mark heads as Universal or Department-specific.
    """
    model = GlobalHead
    template_name = 'finance/coa_department_mapping.html'
    context_object_name = 'global_heads'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = GlobalHead.objects.select_related('minor', 'minor__major').prefetch_related(
            'applicable_departments'
        ).annotate(
            dept_count=Count('applicable_departments')
        ).order_by('code')
        
        # Filter by account type
        account_type = self.request.GET.get('account_type')
        if account_type and account_type in dict(AccountType.choices):
            queryset = queryset.filter(account_type=account_type)
        
        # Filter by scope
        scope = self.request.GET.get('scope')
        if scope in ['UNIVERSAL', 'DEPARTMENTAL']:
            queryset = queryset.filter(scope=scope)
        
        # Filter by department
        dept_id = self.request.GET.get('department')
        if dept_id:
            queryset = queryset.filter(
                Q(scope='UNIVERSAL') | Q(applicable_departments__id=dept_id)
            )
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['account_types'] = AccountType.choices
        context['selected_account_type'] = self.request.GET.get('account_type', '')
        context['selected_scope'] = self.request.GET.get('scope', '')
        context['selected_department'] = self.request.GET.get('department', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        # Build query string for pagination (excluding page parameter)
        query_params = []
        for key, value in self.request.GET.items():
            if key != 'page' and value:
                query_params.append(f'{key}={value}')
        context['query_string'] = '&' + '&'.join(query_params) if query_params else ''
        
        # Statistics
        context['total_heads'] = GlobalHead.objects.count()
        context['universal_count'] = GlobalHead.objects.filter(scope='UNIVERSAL').count()
        context['departmental_count'] = GlobalHead.objects.filter(scope='DEPARTMENTAL').count()
        context['unmapped_count'] = GlobalHead.objects.filter(
            scope='DEPARTMENTAL', applicable_departments=None
        ).count()
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle bulk update of GlobalHead mappings."""
        action = request.POST.get('action')
        
        # Handle bulk actions first (they don't have head_id)
        if action == 'bulk_mark_universal':
            head_ids = request.POST.getlist('selected_heads')
            if head_ids:
                GlobalHead.objects.filter(pk__in=head_ids).update(scope='UNIVERSAL')
                for head_id in head_ids:
                    GlobalHead.objects.get(pk=head_id).applicable_departments.clear()
                messages.success(request, f'Marked {len(head_ids)} heads as Universal')
            else:
                messages.warning(request, 'No heads selected')
            return redirect(request.get_full_path())
        
        elif action == 'bulk_mark_departmental':
            head_ids = request.POST.getlist('selected_heads')
            if head_ids:
                GlobalHead.objects.filter(pk__in=head_ids).update(scope='DEPARTMENTAL')
                messages.success(request, f'Marked {len(head_ids)} heads as Departmental')
            else:
                messages.warning(request, 'No heads selected')
            return redirect(request.get_full_path())
        
        # Handle individual head actions
        head_id = request.POST.get('head_id')
        
        if not head_id:
            messages.error(request, 'Invalid request: Missing head_id')
            return redirect('finance:coa_department_mapping')
        
        global_head = get_object_or_404(GlobalHead, pk=head_id)
        
        if action == 'update_scope':
            scope = request.POST.get('scope')
            if scope in ['UNIVERSAL', 'DEPARTMENTAL']:
                global_head.scope = scope
                global_head.save()
                
                if scope == 'UNIVERSAL':
                    # Clear department assignments for universal heads
                    global_head.applicable_departments.clear()
                    messages.success(request, f'{global_head.code} marked as Universal')
                else:
                    # For departmental scope, also update departments if provided
                    dept_ids = request.POST.getlist('departments')
                    if dept_ids:
                        global_head.applicable_departments.set(dept_ids)
                        messages.success(request, f'{global_head.code} marked as Departmental with {len(dept_ids)} departments')
                    else:
                        messages.success(request, f'{global_head.code} marked as Departmental (no departments assigned yet)')
            else:
                messages.error(request, 'Invalid scope value')
        
        elif action == 'update_departments':
            dept_ids = request.POST.getlist('departments')
            global_head.applicable_departments.set(dept_ids)
            dept_count = len(dept_ids)
            messages.success(request, f'Updated {global_head.code}: {dept_count} departments assigned')
        
        return redirect(request.get_full_path())
