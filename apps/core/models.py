"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Geographic and organizational models for TMAs including
             Division, District, Tehsil (Geography) and Organization (Tenant).
-------------------------------------------------------------------------
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.mixins import TimeStampedMixin, AuditLogMixin, StatusMixin


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


class Tehsil(TimeStampedMixin):
    """
    Geographic tehsil within a district.
    
    Third level of the geographic hierarchy (WHERE it is).
    This is the GEOGRAPHIC unit - NOT the administrative unit.
    One Tehsil may have multiple Organizations (TMAs/Towns).
    """
    
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name='tehsils',
        verbose_name=_('District')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Tehsil Name')
    )
    code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Tehsil Code'),
        help_text=_('Unique code for the tehsil.')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Tehsil')
        verbose_name_plural = _('Tehsils')
        ordering = ['district__division__name', 'district__name', 'name']
        unique_together = ['district', 'name']
    
    def __str__(self) -> str:
        return f"{self.name} ({self.district.name})"
    
    @property
    def full_location(self) -> str:
        """Return full location path: Division > District > Tehsil."""
        return f"{self.district.division.name} > {self.district.name} > {self.name}"
    
    def save(self, *args, **kwargs) -> None:
        """Auto-generate code from hierarchy if not provided."""
        if not self.code:
            import re
            div_code = self.district.division.name[:3].upper()
            dist_code = self.district.name[:3].upper()
            tehsil_clean = re.sub(r'[^a-zA-Z0-9]', '', self.name)[:8].upper()
            self.code = f"{div_code}-{dist_code}-{tehsil_clean}"
        super().save(*args, **kwargs)


class OrganizationType(models.TextChoices):
    """
    Types of organizations in the system.
    """
    TMA = 'TMA', _('Tehsil Municipal Administration')
    TOWN = 'TOWN', _('Town Municipal Administration')
    LCB = 'LCB', _('Local Council Board')
    LGD = 'LGD', _('Local Government Department')


class Organization(TimeStampedMixin):
    """
    Tenant model representing an administrative organization.
    
    This is the PRIMARY TENANT for multi-tenancy (WHO runs it).
    All transactional data (Budget, Bills, etc.) is scoped to an Organization.
    
    Attributes:
        name: Organization display name.
        tehsil: Geographic location (nullable for LCB/LGD).
        org_type: Type of organization (TMA, Town, LCB, LGD).
        ddo_code: Drawing & Disbursing Officer Code (unique identifier).
        pla_account_no: Personal Ledger Account number for treasury.
        is_active: Whether organization is operational.
    """
    
    name = models.CharField(
        max_length=150,
        verbose_name=_('Organization Name'),
        help_text=_('e.g., "TMA Town-1 Peshawar" or "LCB Peshawar"')
    )
    tehsil = models.ForeignKey(
        Tehsil,
        on_delete=models.PROTECT,
        related_name='organizations',
        null=True,
        blank=True,
        verbose_name=_('Tehsil'),
        help_text=_('Geographic location. Null for LCB/LGD.')
    )
    org_type = models.CharField(
        max_length=10,
        choices=OrganizationType.choices,
        default=OrganizationType.TMA,
        verbose_name=_('Organization Type')
    )
    ddo_code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_('DDO Code'),
        help_text=_('Drawing & Disbursing Officer Code (unique per organization).')
    )
    pla_account_no = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('PLA Account No'),
        help_text=_('Personal Ledger Account number at AG Office.')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')
        ordering = ['name']
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def full_location(self) -> str:
        """Return full location path if tehsil is set."""
        if self.tehsil:
            return self.tehsil.full_location
        return f"{self.get_org_type_display()} (Provincial)"
    
    def is_tma(self) -> bool:
        """Check if this is a TMA or Town organization."""
        return self.org_type in [OrganizationType.TMA, OrganizationType.TOWN]
    
    def is_oversight_body(self) -> bool:
        """Check if this is an oversight organization (LCB/LGD)."""
        return self.org_type in [OrganizationType.LCB, OrganizationType.LGD]


class BankAccount(AuditLogMixin, StatusMixin):
    """
    Bank account linked to an organization and the General Ledger.
    
    Each organization can have multiple bank accounts. Each account is
    linked to a BudgetHead (GL code) to enable proper accounting.
    
    Attributes:
        organization: The TMA/Organization that owns this account.
        bank_name: Name of the bank (e.g., "National Bank of Pakistan").
        branch_code: Bank branch code.
        account_number: Bank account number (unique).
        title: Account title/name.
        gl_code: Link to BudgetHead (Asset account in GL).
        is_active: Whether account is currently active.
    """
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='bank_accounts',
        verbose_name=_('Organization'),
        help_text=_('The TMA/Organization that owns this account.')
    )
    bank_name = models.CharField(
        max_length=100,
        verbose_name=_('Bank Name'),
        help_text=_('Name of the bank (e.g., "National Bank of Pakistan").')
    )
    branch_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Branch Code'),
        help_text=_('Bank branch code.')
    )
    account_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('Account Number'),
        help_text=_('Bank account number (must be unique).')
    )
    title = models.CharField(
        max_length=150,
        verbose_name=_('Account Title'),
        help_text=_('Account title/name as per bank records.')
    )
    gl_code = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='bank_accounts',
        verbose_name=_('GL Code'),
        help_text=_('Link to BudgetHead (Asset account in General Ledger).')
    )
    # is_active inherited from StatusMixin
    
    class Meta:
        verbose_name = _('Bank Account')
        verbose_name_plural = _('Bank Accounts')
        ordering = ['organization__name', 'bank_name', 'account_number']
        indexes = [
            models.Index(fields=['organization']),
            models.Index(fields=['account_number']),
        ]
    
    def __str__(self) -> str:
        return f"{self.bank_name} - {self.account_number} ({self.organization.name})"
    
    @property
    def masked_account_number(self) -> str:
        """Return masked account number for display (e.g., ****1234)."""
        if len(self.account_number) > 4:
            return f"****{self.account_number[-4:]}"
        return self.account_number


# Backward compatibility alias - DEPRECATED, use Organization instead
TMA = Organization
