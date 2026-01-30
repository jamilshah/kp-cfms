"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Forms for the Revenue module including Payer, Demand,
             and Collection forms with Select2 integration.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Any, Dict
from django import forms
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.revenue.models import Payer, RevenueDemand, RevenueCollection, DemandStatus
from apps.finance.models import BudgetHead, AccountType, FunctionCode
from apps.budgeting.models import FiscalYear, Department
from apps.core.models import BankAccount


class PayerForm(forms.ModelForm):
    """
    Form for creating and updating Payer records.
    """
    
    class Meta:
        model = Payer
        fields = ['name', 'cnic_ntn', 'contact_no', 'address', 'email']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter payer/citizen name'
            }),
            'cnic_ntn': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'CNIC (XXXXX-XXXXXXX-X) or NTN'
            }),
            'contact_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone/Mobile number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Full mailing address'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
        }


class DemandForm(forms.ModelForm):
    """
    Form for creating Revenue Demand (Challan) records.
    
    Budget head is filtered to Revenue accounts only.
    Payer uses searchable Select2 dropdown.
    """
    
    class Meta:
        model = RevenueDemand
        fields = [
            'payer', 'budget_head', 'issue_date', 'due_date',
            'amount', 'period_description', 'description'
        ]
        widgets = {
            'payer': forms.Select(attrs={
                'class': 'form-select searchable-select'
            }),
            'budget_head': forms.Select(attrs={
                'class': 'form-select searchable-select'
            }),
            'issue_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'period_description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Jan 2026 Rent, Q1 2026 License Fee'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes or description'
            }),
        }
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        required=False,
        label=_('Department'),
        help_text=_('Filter functions and revenue heads'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'hx-get': reverse_lazy('revenue:load_functions'),
            'hx-target': '#id_function',
            'hx-trigger': 'change'
        })
    )
    
    function = forms.ModelChoiceField(
        queryset=FunctionCode.objects.none(),
        required=False,
        label=_('Function'),
        help_text=_('Filter revenue heads by function'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'hx-get': reverse_lazy('revenue:load_revenue_heads'),
            'hx-target': '#id_budget_head',
            'hx-trigger': 'change',
            'hx-include': '#id_department'
        })
    )

    def __init__(self, *args, organization=None, **kwargs) -> None:
        """
        Initialize form with organization-scoped querysets.
        
        Args:
            organization: The organization to filter related objects.
        """
        super().__init__(*args, **kwargs)
        self._current_fiscal_year = None
        
        # Base Queryset: Revenue accounts
        self.fields['budget_head'].queryset = BudgetHead.objects.filter(
            global_head__account_type=AccountType.REVENUE,
            posting_allowed=True,
            is_active=True
        ).order_by('global_head__name', 'global_head__code')

        if organization:
            # Get current operating fiscal year
            today = timezone.now().date()
            self._current_fiscal_year = FiscalYear.objects.filter(
                organization=organization,
                start_date__lte=today,
                end_date__gte=today
            ).first()
            
            # Filter payers to active ones for this organization
            self.fields['payer'].queryset = Payer.objects.filter(
                organization=organization,
                is_active=True
            ).order_by('name')
        
        # Load departments
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')

        # === Dynamic Filtering Logic ===
        
        # 1. Department
        department_id = None
        if 'department' in self.data:
            department_id = self.data.get('department')
        elif self.initial.get('department'):
            department_id = self.initial.get('department')

        # 2. Function
        self.fields['function'].queryset = FunctionCode.objects.none()
        if department_id:
            try:
                dept = Department.objects.get(id=department_id)
                self.fields['function'].queryset = dept.related_functions.all().order_by('code')
            except (ValueError, TypeError, Department.DoesNotExist):
                pass
        
        function_id = None
        if 'function' in self.data:
            function_id = self.data.get('function')
        elif self.initial.get('function'):
            function_id = self.initial.get('function')

        # 3. Budget Head
        if function_id:
             self.fields['budget_head'].queryset = self.fields['budget_head'].queryset.filter(function_id=function_id)
        elif department_id:
             try:
                 dept = Department.objects.get(id=department_id)
                 self.fields['budget_head'].queryset = self.fields['budget_head'].queryset.filter(
                    function__in=dept.related_functions.all()
                 )
             except (ValueError, TypeError, Department.DoesNotExist):
                 pass
        
        # Set default dates
        if not self.instance.pk:
            today = timezone.now().date()
            self.initial['issue_date'] = today
            # Default due date to 30 days from issue
            from datetime import timedelta
            self.initial['due_date'] = today + timedelta(days=30)
    
    def clean(self) -> Dict[str, Any]:
        """Validate form data."""
        cleaned_data = super().clean()
        issue_date = cleaned_data.get('issue_date')
        due_date = cleaned_data.get('due_date')
        
        if issue_date and due_date and due_date < issue_date:
            raise forms.ValidationError({
                'due_date': _('Due date cannot be before issue date.')
            })
        
        return cleaned_data


class CollectionForm(forms.ModelForm):
    """
    Form for recording Revenue Collection (Receipt).
    
    Demand can be searched by challan number or payer name.
    Bank account uses searchable dropdown.
    """
    
    class Meta:
        model = RevenueCollection
        fields = [
            'demand', 'bank_account', 'receipt_date',
            'instrument_type', 'instrument_no', 'amount_received', 'remarks'
        ]
        widgets = {
            'demand': forms.Select(attrs={
                'class': 'form-select searchable-select'
            }),
            'bank_account': forms.Select(attrs={
                'class': 'form-select searchable-select'
            }),
            'receipt_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'instrument_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'instrument_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cheque number or reference'
            }),
            'amount_received': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, organization=None, demand=None, **kwargs) -> None:
        """
        Initialize form with organization-scoped querysets.
        
        Args:
            organization: The organization to filter related objects.
            demand: Pre-selected demand (optional).
        """
        super().__init__(*args, **kwargs)
        
        if organization:
            # Filter demands to Posted or Partial for this organization
            self.fields['demand'].queryset = RevenueDemand.objects.filter(
                organization=organization,
                status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL]
            ).select_related('payer').order_by('-issue_date')
            
            # Filter bank accounts to active ones for this organization
            self.fields['bank_account'].queryset = BankAccount.objects.filter(
                organization=organization,
                is_active=True
            ).order_by('title')
        
        # Pre-select demand if provided
        if demand:
            self.initial['demand'] = demand
            self.fields['demand'].widget.attrs['readonly'] = True
        
        # Set default receipt date
        if not self.instance.pk:
            self.initial['receipt_date'] = timezone.now().date()
    
    def clean_amount_received(self) -> Decimal:
        """Validate amount doesn't exceed outstanding balance."""
        amount = self.cleaned_data.get('amount_received')
        demand = self.cleaned_data.get('demand')
        
        if amount and demand:
            outstanding = demand.get_outstanding_balance()
            if amount > outstanding:
                raise forms.ValidationError(
                    _(f'Amount exceeds outstanding balance of Rs. {outstanding}.')
                )
        
        return amount


class DemandPostForm(forms.Form):
    """Form for confirming demand posting."""
    
    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_('I confirm this demand should be posted to the GL')
    )


class CollectionPostForm(forms.Form):
    """Form for confirming collection posting."""
    
    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_('I confirm this collection should be posted to the GL')
    )


class DemandCancelForm(forms.Form):
    """Form for cancelling a demand."""
    
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter reason for cancellation'
        }),
        label=_('Cancellation Reason')
    )
