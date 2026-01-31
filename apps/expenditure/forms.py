"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Forms for the expenditure module including Bill and
             Payment creation forms.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Any, Optional
from django import forms
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from django.forms import inlineformset_factory
from apps.expenditure.models import Payee, Bill, BillLine, Payment, BillStatus
from apps.finance.models import BudgetHead, AccountType, FunctionCode
from apps.budgeting.models import FiscalYear, BudgetAllocation, Department
from apps.core.models import BankAccount


class PayeeForm(forms.ModelForm):
    """
    Form for creating and updating Payee records.
    """
    
    class Meta:
        model = Payee
        fields = [
            'name', 'cnic_ntn', 'address', 'phone', 
            'email', 'bank_name', 'bank_account'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter payee/vendor name'
            }),
            'cnic_ntn': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'CNIC (XXXXX-XXXXXXX-X) or NTN'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Full mailing address'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contact phone number'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank name'
            }),
            'bank_account': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank account number'
            }),
        }


class BillForm(forms.ModelForm):
    """
    Form for creating Bill/Invoice records.
    
    Includes validation for:
    - Budget head must be an expenditure account
    - Fiscal year must be active
    - Auto-calculation of net_amount
    """
    
    class Meta:
        model = Bill
        fields = [
            'payee', 'bill_date',
            'bill_number', 'description', 
            'gross_amount', 'tax_amount'
        ]
        widgets = {
            'payee': forms.Select(attrs={'class': 'form-select searchable-select'}),
            # 'budget_head': Remove as it is now in lines
            'bill_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'bill_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Vendor invoice number'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of goods/services'
            }),
            'gross_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'tax_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': '0.00'
            }),
        }
    
    # Removed dynamic filter fields from parent form
    # Filter fields (Client-side use only, not saved to Bill)
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        required=False,
        label=_('Department Filter'),
        help_text=_('Filter budget heads by department.'),
        widget=forms.Select(attrs={
            'class': 'form-select select2-enable',
            'hx-get': reverse_lazy('finance:load_functions'),
            'hx-target': '#id_function',
            'hx-trigger': 'change',
        })
    )
    function = forms.ModelChoiceField(
        queryset=FunctionCode.objects.none(),
        required=False,
        label=_('Function Filter'),
        help_text=_('Filter budget heads by function.'),
        widget=forms.Select(attrs={
            'class': 'form-select select2-enable',
            'hx-get': reverse_lazy('finance:load_budget_heads_options'),
            'hx-target': '#budget-head-options',
            'hx-trigger': 'change',
            'hx-include': '[name=department]',
            'hx-vals': '{"account_type": "EXP"}',  # Only show Expenditure heads
        })
    )

    def __init__(self, *args, organization=None, **kwargs) -> None:
        """
        Initialize the form with organization-scoped querysets.
        
        Args:
            organization: The organization to filter related objects.
        """
        super().__init__(*args, **kwargs)
        self._current_fiscal_year = None
        
        # Filter budget heads to expenditure accounts only
        # Filter budget heads removed from parent form

        if organization:
            # Get current operating year
            from django.utils import timezone
            today = timezone.now().date()
            self._current_fiscal_year = FiscalYear.objects.filter(
                organization=organization,
                start_date__lte=today,
                end_date__gte=today
            ).first()
            
            # Filter payees
            self.fields['payee'].queryset = Payee.objects.filter(
                organization=organization,
                is_active=True
            )
            
        # Load departments
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')
        
        # Dynamic filtering logic for function based on department
        department_id = None
        if 'department' in self.data:
            department_id = self.data.get('department')
        elif self.initial.get('department'):
            department_id = self.initial.get('department')
        
        if department_id:
            try:
                dept = Department.objects.get(id=department_id)
                self.fields['function'].queryset = dept.related_functions.all().order_by('code')
            except (ValueError, TypeError, Department.DoesNotExist):
                pass

        # Set default tax amount
        if not self.instance.pk:
            self.initial['tax_amount'] = Decimal('0.00')
    
    def clean(self) -> dict:
        """
        Validate the form data.
        
        Checks:
        - Fiscal year is active and not locked
        - Budget allocation exists for the selected head
        """
        cleaned_data = super().clean()
        fiscal_year = cleaned_data.get('fiscal_year')
        # budget_head = cleaned_data.get('budget_head') # Removed
        gross_amount = cleaned_data.get('gross_amount')
        tax_amount = cleaned_data.get('tax_amount', Decimal('0.00'))
        
        if fiscal_year:
            if fiscal_year.is_locked:
                raise forms.ValidationError({
                    'fiscal_year': _('This fiscal year is locked. No new bills can be created.')
                })
            # Validate the fiscal year covers today's date (current operating year)
            from django.utils import timezone
            today = timezone.now().date()
            if not (fiscal_year.start_date <= today <= fiscal_year.end_date):
                raise forms.ValidationError({
                    'fiscal_year': _('Bills can only be created for the current operating fiscal year.')
                })
        
        # Refactored: Budget allocation check moved to Bill.approve() for each line
        # if budget_head and fiscal_year ...
        
        # Calculate net amount
        if gross_amount and tax_amount is not None:
            cleaned_data['net_amount'] = gross_amount - tax_amount
        
        return cleaned_data



class BillLineForm(forms.ModelForm):
    """
    Form for individual bill line items.
    """
    class Meta:
        model = BillLine
        fields = ['budget_head', 'description', 'amount']
        widgets = {
            'budget_head': forms.Select(attrs={'class': 'form-select searchable-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Line description'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter budget heads to expenditure accounts only, allowing A01 (salary)
        self.fields['budget_head'].queryset = BudgetHead.objects.filter(
            global_head__account_type=AccountType.EXPENDITURE,
            posting_allowed=True,
            is_active=True
        ).select_related('global_head', 'function').order_by('global_head__name', 'global_head__code')


BillLineFormSet = inlineformset_factory(
    Bill,
    BillLine,
    form=BillLineForm,
    extra=1,
    can_delete=True
)


class BillSubmitForm(forms.Form):
    """Simple form for submitting a bill for approval."""
    confirm = forms.BooleanField(
        required=True,
        label=_('I confirm that the bill details are correct and ready for approval.')
    )


class BillApprovalForm(forms.Form):
    """Form for approving or rejecting a bill."""
    
    ACTION_CHOICES = [
        ('approve', _('Approve')),
        ('reject', _('Reject')),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for rejection (required if rejecting)'
        })
    )
    
    def clean(self) -> dict:
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if action == 'reject' and not rejection_reason:
            raise forms.ValidationError({
                'rejection_reason': _('Rejection reason is required when rejecting a bill.')
            })
        
        return cleaned_data


class PaymentForm(forms.ModelForm):
    """
    Form for creating Payment records.
    
    Filters bills to show only APPROVED bills for the organization.
    """
    
    class Meta:
        model = Payment
        fields = ['bill', 'bank_account', 'cheque_number', 'cheque_date', 'amount']
        widgets = {
            'bill': forms.Select(attrs={'class': 'form-select searchable-select'}),
            'bank_account': forms.Select(attrs={'class': 'form-select searchable-select'}),
            'cheque_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cheque number'
            }),
            'cheque_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'readonly': 'readonly'
            }),
        }
    
    def __init__(self, *args, organization=None, **kwargs) -> None:
        """
        Initialize the form with organization-scoped querysets.
        
        Args:
            organization: The organization to filter related objects.
        """
        super().__init__(*args, **kwargs)
        self.organization = organization
        
        if organization:
            # Filter bills to approved ones for this organization
            self.fields['bill'].queryset = Bill.objects.filter(
                organization=organization,
                status=BillStatus.APPROVED
            ).select_related('payee')
            
            # Filter bank accounts to active ones for this organization
            self.fields['bank_account'].queryset = BankAccount.objects.filter(
                organization=organization,
                is_active=True
            )
        
        # If a bill is pre-selected, set the amount
        if 'initial' in kwargs and 'bill' in kwargs['initial']:
            bill = kwargs['initial']['bill']
            if isinstance(bill, Bill):
                self.initial['amount'] = bill.net_amount
    
    def clean(self) -> dict:
        cleaned_data = super().clean()
        bill = cleaned_data.get('bill')
        amount = cleaned_data.get('amount')
        
        if bill:
            if bill.status != BillStatus.APPROVED:
                raise forms.ValidationError({
                    'bill': _('Only APPROVED bills can be paid.')
                })
            
            # Check if payment already exists
            if bill.payments.filter(is_posted=True).exists():
                raise forms.ValidationError({
                    'bill': _('This bill has already been paid.')
                })
            
            # Validate amount matches bill net_amount
            if amount and amount != bill.net_amount:
                raise forms.ValidationError({
                    'amount': _(
                        f'Payment amount must equal bill net amount (Rs. {bill.net_amount}).'
                    )
                })
        
        return cleaned_data
