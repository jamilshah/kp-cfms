"""
Views for salary budget distribution and monitoring
"""
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, Q, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    TemplateView, FormView, DetailView, ListView
)

from apps.budgeting.models import Department, FiscalYear
from apps.finance.models import GlobalHead, Fund
from apps.budgeting.models_salary_budget import DepartmentSalaryBudget, SalaryBillConsumption
from apps.budgeting.models_employee import BudgetEmployee
from apps.budgeting.forms_salary_budget import (
    SalaryBudgetDistributionForm,
    BudgetAllocationAdjustmentForm,
    BudgetAlertSettingsForm
)
from apps.budgeting.services_salary_budget import (
    SalaryBudgetDistributor,
    SalaryBudgetReporter,
    SalaryBillValidator
)
from apps.users.permissions import FinanceOfficerRequiredMixin, AdminRequiredMixin


class SalaryBudgetDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard for salary budget management
    Shows overview of all departments and their budget status
    """
    template_name = 'budgeting/salary_budget/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        current_fy = FiscalYear.get_current_operating_year()
        if not current_fy:
            messages.error(self.request, "No active fiscal year found")
            return context
        
        context['fiscal_year'] = current_fy
        
        # Get all department budgets
        dept_budgets = DepartmentSalaryBudget.objects.filter(
            fiscal_year=current_fy
        ).select_related(
            'department', 'global_head', 'fund'
        ).order_by('department__name', 'global_head__code')
        
        # Group by department
        dept_summary = {}
        total_allocated = Decimal('0.00')
        total_consumed = Decimal('0.00')
        
        for budget in dept_budgets:
            dept_name = budget.department.name
            if dept_name not in dept_summary:
                dept_summary[dept_name] = {
                    'department': budget.department,
                    'accounts': [],
                    'total_allocated': Decimal('0.00'),
                    'total_consumed': Decimal('0.00'),
                    'total_available': Decimal('0.00')
                }
            
            dept_summary[dept_name]['accounts'].append(budget)
            dept_summary[dept_name]['total_allocated'] += budget.allocated_amount
            dept_summary[dept_name]['total_consumed'] += budget.consumed_amount
            dept_summary[dept_name]['total_available'] += budget.available_amount
            
            total_allocated += budget.allocated_amount
            total_consumed += budget.consumed_amount
        
        context['department_summary'] = dept_summary
        context['total_allocated'] = total_allocated
        context['total_consumed'] = total_consumed
        context['total_available'] = total_allocated - total_consumed
        context['overall_utilization'] = (
            (total_consumed / total_allocated * 100) if total_allocated > 0 else 0
        )
        
        # Get alerts (departments over 80%)
        alerts = SalaryBudgetReporter.get_budget_alerts(current_fy, threshold_percentage=80)
        context['alerts'] = alerts
        context['critical_count'] = len([a for a in alerts if a['utilization'] >= 90])
        context['warning_count'] = len([a for a in alerts if 80 <= a['utilization'] < 90])
        
        return context


class SalaryBudgetDistributionView(FinanceOfficerRequiredMixin, FormView):
    """
    View for initial budget distribution among departments
    """
    template_name = 'budgeting/salary_budget/distribution.html'
    form_class = SalaryBudgetDistributionForm
    success_url = reverse_lazy('budgeting:salary_budget_dashboard')
    
    def form_valid(self, form):
        fiscal_year = form.cleaned_data['fiscal_year']
        fund = form.cleaned_data['fund']
        account_code = form.cleaned_data['account_code']
        total_amount = form.cleaned_data['total_amount']
        
        try:
            with transaction.atomic():
                # Calculate distribution
                allocations = SalaryBudgetDistributor.distribute_budget(
                    fiscal_year, fund, account_code, total_amount
                )
                
                # Create records
                created_budgets = SalaryBudgetDistributor.create_department_budgets(
                    fiscal_year, fund, account_code, total_amount
                )
                
                messages.success(
                    self.request,
                    f"Successfully distributed Rs. {total_amount:,.2f} for {account_code.code} "
                    f"among {len(created_budgets)} departments"
                )
                
        except Exception as e:
            messages.error(self.request, f"Distribution failed: {str(e)}")
            return self.form_invalid(form)
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get employee counts for preview
        current_fy = FiscalYear.get_current_operating_year()
        if current_fy:
            dept_counts = {}
            total_employees = 0

            for dept in Department.objects.filter(is_active=True):
                count = BudgetEmployee.objects.filter(
                    schedule__department=dept.name,
                    schedule__fiscal_year=current_fy,
                    is_vacant=False
                ).count()

                if count > 0:
                    dept_counts[dept.name] = count
                    total_employees += count

            context['employee_counts'] = dept_counts
            context['total_employees'] = total_employees
        
        return context


class DepartmentBudgetDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed view of a department's salary budget
    """
    model = Department
    template_name = 'budgeting/salary_budget/department_detail.html'
    context_object_name = 'department'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object
        
        current_fy = FiscalYear.get_current_operating_year()
        if not current_fy:
            return context
        
        context['fiscal_year'] = current_fy
        
        # Get all budgets for this department
        budgets = DepartmentSalaryBudget.objects.filter(
            department=department,
            fiscal_year=current_fy
        ).select_related('global_head', 'fund').order_by('global_head__code')
        
        context['budgets'] = budgets
        
        # Calculate totals
        context['total_allocated'] = sum(b.allocated_amount for b in budgets)
        context['total_consumed'] = sum(b.consumed_amount for b in budgets)
        context['total_available'] = sum(b.available_amount for b in budgets)
        
        # Get consumption history
        consumptions = SalaryBillConsumption.objects.filter(
            department_budget__department=department,
            department_budget__fiscal_year=current_fy
        ).select_related(
            'bill', 'department_budget__global_head'
        ).order_by('-created_at')[:20]
        
        context['recent_consumptions'] = consumptions
        
        # Get employee count
        context['employee_count'] = BudgetEmployee.objects.filter(
            schedule__department=department.name,
            schedule__fiscal_year=current_fy,
            is_vacant=False
        ).count()
        
        return context


class BudgetUtilizationChartView(LoginRequiredMixin, TemplateView):
    """
    HTMX endpoint for budget utilization chart data
    """
    
    def get(self, request, *args, **kwargs):
        current_fy = FiscalYear.get_current_operating_year()
        if not current_fy:
            return JsonResponse({'error': 'No active fiscal year'}, status=400)
        
        # Get data by department
        dept_budgets = DepartmentSalaryBudget.objects.filter(
            fiscal_year=current_fy
        ).values('department__name').annotate(
            allocated=Sum('allocated_amount'),
            consumed=Sum('consumed_amount')
        ).order_by('-allocated')
        
        data = {
            'labels': [d['department__name'] for d in dept_budgets],
            'allocated': [float(d['allocated']) for d in dept_budgets],
            'consumed': [float(d['consumed']) for d in dept_budgets],
        }
        
        return JsonResponse(data)


class BudgetAlertsWidgetView(LoginRequiredMixin, TemplateView):
    """
    HTMX widget showing budget alerts
    """
    template_name = 'budgeting/salary_budget/widgets/alerts.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        current_fy = FiscalYear.get_current_operating_year()
        if current_fy:
            threshold = int(self.request.GET.get('threshold', 80))

            alerts = SalaryBudgetReporter.get_budget_alerts(
                current_fy,
                threshold_percentage=threshold
            )

            context['alerts'] = alerts
            context['threshold'] = threshold
        else:
            context['alerts'] = []
        
        return context


class ValidateBillBudgetView(LoginRequiredMixin, TemplateView):
    """
    HTMX endpoint to validate bill against department budgets
    Returns validation result and error messages
    """
    template_name = 'budgeting/salary_budget/widgets/bill_validation.html'
    
    def post(self, request, *args, **kwargs):
        bill_id = request.POST.get('bill_id')
        
        if not bill_id:
            return JsonResponse({'error': 'Bill ID required'}, status=400)
        
        try:
            from apps.expenditure.models import Bill
            bill = Bill.objects.get(id=bill_id)
            
            # Validate
            is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
            
            context = {
                'bill': bill,
                'is_valid': is_valid,
                'errors': errors
            }
            
            return self.render_to_response(context)
            
        except Bill.DoesNotExist:
            return JsonResponse({'error': 'Bill not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class BudgetConsumptionHistoryView(LoginRequiredMixin, ListView):
    """
    View showing budget consumption history
    """
    model = SalaryBillConsumption
    template_name = 'budgeting/salary_budget/consumption_history.html'
    context_object_name = 'consumptions'
    paginate_by = 50
    
    def get_queryset(self):
        qs = SalaryBillConsumption.objects.select_related(
            'department_budget__department',
            'department_budget__global_head',
            'bill'
        ).order_by('-created_at')
        
        # Filter by department if provided
        dept_id = self.request.GET.get('department')
        if dept_id:
            qs = qs.filter(department_budget__department_id=dept_id)
        
        # Filter by account code if provided
        account = self.request.GET.get('account')
        if account:
            qs = qs.filter(department_budget__global_head__code=account)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True)
        context['accounts'] = GlobalHead.objects.filter(
            code__startswith='A'
        ).order_by('code')
        return context


class ExportBudgetStatusView(LoginRequiredMixin, TemplateView):
    """
    Export budget status as CSV/Excel
    """
    
    def get(self, request, *args, **kwargs):
        import csv
        from django.http import HttpResponse
        
        try:
            current_fy = FiscalYear.get_current_operating_year()
            if not current_fy:
                raise FiscalYear.DoesNotExist
        except FiscalYear.DoesNotExist:
            messages.error(request, "No active fiscal year")
            return redirect('budgeting:salary_budget_dashboard')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="budget_status_{current_fy.year}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Department', 'Account Code', 'Account Title', 'Fund',
            'Allocated Amount', 'Consumed Amount', 'Available Amount', 'Utilization %'
        ])
        
        budgets = DepartmentSalaryBudget.objects.filter(
            fiscal_year=current_fy
        ).select_related(
            'department', 'global_head', 'fund'
        ).order_by('department__name', 'global_head__code')
        
        for budget in budgets:
            writer.writerow([
                budget.department.name,
                budget.global_head.code,
                budget.global_head.name,
                budget.fund.code,
                f"{budget.allocated_amount:.2f}",
                f"{budget.consumed_amount:.2f}",
                f"{budget.available_amount:.2f}",
                f"{budget.utilization_percentage:.2f}"
            ])
        
        return response
