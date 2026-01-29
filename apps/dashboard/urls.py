"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: URL routing for dashboard app.
-------------------------------------------------------------------------
"""
from django.urls import path
from apps.dashboard.views import ExecutiveDashboardView, ProvincialDashboardView

app_name = 'dashboard'

urlpatterns = [
    path('', ExecutiveDashboardView.as_view(), name='index'),
    path('provincial/', ProvincialDashboardView.as_view(), name='provincial'),
]
