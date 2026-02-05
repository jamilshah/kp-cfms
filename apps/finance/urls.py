"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: URL configuration for the finance module including
             Bank Reconciliation and Financial Reporting.
-------------------------------------------------------------------------
"""
from django.urls import path

from apps.finance.views import (
    # Master Data
    FundListView,
    BudgetHeadListView,
    
    # Bank Statement Management
    BankStatementListView,
    BankStatementCreateView,
    BankStatementDetailView,
    BankStatementUploadCSVView,
    BankStatementAddLineView,
    
    # Reconciliation Workbench
    ReconciliationWorkbenchView,
    AutoReconcileView,
    ManualMatchView,
    UnmatchLineView,
    LockStatementView,
    BRSSummaryView,
    
    # Manual Journal Vouchers (Phase 10)
    VoucherListView,
    VoucherCreateView,
    VoucherDetailView,
    PostVoucherView,
    UnpostVoucherView,
    
    # AJAX Views
    load_functions,
    load_budget_heads_options,
    budget_head_search_api,
)

from apps.finance.views_coa_mapping import (
    CoADepartmentMappingView,
)

app_name = 'finance'

urlpatterns = [
    # Master Data
    path('funds/', FundListView.as_view(), name='fund_list'),
    path('budget-heads/', BudgetHeadListView.as_view(), name='budget_head_list'),
    
    # CoA Department Mapping (Super Admin)
    path('coa-department-mapping/', CoADepartmentMappingView.as_view(), name='coa_department_mapping'),
    
    # Bank Statement Management
    path('statements/', BankStatementListView.as_view(), name='statement_list'),
    path('statements/create/', BankStatementCreateView.as_view(), name='statement_create'),
    path('statements/<int:pk>/', BankStatementDetailView.as_view(), name='statement_detail'),
    path('statements/<int:pk>/upload-csv/', BankStatementUploadCSVView.as_view(), name='statement_upload_csv'),
    path('statements/<int:pk>/add-line/', BankStatementAddLineView.as_view(), name='statement_add_line'),
    
    # Reconciliation Workbench
    path('statements/<int:pk>/reconcile/', ReconciliationWorkbenchView.as_view(), name='reconciliation_workbench'),
    path('statements/<int:pk>/auto-reconcile/', AutoReconcileView.as_view(), name='auto_reconcile'),
    path('statements/<int:pk>/manual-match/', ManualMatchView.as_view(), name='manual_match'),
    path('statements/<int:pk>/lines/<int:line_pk>/unmatch/', UnmatchLineView.as_view(), name='unmatch_line'),
    path('statements/<int:pk>/lock/', LockStatementView.as_view(), name='lock_statement'),
    path('statements/<int:pk>/brs/', BRSSummaryView.as_view(), name='brs_summary'),
    
    # Manual Journal Vouchers (Phase 10: General Journal)
    path('vouchers/', VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/create/', VoucherCreateView.as_view(), name='voucher_create'),
    path('vouchers/<int:pk>/', VoucherDetailView.as_view(), name='voucher_detail'),
    path('vouchers/<int:pk>/post/', PostVoucherView.as_view(), name='voucher_post'),
    path('vouchers/<int:pk>/unpost/', UnpostVoucherView.as_view(), name='voucher_unpost'),
    
    # AJAX
    path('ajax/load-functions/', load_functions, name='load_functions'),
    path('ajax/load-budget-heads-options/', load_budget_heads_options, name='load_budget_heads_options'),
    path('ajax/budget-head-search/', budget_head_search_api, name='budget_head_search_api'),
]