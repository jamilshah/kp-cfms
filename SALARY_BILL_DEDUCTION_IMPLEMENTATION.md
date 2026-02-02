# Salary Bill Budget Deduction - Implementation Summary

## What Was Implemented

### 1. Budget Deduction Service (`apps/expenditure/services_salary.py`)

Added `deduct_salary_bill_budgets()` function that:
- Takes an approved salary bill
- Recreates the salary breakdown (by function × component)
- For each function's each component:
  - Finds the corresponding BudgetHead (e.g., GEN-011103-A01151)
  - Gets the BudgetAllocation
  - Validates sufficient budget is available
  - Deducts the amount from `spent_amount`
  - Saves the allocation

### 2. Bill Approval Enhancement (`apps/expenditure/models.py`)

Modified `Bill.approve()` method:
- Detects if bill is a SALARY bill (via `bill_type` field)
- Routes to `_approve_salary_bill()` for salary bills
- Continues normal process for REGULAR bills

Added `Bill._approve_salary_bill()` method:
- Calls `deduct_salary_bill_budgets()` to handle multi-function deductions
- Creates simplified GL voucher:
  - Debit: Salary Expense (A01151) for gross_amount
  - Credit: Accounts Payable (AP) for net_amount
  - Credit: Tax Payable (TAX_IT) for tax_amount (if any)
- Posts the voucher
- Updates bill status to APPROVED

## How It Works - Complete Flow

### Step 1: Bill Creation
```
User: Generate Salary Bill for February 2026
System: 
  - Calculates breakdown from BudgetEmployee records
  - 234 employees × 9 salary components = detailed breakdown
  - Validates budget availability for all function/component combinations
  - Creates bill with single line: "Monthly Salary - February 2026"
  - Bill type = 'SALARY'
  - Stores salary_month = 2, salary_year = 2026
```

### Step 2: Bill Approval
```
TMO: Approves the salary bill
System calls Bill.approve(tmo_user):
  1. Detects bill_type == 'SALARY'
  2. Calls _approve_salary_bill():
     a. Calls deduct_salary_bill_budgets():
        - Function 011103 - A01151 (Basic Pay): Rs 12,345,678
          → BudgetAllocation.spent_amount += 12,345,678
        - Function 011103 - A01202 (HRA): Rs 1,234,567
          → BudgetAllocation.spent_amount += 1,234,567
        - Function 011103 - A01203 (Conveyance): Rs 345,678
          → BudgetAllocation.spent_amount += 345,678
        ... (repeat for all ~220 function/component combinations)
     
     b. Creates GL Voucher:
        Debit:  A01151 (Salary Expense) Rs 45,234,567
        Credit: AP (Accounts Payable) Rs 45,234,567
     
     c. Sets status = APPROVED
```

### Step 3: Budget State After Approval

Each BudgetAllocation reflects the deduction:
```
Example:
BudgetAllocation: GEN-011103-A01151-00
  allocated_amount: 150,000,000
  spent_amount:      12,345,678  (increased by salary)
  available:        137,654,322

BudgetAllocation: GEN-015101-A01202-00
  allocated_amount:  10,000,000
  spent_amount:         345,678  (increased by HRA for Finance)
  available:          9,654,322
```

## Key Features

✅ **Automatic Multi-Function Deduction**: One bill approval triggers ~220 budget deductions (22 functions × ~10 components)

✅ **Budget Validation**: Checks ALL allocations before approval - fails if ANY is insufficient

✅ **Audit Trail**: Each deduction recorded in BudgetAllocation.spent_amount with timestamp

✅ **GL Integration**: Proper double-entry voucher created for accounting

✅ **Zero Manual Work**: No manual entry - everything calculated from employee records

## Error Handling

If budget is insufficient for ANY function/component:
```python
raise BudgetExceededException(
    f"Infrastructure - House Rent Allowance (A01202): "
    f"Insufficient budget. Required: Rs 2,500,000, "
    f"Available: Rs 2,300,000"
)
```

Bill approval is **atomically rolled back** - no partial deductions.

## Testing

To test the complete flow:

1. Navigate to: http://127.0.0.1:8000/expenditure/bills/
2. Click "Generate Salary Bill"
3. Select February 2026
4. Review preview (should show ~220 component deductions)
5. Click "Create Salary Bill"
6. Submit bill for verification
7. Verify bill (as Accountant)
8. Approve bill (as TMO)
9. Check BudgetAllocations - spent_amount should increase for each function's components

## Database Impact

When salary bill is approved:
- 1 Bill record updated (status → APPROVED)
- 1 Voucher created
- 3 JournalEntry records created (Debit Salary, Credit AP, Credit Tax)
- ~220 BudgetAllocation records updated (spent_amount increased)

Total: ~225 database writes per salary bill approval
