"""
Forms for the Finance module.
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from apps.finance.models import (
    BudgetHead, FunctionCode, ChequeBook, ChequeLeaf,
    BankStatement, BankStatementLine, StatementStatus
)
from apps.core.models import BankAccount
from apps.budgeting.models import FiscalYear


class BudgetHeadForm(forms.ModelForm):
    """
    Form for creating/editing Budget Heads (Chart of Accounts).
    """
    
    class Meta:
        model = BudgetHead
        fields = [
            'function', 'pifra_object', 'pifra_description',
            'tma_sub_object', 'tma_description',
            'account_type', 'fund',
            'is_active', 'is_charged',
            'budget_control', 'posting_allowed'
        ]
        widgets = {
            'function': forms.Select(attrs={'class': 'form-select'}),
            'pifra_object': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. A01101'}),
            'pifra_description': forms.TextInput(attrs={'class': 'form-control'}),
            'tma_sub_object': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. A01101-000'}),
            'tma_description': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'fund': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_charged': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'budget_control': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'posting_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ChequeBookForm(forms.ModelForm):
    """
    Form for creating a new Cheque Book.
    
    Validates serial range and checks for overlaps.
    """
    
    class Meta:
        model = ChequeBook
        fields = ['bank_account', 'book_no', 'prefix', 'start_serial', 'end_serial', 'issue_date']
        widgets = {
            'bank_account': forms.Select(attrs={
                'class': 'form-select searchable-select'
            }),
            'book_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., BK-2025-01'
            }),
            'prefix': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 00, CHQ (optional)'
            }),
            'start_serial': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1001',
                'min': '1'
            }),
            'end_serial': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1050',
                'min': '1'
            }),
            'issue_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
    
    def __init__(self, *args, organization=None, **kwargs):
        """
        Initialize form with organization-scoped bank accounts.
        """
        super().__init__(*args, **kwargs)
        
        if organization:
            self.fields['bank_account'].queryset = BankAccount.objects.filter(
                organization=organization,
                is_active=True
            ).order_by('title')
    
    def clean(self):
        """Validate serial range."""
        cleaned_data = super().clean()
        start_serial = cleaned_data.get('start_serial')
        end_serial = cleaned_data.get('end_serial')
        bank_account = cleaned_data.get('bank_account')
        
        if start_serial and end_serial:
            if end_serial < start_serial:
                raise forms.ValidationError({
                    'end_serial': _('End serial must be greater than or equal to start serial.')
                })
            
            # Check for overlapping ranges
            if bank_account:
                from django.db.models import Q
                overlapping = ChequeBook.objects.filter(
                    bank_account=bank_account
                ).filter(
                    Q(start_serial__lte=end_serial, end_serial__gte=start_serial)
                )
                
                if self.instance.pk:
                    overlapping = overlapping.exclude(pk=self.instance.pk)
                
                if overlapping.exists():
                    raise forms.ValidationError(
                        _('Serial range overlaps with an existing cheque book for this bank account.')
                    )
        
        return cleaned_data


class ChequeLeafCancelForm(forms.Form):
    """
    Form for cancelling a cheque leaf.
    """
    
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Enter reason for cancellation (e.g., page torn, printing error)'
        }),
        label=_('Cancellation Reason')
    )


# ============================================================================
# Bank Statement & Reconciliation Forms
# ============================================================================

class BankStatementForm(forms.ModelForm):
    """
    Form for creating a new Bank Statement for reconciliation.
    """
    
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'),
        (4, 'April'), (5, 'May'), (6, 'June'),
        (7, 'July'), (8, 'August'), (9, 'September'),
        (10, 'October'), (11, 'November'), (12, 'December'),
    ]
    
    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = BankStatement
        fields = ['bank_account', 'month', 'year', 'opening_balance', 'closing_balance', 'file', 'notes']
        widgets = {
            'bank_account': forms.Select(attrs={
                'class': 'form-select searchable-select'
            }),
            'year': forms.Select(attrs={
                'class': 'form-select'
            }),
            'opening_balance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Opening balance from statement'
            }),
            'closing_balance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Closing balance from statement'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv,.pdf'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes about this statement'
            }),
        }
    
    def __init__(self, *args, organization=None, **kwargs):
        """
        Initialize form with organization-scoped bank accounts and fiscal years.
        """
        super().__init__(*args, **kwargs)
        
        if organization:
            self.fields['bank_account'].queryset = BankAccount.objects.filter(
                organization=organization,
                is_active=True
            ).order_by('title')
            
            self.fields['year'].queryset = FiscalYear.objects.filter(
                organization=organization
            ).order_by('-start_date')
    
    def clean(self):
        """Validate uniqueness of bank_account + month + year."""
        cleaned_data = super().clean()
        bank_account = cleaned_data.get('bank_account')
        month = cleaned_data.get('month')
        year = cleaned_data.get('year')
        
        if bank_account and month and year:
            existing = BankStatement.objects.filter(
                bank_account=bank_account,
                month=month,
                year=year
            )
            
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError(
                    _('A statement for this bank account and month already exists.')
                )
        
        return cleaned_data


class BankStatementLineForm(forms.ModelForm):
    """
    Form for manually adding a statement line.
    """
    
    class Meta:
        model = BankStatementLine
        fields = ['date', 'description', 'debit', 'credit', 'ref_no', 'balance']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Transaction description'
            }),
            'debit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'credit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'ref_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cheque no. / Reference'
            }),
            'balance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Running balance'
            }),
        }


class ManualMatchForm(forms.Form):
    """
    Form for manual matching of statement lines with GL entries.
    """
    
    statement_line_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    journal_entry_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    def clean_statement_line_ids(self):
        """Parse comma-separated IDs."""
        data = self.cleaned_data['statement_line_ids']
        try:
            return [int(x.strip()) for x in data.split(',') if x.strip()]
        except ValueError:
            raise forms.ValidationError(_('Invalid statement line IDs.'))
    
    def clean_journal_entry_ids(self):
        """Parse comma-separated IDs."""
        data = self.cleaned_data['journal_entry_ids']
        try:
            return [int(x.strip()) for x in data.split(',') if x.strip()]
        except ValueError:
            raise forms.ValidationError(_('Invalid journal entry IDs.'))


class StatementUploadForm(forms.Form):
    """
    Form for uploading a bank statement CSV file.
    """
    
    csv_file = forms.FileField(
        label=_('Statement CSV File'),
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        help_text=_('Upload a CSV file with columns: Date, Description, Debit, Credit, Balance, Reference')
    )
    
    def clean_csv_file(self):
        """Validate file type and size."""
        file = self.cleaned_data['csv_file']
        
        if not file.name.endswith('.csv'):
            raise forms.ValidationError(_('Only CSV files are allowed.'))
        
        # Max 5MB
        if file.size > 5 * 1024 * 1024:
            raise forms.ValidationError(_('File size must be under 5MB.'))
        
        return file
