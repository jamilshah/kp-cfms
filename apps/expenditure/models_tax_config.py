"""
Tax Rate Configuration Models for KP-CFMS.

Allows super admins to configure and update tax rates annually
without requiring code changes.
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from apps.core.mixins import TimeStampedMixin


class TaxRateConfiguration(TimeStampedMixin):
    """
    Configurable tax rates for withholding calculations.
    
    Super admins can update these rates annually as per FBR/KPRA notifications.
    The TaxCalculator service will use the active configuration.
    
    Attributes:
        tax_year: Fiscal year for which these rates apply (e.g., "2025-26")
        effective_from: Date from which these rates become active
        effective_to: Date until which these rates are valid
        is_active: Whether this configuration is currently active
    """
    
    tax_year = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_('Tax Year'),
        help_text=_('Fiscal year for these rates (e.g., "2025-26")')
    )
    effective_from = models.DateField(
        verbose_name=_('Effective From'),
        help_text=_('Date from which these rates become active')
    )
    effective_to = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Effective To'),
        help_text=_('Date until which these rates are valid (leave blank for indefinite)')
    )
    is_active = models.BooleanField(
        default=False,
        verbose_name=_('Is Active'),
        help_text=_('Only one configuration can be active at a time')
    )
    
    # Income Tax Rates - Goods
    goods_filer_company = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0500'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Goods - Active Filer (Company)'),
        help_text=_('Income tax rate for goods supplied by active filer companies (e.g., 0.0500 for 5%)')
    )
    goods_filer_individual = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0550'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Goods - Active Filer (Individual)'),
        help_text=_('Income tax rate for goods supplied by active filer individuals')
    )
    goods_nonfiler_company = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.1000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Goods - Non-Filer (Company)'),
        help_text=_('Income tax rate for goods supplied by non-filer companies')
    )
    goods_nonfiler_individual = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.1100'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Goods - Non-Filer (Individual)'),
        help_text=_('Income tax rate for goods supplied by non-filer individuals')
    )
    
    # Income Tax Rates - Services
    services_filer = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.1500'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Services - Active Filer'),
        help_text=_('Income tax rate for services by active filers')
    )
    services_nonfiler = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.3000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Services - Non-Filer'),
        help_text=_('Income tax rate for services by non-filers')
    )
    
    # Income Tax Rates - Works Contracts
    works_filer_company = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0750'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Works - Active Filer (Company)'),
        help_text=_('Income tax rate for works contracts by active filer companies')
    )
    works_filer_individual = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0800'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Works - Active Filer (Individual)'),
        help_text=_('Income tax rate for works contracts by active filer individuals')
    )
    works_nonfiler_company = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.1500'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Works - Non-Filer (Company)'),
        help_text=_('Income tax rate for works contracts by non-filer companies')
    )
    works_nonfiler_individual = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.1600'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Works - Non-Filer (Individual)'),
        help_text=_('Income tax rate for works contracts by non-filer individuals')
    )
    
    # Sales Tax Withholding Rates
    sales_tax_goods_filer = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.2000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Sales Tax Withholding - Goods (Filer)'),
        help_text=_('Withholding rate for goods (1/5th = 0.2000)')
    )
    sales_tax_goods_nonfiler = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('1.0000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Sales Tax Withholding - Goods (Non-Filer)'),
        help_text=_('Withholding rate for goods (whole = 1.0000)')
    )
    sales_tax_services_filer = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.5000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Sales Tax Withholding - Services (Filer)'),
        help_text=_('Withholding rate for services (50% = 0.5000)')
    )
    sales_tax_services_nonfiler = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('1.0000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Sales Tax Withholding - Services (Non-Filer)'),
        help_text=_('Withholding rate for services (whole = 1.0000)')
    )
    sales_tax_works = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('1.0000'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Sales Tax Withholding - Works'),
        help_text=_('Withholding rate for works (whole = 1.0000, regardless of filer status)')
    )
    
    # Stamp Duty Rate
    stamp_duty_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0100'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Stamp Duty Rate'),
        help_text=_('Stamp duty rate for works contracts (1% = 0.0100)')
    )
    
    # Standard Sales Tax Rate (for calculation when invoice not provided)
    standard_sales_tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.1800'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        verbose_name=_('Standard Sales Tax Rate'),
        help_text=_('Default sales tax rate for calculation (18% = 0.1800)')
    )
    
    # Audit fields
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Reference to FBR/KPRA notification or any special notes')
    )
    
    class Meta:
        verbose_name = _('Tax Rate Configuration')
        verbose_name_plural = _('Tax Rate Configurations')
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['effective_from', 'effective_to']),
        ]
    
    def __str__(self) -> str:
        status = "Active" if self.is_active else "Inactive"
        return f"Tax Rates {self.tax_year} ({status})"
    
    def save(self, *args, **kwargs):
        """Ensure only one configuration is active at a time."""
        if self.is_active:
            # Deactivate all other configurations
            TaxRateConfiguration.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_config(cls):
        """
        Get the currently active tax rate configuration.
        
        Returns:
            TaxRateConfiguration: Active configuration or None if not found
        """
        return cls.objects.filter(is_active=True).first()
