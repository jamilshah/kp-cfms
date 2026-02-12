"""
Forms for the Finance module.
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from apps.finance.models import (
    BudgetHead, FunctionCode, ChequeBook, ChequeLeaf,
    BankStatement, BankStatementLine, StatementStatus,
    Voucher, JournalEntry, NAMHead, SubHead
)
from apps.core.models import BankAccount
from apps.budgeting.models import FiscalYear, Department
from django.urls import reverse_lazy


class BudgetHeadForm(forms.ModelForm):
    """
    Form for creating/editing Budget Heads (Chart of Accounts).
    
    NAM CoA Structure (5-level hierarchy):
    - Department + Fund + Function are required
    - EITHER nam_head OR sub_head must be selected (mutually exclusive)
    - Selecting department/function filters available NAM heads
    """
    
    class Meta:
        model = BudgetHead
        fields = [
            'department', 'fund', 'function',
            'nam_head', 'sub_head',
            'current_budget',
            'is_active',
            'budget_control', 'posting_allowed', 'project_required'
        ]
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'fund': forms.Select(attrs={'class': 'form-select'}),
            'function': forms.Select(attrs={'class': 'form-select', 'id': 'id_function'}),
            'nam_head': forms.Select(attrs={'class': 'form-select searchable-select', 'id': 'id_nam_head'}),
            'sub_head': forms.Select(attrs={'class': 'form-select searchable-select', 'id': 'id_sub_head'}),
            'current_budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'budget_control': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'posting_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'project_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        kwargs.pop('mode', '')  # Remove mode parameter (no longer used)
        super().__init__(*args, **kwargs)
        
        # Configure department field
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')
        self.fields['department'].help_text = _('Select the department responsible for this budget head.')
        
        # Configure function field
        self.fields['function'].label = _('Function Code')
        self.fields['function'].help_text = _('The PIFRA functional classification code.')
        
        # Configure NAM Head field
        self.fields['nam_head'].label = _('NAM Head (Level 4)')
        self.fields['nam_head'].help_text = _('Select if this is a regular budget head without sub-divisions.')
        self.fields['nam_head'].required = False
        
        # Configure Sub-Head field
        self.fields['sub_head'].label = _('Sub-Head (Level 5)')
        self.fields['sub_head'].help_text = _('Select if this is a sub-divided budget head.')
        self.fields['sub_head'].required = False
        
        # Filter NAM heads by department and function if available
        from django.db.models import Q
        from apps.finance.models import NAMHead, SubHead
        
        nam_head_qs = NAMHead.objects.select_related('minor__major').order_by('code')
        # SubHead.code is a @property, not a DB field - must order by nam_head__code, sub_code
        sub_head_qs = SubHead.objects.select_related('nam_head__minor__major').order_by('nam_head__code', 'sub_code')
        
        # If editing instance with department/function, filter by DepartmentFunctionConfiguration
        # This replaces the deprecated scope-based filtering
        if self.instance and self.instance.pk:
            if self.instance.department and self.instance.function:
                # Get configured NAM heads for this dept-func combination
                from apps.finance.models import DepartmentFunctionConfiguration
                config = DepartmentFunctionConfiguration.objects.filter(
                    department=self.instance.department,
                    function=self.instance.function
                ).first()
                
                if config:
                    # Only show NAM heads configured for this department-function
                    allowed_nam_ids = list(config.allowed_nam_heads.values_list('id', flat=True))
                    nam_head_qs = nam_head_qs.filter(id__in=allowed_nam_ids)
                    
                    # Filter sub-heads by their parent NAM head
                    sub_head_qs = sub_head_qs.filter(nam_head_id__in=allowed_nam_ids)
                else:
                    # No configuration found - show all heads with a warning
                    # (backward compatibility - in production this shouldn't happen)
                    pass
            
            # Lock identity fields unless superuser
            is_superuser = self.request and self.request.user.is_superuser
            if not is_superuser:
                self.fields['fund'].disabled = True
                self.fields['department'].disabled = True
                self.fields['function'].disabled = True
                self.fields['nam_head'].disabled = True
                self.fields['sub_head'].disabled = True
        
        self.fields['nam_head'].queryset = nam_head_qs
        self.fields['sub_head'].queryset = sub_head_qs
    
    def clean(self):
        """
        Validate budget head:
        - Delegates mutual exclusivity validation to model's clean() method
        - Check for duplicate budget heads
        """
        cleaned_data = super().clean()
        
        department = cleaned_data.get('department')
        fund = cleaned_data.get('fund')
        function = cleaned_data.get('function')
        nam_head = cleaned_data.get('nam_head')
        sub_head = cleaned_data.get('sub_head')
        
        # NOTE: Mutual exclusivity validation is handled by model's clean() method
        # No need to duplicate that logic here
        
        # Check for duplicates
        if department and fund and function and (nam_head or sub_head):
            # Build the query
            duplicate_query = BudgetHead.objects.filter(
                department=department,
                fund=fund,
                function=function,
            )
            
            if nam_head:
                duplicate_query = duplicate_query.filter(nam_head=nam_head)
            else:
                duplicate_query = duplicate_query.filter(sub_head=sub_head)
            
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
            
            if duplicate_query.exists():
                existing = duplicate_query.first()
                error_msg = _(
                    f'This budget head already exists: {existing}. '
                    f'Each combination of Department + Fund + Function + (NAM Head OR Sub-Head) must be unique.'
                )
                raise ValidationError(error_msg)
        
        return cleaned_data


class SubHeadForm(forms.ModelForm):
    """
    Form for creating/editing Sub-Heads (Level 5 of CoA hierarchy).
    
    Sub-Heads provide optional subdivisions of NAM Heads for more granular tracking.
    Example: A01101-01, A01101-02 under parent NAM Head A01101.
    """
    
    class Meta:
        model = SubHead
        fields = ['nam_head', 'sub_code', 'name', 'description', 'is_active']
        widgets = {
            'nam_head': forms.Select(attrs={
                'class': 'form-select searchable-select',
                'data-placeholder': 'Select parent NAM Head...'
            }),
            'sub_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '01, 02, 03...',
                'maxlength': '2',
                'pattern': '[0-9]{2}',
                'title': 'Enter 2-digit code (e.g., 01, 02, 03)'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descriptive name for this sub-head'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional detailed description'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'nam_head': _('Select the parent NAM Head (Level 4) for this sub-head'),
            'sub_code': _('2-digit code (01-99). Must be unique within the parent NAM head.'),
            'name': _('Descriptive name for this specific subdivision'),
            'description': _('Optional detailed description or usage notes'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Order NAM heads by code for easier selection
        self.fields['nam_head'].queryset = NAMHead.objects.filter(
            is_active=True
        ).select_related('minor__major').order_by('code')
        
        # Make description optional but encourage usage
        self.fields['description'].required = False
        
        # Set default to active
        if not self.instance.pk:
            self.fields['is_active'].initial = True
    
    def clean_sub_code(self):
        """Validate sub_code format."""
        sub_code = self.cleaned_data.get('sub_code', '').strip()
        
        if not sub_code:
            raise ValidationError(_('Sub-code is required'))
        
        # Ensure 2 digits
        if not sub_code.isdigit() or len(sub_code) != 2:
            raise ValidationError(_('Sub-code must be exactly 2 digits (e.g., 01, 02, 03)'))
        
        return sub_code
    
    def clean(self):
        """Check for duplicate nam_head + sub_code combination."""
        cleaned_data = super().clean()
        nam_head = cleaned_data.get('nam_head')
        sub_code = cleaned_data.get('sub_code')
        
        if nam_head and sub_code:
            # Check for duplicates
            duplicate_query = SubHead.objects.filter(
                nam_head=nam_head,
                sub_code=sub_code
            )
            
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
            
            if duplicate_query.exists():
                existing = duplicate_query.first()
                raise ValidationError(
                    _(f'Sub-head {existing.code} already exists. '
                      f'Each sub-code must be unique within its parent NAM head.')
                )
        
        return cleaned_data


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
            
            self.fields['year'].queryset = FiscalYear.objects.all().order_by('-start_date')
            
            # Set default to current fiscal year
            from django.utils import timezone
            today = timezone.now().date()
            try:
                current_fy = FiscalYear.objects.filter(
                    start_date__lte=today,
                    end_date__gte=today
                ).first()
                
                if current_fy:
                    self.initial['year'] = current_fy
            except Exception:
                pass
    
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


class VoucherForm(forms.ModelForm):
    """
    Form for creating/editing Voucher header (Manual Journal Vouchers).
    
    For manual journal entries by accountants to post adjustments,
    opening balances, and corrections. Allows JV and CV voucher types only.
    """
    
    # Filter fields (not saved to model)
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        required=False,
        label='Department (Filter)',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'hx-get': reverse_lazy('finance:load_functions'),
            'hx-target': '#id_function',
            'hx-trigger': 'change',
        })
    )
    function = forms.ModelChoiceField(
        queryset=FunctionCode.objects.none(),
        required=False,
        label='Function (Filter)',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'hx-get': reverse_lazy('finance:load_budget_heads_options'),
            'hx-target': '#budget-head-options',
            'hx-trigger': 'change',
            'hx-include': '[name=department]',
        })
    )
    
    class Meta:
        model = Voucher
        fields = ['voucher_type', 'date', 'fund', 'payee', 'reference_no', 'description']
        widgets = {
            'voucher_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'fund': forms.Select(attrs={
                'class': 'form-select'
            }),
            'payee': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Payee name (optional)'
            }),
            'reference_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Reference number (optional)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of the transaction'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # Load departments
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')
        
        # RESTRICT voucher_type choices to only Manual types (exclude automated BP/BR)
        MANUAL_TYPES = [
            ('JV', 'Journal Voucher'),
            ('PV', 'Payment Voucher'),
            ('RV', 'Receipt Voucher'),
            ('CV', 'Contra Voucher'),
        ]
        self.fields['voucher_type'].choices = MANUAL_TYPES
        self.fields['voucher_type'].initial = 'PV'
        
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
        
        # Filter funds by organization if available
        if self.organization:
            # Assuming Fund model has organization field or is global
            # For now, keep all funds available
            pass
    
    def clean_date(self):
        """Validate that date falls within a fiscal year."""
        date = self.cleaned_data['date']
        
        # Check if fiscal year exists for the date
        fiscal_year = FiscalYear.objects.filter(
            start_date__lte=date,
            end_date__gte=date
        ).first()
        
        if not fiscal_year:
            raise ValidationError(
                _('No fiscal year found for the selected date. Please select a date within an active fiscal year.')
            )
        
        # Note: We do NOT check is_locked here because:
        # - Locked FY = Budget modifications blocked
        # - Transactions (vouchers, bills, payments) should still be allowed
        
        return date


class JournalEntryForm(forms.ModelForm):
    """
    Form for individual Journal Entry lines in a Voucher.
    
    Each line posts to a BudgetHead (GL account) with either a debit or credit.
    """
    
    class Meta:
        model = JournalEntry
        fields = ['budget_head', 'description', 'debit', 'credit']
        widgets = {
            'budget_head': forms.Select(attrs={
                'class': 'form-select searchable-select-ajax',
                'data-placeholder': 'Type to search budget heads...'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Line description'
            }),
            'debit': forms.NumberInput(attrs={
                'class': 'form-control debit-amount',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'credit': forms.NumberInput(attrs={
                'class': 'form-control credit-amount',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # For AJAX Select2, we need to handle both display and validation
        if self.instance and self.instance.pk and self.instance.budget_head:
            # Editing existing entry - include the current budget head
            self.fields['budget_head'].queryset = BudgetHead.objects.filter(
                id=self.instance.budget_head.id
            ).select_related('global_head', 'function')
        elif self.data:
            # Form submitted (POST) - include the submitted budget head for validation
            # In a formset, the field name has a prefix like 'entries-0-budget_head'
            budget_head_id = None
            
            # Try to get the budget_head value from data
            # First try without prefix (for standalone forms)
            if 'budget_head' in self.data:
                budget_head_id = self.data.get('budget_head')
            # Then try with prefix (for formsets)
            elif self.prefix and f'{self.prefix}-budget_head' in self.data:
                budget_head_id = self.data.get(f'{self.prefix}-budget_head')
            
            if budget_head_id:
                try:
                    budget_head_id = int(budget_head_id)
                    self.fields['budget_head'].queryset = BudgetHead.objects.filter(
                        id=budget_head_id,
                        posting_allowed=True,
                        is_active=True
                    ).select_related('global_head', 'function')
                except (ValueError, TypeError):
                    # Invalid ID submitted
                    self.fields['budget_head'].queryset = BudgetHead.objects.none()
            else:
                self.fields['budget_head'].queryset = BudgetHead.objects.none()
        else:
            # New entry - empty queryset, Select2 will load via AJAX
            self.fields['budget_head'].queryset = BudgetHead.objects.none()
    
    def clean(self):
        """Validate that either debit or credit is entered, and check budget."""
        cleaned_data = super().clean()
        debit = cleaned_data.get('debit', 0)
        credit = cleaned_data.get('credit', 0)
        budget_head = cleaned_data.get('budget_head')
        
        if debit and credit:
            raise ValidationError(
                _('A line cannot have both debit and credit. Enter one or the other.')
            )
        
        if not debit and not credit:
            raise ValidationError(
                _('Either debit or credit amount must be entered.')
            )
        
        # Budget control check for expenditure entries (credit > 0 as per action plan)
        if budget_head and credit > 0:
            from apps.budgeting.models import FiscalYear
            
            # Get fiscal year from form data or current
            # Since this is a line item, we rely on the parent voucher's date/FY presumably, 
            # but we don't have access to parent voucher date easily here without 'cleaned_data' context of parent form if avail.
            # We'll use current operating year as fallback/default 
            fiscal_year = FiscalYear.get_current_operating_year()
            
            if budget_head.budget_control:
                # Use self.organization which is passed in __init__
                available = budget_head.get_available_budget(fiscal_year, organization=self.organization)
                
                if credit > available:
                    raise ValidationError({
                        'credit': _(
                            'Insufficient budget. Amount: %(amount)s, Available: %(available)s'
                        ) % {
                            'amount': credit,
                            'available': available
                        }
                    })
        
        return cleaned_data
