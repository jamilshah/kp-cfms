from django.urls import path

from apps.reporting.views import (
    ReportDashboardView,
    CashBookReportView,
    BRSReportView,
    MonthlySummaryView,
)
from apps.reporting.views_ledger import GeneralLedgerView, TrialBalanceView, AccountStatementView, PendingLiabilitiesView
from apps.reporting.views_api import BudgetHeadAutocompleteView

app_name = 'reporting'

urlpatterns = [
    # Dashboard
    path('', ReportDashboardView.as_view(), name='dashboard'),
    
    # Cash Book Report
    path(
        'cash-book/<int:bank_account_id>/<int:year>/<int:month>/',
        CashBookReportView.as_view(),
        name='cash_book_report'
    ),
    
    # BRS Report
    path(
        'brs/<int:statement_id>/',
        BRSReportView.as_view(),
        name='brs_report'
    ),
    
    # Monthly Summary
    path(
        'monthly-summary/',
        MonthlySummaryView.as_view(),
        name='monthly_summary'
    ),
    path(
        'monthly-summary/<int:year>/<int:month>/',
        MonthlySummaryView.as_view(),
        name='monthly_summary_detail'
    ),
    
    # Ledger Reports
    path('general-ledger/', GeneralLedgerView.as_view(), name='general_ledger'),
    path('trial-balance/', TrialBalanceView.as_view(), name='trial_balance'),
    path('account-statement/', AccountStatementView.as_view(), name='account_statement'),
    path('pending-liabilities/', PendingLiabilitiesView.as_view(), name='pending_liabilities'),
    
    # API Endpoints
    path('api/budget-heads/autocomplete/', BudgetHeadAutocompleteView.as_view(), name='budget_head_autocomplete'),
]
