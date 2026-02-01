"""
Forms for salary budget distribution and management
"""
from django import forms
from decimal import Decimal
from apps.budgeting.models import FiscalYear, Department
from apps.finance.models import Fund, GlobalHead


class SalaryBudgetDistributionForm(forms.Form):
    """Form for distributing salary budget among departments"""
    
    fiscal_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.all(),
        label="Fiscal Year",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    fund = forms.ModelChoiceField(
        queryset=Fund.objects.all(),
        label="Fund",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    account_code = forms.ModelChoiceField(
        queryset=GlobalHead.objects.filter(
            code__startswith='A'
        ).order_by('code'),
        label="Account Code",
        help_text="Select salary account code (A01151, A01202, etc.)",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    total_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Total Budget Amount",
        help_text="Enter total budget allocation from provincial letter",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'required': True
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default fiscal year to current (use is_active flag)
        current_fy = FiscalYear.objects.filter(is_active=True).first()
        if current_fy:
            self.fields['fiscal_year'].initial = current_fy


class BudgetAllocationAdjustmentForm(forms.Form):
    """Form for manually adjusting department allocations"""
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        label="Department",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    adjustment_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        label="Adjustment Amount",
        help_text="Enter positive for increase, negative for decrease",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'required': True
        })
    )
    
    reason = forms.CharField(
        max_length=500,
        label="Reason for Adjustment",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Explain why this adjustment is needed...',
            'required': True
        })
    )


class BudgetAlertSettingsForm(forms.Form):
    """Form for configuring budget alert thresholds"""
    
    warning_threshold = forms.IntegerField(
        min_value=50,
        max_value=100,
        initial=80,
        label="Warning Threshold (%)",
        help_text="Show yellow warning when budget utilization reaches this percentage",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'required': True
        })
    )
    
    critical_threshold = forms.IntegerField(
        min_value=50,
        max_value=100,
        initial=90,
        label="Critical Threshold (%)",
        help_text="Show red alert when budget utilization reaches this percentage",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'required': True
        })
    )
    
    enable_email_alerts = forms.BooleanField(
        required=False,
        initial=True,
        label="Enable Email Alerts",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        warning = cleaned_data.get('warning_threshold')
        critical = cleaned_data.get('critical_threshold')
        
        if warning and critical and warning >= critical:
            raise forms.ValidationError(
                "Warning threshold must be less than critical threshold"
            )
        
        return cleaned_data
