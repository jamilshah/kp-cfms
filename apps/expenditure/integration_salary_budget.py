"""
Integration code for salary budget validation in bill approval workflow

Add this to your bill approval view (apps/expenditure/views.py or similar)
"""

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone

from apps.expenditure.models import Bill
from apps.budgeting.services_salary_budget import SalaryBillValidator


@login_required
def approve_salary_bill(request, bill_id):
    """
    Approve salary bill with budget validation
    
    This view demonstrates how to integrate budget validation
    into your existing bill approval workflow.
    """
    
    bill = get_object_or_404(Bill, id=bill_id)
    
    # Check permissions
    if not request.user.has_perm('expenditure.can_approve_bill'):
        messages.error(request, "You don't have permission to approve bills")
        return redirect('expenditure:bill_detail', pk=bill_id)
    
    # Check if bill is in correct status
    if bill.status != 'SUBMITTED':
        messages.warning(request, "Bill can only be approved from SUBMITTED status")
        return redirect('expenditure:bill_detail', pk=bill_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'validate':
            # HTMX validation request
            is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
            
            return render(request, 'budgeting/salary_budget/widgets/bill_validation.html', {
                'bill': bill,
                'is_valid': is_valid,
                'errors': errors
            })
        
        elif action == 'approve':
            # Actual approval
            try:
                with transaction.atomic():
                    # Validate budget first
                    is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
                    
                    if not is_valid:
                        for error in errors:
                            messages.error(request, error)
                        return redirect('expenditure:bill_detail', pk=bill_id)
                    
                    # Update bill status
                    bill.status = 'APPROVED'
                    bill.approved_by = request.user
                    bill.approved_at = timezone.now()
                    bill.save()
                    
                    # Consume department budgets
                    SalaryBillValidator.consume_budget_for_bill(bill)
                    
                    messages.success(request, f"Bill {bill.bill_number} approved successfully")
                    return redirect('expenditure:bill_list')
                    
            except Exception as e:
                messages.error(request, f"Approval failed: {str(e)}")
                return redirect('expenditure:bill_detail', pk=bill_id)
    
    # GET request - show approval form
    return render(request, 'expenditure/bill_approve.html', {
        'bill': bill
    })


@login_required
def cancel_salary_bill(request, bill_id):
    """
    Cancel/reverse approved salary bill and release budgets
    """
    
    bill = get_object_or_404(Bill, id=bill_id)
    
    if not request.user.has_perm('expenditure.can_cancel_bill'):
        messages.error(request, "You don't have permission to cancel bills")
        return redirect('expenditure:bill_detail', pk=bill_id)
    
    if bill.status != 'APPROVED':
        messages.warning(request, "Only approved bills can be cancelled")
        return redirect('expenditure:bill_detail', pk=bill_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Release department budgets
                SalaryBillValidator.release_budget_for_bill(bill)
                
                # Update bill status
                bill.status = 'CANCELLED'
                bill.cancelled_by = request.user
                bill.cancelled_at = timezone.now()
                bill.cancellation_reason = request.POST.get('reason', '')
                bill.save()
                
                messages.success(request, f"Bill {bill.bill_number} cancelled and budgets released")
                return redirect('expenditure:bill_list')
                
        except Exception as e:
            messages.error(request, f"Cancellation failed: {str(e)}")
    
    return render(request, 'expenditure/bill_cancel.html', {'bill': bill})


# Example: Add budget validation widget to existing bill detail template
"""
In your templates/expenditure/bill_detail.html, add:

{% if bill.status == 'SUBMITTED' and perms.expenditure.can_approve_bill %}
<div class="card mt-3">
    <div class="card-header bg-warning">
        <h5 class="mb-0">Budget Validation</h5>
    </div>
    <div class="card-body">
        <button 
            hx-post="{% url 'budgeting:validate_bill_budget' %}"
            hx-vals='{"bill_id": "{{ bill.id }}"}'
            hx-target="#validation-result"
            hx-indicator="#validation-spinner"
            class="btn btn-primary">
            <span id="validation-spinner" class="spinner-border spinner-border-sm d-none"></span>
            Validate Budget Availability
        </button>
        
        <div id="validation-result" class="mt-3"></div>
    </div>
</div>
{% endif %}
"""
