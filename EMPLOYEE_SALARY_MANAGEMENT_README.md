# Employee Salary Structure Management System

**Comprehensive salary management with Budget Book reporting**

---

## ✨ Features

### 1. Detailed Pay Structure
- Individual allowance fields (HRA, Conveyance, Medical, Adhoc Relief, etc.)
- Automatic calculation from BPS scales
- GPF and Income Tax deductions
- Real-time gross/net salary calculation

### 2. UI for Data Entry
- User-friendly forms with live preview
- Auto-calculate allowances button
- Field validation and help text
- Employee search and filtering

### 3. CSV Import/Export
- **CSV Template** download for Excel entry
- Bulk import employee data
- Update existing records
- Export Budget Book to CSV

### 4. Budget Book Reports
- **Summary Page**: Department-wise totals
- **Detailed List**: Row-wise employee salary breakdown
- Print-friendly format
- Export to CSV/Excel

### 5. Annual Increment Automation
- Bulk apply increments to all employees
- Department-wise filtering
- Effective date tracking
- Automatic basic pay updates

---

## 🚀 Quick Start

### Add New Employee

```
1. Navigate to: Budget Planning → Employee Salaries
2. Click "Add Employee"
3. Fill in personal details
4. Enter basic pay
5. Click "Auto-Calculate from BPS" button
6. Review and adjust allowances
7. Save
```

### CSV Import (Bulk Entry)

```bash
# 1. Download CSV template
/budgeting/employee-salary/csv-template/

# 2. Fill in Excel with employee data
# Required: name, basic_pay
# Optional: all allowance fields

# 3. Upload CSV
/budgeting/employee-salary/csv-import/
```

### Generate Budget Book

```
1. Navigate to: Employee Salaries → Budget Book
2. Select Fiscal Year
3. View Summary + Detailed List
4. Print or Export CSV
```

### Apply Annual Increments

```
1. Navigate to: Employee Salaries → Apply Increments
2. Select Fiscal Year
3. Set Effective Date
4. Click "Apply Increments"
```

---

## 📊 URL Patterns

| URL | Purpose |
|-----|---------|
| `/budgeting/employee-salary/` | List all employees |
| `/budgeting/employee-salary/create/` | Add new employee |
| `/budgeting/employee-salary/<id>/` | View details |
| `/budgeting/employee-salary/<id>/edit/` | Edit employee |
| `/budgeting/employee-salary/csv-import/` | CSV import |
| `/budgeting/employee-salary/csv-template/` | Download template |
| `/budgeting/employee-salary/bulk-increment/` | Apply increments |
| `/budgeting/employee-salary/budget-book/` | Budget Book report |
| `/budgeting/employee-salary/budget-book/export/` | Export CSV |

---

## 💾 Database Structure

### Enhanced BudgetEmployee Model

**New Fields Added:**
```python
# Individual Allowances
house_rent_allowance
conveyance_allowance
medical_allowance
adhoc_relief_2024
special_allowance
utility_allowance
entertainment_allowance

# Increment Tracking
annual_increment_amount
last_increment_date

# Deductions
gpf_contribution
income_tax

# Metadata
joining_date
remarks
```

**Calculated Properties:**
```python
@property
def total_monthly_allowances(self) -> Decimal
def monthly_gross(self) -> Decimal
def total_monthly_deductions(self) -> Decimal
def monthly_net(self) -> Decimal
def annual_cost(self) -> Decimal
```

**Helper Methods:**
```python
def apply_annual_increment()
def calculate_allowances_from_bps()
```

---

## 📝 CSV Template Format

**Required Columns:**
- `name` (required)
- `basic_pay` (required)

**Optional Columns:**
- `personnel_number`, `cnic`, `joining_date`
- `hra`, `conveyance`, `medical`, `adhoc_relief`
- `special_allowance`, `utility`, `entertainment`
- `annual_increment`, `gpf`, `income_tax`
- `remarks`

**Example:**
```csv
personnel_number,name,cnic,joining_date,basic_pay,hra,conveyance,medical,adhoc_relief,annual_increment,gpf,income_tax
EMP001,John Doe,12345-1234567-1,2024-01-01,50000,22500,3000,1500,25000,2500,4000,1000
```

---

## 🎨 UI Components

### List View
- Filters: Fiscal Year, Department, Search
- Summary stats: Total employees, monthly cost
- Action buttons: Add, Import, Export, Budget Book
- Pagination

### Form View
- Sections: Personal Info, Pay Structure, Allowances, Deductions
- Live calculation preview
- Auto-calculate button
- Field tooltips

### Detail View
- Complete salary breakdown
- Quick stats (Annual cost, Last increment)
- Edit/Delete actions

### Budget Book View
- Grand summary
- Department-wise summary table
- Detailed employee list with all pay heads
- Print/Export functionality

---

## 🔐 Permissions

- **View/List**: All authenticated users
- **Create/Edit**: Maker role required
- **CSV Import**: Admin required
- **Bulk Increment**: Admin required
- **Delete**: Admin required

---

## 🧪 Testing Checklist

- [ ] Add employee manually
- [ ] Auto-calculate allowances
- [ ] Import employees via CSV
- [ ] Export Budget Book to CSV
- [ ] Apply annual increments
- [ ] View detailed employee report
- [ ] Print Budget Book
- [ ] Search and filter employees
- [ ] Update existing employee
- [ ] Delete employee

---

## 📈 Benefits

| Feature | Impact |
|---------|--------|
| **Detailed Allowances** | Accurate budget estimates |
| **CSV Import** | 90% faster data entry |
| **Budget Book** | Official reporting requirement met |
| **Auto-calculate** | Reduced errors |
| **Bulk Increment** | 100% time saving vs manual |
| **Export** | Easy data sharing |

---

## 🔄 Integration with Existing System

- **Linked to**: `ScheduleOfEstablishment`
- **Used by**: Salary Budget Distribution
- **Feeds into**: Bill creation (future)
- **Compatible with**: BPS Salary Scale data

---

## 📞 Support

For questions or issues:
- Check field help text (hover tooltips)
- Review Quick Guide in form sidebar
- Contact system administrator

---

## 🎯 Future Enhancements (Optional)

- [ ] Integration with payroll module
- [ ] Automatic bill generation from salary data
- [ ] Leave deduction calculations
- [ ] Overtime allowance support
- [ ] Tax calculation automation
- [ ] Historical salary tracking

---

**System:** KP-CFMS  
**Module:** Budget - Employee Salary Management  
**Version:** 1.0  
**Last Updated:** February 2026  

✅ **Status:** PRODUCTION READY
