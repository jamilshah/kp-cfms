"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Django admin for Property Management module
-------------------------------------------------------------------------
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.property.models import (
    Mauza, Village, Property, PropertyLease,
    PropertyPhoto, PropertyDocument, PropertyHistory
)
from apps.core.models import District


# ============================================================================
# INLINE ADMINS
# ============================================================================

class PropertyLeaseInline(admin.TabularInline):
    """Inline admin for property leases."""
    model = PropertyLease
    extra = 0
    fields = ('lease_number', 'tenant', 'lease_start_date', 'lease_end_date', 'monthly_rent', 'status')
    readonly_fields = ('lease_number', 'created_at')
    can_delete = False


class PropertyPhotoInline(admin.TabularInline):
    """Inline admin for property photos."""
    model = PropertyPhoto
    extra = 1
    fields = ('photo', 'photo_url', 'caption', 'is_primary')
    readonly_fields = ('created_at',)


class PropertyDocumentInline(admin.TabularInline):
    """Inline admin for property documents."""
    model = PropertyDocument
    extra = 1
    fields = ('document_type', 'document', 'document_url', 'description')
    readonly_fields = ('created_at',)


class PropertyHistoryInline(admin.TabularInline):
    """Inline admin for property history."""
    model = PropertyHistory
    extra = 0
    fields = ('action', 'field_changed', 'old_value', 'new_value', 'changed_by', 'created_at')
    readonly_fields = ('action', 'field_changed', 'old_value', 'new_value', 'changed_by', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


# ============================================================================
# MODEL ADMINS
# ============================================================================

# District is managed in core app admin

@admin.register(Mauza)
class MauzaAdmin(admin.ModelAdmin):
    """Admin for Mauza model."""
    
    list_display = ('name', 'district', 'code', 'property_count', 'created_at')
    list_filter = ('district',)
    search_fields = ('name', 'code', 'district__name')
    ordering = ('district__name', 'name')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'district', 'code')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def property_count(self, obj):
        """Count properties in mauza."""
        count = obj.properties.count()
        if count > 0:
            url = reverse('admin:property_property_changelist') + f'?mauza__id__exact={obj.id}'
            return format_html('<a href="{}">{} properties</a>', url, count)
        return count
    property_count.short_description = _('Properties')


@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    """Admin for Village model."""
    
    list_display = ('name', 'mauza', 'get_district', 'code', 'property_count', 'created_at')
    list_filter = ('mauza__district',)
    search_fields = ('name', 'code', 'mauza__name')
    ordering = ('mauza__district__name', 'mauza__name', 'name')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'mauza', 'code')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_district(self, obj):
        """Get district from mauza."""
        return obj.mauza.district.name
    get_district.short_description = _('District')
    get_district.admin_order_field = 'mauza__district__name'
    
    def property_count(self, obj):
        """Count properties in village."""
        count = obj.properties.count()
        if count > 0:
            url = reverse('admin:property_property_changelist') + f'?village__id__exact={obj.id}'
            return format_html('<a href="{}">{} properties</a>', url, count)
        return count
    property_count.short_description = _('Properties')


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    """Admin for Property model."""
    
    list_display = (
        'property_code', 'name', 'property_type', 'status_badge',
        'area_marlas', 'monthly_rent', 'get_location', 'is_active'
    )
    list_filter = (
        'status', 'property_type', 'property_sub_type',
        'district', 'is_active', 'court_case_status'
    )
    search_fields = (
        'property_code', 'name', 'address', 'tenant_name',
        'ownership_title', 'remarks'
    )
    
    readonly_fields = (
        'area_sqft', 'area_sqm', 'monthly_rent',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'property_code', 'name', 'property_type', 'property_sub_type',
                'status', 'organization', 'is_active'
            )
        }),
        (_('Location'), {
            'fields': (
                'address', 'district', 'mauza', 'village',
                'latitude', 'longitude'
            )
        }),
        (_('Area'), {
            'fields': (
                'area_marlas', 'area_sqft', 'area_sqm'
            )
        }),
        (_('Ownership & Legal'), {
            'fields': (
                'ownership_title', 'survey_number'
            )
        }),
        (_('Financial Information'), {
            'fields': (
                'annual_rent', 'monthly_rent', 'last_rent_revision'
            )
        }),
        (_('Tenant Information'), {
            'fields': (
                'current_tenant', 'tenant_name', 'tenant_cnic', 'tenant_contact',
                'lease_start_date', 'lease_end_date'
            ),
            'classes': ('collapse',)
        }),
        (_('Litigation'), {
            'fields': (
                'court_case_status', 'court_case_title', 'court_name',
                'case_number', 'next_hearing_date'
            ),
            'classes': ('collapse',)
        }),
        (_('Future Plans & Remarks'), {
            'fields': (
                'future_use', 'remarks'
            ),
            'classes': ('collapse',)
        }),
        (_('Audit Information'), {
            'fields': (
                'created_at', 'updated_at', 'created_by', 'updated_by'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PropertyLeaseInline, PropertyPhotoInline, PropertyDocumentInline, PropertyHistoryInline]
    
    actions = ['mark_as_vacant', 'mark_as_rented', 'mark_as_under_litigation']
    
    def status_badge(self, obj):
        """Display status with color badge."""
        color_map = {
            'RENTED_OUT': 'success',
            'VACANT': 'danger',
            'UNDER_LITIGATION': 'warning',
            'SELF_USE': 'info',
            'UNDER_CONSTRUCTION': 'secondary',
            'DEMOLISHED': 'dark',
            'ENCROACHED': 'warning',
        }
        color = color_map.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def get_location(self, obj):
        """Get formatted location."""
        return f"{obj.district.name}, {obj.mauza.name}"
    get_location.short_description = _('Location')
    
    # Custom actions
    def mark_as_vacant(self, request, queryset):
        """Mark selected properties as vacant."""
        updated = queryset.update(status='VACANT')
        self.message_user(request, f'{updated} properties marked as vacant.')
    mark_as_vacant.short_description = _('Mark selected as Vacant')
    
    def mark_as_rented(self, request, queryset):
        """Mark selected properties as rented out."""
        updated = queryset.update(status='RENTED_OUT')
        self.message_user(request, f'{updated} properties marked as rented out.')
    mark_as_rented.short_description = _('Mark selected as Rented Out')
    
    def mark_as_under_litigation(self, request, queryset):
        """Mark selected properties as under litigation."""
        updated = queryset.update(status='UNDER_LITIGATION', court_case_status='PENDING')
        self.message_user(request, f'{updated} properties marked as under litigation.')
    mark_as_under_litigation.short_description = _('Mark selected as Under Litigation')


@admin.register(PropertyPhoto)
class PropertyPhotoAdmin(admin.ModelAdmin):
    """Admin for Property Photo model."""
    
    list_display = ('property', 'caption', 'is_primary', 'created_at')
    list_filter = ('is_primary', 'created_at')
    search_fields = ('property__property_code', 'property__name', 'caption')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Photo Information'), {
            'fields': ('property', 'photo', 'photo_url', 'caption', 'is_primary')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PropertyDocument)
class PropertyDocumentAdmin(admin.ModelAdmin):
    """Admin for Property Document model."""
    
    list_display = ('property', 'document_type', 'created_at')
    list_filter = ('document_type', 'created_at')
    search_fields = ('property__property_code', 'property__name', 'document_type', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Document Information'), {
            'fields': ('property', 'document_type', 'document', 'document_url', 'description')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PropertyHistory)
class PropertyHistoryAdmin(admin.ModelAdmin):
    """Admin for Property History model."""
    
    list_display = ('property', 'action', 'field_changed', 'changed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('property__property_code', 'property__name', 'action', 'field_changed')
    readonly_fields = ('property', 'action', 'field_changed', 'old_value', 'new_value', 'remarks', 'changed_by', 'created_at')
    
    def has_add_permission(self, request):
        """History records are created automatically."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """History records should not be deleted."""
        return False


@admin.register(PropertyLease)
class PropertyLeaseAdmin(admin.ModelAdmin):
    """Admin for Property Lease model."""
    
    list_display = (
        'lease_number', 'property_code_link', 'tenant_name', 
        'lease_start_date', 'lease_end_date', 'monthly_rent', 
        'status_badge', 'remaining_days_display'
    )
    list_filter = ('status', 'lease_start_date', 'created_at')
    search_fields = ('lease_number', 'property__property_code', 'property__name', 'tenant__name')
    readonly_fields = ('lease_number', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        (_('Lease Identification'), {
            'fields': ('lease_number', 'property', 'tenant', 'organization')
        }),
        (_('Lease Period'), {
            'fields': ('lease_start_date', 'lease_end_date', 'status')
        }),
        (_('Financial Terms'), {
            'fields': ('monthly_rent', 'security_deposit', 'annual_increment_percentage')
        }),
        (_('Agreement Details'), {
            'fields': ('agreement_date', 'agreement_document', 'terms_and_conditions')
        }),
        (_('Termination'), {
            'fields': ('termination_date', 'termination_reason'),
            'classes': ('collapse',)
        }),
        (_('Additional'), {
            'fields': ('remarks', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def property_code_link(self, obj):
        """Link to property detail."""
        url = reverse('admin:property_property_change', args=[obj.property.id])
        return format_html('<a href="{}">{}</a>', url, obj.property.property_code)
    property_code_link.short_description = _('Property')
    
    def tenant_name(self, obj):
        """Get tenant name."""
        return obj.tenant.name
    tenant_name.short_description = _('Tenant')
    tenant_name.admin_order_field = 'tenant__name'
    
    def status_badge(self, obj):
        """Display status with color badge."""
        color_map = {
            'DRAFT': 'gray',
            'ACTIVE': 'green',
            'EXPIRED': 'orange',
            'TERMINATED': 'red',
            'RENEWED': 'blue'
        }
        color = color_map.get(obj.status, 'gray')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def remaining_days_display(self, obj):
        """Display remaining days if active."""
        if obj.status == 'ACTIVE' and obj.remaining_days is not None:
            if obj.remaining_days < 30:
                color = 'red'
            elif obj.remaining_days < 90:
                color = 'orange'
            else:
                color = 'green'
            return format_html(
                '<span style="color: {};">{} days</span>',
                color, obj.remaining_days
            )
        return '-'
    remaining_days_display.short_description = _('Remaining')
