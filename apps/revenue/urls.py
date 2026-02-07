"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Revenue URL Configuration
-------------------------------------------------------------------------
"""
from django.urls import path
from . import views

app_name = 'revenue'

urlpatterns = [
    # Dashboard
    path('', views.RevenueDashboardView.as_view(), name='dashboard'),
    
    # Payers
    path('payers/', views.PayerListView.as_view(), name='payer_list'),
    path('payers/create/', views.PayerCreateView.as_view(), name='payer_create'),
    path('payers/<int:pk>/', views.PayerDetailView.as_view(), name='payer_detail'),
    path('payers/<int:pk>/edit/', views.PayerUpdateView.as_view(), name='payer_update'),
    
    # Demands
    path('demands/', views.DemandListView.as_view(), name='demand_list'),
    path('demands/create/', views.DemandCreateView.as_view(), name='demand_create'),
    path('demands/<int:pk>/', views.DemandDetailView.as_view(), name='demand_detail'),
    path('demands/<int:pk>/post/', views.DemandPostView.as_view(), name='demand_post'),
    path('demands/<int:pk>/cancel/', views.DemandCancelView.as_view(), name='demand_cancel'),
    path('demands/<int:pk>/waive-penalty/', views.DemandWaivePenaltyView.as_view(), name='demand_waive_penalty'),
    
    # Collections
    path('collections/', views.CollectionListView.as_view(), name='collection_list'),
    path('collections/create/', views.CollectionCreateView.as_view(), name='collection_create'),
    path('collections/<int:pk>/', views.CollectionDetailView.as_view(), name='collection_detail'),
    path('collections/<int:pk>/post/', views.CollectionPostView.as_view(), name='collection_post'),
    path('collections/<int:pk>/cancel/', views.CollectionCancelView.as_view(), name='collection_cancel'),
    
    # API
    path('api/demands/<int:pk>/outstanding/', views.DemandOutstandingAPIView.as_view(), name='demand_outstanding_api'),
    
    # Export
    path('demands/export/', views.DemandExportView.as_view(), name='demand_export'),
    path('collections/export/', views.CollectionExportView.as_view(), name='collection_export'),
    
    # Reports
    path('reports/outstanding-receivables/', views.OutstandingReceivablesReportView.as_view(), name='report_outstanding_receivables'),
    path('reports/revenue-by-head/', views.RevenueByHeadReportView.as_view(), name='report_revenue_by_head'),
    path('reports/payer-wise-summary/', views.PayerWiseSummaryView.as_view(), name='report_payer_wise'),
    path('reports/collection-efficiency/', views.CollectionEfficiencyReportView.as_view(), name='report_collection_efficiency'),
    path('reports/overdue-demands/', views.OverdueDemandsReportView.as_view(), name='report_overdue_demands'),
    path('reports/demand-vs-collection/', views.DemandVsCollectionComparisonView.as_view(), name='report_demand_vs_collection'),
    
    # AJAX
    path('ajax/load-functions/', views.load_functions, name='load_functions'),
    path('ajax/load-revenue-heads/', views.load_revenue_heads, name='load_revenue_heads'),
]
