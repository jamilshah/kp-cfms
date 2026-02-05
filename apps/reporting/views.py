"""
Reporting Views
"""

from datetime import date
from calendar import month_name

from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from apps.core.mixins import TenantAwareMixin
from apps.core.models import BankAccount
from apps.budgeting.models import FiscalYear
from apps.finance.models import BankStatement

from .services import generate_cash_book_pdf, generate_brs_pdf, get_monthly_summary


class ReportDashboardView(LoginRequiredMixin, TenantAwareMixin, TemplateView):
    """Dashboard for all available reports."""
    template_name = 'reporting/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bank_accounts'] = BankAccount.objects.filter(
            organization=self.request.user.organization,
            is_active=True
        )
        context['fiscal_years'] = FiscalYear.objects.all().order_by('-start_date')
        
        # Current month info
        today = date.today()
        context['current_month'] = today.month
        context['current_year'] = today.year
        context['months'] = [(i, month_name[i]) for i in range(1, 13)]
        
        return context


class CashBookReportView(LoginRequiredMixin, TenantAwareMixin, View):
    """Generate Cash Book PDF for a specific month and bank account."""
    
    def get(self, request, bank_account_id, year, month):
        organization = request.user.organization
        
        # Validate inputs
        if month < 1 or month > 12:
            return HttpResponse("Invalid month", status=400)
        
        bank_account = get_object_or_404(
            BankAccount, 
            pk=bank_account_id, 
            organization=organization
        )
        
        return generate_cash_book_pdf(
            month=month,
            year=year,
            bank_account_id=bank_account_id,
            organization=organization
        )


class BRSReportView(LoginRequiredMixin, TenantAwareMixin, View):
    """Generate BRS PDF for a specific statement."""
    
    def get(self, request, statement_id):
        organization = request.user.organization
        
        statement = get_object_or_404(
            BankStatement,
            pk=statement_id,
            bank_account__organization=organization
        )
        
        return generate_brs_pdf(
            statement_id=statement_id,
            organization=organization
        )


class MonthlySummaryView(LoginRequiredMixin, TenantAwareMixin, TemplateView):
    """View monthly summary across all bank accounts."""
    template_name = 'reporting/monthly_summary.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        year = int(self.kwargs.get('year', date.today().year))
        month = int(self.kwargs.get('month', date.today().month))
        
        summary = get_monthly_summary(
            month=month,
            year=year,
            organization=self.request.user.organization
        )
        
        context.update(summary)
        context['month_name'] = month_name[month]
        context['months'] = [(i, month_name[i]) for i in range(1, 13)]
        
        return context
