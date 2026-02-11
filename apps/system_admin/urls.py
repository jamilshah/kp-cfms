"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: URL configuration for System Admin module.
-------------------------------------------------------------------------
"""
from django.urls import path
from . import views
from . import master_data_views as md_views

app_name = 'system_admin'

urlpatterns = [
    # Dashboard
    path('', views.SystemDashboardView.as_view(), name='dashboard'),
    
    # Master Data Seeding
    path('seed/', views.MasterDataSeedView.as_view(), name='master_data_seed'),
    
    # Organization Management
    path('organizations/', views.OrganizationListView.as_view(), name='organization_list'),
    path('organizations/create/', views.ProvisionOrganizationView.as_view(), name='provision_organization'),
    path('organizations/settings/', views.OrganizationSettingsView.as_view(), name='organization_settings'),
    path('organizations/<int:pk>/settings/', views.OrganizationSettingsView.as_view(), name='organization_settings_pk'),
    path('organizations/<int:org_pk>/admin/', views.CreateTenantAdminView.as_view(), name='create_tenant_admin'),
    path('organizations/<int:org_pk>/users/', views.TenantUserListView.as_view(), name='tenant_user_list'),
    path('organizations/<int:org_pk>/users/create/', views.TenantUserCreateView.as_view(), name='tenant_user_create'),
    path('organizations/<int:org_pk>/users/<int:pk>/edit/', views.TenantUserEditView.as_view(), name='tenant_user_edit'),
    
    # System User Management (Super Admin)
    path('users/', views.SystemUserListView.as_view(), name='system_user_list'),
    path('users/<int:pk>/assign-role/', views.AssignRoleView.as_view(), name='assign_role'),
    
    # Role Management
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/edit/', views.RoleUpdateView.as_view(), name='role_edit'),
    # path('roles/<int:pk>/permissions/', views.RolePermissionView.as_view(), name='role_permissions'), # Removed
    path('roles/<int:pk>/delete/', views.RoleDeleteView.as_view(), name='role_delete'),
    
    # ==========================================================================
    # Master Data CRUD - Locations
    # ==========================================================================
    path('master-data/locations/template/', md_views.LocationsTemplateView.as_view(), name='locations_template'),
    
    # Divisions
    path('master-data/divisions/', md_views.DivisionListView.as_view(), name='division_list'),
    path('master-data/divisions/create/', md_views.DivisionCreateView.as_view(), name='division_create'),
    path('master-data/divisions/<int:pk>/edit/', md_views.DivisionUpdateView.as_view(), name='division_edit'),
    path('master-data/divisions/<int:pk>/delete/', md_views.DivisionDeleteView.as_view(), name='division_delete'),
    
    # Districts
    path('master-data/districts/', md_views.DistrictListView.as_view(), name='district_list'),
    path('master-data/districts/create/', md_views.DistrictCreateView.as_view(), name='district_create'),
    path('master-data/districts/<int:pk>/edit/', md_views.DistrictUpdateView.as_view(), name='district_edit'),
    path('master-data/districts/<int:pk>/delete/', md_views.DistrictDeleteView.as_view(), name='district_delete'),
    
    # Tehsils
    path('master-data/tehsils/', md_views.TehsilListView.as_view(), name='tehsil_list'),
    path('master-data/tehsils/create/', md_views.TehsilCreateView.as_view(), name='tehsil_create'),
    path('master-data/tehsils/<int:pk>/edit/', md_views.TehsilUpdateView.as_view(), name='tehsil_edit'),
    path('master-data/tehsils/<int:pk>/delete/', md_views.TehsilDeleteView.as_view(), name='tehsil_delete'),
    
    # Global Heads (CoA)
    path('master-data/global-heads/', md_views.GlobalHeadListView.as_view(), name='global_head_list'),
    path('master-data/global-heads/create/', md_views.GlobalHeadCreateView.as_view(), name='global_head_create'),
    path('master-data/global-heads/<int:pk>/edit/', md_views.GlobalHeadUpdateView.as_view(), name='global_head_edit'),
    path('master-data/global-heads/<int:pk>/delete/', md_views.GlobalHeadDeleteView.as_view(), name='global_head_delete'),

    # Function Codes
    path('master-data/function-codes/', md_views.FunctionCodeListView.as_view(), name='function_code_list'),
    path('master-data/function-codes/create/', md_views.FunctionCodeCreateView.as_view(), name='function_code_create'),
    path('master-data/function-codes/<int:pk>/edit/', md_views.FunctionCodeUpdateView.as_view(), name='function_code_edit'),
    path('master-data/function-codes/<int:pk>/delete/', md_views.FunctionCodeDeleteView.as_view(), name='function_code_delete'),
    
    # Tax Rate Configurations
    path('master-data/tax-rates/', md_views.TaxRateConfigurationListView.as_view(), name='tax_rate_list'),
    path('master-data/tax-rates/create/', md_views.TaxRateConfigurationCreateView.as_view(), name='tax_rate_create'),
    path('master-data/tax-rates/<int:pk>/edit/', md_views.TaxRateConfigurationUpdateView.as_view(), name='tax_rate_edit'),
    path('master-data/tax-rates/<int:pk>/activate/', md_views.TaxRateActivateView.as_view(), name='tax_rate_activate'),
    
    # ==========================================================================
    # Master Data CRUD - CSV Templates
    # ==========================================================================
    path('master-data/funds/template/', md_views.FundsTemplateView.as_view(), name='funds_template'),
    path('master-data/departments/template/', md_views.DepartmentsTemplateView.as_view(), name='departments_template'),
    path('master-data/designations/template/', md_views.DesignationsTemplateView.as_view(), name='designations_template'),
    path('master-data/bps-scales/template/', md_views.BPSScalesTemplateView.as_view(), name='bps_scales_template'),
    path('master-data/budget-heads/template/', md_views.BudgetHeadsTemplateView.as_view(), name='budget_heads_template'),
    path('master-data/roles/template/', md_views.RolesTemplateView.as_view(), name='roles_template'),
    path('master-data/organizations/template/', md_views.OrganizationsTemplateView.as_view(), name='organizations_template'),
]
