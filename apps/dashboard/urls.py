"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: URL routing for dashboard app including role-based workspaces.
-------------------------------------------------------------------------
"""
from django.urls import path
from apps.dashboard.views import (
    ExecutiveDashboardView,
    ProvincialDashboardView,
    DashboardRedirectView,
    FinanceWorkspaceView,
    AuditWorkspaceView,
    RevenueWorkspaceView,
    PAOWorkspaceView,
    EBaldiaDashboardView,
    ComingSoonView,
)

app_name = 'dashboard'

urlpatterns = [
    # e-Baldia Landing Page
    path('ebaldia/', EBaldiaDashboardView.as_view(), name='ebaldia'),
    path('coming-soon/', ComingSoonView.as_view(), name='coming_soon'),
    
    # Main Dashboards
    path('', ExecutiveDashboardView.as_view(), name='index'),
    path('provincial/', ProvincialDashboardView.as_view(), name='provincial'),
    path('workspace/', DashboardRedirectView.as_view(), name='workspace_redirect'),
    
    # Role-Specific Workspaces
    path('workspace/finance/', FinanceWorkspaceView.as_view(), name='workspace_finance'),
    path('workspace/audit/', AuditWorkspaceView.as_view(), name='workspace_audit'),
    path('workspace/revenue/', RevenueWorkspaceView.as_view(), name='workspace_revenue'),
    path('workspace/pao/', PAOWorkspaceView.as_view(), name='workspace_pao'),
]
