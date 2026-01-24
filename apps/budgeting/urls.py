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

from apps.budgeting.views import (
    BudgetingDashboardView,
    FiscalYearListView, FiscalYearCreateView, FiscalYearDetailView,
    BudgetAllocationListView, ReceiptEstimateCreateView, ExpenditureEstimateCreateView,
    ScheduleOfEstablishmentListView, ScheduleOfEstablishmentCreateView,
    BudgetApprovalView, QuarterlyReleaseView,
    SAEListView, SAEDetailView,
)

app_name = 'budgeting'

urlpatterns = [
    # Dashboard
    path('', BudgetingDashboardView.as_view(), name='dashboard'),
    
    # Fiscal Year Management
    path('fiscal-years/', FiscalYearListView.as_view(), name='fiscal_year_list'),
    path('fiscal-years/create/', FiscalYearCreateView.as_view(), name='fiscal_year_create'),
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
    
    # Budget Approval & Finalization
    path('fiscal-years/<int:pk>/approve/', BudgetApprovalView.as_view(), name='budget_approval'),
    
    # Quarterly Release
    path('fiscal-years/<int:pk>/release/', QuarterlyReleaseView.as_view(), name='quarterly_release'),
    
    # SAE (Schedule of Authorized Expenditure)
    path('sae/', SAEListView.as_view(), name='sae_list'),
    path('sae/<int:pk>/', SAEDetailView.as_view(), name='sae_detail'),
]
