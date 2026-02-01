"""
Integration of salary budget validation into bill approval workflow.

Add this to your Bill model or workflow service:
"""

# apps/expenditure/models.py or services.py

def approve_salary_bill(bill):
    """
    Approve salary bill with budget validation and consumption.
    
    Usage in your workflow:
        from apps.budgeting.services_salary_budget import SalaryBillValidator
        
        try:
            # Validate before approval
            is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
            
            if not is_valid:
                # Show errors to user
                return {
                    'success': False,
                    'errors': errors,
                    'message': 'Bill cannot be approved due to insufficient department budgets'
                }
            
            # Approve the bill
            bill.status = 'APPROVED'
            bill.approved_at = timezone.now()
            bill.save()
            
            # Consume department budgets
            SalaryBillValidator.consume_budget_for_bill(bill)
            
            return {
                'success': True,
                'message': 'Bill approved and budgets updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'errors': [str(e)]
            }
    """
    pass


# Sample view implementation
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.expenditure.models import Bill
from apps.budgeting.services_salary_budget import SalaryBillValidator


@login_required
def approve_bill_view(request, bill_id):
    """View to approve salary bill with budget validation"""
    
    bill = get_object_or_404(Bill, id=bill_id)
    
    if request.method == 'POST':
        # Validate budget availability
        is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
        
        if not is_valid:
            # Show validation errors
            for error in errors:
                messages.error(request, error)
            
            return render(request, 'expenditure/bill_approval.html', {
                'bill': bill,
                'validation_errors': errors
            })
        
        # Proceed with approval
        try:
            bill.status = 'APPROVED'
            bill.save()
            
            # Consume budgets
            SalaryBillValidator.consume_budget_for_bill(bill)
            
            messages.success(request, 'Bill approved successfully')
            
        except Exception as e:
            messages.error(request, f'Approval failed: {str(e)}')
    
    return render(request, 'expenditure/bill_approval.html', {'bill': bill})


# Sample dashboard widget for budget alerts
from apps.budgeting.services_salary_budget import SalaryBudgetReporter
from apps.core.models import FiscalYear


@login_required
def budget_alerts_widget(request):
    """Dashboard widget showing departments nearing budget limits"""
    
    current_fy = FiscalYear.objects.get_current()
    alerts = SalaryBudgetReporter.get_budget_alerts(
        current_fy, 
        threshold_percentage=90
    )
    
    return render(request, 'dashboard/widgets/budget_alerts.html', {
        'alerts': alerts
    })
