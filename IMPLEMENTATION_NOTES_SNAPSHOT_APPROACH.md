# Opening Balance Snapshot Approach - Implementation Complete

## Overview
The salary calculation system has been successfully refactored to use the "Opening Balance Snapshot Approach" instead of historical increment-based calculations.

## What Changed

### Database Schema (Migration 0020)
- **Removed:** `ara_percentage` field (no longer needed)
- **Added:** `frozen_ara_2022_input` (DecimalField) - stores ARA 2022 from last pay slip
- **Added:** `ara_2022_auto_calculated` (BooleanField) - flag for verification when auto-calculated

### Model Methods (BudgetEmployee)
New year-by-year ARA calculation methods:

```python
get_ara_2022()    # Frozen from last slip OR auto-calc 15% of min basic (sets flag)
get_ara_2023()    # 35% (BPS 1-16) or 30% (BPS 17-22) of Running Basic
get_ara_2024()    # 25% (BPS 1-16) or 20% (BPS 17-22) of Running Basic
get_ara_2025()    # 10% (all BPS) of Running Basic
get_ara_total()   # Sum of ARA 2022 + 2023 + 2024 + 2025
```

### Form Updates
- Removed `ara_percentage` field
- Added `frozen_ara_2022_input` field with helpful guidance
- Form label: "ARA 2022 amount from last pay slip"
- Help text: "If left blank, will auto-calculate as 15% of min BPS"

### Template Updates (form.html)
- New section: "ARA 2022 Snapshot (From Last Pay Slip)"
- Updated salary breakdown to show year-by-year ARA breakdown
- New JavaScript functions for calculating ARA 2023, 2024, 2025
- Real-time calculation showing:
  - Running Basic
  - HRA (fixed slab)
  - Conveyance (fixed per BPS)
  - Medical (fixed per BPS)
  - DRA (fixed)
  - **ARA 2022-2025 (separate line items)**
  - Monthly Gross Salary
  - Annual Cost

### Quick Guide Update
Updated sidebar to explain the Opening Balance approach with year-by-year ARA breakdown.

## Calculation Logic

### ARA 2022 (Snapshot from Last Pay Slip)
```
If frozen_ara_2022_input > 0:
    Use the value from last pay slip
Else:
    Auto-calculate as: 15% × Minimum Basic for this BPS
    Set ara_2022_auto_calculated = True (for verification)
```

### ARA 2023
```
BPS 1-16:  35% of Running Basic
BPS 17-22: 30% of Running Basic
```

### ARA 2024
```
BPS 1-16:  25% of Running Basic
BPS 17-22: 20% of Running Basic
```

### ARA 2025
```
All BPS: 10% of Running Basic
```

### Monthly Gross Salary
```
Running Basic
  + HRA (fixed slab by BPS & City)
  + Conveyance (fixed per BPS)
  + Medical (fixed per BPS)
  + ARA 2022 (frozen)
  + ARA 2023 (percentage-based)
  + ARA 2024 (percentage-based)
  + ARA 2025 (percentage-based)
  + DRA (fixed)
```

## Test Results

All calculations verified with three test cases:

### Test Case 1: Existing Employee with Frozen ARA 2022
- BPS: 7 | Running Basic: 30,773 | Frozen ARA 2022: 1,000
- ARA 2023: 10,770.55 (35%)
- ARA 2024: 7,693.25 (25%)
- ARA 2025: 3,077.30 (10%)
- **Total ARA: 22,541.10**

### Test Case 2: New Entrant (Auto-Calculated ARA 2022)
- BPS: 7 | Running Basic: 20,000 | Frozen ARA 2022: NULL
- ARA 2022 (Auto): 4,609.95 (15% of min 30,733)
- ARA 2023: 7,000.00 (35%)
- ARA 2024: 5,000.00 (25%)
- ARA 2025: 2,000.00 (10%)
- **Total ARA: 18,609.95**

### Test Case 3: Senior Officer (BPS 20)
- BPS: 20 | Running Basic: 80,000 | Frozen ARA 2022: 5,000
- ARA 2023: 24,000.00 (30% for BPS 17-22)
- ARA 2024: 16,000.00 (20% for BPS 17-22)
- ARA 2025: 8,000.00 (10%)
- **Total ARA: 53,000.00**

## System Status

✅ Migration 0020 applied successfully
✅ System check: 0 errors
✅ All ARA calculation methods tested and verified
✅ Form updated with new frozen_ara_2022_input field
✅ Template updated with year-by-year ARA display
✅ JavaScript calculator updated for snapshot approach

## Next Steps

1. **Test Form Creation/Editing**
   - Navigate to Employee Salary list
   - Create a new employee or edit existing
   - Verify frozen_ara_2022_input field appears
   - Test salary breakdown calculations

2. **Data Migration (Optional)**
   - For existing employees, populate frozen_ara_2022_input from last pay slip
   - Can be done via management command or admin interface

3. **Admin Enhancements (Optional)**
   - Add ara_2022_auto_calculated to list_display in admin
   - Filter records with auto-calculated values for verification
   - Color-code or highlight records needing review

4. **Documentation**
   - Update user guide with Opening Balance approach
   - Provide examples with actual salary numbers
   - Explain when auto-calculation triggers (new entrants)

## Files Modified

1. `apps/budgeting/models_employee.py` - ARA methods refactored
2. `apps/budgeting/forms_employee_salary.py` - Form field updated
3. `apps/budgeting/migrations/0020_*.py` - Database schema changes
4. `templates/budgeting/employee_salary/form.html` - Form and calculations UI

## Example: Real Salary Calculation

**Employee: Nasir Ahmad**
- BPS: 7 (Federal Government - KP)
- Running Basic (from June 2024 slip): 32,000.00
- City Category: Other Cities
- Frozen ARA 2022 (from last slip): 1,200.00

**Calculated:**
- HRA: 2,000.00 (fixed for BPS 7, Other Cities)
- Conveyance: 1,500.00 (fixed for BPS 7)
- Medical: 1,500.00 (fixed for BPS 7)
- DRA: 500.00 (fixed)
- ARA 2022: 1,200.00 (from pay slip)
- ARA 2023: 11,200.00 (35% × 32,000)
- ARA 2024: 8,000.00 (25% × 32,000)
- ARA 2025: 3,200.00 (10% × 32,000)

**Monthly Gross Salary:**
32,000 + 2,000 + 1,500 + 1,500 + 500 + 1,200 + 11,200 + 8,000 + 3,200 = **61,100.00**

**Annual Cost:** 61,100 × 12 = **733,200.00**

---

This implementation follows KP Government CFMS standards for salary calculation with the Opening Balance snapshot approach, supporting both existing employees with frozen ARA 2022 values and new entrants with auto-calculated fallback.
