"""
Admin interface for Tax Rate Configuration.

Allows super admins to manage tax rates through the Django admin panel.
"""
from django.contrib import admin
from django.utils.html import format_html
from apps.expenditure.models_tax_config import TaxRateConfiguration


@admin.register(TaxRateConfiguration)
class TaxRateConfigurationAdmin(admin.ModelAdmin):
    """
    Admin interface for managing tax rate configurations.
    
    Organized into fieldsets for easy navigation:
    - Basic Information
    - Income Tax Rates (Goods, Services, Works)
    - Sales Tax Withholding Rates
    - Other Rates (Stamp Duty, Standard Sales Tax)
    """
    
    list_display = [
        'tax_year', 'effective_from', 'effective_to', 
        'is_active_badge', 'created_at'
    ]
    list_filter = ['is_active', 'effective_from']
    search_fields = ['tax_year', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tax_year', 'effective_from', 'effective_to', 'is_active', 'notes')
        }),
        ('Income Tax Rates - Goods (Section 153)', {
            'fields': (
                'goods_filer_company',
                'goods_filer_individual',
                'goods_nonfiler_company',
                'goods_nonfiler_individual',
            ),
            'description': 'Income tax rates for supply of goods'
        }),
        ('Income Tax Rates - Services (Section 153)', {
            'fields': (
                'services_filer',
                'services_nonfiler',
            ),
            'description': 'Income tax rates for services'
        }),
        ('Income Tax Rates - Works Contracts (Section 153)', {
            'fields': (
                'works_filer_company',
                'works_filer_individual',
                'works_nonfiler_company',
                'works_nonfiler_individual',
            ),
            'description': 'Income tax rates for works contracts'
        }),
        ('Sales Tax Withholding Rates', {
            'fields': (
                'sales_tax_goods_filer',
                'sales_tax_goods_nonfiler',
                'sales_tax_services_filer',
                'sales_tax_services_nonfiler',
                'sales_tax_works',
            ),
            'description': 'Sales tax withholding percentages (1/5th, 50%, whole)'
        }),
        ('Other Rates', {
            'fields': (
                'stamp_duty_rate',
                'standard_sales_tax_rate',
            ),
            'description': 'Stamp duty and default sales tax rate'
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_badge(self, obj):
        """Display active status as a colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        """
        Override save to ensure only one configuration is active.
        This is also handled in the model's save() method.
        """
        super().save_model(request, obj, form, change)
        
        if obj.is_active:
            # Show message about deactivating other configurations
            from django.contrib import messages
            deactivated = TaxRateConfiguration.objects.filter(
                is_active=True
            ).exclude(pk=obj.pk).count()
            
            if deactivated > 0:
                messages.info(
                    request,
                    f'{deactivated} other configuration(s) were automatically deactivated.'
                )
    
    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }
