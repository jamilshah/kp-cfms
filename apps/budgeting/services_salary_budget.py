"""
Salary Budget Distribution and Validation Services

Handles:
1. Initial budget distribution among departments based on employee strength
2. Pre-approval validation of salary bills
3. Budget consumption tracking
4. Budget reconciliation and reporting
"""

from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.budgeting.models_salary_budget import DepartmentSalaryBudget, SalaryBillConsumption
from apps.budgeting.models_employee import BudgetEmployee
from apps.finance.models import GlobalHead

def get_department_model():
    """Lazy import to avoid circular dependency"""
    from apps.budgeting.models import Department
    return Department


class SalaryBudgetDistributor:
    """Distributes centralized salary budget among departments"""
    
    @staticmethod
    def distribute_budget(fiscal_year, fund, global_head, total_budget):
        """
        Distribute total budget among departments based on employee strength.
        
        Args:
            fiscal_year: FiscalYear instance
            fund: Fund instance
            global_head: GlobalHead instance (salary code like A01151)
            total_budget: Decimal - Total budget amount to distribute
            
        Returns:
            dict: {department: allocated_amount}
        """
        
        # Get employee count per department
        dept_counts = {}
        total_employees = 0
        
        Department = get_department_model()
        for dept in Department.objects.filter(is_active=True):
            count = BudgetEmployee.objects.filter(
                schedule__department=dept.name,
                schedule__fiscal_year=fiscal_year,
                is_vacant=False
            ).count()
            
            if count > 0:
                dept_counts[dept] = count
                total_employees += count
        
        if total_employees == 0:
            raise ValidationError("No active employees found for budget distribution")
        
        # Calculate proportional allocation
        allocations = {}
        allocated_sum = Decimal('0.00')
        
        departments = sorted(dept_counts.keys(), key=lambda d: dept_counts[d], reverse=True)
        
        for i, dept in enumerate(departments):
            if i == len(departments) - 1:
                # Last department gets remainder to handle rounding
                allocation = total_budget - allocated_sum
            else:
                proportion = Decimal(dept_counts[dept]) / Decimal(total_employees)
                allocation = (total_budget * proportion).quantize(Decimal('0.01'))
            
            allocations[dept] = allocation
            allocated_sum += allocation
        
        return allocations
    
    @staticmethod
    @transaction.atomic
    def create_department_budgets(fiscal_year, fund, global_head, total_budget):
        """
        Create DepartmentSalaryBudget records for all departments.
        
        Args:
            fiscal_year: FiscalYear instance
            fund: Fund instance
            global_head: GlobalHead instance
            total_budget: Decimal
            
        Returns:
            list: Created DepartmentSalaryBudget instances
        """
        
        allocations = SalaryBudgetDistributor.distribute_budget(
            fiscal_year, fund, global_head, total_budget
        )
        
        created_budgets = []
        
        for dept, amount in allocations.items():
            budget, created = DepartmentSalaryBudget.objects.update_or_create(
                department=dept,
                fiscal_year=fiscal_year,
                fund=fund,
                global_head=global_head,
                defaults={'allocated_amount': amount}
            )
            created_budgets.append(budget)
        
        return created_budgets


class SalaryBillValidator:
    """Validates salary bills against department budgets"""
    
    @staticmethod
    def validate_bill_against_budget(bill):
        """
        Validate if departments have sufficient budget for bill.
        
        Args:
            bill: Bill instance with bill_lines loaded
            
        Returns:
            tuple: (is_valid: bool, errors: list[str])
        """
        
        errors = []
        
        # Group bill lines by department
        dept_amounts = {}
        
        from apps.budgeting.models import Department as DeptModel

        for line in bill.bill_lines.all():
            if not hasattr(line, 'employee') or not line.employee:
                errors.append(f"Bill line {line.id} has no employee assigned")
                continue

            # ScheduleOfEstablishment stores department as a string field.
            dept_name = getattr(line.employee.schedule, 'department', None)
            if not dept_name:
                errors.append(f"Bill line {line.id} employee has no schedule department")
                continue

            dept = DeptModel.objects.filter(name=dept_name).first()
            if not dept:
                errors.append(f"Department '{dept_name}' not found for bill line {line.id}")
                continue

            account_code = line.budget_head.global_head
            
            key = (dept, account_code)
            if key not in dept_amounts:
                dept_amounts[key] = {
                    'department': dept,
                    'global_head': account_code,
                    'amount': Decimal('0.00'),
                    'employees': 0
                }
            
            dept_amounts[key]['amount'] += line.gross_amount
            dept_amounts[key]['employees'] += 1
        
        # Check each department's budget
        for key, data in dept_amounts.items():
            dept = data['department']
            global_head = data['global_head']
            amount = data['amount']
            
            try:
                dept_budget = DepartmentSalaryBudget.objects.get(
                    department=dept,
                    fiscal_year=bill.fiscal_year,
                    fund=bill.fund,
                    global_head=global_head
                )
                
                if not dept_budget.can_accommodate(amount):
                    errors.append(
                        f"{dept.name} has insufficient budget for {global_head.code}. "
                        f"Required: Rs. {amount:,.2f}, Available: Rs. {dept_budget.available_amount:,.2f}"
                    )
            
            except DepartmentSalaryBudget.DoesNotExist:
                errors.append(
                    f"No salary budget found for {dept.name} - {global_head.code}"
                )
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    @transaction.atomic
    def consume_budget_for_bill(bill):
        """
        Consume department budgets when bill is approved.
        
        Args:
            bill: Approved Bill instance
        """
        
        # Validate first
        is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
        if not is_valid:
            raise ValidationError(errors)
        
        # Group by department and account
        dept_amounts = {}
        
        for line in bill.bill_lines.all():
            dept = line.employee.schedule.function.department
            account_code = line.budget_head.global_head
            
            key = (dept, account_code)
            if key not in dept_amounts:
                dept_amounts[key] = {
                    'amount': Decimal('0.00'),
                    'employees': 0
                }
            
            dept_amounts[key]['amount'] += line.gross_amount
            dept_amounts[key]['employees'] += 1
        
        # Consume budgets and create consumption records
        for (dept, global_head), data in dept_amounts.items():
            dept_budget = DepartmentSalaryBudget.objects.get(
                department=dept,
                fiscal_year=bill.fiscal_year,
                fund=bill.fund,
                global_head=global_head
            )
            
            # Consume budget
            dept_budget.consume(data['amount'])
            
            # Create consumption record
            SalaryBillConsumption.objects.create(
                department_budget=dept_budget,
                bill=bill,
                amount=data['amount'],
                employee_count=data['employees']
            )
    
    @staticmethod
    @transaction.atomic
    def release_budget_for_bill(bill):
        """
        Release department budgets when bill is cancelled/reversed.
        
        Args:
            bill: Bill instance to reverse
        """
        
        consumptions = SalaryBillConsumption.objects.filter(
            bill=bill,
            is_reversed=False
        )
        
        for consumption in consumptions:
            consumption.department_budget.release(consumption.amount)
            consumption.is_reversed = True
            consumption.save(update_fields=['is_reversed'])


class SalaryBudgetReporter:
    """Generate salary budget reports and alerts"""
    
    @staticmethod
    def get_department_budget_status(fiscal_year, department=None):
        """
        Get current budget status for departments.
        
        Args:
            fiscal_year: FiscalYear instance
            department: Optional Department to filter
            
        Returns:
            QuerySet of DepartmentSalaryBudget with annotations
        """
        
        qs = DepartmentSalaryBudget.objects.filter(
            fiscal_year=fiscal_year
        ).select_related('department', 'global_head', 'fund')
        
        if department:
            qs = qs.filter(department=department)
        
        return qs.order_by('department__name', 'global_head__code')
    
    @staticmethod
    def get_budget_alerts(fiscal_year, threshold_percentage=90):
        """
        Get departments approaching budget limit.
        
        Args:
            fiscal_year: FiscalYear instance
            threshold_percentage: Alert threshold (default 90%)
            
        Returns:
            list: Departments exceeding threshold
        """
        
        alerts = []
        
        budgets = DepartmentSalaryBudget.objects.filter(
            fiscal_year=fiscal_year
        ).select_related('department', 'global_head')
        
        for budget in budgets:
            if budget.utilization_percentage >= threshold_percentage:
                alerts.append({
                    'department': budget.department,
                    'account': budget.global_head,
                    'utilization': budget.utilization_percentage,
                    'available': budget.available_amount,
                    'allocated': budget.allocated_amount
                })
        
        return sorted(alerts, key=lambda x: x['utilization'], reverse=True)
