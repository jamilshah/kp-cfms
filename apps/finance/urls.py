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
    # CoA Management Hub
    CoAManagementHubView,
    
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
    load_global_heads,
    load_budget_heads_options,
    load_existing_subheads,
    budget_head_search_api,
    smart_budget_head_search_api,
    toggle_budget_head_favorite,
    record_budget_head_usage,
    
    # CSV Import/Export
    SubHeadCSVTemplateView,
    SubHeadCSVImportView,
    GlobalHeadCSVTemplateView,
    GlobalHeadCSVImportView,
)

from apps.finance.views_coa_configuration import (
    DepartmentFunctionConfigurationMatrixView,
    DepartmentFunctionConfigurationDetailView,
)

from apps.finance.views_coa_mapping import (
    BudgetHeadDepartmentAssignmentView,
)

from apps.finance.views_create_budget_heads_ui import (
    CreateBudgetHeadsFromConfigUIView,
)

from apps.finance.views_subhead_api import (
    NAMHeadSubHeadsAPIView,
)

from apps.finance.views_subhead import (
    SubHeadListView,
    SubHeadCreateView,
    SubHeadUpdateView,
)

app_name = 'finance'

urlpatterns = [
    # CoA Management Hub
    path('coa-hub/', CoAManagementHubView.as_view(), name='coa_hub'),
    
    # Master Data
    path('funds/', FundListView.as_view(), name='fund_list'),
    path('budget-heads/', BudgetHeadListView.as_view(), name='budget_head_list'),
    
    # CoA Configuration (Super Admin - Provincial Level)
    # PRIMARY ACCESS CONTROL INTERFACE
    path('dept-func-config-matrix/', DepartmentFunctionConfigurationMatrixView.as_view(), name='dept_func_config_matrix'),
    path('dept-func-config/<int:dept_id>/<int:func_id>/', DepartmentFunctionConfigurationDetailView.as_view(), name='dept_func_config_detail'),
    path('create-budget-heads-from-config-ui/', CreateBudgetHeadsFromConfigUIView.as_view(), name='create_budget_heads_from_config_ui'),
    
    # Sub-Head Management (Level 5 Master Data)
    path('subheads/', SubHeadListView.as_view(), name='subhead_list'),
    path('subheads/create/', SubHeadCreateView.as_view(), name='subhead_create'),
    path('subheads/<int:pk>/edit/', SubHeadUpdateView.as_view(), name='subhead_edit'),
    
    # NAM Head API endpoints
    path('nam-head/<int:nam_head_id>/subheads/', NAMHeadSubHeadsAPIView.as_view(), name='nam_head_subheads_api'),
    
    # CSV Import/Export for Sub-Heads
    path('subheads/csv-template/', SubHeadCSVTemplateView.as_view(), name='subhead_csv_template'),
    path('subheads/csv-import/', SubHeadCSVImportView.as_view(), name='subhead_csv_import'),
    
    # CSV Import/Export for Global Heads (Master CoA)
    path('global-heads/csv-template/', GlobalHeadCSVTemplateView.as_view(), name='global_head_csv_template'),
    path('global-heads/csv-import/', GlobalHeadCSVImportView.as_view(), name='global_head_csv_import'),
    
    # DEPRECATED: Department assignment is now automatic via DepartmentFunctionConfiguration
    # path('budget-head-departments/', BudgetHeadDepartmentAssignmentView.as_view(), name='budget_head_departments'),
    
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
    
    # AJAX/HTMX endpoints
    path('ajax/load-functions/', load_functions, name='load_functions'),
    path('ajax/load-global-heads/', load_global_heads, name='load_global_heads'),
    path('ajax/load-budget-heads-options/', load_budget_heads_options, name='load_budget_heads_options'),
    path('ajax/existing-subheads/', load_existing_subheads, name='load_existing_subheads'),
    path('ajax/budget-head-search/', budget_head_search_api, name='budget_head_search_api'),
    path('ajax/smart-budget-head-search/', smart_budget_head_search_api, name='smart_budget_head_search_api'),
    path('ajax/toggle-favorite/', toggle_budget_head_favorite, name='toggle_budget_head_favorite'),
    path('ajax/record-usage/', record_budget_head_usage, name='record_budget_head_usage'),
]