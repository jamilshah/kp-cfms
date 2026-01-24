"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Finance models including BudgetHead (Chart of Accounts)
             following the PIFRA/NAM hierarchy structure.
-------------------------------------------------------------------------
"""
import re
from typing import Optional
from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from apps.core.mixins import AuditLogMixin, StatusMixin


class AccountType(models.TextChoices):
    """
    Account type classification based on NAM structure.
    """
    
    EXPENDITURE = 'EXP', _('Expenditure')
    REVENUE = 'REV', _('Revenue')
    LIABILITY = 'LIA', _('Liability')
    ASSET = 'AST', _('Asset')
    EQUITY = 'EQT', _('Equity')


class FundType(models.TextChoices):
    """
    Fund type classification for reporting.
    
    PUGF: Provincial Urban General Fund (for Provincial cadre officers)
    NON_PUGF: Local Council Staff and operational expenses
    DEVELOPMENT: Capital/ADP projects
    PENSION: Pension fund
    """
    
    PUGF = 'PUGF', _('PUGF (Provincial)')
    NON_PUGF = 'NPUGF', _('Non-PUGF (Local)')
    DEVELOPMENT = 'DEV', _('Development')
    PENSION = 'PEN', _('Pension')
    OTHER = 'OTH', _('Other')


class FunctionCode(models.Model):
    """
    Functional classification of budget heads.
    
    Examples: AD (Administration), WS (Water Supply), SW (Sanitation).
    """
    
    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_('Function Code'),
        help_text=_('Short code for the function (e.g., AD, WS, SW).')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Function Name'),
        help_text=_('Full name of the function (e.g., Administration).')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Function Code')
        verbose_name_plural = _('Function Codes')
        ordering = ['code']
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class BudgetHead(AuditLogMixin, StatusMixin):
    """
    Budget Head representing a Chart of Accounts entry.
    
    Follows the PIFRA/NAM hierarchy:
    Entity -> Fund -> Function -> Object (Major/Minor/Detailed)
    
    The PUGF classification is DERIVED from:
    1. Object code (A01101 = Officers = PUGF, A01151 = Other Staff = Non-PUGF)
    2. Designation keywords in description
    
    Attributes:
        fund_id: Numeric fund identifier (1=Current, 2=Development, 5=Pension)
        function: ForeignKey to FunctionCode
        pifra_object: PIFRA object code (e.g., A01101)
        tma_sub_object: TMA-specific sub-object code
        description: Human-readable description
        account_type: Expenditure, Revenue, etc.
        fund_type: Derived PUGF/Non-PUGF classification
        budget_control: Whether budget limits apply
        project_required: Whether project code is required
        posting_allowed: Whether transactions can be posted
    """
    
    # NAM Code validator (alphanumeric with optional dash)
    nam_code_validator = RegexValidator(
        regex=r'^[A-Z0-9]+-?[A-Z0-9]*$',
        message=_('NAM code must be alphanumeric (e.g., A01101 or A01101-000).')
    )
    
    fund_id = models.PositiveSmallIntegerField(
        verbose_name=_('Fund ID'),
        help_text=_('1=Current, 2=Development, 4=PLA, 5=Pension'),
        default=1
    )
    function = models.ForeignKey(
        FunctionCode,
        on_delete=models.PROTECT,
        related_name='budget_heads',
        verbose_name=_('Function'),
        null=True,
        blank=True
    )
    pifra_object = models.CharField(
        max_length=20,
        validators=[nam_code_validator],
        verbose_name=_('PIFRA Object Code'),
        help_text=_('Standard PIFRA object code (e.g., A01101).')
    )
    pifra_description = models.CharField(
        max_length=255,
        verbose_name=_('PIFRA Description'),
        help_text=_('Standard PIFRA description.')
    )
    tma_sub_object = models.CharField(
        max_length=30,
        unique=True,
        validators=[nam_code_validator],
        verbose_name=_('TMA Sub-Object Code'),
        help_text=_('TMA-specific sub-object code (e.g., A01101-000).')
    )
    tma_description = models.CharField(
        max_length=255,
        verbose_name=_('TMA Description'),
        help_text=_('TMA-specific description.')
    )
    account_type = models.CharField(
        max_length=3,
        choices=AccountType.choices,
        default=AccountType.EXPENDITURE,
        verbose_name=_('Account Type')
    )
    fund_type = models.CharField(
        max_length=5,
        choices=FundType.choices,
        default=FundType.NON_PUGF,
        verbose_name=_('Fund Type'),
        help_text=_('PUGF/Non-PUGF classification (derived from object code).')
    )
    budget_control = models.BooleanField(
        default=True,
        verbose_name=_('Budget Control'),
        help_text=_('Whether hard budget limits are enforced.')
    )
    project_required = models.BooleanField(
        default=False,
        verbose_name=_('Project Required'),
        help_text=_('Whether a project code is required for transactions.')
    )
    posting_allowed = models.BooleanField(
        default=True,
        verbose_name=_('Posting Allowed'),
        help_text=_('Whether transactions can be posted to this head.')
    )
    is_charged = models.BooleanField(
        default=False,
        verbose_name=_('Is Charged (Non-Votable)'),
        help_text=_('Charged expenditure that Council cannot reduce.')
    )
    
    class Meta:
        verbose_name = _('Budget Head')
        verbose_name_plural = _('Budget Heads')
        ordering = ['fund_id', 'pifra_object', 'tma_sub_object']
        indexes = [
            models.Index(fields=['pifra_object']),
            models.Index(fields=['tma_sub_object']),
            models.Index(fields=['fund_type']),
            models.Index(fields=['account_type']),
        ]
    
    def __str__(self) -> str:
        return f"{self.tma_sub_object} - {self.tma_description}"
    
    def save(self, *args, **kwargs) -> None:
        """
        Override save to auto-derive fund_type based on object code.
        """
        self.fund_type = self.derive_fund_type()
        super().save(*args, **kwargs)
    
    def derive_fund_type(self) -> str:
        """
        Derive PUGF/Non-PUGF classification based on rules.
        
        Logic (as per KP LG Act 2013 clarification):
        1. Fund 5 -> PENSION
        2. Fund 2 -> DEVELOPMENT
        3. Fund 1 with A01101 (Officers) -> PUGF
        4. Fund 1 with A01151 (Other Staff) -> NON_PUGF
        5. Fund 1 + Officer keywords in desc -> PUGF
        6. Otherwise -> NON_PUGF
        
        Returns:
            FundType value string.
        """
        # Pension is always separate
        if self.fund_id == 5:
            return FundType.PENSION
        
        # Development is always separate
        if self.fund_id == 2:
            return FundType.DEVELOPMENT
        
        # For Fund 1 (Current), derive from object code
        if self.fund_id == 1:
            # A01101 = Basic Pay of Officers = PUGF
            if self.pifra_object == 'A01101':
                return FundType.PUGF
            
            # A01151 = Basic Pay of Other Staff = Non-PUGF
            if self.pifra_object == 'A01151':
                return FundType.NON_PUGF
            
            # Check for officer keywords in description
            pugf_keywords = ['tmo', 'tehsil officer', 'engineer', 'superintendent']
            desc_lower = self.tma_description.lower()
            if any(keyword in desc_lower for keyword in pugf_keywords):
                return FundType.PUGF
        
        # Default to Non-PUGF
        return FundType.NON_PUGF
    
    def get_full_code(self) -> str:
        """Return the complete NAM code path."""
        func_code = self.function.code if self.function else 'XX'
        return f"F{self.fund_id}-{func_code}-{self.tma_sub_object}"
    
    def is_salary_head(self) -> bool:
        """Check if this is a salary-related budget head (A01*)."""
        return self.pifra_object.startswith('A01')
    
    def is_development_head(self) -> bool:
        """Check if this is a development budget head."""
        return self.fund_id == 2 or self.fund_type == FundType.DEVELOPMENT
