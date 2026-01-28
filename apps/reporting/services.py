"""
Reporting Services for PDF Generation
======================================

This module provides services for generating PDF reports including:
- Monthly Cash Book Report
- Bank Reconciliation Statement (BRS)

Uses WeasyPrint for PDF generation with Django templates.
"""

import io
from datetime import date
from decimal import Decimal
from typing import Optional

from django.template.loader import render_to_string
from django.http import HttpResponse

from apps.core.models import BankAccount, Organization
from apps.budgeting.models import FiscalYear
from apps.finance.models import JournalEntry, BankStatement
from apps.finance.services_reconciliation import ReconciliationEngine


def generate_cash_book_pdf(
    month: int,
    year: int,
    bank_account_id: int,
    organization: Organization,
    fiscal_year: Optional[FiscalYear] = None
) -> HttpResponse:
    """
    Generate Monthly Cash Book PDF Report.
    
    Args:
        month: Month number (1-12)
        year: Calendar year
        bank_account_id: ID of the bank account
        organization: Organization instance
        fiscal_year: Optional fiscal year for filtering
        
    Returns:
        HttpResponse with PDF content
    """
    from calendar import monthrange, month_name
    
    # Get bank account
    bank_account = BankAccount.objects.get(pk=bank_account_id, organization=organization)
    
    # Date range for the month
    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    
    # Get journal entries for this bank account in the month
    entries = JournalEntry.objects.filter(
        voucher__organization=organization,
        head=bank_account.gl_code,
        voucher__date__gte=start_date,
        voucher__date__lte=end_date,
    ).select_related('voucher').order_by('voucher__date', 'pk')
    
    # Calculate opening balance (sum of all entries before start_date)
    previous_entries = JournalEntry.objects.filter(
        voucher__organization=organization,
        head=bank_account.gl_code,
        voucher__date__lt=start_date,
    )
    opening_debit = sum(e.debit for e in previous_entries)
    opening_credit = sum(e.credit for e in previous_entries)
    opening_balance = opening_debit - opening_credit
    
    # Build cash book entries with running balance
    running_balance = opening_balance
    cash_book_entries = []
    total_receipts = Decimal('0')
    total_payments = Decimal('0')
    
    for entry in entries:
        if entry.debit > 0:
            total_receipts += entry.debit
            running_balance += entry.debit
        if entry.credit > 0:
            total_payments += entry.credit
            running_balance -= entry.credit
            
        cash_book_entries.append({
            'date': entry.voucher.date,
            'voucher_no': entry.voucher.voucher_no,
            'description': entry.description or entry.voucher.description,
            'instrument_no': entry.instrument_no or '',
            'debit': entry.debit,
            'credit': entry.credit,
            'balance': running_balance,
        })
    
    closing_balance = running_balance
    
    # Prepare context
    context = {
        'bank_account': bank_account,
        'month_name': month_name[month],
        'year': year,
        'organization': organization,
        'opening_balance': opening_balance,
        'closing_balance': closing_balance,
        'total_receipts': total_receipts,
        'total_payments': total_payments,
        'entries': cash_book_entries,
        'generated_date': date.today(),
    }
    
    # Try WeasyPrint, fallback to HTML
    try:
        from weasyprint import HTML
        html_string = render_to_string('reporting/cash_book_pdf.html', context)
        html = HTML(string=html_string)
        pdf_file = html.write_pdf()
        
        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = f"cash_book_{bank_account.account_number}_{year}_{month:02d}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except ImportError:
        # WeasyPrint not installed, return HTML for print
        html_string = render_to_string('reporting/cash_book_pdf.html', context)
        return HttpResponse(html_string)


def generate_brs_pdf(statement_id: int, organization: Organization) -> HttpResponse:
    """
    Generate Bank Reconciliation Statement PDF.
    
    Args:
        statement_id: ID of the BankStatement
        organization: Organization instance
        
    Returns:
        HttpResponse with PDF content
    """
    # Get statement
    statement = BankStatement.objects.select_related(
        'bank_account', 'fiscal_year'
    ).get(pk=statement_id, bank_account__organization=organization)
    
    # Get BRS data
    engine = ReconciliationEngine(statement)
    brs = engine.get_brs_summary()
    
    # Prepare context
    context = {
        'statement': statement,
        'brs': brs,
        'organization': organization,
        'generated_date': date.today(),
    }
    
    # Try WeasyPrint, fallback to HTML
    try:
        from weasyprint import HTML
        html_string = render_to_string('reporting/brs_pdf.html', context)
        html = HTML(string=html_string)
        pdf_file = html.write_pdf()
        
        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = f"brs_{statement.bank_account.account_number}_{statement.get_month_display()}_{statement.fiscal_year.code}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except ImportError:
        # WeasyPrint not installed, return HTML for print
        html_string = render_to_string('reporting/brs_pdf.html', context)
        return HttpResponse(html_string)


def get_monthly_summary(
    month: int,
    year: int,
    organization: Organization,
) -> dict:
    """
    Get summary data for a month across all bank accounts.
    
    Args:
        month: Month number (1-12)
        year: Calendar year
        organization: Organization instance
        
    Returns:
        Dictionary with summary data
    """
    from calendar import monthrange
    from django.db.models import Sum
    
    # Date range
    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    
    # Get all bank accounts
    bank_accounts = BankAccount.objects.filter(
        organization=organization,
        is_active=True
    ).select_related('gl_code')
    
    summaries = []
    
    for account in bank_accounts:
        entries = JournalEntry.objects.filter(
            voucher__organization=organization,
            head=account.gl_code,
            voucher__date__gte=start_date,
            voucher__date__lte=end_date,
        )
        
        totals = entries.aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )
        
        summaries.append({
            'bank_account': account,
            'receipts': totals['total_debit'] or Decimal('0'),
            'payments': totals['total_credit'] or Decimal('0'),
        })
    
    return {
        'month': month,
        'year': year,
        'accounts': summaries,
        'total_receipts': sum(s['receipts'] for s in summaries),
        'total_payments': sum(s['payments'] for s in summaries),
    }
