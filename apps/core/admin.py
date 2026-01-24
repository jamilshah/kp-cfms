"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Django admin configuration for core models.
-------------------------------------------------------------------------
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.core.models import Division, District, TMA


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    """Admin configuration for Division model."""
    
    list_display = ['name', 'code', 'district_count', 'tma_count', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']
    
    def district_count(self, obj: Division) -> int:
        """Count districts in this division."""
        return obj.districts.count()
    district_count.short_description = _('Districts')
    
    def tma_count(self, obj: Division) -> int:
        """Count TMAs in this division."""
        return TMA.objects.filter(district__division=obj).count()
    tma_count.short_description = _('TMAs')


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    """Admin configuration for District model."""
    
    list_display = ['name', 'division', 'code', 'tma_count', 'is_active']
    list_filter = ['division', 'is_active']
    search_fields = ['name', 'code', 'division__name']
    ordering = ['division__name', 'name']
    
    def tma_count(self, obj: District) -> int:
        """Count TMAs in this district."""
        return obj.tmas.count()
    tma_count.short_description = _('TMAs')


@admin.register(TMA)
class TMAAdmin(admin.ModelAdmin):
    """Admin configuration for TMA model."""
    
    list_display = ['name', 'district', 'division_name', 'code', 'is_active']
    list_filter = ['district__division', 'district', 'is_active']
    search_fields = ['name', 'code', 'district__name', 'district__division__name']
    ordering = ['district__division__name', 'district__name', 'name']
    
    def division_name(self, obj: TMA) -> str:
        """Get division name."""
        return obj.district.division.name
    division_name.short_description = _('Division')
