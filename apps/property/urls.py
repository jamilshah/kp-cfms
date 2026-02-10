"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: URL configuration for Property Management module
-------------------------------------------------------------------------
"""
from django.urls import path
from apps.property import views

app_name = 'property'

urlpatterns = [
    # Dashboard
    path('', views.PropertyDashboardView.as_view(), name='dashboard'),
    
    # Property CRUD
    path('properties/', views.PropertyListView.as_view(), name='list'),
    path('properties/add/', views.PropertyCreateView.as_view(), name='create'),
    path('properties/<int:pk>/', views.PropertyDetailView.as_view(), name='detail'),
    path('properties/<int:pk>/edit/', views.PropertyUpdateView.as_view(), name='update'),
    path('properties/<int:pk>/delete/', views.PropertyDeleteView.as_view(), name='delete'),
    
    # CSV Import
    path('import/csv/', views.PropertyCSVImportView.as_view(), name='csv_import'),
    path('import/csv-template/', views.PropertyCSVTemplateView.as_view(), name='csv_template'),
    
    # AJAX endpoints for cascading dropdowns
    path('ajax/load-districts/', views.load_districts, name='ajax_load_districts'),
    path('ajax/load-tehsils/', views.load_tehsils, name='ajax_load_tehsils'),
    path('ajax/load-mauzas/', views.load_mauzas, name='ajax_load_mauzas'),
    path('ajax/load-villages/', views.load_villages, name='ajax_load_villages'),
    
    # Master data views (optional - can also use admin)
    path('districts/', views.DistrictListView.as_view(), name='district_list'),
    path('mauzas/', views.MauzaListView.as_view(), name='mauza_list'),
    path('villages/', views.VillageListView.as_view(), name='village_list'),
    
    # Lease management
    path('leases/', views.PropertyLeaseListView.as_view(), name='lease_list'),
    path('leases/add/', views.PropertyLeaseCreateView.as_view(), name='lease_create'),
    path('leases/<int:pk>/', views.PropertyLeaseDetailView.as_view(), name='lease_detail'),
    path('leases/<int:pk>/edit/', views.PropertyLeaseUpdateView.as_view(), name='lease_update'),
    path('leases/<int:pk>/terminate/', views.PropertyLeaseTerminateView.as_view(), name='lease_terminate'),
    
    # GIS Map
    path('map/', views.PropertyMapView.as_view(), name='map'),
    path('map/fullscreen/', views.PropertyMapFullscreenView.as_view(), name='map_fullscreen'),
    
    # API endpoints for GIS
    path('api/geojson/', views.PropertyGeoJSONAPIView.as_view(), name='api_geojson'),
    path('api/property/<int:pk>/', views.PropertyDetailAPIView.as_view(), name='api_property_detail'),
    path('api/stats/', views.PropertyStatsAPIView.as_view(), name='api_stats'),
]