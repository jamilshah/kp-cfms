"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: BudgetEmployee model for employee-wise budget estimation.
             Links individual employees to ScheduleOfEstablishment entries.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

from apps.core.mixins import TimeStampedMixin


class BudgetEmployee(TimeStampedMixin):
    """
    Individual employee record linked to a ScheduleOfEstablishment entry.
    
    Used for employee-wise budget estimation (BDC-2).
    Each employee's actual pay data is used to calculate precise budget requirements.
    
    Attributes:
        schedule: Parent ScheduleOfEstablishment entry
        name: Employee name
        cnic: National ID (optional)
        personnel_number: HR personnel number (optional)
        is_vacant: Whether this is a vacant post placeholder
        current_basic_pay: Current running basic pay
        monthly_allowances: Total monthly allowances
        annual_increment_amount: Expected annual increment
    """
    
    schedule = models.ForeignKey(
        'budgeting.ScheduleOfEstablishment',
        on_delete=models.CASCADE,
        related_name='employees',
        verbose_name=_('Schedule Entry')
    )
    
    # Personal Data
    name = models.CharField(
        max_length=150,
        verbose_name=_('Employee Name'),
        help_text=_('Full name of the employee.')
    )
    cnic = models.CharField(
        max_length=15,
        blank=True,
        verbose_name=_('CNIC'),
        help_text=_('National ID (e.g., 12345-1234567-1).')
    )
    personnel_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Personnel Number'),
        help_text=_('HR personnel/employee number.')
    )
    
    # Status
    is_vacant = models.BooleanField(
        default=False,
        verbose_name=_('Is Vacant Post'),
        help_text=_('Mark as True if this is a placeholder for a vacant position.')
    )
    
    # Pay Data
    current_basic_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Current Basic Pay'),
        help_text=_('Current running basic pay (monthly).')
    )
    monthly_allowances = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Monthly Allowances'),
        help_text=_('Total monthly allowances (HRA, Medical, Conveyance, Adhoc, etc.).')
    )
    annual_increment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Annual Increment Amount'),
        help_text=_('Expected annual increment (added once per year).')
    )
    
    class Meta:
        verbose_name = _('Budget Employee')
        verbose_name_plural = _('Budget Employees')
        ordering = ['schedule', 'name']
        # Unique constraint only if personnel_number is provided
        constraints = [
            models.UniqueConstraint(
                fields=['schedule', 'personnel_number'],
                name='unique_schedule_personnel',
                condition=models.Q(personnel_number__gt='')
            )
        ]
    
    def __str__(self) -> str:
        if self.is_vacant:
            return f"[VACANT] {self.schedule.designation_name}"
        return f"{self.name} ({self.schedule.designation_name})"
    
    @property
    def monthly_gross(self) -> Decimal:
        """Calculate monthly gross salary."""
        return self.current_basic_pay + self.monthly_allowances
    
    @property
    def annual_cost(self) -> Decimal:
        """
        Calculate annual cost for this employee.
        
        Formula: (Basic + Allowances) * 12 + Annual Increment
        """
        monthly_total = self.current_basic_pay + self.monthly_allowances
        annual = (monthly_total * 12) + self.annual_increment_amount
        return annual.quantize(Decimal('0.01'))
