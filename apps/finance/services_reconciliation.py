"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Bank Reconciliation Engine for matching GL entries with
             bank statements and generating Bank Reconciliation
             Statement (BRS) summaries.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone

from apps.finance.models import (
    BankStatement, BankStatementLine, JournalEntry, BudgetHead
)


@dataclass
class ReconciliationResult:
    """Result of an auto-reconciliation run."""
    matched_count: int
    unmatched_statement_lines: int
    unmatched_gl_entries: int
    matched_pairs: List[Tuple[int, int]]  # (statement_line_id, journal_entry_id)


@dataclass
class BRSSummary:
    """Bank Reconciliation Statement summary."""
    balance_per_cash_book: Decimal
    add_unpresented_cheques: Decimal
    less_uncredited_deposits: Decimal
    calculated_bank_balance: Decimal
    actual_bank_balance: Decimal
    difference: Decimal
    unpresented_cheques_list: List[Dict[str, Any]]
    uncredited_deposits_list: List[Dict[str, Any]]
    unmatched_bank_items: List[Dict[str, Any]]


class ReconciliationEngine:
    """
    Engine for automating bank reconciliation.
    
    Provides methods for:
    - Auto-matching GL entries with bank statement lines
    - Manual matching of selected items
    - Generating BRS (Bank Reconciliation Statement) summaries
    
    Attributes:
        statement: The BankStatement being reconciled.
    """
    
    def __init__(self, statement: BankStatement) -> None:
        """
        Initialize the reconciliation engine.
        
        Args:
            statement: The BankStatement to reconcile.
        """
        self.statement = statement
        self.bank_account = statement.bank_account
        self.gl_code = self.bank_account.gl_code
    
    def get_unreconciled_gl_entries(self) -> List[JournalEntry]:
        """
        Get all unreconciled GL entries for this bank account.
        
        Returns:
            List of unreconciled JournalEntry objects.
        """
        return list(JournalEntry.objects.filter(
            budget_head=self.gl_code,
            is_reconciled=False,
            voucher__is_posted=True,
            voucher__organization=self.bank_account.organization
        ).select_related('voucher').order_by('voucher__date', 'id'))
    
    def get_unreconciled_statement_lines(self) -> List[BankStatementLine]:
        """
        Get all unreconciled statement lines.
        
        Returns:
            List of unreconciled BankStatementLine objects.
        """
        return list(self.statement.lines.filter(
            is_reconciled=False
        ).order_by('date', 'id'))
    
    @transaction.atomic
    def auto_reconcile(self) -> ReconciliationResult:
        """
        Automatically reconcile GL entries with statement lines.
        
        Matching Logic (Strong Match):
        - instrument_no (GL) matches ref_no (Bank) AND
        - amount matches (GL credit = Bank debit OR GL debit = Bank credit)
        
        Returns:
            ReconciliationResult with match statistics.
        """
        gl_entries = self.get_unreconciled_gl_entries()
        statement_lines = self.get_unreconciled_statement_lines()
        
        matched_pairs: List[Tuple[int, int]] = []
        matched_gl_ids: set = set()
        matched_line_ids: set = set()
        
        # Build lookup by instrument_no for GL entries
        gl_by_instrument: Dict[str, List[JournalEntry]] = {}
        for entry in gl_entries:
            if entry.instrument_no:
                key = entry.instrument_no.strip().upper()
                if key not in gl_by_instrument:
                    gl_by_instrument[key] = []
                gl_by_instrument[key].append(entry)
        
        # Attempt to match each statement line
        for line in statement_lines:
            if not line.ref_no:
                continue
            
            ref_key = line.ref_no.strip().upper()
            if ref_key not in gl_by_instrument:
                continue
            
            # Find matching GL entry by amount
            for entry in gl_by_instrument[ref_key]:
                if entry.id in matched_gl_ids:
                    continue
                
                # Check amount match:
                # Bank debit (withdrawal) = GL credit (money out from our books)
                # Bank credit (deposit) = GL debit (money in to our books)
                amount_match = False
                
                if line.debit > 0 and entry.credit == line.debit:
                    amount_match = True
                elif line.credit > 0 and entry.debit == line.credit:
                    amount_match = True
                
                if amount_match:
                    # Perform the match
                    line.match_with_entry(entry)
                    matched_pairs.append((line.id, entry.id))
                    matched_gl_ids.add(entry.id)
                    matched_line_ids.add(line.id)
                    break
        
        # Update statement status
        if self.statement.status == 'DRAFT':
            from apps.finance.models import StatementStatus
            self.statement.status = StatementStatus.RECONCILING
            self.statement.save(update_fields=['status', 'updated_at'])
        
        return ReconciliationResult(
            matched_count=len(matched_pairs),
            unmatched_statement_lines=len(statement_lines) - len(matched_line_ids),
            unmatched_gl_entries=len(gl_entries) - len(matched_gl_ids),
            matched_pairs=matched_pairs
        )
    
    @transaction.atomic
    def manual_match(
        self, 
        statement_line_ids: List[int], 
        journal_entry_ids: List[int]
    ) -> int:
        """
        Manually match selected statement lines with GL entries.
        
        Validates that the totals match before performing the match.
        
        Args:
            statement_line_ids: List of BankStatementLine IDs to match.
            journal_entry_ids: List of JournalEntry IDs to match.
            
        Returns:
            Number of pairs matched.
            
        Raises:
            ValidationError: If totals don't match or items already reconciled.
        """
        from django.core.exceptions import ValidationError
        
        # Fetch the items
        statement_lines = list(BankStatementLine.objects.filter(
            id__in=statement_line_ids,
            statement=self.statement,
            is_reconciled=False
        ))
        
        gl_entries = list(JournalEntry.objects.filter(
            id__in=journal_entry_ids,
            budget_head=self.gl_code,
            is_reconciled=False,
            voucher__is_posted=True
        ))
        
        if len(statement_lines) != len(statement_line_ids):
            raise ValidationError(
                _('Some statement lines are not found or already reconciled.')
            )
        
        if len(gl_entries) != len(journal_entry_ids):
            raise ValidationError(
                _('Some GL entries are not found or already reconciled.')
            )
        
        # Calculate totals
        stmt_total_debit = sum(l.debit for l in statement_lines)
        stmt_total_credit = sum(l.credit for l in statement_lines)
        gl_total_debit = sum(e.debit for e in gl_entries)
        gl_total_credit = sum(e.credit for e in gl_entries)
        
        # Validate matching totals
        # Bank debit should equal GL credit, Bank credit should equal GL debit
        if stmt_total_debit != gl_total_credit or stmt_total_credit != gl_total_debit:
            raise ValidationError(
                f'Totals do not match. '
                f'Statement: Dr {stmt_total_debit} / Cr {stmt_total_credit}. '
                f'GL: Dr {gl_total_debit} / Cr {gl_total_credit}. '
                f'Expected: Statement Dr = GL Cr, Statement Cr = GL Dr.'
            )
        
        # Match items 1:1 or many:many (for split transactions)
        matched_count = 0
        
        if len(statement_lines) == 1 and len(gl_entries) == 1:
            # Simple 1:1 match
            statement_lines[0].match_with_entry(gl_entries[0])
            matched_count = 1
        else:
            # Many-to-many: mark all as reconciled without individual links
            today = timezone.now().date()
            
            for line in statement_lines:
                line.is_reconciled = True
                line.save(update_fields=['is_reconciled', 'updated_at'])
            
            for entry in gl_entries:
                entry.is_reconciled = True
                entry.reconciled_date = today
                entry.save(update_fields=['is_reconciled', 'reconciled_date', 'updated_at'])
            
            matched_count = max(len(statement_lines), len(gl_entries))
        
        return matched_count
    
    def get_brs_summary(self) -> BRSSummary:
        """
        Generate a Bank Reconciliation Statement summary.
        
        The BRS reconciles the Cash Book balance with the Bank Statement balance.
        
        Formula:
        Balance per Cash Book
        + Unpresented Cheques (issued by us, not yet debited by bank)
        - Uncredited Deposits (received by us, not yet credited by bank)
        = Calculated Bank Balance
        
        If Calculated == Actual, reconciliation is complete.
        
        Returns:
            BRSSummary dataclass with all reconciliation details.
        """
        # Get Cash Book (GL) balance for this bank account
        # Sum all posted entries: Debits (increase) - Credits (decrease)
        gl_entries = JournalEntry.objects.filter(
            budget_head=self.gl_code,
            voucher__is_posted=True,
            voucher__organization=self.bank_account.organization,
            voucher__fiscal_year=self.statement.year
        )
        
        gl_totals = gl_entries.aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )
        
        total_debit = gl_totals['total_debit'] or Decimal('0.00')
        total_credit = gl_totals['total_credit'] or Decimal('0.00')
        balance_per_cash_book = total_debit - total_credit
        
        # Unpresented Cheques: We credited (payment) but bank hasn't debited yet
        # These are GL credits (payments made) that are NOT reconciled
        unpresented_entries = JournalEntry.objects.filter(
            budget_head=self.gl_code,
            voucher__is_posted=True,
            voucher__organization=self.bank_account.organization,
            is_reconciled=False,
            credit__gt=Decimal('0.00')
        ).select_related('voucher')
        
        unpresented_total = unpresented_entries.aggregate(
            total=Sum('credit')
        )['total'] or Decimal('0.00')
        
        unpresented_list = [
            {
                'date': e.voucher.date,
                'voucher_no': e.voucher.voucher_no,
                'description': e.description,
                'instrument_no': e.instrument_no,
                'amount': e.credit
            }
            for e in unpresented_entries
        ]
        
        # Uncredited Deposits: We debited (receipt) but bank hasn't credited yet
        # These are GL debits (receipts) that are NOT reconciled
        uncredited_entries = JournalEntry.objects.filter(
            budget_head=self.gl_code,
            voucher__is_posted=True,
            voucher__organization=self.bank_account.organization,
            is_reconciled=False,
            debit__gt=Decimal('0.00')
        ).select_related('voucher')
        
        uncredited_total = uncredited_entries.aggregate(
            total=Sum('debit')
        )['total'] or Decimal('0.00')
        
        uncredited_list = [
            {
                'date': e.voucher.date,
                'voucher_no': e.voucher.voucher_no,
                'description': e.description,
                'instrument_no': e.instrument_no,
                'amount': e.debit
            }
            for e in uncredited_entries
        ]
        
        # Unmatched bank items (items in bank statement not in our books)
        unmatched_bank_lines = self.statement.lines.filter(
            is_reconciled=False
        )
        
        unmatched_bank_list = [
            {
                'date': l.date,
                'description': l.description,
                'ref_no': l.ref_no,
                'debit': l.debit,
                'credit': l.credit
            }
            for l in unmatched_bank_lines
        ]
        
        # Calculate reconciled bank balance
        calculated_bank_balance = (
            balance_per_cash_book 
            + unpresented_total 
            - uncredited_total
        )
        
        actual_bank_balance = self.statement.closing_balance
        difference = calculated_bank_balance - actual_bank_balance
        
        return BRSSummary(
            balance_per_cash_book=balance_per_cash_book,
            add_unpresented_cheques=unpresented_total,
            less_uncredited_deposits=uncredited_total,
            calculated_bank_balance=calculated_bank_balance,
            actual_bank_balance=actual_bank_balance,
            difference=difference,
            unpresented_cheques_list=unpresented_list,
            uncredited_deposits_list=uncredited_list,
            unmatched_bank_items=unmatched_bank_list
        )
    
    def is_fully_reconciled(self) -> bool:
        """
        Check if reconciliation is complete.
        
        Returns:
            True if difference is zero and no unmatched items.
        """
        summary = self.get_brs_summary()
        return (
            summary.difference == Decimal('0.00') and
            len(summary.unmatched_bank_items) == 0 and
            len(summary.unpresented_cheques_list) == 0 and
            len(summary.uncredited_deposits_list) == 0
        )


def parse_bank_statement_csv(
    file_content: str, 
    statement: BankStatement
) -> Tuple[int, List[str]]:
    """
    Parse a CSV bank statement and create BankStatementLine records.
    
    Expected CSV format:
    Date,Description,Debit,Credit,Balance,Reference
    
    Args:
        file_content: CSV content as string.
        statement: The BankStatement to attach lines to.
        
    Returns:
        Tuple of (lines_created, list_of_errors).
    """
    import csv
    from io import StringIO
    from datetime import datetime
    
    errors: List[str] = []
    lines_created = 0
    
    reader = csv.DictReader(StringIO(file_content))
    
    required_columns = {'Date', 'Description', 'Debit', 'Credit', 'Balance'}
    if not required_columns.issubset(set(reader.fieldnames or [])):
        missing = required_columns - set(reader.fieldnames or [])
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return 0, errors
    
    with transaction.atomic():
        for row_num, row in enumerate(reader, start=2):
            try:
                # Parse date (try multiple formats)
                date_str = row['Date'].strip()
                date = None
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y']:
                    try:
                        date = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                
                if not date:
                    errors.append(f"Row {row_num}: Invalid date format '{date_str}'")
                    continue
                
                # Parse amounts
                debit_str = row['Debit'].strip().replace(',', '') or '0'
                credit_str = row['Credit'].strip().replace(',', '') or '0'
                balance_str = row['Balance'].strip().replace(',', '') or '0'
                
                debit = Decimal(debit_str) if debit_str else Decimal('0.00')
                credit = Decimal(credit_str) if credit_str else Decimal('0.00')
                balance = Decimal(balance_str) if balance_str else Decimal('0.00')
                
                # Get reference
                ref_no = row.get('Reference', '').strip() or row.get('Ref', '').strip()
                
                BankStatementLine.objects.create(
                    statement=statement,
                    date=date,
                    description=row['Description'].strip(),
                    debit=debit,
                    credit=credit,
                    balance=balance,
                    ref_no=ref_no
                )
                lines_created += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
    
    return lines_created, errors
