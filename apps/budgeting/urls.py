"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: URL configuration for the budgeting module.
-------------------------------------------------------------------------
"""
from django.urls import path

from apps.finance.views import (
    BudgetHeadListView, BudgetHeadCreateView, 
    BudgetHeadUpdateView, BudgetHeadDeleteView,
    FundListView, FundCreateView, FundUpdateView, FundDeleteView
)
from apps.core.views import (
    BankAccountListView, BankAccountCreateView, 
    BankAccountUpdateView, BankAccountDeleteView
)
from apps.budgeting.views import (
    BudgetingDashboardView,
    FiscalYearListView, FiscalYearCreateView, FiscalYearUpdateView, FiscalYearDetailView,
    BudgetAllocationListView, ReceiptEstimateCreateView, ExpenditureEstimateCreateView,
    ScheduleOfEstablishmentListView, ScheduleOfEstablishmentCreateView, NewPostProposalCreateView,
    BudgetApprovalView, QuarterlyReleaseView,
    SAEListView, SAEDetailView,
    SmartCalculatorView, EstablishmentDetailView, 
    EstablishmentApprovalView, EstablishmentBulkApprovalView,
    SetupDashboardView, DepartmentListView, DepartmentCreateView,
    DepartmentUpdateView, DepartmentDeleteView,
    DesignationListView, DesignationCreateView,
    DesignationUpdateView, DesignationDeleteView,
    SalaryStructureView,
    EmployeeListView, EmployeeCreateView, 
    EmployeeUpdateView, EmployeeDeleteView,
    # Phase 3
    PensionEstimateListView, PensionEstimateCreateView, PensionEstimateDetailView, PensionEstimateCalculateView,
    SupplementaryGrantListView, SupplementaryGrantCreateView, SupplementaryGrantDetailView, SupplementaryGrantApproveView,
    ReappropriationListView, ReappropriationCreateView, ReappropriationDetailView, ReappropriationApproveView,
    # Phase 4: Reporting
    PrintBudgetBookView
)
from apps.finance.views import (
    BudgetHeadListView, BudgetHeadCreateView, 
    BudgetHeadUpdateView, BudgetHeadDeleteView,
    FundListView, FundCreateView, FundUpdateView, FundDeleteView,
    ChequeBookListView, ChequeBookCreateView, ChequeBookDetailView,
    ChequeLeafCancelView, ChequeLeafDamageView
)
from apps.core.views import (
    BankAccountListView, BankAccountCreateView, 
    BankAccountUpdateView, BankAccountDeleteView
)

app_name = 'budgeting'

urlpatterns = [
    # Dashboard
    path('', BudgetingDashboardView.as_view(), name='dashboard'),
    
    # Fiscal Year Management
    path('fiscal-years/', FiscalYearListView.as_view(), name='fiscal_year_list'),
    path('fiscal-years/create/', FiscalYearCreateView.as_view(), name='fiscal_year_create'),
    path('fiscal-years/<int:pk>/update/', FiscalYearUpdateView.as_view(), name='fiscal_year_update'),
    path('fiscal-years/<int:pk>/', FiscalYearDetailView.as_view(), name='fiscal_year_detail'),
    
    # Budget Allocations
    path('allocations/', BudgetAllocationListView.as_view(), name='allocation_list'),
    
    # Form BDR-1: Receipt Estimates
    path('receipt/create/', ReceiptEstimateCreateView.as_view(), name='receipt_create'),
    
    # Form BDC-1: Expenditure Estimates
    path('expenditure/create/', ExpenditureEstimateCreateView.as_view(), name='expenditure_create'),
    
    # Form BDC-2: Schedule of Establishment
    path('establishment/', ScheduleOfEstablishmentListView.as_view(), name='establishment_list'),
    path('establishment/create/', ScheduleOfEstablishmentCreateView.as_view(), name='establishment_create'),
    path('establishment/propose/', NewPostProposalCreateView.as_view(), name='establishment_propose'),
    path('establishment/<int:pk>/', EstablishmentDetailView.as_view(), name='establishment_detail'),
    path('establishment/<int:pk>/approve/', EstablishmentApprovalView.as_view(), name='establishment_approve'),
    path('establishment/bulk-approval/', EstablishmentBulkApprovalView.as_view(), name='establishment_bulk_approval'),
    
    # Smart Calculator API (for HTMX/AJAX)
    path('establishment/<int:pk>/estimate/', SmartCalculatorView.as_view(), name='smart_calculator'),
    
    # Budget Approval & Finalization
    path('fiscal-years/<int:pk>/approve/', BudgetApprovalView.as_view(), name='budget_approval'),
    
    # Quarterly Release
    path('fiscal-years/<int:pk>/release/', QuarterlyReleaseView.as_view(), name='quarterly_release'),
    
    # SAE (Schedule of Authorized Expenditure)
    path('sae/', SAEListView.as_view(), name='sae_list'),
    path('sae/<int:pk>/', SAEDetailView.as_view(), name='sae_detail'),

    # Employee Management (Nested under Schedule Entry)
    path('establishment/<int:schedule_pk>/employees/', EmployeeListView.as_view(), name='employee_list'),
    path('establishment/<int:schedule_pk>/employees/add/', EmployeeCreateView.as_view(), name='employee_add'),
    path('establishment/employees/<int:pk>/edit/', EmployeeUpdateView.as_view(), name='employee_edit'),
    path('establishment/employees/<int:pk>/delete/', EmployeeDeleteView.as_view(), name='employee_delete'),
    
    # Setup Workspace (Admin Only)
    path('setup/', SetupDashboardView.as_view(), name='setup_dashboard'),
    path('setup/departments/', DepartmentListView.as_view(), name='setup_departments'),
    path('setup/departments/add/', DepartmentCreateView.as_view(), name='setup_department_add'),
    path('setup/departments/<int:pk>/edit/', DepartmentUpdateView.as_view(), name='setup_department_edit'),
    path('setup/departments/<int:pk>/delete/', DepartmentDeleteView.as_view(), name='setup_department_delete'),
    
    path('setup/designations/', DesignationListView.as_view(), name='setup_designations'),
    path('setup/designations/add/', DesignationCreateView.as_view(), name='setup_designation_add'),
    path('setup/designations/<int:pk>/edit/', DesignationUpdateView.as_view(), name='setup_designation_edit'),
    path('setup/designations/<int:pk>/delete/', DesignationDeleteView.as_view(), name='setup_designation_delete'),
    
    path('setup/salary-structure/', SalaryStructureView.as_view(), name='setup_salary_structure'),
    
    # Funds
    path('setup/funds/', FundListView.as_view(), name='setup_funds'),
    path('setup/funds/add/', FundCreateView.as_view(), name='setup_fund_add'),
    path('setup/funds/<int:pk>/edit/', FundUpdateView.as_view(), name='setup_fund_edit'),
    path('setup/funds/<int:pk>/delete/', FundDeleteView.as_view(), name='setup_fund_delete'),
    
    # Bank Accounts
    path('setup/bank-accounts/', BankAccountListView.as_view(), name='setup_bank_accounts'),
    path('setup/bank-accounts/add/', BankAccountCreateView.as_view(), name='setup_bank_account_add'),
    path('setup/bank-accounts/<int:pk>/edit/', BankAccountUpdateView.as_view(), name='setup_bank_account_edit'),
    path('setup/bank-accounts/<int:pk>/delete/', BankAccountDeleteView.as_view(), name='setup_bank_account_delete'),

    # Chart of Accounts (CoA)
    path('setup/coa/', BudgetHeadListView.as_view(), name='setup_coa_list'),
    path('setup/coa/add/', BudgetHeadCreateView.as_view(), name='setup_coa_add'),
    path('setup/coa/<int:pk>/edit/', BudgetHeadUpdateView.as_view(), name='setup_coa_edit'),
    path('setup/coa/<int:pk>/delete/', BudgetHeadDeleteView.as_view(), name='setup_coa_delete'),

    # Cheque Books
    path('setup/chequebooks/', ChequeBookListView.as_view(), name='setup_chequebooks'),
    path('setup/chequebooks/add/', ChequeBookCreateView.as_view(), name='setup_chequebook_add'),
    path('setup/chequebooks/<int:pk>/', ChequeBookDetailView.as_view(), name='setup_chequebook_detail'),
    path('setup/chequebooks/<int:pk>/leaves/<int:leaf_pk>/cancel/', ChequeLeafCancelView.as_view(), name='setup_chequeleaf_cancel'),
    path('setup/chequebooks/<int:pk>/leaves/<int:leaf_pk>/damage/', ChequeLeafDamageView.as_view(), name='setup_chequeleaf_damage'),

    # Phase 3: Pension Estimate
    path('pension/', PensionEstimateListView.as_view(), name='pension_list'),
    path('pension/create/', PensionEstimateCreateView.as_view(), name='pension_create'),
    path('pension/<int:pk>/', PensionEstimateDetailView.as_view(), name='pension_detail'),
    path('pension/<int:pk>/calculate/', PensionEstimateCalculateView.as_view(), name='pension_calculate'),

    # Phase 3: Supplementary Grant
    path('supplementary/', SupplementaryGrantListView.as_view(), name='supplementary_list'),
    path('supplementary/create/', SupplementaryGrantCreateView.as_view(), name='supplementary_create'),
    path('supplementary/<int:pk>/', SupplementaryGrantDetailView.as_view(), name='supplementary_detail'),
    path('supplementary/<int:pk>/approve/', SupplementaryGrantApproveView.as_view(), name='supplementary_approve'),

    # Phase 3: Re-appropriation
    path('reappropriation/', ReappropriationListView.as_view(), name='reappropriation_list'),
    path('reappropriation/create/', ReappropriationCreateView.as_view(), name='reappropriation_create'),
    path('reappropriation/<int:pk>/', ReappropriationDetailView.as_view(), name='reappropriation_detail'),
    path('reappropriation/<int:pk>/approve/', ReappropriationApproveView.as_view(), name='reappropriation_approve'),
    
    # Phase 4: Budget Book Reporting
    path('reports/budget-book/<int:fy_id>/', PrintBudgetBookView.as_view(), name='budget_book_print'),
]
