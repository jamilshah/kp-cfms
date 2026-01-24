"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Geographic and organizational models for TMAs including
             Division, District, and Tehsil hierarchy.
-------------------------------------------------------------------------
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.mixins import TimeStampedMixin


class Division(TimeStampedMixin):
    """
    Administrative division of Khyber Pakhtunkhwa.
    
    Top level of the geographic hierarchy.
    Examples: Peshawar, Mardan, Hazara, Bannu, etc.
    """
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Division Name')
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        verbose_name=_('Division Code'),
        help_text=_('Short code for the division.')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Division')
        verbose_name_plural = _('Divisions')
        ordering = ['name']
    
    def __str__(self) -> str:
        return self.name
    
    def save(self, *args, **kwargs) -> None:
        """Auto-generate code from name if not provided."""
        if not self.code:
            self.code = self.name[:3].upper()
        super().save(*args, **kwargs)


class District(TimeStampedMixin):
    """
    Administrative district within a division.
    
    Second level of the geographic hierarchy.
    Examples: Peshawar, Nowshera, Abbottabad, Swat, etc.
    """
    
    division = models.ForeignKey(
        Division,
        on_delete=models.PROTECT,
        related_name='districts',
        verbose_name=_('Division')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('District Name')
    )
    code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_('District Code'),
        help_text=_('Short code for the district.')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('District')
        verbose_name_plural = _('Districts')
        ordering = ['division__name', 'name']
        unique_together = ['division', 'name']
    
    def __str__(self) -> str:
        return f"{self.name} ({self.division.name})"
    
    def save(self, *args, **kwargs) -> None:
        """Auto-generate code from name if not provided."""
        if not self.code:
            self.code = self.name[:3].upper()
        super().save(*args, **kwargs)


class TMA(TimeStampedMixin):
    """
    Tehsil Municipal Administration - the primary organizational unit.
    
    Each TMA has its own budget, Chart of Accounts, and financial records.
    This is the lowest level of the geographic hierarchy.
    """
    
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name='tmas',
        verbose_name=_('District')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Tehsil/TMA Name')
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name=_('TMA Code'),
        help_text=_('Unique code for the TMA (auto-generated if blank).')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('TMA')
        verbose_name_plural = _('TMAs')
        ordering = ['district__division__name', 'district__name', 'name']
        unique_together = ['district', 'name']
    
    def __str__(self) -> str:
        return f"TMA {self.name}"
    
    @property
    def full_location(self) -> str:
        """Return full location path: Division > District > Tehsil."""
        return f"{self.district.division.name} > {self.district.name} > {self.name}"
    
    def save(self, *args, **kwargs) -> None:
        """Auto-generate code from division, district, and tehsil name if not provided."""
        if not self.code:
            import re
            div_code = self.district.division.name[:3].upper()
            dist_code = self.district.name[:3].upper()
            # Clean tehsil name: remove special chars, spaces, take first 8 chars
            tehsil_clean = re.sub(r'[^a-zA-Z0-9]', '', self.name)[:8].upper()
            self.code = f"{div_code}-{dist_code}-{tehsil_clean}"
        super().save(*args, **kwargs)
