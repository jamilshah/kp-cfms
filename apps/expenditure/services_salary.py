"""
Salary Bill Generation Service

Automates monthly salary bill creation from BudgetEmployee records.
Validates budget availability and creates consolidated bills.
"""

from decimal import Decimal
from collections import defaultdict
from typing import Dict, List, Tuple
from django.db.models import Sum
from django.core.exceptions import ValidationError

from apps.budgeting.models import FiscalYear
from apps.budgeting.models_employee import BudgetEmployee
from apps.budgeting.models_employee import (
    get_hra, get_conveyance, get_medical,
    get_ara_2023, get_ara_2024, get_ara_2025
)
from apps.finance.models import BudgetHead, GlobalHead, FunctionCode


# Mapping of salary components to account codes
SALARY_COMPONENT_MAPPING = {
    'basic_pay': 'A01151',           # Basic Pay Staff
    'hra': 'A01202',                 # House Rent Allowance
    'conveyance': 'A01203',          # Conveyance Allowance
    'medical': 'A01217',             # Medical Allowance
    'ara_2022': 'A0124N',            # Disparity Reduction Allowance 2022-30%
    'ara_2023': 'A0124413',          # Adhoc Relief 2023
    'ara_2024': 'A0124415',          # Adhoc Relief 2024
    'ara_2025': 'A0125N',            # Disparity Reduction Allowance 2025 @15%
    'dra': 'A01257',                 # Disability Allowance (using for DRA)
}


class SalaryBillGenerator:
    """Generates consolidated salary bills from employee records"""
    
    def __init__(self, organization, fiscal_year, month, year):
        """
        Initialize salary bill generator.
        
        Args:
            organization: Organization instance
            fiscal_year: FiscalYear instance
            month: Month number (1-12)
            year: Year (e.g., 2026)
        """
        self.organization = organization
        self.fiscal_year = fiscal_year
        self.month = month
        self.year = year
        self.employees = None
        self.breakdown = None
    
    def get_active_employees(self):
        """Get all active (non-vacant) employees for the organization"""
        if self.employees is None:
            self.employees = BudgetEmployee.objects.filter(
                fiscal_year=self.fiscal_year,
                is_vacant=False
            ).select_related('function', 'department')
        
        return self.employees
    
    def calculate_breakdown(self) -> Dict:
        """
        Calculate salary breakdown by function and component.
        
        Returns:
            dict: {
                'total_employees': int,
                'total_amount': Decimal,
                'by_function': {
                    function_code: {
                        'function_name': str,
                        'employee_count': int,
                        'components': {
                            'basic_pay': Decimal,
                            'hra': Decimal,
                            ...
                        },
                        'total': Decimal
                    }
                },
                'by_component': {
                    'A01151': {'name': str, 'amount': Decimal, 'employees': int},
                    ...
                }
            }
        """
        if self.breakdown is not None:
            return self.breakdown
        
        employees = self.get_active_employees()
        
        # Group by function
        by_function = defaultdict(lambda: {
            'function_name': '',
            'employee_count': 0,
            'components': defaultdict(Decimal),
            'total': Decimal('0.00')
        })
        
        # Track totals by component across all functions
        by_component = defaultdict(lambda: {
            'amount': Decimal('0.00'),
            'employees': set()
        })
        
        for emp in employees:
            function = emp.function
            if not function:
                continue
            
            func_code = function.code
            by_function[func_code]['function_name'] = function.name
            by_function[func_code]['employee_count'] += 1
            
            # Calculate each component
            components = {
                'basic_pay': emp.running_basic,
                'hra': emp.get_hra(),
                'conveyance': emp.get_conveyance(),
                'medical': emp.get_medical(),
                'ara_2022': emp.get_ara_2022(),
                'ara_2023': emp.get_ara_2023(),
                'ara_2024': emp.get_ara_2024(),
                'ara_2025': emp.get_ara_2025(),
                'dra': emp.get_dra(),
            }
            
            # Add to function totals
            for comp_name, amount in components.items():
                by_function[func_code]['components'][comp_name] += amount
                by_function[func_code]['total'] += amount
                
                # Track by component
                account_code = SALARY_COMPONENT_MAPPING.get(comp_name)
                if account_code and amount > 0:
                    by_component[account_code]['amount'] += amount
                    by_component[account_code]['employees'].add(emp.id)
        
        # Convert sets to counts
        for code, data in by_component.items():
            data['employees'] = len(data['employees'])
            # Get component name
            gh = GlobalHead.objects.filter(code=code).first()
            data['name'] = gh.name if gh else code
        
        # Calculate grand total
        total_amount = sum(f['total'] for f in by_function.values())
        total_employees = employees.count()
        
        self.breakdown = {
            'total_employees': total_employees,
            'total_amount': total_amount,
            'by_function': dict(by_function),
            'by_component': dict(by_component),
        }
        
        return self.breakdown
    
    def validate_budget_availability(self) -> Tuple[bool, List[str]]:
        """
        Validate that sufficient budget is available for all salary components.
        
        Returns:
            tuple: (is_valid: bool, errors: list[str])
        """
        from apps.budgeting.models import BudgetAllocation
        
        breakdown = self.calculate_breakdown()
        errors = []
        
        # Get fund (assume GEN for now)
        from apps.finance.models import Fund
        fund = Fund.objects.filter(code='GEN').first()
        if not fund:
            errors.append("Fund 'GEN' not found")
            return False, errors
        
        # Check each function's each component
        for func_code, func_data in breakdown['by_function'].items():
            function = FunctionCode.objects.filter(code=func_code).first()
            if not function:
                errors.append(f"Function {func_code} not found")
                continue
            
            for comp_name, amount in func_data['components'].items():
                if amount <= 0:
                    continue
                
                account_code = SALARY_COMPONENT_MAPPING.get(comp_name)
                if not account_code:
                    continue
                
                # Find the budget head
                budget_head = BudgetHead.objects.filter(
                    fund=fund,
                    function=function,
                    global_head__code=account_code,
                    is_active=True
                ).first()
                
                if not budget_head:
                    errors.append(
                        f"Budget head not found: {fund.code}-{func_code}-{account_code}"
                    )
                    continue
                
                # Check allocation
                try:
                    allocation = BudgetAllocation.objects.get(
                        organization=self.organization,
                        fiscal_year=self.fiscal_year,
                        budget_head=budget_head
                    )
                    
                    available = allocation.get_available_budget()
                    if available < amount:
                        errors.append(
                            f"{function.name} - {account_code}: "
                            f"Insufficient budget. Required: Rs {amount:,.2f}, "
                            f"Available: Rs {available:,.2f}"
                        )
                
                except BudgetAllocation.DoesNotExist:
                    errors.append(
                        f"No budget allocation for {function.name} - {account_code}"
                    )
        
        return (len(errors) == 0, errors)
    
    def generate_bill_description(self) -> str:
        """Generate bill description"""
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        month_name = month_names[self.month - 1]
        return f"Monthly Salary - {month_name} {self.year}"
    
    def create_bill(self, created_by) -> 'Bill':
        """
        Create the actual bill with a single line item.
        Budget deductions will happen on approval.
        
        Args:
            created_by: User creating the bill
            
        Returns:
            Bill instance
        """
        from apps.expenditure.models import Bill
        from apps.finance.models import Fund
        
        # Validate first
        is_valid, errors = self.validate_budget_availability()
        if not is_valid:
            raise ValidationError(errors)
        
        breakdown = self.calculate_breakdown()
        fund = Fund.objects.filter(code='GEN').first()
        
        # Create bill
        bill = Bill.objects.create(
            organization=self.organization,
            fiscal_year=self.fiscal_year,
            fund=fund,
            bill_type='SALARY',  # We'll need to add this choice
            description=self.generate_bill_description(),
            gross_amount=breakdown['total_amount'],
            tax_amount=Decimal('0.00'),
            net_amount=breakdown['total_amount'],
            created_by=created_by,
            status='DRAFT'
        )
        
        # Store salary metadata for later deduction
        bill.salary_month = self.month
        bill.salary_year = self.year
        bill.save()
        
        return bill


def deduct_salary_bill_budgets(bill, user):
    """
    Deduct budgets for a salary bill across all function/component combinations.
    
    This is called when a salary bill is approved. It deducts the calculated
    salary amounts from each function's salary component budget allocations.
    
    Args:
        bill: Approved salary bill
        user: User approving the bill
        
    Returns:
        int: Number of deductions made
    """
    from apps.budgeting.models import BudgetAllocation
    from apps.finance.models import BudgetHead, FunctionCode
    
    if bill.bill_type != 'SALARY':
        raise ValidationError("This function only handles SALARY bills")
    
    if not bill.salary_month or not bill.salary_year:
        raise ValidationError("Salary bill missing month/year information")
    
    # Recreate the generator to get breakdown
    generator = SalaryBillGenerator(
        bill.organization,
        bill.fiscal_year,
        bill.salary_month,
        bill.salary_year
    )
    
    breakdown = generator.calculate_breakdown()
    deduction_count = 0
    
    # Process each function's each component
    for func_code, func_data in breakdown['by_function'].items():
        function = FunctionCode.objects.filter(code=func_code).first()
        if not function:
            continue
        
        for comp_name, amount in func_data['components'].items():
            if amount <= 0:
                continue
            
            account_code = SALARY_COMPONENT_MAPPING.get(comp_name)
            if not account_code:
                continue
            
            # Find the budget head
            budget_head = BudgetHead.objects.filter(
                fund=bill.fund,
                function=function,
                global_head__code=account_code,
                is_active=True
            ).first()
            
            if not budget_head:
                raise ValidationError(
                    f"Budget head not found: {bill.fund.code}-{func_code}-{account_code}"
                )
            
            # Get or create allocation
            try:
                allocation = BudgetAllocation.objects.get(
                    organization=bill.organization,
                    fiscal_year=bill.fiscal_year,
                    budget_head=budget_head
                )
                
                # Check if we can spend
                if not allocation.can_spend(amount):
                    available = allocation.get_available_budget()
                    raise ValidationError(
                        f"Insufficient budget for {function.name} - {account_code}. "
                        f"Required: Rs {amount:,.2f}, Available: Rs {available:,.2f}"
                    )
                
                # Deduct
                allocation.spent_amount += amount
                allocation.save(update_fields=['spent_amount', 'updated_at'])
                deduction_count += 1
                
            except BudgetAllocation.DoesNotExist:
                raise ValidationError(
                    f"No budget allocation for {function.name} - {account_code}"
                )
    
    return deduction_count

