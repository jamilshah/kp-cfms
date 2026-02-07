"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Centralized logging for revenue module operations.
-------------------------------------------------------------------------
"""
import logging
from decimal import Decimal
from typing import Optional, Dict, Any

logger = logging.getLogger('revenue')


class RevenueLogger:
    """Centralized logging for revenue operations"""
    
    @staticmethod
    def log_demand_posted(demand, user):
        """Log demand posting with full context"""
        logger.info(
            f"Demand posted: {demand.challan_no} | "
            f"Payer: {demand.payer.name} | "
            f"Amount: Rs {demand.amount} | "
            f"Voucher: {demand.accrual_voucher.voucher_no} | "
            f"Posted by: {user.username}",
            extra={
                'demand_id': demand.pk,
                'payer_id': demand.payer_id,
                'amount': str(demand.amount),
                'voucher_id': demand.accrual_voucher_id,
                'user_id': user.id,
                'organization': demand.organization.name
            }
        )
    
    @staticmethod
    def log_demand_cancelled(demand, user, reason: str):
        """Log demand cancellation"""
        logger.warning(
            f"Demand cancelled: {demand.challan_no} | "
            f"Payer: {demand.payer.name} | "
            f"Amount: Rs {demand.amount} | "
            f"Reason: {reason} | "
            f"Cancelled by: {user.username}",
            extra={
                'demand_id': demand.pk,
                'payer_id': demand.payer_id,
                'amount': str(demand.amount),
                'reason': reason,
                'user_id': user.id,
                'organization': demand.organization.name
            }
        )
    
    @staticmethod
    def log_collection_posted(collection, user):
        """Log collection posting"""
        logger.info(
            f"Collection posted: {collection.receipt_no} | "
            f"Against: {collection.demand.challan_no} | "
            f"Amount: Rs {collection.amount_received} | "
            f"Bank: {collection.bank_account.title} | "
            f"Posted by: {user.username}",
            extra={
                'collection_id': collection.pk,
                'demand_id': collection.demand_id,
                'amount': str(collection.amount_received),
                'user_id': user.id,
                'organization': collection.organization.name
            }
        )
    
    @staticmethod
    def log_collection_cancelled(collection, user):
        """Log collection cancellation"""
        logger.warning(
            f"Collection cancelled: {collection.receipt_no} | "
            f"Against: {collection.demand.challan_no} | "
            f"Amount: Rs {collection.amount_received} | "
            f"Cancelled by: {user.username}",
            extra={
                'collection_id': collection.pk,
                'demand_id': collection.demand_id,
                'amount': str(collection.amount_received),
                'user_id': user.id,
                'organization': collection.organization.name
            }
        )
    
    @staticmethod
    def log_penalty_waived(demand, user, reason: str):
        """Log penalty waiver"""
        logger.info(
            f"Penalty waived: {demand.challan_no} | "
            f"Payer: {demand.payer.name} | "
            f"Original penalty: Rs {demand.penalty_amount or 0} | "
            f"Reason: {reason} | "
            f"Waived by: {user.username}",
            extra={
                'demand_id': demand.pk,
                'payer_id': demand.payer_id,
                'penalty_amount': str(demand.penalty_amount or 0),
                'reason': reason,
                'user_id': user.id,
                'organization': demand.organization.name
            }
        )
    
    @staticmethod
    def log_error(operation: str, error: Exception, context: Dict[str, Any]):
        """Log errors with context"""
        logger.error(
            f"Revenue error in {operation}: {str(error)}",
            extra=context,
            exc_info=True
        )
    
    @staticmethod
    def log_validation_error(operation: str, errors: Dict[str, Any], context: Dict[str, Any]):
        """Log validation errors"""
        logger.warning(
            f"Validation error in {operation}: {errors}",
            extra={**context, 'validation_errors': errors}
        )
    
    @staticmethod
    def log_workflow_error(operation: str, error: str, context: Dict[str, Any]):
        """Log workflow transition errors"""
        logger.warning(
            f"Workflow error in {operation}: {error}",
            extra={**context, 'workflow_error': error}
        )
