"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Revenue reporting and analytics functions for management
             decision support and compliance reporting.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Any
from datetime import date, timedelta
from django.db.models import Sum, Count, Q, F, Avg, Max, Min, Case, When, DecimalField, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.revenue.models import (
    RevenueDemand, RevenueCollection, Payer,
    DemandStatus, CollectionStatus
)
from apps.core.models import Organization
from apps.budgeting.models import FiscalYear


class RevenueReports:
    """
    Revenue reporting and analytics.
    
    Provides comprehensive reports for:
    - Outstanding receivables with aging analysis
    - Revenue by budget head
    - Payer-wise revenue summary
    - Collection efficiency metrics
    - Trend analysis
    """
    
    @staticmethod
    def outstanding_receivables_aging(
        organization: Organization,
        as_of_date: Optional[date] = None,
        fiscal_year: Optional[FiscalYear] = None
    ) -> Dict[str, Any]:
        """
        Generate aging analysis of outstanding receivables.
        
        Categorizes outstanding demands by age:
        - Current (0-30 days)
        - 31-60 days
        - 61-90 days
        - Over 90 days
        
        Args:
            organization: The organization to report on
            as_of_date: Reference date for aging (default: today)
            fiscal_year: Optional fiscal year filter
            
        Returns:
            Dictionary with aging buckets and totals
        """
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        # Base queryset - demands with outstanding balances
        demands = RevenueDemand.objects.filter(
            organization=organization,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL]
        ).select_related(
            'payer',
            'budget_head',
            'budget_head__nam_head',
            'fiscal_year'
        )
        
        if fiscal_year:
            demands = demands.filter(fiscal_year=fiscal_year)
        
        # Initialize aging buckets
        aging_buckets = {
            'current': {'demands': [], 'total': Decimal('0'), 'count': 0},
            '31_60': {'demands': [], 'total': Decimal('0'), 'count': 0},
            '61_90': {'demands': [], 'total': Decimal('0'), 'count': 0},
            'over_90': {'demands': [], 'total': Decimal('0'), 'count': 0},
        }
        
        grand_total = Decimal('0')
        
        for demand in demands:
            outstanding = demand.get_outstanding_balance()
            if outstanding > 0:
                days = (as_of_date - demand.issue_date).days
                
                # Determine bucket
                if days <= 30:
                    bucket = 'current'
                elif days <= 60:
                    bucket = '31_60'
                elif days <= 90:
                    bucket = '61_90'
                else:
                    bucket = 'over_90'
                
                # Add to bucket
                aging_buckets[bucket]['demands'].append({
                    'demand': demand,
                    'challan_no': demand.challan_no,
                    'payer_name': demand.payer.name,
                    'budget_head': demand.budget_head.nam_head.name,
                    'issue_date': demand.issue_date,
                    'due_date': demand.due_date,
                    'amount': demand.amount,
                    'outstanding': outstanding,
                    'days_outstanding': days
                })
                aging_buckets[bucket]['total'] += outstanding
                aging_buckets[bucket]['count'] += 1
                grand_total += outstanding
        
        return {
            'as_of_date': as_of_date,
            'organization': organization,
            'fiscal_year': fiscal_year,
            'buckets': aging_buckets,
            'grand_total': grand_total,
            'total_count': sum(b['count'] for b in aging_buckets.values())
        }
    
    @staticmethod
    def revenue_by_head_summary(
        organization: Organization,
        fiscal_year: FiscalYear,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Revenue summary by budget head.
        
        Shows total demanded, collected, and outstanding for each
        revenue budget head.
        
        Args:
            organization: The organization to report on
            fiscal_year: Fiscal year to report on
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of dictionaries with revenue head summaries
        """
        # Base filter
        demand_filter = Q(
            organization=organization,
            fiscal_year=fiscal_year,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL, DemandStatus.PAID]
        )
        
        if start_date:
            demand_filter &= Q(issue_date__gte=start_date)
        if end_date:
            demand_filter &= Q(issue_date__lte=end_date)
        
        # Aggregate by budget head
        summary = RevenueDemand.objects.filter(
            demand_filter
        ).values(
            'budget_head',
            'budget_head__nam_head__code',
            'budget_head__nam_head__name',
            'budget_head__sub_code'
        ).annotate(
            total_demanded=Coalesce(Sum('amount'), Decimal('0')),
            demand_count=Count('id')
        ).order_by('-total_demanded')
        
        # Add collection data for each head
        result = []
        for item in summary:
            budget_head_id = item['budget_head']
            
            # Get collections for this budget head
            collection_filter = Q(
                demand__organization=organization,
                demand__fiscal_year=fiscal_year,
                demand__budget_head_id=budget_head_id,
                status=CollectionStatus.POSTED
            )
            
            if start_date:
                collection_filter &= Q(receipt_date__gte=start_date)
            if end_date:
                collection_filter &= Q(receipt_date__lte=end_date)
            
            collections = RevenueCollection.objects.filter(
                collection_filter
            ).aggregate(
                total=Coalesce(Sum('amount_received'), Decimal('0')),
                count=Count('id')
            )
            
            total_collected = collections['total']
            collection_count = collections['count']
            outstanding = item['total_demanded'] - total_collected
            collection_rate = (
                (total_collected / item['total_demanded'] * 100)
                if item['total_demanded'] > 0
                else Decimal('0')
            )
            
            result.append({
                'head_code': item['budget_head__nam_head__code'],
                'head_name': item['budget_head__nam_head__name'],
                'sub_code': item['budget_head__sub_code'],
                'total_demanded': item['total_demanded'],
                'demand_count': item['demand_count'],
                'total_collected': total_collected,
                'collection_count': collection_count,
                'outstanding': outstanding,
                'collection_rate': round(collection_rate, 2)
            })
        
        return result
    
    @staticmethod
    def payer_wise_summary(
        organization: Organization,
        fiscal_year: Optional[FiscalYear] = None,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Payer-wise revenue summary.
        
        Shows total demands, collections, and outstanding for each payer.
        
        Args:
            organization: The organization to report on
            fiscal_year: Optional fiscal year filter
            include_inactive: Include inactive payers
            
        Returns:
            List of dictionaries with payer summaries
        """
        payer_filter = Q(organization=organization)
        if not include_inactive:
            payer_filter &= Q(is_active=True)
        
        payers = Payer.objects.filter(payer_filter).select_related('organization')
        
        result = []
        for payer in payers:
            # Get demands
            demand_filter = Q(payer=payer, status__in=[
                DemandStatus.POSTED, DemandStatus.PARTIAL, DemandStatus.PAID
            ])
            if fiscal_year:
                demand_filter &= Q(fiscal_year=fiscal_year)
            
            demand_stats = RevenueDemand.objects.filter(demand_filter).aggregate(
                total_demanded=Coalesce(Sum('amount'), Decimal('0')),
                demand_count=Count('id')
            )
            
            # Get collections
            collection_filter = Q(
                demand__payer=payer,
                status=CollectionStatus.POSTED
            )
            if fiscal_year:
                collection_filter &= Q(demand__fiscal_year=fiscal_year)
            
            collection_stats = RevenueCollection.objects.filter(
                collection_filter
            ).aggregate(
                total_collected=Coalesce(Sum('amount_received'), Decimal('0')),
                collection_count=Count('id')
            )
            
            total_demanded = demand_stats['total_demanded']
            total_collected = collection_stats['total_collected']
            outstanding = total_demanded - total_collected
            
            # Only include payers with transactions
            if total_demanded > 0:
                result.append({
                    'payer_id': payer.id,
                    'payer_name': payer.name,
                    'cnic_ntn': payer.cnic_ntn,
                    'contact_no': payer.contact_no,
                    'total_demanded': total_demanded,
                    'demand_count': demand_stats['demand_count'],
                    'total_collected': total_collected,
                    'collection_count': collection_stats['collection_count'],
                    'outstanding': outstanding,
                    'is_active': payer.is_active
                })
        
        # Sort by outstanding (highest first)
        result.sort(key=lambda x: x['outstanding'], reverse=True)
        return result
    
    @staticmethod
    def collection_efficiency_report(
        organization: Organization,
        fiscal_year: FiscalYear
    ) -> Dict[str, Any]:
        """
        Collection efficiency metrics.
        
        Calculates:
        - Overall collection rate
        - Average days to collect
        - On-time vs late collections
        - Monthly collection trends
        
        Args:
            organization: The organization to report on
            fiscal_year: Fiscal year to analyze
            
        Returns:
            Dictionary with efficiency metrics
        """
        # Total demands and collections
        demands = RevenueDemand.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL, DemandStatus.PAID]
        ).aggregate(
            total_demanded=Coalesce(Sum('amount'), Decimal('0')),
            demand_count=Count('id')
        )
        
        collections = RevenueCollection.objects.filter(
            demand__organization=organization,
            demand__fiscal_year=fiscal_year,
            status=CollectionStatus.POSTED
        ).aggregate(
            total_collected=Coalesce(Sum('amount_received'), Decimal('0')),
            collection_count=Count('id')
        )
        
        total_demanded = demands['total_demanded']
        total_collected = collections['total_collected']
        outstanding = total_demanded - total_collected
        
        collection_rate = (
            (total_collected / total_demanded * 100)
            if total_demanded > 0
            else Decimal('0')
        )
        
        # Average days to collect
        paid_demands = RevenueDemand.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status=DemandStatus.PAID
        ).select_related('fiscal_year')
        
        days_to_collect = []
        on_time_count = 0
        late_count = 0
        
        for demand in paid_demands:
            # Get first collection date
            first_collection = demand.collections.filter(
                status=CollectionStatus.POSTED
            ).order_by('receipt_date').first()
            
            if first_collection:
                days = (first_collection.receipt_date - demand.issue_date).days
                days_to_collect.append(days)
                
                if first_collection.receipt_date <= demand.due_date:
                    on_time_count += 1
                else:
                    late_count += 1
        
        avg_days_to_collect = (
            sum(days_to_collect) / len(days_to_collect)
            if days_to_collect else 0
        )
        
        # Monthly trend
        monthly_trend = RevenueCollection.objects.filter(
            demand__organization=organization,
            demand__fiscal_year=fiscal_year,
            status=CollectionStatus.POSTED
        ).annotate(
            month=TruncMonth('receipt_date')
        ).values('month').annotate(
            total=Coalesce(Sum('amount_received'), Decimal('0')),
            count=Count('id')
        ).order_by('month')
        
        return {
            'fiscal_year': fiscal_year,
            'total_demanded': total_demanded,
            'demand_count': demands['demand_count'],
            'total_collected': total_collected,
            'collection_count': collections['collection_count'],
            'outstanding': outstanding,
            'collection_rate': round(collection_rate, 2),
            'avg_days_to_collect': round(avg_days_to_collect, 1),
            'on_time_collections': on_time_count,
            'late_collections': late_count,
            'on_time_rate': (
                round((on_time_count / (on_time_count + late_count) * 100), 2)
                if (on_time_count + late_count) > 0
                else Decimal('0')
            ),
            'monthly_trend': list(monthly_trend)
        }
    
    @staticmethod
    def overdue_demands_report(
        organization: Organization,
        as_of_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Report of overdue demands.
        
        Lists all demands past their due date with outstanding balances.
        
        Args:
            organization: The organization to report on
            as_of_date: Reference date (default: today)
            
        Returns:
            List of overdue demands with details
        """
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        overdue_demands = RevenueDemand.objects.filter(
            organization=organization,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL],
            due_date__lt=as_of_date
        ).select_related(
            'payer',
            'budget_head',
            'budget_head__nam_head',
            'fiscal_year'
        ).order_by('due_date')
        
        result = []
        total_overdue_amount = Decimal('0')
        
        for demand in overdue_demands:
            outstanding = demand.get_outstanding_balance()
            if outstanding > 0:
                days_overdue = (as_of_date - demand.due_date).days
                
                result.append({
                    'demand_id': demand.id,
                    'challan_no': demand.challan_no,
                    'payer_name': demand.payer.name,
                    'payer_contact': demand.payer.contact_no,
                    'budget_head': demand.budget_head.nam_head.name,
                    'issue_date': demand.issue_date,
                    'due_date': demand.due_date,
                    'days_overdue': days_overdue,
                    'total_amount': demand.amount,
                    'collected': demand.get_total_collected(),
                    'outstanding': outstanding
                })
                total_overdue_amount += outstanding
        
        return {
            'as_of_date': as_of_date,
            'overdue_demands': result,
            'total_overdue_amount': total_overdue_amount,
            'count': len(result)
        }
    
    @staticmethod
    def demand_vs_collection_comparison(
        organization: Organization,
        fiscal_year: FiscalYear,
        group_by: str = 'month'  # 'month', 'quarter', 'head'
    ) -> Dict[str, Any]:
        """
        Compare demands issued vs collections received.
        
        Args:
            organization: The organization to report on
            fiscal_year: Fiscal year to analyze
            group_by: Grouping method ('month', 'quarter', 'head')
            
        Returns:
            Dictionary with comparison data
        """
        result = {
            'fiscal_year': fiscal_year,
            'group_by': group_by,
            'data': []
        }
        
        if group_by == 'month':
            # Monthly comparison
            months = []
            current = fiscal_year.start_date
            while current <= fiscal_year.end_date:
                month_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                month_end = min(month_end, fiscal_year.end_date)
                
                demands = RevenueDemand.objects.filter(
                    organization=organization,
                    fiscal_year=fiscal_year,
                    issue_date__gte=current,
                    issue_date__lte=month_end,
                    status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL, DemandStatus.PAID]
                ).aggregate(
                    total=Coalesce(Sum('amount'), Decimal('0')),
                    count=Count('id')
                )
                
                collections = RevenueCollection.objects.filter(
                    demand__organization=organization,
                    demand__fiscal_year=fiscal_year,
                    receipt_date__gte=current,
                    receipt_date__lte=month_end,
                    status=CollectionStatus.POSTED
                ).aggregate(
                    total=Coalesce(Sum('amount_received'), Decimal('0')),
                    count=Count('id')
                )
                
                result['data'].append({
                    'period': current.strftime('%B %Y'),
                    'start_date': current,
                    'end_date': month_end,
                    'demands_issued': demands['total'],
                    'demand_count': demands['count'],
                    'collections_received': collections['total'],
                    'collection_count': collections['count'],
                    'variance': demands['total'] - collections['total']
                })
                
                current = month_end + timedelta(days=1)
        
        elif group_by == 'head':
            # By budget head
            result['data'] = RevenueReports.revenue_by_head_summary(
                organization, fiscal_year
            )
        
        return result
