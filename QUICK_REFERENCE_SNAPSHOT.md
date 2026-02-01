# Quick Reference: Opening Balance Snapshot Approach

## For Users/Admins

### Employee Salary Entry
1. Open Employee Salary form (Create or Edit)
2. Fill personal information (Name, Designation, etc.)
3. Select **BPS Grade** (1-22)
4. Enter **Running Basic** from last pay slip
5. Enter **Frozen ARA 2022** from last pay slip
   - If blank: System auto-calculates as 15% of minimum basic
6. Select **City Category** (Large/Other) for HRA
7. Check HRA eligibility options if applicable
8. View **Salary Breakdown** below (auto-calculated)
9. Save

### Salary Breakdown Display
The form shows:
- Running Basic (your input)
- HRA (fixed slab determined by BPS & City)
- Conveyance (fixed per BPS)
- Medical (fixed per BPS)
- DRA (your input)
- **ARA 2022** (your input OR auto-calculated)
- **ARA 2023** (automatically calculated)
- **ARA 2024** (automatically calculated)
- **ARA 2025** (automatically calculated)
- **Monthly Gross Salary** (total)
- **Annual Cost** (monthly × 12)

### Auto-Calculation Alert
If you leave "Frozen ARA 2022" blank:
- System calculates: 15% × Minimum Basic for that BPS
- Record is flagged for verification
- You'll see note: "Will auto-calculate as 15% of min BPS"

---

## For Developers

### Model (BudgetEmployee)
Location: `apps/budgeting/models_employee.py`

```python
# New fields
frozen_ara_2022_input = models.DecimalField(...)      # From last pay slip
ara_2022_auto_calculated = models.BooleanField()      # Auto-calc flag

# Calculation methods
employee.get_ara_2022()         # Frozen OR auto-calc
employee.get_ara_2023()         # 35%/30% per BPS
employee.get_ara_2024()         # 25%/20% per BPS
employee.get_ara_2025()         # 10% all BPS
employee.get_ara_total()        # Sum of all 4 years
```

### Form (EmployeeSalaryForm)
Location: `apps/budgeting/forms_employee_salary.py`

```python
# Fields in form.Meta
fields = [
    'name', 'father_name', 'designation', 'date_of_birth', 'qualification', 'joining_date',
    'bps', 'running_basic',
    'city_category', 'is_govt_accommodation', 'is_house_hiring',
    'frozen_ara_2022_input',        # NEW: Optional field
    'dra_amount',
    'remarks'
]
# REMOVED: 'ara_percentage'
```

### Template (form.html)
Location: `templates/budgeting/employee_salary/form.html`

Sections:
1. Personal Information (name, father_name, designation, etc.)
2. Pay Structure (BPS, Running Basic, City Category)
3. **ARA 2022 Snapshot** (NEW: frozen_ara_2022_input field)
4. HRA Eligibility (govt accommodation, house hiring)
5. Fixed Allowances (DRA only, ARA removed)
6. Salary Breakdown (Shows ARA 2022-2025 separately)
7. JavaScript Calculator (Real-time calculations)

### Database Migration
Location: `apps/budgeting/migrations/0020_*.py`

```sql
-- Removed
ALTER TABLE budgeting_budgetemployee DROP COLUMN ara_percentage;

-- Added
ALTER TABLE budgeting_budgetemployee 
ADD COLUMN frozen_ara_2022_input DECIMAL(10,2) NULL,
ADD COLUMN ara_2022_auto_calculated BOOLEAN DEFAULT FALSE;

-- Modified
ALTER TABLE budgeting_budgetemployee 
MODIFY COLUMN running_basic_help_text = 'From last pay slip. Basis for ARA calculations.';
```

---

## Calculation Reference

### ARA 2022
```
IF frozen_ara_2022_input > 0:
    ARA_2022 = frozen_ara_2022_input
ELSE:
    min_basic = BPSSalaryScale.objects.get(bps=employee.bps).basic_pay_min
    ARA_2022 = min_basic * 0.15
    ara_2022_auto_calculated = True
```

### ARA 2023
```
IF employee.bps IN [1..16]:
    ARA_2023 = running_basic * 0.35
ELSE:  # BPS 17-22
    ARA_2023 = running_basic * 0.30
```

### ARA 2024
```
IF employee.bps IN [1..16]:
    ARA_2024 = running_basic * 0.25
ELSE:  # BPS 17-22
    ARA_2024 = running_basic * 0.20
```

### ARA 2025
```
ARA_2025 = running_basic * 0.10  # All BPS
```

### Total ARA
```
ARA_TOTAL = ARA_2022 + ARA_2023 + ARA_2024 + ARA_2025
```

### Monthly Gross
```
GROSS = running_basic 
      + hra 
      + conveyance 
      + medical 
      + ara_total 
      + dra
```

---

## Testing

### Run All Tests
```bash
python test_ara_snapshot.py              # Individual ARA calculations
python test_snapshot_comprehensive.py    # Full system test
```

### Manual Test in Django Shell
```python
from apps.budgeting.models_employee import BudgetEmployee
from decimal import Decimal

# Create test employee
emp = BudgetEmployee(
    name="Test", bps=7, running_basic=Decimal('30000'),
    frozen_ara_2022_input=Decimal('1000'),
    city_category='LARGE'
)

# Check calculations
print(emp.get_ara_2022())    # 1000.00
print(emp.get_ara_2023())    # 10500.00 (35% × 30000)
print(emp.get_ara_2024())    # 7500.00 (25% × 30000)
print(emp.get_ara_2025())    # 3000.00 (10% × 30000)
print(emp.get_ara_total())   # 22000.00
```

---

## Common Scenarios

### Scenario 1: New Employee Joins
**Action:** HR enters employee in system
- BPS: 7
- Running Basic: 25,000 (starting salary)
- Frozen ARA 2022: (leave blank)
- **Result:** Auto-calculates ARA 2022 as 15% of min basic for BPS 7

### Scenario 2: Transfer from Another Department
**Action:** HR updates employee salary from transfer paperwork
- BPS: 10 (new posting)
- Running Basic: 45,000 (from last pay slip in old posting)
- Frozen ARA 2022: 3,500 (from last pay slip)
- **Result:** Uses all snapshot values as provided

### Scenario 3: New Relief Announcement (ARA 2025)
**Action:** Government announces new relief
- No change needed in system
- ARA 2025 is automatically calculated (10% of running basic)
- Salary breakdown updates immediately

---

## Troubleshooting

### Problem: Form won't save
**Check:**
1. Required fields filled (name, BPS, running_basic, etc.)
2. Numeric fields have valid decimal values
3. No validation errors displayed below fields

### Problem: Salary calculation shows wrong amount
**Check:**
1. BPS is correct (affects ARA percentages)
2. Running Basic matches last pay slip
3. City Category is correct (affects HRA)
4. ARA 2022 value entered matches last pay slip (or left blank for auto-calc)

### Problem: ARA seems too low/high
**Check:**
1. ARA 2023 = 35% (BPS 1-16) or 30% (BPS 17-22)
2. ARA 2024 = 25% (BPS 1-16) or 20% (BPS 17-22)
3. ARA 2025 = 10% (all BPS)
4. Running Basic used is correct

### Problem: Auto-calculated ARA 2022 is wrong
**Check:**
1. frozen_ara_2022_input field is truly empty/NULL
2. BPS is in system (check BPSSalaryScale table)
3. Calculate manually: 15% × BPS min basic

---

## Key Files

| File | Purpose | Modified |
|------|---------|----------|
| `apps/budgeting/models_employee.py` | Employee salary model with ARA methods | ✅ |
| `apps/budgeting/forms_employee_salary.py` | Form for employee salary data entry | ✅ |
| `templates/budgeting/employee_salary/form.html` | HTML form and JavaScript calculator | ✅ |
| `apps/budgeting/models.py` | BPSSalaryScale (reference data) | ❌ |
| `apps/budgeting/migrations/0020_*.py` | Database schema changes | ✅ |

---

## Status Checklist

- [x] Migration 0020 applied
- [x] Model fields updated (frozen_ara_2022_input, ara_2022_auto_calculated)
- [x] Form updated (removed ara_percentage, added frozen_ara_2022_input)
- [x] Template updated (new ARA sections, JavaScript calculator)
- [x] All ARA methods implemented and tested
- [x] Auto-calculation fallback working
- [x] System check: 0 errors
- [x] Comprehensive tests passing

---

## References

- Implementation Notes: `IMPLEMENTATION_NOTES_SNAPSHOT_APPROACH.md`
- Complete Summary: `OPENING_BALANCE_SNAPSHOT_COMPLETE.md`
- Test Scripts: `test_ara_snapshot.py`, `test_snapshot_comprehensive.py`

---

**Last Updated:** 2024
**Status:** ✅ PRODUCTION READY
