"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: URL configuration for the expenditure module.
-------------------------------------------------------------------------
"""
from django.urls import path

from apps.expenditure.views import (
    ExpenditureDashboardView,
    PayeeListView, PayeeCreateView, PayeeUpdateView,
    BillListView, BillCreateView, BillDetailView,
    BillSubmitView, BillVerifyView, BillApproveView,
    PaymentCreateView, PaymentListView,
    BillAmountAPIView, load_budget_heads, load_functions
)
from apps.expenditure.views import BankAccountNextChequeAPIView
from apps.expenditure.views_salary import (
    SalaryBillGenerateView, SalaryBillPreviewAPI
)

app_name = 'expenditure'

urlpatterns = [
    # Dashboard
    path('', ExpenditureDashboardView.as_view(), name='dashboard'),
    
    # Payee/Vendor Management
    path('payees/', PayeeListView.as_view(), name='payee_list'),
    path('payees/create/', PayeeCreateView.as_view(), name='payee_create'),
    path('payees/<int:pk>/edit/', PayeeUpdateView.as_view(), name='payee_update'),
    
    # Bill Management
    path('bills/', BillListView.as_view(), name='bill_list'),
    path('bills/create/', BillCreateView.as_view(), name='bill_create'),
    path('bills/<int:pk>/', BillDetailView.as_view(), name='bill_detail'),
    path('bills/<int:pk>/submit/', BillSubmitView.as_view(), name='bill_submit'),
    path('bills/<int:pk>/verify/', BillVerifyView.as_view(), name='bill_verify'),
    path('bills/<int:pk>/approve/', BillApproveView.as_view(), name='bill_approve'),
    
    # Salary Bill Generation
    path('bills/salary/generate/', SalaryBillGenerateView.as_view(), name='salary_bill_generate'),
    path('api/salary/preview/', SalaryBillPreviewAPI.as_view(), name='salary_bill_preview_api'),
    
    # Payment Management
    path('payments/', PaymentListView.as_view(), name='payment_list'),
    path('payments/create/', PaymentCreateView.as_view(), name='payment_create'),
    path('payments/create/<int:bill_pk>/', PaymentCreateView.as_view(), name='payment_create_for_bill'),
    
    # API Endpoints
    path('api/bills/<int:pk>/amount/', BillAmountAPIView.as_view(), name='bill_amount_api'),
    path('api/bank-accounts/<int:pk>/next-cheque/', BankAccountNextChequeAPIView.as_view(), name='bank_account_next_cheque_api'),
    path('ajax/load-budget-heads/', load_budget_heads, name='load_budget_heads'),
    path('ajax/load-functions/', load_functions, name='load_functions'),
]
