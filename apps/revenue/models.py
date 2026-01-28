"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Revenue models for Demand (Challan) and Collection (Receipt)
             management. Implements the Revenue Cycle with Double-Entry
             Accounting for Accounts Receivable.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from django.db import models, transaction
from django.db.models import Sum
from django.core.validators import MinValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.mixins import AuditLogMixin, StatusMixin, TenantAwareMixin, TimeStampedMixin
from apps.core.exceptions import WorkflowTransitionException

if TYPE_CHECKING:
    from apps.users.models import CustomUser


class DemandStatus(models.TextChoices):
    """
    Status choices for RevenueDemand workflow.
    
    DRAFT: Demand created but not yet posted
    POSTED: Demand posted, receivable recorded in GL
    PAID: Full payment received
    PARTIAL: Partial payment received
    CANCELLED: Demand cancelled/voided
    """
    DRAFT = 'DRAFT', _('Draft')
    POSTED = 'POSTED', _('Posted')
    PARTIAL = 'PARTIAL', _('Partially Paid')
    PAID = 'PAID', _('Fully Paid')
    CANCELLED = 'CANCELLED', _('Cancelled')


class CollectionStatus(models.TextChoices):
    """
    Status choices for RevenueCollection.
    
    DRAFT: Collection recorded but not yet posted
    POSTED: Collection posted to GL
    CANCELLED: Collection cancelled/voided
    """
    DRAFT = 'DRAFT', _('Draft')
    POSTED = 'POSTED', _('Posted')
    CANCELLED = 'CANCELLED', _('Cancelled')


class Payer(AuditLogMixin, StatusMixin, TenantAwareMixin):
    """
    Payer Registry - Citizens, Entities, or Organizations that pay revenue.
    
    Represents taxpayers, shop renters, license holders, etc.
    
    Attributes:
        organization: The TMA/Organization (from TenantAwareMixin)
        name: Payer name (individual or entity)
        cnic_ntn: CNIC (for individuals) or NTN (for companies)
        contact_no: Phone number
        address: Full address
        is_active: Whether payer is active
    """
    
    cnic_ntn_validator = RegexValidator(
        regex=r'^(\d{5}-\d{7}-\d{1}|\d{13}|\d{7}-\d{1})$',
        message=_('Enter a valid CNIC (XXXXX-XXXXXXX-X) or NTN (XXXXXXX-X).')
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Payer Name'),
        help_text=_('Full name of the citizen/entity.')
    )
    cnic_ntn = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('CNIC/NTN'),
        help_text=_('CNIC for individuals or NTN for companies.')
    )
    contact_no = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Contact Number'),
        help_text=_('Phone/mobile number.')
    )
    address = models.TextField(
        blank=True,
        verbose_name=_('Address'),
        help_text=_('Full mailing address.')
    )
    email = models.EmailField(
        blank=True,
        verbose_name=_('Email'),
        help_text=_('Contact email address.')
    )
    
    class Meta:
        verbose_name = _('Payer')
        verbose_name_plural = _('Payers')
        ordering = ['name']
        unique_together = ['organization', 'name']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['name']),
            models.Index(fields=['cnic_ntn']),
        ]
    
    def __str__(self) -> str:
        return self.name
    
    def get_total_demands(self) -> Decimal:
        """Get total amount of all demands for this payer."""
        result = self.demands.filter(
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL, DemandStatus.PAID]
        ).aggregate(total=Sum('amount'))
        return result['total'] or Decimal('0.00')
    
    def get_total_collections(self) -> Decimal:
        """Get total amount collected from this payer."""
        result = RevenueCollection.objects.filter(
            demand__payer=self,
            status=CollectionStatus.POSTED
        ).aggregate(total=Sum('amount_received'))
        return result['total'] or Decimal('0.00')
    
    def get_outstanding_balance(self) -> Decimal:
        """Get outstanding balance for this payer."""
        return self.get_total_demands() - self.get_total_collections()


class RevenueDemand(AuditLogMixin, TenantAwareMixin):
    """
    Revenue Demand (Challan/Receivable).
    
    Represents an amount due from a payer for a specific revenue type.
    On posting, creates an accrual entry:
        Dr Accounts Receivable (AR) = amount
        Cr Revenue Head = amount
    
    Attributes:
        fiscal_year: The fiscal year this demand belongs to
        payer: The citizen/entity who owes
        budget_head: The revenue head (must be account_type='REV')
        challan_no: Unique challan/demand number
        issue_date: Date demand was issued
        due_date: Payment due date
        amount: Demand amount
        period_description: Period covered (e.g., "Jan 2026 Rent")
        status: Current workflow status
        accrual_voucher: GL voucher recording the receivable
    """
    
    fiscal_year = models.ForeignKey(
        'budgeting.FiscalYear',
        on_delete=models.PROTECT,
        related_name='revenue_demands',
        verbose_name=_('Fiscal Year')
    )
    payer = models.ForeignKey(
        Payer,
        on_delete=models.PROTECT,
        related_name='demands',
        verbose_name=_('Payer')
    )
    budget_head = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='revenue_demands',
        verbose_name=_('Revenue Head'),
        help_text=_('Revenue type/head for this demand.')
    )
    challan_no = models.CharField(
        max_length=50,
        verbose_name=_('Challan Number'),
        help_text=_('Unique demand/challan number.')
    )
    issue_date = models.DateField(
        verbose_name=_('Issue Date'),
        help_text=_('Date demand was issued.')
    )
    due_date = models.DateField(
        verbose_name=_('Due Date'),
        help_text=_('Payment due date.')
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Demand Amount'),
        help_text=_('Total amount due.')
    )
    period_description = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Period Description'),
        help_text=_('Period covered (e.g., "Jan 2026 Rent", "Q1 2026 License Fee").')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Additional notes or description.')
    )
    status = models.CharField(
        max_length=15,
        choices=DemandStatus.choices,
        default=DemandStatus.DRAFT,
        verbose_name=_('Status')
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
        related_name='posted_demands',
        verbose_name=_('Posted By')
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Cancelled At')
    )
    cancelled_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='cancelled_demands',
        verbose_name=_('Cancelled By')
    )
    cancellation_reason = models.TextField(
        blank=True,
        verbose_name=_('Cancellation Reason')
    )
    accrual_voucher = models.OneToOneField(
        'finance.Voucher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revenue_demand',
        verbose_name=_('Accrual Voucher'),
        help_text=_('GL voucher recording the receivable.')
    )
    
    class Meta:
        verbose_name = _('Revenue Demand')
        verbose_name_plural = _('Revenue Demands')
        ordering = ['-issue_date', '-created_at']
        unique_together = ['organization', 'fiscal_year', 'challan_no']
        indexes = [
            models.Index(fields=['organization', 'fiscal_year']),
            models.Index(fields=['status']),
            models.Index(fields=['issue_date']),
            models.Index(fields=['payer']),
            models.Index(fields=['challan_no']),
        ]
    
    def __str__(self) -> str:
        return f"Challan {self.challan_no} - {self.payer.name} - Rs. {self.amount}"
    
    def clean(self) -> None:
        """Validate that budget_head is a revenue account."""
        from apps.finance.models import AccountType
        
        if self.budget_head and self.budget_head.account_type != AccountType.REVENUE:
            raise ValidationError({
                'budget_head': _('Budget head must be a Revenue account type.')
            })
        
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValidationError({
                'due_date': _('Due date cannot be before issue date.')
            })
    
    def save(self, *args, **kwargs) -> None:
        """Validate before saving."""
        self.clean()
        super().save(*args, **kwargs)
    
    def get_total_collected(self) -> Decimal:
        """Get total amount collected against this demand."""
        result = self.collections.filter(
            status=CollectionStatus.POSTED
        ).aggregate(total=Sum('amount_received'))
        return result['total'] or Decimal('0.00')
    
    def get_outstanding_balance(self) -> Decimal:
        """Get remaining balance to be collected."""
        return self.amount - self.get_total_collected()
    
    def is_fully_paid(self) -> bool:
        """Check if demand is fully paid."""
        return self.get_total_collected() >= self.amount
    
    @transaction.atomic
    def post(self, user: 'CustomUser') -> None:
        """
        Post the demand and create accrual GL entry.
        
        Creates Journal Voucher:
            Dr Accounts Receivable (AR) = amount
            Cr Revenue Head = amount
        
        Args:
            user: The user posting the demand.
            
        Raises:
            WorkflowTransitionException: If demand is not in DRAFT status.
            ValidationError: If AR system head is not configured.
        """
        from apps.finance.models import Voucher, VoucherType, JournalEntry, BudgetHead, Fund
        
        if self.status != DemandStatus.DRAFT:
            raise WorkflowTransitionException(
                _('Demand can only be posted from Draft status.')
            )
        
        # Get the Accounts Receivable system head
        ar_head = BudgetHead.objects.filter(
            is_system_head=True,
            system_code='AR'
        ).first()
        
        if not ar_head:
            raise ValidationError(
                _('Accounts Receivable (AR) system head is not configured. '
                  'Please run the seed command or configure it manually.')
            )
        
        # Get default fund
        fund = Fund.objects.filter(is_active=True).first()
        if not fund:
            raise ValidationError(_('No active fund found.'))
        
        # Generate voucher number
        voucher_count = Voucher.objects.filter(
            organization=self.organization,
            fiscal_year=self.fiscal_year,
            voucher_type=VoucherType.JOURNAL
        ).count()
        voucher_no = f"JV-{self.fiscal_year.year_name}-{voucher_count + 1:04d}"
        
        # Create the accrual voucher
        voucher = Voucher.objects.create(
            organization=self.organization,
            voucher_no=voucher_no,
            fiscal_year=self.fiscal_year,
            date=self.issue_date,
            voucher_type=VoucherType.JOURNAL,
            fund=fund,
            description=f"Revenue Accrual: {self.challan_no} - {self.payer.name}"
        )
        
        # Debit: Accounts Receivable
        JournalEntry.objects.create(
            voucher=voucher,
            budget_head=ar_head,
            description=f"AR - {self.payer.name} - {self.period_description}",
            debit=self.amount,
            credit=Decimal('0.00')
        )
        
        # Credit: Revenue Head
        JournalEntry.objects.create(
            voucher=voucher,
            budget_head=self.budget_head,
            description=f"Revenue - {self.budget_head.tma_description}",
            debit=Decimal('0.00'),
            credit=self.amount
        )
        
        # Post the voucher
        voucher.post_voucher(user)
        
        # Update demand status
        self.accrual_voucher = voucher
        self.status = DemandStatus.POSTED
        self.posted_at = timezone.now()
        self.posted_by = user
        self.save(update_fields=[
            'accrual_voucher', 'status', 'posted_at', 'posted_by', 'updated_at'
        ])
    
    @transaction.atomic
    def cancel(self, user: 'CustomUser', reason: str) -> None:
        """
        Cancel the demand.
        
        Args:
            user: The user cancelling the demand.
            reason: Reason for cancellation.
            
        Raises:
            WorkflowTransitionException: If demand cannot be cancelled.
        """
        if self.status == DemandStatus.PAID:
            raise WorkflowTransitionException(
                _('Cannot cancel a fully paid demand.')
            )
        
        if self.status == DemandStatus.CANCELLED:
            raise WorkflowTransitionException(
                _('Demand is already cancelled.')
            )
        
        # Check if there are any collections
        if self.collections.filter(status=CollectionStatus.POSTED).exists():
            raise WorkflowTransitionException(
                _('Cannot cancel demand with existing collections. '
                  'Please cancel the collections first.')
            )
        
        # Unpost the accrual voucher if exists
        if self.accrual_voucher and self.accrual_voucher.is_posted:
            self.accrual_voucher.unpost_voucher()
        
        self.status = DemandStatus.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.cancellation_reason = reason
        self.save(update_fields=[
            'status', 'cancelled_at', 'cancelled_by', 
            'cancellation_reason', 'updated_at'
        ])


class RevenueCollection(AuditLogMixin, TenantAwareMixin):
    """
    Revenue Collection (Receipt).
    
    Records payment received against a demand.
    On posting, creates a receipt entry:
        Dr Bank Account = amount_received
        Cr Accounts Receivable (AR) = amount_received
    
    Attributes:
        demand: The demand being paid against
        bank_account: Bank account receiving the payment
        receipt_date: Date payment was received
        receipt_no: Receipt number
        instrument_type: Cash, Cheque, Online, etc.
        instrument_no: Cheque number or reference
        amount_received: Amount collected
        status: Collection status
        receipt_voucher: GL voucher recording the receipt
    """
    
    class InstrumentType(models.TextChoices):
        """Payment instrument types."""
        CASH = 'CASH', _('Cash')
        CHEQUE = 'CHEQUE', _('Cheque')
        ONLINE = 'ONLINE', _('Online Transfer')
        DD = 'DD', _('Demand Draft')
        PO = 'PO', _('Pay Order')
    
    demand = models.ForeignKey(
        RevenueDemand,
        on_delete=models.PROTECT,
        related_name='collections',
        verbose_name=_('Demand')
    )
    bank_account = models.ForeignKey(
        'core.BankAccount',
        on_delete=models.PROTECT,
        related_name='revenue_collections',
        verbose_name=_('Bank Account'),
        help_text=_('Bank account receiving the payment.')
    )
    receipt_date = models.DateField(
        verbose_name=_('Receipt Date'),
        help_text=_('Date payment was received.')
    )
    receipt_no = models.CharField(
        max_length=50,
        verbose_name=_('Receipt Number'),
        help_text=_('Unique receipt number.')
    )
    instrument_type = models.CharField(
        max_length=10,
        choices=InstrumentType.choices,
        default=InstrumentType.CASH,
        verbose_name=_('Instrument Type')
    )
    instrument_no = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Instrument Number'),
        help_text=_('Cheque number or transaction reference.')
    )
    amount_received = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Amount Received'),
        help_text=_('Amount collected.')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks'),
        help_text=_('Additional notes.')
    )
    status = models.CharField(
        max_length=15,
        choices=CollectionStatus.choices,
        default=CollectionStatus.DRAFT,
        verbose_name=_('Status')
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
        related_name='posted_collections',
        verbose_name=_('Posted By')
    )
    receipt_voucher = models.OneToOneField(
        'finance.Voucher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revenue_collection',
        verbose_name=_('Receipt Voucher'),
        help_text=_('GL voucher recording the receipt.')
    )
    
    class Meta:
        verbose_name = _('Revenue Collection')
        verbose_name_plural = _('Revenue Collections')
        ordering = ['-receipt_date', '-created_at']
        unique_together = ['organization', 'receipt_no']
        indexes = [
            models.Index(fields=['organization', 'receipt_date']),
            models.Index(fields=['status']),
            models.Index(fields=['demand']),
            models.Index(fields=['receipt_no']),
        ]
    
    def __str__(self) -> str:
        return f"Receipt {self.receipt_no} - Rs. {self.amount_received}"
    
    def clean(self) -> None:
        """Validate collection amount."""
        if self.demand and self.amount_received:
            outstanding = self.demand.get_outstanding_balance()
            # Allow for existing collection being edited
            if self.pk:
                existing = RevenueCollection.objects.filter(pk=self.pk).first()
                if existing and existing.status == CollectionStatus.POSTED:
                    outstanding += existing.amount_received
            
            if self.amount_received > outstanding:
                raise ValidationError({
                    'amount_received': _(
                        f'Amount ({self.amount_received}) exceeds outstanding balance ({outstanding}).'
                    )
                })
    
    def save(self, *args, **kwargs) -> None:
        """Set organization from demand and validate."""
        if self.demand and not self.organization_id:
            self.organization = self.demand.organization
        self.clean()
        super().save(*args, **kwargs)
    
    @transaction.atomic
    def post(self, user: 'CustomUser') -> None:
        """
        Post the collection and create receipt GL entry.
        
        Creates Receipt Voucher:
            Dr Bank Account = amount_received
            Cr Accounts Receivable (AR) = amount_received
        
        Also updates demand status if fully paid.
        
        Args:
            user: The user posting the collection.
            
        Raises:
            WorkflowTransitionException: If collection is not in DRAFT status.
            ValidationError: If AR system head is not configured.
        """
        from apps.finance.models import Voucher, VoucherType, JournalEntry, BudgetHead, Fund
        
        if self.status != CollectionStatus.DRAFT:
            raise WorkflowTransitionException(
                _('Collection can only be posted from Draft status.')
            )
        
        if self.demand.status not in [DemandStatus.POSTED, DemandStatus.PARTIAL]:
            raise WorkflowTransitionException(
                _('Cannot post collection for a demand that is not Posted or Partially Paid.')
            )
        
        # Get the Accounts Receivable system head
        ar_head = BudgetHead.objects.filter(
            is_system_head=True,
            system_code='AR'
        ).first()
        
        if not ar_head:
            raise ValidationError(
                _('Accounts Receivable (AR) system head is not configured.')
            )
        
        # Get bank account's GL head
        if not self.bank_account.gl_code:
            raise ValidationError(
                _('Bank account does not have a GL code configured.')
            )
        
        # Get default fund
        fund = Fund.objects.filter(is_active=True).first()
        if not fund:
            raise ValidationError(_('No active fund found.'))
        
        # Generate voucher number
        voucher_count = Voucher.objects.filter(
            organization=self.organization,
            fiscal_year=self.demand.fiscal_year,
            voucher_type=VoucherType.RECEIPT
        ).count()
        voucher_no = f"RV-{self.demand.fiscal_year.year_name}-{voucher_count + 1:04d}"
        
        # Create the receipt voucher
        voucher = Voucher.objects.create(
            organization=self.organization,
            voucher_no=voucher_no,
            fiscal_year=self.demand.fiscal_year,
            date=self.receipt_date,
            voucher_type=VoucherType.RECEIPT,
            fund=fund,
            description=f"Revenue Receipt: {self.receipt_no} - {self.demand.payer.name}"
        )
        
        # Debit: Bank Account
        JournalEntry.objects.create(
            voucher=voucher,
            budget_head=self.bank_account.gl_code,
            description=f"Bank - {self.bank_account.account_name}",
            debit=self.amount_received,
            credit=Decimal('0.00')
        )
        
        # Credit: Accounts Receivable
        JournalEntry.objects.create(
            voucher=voucher,
            budget_head=ar_head,
            description=f"AR - {self.demand.payer.name}",
            debit=Decimal('0.00'),
            credit=self.amount_received
        )
        
        # Post the voucher
        voucher.post_voucher(user)
        
        # Update collection status
        self.receipt_voucher = voucher
        self.status = CollectionStatus.POSTED
        self.posted_at = timezone.now()
        self.posted_by = user
        self.save(update_fields=[
            'receipt_voucher', 'status', 'posted_at', 'posted_by', 'updated_at'
        ])
        
        # Update demand status based on total collected
        if self.demand.is_fully_paid():
            self.demand.status = DemandStatus.PAID
        else:
            self.demand.status = DemandStatus.PARTIAL
        self.demand.save(update_fields=['status', 'updated_at'])
    
    @transaction.atomic
    def cancel(self, user: 'CustomUser', reason: str = '') -> None:
        """
        Cancel the collection.
        
        Args:
            user: The user cancelling the collection.
            reason: Reason for cancellation.
            
        Raises:
            WorkflowTransitionException: If collection cannot be cancelled.
        """
        if self.status == CollectionStatus.CANCELLED:
            raise WorkflowTransitionException(
                _('Collection is already cancelled.')
            )
        
        # Unpost the receipt voucher if exists
        if self.receipt_voucher and self.receipt_voucher.is_posted:
            self.receipt_voucher.unpost_voucher()
        
        self.status = CollectionStatus.CANCELLED
        self.save(update_fields=['status', 'updated_at'])
        
        # Update demand status - recalculate
        if self.demand.get_total_collected() <= Decimal('0.00'):
            self.demand.status = DemandStatus.POSTED
        elif self.demand.is_fully_paid():
            self.demand.status = DemandStatus.PAID
        else:
            self.demand.status = DemandStatus.PARTIAL
        self.demand.save(update_fields=['status', 'updated_at'])
