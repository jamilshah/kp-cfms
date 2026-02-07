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
from typing import Optional, Dict, Any, TYPE_CHECKING
from django.db import models, transaction
from django.db.models import Sum
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
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
        validators=[cnic_ntn_validator],
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
        validators=[
            MinValueValidator(Decimal('0.01')),
            MaxValueValidator(Decimal('9999999999999.99'))  # Max for 15 digits, 2 decimals
        ],
        verbose_name=_('Demand Amount'),
        help_text=_('Principal demand amount (excluding penalty).')
    )
    apply_penalty = models.BooleanField(
        default=False,
        verbose_name=_('Apply Late Payment Penalty'),
        help_text=_('Whether to calculate penalty for late payment.')
    )
    penalty_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00'))
        ],
        verbose_name=_('Penalty Rate (% per day)'),
        help_text=_('Daily penalty rate as percentage of principal amount.')
    )
    penalty_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('9999999999999.99'))
        ],
        verbose_name=_('Penalty Amount'),
        help_text=_('Calculated late payment penalty.')
    )
    grace_period_days = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(365)],
        verbose_name=_('Grace Period (Days)'),
        help_text=_('Number of days after due date before penalty starts (0 = no grace period).')
    )
    max_penalty_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('500.00'))
        ],
        verbose_name=_('Max Penalty (% of Principal)'),
        help_text=_('Maximum penalty as percentage of principal amount (e.g., 50 = penalty cannot exceed 50% of principal).')
    )
    penalty_waived = models.BooleanField(
        default=False,
        verbose_name=_('Penalty Waived'),
        help_text=_('Whether penalty has been waived by management.')
    )
    waived_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='waived_demand_penalties',
        verbose_name=_('Waived By')
    )
    waived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Waived At')
    )
    waiver_reason = models.TextField(
        blank=True,
        verbose_name=_('Waiver Reason')
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
            models.Index(fields=['budget_head']),
            models.Index(fields=['posted_at']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self) -> str:
        return f"Challan {self.challan_no} - {self.payer.name} - Rs. {self.amount}"
    
    def clean(self) -> None:
        """Enhanced validation for revenue demands."""
        super().clean()
        from apps.finance.models import AccountType
        
        # 1. Budget head validation
        if self.budget_head and self.budget_head.account_type != AccountType.REVENUE:
            raise ValidationError({
                'budget_head': _('Budget head must be a Revenue account type.')
            })
        
        # 2. Date validation
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValidationError({
                'due_date': _('Due date cannot be before issue date.')
            })
        
        # 3. Fiscal year validation
        if self.issue_date and self.fiscal_year:
            if not (self.fiscal_year.start_date <= self.issue_date <= self.fiscal_year.end_date):
                raise ValidationError({
                    'issue_date': _(f'Issue date must be within fiscal year {self.fiscal_year.year_name}.')
                })
        
        # 4. Amount validation
        if self.amount and self.amount <= Decimal('0'):
            raise ValidationError({
                'amount': _('Amount must be greater than zero.')
            })
        
        # 5. Payer active status validation
        if self.payer and not self.payer.is_active:
            raise ValidationError({
                'payer': _('Cannot create demand for inactive payer.')
            })
    
    def save(self, *args, **kwargs) -> None:
        """Validate before saving and create audit trail."""
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            # Track status changes for audit
            try:
                old_instance = RevenueDemand.objects.get(pk=self.pk)
                old_status = old_instance.status
            except RevenueDemand.DoesNotExist:
                pass
        
        self.clean()
        super().save(*args, **kwargs)
        
        # Create audit trail entry
        if is_new:
            # New demand created
            from apps.revenue.notifications import RevenueNotifications
            RevenueNotifications.notify_demand_created(self)
    
    def get_total_collected(self) -> Decimal:
        """Get total amount collected against this demand."""
        result = self.collections.filter(
            status=CollectionStatus.POSTED
        ).aggregate(total=Sum('amount_received'))
        return result['total'] or Decimal('0.00')
    
    def get_outstanding_balance(self) -> Decimal:
        """Get remaining balance to be collected (principal only)."""
        return self.amount - self.get_total_collected()
    
    def get_days_overdue(self, as_of_date=None) -> int:
        """
        Get number of days the demand is overdue.
        
        Args:
            as_of_date: Date to calculate from (defaults to today)
            
        Returns:
            Number of days overdue (0 if not overdue)
        """
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        if self.status not in [DemandStatus.POSTED, DemandStatus.PARTIAL]:
            return 0
        
        if as_of_date <= self.due_date:
            return 0
        
        return (as_of_date - self.due_date).days
    
    def calculate_penalty(self, as_of_date=None) -> Decimal:
        """
        Calculate late payment penalty based on days overdue with grace period and cap.
        
        Formula: penalty = (principal × penalty_rate × penalty_days) / 100
        Where penalty_days = days_overdue - grace_period_days
        
        Args:
            as_of_date: Date to calculate from (defaults to today)
            
        Returns:
            Calculated penalty amount (capped if max_penalty_percent is set)
        """
        # If penalty is waived, return 0
        if self.penalty_waived:
            return Decimal('0.00')
        
        # If penalty not enabled or rate is 0
        if not self.apply_penalty or self.penalty_rate <= Decimal('0'):
            return Decimal('0.00')
        
        days_overdue = self.get_days_overdue(as_of_date)
        if days_overdue <= 0:
            return Decimal('0.00')
        
        # Apply grace period
        penalty_days = days_overdue - self.grace_period_days
        if penalty_days <= 0:
            return Decimal('0.00')
        
        # Calculate penalty: (amount × rate × penalty_days) / 100
        penalty = (self.amount * self.penalty_rate * Decimal(str(penalty_days))) / Decimal('100')
        penalty = penalty.quantize(Decimal('0.01'))
        
        # Apply penalty cap
        max_penalty = (self.amount * self.max_penalty_percent) / Decimal('100')
        max_penalty = max_penalty.quantize(Decimal('0.01'))
        
        if penalty > max_penalty:
            penalty = max_penalty
        
        return penalty
    
    def update_penalty_amount(self, save=True) -> Decimal:
        """
        Update the stored penalty_amount field with current calculation.
        
        Args:
            save: Whether to save the model after updating
            
        Returns:
            Updated penalty amount
        """
        self.penalty_amount = self.calculate_penalty()
        if save:
            self.save(update_fields=['penalty_amount', 'updated_at'])
        return self.penalty_amount
    
    def get_total_amount_due(self, as_of_date=None) -> Decimal:
        """
        Get total amount due including principal and penalty.
        
        Args:
            as_of_date: Date to calculate penalty from (defaults to today)
            
        Returns:
            Total due (principal - collected + penalty)
        """
        outstanding_principal = self.get_outstanding_balance()
        current_penalty = self.calculate_penalty(as_of_date)
        return outstanding_principal + current_penalty
    
    def is_fully_paid(self) -> bool:
        """Check if demand is fully paid (principal only)."""
        return self.get_total_collected() >= self.amount
    
    @transaction.atomic
    def waive_penalty(self, user: 'CustomUser', reason: str) -> None:
        """
        Waive the penalty for this demand.
        
        Args:
            user: The user authorizing the waiver
            reason: Reason for waiving the penalty
            
        Raises:
            ValidationError: If penalty is not applicable or already waived
        """
        if not self.apply_penalty:
            raise ValidationError(_('This demand does not have penalty enabled.'))
        
        if self.penalty_waived:
            raise ValidationError(_('Penalty has already been waived for this demand.'))
        
        self.penalty_waived = True
        self.waived_by = user
        self.waived_at = timezone.now()
        self.waiver_reason = reason
        self.penalty_amount = Decimal('0.00')
        
        self.save(update_fields=[
            'penalty_waived', 'waived_by', 'waived_at', 
            'waiver_reason', 'penalty_amount', 'updated_at'
        ])
        
        # Log the waiver
        from apps.revenue.logging import RevenueLogger
        RevenueLogger.log_penalty_waived(self, user, reason)
    
    def get_penalty_info(self, as_of_date=None) -> Dict[str, Any]:
        """
        Get comprehensive penalty information.
        
        Args:
            as_of_date: Date to calculate from (defaults to today)
            
        Returns:
            Dictionary with penalty details
        """
        days_overdue = self.get_days_overdue(as_of_date)
        penalty_amount = self.calculate_penalty(as_of_date)
        
        # Calculate penalty days (after grace period)
        penalty_days = max(0, days_overdue - self.grace_period_days)
        
        # Calculate max penalty
        max_penalty = (self.amount * self.max_penalty_percent) / Decimal('100')
        max_penalty = max_penalty.quantize(Decimal('0.01'))
        
        # Check if penalty is capped
        uncapped_penalty = Decimal('0.00')
        is_capped = False
        if penalty_days > 0 and self.apply_penalty and self.penalty_rate > 0:
            uncapped_penalty = (self.amount * self.penalty_rate * Decimal(str(penalty_days))) / Decimal('100')
            uncapped_penalty = uncapped_penalty.quantize(Decimal('0.01'))
            is_capped = uncapped_penalty > max_penalty
        
        return {
            'enabled': self.apply_penalty,
            'rate': self.penalty_rate,
            'days_overdue': days_overdue,
            'grace_period': self.grace_period_days,
            'penalty_days': penalty_days,
            'penalty_amount': penalty_amount,
            'max_penalty': max_penalty,
            'max_penalty_percent': self.max_penalty_percent,
            'is_capped': is_capped,
            'uncapped_amount': uncapped_penalty,
            'waived': self.penalty_waived,
            'waived_by': self.waived_by,
            'waived_at': self.waived_at,
            'waiver_reason': self.waiver_reason,
        }
    
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
            global_head__system_code='AR'
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
            description=f"Revenue - {self.budget_head.name}",
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
        
        # Log the posting
        from apps.revenue.logging import RevenueLogger
        RevenueLogger.log_demand_posted(self, user)
        
        # Create audit trail
        from apps.revenue.notifications import RevenueNotifications
        RevenueNotifications.notify_demand_posted(self)
    
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
        
        # Log the cancellation
        from apps.revenue.logging import RevenueLogger
        RevenueLogger.log_demand_cancelled(self, user, reason)
        
        # Send cancellation notifications
        from apps.revenue.notifications import RevenueNotifications
        RevenueNotifications.notify_demand_cancelled(self, reason)


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
        validators=[
            MinValueValidator(Decimal('0.01')),
            MaxValueValidator(Decimal('9999999999999.99'))  # Max for 15 digits, 2 decimals
        ],
        verbose_name=_('Amount Received (Principal)'),
        help_text=_('Principal amount collected against demand.')
    )
    penalty_collected = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('9999999999999.99'))
        ],
        verbose_name=_('Penalty Collected'),
        help_text=_('Late payment penalty collected.')
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
            models.Index(fields=['posted_at']),
            models.Index(fields=['bank_account']),
        ]
    
    def __str__(self) -> str:
        total = self.amount_received + self.penalty_collected
        if self.penalty_collected > Decimal('0'):
            return f"Receipt {self.receipt_no} - Rs. {total} (Principal: {self.amount_received}, Penalty: {self.penalty_collected})"
        return f"Receipt {self.receipt_no} - Rs. {self.amount_received}"
    
    def get_total_collection(self) -> Decimal:
        """Get total amount collected (principal + penalty)."""
        return self.amount_received + self.penalty_collected
    
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
        """Set organization from demand, validate, and create audit trail."""
        is_new = self.pk is None
        
        if self.demand and not self.organization_id:
            self.organization = self.demand.organization
        self.clean()
        super().save(*args, **kwargs)
        
        # Notify about new collection
        if is_new:
            from apps.revenue.notifications import RevenueNotifications
            RevenueNotifications.notify_collection_received(self)
    
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
            global_head__system_code='AR'
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
            description=f"Bank - {self.bank_account.title}",
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
        
        # Log the posting
        from apps.revenue.logging import RevenueLogger
        RevenueLogger.log_collection_posted(self, user)
        
        # Send notifications
        from apps.revenue.notifications import RevenueNotifications
        RevenueNotifications.notify_collection_posted(self)
    
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
        
        # Log the cancellation
        from apps.revenue.logging import RevenueLogger
        RevenueLogger.log_collection_cancelled(self, user)
        
        # Send cancellation notifications
        from apps.revenue.notifications import RevenueNotifications
        RevenueNotifications.notify_collection_cancelled(self, reason)


class RevenueDemandAudit(TimeStampedMixin):
    """
    Audit trail for demand changes.
    
    Tracks all modifications to demands including creation, updates,
    posting, and cancellation with full user context.
    
    Attributes:
        demand: The demand being tracked
        action: Type of action (CREATED, UPDATED, POSTED, CANCELLED)
        old_status: Previous status before change
        new_status: New status after change
        changed_fields: JSON dictionary of changed field values
        changed_by: User who made the change
        changed_at: Timestamp of change
        ip_address: IP address of request
        user_agent: Browser/client user agent
        remarks: Optional notes about the change
    """
    
    class AuditAction(models.TextChoices):
        """Types of audit actions."""
        CREATED = 'CREATED', _('Created')
        UPDATED = 'UPDATED', _('Updated')
        POSTED = 'POSTED', _('Posted')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    demand = models.ForeignKey(
        RevenueDemand,
        on_delete=models.CASCADE,
        related_name='audit_trail',
        verbose_name=_('Demand')
    )
    action = models.CharField(
        max_length=20,
        choices=AuditAction.choices,
        verbose_name=_('Action')
    )
    old_status = models.CharField(
        max_length=15,
        blank=True,
        verbose_name=_('Old Status')
    )
    new_status = models.CharField(
        max_length=15,
        blank=True,
        verbose_name=_('New Status')
    )
    changed_fields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Changed Fields'),
        help_text=_('Dictionary of field names and their new values.')
    )
    changed_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        related_name='revenue_demand_audits',
        verbose_name=_('Changed By')
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Changed At')
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address')
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent'),
        help_text=_('Browser/client identifier.')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks'),
        help_text=_('Additional notes about this change.')
    )
    
    class Meta:
        verbose_name = _('Revenue Demand Audit')
        verbose_name_plural = _('Revenue Demand Audits')
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['demand', '-changed_at']),
            models.Index(fields=['changed_by', '-changed_at']),
            models.Index(fields=['action', '-changed_at']),
        ]
    
    def __str__(self) -> str:
        return (
            f"{self.get_action_display()} - "
            f"Demand {self.demand.challan_no} - "
            f"{self.changed_by.get_full_name()} - "
            f"{self.changed_at.strftime('%Y-%m-%d %H:%M')}"
        )


class RevenueCollectionAudit(TimeStampedMixin):
    """
    Audit trail for collection changes.
    
    Tracks all modifications to collections including creation, posting,
    and cancellation.
    """
    
    class AuditAction(models.TextChoices):
        """Types of audit actions."""
        CREATED = 'CREATED', _('Created')
        UPDATED = 'UPDATED', _('Updated')
        POSTED = 'POSTED', _('Posted')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    collection = models.ForeignKey(
        RevenueCollection,
        on_delete=models.CASCADE,
        related_name='audit_trail',
        verbose_name=_('Collection')
    )
    action = models.CharField(
        max_length=20,
        choices=AuditAction.choices,
        verbose_name=_('Action')
    )
    old_status = models.CharField(
        max_length=15,
        blank=True,
        verbose_name=_('Old Status')
    )
    new_status = models.CharField(
        max_length=15,
        blank=True,
        verbose_name=_('New Status')
    )
    changed_fields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Changed Fields')
    )
    changed_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        related_name='revenue_collection_audits',
        verbose_name=_('Changed By')
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Changed At')
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address')
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks')
    )
    
    class Meta:
        verbose_name = _('Revenue Collection Audit')
        verbose_name_plural = _('Revenue Collection Audits')
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['collection', '-changed_at']),
            models.Index(fields=['changed_by', '-changed_at']),
            models.Index(fields=['action', '-changed_at']),
        ]
    
    def __str__(self) -> str:
        return (
            f"{self.get_action_display()} - "
            f"Receipt {self.collection.receipt_no} - "
            f"{self.changed_by.get_full_name()} - "
            f"{self.changed_at.strftime('%Y-%m-%d %H:%M')}"
        )
