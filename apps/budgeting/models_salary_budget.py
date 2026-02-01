"""
Salary Budget Allocation and Tracking Models

Handles department-level salary budget distribution and consumption tracking.
Since provincial budget is allocated as lumpsum per account code, this model
distributes it among departments based on employee strength and tracks monthly
consumption to enforce budget control.
"""

from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from apps.finance.models import GlobalHead, Fund

# Import Department from budgeting (avoid circular import)
from django.apps import apps


class DepartmentSalaryBudget(models.Model):
    """
    Tracks salary budget allocation and consumption per department.
    
    Budget is distributed among departments based on employee strength,
    then consumed as salary bills are approved. Enforces department-level
    budget control even though provincial allocation is centralized.
    """
    
    department = models.ForeignKey(
        'budgeting.Department',
        on_delete=models.PROTECT,
        related_name='salary_budgets'
    )
    fiscal_year = models.ForeignKey(
        'budgeting.FiscalYear',
        on_delete=models.PROTECT,
        related_name='dept_salary_budgets'
    )
    fund = models.ForeignKey(
        Fund,
        on_delete=models.PROTECT,
        related_name='dept_salary_budgets'
    )
    global_head = models.ForeignKey(
        GlobalHead,
        on_delete=models.PROTECT,
        related_name='dept_salary_budgets',
        help_text="Salary account code (A01151, A01202, etc.)"
    )
    
    # Budget allocation
    allocated_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Initial budget allocated based on employee strength"
    )
    
    # Consumption tracking
    consumed_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount consumed through approved bills"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'budgeting_department_salary_budget'
        unique_together = ['department', 'fiscal_year', 'fund', 'global_head']
        indexes = [
            models.Index(fields=['department', 'fiscal_year']),
            models.Index(fields=['fiscal_year', 'global_head']),
        ]
    
    def __str__(self):
        return f"{self.department.name} - {self.global_head.code} - FY{self.fiscal_year.year}"
    
    @property
    def available_amount(self):
        """Calculate remaining budget"""
        return self.allocated_amount - self.consumed_amount
    
    @property
    def utilization_percentage(self):
        """Calculate budget utilization as percentage"""
        if self.allocated_amount == 0:
            return Decimal('0.00')
        return (self.consumed_amount / self.allocated_amount) * 100
    
    def can_accommodate(self, amount):
        """Check if sufficient budget available for given amount"""
        return self.available_amount >= amount
    
    def consume(self, amount):
        """
        Consume budget amount (called when bill is approved).
        Raises ValidationError if insufficient budget.
        """
        if not self.can_accommodate(amount):
            raise ValidationError(
                f"Insufficient budget in {self.department.name} for {self.global_head.code}. "
                f"Required: Rs. {amount:,.2f}, Available: Rs. {self.available_amount:,.2f}"
            )
        
        self.consumed_amount += amount
        self.save(update_fields=['consumed_amount', 'updated_at'])
    
    def release(self, amount):
        """Release budget amount (called when bill is cancelled/reversed)"""
        self.consumed_amount -= amount
        if self.consumed_amount < 0:
            self.consumed_amount = Decimal('0.00')
        self.save(update_fields=['consumed_amount', 'updated_at'])


class SalaryBillConsumption(models.Model):
    """
    Tracks which bills consumed budget from which departments.
    Enables drill-down reporting and budget reconciliation.
    """
    
    department_budget = models.ForeignKey(
        DepartmentSalaryBudget,
        on_delete=models.PROTECT,
        related_name='consumptions'
    )
    bill = models.ForeignKey(
        'expenditure.Bill',
        on_delete=models.PROTECT,
        related_name='salary_consumptions'
    )
    
    # Consumption details
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Amount consumed from this department's budget"
    )
    employee_count = models.IntegerField(
        help_text="Number of employees from this department in the bill"
    )
    
    # Status tracking
    is_reversed = models.BooleanField(
        default=False,
        help_text="True if bill was cancelled and budget released"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'budgeting_salary_bill_consumption'
        indexes = [
            models.Index(fields=['bill', 'department_budget']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Bill {self.bill.bill_number} - {self.department_budget.department.name} - Rs. {self.amount:,.2f}"
