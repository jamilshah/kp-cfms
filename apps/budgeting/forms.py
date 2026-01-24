"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Django forms for the budgeting module.
             Implements BDR-1, BDC-1, BDC-2 forms with validation.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Optional, Dict, Any
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from apps.budgeting.models import (
    FiscalYear, BudgetAllocation, ScheduleOfEstablishment, BudgetStatus
)
from apps.budgeting.services import validate_receipt_growth
from apps.finance.models import BudgetHead, AccountType


class FiscalYearForm(forms.ModelForm):
    """
    Form for creating/editing fiscal years.
    """
    
    class Meta:
        model = FiscalYear
        fields = ['year_name', 'start_date', 'end_date', 'is_active']
        widgets = {
            'year_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2026-27'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean(self) -> Dict[str, Any]:
        """Validate fiscal year dates."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError({
                    'end_date': _('End date must be after start date.')
                })
            
            # Validate fiscal year spans approximately one year
            days_diff = (end_date - start_date).days
            if days_diff < 360 or days_diff > 370:
                raise ValidationError({
                    'end_date': _('Fiscal year should span approximately 365 days.')
                })
        
        return cleaned_data


class BudgetAllocationBaseForm(forms.ModelForm):
    """
    Base form for budget allocation entries.
    Contains common fields and validation.
    """
    
    class Meta:
        model = BudgetAllocation
        fields = [
            'budget_head', 'previous_year_actual', 'current_year_budget',
            'original_allocation', 'remarks'
        ]
        widgets = {
            'budget_head': forms.Select(attrs={
                'class': 'form-select',
            }),
            'previous_year_actual': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'current_year_budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'original_allocation': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Justification for significant changes...'
            }),
        }
    
    def __init__(self, *args, fiscal_year: Optional[FiscalYear] = None, **kwargs):
        """
        Initialize form with fiscal year context.
        
        Args:
            fiscal_year: The fiscal year for this allocation.
        """
        self.fiscal_year = fiscal_year
        super().__init__(*args, **kwargs)
        
        # Check if budget is editable
        if fiscal_year and not fiscal_year.can_edit_budget():
            for field in self.fields.values():
                field.disabled = True


class ReceiptEstimateForm(BudgetAllocationBaseForm):
    """
    Form BDR-1: Receipt/Revenue Estimate Entry.
    
    Used by Dealing Assistant to enter revenue budget estimates.
    Enforces 15% growth cap on estimates.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to revenue heads only
        self.fields['budget_head'].queryset = BudgetHead.objects.filter(
            account_type=AccountType.REVENUE,
            is_active=True
        )
        self.fields['budget_head'].label = _('Revenue Head')
        self.fields['original_allocation'].label = _('Next Year Estimate')
    
    def clean(self) -> Dict[str, Any]:
        """Validate 15% growth cap."""
        cleaned_data = super().clean()
        
        previous_actual = cleaned_data.get('previous_year_actual', Decimal('0.00'))
        next_estimate = cleaned_data.get('original_allocation', Decimal('0.00'))
        remarks = cleaned_data.get('remarks', '')
        
        is_valid, error = validate_receipt_growth(previous_actual, next_estimate)
        
        if not is_valid:
            # Allow if justification provided
            if not remarks or len(remarks.strip()) < 20:
                raise ValidationError({
                    'original_allocation': error,
                    'remarks': _('Please provide detailed justification for exceeding 15% growth.')
                })
        
        return cleaned_data


class ExpenditureEstimateForm(BudgetAllocationBaseForm):
    """
    Form BDC-1: Expenditure Estimate Entry.
    
    Used by Dealing Assistant to enter expenditure budget estimates.
    Salary heads require linkage to Schedule of Establishment.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to expenditure heads only
        self.fields['budget_head'].queryset = BudgetHead.objects.filter(
            account_type=AccountType.EXPENDITURE,
            is_active=True
        )
        self.fields['budget_head'].label = _('Expenditure Head')
        self.fields['original_allocation'].label = _('Proposed Budget')
    
    def clean(self) -> Dict[str, Any]:
        """Validate salary head linkage for A01 heads."""
        cleaned_data = super().clean()
        budget_head = cleaned_data.get('budget_head')
        
        if budget_head and budget_head.is_salary_head():
            # Check if establishment entry exists
            if self.fiscal_year:
                has_establishment = ScheduleOfEstablishment.objects.filter(
                    fiscal_year=self.fiscal_year,
                    budget_head=budget_head
                ).exists()
                
                if not has_establishment:
                    self.add_error(
                        'budget_head',
                        _(
                            'Salary head (A01*) requires linked sanctioned posts. '
                            'Please create Schedule of Establishment entry first.'
                        )
                    )
        
        return cleaned_data


class ScheduleOfEstablishmentForm(forms.ModelForm):
    """
    Form BDC-2: Schedule of Establishment Entry.
    
    Used to define sanctioned posts and link them to salary budget heads.
    """
    
    class Meta:
        model = ScheduleOfEstablishment
        fields = [
            'department', 'designation', 'bps_scale', 
            'sanctioned_posts', 'occupied_posts', 'annual_salary',
            'budget_head', 'is_pugf'
        ]
        widgets = {
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Administration'
            }),
            'designation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Junior Clerk'
            }),
            'bps_scale': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '22'
            }),
            'sanctioned_posts': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'occupied_posts': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'annual_salary': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'budget_head': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_pugf': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, fiscal_year: Optional[FiscalYear] = None, **kwargs):
        """
        Initialize form with fiscal year context.
        
        Args:
            fiscal_year: The fiscal year for this entry.
        """
        self.fiscal_year = fiscal_year
        super().__init__(*args, **kwargs)
        
        # Filter to salary heads only (A01*)
        self.fields['budget_head'].queryset = BudgetHead.objects.filter(
            pifra_object__startswith='A01',
            is_active=True
        )
        self.fields['budget_head'].label = _('Salary Budget Head')
        
        # Check if budget is editable
        if fiscal_year and not fiscal_year.can_edit_budget():
            for field in self.fields.values():
                field.disabled = True
    
    def clean(self) -> Dict[str, Any]:
        """Validate establishment entry."""
        cleaned_data = super().clean()
        
        sanctioned = cleaned_data.get('sanctioned_posts', 0)
        occupied = cleaned_data.get('occupied_posts', 0)
        
        if occupied > sanctioned:
            raise ValidationError({
                'occupied_posts': _('Occupied posts cannot exceed sanctioned posts.')
            })
        
        return cleaned_data


class BudgetApprovalForm(forms.Form):
    """
    Form for TMO to approve and finalize budget.
    """
    
    confirmation = forms.BooleanField(
        required=True,
        label=_('I confirm the budget is correct and ready for finalization'),
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    remarks = forms.CharField(
        required=False,
        label=_('Approval Remarks'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional remarks for the approval...'
        })
    )


class QuarterlyReleaseForm(forms.Form):
    """
    Form for TO Finance to process quarterly fund releases.
    """
    
    quarter = forms.ChoiceField(
        choices=[],
        label=_('Quarter to Release'),
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    confirmation = forms.BooleanField(
        required=True,
        label=_('I confirm the quarterly release should be processed'),
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def __init__(self, *args, pending_quarters=None, **kwargs):
        """
        Initialize with available quarters.
        
        Args:
            pending_quarters: List of quarter tuples (code, display_name).
        """
        super().__init__(*args, **kwargs)
        if pending_quarters:
            self.fields['quarter'].choices = pending_quarters


class BudgetSearchForm(forms.Form):
    """
    Form for searching and filtering budget allocations.
    """
    
    fiscal_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.all(),
        required=False,
        empty_label=_('All Fiscal Years'),
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    account_type = forms.ChoiceField(
        choices=[('', _('All Types'))] + list(AccountType.choices),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by head code or description...')
        })
    )
