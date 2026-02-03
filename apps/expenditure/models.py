"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Expenditure models for Bill Processing and Payment
             management. Implements the Procure-to-Pay cycle with
             Double-Entry Accounting and Hard Budget Constraints.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from django.db import models, transaction
from django.core.validators import MinValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.mixins import AuditLogMixin, StatusMixin, TenantAwareMixin, TimeStampedMixin
from apps.core.exceptions import BudgetExceededException, WorkflowTransitionException

if TYPE_CHECKING:
    from apps.users.models import CustomUser


class BillStatus(models.TextChoices):
    """
    Status choices for Bill workflow.
    
    DRAFT: Bill created but not yet submitted
    SUBMITTED: Bill submitted for approval
    MARKED_FOR_AUDIT: Bill marked for audit review
    AUDITED: Bill passed audit, ready for approval
    APPROVED: Bill approved, liability recorded in GL
    PAID: Payment issued against the bill
    REJECTED: Bill rejected in approval workflow
    RETURNED: Bill returned for corrections
    """
    DRAFT = 'DRAFT', _('Draft')
    SUBMITTED = 'SUBMITTED', _('Submitted for Approval')
    VERIFIED = 'VERIFIED', _('Verified by Accountant')
    MARKED_FOR_AUDIT = 'MARKED_FOR_AUDIT', _('Marked for Audit')
    AUDITED = 'AUDITED', _('Audited')
    APPROVED = 'APPROVED', _('Approved')
    PAID = 'PAID', _('Paid')
    REJECTED = 'REJECTED', _('Rejected')
    RETURNED = 'RETURNED', _('Returned for Corrections')


class BillType(models.TextChoices):
    REGULAR = 'REGULAR', _('Regular Bill')
    SALARY = 'SALARY', _('Monthly Salary')


class Payee(AuditLogMixin, StatusMixin, TenantAwareMixin):
    """
    Payee/Vendor Registry for the organization.
    
    Represents vendors, contractors, and employees who receive
    payments from the organization.
    
    Attributes:
        organization: The TMA/Organization (from TenantAwareMixin)
        name: Payee/Vendor name
        cnic_ntn: CNIC (for individuals) or NTN (for companies)
        address: Full address
        is_active: Whether payee is active
    """
    
    cnic_ntn_validator = RegexValidator(
        regex=r'^(\d{5}-\d{7}-\d{1}|\d{13}|\d{7}-\d{1})$',
        message=_('Enter a valid CNIC (XXXXX-XXXXXXX-X) or NTN (XXXXXXX-X).')
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Payee Name'),
        help_text=_('Full name of the vendor/contractor/employee.')
    )
    cnic_ntn = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('CNIC/NTN'),
        help_text=_('CNIC for individuals or NTN for companies.')
    )
    address = models.TextField(
        blank=True,
        verbose_name=_('Address'),
        help_text=_('Full mailing address.')
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Phone'),
        help_text=_('Contact phone number.')
    )
    email = models.EmailField(
        blank=True,
        verbose_name=_('Email'),
        help_text=_('Contact email address.')
    )
    bank_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Bank Name'),
        help_text=_('Name of the bank for payment.')
    )
    bank_account = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Bank Account'),
        help_text=_('Bank account number for payment.')
    )
    
    class Meta:
        verbose_name = _('Payee')
        verbose_name_plural = _('Payees')
        ordering = ['name']
        unique_together = ['organization', 'name']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self) -> str:
        return self.name


class BillLine(models.Model):
    """
    Line item for a Bill.
    Allows splitting a bill across multiple budget heads (e.g., Salary split by department).
    """
    bill = models.ForeignKey(
        'Bill',
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Bill')
    )
    budget_head = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='bill_lines',
        verbose_name=_('Budget Head'),
        help_text=_('Expense head to charge.')
    )
    description = models.CharField(
        max_length=255,
        verbose_name=_('Description'),
        help_text=_('Line item description.')
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Amount')
    )
    
    class Meta:
        verbose_name = _('Bill Line')
        verbose_name_plural = _('Bill Lines')
    
    def __str__(self) -> str:
        return f"{self.budget_head.code} - {self.amount}"


class Bill(AuditLogMixin, TenantAwareMixin):
    """
    Bill/Invoice representing a liability to be paid.
    
    The bill goes through a workflow: Draft -> Submitted -> Approved -> Paid.
    On approval, a Journal Voucher is created to record the liability:
        Dr Expense Head (gross_amount)
        Cr Accounts Payable (net_amount)
        Cr Tax Payable (tax_amount)
    
    Attributes:
        fiscal_year: The fiscal year this bill belongs to
        payee: The vendor/contractor being paid
        budget_head: The expense head to charge
        bill_date: Date of the bill/invoice
        bill_number: Vendor's invoice/reference number
        gross_amount: Total bill amount before tax deduction
        tax_amount: Tax deducted at source (Income Tax, GST)
        net_amount: Amount payable to vendor (gross - tax)
        status: Current workflow status
        liability_voucher: GL voucher recording the liability
    """
    
    fiscal_year = models.ForeignKey(
        'budgeting.FiscalYear',
        on_delete=models.PROTECT,
        related_name='bills',
        verbose_name=_('Fiscal Year')
    )
    payee = models.ForeignKey(
        Payee,
        on_delete=models.PROTECT,
        related_name='bills',
        verbose_name=_('Payee')
    )
    # Refactored: Budget Head moved to BillLine, but kept here for backward compatibility
    # This field is optional - new bills should use BillLine.budget_head instead
    budget_head = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='legacy_bills',
        verbose_name=_('Budget Head'),
        help_text=_('Expense head to charge (legacy field, use BillLine for new bills).'),
        null=True,
        blank=True
    )
    
    bill_date = models.DateField(
        verbose_name=_('Bill Date'),
        help_text=_('Date on the vendor invoice.')
    )
    bill_number = models.CharField(
        max_length=50,
        verbose_name=_('Bill/Invoice Number'),
        help_text=_('Vendor\'s invoice or reference number.')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Description of goods/services.')
    )
    gross_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Gross Amount'),
        help_text=_('Total bill amount before tax deduction.')
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Tax Amount'),
        help_text=_('Total tax deducted (Income Tax + GST).')
    )
    net_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Net Amount'),
        help_text=_('Amount payable to vendor (Gross - Tax).')
    )
    status = models.CharField(
        max_length=32,
        choices=BillStatus.choices,
        default=BillStatus.DRAFT,
        verbose_name=_('Status')
    )
    bill_type = models.CharField(
        max_length=20,
        choices=BillType.choices,
        default=BillType.REGULAR,
        verbose_name=_('Bill Type')
    )
    fund = models.ForeignKey(
        'finance.Fund',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bills',
        verbose_name=_('Fund')
    )
    salary_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Salary Month'),
        help_text=_('Month (1-12) for salary bills')
    )
    salary_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Salary Year'),
        help_text=_('Year for salary bills')
    )
    department = models.ForeignKey(
        'budgeting.Department',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bills',
        verbose_name=_('Department')
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Submitted At')
    )
    submitted_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='submitted_bills',
        verbose_name=_('Submitted By')
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    approved_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='approved_bills',
        verbose_name=_('Approved By')
    )
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Rejected At')
    )
    rejected_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rejected_bills',
        verbose_name=_('Rejected By')
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_('Rejection Reason')
    )
    liability_voucher = models.OneToOneField(
        'finance.Voucher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bill',
        verbose_name=_('Liability Voucher'),
        help_text=_('GL voucher recording the liability.')
    )
    
    class Meta:
        verbose_name = _('Bill')
        verbose_name_plural = _('Bills')
        ordering = ['-bill_date', '-created_at']
        indexes = [
            models.Index(fields=['organization', 'fiscal_year']),
            models.Index(fields=['status']),
            models.Index(fields=['bill_date']),
            models.Index(fields=['payee']),
        ]
    
    def __str__(self) -> str:
        return f"Bill #{self.id} - {self.payee.name} - Rs. {self.gross_amount}"
    
    def clean(self) -> None:
        """
        Validate that net_amount + tax_amount equals gross_amount.
        """
        if self.gross_amount and self.tax_amount is not None and self.net_amount:
            expected_net = self.gross_amount - self.tax_amount
            if self.net_amount != expected_net:
                raise ValidationError({
                    'net_amount': _(
                        f'Net amount ({self.net_amount}) must equal '
                        f'Gross amount ({self.gross_amount}) - Tax amount ({self.tax_amount}) = {expected_net}'
                    )
                })
    
    def save(self, *args, **kwargs) -> None:
        """Auto-calculate net_amount if not set."""
        if self.gross_amount and self.tax_amount is not None:
            if not self.net_amount or self.net_amount == Decimal('0.00'):
                self.net_amount = self.gross_amount - self.tax_amount
        self.clean()
        super().save(*args, **kwargs)
    
    def submit(self, user: 'CustomUser') -> None:
        """
        Submit the bill for approval.
        
        Args:
            user: The user submitting the bill.
            
        Raises:
            WorkflowTransitionException: If bill is not in DRAFT status.
        """
        if self.status != BillStatus.DRAFT:
            raise WorkflowTransitionException(
                f"Cannot submit bill. Current status is '{self.get_status_display()}'. "
                "Only DRAFT bills can be submitted."
            )
        
        self.status = BillStatus.SUBMITTED
        self.submitted_at = timezone.now()
        self.submitted_by = user
        self.save(update_fields=['status', 'submitted_at', 'submitted_by', 'updated_at'])

    @transaction.atomic
    def verify(self, user: 'CustomUser') -> None:
        """
        Verify the bill (Accountant Step).
        
        Args:
            user: The accountant verifying the bill.
            
        Raises:
            WorkflowTransitionException: If bill is not in SUBMITTED status.
        """
        if self.status != BillStatus.SUBMITTED:
            raise WorkflowTransitionException(
                f"Cannot verify bill. Current status is '{self.get_status_display()}'. "
                "Only SUBMITTED bills can be verified."
            )
        
        previous_status = self.status
        self.status = BillStatus.VERIFIED
        # We can store verified_by in updated_by for now (or add a dedicated field if needed)
        self.updated_by = user
        self.save(update_fields=['status', 'updated_at', 'updated_by'])
    
    @transaction.atomic
    def approve(self, user: 'CustomUser') -> None:
        """
        Approve the bill and create liability GL entries.
        
        This method:
        1. Validates the workflow transition
        2. For SALARY bills: Deducts budgets from all function/component allocations
        3. For REGULAR bills: Checks budget availability for EACH line
        4. Creates a Journal Voucher with:
           - Multiple Debits: Expense Head (line.amount) OR Single Debit for Salary
           - Credit: Accounts Payable (net_amount)
           - Credit: Tax Payable (tax_amount)
        5. Updates the BudgetAllocation spent_amount for all heads
        6. Updates bill status to APPROVED
        
        Args:
            user: The user approving the bill.
            
        Raises:
            WorkflowTransitionException: If bill is not in VERIFIED status.
            BudgetExceededException: If budget is insufficient.
        """
        from apps.finance.models import Voucher, VoucherType, JournalEntry, BudgetHead
        from apps.budgeting.models import BudgetAllocation
        
        # Validate workflow: Must be VERIFIED first
        if self.status != BillStatus.VERIFIED:
            raise WorkflowTransitionException(
                f"Cannot approve bill. Current status is '{self.get_status_display()}'. "
                "Only VERIFIED bills can be approved. Please verify first."
            )
        
        # Handle SALARY bills differently
        if hasattr(self, 'bill_type') and self.bill_type == 'SALARY':
            self._approve_salary_bill(user)
            return
        
        # Regular bill processing continues below...
        # Verify lines exist
        lines = self.lines.all()
        if not lines:
             raise ValidationError(_("Cannot approve a bill with no actions/lines."))

        # Validate total amount matches lines
        total_line_amount = sum(line.amount for line in lines)
        if total_line_amount != self.gross_amount:
             raise ValidationError(
                f"Line total ({total_line_amount}) does not match Bill Gross Amount ({self.gross_amount})."
            )

        # check budget for EACH line
        allocations_to_update = []
        
        for line in lines:
            try:
                allocation = BudgetAllocation.objects.get(
                    organization=self.organization,
                    fiscal_year=self.fiscal_year,
                    budget_head=line.budget_head
                )
            except BudgetAllocation.DoesNotExist:
                raise BudgetExceededException(
                    f"No budget allocation found for {line.budget_head} in {self.fiscal_year}."
                )
            
            # Hard Budget Constraint check
            if not allocation.can_spend(line.amount):
                available = allocation.get_available_budget()
                raise BudgetExceededException(
                    f"Insufficient budget for {line.budget_head}. Requested: Rs. {line.amount}, "
                    f"Available: Rs. {available}."
                )
            
            # Queue for update
            allocation.spent_amount += line.amount
            allocations_to_update.append(allocation)

        
        # Get system accounts
        try:
            ap_head = BudgetHead.objects.get(
                global_head__system_code='AP',
                is_active=True
            )
        except BudgetHead.DoesNotExist:
            raise ValidationError(
                "System account 'Accounts Payable' (AP) not configured. "
                "Please run 'python manage.py assign_system_codes' and create BudgetHead for AP."
            )
        except BudgetHead.MultipleObjectsReturned:
            # If multiple AP heads exist, get first active one
            ap_head = BudgetHead.objects.filter(
                global_head__system_code='AP',
                is_active=True
            ).first()
        
        tax_head = None
        if self.tax_amount > Decimal('0.00'):
            try:
                tax_head = BudgetHead.objects.get(
                    global_head__system_code='TAX_IT',
                    is_active=True
                )
            except BudgetHead.DoesNotExist:
                raise ValidationError(
                    "System account 'Income Tax' (TAX_IT) not configured. "
                    "Please run 'python manage.py assign_system_codes' and create BudgetHead for TAX_IT."
                )
            except BudgetHead.MultipleObjectsReturned:
                tax_head = BudgetHead.objects.filter(
                    global_head__system_code='TAX_IT',
                    is_active=True
                ).first()
        
        # Generate voucher number
        voucher_count = Voucher.objects.filter(
            organization=self.organization,
            fiscal_year=self.fiscal_year,
            voucher_type=VoucherType.JOURNAL
        ).count() + 1
        voucher_no = f"JV-{self.fiscal_year.year_name}-{voucher_count:04d}"
        
        # Create liability voucher
        voucher = Voucher.objects.create(
            organization=self.organization,
            voucher_no=voucher_no,
            fiscal_year=self.fiscal_year,
            date=timezone.now().date(),
            voucher_type=VoucherType.JOURNAL,
            fund=lines[0].budget_head.fund, # Use fund from first line (assuming single fund voucher)
            description=f"Liability for Bill #{self.id}: {self.payee.name} - {self.description[:100]}",
            created_by=user
        )
        
        # Debit: Expense Heads (Loop)
        for line in lines:
            JournalEntry.objects.create(
                voucher=voucher,
                budget_head=line.budget_head,
                description=f"Expense: {line.description[:100]}",
                debit=line.amount,
                credit=Decimal('0.00')
            )
        
        # Credit: Accounts Payable (net_amount)
        JournalEntry.objects.create(
            voucher=voucher,
            budget_head=ap_head,
            description=f"Clear payable: {self.payee.name}",
            debit=Decimal('0.00'),
            credit=self.net_amount
        )
        
        # Credit: Tax Head (tax_amount) - only if tax is applicable
        if tax_head and self.tax_amount > Decimal('0.00'):
            JournalEntry.objects.create(
                voucher=voucher,
                budget_head=tax_head,
                description=f"Tax withheld: Bill #{self.id}",
                debit=Decimal('0.00'),
                credit=self.tax_amount
            )
        
        # Post the voucher
        voucher.post_voucher(user)
        
        # Commit budget updates
        for allocation in allocations_to_update:
            allocation.save(update_fields=['spent_amount', 'updated_at'])
        
        # Update bill status
        self.status = BillStatus.APPROVED
        self.approved_at = timezone.now()
        self.approved_by = user
        self.liability_voucher = voucher
        self.save(update_fields=[
            'status', 'approved_at', 'approved_by', 
            'liability_voucher', 'updated_at'
        ])
    
    def _approve_salary_bill(self, user: 'CustomUser') -> None:
        """
        Approve a salary bill with automatic budget deductions.
        
        For salary bills, we:
        1. Deduct budgets from all function/component combinations
        2. Create a simple GL voucher (single debit to Salary Expense)
        3. Update bill status to APPROVED
        
        Args:
            user: The user approving the bill
        """
        from apps.expenditure.services_salary import deduct_salary_bill_budgets
        from apps.finance.models import Voucher, VoucherType, JournalEntry, BudgetHead
        
        # Deduct budgets across all functions and components
        try:
            deduction_count = deduct_salary_bill_budgets(self, user)
        except Exception as e:
            raise BudgetExceededException(f"Salary bill budget validation failed: {str(e)}")
        
        # Get the salary breakdown for GL entries
        from apps.expenditure.services_salary import SalaryBillGenerator, SALARY_COMPONENT_MAPPING
        from apps.finance.models import FunctionCode
        
        generator = SalaryBillGenerator(
            self.organization,
            self.fiscal_year,
            self.salary_month,
            self.salary_year
        )
        breakdown = generator.calculate_breakdown()
        
        # Get system accounts
        try:
            ap_head = BudgetHead.objects.get(
                global_head__system_code='AP',
                is_active=True
            )
        except BudgetHead.DoesNotExist:
            raise ValidationError(
                "System account 'Accounts Payable' (AP) not configured."
            )
        except BudgetHead.MultipleObjectsReturned:
            ap_head = BudgetHead.objects.filter(
                global_head__system_code='AP',
                is_active=True
            ).first()
        
        # Generate voucher number
        voucher_count = Voucher.objects.filter(
            organization=self.organization,
            fiscal_year=self.fiscal_year,
            voucher_type=VoucherType.JOURNAL
        ).count() + 1
        voucher_no = f"JV-{self.fiscal_year.year_name}-{voucher_count:04d}"
        
        # Create liability voucher
        voucher = Voucher.objects.create(
            organization=self.organization,
            voucher_no=voucher_no,
            fiscal_year=self.fiscal_year,
            date=timezone.now().date(),
            voucher_type=VoucherType.JOURNAL,
            fund=self.fund,
            description=f"Salary Bill - {self.description}",
            created_by=user
        )
        
        # Create FUNCTION-WISE GL entries for each salary component
        # This ensures the ledger shows function-wise breakdown for NAM reporting
        total_debited = Decimal('0.00')
        
        for func_code, func_data in breakdown['by_function'].items():
            function = FunctionCode.objects.filter(code=func_code).first()
            if not function:
                continue
            
            for comp_name, amount in func_data['components'].items():
                if amount <= 0:
                    continue
                
                account_code = SALARY_COMPONENT_MAPPING.get(comp_name)
                if not account_code:
                    continue
                
                # Find the budget head for this function + component
                budget_head = BudgetHead.objects.filter(
                    fund=self.fund,
                    function=function,
                    global_head__code=account_code,
                    is_active=True
                ).first()
                
                if budget_head:
                    # Create GL entry for this specific function + component
                    JournalEntry.objects.create(
                        voucher=voucher,
                        budget_head=budget_head,
                        description=f"{function.name} - {comp_name.replace('_', ' ').title()}",
                        debit=amount,
                        credit=Decimal('0.00')
                    )
                    total_debited += amount
        
        # Credit: Accounts Payable (net_amount)
        JournalEntry.objects.create(
            voucher=voucher,
            budget_head=ap_head,
            description=f"Salary payable: {self.description}",
            debit=Decimal('0.00'),
            credit=self.net_amount
        )
        
        # Credit: Tax (if any)
        if self.tax_amount > Decimal('0.00'):
            try:
                tax_head = BudgetHead.objects.get(
                    global_head__system_code='TAX_IT',
                    is_active=True
                )
            except BudgetHead.DoesNotExist:
                raise ValidationError("Income Tax account (TAX_IT) not configured.")
            except BudgetHead.MultipleObjectsReturned:
                tax_head = BudgetHead.objects.filter(
                    global_head__system_code='TAX_IT',
                    is_active=True
                ).first()
            
            JournalEntry.objects.create(
                voucher=voucher,
                budget_head=tax_head,
                description=f"Tax withheld: {self.description}",
                debit=Decimal('0.00'),
                credit=self.tax_amount
            )
        
        # Post the voucher
        voucher.post_voucher(user)
        
        # Update bill status
        self.status = BillStatus.APPROVED
        self.approved_at = timezone.now()
        self.approved_by = user
        self.liability_voucher = voucher
        self.save(update_fields=[
            'status', 'approved_at', 'approved_by',
            'liability_voucher', 'updated_at'
        ])
    
    def reject(self, user: 'CustomUser', reason: str) -> None:
        """
        Reject the bill.
        
        Args:
            user: The user rejecting the bill.
            reason: Reason for rejection.
            
        Raises:
            WorkflowTransitionException: If bill is not in SUBMITTED status.
        """
        if self.status != BillStatus.SUBMITTED:
            raise WorkflowTransitionException(
                f"Cannot reject bill. Current status is '{self.get_status_display()}'. "
                "Only SUBMITTED bills can be rejected."
            )
        
        self.status = BillStatus.REJECTED
        self.rejected_at = timezone.now()
        self.rejected_by = user
        self.rejection_reason = reason
        self.save(update_fields=[
            'status', 'rejected_at', 'rejected_by', 
            'rejection_reason', 'updated_at'
        ])


class Payment(AuditLogMixin, TenantAwareMixin):
    """
    Payment record representing cash outflow via cheque.
    
    When a payment is posted, a Payment Voucher is created:
        Dr Accounts Payable (net_amount)
        Cr Bank Account (net_amount)
    
    Attributes:
        bill: The approved bill being paid
        bank_account: The bank account from which payment is made
        cheque_number: Cheque number
        cheque_date: Date on the cheque
        payment_voucher: GL voucher recording the payment
    """
    
    bill = models.ForeignKey(
        Bill,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name=_('Bill')
    )
    bank_account = models.ForeignKey(
        'core.BankAccount',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name=_('Bank Account')
    )
    cheque_number = models.CharField(
        max_length=20,
        verbose_name=_('Cheque Number')
    )
    cheque_date = models.DateField(
        verbose_name=_('Cheque Date')
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Amount'),
        help_text=_('Payment amount (should equal bill net_amount).')
    )
    is_posted = models.BooleanField(
        default=False,
        verbose_name=_('Is Posted'),
        help_text=_('Whether payment has been posted to GL.')
    )
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Posted At')
    )
    posted_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='posted_payments',
        verbose_name=_('Posted By')
    )
    payment_voucher = models.OneToOneField(
        'finance.Voucher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment',
        verbose_name=_('Payment Voucher'),
        help_text=_('GL voucher recording the payment.')
    )
    
    class Meta:
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')
        ordering = ['-cheque_date', '-created_at']
        indexes = [
            models.Index(fields=['organization']),
            models.Index(fields=['cheque_date']),
            models.Index(fields=['is_posted']),
        ]
    
    def __str__(self) -> str:
        return f"Payment #{self.id} - Cheque {self.cheque_number} - Rs. {self.amount}"
    
    def clean(self) -> None:
        """Validate payment amount matches bill net_amount."""
        if self.bill and self.amount:
            if self.amount != self.bill.net_amount:
                raise ValidationError({
                    'amount': _(
                        f'Payment amount ({self.amount}) must equal '
                        f'bill net amount ({self.bill.net_amount}).'
                    )
                })
        
        if self.bill and self.bill.status != BillStatus.APPROVED:
            raise ValidationError({
                'bill': _('Only APPROVED bills can be paid.')
            })
    
    @transaction.atomic
    def post(self, user: 'CustomUser') -> None:
        """
        Post the payment and create GL entries.
        
        This method:
        1. Creates a Payment Voucher with:
           - Debit: Accounts Payable (net_amount)
           - Credit: Bank GL Code (net_amount)
        2. Updates bill status to PAID
        3. Marks payment as posted
        
        Args:
            user: The user posting the payment.
            
        Raises:
            ValidationError: If payment is already posted or bill not approved.
        """
        from apps.finance.models import Voucher, VoucherType, JournalEntry, BudgetHead
        
        if self.is_posted:
            raise ValidationError(_('Payment is already posted.'))
        
        if self.bill.status != BillStatus.APPROVED:
            raise ValidationError(
                _('Cannot post payment. Bill status must be APPROVED.')
            )
        
        # Get system accounts
        try:
            ap_head = BudgetHead.objects.get(
                global_head__system_code='AP',
                is_active=True
            )
        except BudgetHead.DoesNotExist:
            raise ValidationError(
                "System account 'Accounts Payable' (AP) not configured. "
                "Please run 'python manage.py assign_system_codes' and create BudgetHead for AP."
            )
        except BudgetHead.MultipleObjectsReturned:
            ap_head = BudgetHead.objects.filter(
                global_head__system_code='AP',
                is_active=True
            ).first()
        
        # Get bank GL code
        bank_gl = self.bank_account.gl_code
        
        # Generate voucher number
        voucher_count = Voucher.objects.filter(
            organization=self.organization,
            fiscal_year=self.bill.fiscal_year,
            voucher_type=VoucherType.PAYMENT
        ).count() + 1
        voucher_no = f"PV-{self.bill.fiscal_year.year_name}-{voucher_count:04d}"
        
        # Create payment voucher
        voucher = Voucher.objects.create(
            organization=self.organization,
            voucher_no=voucher_no,
            fiscal_year=self.bill.fiscal_year,
            date=self.cheque_date,
            voucher_type=VoucherType.PAYMENT,
            # fund=self.bill.budget_head.fund, # old way
            fund=self.bill.lines.first().budget_head.fund, # new way: use fund from first line (Refinement needed if multi-fund)
            description=f"Payment for Bill #{self.bill.id}: {self.bill.payee.name} - Cheque #{self.cheque_number}",
            created_by=user
        )
        
        # Debit: Accounts Payable (net_amount)
        JournalEntry.objects.create(
            voucher=voucher,
            budget_head=ap_head,
            description=f"Clear payable: {self.bill.payee.name}",
            debit=self.amount,
            credit=Decimal('0.00')
        )
        
        # Credit: Bank Account (net_amount)
        JournalEntry.objects.create(
            voucher=voucher,
            budget_head=bank_gl,
            description=f"Bank payment: Cheque #{self.cheque_number}",
            debit=Decimal('0.00'),
            credit=self.amount
        )
        
        # Post the voucher
        voucher.post_voucher(user)
        
        # Update payment
        self.is_posted = True
        self.posted_at = timezone.now()
        self.posted_by = user
        self.payment_voucher = voucher
        self.save(update_fields=[
            'is_posted', 'posted_at', 'posted_by', 
            'payment_voucher', 'updated_at'
        ])
        
        # Update bill status to PAID
        self.bill.status = BillStatus.PAID
        self.bill.save(update_fields=['status', 'updated_at'])
