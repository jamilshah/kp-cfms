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
    FiscalYear, BudgetAllocation, ScheduleOfEstablishment, BudgetStatus,
    DesignationMaster, Department, BPSSalaryScale,
    # Phase 3: Pension & Budget Execution
    PensionEstimate, RetiringEmployee, SupplementaryGrant, Reappropriation
)
from apps.budgeting.services import validate_receipt_growth
from apps.finance.models import BudgetHead, AccountType


class FiscalYearForm(forms.ModelForm):
    """
    Form for creating/editing fiscal years.
    """
    
    class Meta:
        model = FiscalYear
        fields = ['organization', 'year_name', 'start_date', 'end_date', 'is_active']
        widgets = {
            'organization': forms.Select(attrs={
                'class': 'form-control'
            }),
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
    
    def __init__(self, *args, **kwargs):
        """Initialize form and customize organization field based on user."""
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # If user has an organization (TMA admin), hide org field and pre-set it
        if self.request and self.request.user.organization:
            self.fields['organization'].widget = forms.HiddenInput()
            self.fields['organization'].initial = self.request.user.organization
            self.fields['organization'].disabled = True
    
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
                'class': 'form-select searchable-select',
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
    Form BDC-2 (Part A): Existing Sanctioned Posts.
    
    Restricted editing for existing posts (view-only sanctioned count).
    """
    
    department_select = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by('name'),
        label=_('Department/Wing'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label=_("Select Department...")
    )
    
    designation = forms.ModelChoiceField(
        queryset=DesignationMaster.objects.filter(is_active=True).order_by('name'),
        label=_('Designation'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label=_("Select Designation...")
    )

    class Meta:
        model = ScheduleOfEstablishment
        fields = [
            'department_select', 'designation', 'bps_scale', 
            'sanctioned_posts', 'occupied_posts', 'annual_salary',
            'budget_head', 'post_type'
        ]
        widgets = {
            'bps_scale': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '22'
            }),
            'sanctioned_posts': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'readonly': 'readonly',  # Cannot change sanctioned count here
                'title': 'Cannot modify sanctioned strength of existing posts'
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
            'post_type': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, fiscal_year: Optional[FiscalYear] = None, **kwargs):
        """Initialize form."""
        self.fiscal_year = fiscal_year
        super().__init__(*args, **kwargs)
        
        # Initialize dropdowns for existing instance
        if self.instance.pk:
            if self.instance.department:
                try:
                    dept = Department.objects.get(name=self.instance.department)
                    self.fields['department_select'].initial = dept
                except Department.DoesNotExist:
                    pass
        
        # Filter to salary heads only (A01*)
        self.fields['budget_head'].queryset = BudgetHead.objects.filter(
            pifra_object__startswith='A01',
            is_active=True
        )
        
        # Make sanctioned_posts read-only ONLY for existing records
        if self.instance.pk:
            self.fields['sanctioned_posts'].widget.attrs['readonly'] = 'readonly'
            self.fields['sanctioned_posts'].widget.attrs['title'] = _('Cannot modify sanctioned strength of existing posts')
        else:
            # Editable for new entries
            self.fields['sanctioned_posts'].widget.attrs.pop('readonly', None)
        
        if fiscal_year and not fiscal_year.can_edit_budget():
            for field in self.fields.values():
                field.disabled = True

    def save(self, commit=True):
        """Map dropdown selections to text fields."""
        instance = super().save(commit=False)
        
        # Map Department
        department = self.cleaned_data.get('department_select')
        if department:
            instance.department = department.name
            
        # Map Designation details
        # designation FK is set by form, but we need to sync redundant fields
        if instance.designation:
            instance.designation_name = instance.designation.name
            # If creating new or empty, sync BPS/Post Type
            if not instance.pk: 
                instance.bps_scale = instance.designation.bps_scale
                instance.post_type = instance.designation.post_type
        
        if commit:
            instance.save()
            
        return instance


class NewPostProposalForm(forms.ModelForm):
    """
    Form BDC-2 (Part B): New Post Proposals (SNE).
    
    Used to propose NEW posts for the upcoming year.
    Refactored to use dropdowns for Designation and dynamically
    determine BPS, Post Type, and Budget Head.
    """
    
    designation = forms.ModelChoiceField(
        queryset=DesignationMaster.objects.filter(is_active=True).order_by('name'),
        label=_('Proposed Designation'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label=_("Select Designation...")
    )
    
    department_select = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by('name'),
        label=_('Department/Wing'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label=_("Select Department...")
    )
    
    class Meta:
        model = ScheduleOfEstablishment
        fields = ['sanctioned_posts', 'justification']
        labels = {
            'sanctioned_posts': _('Number of Posts Required'),
        }
        widgets = {
            'sanctioned_posts': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'justification': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Explain WHY these posts are needed (Required)...'
            }),
        }
    
    def __init__(self, *args, fiscal_year: Optional[FiscalYear] = None, **kwargs):
        self.fiscal_year = fiscal_year
        super().__init__(*args, **kwargs)
        
        # Initialize designation/department from instance if editing
        if self.instance.pk:
            if self.instance.designation_name:
                try:
                    dm = DesignationMaster.objects.get(name=self.instance.designation_name)
                    self.fields['designation'].initial = dm
                except DesignationMaster.DoesNotExist:
                    pass
            
            if self.instance.department:
                try:
                    dept = Department.objects.get(name=self.instance.department)
                    self.fields['department_select'].initial = dept
                except Department.DoesNotExist:
                    pass

        # New proposals start with 0 occupied posts
        self.instance.occupied_posts = 0
        from apps.budgeting.models import EstablishmentStatus
        self.instance.establishment_status = EstablishmentStatus.PROPOSED
        self.instance.post_type = "TBD"  # Will be set in save()

    def clean_justification(self):
        """Enforce strict justification."""
        justification = self.cleaned_data.get('justification')
        if not justification or len(justification.strip()) < 20:
            raise ValidationError(
                _("Please provide a detailed justification (at least 20 chars) for this new expenditure.")
            )
        return justification
    
    def save(self, commit=True):
        """Auto-populate fields driven by designation."""
        instance = super().save(commit=False)
        
        designation = self.cleaned_data['designation']
        department = self.cleaned_data['department_select']
        
        instance.designation_name = designation.name
        instance.department = department.name
        instance.bps_scale = designation.bps_scale
        instance.post_type = designation.post_type
        
        # Auto-select budget head
        # Officers (BPS 17+) vs Staff (BPS 1-16)
        code_prefix = 'A01101' if instance.bps_scale >= 17 else 'A0115'
        
        # Try to find specific head
        head = BudgetHead.objects.filter(
            pifra_object__startswith=code_prefix,
            is_active=True
        ).first()
        
        if not head:
            # Fallback to generic Salary of Officers/Staff
            search_term = 'Officer' if instance.bps_scale >= 17 else 'Other Staff'
            head = BudgetHead.objects.filter(
                tma_description__icontains=search_term,
                is_active=True
            ).first()
            
        if not head:
            # Last resort: A01 (Total Basic Pay)
            head = BudgetHead.objects.filter(
                pifra_object='A01', is_active=True
            ).first()
            
        if not head:
            # Absolute Failsafe: Any Expenditure Head
            head = BudgetHead.objects.first()
            
        instance.budget_head = head
        
        if self.fiscal_year:
            instance.fiscal_year = self.fiscal_year
            
        if commit:
            instance.save()
            self.save_m2m()
            
        return instance


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


class BPSSalaryScaleForm(forms.ModelForm):
    """
    Form for editing BPS Salary Scale grid row.
    """
    class Meta:
        model = BPSSalaryScale
        fields = [
            'basic_pay_min', 'annual_increment', 'basic_pay_max',
            'conveyance_allowance', 'medical_allowance',
            'house_rent_percent', 'adhoc_relief_total_percent'
        ]
        widgets = {
            'basic_pay_min': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '1'}),
            'annual_increment': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '1'}),
            'basic_pay_max': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '1'}),
            'conveyance_allowance': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '1'}),
            'medical_allowance': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '1'}),
            'house_rent_percent': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01'}),
            'adhoc_relief_total_percent': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01'}),
        }


# =============================================================================
# Phase 3: Pension & Budget Execution Forms
# =============================================================================

class PensionEstimateForm(forms.ModelForm):
    """
    Form for creating/editing Pension Estimates.
    """
    class Meta:
        model = PensionEstimate
        fields = ['fiscal_year', 'current_monthly_bill', 'expected_increase', 'remarks']
        widgets = {
            'fiscal_year': forms.Select(attrs={'class': 'form-select'}),
            'current_monthly_bill': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'expected_increase': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter active fiscal years or future ones
        self.fields['fiscal_year'].queryset = FiscalYear.objects.filter(is_locked=False)


class RetiringEmployeeForm(forms.ModelForm):
    """
    Form for adding Retiring Employees to a Pension Estimate.
    """
    class Meta:
        model = RetiringEmployee
        fields = ['name', 'designation', 'retirement_date', 
                  'monthly_pension_amount', 'commutation_amount', 'remarks']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'retirement_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'monthly_pension_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'commutation_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SupplementaryGrantForm(forms.ModelForm):
    """
    Form for requesting a Supplementary Grant.
    """
    class Meta:
        model = SupplementaryGrant
        fields = ['fiscal_year', 'budget_head', 'amount', 'reference_no', 
                  'date', 'description']
        widgets = {
            'fiscal_year': forms.Select(attrs={'class': 'form-select'}),
            'budget_head': forms.Select(attrs={'class': 'form-select searchable-select'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'reference_no': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['budget_head'].queryset = BudgetHead.objects.filter(is_active=True)


class ReappropriationForm(forms.ModelForm):
    """
    Form for requesting Re-appropriation of funds.
    """
    class Meta:
        model = Reappropriation
        fields = ['fiscal_year', 'from_head', 'to_head', 'amount', 
                  'reference_no', 'date', 'description']
        widgets = {
            'fiscal_year': forms.Select(attrs={'class': 'form-select'}),
            'from_head': forms.Select(attrs={'class': 'form-select searchable-select'}),
            'to_head': forms.Select(attrs={'class': 'form-select searchable-select'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'reference_no': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter budget heads that are active
        active_heads = BudgetHead.objects.filter(is_active=True)
        self.fields['from_head'].queryset = active_heads
        self.fields['to_head'].queryset = active_heads

    def clean(self):
        cleaned_data = super().clean()
        from_head = cleaned_data.get('from_head')
        to_head = cleaned_data.get('to_head')
        amount = cleaned_data.get('amount')
        fiscal_year = cleaned_data.get('fiscal_year')

        if from_head and to_head:
            # Rule 1: Same Fund check
            if from_head.fund != to_head.fund:
                raise forms.ValidationError(
                    f"Both budget heads must belong to the same Fund. "
                    f"From: {from_head.fund}, To: {to_head.fund}"
                )
            
            # Rule 2: Validation of sufficient balance is done in model.clean(), 
            # but we can do a preliminary check here if we have fiscal_year
            if fiscal_year and amount:
                try:
                    from_allocation = BudgetAllocation.objects.get(
                        fiscal_year=fiscal_year,
                        budget_head=from_head
                    )
                    available = from_allocation.revised_allocation - from_allocation.spent_amount
                    if amount > available:
                        self.add_error('amount', 
                            f"Insufficient balance in {from_head}. Available: {available}"
                        )
                except BudgetAllocation.DoesNotExist:
                   self.add_error('from_head', f"No budget allocation found for {from_head} in {fiscal_year}.")

        return cleaned_data
