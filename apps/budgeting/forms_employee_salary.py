"""
Forms for Employee Salary Structure Management (KP Government CFMS Compliant)
"""
from django import forms
from decimal import Decimal
from apps.budgeting.models_employee import BudgetEmployee, CITY_CATEGORIES
from apps.budgeting.models import ScheduleOfEstablishment, Department, FiscalYear
from apps.finance.models import FunctionCode


class EmployeeSalaryForm(forms.ModelForm):
    """
    Form for entering/editing employee salary details (Opening Balance Snapshot Approach).
    
    Uses year-by-year ARA calculation based on frozen 2022 value and subsequent relief announcements.
    
    Fields:
    - Assignment: fiscal_year, department, function (NEW)
    - Personal: name, father_name, designation, date_of_birth, qualification, joining_date
    - Pay: bps (BPS grade), running_basic (from last pay slip)
    - Eligibility: city_category, is_govt_accommodation, is_house_hiring
    - ARA Snapshot: frozen_ara_2022_input (from last pay slip)
    - Fixed: dra_amount
    """
    
    class Meta:
        model = BudgetEmployee
        fields = [
            'fiscal_year', 'department', 'function',
            'name', 'father_name', 'designation', 'date_of_birth', 'qualification', 'joining_date',
            'bps', 'running_basic',
            'city_category', 'is_govt_accommodation', 'is_house_hiring',
            'frozen_ara_2022_input',
            'dra_amount',
            'expected_salary_increase_percentage',
            'remarks'
        ]
        widgets = {
            'fiscal_year': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'department': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'function': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full Name',
                'required': True
            }),
            'father_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Father's Name"
            }),
            'designation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Designation / Position'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'qualification': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., B.A., M.A., M.B.B.S.'
            }),
            'joining_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'bps': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
                'help_text': 'BPS Grade (1-22)'
            }),
            'running_basic': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'help_text': 'Current Running Basic from last pay slip'
            }),
            'city_category': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
                'help_text': 'City for HRA Slab Selection'
            }),
            'is_govt_accommodation': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'help_text': 'If checked, HRA = 0'
            }),
            'is_house_hiring': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'help_text': 'If checked, HRA = 0'
            }),
            'frozen_ara_2022_input': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00 (Leave blank for new entrants)',
                'step': '0.01',
                'min': '0',
                'help_text': 'ARA 2022 amount from last pay slip. Auto-calculated (15% of min basic) if blank.'
            }),
            'dra_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'help_text': 'DRA (Disparity Reduction Allowance) - fixed amount from 2017 scale'
            }),
            'expected_salary_increase_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'help_text': 'Expected salary increase % for next year budget estimates (0-100)'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes'
            })
        }


class EmployeeSalaryCSVUploadForm(forms.Form):
    """
    Form for uploading employee salary data via CSV.
    """
    schedule = forms.ModelChoiceField(
        queryset=ScheduleOfEstablishment.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        help_text='Select the schedule to import employees into'
    )
    
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv',
            'required': True
        }),
        help_text='Upload CSV file with employee data'
    )
    
    overwrite = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Check to overwrite existing employees (matched by name + BPS)'
    )


class BulkIncrementForm(forms.Form):
    """
    Form for applying bulk annual increments to Running Basic.
    """
    fiscal_year = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        help_text='Select fiscal year'
    )
    
    city_category = forms.ChoiceField(
        choices=[('', 'All Cities')] + list(CITY_CATEGORIES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        help_text='Filter by city (optional)'
    )
    
    increment_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        initial=Decimal('3.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '3.00',
            'step': '0.01',
            'min': '0'
        }),
        help_text='Increment percentage to apply (e.g., 3.00 for 3%)'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.budgeting.models import FiscalYear
        self.fields['fiscal_year'].queryset = FiscalYear.objects.filter(is_active=True)


class AutoCalculateAllowancesForm(forms.Form):
    """
    Form for auto-calculating HRA, Conveyance, and Medical allowances.
    """
    apply_hra = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Calculate HRA'
    )
    apply_conveyance = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Calculate Conveyance'
    )
    apply_medical = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Calculate Medical'
    )
