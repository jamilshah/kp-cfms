"""
QUICK START: Salary Budget Management System
=============================================

Follow these steps to get the system running in 15 minutes.
"""

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           SALARY BUDGET MANAGEMENT SYSTEM - QUICK START GUIDE                ║
║                                                                              ║
║                        KP-CFMS v4.0 - February 2026                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

STEP 1: Setup Database (2 minutes)
───────────────────────────────────────────────────────────────────────────────

Run these commands:

    python manage.py makemigrations budgeting
    python manage.py migrate

Expected output:
    ✓ Creating table budgeting_department_salary_budget
    ✓ Creating table budgeting_salary_bill_consumption


STEP 2: Verify Prerequisites (1 minute)
───────────────────────────────────────────────────────────────────────────────

Check you have:
    □ Chart of Accounts imported (GlobalHeads exist)
    □ Departments created and active
    □ Employees assigned to functions
    □ Current fiscal year set

Quick check:
    python manage.py shell
    >>> from apps.finance.models import GlobalHead
    >>> from apps.core.models import Department
    >>> from apps.budgeting.models_employee import BudgetEmployee
    >>> print(f"GlobalHeads: {GlobalHead.objects.count()}")
    >>> print(f"Departments: {Department.objects.filter(is_active=True).count()}")
    >>> print(f"Employees: {BudgetEmployee.objects.filter(is_vacant=False).count()}")


STEP 3: Distribute Your First Budget (5 minutes)
───────────────────────────────────────────────────────────────────────────────

Option A: Web Interface
    1. Open browser: http://localhost:8000/budgeting/salary-budget/
    2. Click "Distribute New Budget"
    3. Fill form:
       - Fiscal Year: 2025-26
       - Fund: GEN
       - Account: A01151 (Basic Pay)
       - Amount: 942657799
    4. Click "Distribute Budget"

Option B: Command Line
    python manage.py distribute_salary_budget \\
        --fy=2025-26 \\
        --fund=GEN \\
        --account=A01151 \\
        --amount=942657799

Example output:
    ════════════════════════════════════════════════════════════════
    Department                    Employees      Allocation        %
    ────────────────────────────────────────────────────────────────
    Administration                      200   Rs. 200,000,000   21%
    Finance                              50   Rs.  50,000,000    5%
    Infrastructure                      400   Rs. 400,000,000   43%
    Planning                            150   Rs. 150,000,000   16%
    Regulations                         142   Rs. 142,657,799   15%
    ────────────────────────────────────────────────────────────────
    TOTAL                               942   Rs. 942,657,799  100%
    
    ✓ Created 5 DepartmentSalaryBudget records


STEP 4: View Dashboard (1 minute)
───────────────────────────────────────────────────────────────────────────────

Navigate to: http://localhost:8000/budgeting/salary-budget/

You should see:
    ✓ Summary cards showing total allocated/consumed/available
    ✓ Department-wise budget breakdown
    ✓ Utilization percentages
    ✓ Color-coded status (green/yellow/red)


STEP 5: Test Bill Validation (5 minutes)
───────────────────────────────────────────────────────────────────────────────

Create a test bill:
    1. Go to Expenditure > Bills > Create Bill
    2. Add bill lines for employees from different departments
    3. Submit for approval

Validate budget:
    from apps.expenditure.models import Bill
    from apps.budgeting.services_salary_budget import SalaryBillValidator
    
    bill = Bill.objects.get(bill_number="TEST-001")
    is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
    
    if is_valid:
        print("✓ Budget validation passed - bill can be approved")
    else:
        print("✗ Budget validation failed:")
        for error in errors:
            print(f"  - {error}")


STEP 6: Integrate with Bill Approval (1 minute)
───────────────────────────────────────────────────────────────────────────────

Add to your bill approval view (apps/expenditure/views.py):

    from apps.budgeting.services_salary_budget import SalaryBillValidator
    
    # Before approval
    is_valid, errors = SalaryBillValidator.validate_bill_against_budget(bill)
    if not is_valid:
        for error in errors:
            messages.error(request, error)
        return redirect('expenditure:bill_detail', pk=bill.id)
    
    # After approval
    bill.status = 'APPROVED'
    bill.save()
    SalaryBillValidator.consume_budget_for_bill(bill)


═══════════════════════════════════════════════════════════════════════════════
                              THAT'S IT! 🎉
═══════════════════════════════════════════════════════════════════════════════

You now have:
    ✓ Budget distributed among departments
    ✓ Real-time monitoring dashboard
    ✓ Automatic bill validation
    ✓ Budget consumption tracking
    ✓ Alert system for overruns


NEXT STEPS:
───────────────────────────────────────────────────────────────────────────────

1. Distribute budget for other salary codes:
   - A01202 (House Rent)
   - A01203 (Conveyance)
   - A01217 (Medical)
   - etc.

2. Train users:
   - Finance Officers: Budget distribution
   - Department Heads: Monitoring
   - Approvers: Validation workflow

3. Monitor for 1 month:
   - Check utilization weekly
   - Review alerts
   - Adjust thresholds if needed

4. Generate reports:
   - Export CSV monthly
   - Compare with manual records
   - Fine-tune allocations


TROUBLESHOOTING:
───────────────────────────────────────────────────────────────────────────────

Issue: "No active employees found"
Fix: Assign employees to functions via Schedule of Establishment

Issue: "GlobalHead not found"
Fix: Import Chart of Accounts first using import_coa command

Issue: "Division by zero"
Fix: Ensure at least one employee in at least one department

Issue: Dashboard shows empty
Fix: Run budget distribution command first


DOCUMENTATION:
───────────────────────────────────────────────────────────────────────────────

📖 Full User Guide: docs/SALARY_BUDGET_USER_GUIDE.md
📋 Implementation Guide: docs/SALARY_BUDGET_IMPLEMENTATION_GUIDE.md
✅ Checklist: docs/SALARY_BUDGET_CHECKLIST.md


SUPPORT:
───────────────────────────────────────────────────────────────────────────────

Questions? Contact:
    Email: support@kp-cfms.gov.pk
    Phone: +92-91-XXXXXXX
    Docs: https://docs.kp-cfms.gov.pk


═══════════════════════════════════════════════════════════════════════════════
                    System Ready for Production Use! 🚀
═══════════════════════════════════════════════════════════════════════════════
""")
