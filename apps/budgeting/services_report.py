"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Reporting services for Budget Book generation.
             Groups budget data by Operating vs Capital classification.

PHASE 4 - BUDGET BOOK REPORTING:
    
    This module implements the Budget Book Report which segregates budget
    allocations into Operating and Capital sections following government
    financial reporting standards.
    
    KEY FEATURES:
    1. Operating Budget:
       - Operating Receipts (Revenue accounts)
       - Operating Expenditure (Salary A01 + Non-Salary A03, excluding Development)
       - Operating Surplus/Deficit calculation
    
    2. Capital Budget:
       - Capital Receipts (Development Grants, Loans)
       - Capital Expenditure (A09 Physical Assets)
       - Net Capital Flow calculation
    
    3. Establishment Summary:
       - Posts summary by department and type (PUGF/Local)
       - Total sanctioned, occupied, and budget figures
    
    4. Net Surplus/Deficit:
       - Overall financial position combining Operating and Capital
    
    USAGE:
        from apps.budgeting.services_report import BudgetBookService
        
        context = BudgetBookService.get_budget_book_context(fiscal_year_id=1)
        # Returns structured dictionary ready for template rendering
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Dict, List, Any
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404

from apps.budgeting.models import FiscalYear, BudgetAllocation, ScheduleOfEstablishment
from apps.finance.models import AccountType


class BudgetBookService:
    """
    Service class for generating Budget Book report context.
    
    Segregates budget allocations into Operating and Capital sections
    as per government financial reporting standards.
    """
    
    @staticmethod
    def get_budget_book_context(fiscal_year_id: int) -> Dict[str, Any]:
        """
        Generate structured context for Budget Book PDF generation.
        
        Args:
            fiscal_year_id: Primary key of the FiscalYear.
        
        Returns:
            Dictionary containing:
                - fiscal_year: FiscalYear object
                - operating_receipts: List of revenue allocations
                - operating_expenditure_salary: List of salary (A01) allocations
                - operating_expenditure_nonsalary: List of non-salary (A03) allocations
                - capital_receipts: List of capital/grant allocations
                - capital_expenditure: List of development (A09) allocations
                - establishment_summary: Summary of posts by department
                - totals: Dictionary of calculated totals and surplus/deficit
        
        Raises:
            FiscalYear.DoesNotExist: If fiscal year not found.
        """
        fiscal_year = get_object_or_404(FiscalYear, pk=fiscal_year_id)
        
        # Base queryset for all allocations
        allocations = BudgetAllocation.objects.filter(
            fiscal_year=fiscal_year
        ).select_related('budget_head', 'budget_head__function')
        
        # ============================================================
        # GROUP A: OPERATING RECEIPTS (Revenue)
        # ============================================================
        operating_receipts = allocations.filter(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__account_type=AccountType.REVENUE) |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__account_type=AccountType.REVENUE)
        ).order_by('budget_head__department__name', 'budget_head__function__code')
        
        total_operating_receipts = operating_receipts.aggregate(
            total=Sum('original_allocation')
        )['total'] or Decimal('0.00')
        
        # ============================================================
        # GROUP B: OPERATING EXPENDITURE
        # Exclude A09 (Physical Assets/Development)
        # ============================================================
        operating_expenditure = allocations.filter(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__account_type=AccountType.EXPENDITURE) |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__account_type=AccountType.EXPENDITURE)
        ).exclude(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A09') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A09')
        )
        
        # Sub-group B1: Salaries (A01*)
        operating_expenditure_salary = operating_expenditure.filter(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A01') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A01')
        ).order_by('budget_head__department__name', 'budget_head__function__code')
        
        total_salary = operating_expenditure_salary.aggregate(
            total=Sum('original_allocation')
        )['total'] or Decimal('0.00')
        
        # Sub-group B2: Non-Salary (A03, A04, A05, etc. - excluding A01 and A09)
        operating_expenditure_nonsalary = operating_expenditure.exclude(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A01') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A01')
        ).order_by('budget_head__department__name', 'budget_head__function__code')
        
        total_nonsalary = operating_expenditure_nonsalary.aggregate(
            total=Sum('original_allocation')
        )['total'] or Decimal('0.00')
        
        total_operating_expenditure = total_salary + total_nonsalary
        
        # ============================================================
        # GROUP C: CAPITAL RECEIPTS
        # Development Grants, Loans, etc.
        # ============================================================
        # Note: Capital receipts typically start with 'B' in the CoA
        capital_receipts = allocations.filter(
            Q(budget_head__nam_head__isnull=False,
              budget_head__nam_head__account_type=AccountType.REVENUE,
              budget_head__nam_head__code__startswith='B') |
            Q(budget_head__sub_head__isnull=False,
              budget_head__sub_head__nam_head__account_type=AccountType.REVENUE,
              budget_head__sub_head__nam_head__code__startswith='B')
        ).order_by('budget_head__department__name', 'budget_head__function__code')
        
        total_capital_receipts = capital_receipts.aggregate(
            total=Sum('original_allocation')
        )['total'] or Decimal('0.00')
        
        # ============================================================
        # GROUP D: CAPITAL EXPENDITURE (Development/A09)
        # ============================================================
        capital_expenditure = allocations.filter(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A09') |
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__account_type=AccountType.ASSET) |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A09') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__account_type=AccountType.ASSET)
        ).order_by('budget_head__department__name', 'budget_head__function__code')
        
        total_capital_expenditure = capital_expenditure.aggregate(
            total=Sum('original_allocation')
        )['total'] or Decimal('0.00')
        
        # ============================================================
        # CALCULATIONS
        # ============================================================
        operating_surplus = total_operating_receipts - total_operating_expenditure
        net_capital_flow = total_capital_receipts - total_capital_expenditure
        net_surplus_deficit = operating_surplus + net_capital_flow
        
        # ============================================================
        # ESTABLISHMENT SUMMARY (Part III)
        # ============================================================
        establishment_summary = ScheduleOfEstablishment.objects.filter(
            fiscal_year=fiscal_year
        ).values(
            'department', 'post_type'
        ).annotate(
            total_sanctioned=Sum('sanctioned_posts'),
            total_occupied=Sum('occupied_posts'),
            total_budget=Sum('estimated_budget')
        ).order_by('department', 'post_type')
        
        # Calculate grand totals for establishment
        establishment_totals = ScheduleOfEstablishment.objects.filter(
            fiscal_year=fiscal_year
        ).aggregate(
            total_sanctioned=Sum('sanctioned_posts'),
            total_occupied=Sum('occupied_posts'),
            total_vacant=Sum('sanctioned_posts') - Sum('occupied_posts'),
            total_budget=Sum('estimated_budget')
        )
        
        # ============================================================
        # RETURN STRUCTURED CONTEXT
        # ============================================================
        return {
            'fiscal_year': fiscal_year,
            
            # Operating Section
            'operating_receipts': operating_receipts,
            'operating_expenditure_salary': operating_expenditure_salary,
            'operating_expenditure_nonsalary': operating_expenditure_nonsalary,
            
            # Capital Section
            'capital_receipts': capital_receipts,
            'capital_expenditure': capital_expenditure,
            
            # Establishment Summary
            'establishment_summary': establishment_summary,
            'establishment_totals': establishment_totals,
            
            # Totals and Calculations
            'totals': {
                'operating_receipts': total_operating_receipts,
                'salary_expenditure': total_salary,
                'nonsalary_expenditure': total_nonsalary,
                'operating_expenditure': total_operating_expenditure,
                'operating_surplus': operating_surplus,
                
                'capital_receipts': total_capital_receipts,
                'capital_expenditure': total_capital_expenditure,
                'net_capital_flow': net_capital_flow,
                
                'net_surplus_deficit': net_surplus_deficit,
                
                # Additional useful metrics
                'total_receipts': total_operating_receipts + total_capital_receipts,
                'total_expenditure': total_operating_expenditure + total_capital_expenditure,
            }
        }
