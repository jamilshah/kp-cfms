from django.urls import path
from . import views

app_name = 'reporting'

urlpatterns = [
    # Dashboard
    path('', views.ReportDashboardView.as_view(), name='dashboard'),
    
    # Cash Book Report
    path(
        'cash-book/<int:bank_account_id>/<int:year>/<int:month>/',
        views.CashBookReportView.as_view(),
        name='cash_book_report'
    ),
    
    # BRS Report
    path(
        'brs/<int:statement_id>/',
        views.BRSReportView.as_view(),
        name='brs_report'
    ),
    
    # Monthly Summary
    path(
        'monthly-summary/',
        views.MonthlySummaryView.as_view(),
        name='monthly_summary'
    ),
    path(
        'monthly-summary/<int:year>/<int:month>/',
        views.MonthlySummaryView.as_view(),
        name='monthly_summary_detail'
    ),
]
