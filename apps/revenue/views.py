"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Views for the Revenue module including Payer, Demand,
             and Collection management with workflow support.
-------------------------------------------------------------------------
"""
from typing import Any, Dict
from decimal import Decimal
from django.views.generic import (
    ListView, CreateView, DetailView, UpdateView, TemplateView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.users.permissions import MakerRequiredMixin, CashierRequiredMixin, CheckerRequiredMixin
from apps.revenue.models import (
    Payer, RevenueDemand, RevenueCollection, 
    DemandStatus, CollectionStatus
)
from apps.revenue.forms import (
    PayerForm, DemandForm, CollectionForm,
    DemandPostForm, CollectionPostForm, DemandCancelForm
)
from apps.budgeting.models import FiscalYear, Department
from apps.finance.models import BudgetHead, AccountType, FunctionCode
from apps.core.exceptions import WorkflowTransitionException


class RevenueDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard view for the revenue module.
    
    Shows summary statistics for demands and collections.
    """
    template_name = 'revenue/dashboard.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        # Get current operating fiscal year (based on today's date)
        active_fy = FiscalYear.get_current_operating_year(org) if org else None
        
        if org and active_fy:
            demands_qs = RevenueDemand.objects.filter(
                organization=org,
                fiscal_year=active_fy
            )
            
            collections_qs = RevenueCollection.objects.filter(
                organization=org,
                demand__fiscal_year=active_fy
            )
            
            # Demand statistics
            total_demands = demands_qs.exclude(status=DemandStatus.CANCELLED).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            total_collections = collections_qs.filter(
                status=CollectionStatus.POSTED
            ).aggregate(
                total=Sum('amount_received')
            )['total'] or Decimal('0.00')
            
            context.update({
                'active_fiscal_year': active_fy,
                'total_demands': total_demands,
                'total_collections': total_collections,
                'outstanding_balance': total_demands - total_collections,
                'demand_count': demands_qs.exclude(status=DemandStatus.CANCELLED).count(),
                'draft_demands': demands_qs.filter(status=DemandStatus.DRAFT).count(),
                'posted_demands': demands_qs.filter(status=DemandStatus.POSTED).count(),
                'partial_demands': demands_qs.filter(status=DemandStatus.PARTIAL).count(),
                'paid_demands': demands_qs.filter(status=DemandStatus.PAID).count(),
                'collection_count': collections_qs.filter(status=CollectionStatus.POSTED).count(),
                'pending_collections': collections_qs.filter(status=CollectionStatus.DRAFT),
                'recent_demands': demands_qs.order_by('-created_at')[:5],
                'recent_collections': collections_qs.filter(
                    status=CollectionStatus.POSTED
                ).order_by('-receipt_date')[:5],
            })
        
        return context


# ============================================================================
# Payer Views
# ============================================================================

class PayerListView(LoginRequiredMixin, ListView):
    """List view for payers."""
    
    model = Payer
    template_name = 'revenue/payer_list.html'
    context_object_name = 'payers'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            queryset = Payer.objects.filter(organization=org).order_by('name')
            
            # Search by name or CNIC
            search = self.request.GET.get('search', '')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) | Q(cnic_ntn__icontains=search)
                )
            
            return queryset
        return Payer.objects.none()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class PayerCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """Create view for payers.
    
    Requires Dealing Assistant (Maker) role.
    """
    
    model = Payer
    form_class = PayerForm
    template_name = 'revenue/payer_form.html'
    success_url = reverse_lazy('revenue:payer_list')
    
    def form_valid(self, form):
        user = self.request.user
        org = getattr(user, 'organization', None)
        form.instance.organization = org
        form.instance.created_by = user
        messages.success(self.request, _('Payer created successfully.'))
        return super().form_valid(form)


class PayerUpdateView(LoginRequiredMixin, UpdateView):
    """Update view for payers."""
    
    model = Payer
    form_class = PayerForm
    template_name = 'revenue/payer_form.html'
    success_url = reverse_lazy('revenue:payer_list')
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            return Payer.objects.filter(organization=org)
        return Payer.objects.none()
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, _('Payer updated successfully.'))
        return super().form_valid(form)


class PayerDetailView(LoginRequiredMixin, DetailView):
    """Detail view for payers with demand history."""
    
    model = Payer
    template_name = 'revenue/payer_detail.html'
    context_object_name = 'payer'
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            return Payer.objects.filter(organization=org)
        return Payer.objects.none()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['demands'] = self.object.demands.order_by('-issue_date')[:10]
        context['total_demands'] = self.object.get_total_demands()
        context['total_collected'] = self.object.get_total_collections()
        context['outstanding'] = self.object.get_outstanding_balance()
        return context


# ============================================================================
# Demand Views
# ============================================================================

class DemandListView(LoginRequiredMixin, ListView):
    """List view for revenue demands."""
    
    model = RevenueDemand
    template_name = 'revenue/demand_list.html'
    context_object_name = 'demands'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if not org:
            return RevenueDemand.objects.none()
        
        queryset = RevenueDemand.objects.filter(
            organization=org
        ).select_related(
            'payer', 'budget_head', 'fiscal_year'
        ).order_by('-issue_date', '-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status and status in dict(DemandStatus.choices):
            queryset = queryset.filter(status=status)
        
        # Filter by fiscal year
        fy_id = self.request.GET.get('fiscal_year')
        if fy_id:
            queryset = queryset.filter(fiscal_year_id=fy_id)
        
        # Search by challan no or payer name
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(challan_no__icontains=search) | Q(payer__name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        context['status_choices'] = DemandStatus.choices
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        if org:
            context['fiscal_years'] = FiscalYear.objects.filter(
                organization=org
            ).order_by('-start_date')
        
        return context


class DemandCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """Create view for revenue demands.
    
    Requires Dealing Assistant (Maker) role.
    """
    
    model = RevenueDemand
    form_class = DemandForm
    template_name = 'revenue/demand_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Check for current operating fiscal year before allowing access."""
        user = request.user
        org = getattr(user, 'organization', None)
        
        if org:
            active_fy = FiscalYear.get_current_operating_year(org)
            if not active_fy:
                messages.error(
                    request, 
                    _('No active fiscal year found for the current period. '
                      'Please contact your administrator to set up a fiscal year.')
                )
                return redirect('revenue:dashboard')
            
            if active_fy.is_locked:
                messages.error(
                    request,
                    _('The current fiscal year is locked. No new demands can be created.')
                )
                return redirect('revenue:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        user = self.request.user
        kwargs['organization'] = getattr(user, 'organization', None)
        return kwargs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            context['current_fiscal_year'] = FiscalYear.get_current_operating_year(org)
        return context
    
    def form_valid(self, form):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        form.instance.organization = org
        form.instance.created_by = user
        
        # Set fiscal year from form's cached value
        if form._current_fiscal_year:
            form.instance.fiscal_year = form._current_fiscal_year
        
        # Generate challan number
        fy = form.instance.fiscal_year
        challan_count = RevenueDemand.objects.filter(
            organization=org,
            fiscal_year=fy
        ).count()
        form.instance.challan_no = f"CH-{fy.year_name}-{challan_count + 1:04d}"
        
        messages.success(self.request, _('Demand created successfully.'))
        return super().form_valid(form)
    
    def get_success_url(self) -> str:
        return reverse('revenue:demand_detail', kwargs={'pk': self.object.pk})


class DemandDetailView(LoginRequiredMixin, DetailView):
    """Detail view for demands with collection history."""
    
    model = RevenueDemand
    template_name = 'revenue/demand_detail.html'
    context_object_name = 'demand'
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            return RevenueDemand.objects.filter(
                organization=org
            ).select_related(
                'payer', 'budget_head', 'fiscal_year', 
                'accrual_voucher', 'posted_by'
            )
        return RevenueDemand.objects.none()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['collections'] = self.object.collections.order_by('-receipt_date')
        context['total_collected'] = self.object.get_total_collected()
        context['outstanding'] = self.object.get_outstanding_balance()
        context['can_post'] = self.object.status == DemandStatus.DRAFT
        context['can_collect'] = self.object.status in [
            DemandStatus.POSTED, DemandStatus.PARTIAL
        ]
        context['can_cancel'] = self.object.status in [
            DemandStatus.DRAFT, DemandStatus.POSTED
        ] and not self.object.collections.filter(
            status=CollectionStatus.POSTED
        ).exists()
        return context


class DemandPostView(LoginRequiredMixin, View):
    """View for posting a demand to GL."""
    
    def post(self, request, pk):
        user = request.user
        org = getattr(user, 'organization', None)
        
        demand = get_object_or_404(
            RevenueDemand.objects.filter(organization=org),
            pk=pk
        )
        
        try:
            demand.post(user)
            messages.success(request, _('Demand posted successfully.'))
        except WorkflowTransitionException as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, _('Error posting demand: ') + str(e))
        
        return redirect('revenue:demand_detail', pk=pk)


class DemandCancelView(LoginRequiredMixin, View):
    """View for cancelling a demand."""
    
    def post(self, request, pk):
        user = request.user
        org = getattr(user, 'organization', None)
        
        demand = get_object_or_404(
            RevenueDemand.objects.filter(organization=org),
            pk=pk
        )
        
        reason = request.POST.get('reason', '')
        if not reason:
            messages.error(request, _('Cancellation reason is required.'))
            return redirect('revenue:demand_detail', pk=pk)
        
        try:
            demand.cancel(user, reason)
            messages.success(request, _('Demand cancelled successfully.'))
        except WorkflowTransitionException as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, _('Error cancelling demand: ') + str(e))
        
        return redirect('revenue:demand_detail', pk=pk)


# ============================================================================
# Collection Views
# ============================================================================

class CollectionListView(LoginRequiredMixin, ListView):
    """List view for revenue collections."""
    
    model = RevenueCollection
    template_name = 'revenue/collection_list.html'
    context_object_name = 'collections'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if not org:
            return RevenueCollection.objects.none()
        
        queryset = RevenueCollection.objects.filter(
            organization=org
        ).select_related(
            'demand', 'demand__payer', 'bank_account'
        ).order_by('-receipt_date', '-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status and status in dict(CollectionStatus.choices):
            queryset = queryset.filter(status=status)
        
        # Search by receipt no or payer name
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(receipt_no__icontains=search) | 
                Q(demand__payer__name__icontains=search) |
                Q(demand__challan_no__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['status_choices'] = CollectionStatus.choices
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class CollectionCreateView(LoginRequiredMixin, CashierRequiredMixin, CreateView):
    """Create view for revenue collections.
    
    Requires Cashier role to record cash/bank receipts.
    """
    
    model = RevenueCollection
    form_class = CollectionForm
    template_name = 'revenue/collection_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Check for current operating fiscal year."""
        user = request.user
        org = getattr(user, 'organization', None)
        
        if org:
            active_fy = FiscalYear.get_current_operating_year(org)
            if not active_fy:
                messages.error(
                    request, 
                    _('No active fiscal year found for the current period.')
                )
                return redirect('revenue:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        user = self.request.user
        kwargs['organization'] = getattr(user, 'organization', None)
        
        # Pre-select demand if provided in URL
        demand_id = self.request.GET.get('demand')
        if demand_id:
            try:
                demand = RevenueDemand.objects.get(pk=demand_id)
                kwargs['demand'] = demand
            except RevenueDemand.DoesNotExist:
                pass
        
        return kwargs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # If demand is pre-selected, add to context
        demand_id = self.request.GET.get('demand')
        if demand_id:
            try:
                demand = RevenueDemand.objects.get(pk=demand_id)
                context['selected_demand'] = demand
                context['outstanding_balance'] = demand.get_outstanding_balance()
            except RevenueDemand.DoesNotExist:
                pass
        
        return context
    
    def form_valid(self, form):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        form.instance.organization = org
        form.instance.created_by = user
        
        # Generate receipt number
        receipt_count = RevenueCollection.objects.filter(
            organization=org
        ).count()
        fy = form.cleaned_data['demand'].fiscal_year
        form.instance.receipt_no = f"REC-{fy.year_name}-{receipt_count + 1:04d}"
        
        messages.success(self.request, _('Collection recorded successfully.'))
        return super().form_valid(form)
    
    def get_success_url(self) -> str:
        return reverse('revenue:collection_detail', kwargs={'pk': self.object.pk})


class CollectionDetailView(LoginRequiredMixin, DetailView):
    """Detail view for collections."""
    
    model = RevenueCollection
    template_name = 'revenue/collection_detail.html'
    context_object_name = 'collection'
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            return RevenueCollection.objects.filter(
                organization=org
            ).select_related(
                'demand', 'demand__payer', 'bank_account',
                'receipt_voucher', 'posted_by'
            )
        return RevenueCollection.objects.none()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['can_post'] = self.object.status == CollectionStatus.DRAFT
        context['can_cancel'] = self.object.status in [
            CollectionStatus.DRAFT, CollectionStatus.POSTED
        ]
        return context


class CollectionPostView(LoginRequiredMixin, View):
    """View for posting a collection to GL."""
    
    def post(self, request, pk):
        user = request.user
        org = getattr(user, 'organization', None)
        
        collection = get_object_or_404(
            RevenueCollection.objects.filter(organization=org),
            pk=pk
        )
        
        try:
            collection.post(user)
            messages.success(request, _('Collection posted successfully.'))
        except WorkflowTransitionException as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, _('Error posting collection: ') + str(e))
        
        return redirect('revenue:collection_detail', pk=pk)


class CollectionCancelView(LoginRequiredMixin, View):
    """View for cancelling a collection."""
    
    def post(self, request, pk):
        user = request.user
        org = getattr(user, 'organization', None)
        
        collection = get_object_or_404(
            RevenueCollection.objects.filter(organization=org),
            pk=pk
        )
        
        try:
            collection.cancel(user)
            messages.success(request, _('Collection cancelled successfully.'))
        except WorkflowTransitionException as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, _('Error cancelling collection: ') + str(e))
        
        return redirect('revenue:collection_detail', pk=pk)


# ============================================================================
# API Views
# ============================================================================

class DemandOutstandingAPIView(LoginRequiredMixin, View):
    """API endpoint to get outstanding balance for a demand."""
    
    def get(self, request, pk):
        user = request.user
        org = getattr(user, 'organization', None)
        
        try:
            demand = RevenueDemand.objects.get(pk=pk, organization=org)
            return JsonResponse({
                'demand_amount': str(demand.amount),
                'total_collected': str(demand.get_total_collected()),
                'outstanding': str(demand.get_outstanding_balance()),
                'payer_name': demand.payer.name,
                'challan_no': demand.challan_no,
            })
        except RevenueDemand.DoesNotExist:
            return JsonResponse({'error': 'Demand not found'}, status=404)


def load_functions(request):
    """
    AJAX view to load functions filtered by department.
    """
    department_id = request.GET.get('department')
    functions = FunctionCode.objects.none()
    
    if department_id:
        try:
            dept = Department.objects.get(id=department_id)
            functions = dept.related_functions.all().order_by('code')
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
            
    # Reuse expenditure partial as it is generic and compatible
    return render(request, 'expenditure/partials/function_options.html', {'functions': functions})


def load_revenue_heads(request):
    """
    AJAX view to load revenue budget heads filtered by department and/or function.
    """
    department_id = request.GET.get('department')
    function_id = request.GET.get('function')
    
    # Base queryset
    budget_heads = BudgetHead.objects.filter(
        global_head__account_type=AccountType.REVENUE,
        posting_allowed=True,
        is_active=True
    ).order_by('global_head__name', 'global_head__code')
    
    if function_id:
        budget_heads = budget_heads.filter(function_id=function_id)
    elif department_id:
        try:
            dept = Department.objects.get(id=department_id)
            budget_heads = budget_heads.filter(function__in=dept.related_functions.all())
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
            
    # Reuse expenditure partial as it is generic (uses 'budget_heads' context)
    return render(request, 'expenditure/partials/budget_head_options.html', {'budget_heads': budget_heads})
