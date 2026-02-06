"""
Tax calculation service for KP-CFMS.

Implements the tax withholding matrix for TMAs as per:
- Income Tax Ordinance, 2001 (Section 153)
- Sales Tax Act, 1990
- KP Sales Tax on Services Act, 2022
- Stamp Act, 1899 (Article 22A)
"""
from decimal import Decimal
from typing import Dict, Optional
from apps.expenditure.models import Bill, PayeeTaxStatus, PayeeEntityType, TransactionType


class TaxCalculator:
    """
    Automated tax calculation engine based on transaction type and vendor status.
    
    Tax rates are loaded from TaxRateConfiguration model (admin-configurable).
    Falls back to default rates if no active configuration exists.
    """
    
    def __init__(self):
        """Initialize calculator and load active tax rate configuration."""
        self._load_tax_rates()
    
    def _load_tax_rates(self):
        """Load tax rates from active configuration or use defaults."""
        from apps.expenditure.models_tax_config import TaxRateConfiguration
        
        config = TaxRateConfiguration.get_active_config()
        
        if config:
            # Load rates from database configuration
            self.INCOME_TAX_RATES = {
                TransactionType.GOODS: {
                    PayeeTaxStatus.ACTIVE_FILER: {
                        PayeeEntityType.COMPANY: config.goods_filer_company,
                        PayeeEntityType.INDIVIDUAL: config.goods_filer_individual
                    },
                    PayeeTaxStatus.NON_FILER: {
                        PayeeEntityType.COMPANY: config.goods_nonfiler_company,
                        PayeeEntityType.INDIVIDUAL: config.goods_nonfiler_individual
                    }
                },
                TransactionType.SERVICES: {
                    PayeeTaxStatus.ACTIVE_FILER: config.services_filer,
                    PayeeTaxStatus.NON_FILER: config.services_nonfiler
                },
                TransactionType.WORKS: {
                    PayeeTaxStatus.ACTIVE_FILER: {
                        PayeeEntityType.COMPANY: config.works_filer_company,
                        PayeeEntityType.INDIVIDUAL: config.works_filer_individual
                    },
                    PayeeTaxStatus.NON_FILER: {
                        PayeeEntityType.COMPANY: config.works_nonfiler_company,
                        PayeeEntityType.INDIVIDUAL: config.works_nonfiler_individual
                    }
                }
            }
            
            self.SALES_TAX_WITHHOLDING = {
                TransactionType.GOODS: {
                    PayeeTaxStatus.ACTIVE_FILER: config.sales_tax_goods_filer,
                    PayeeTaxStatus.NON_FILER: config.sales_tax_goods_nonfiler
                },
                TransactionType.SERVICES: {
                    PayeeTaxStatus.ACTIVE_FILER: config.sales_tax_services_filer,
                    PayeeTaxStatus.NON_FILER: config.sales_tax_services_nonfiler
                },
                TransactionType.WORKS: {
                    PayeeTaxStatus.ACTIVE_FILER: config.sales_tax_works,
                    PayeeTaxStatus.NON_FILER: config.sales_tax_works
                }
            }
            
            self.STAMP_DUTY_RATE = config.stamp_duty_rate
            self.SALES_TAX_RATE = config.standard_sales_tax_rate
        else:
            # Fallback to default rates (Tax Year 2025-26)
            self.INCOME_TAX_RATES = {
                TransactionType.GOODS: {
                    PayeeTaxStatus.ACTIVE_FILER: {
                        PayeeEntityType.COMPANY: Decimal('0.05'),
                        PayeeEntityType.INDIVIDUAL: Decimal('0.055')
                    },
                    PayeeTaxStatus.NON_FILER: {
                        PayeeEntityType.COMPANY: Decimal('0.10'),
                        PayeeEntityType.INDIVIDUAL: Decimal('0.11')
                    }
                },
                TransactionType.SERVICES: {
                    PayeeTaxStatus.ACTIVE_FILER: Decimal('0.15'),
                    PayeeTaxStatus.NON_FILER: Decimal('0.30')
                },
                TransactionType.WORKS: {
                    PayeeTaxStatus.ACTIVE_FILER: {
                        PayeeEntityType.COMPANY: Decimal('0.075'),
                        PayeeEntityType.INDIVIDUAL: Decimal('0.08')
                    },
                    PayeeTaxStatus.NON_FILER: {
                        PayeeEntityType.COMPANY: Decimal('0.15'),
                        PayeeEntityType.INDIVIDUAL: Decimal('0.16')
                    }
                }
            }
            
            self.SALES_TAX_WITHHOLDING = {
                TransactionType.GOODS: {
                    PayeeTaxStatus.ACTIVE_FILER: Decimal('0.20'),
                    PayeeTaxStatus.NON_FILER: Decimal('1.00')
                },
                TransactionType.SERVICES: {
                    PayeeTaxStatus.ACTIVE_FILER: Decimal('0.50'),
                    PayeeTaxStatus.NON_FILER: Decimal('1.00')
                },
                TransactionType.WORKS: {
                    PayeeTaxStatus.ACTIVE_FILER: Decimal('1.00'),
                    PayeeTaxStatus.NON_FILER: Decimal('1.00')
                }
            }
            
            self.STAMP_DUTY_RATE = Decimal('0.01')
            self.SALES_TAX_RATE = Decimal('0.18')
    
    def calculate_taxes(
        self, 
        bill: Bill,
        sales_tax_invoice_amount: Optional[Decimal] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate all applicable taxes for a bill.
        
        Args:
            bill: Bill instance with payee, transaction_type, and gross_amount
            sales_tax_invoice_amount: Sales tax amount from vendor invoice (optional)
                                     If not provided, calculated as 18% of gross
        
        Returns:
            Dictionary with:
                - income_tax: Income tax amount
                - sales_tax: Sales tax withholding amount
                - stamp_duty: Stamp duty amount (Works only)
                - total_tax: Sum of all taxes
                - net_amount: Amount payable to vendor (gross - total_tax)
        
        Raises:
            ValueError: If required bill attributes are missing
        
        Example:
            >>> calculator = TaxCalculator()
            >>> bill = Bill(payee=vendor, transaction_type='SERVICES', gross_amount=100000)
            >>> taxes = calculator.calculate_taxes(bill)
            >>> print(f"Income Tax: Rs {taxes['income_tax']}")
            Income Tax: Rs 15000.00  # 15% for Active Filer Services
        """
        if not bill.payee:
            raise ValueError("Bill must have a payee assigned")
        if not bill.gross_amount or bill.gross_amount <= 0:
            raise ValueError("Bill must have a valid gross amount")
        
        # Get vendor details
        tax_status = bill.payee.tax_status
        entity_type = bill.payee.entity_type
        transaction_type = bill.transaction_type
        gross_amount = bill.gross_amount
        
        # Tax-exempt vendors (e.g., government departments)
        if tax_status == PayeeTaxStatus.EXEMPT:
            return {
                'income_tax': Decimal('0.00'),
                'sales_tax': Decimal('0.00'),
                'stamp_duty': Decimal('0.00'),
                'total_tax': Decimal('0.00'),
                'net_amount': gross_amount
            }
        
        # Calculate Income Tax
        income_tax = self._calculate_income_tax(
            gross_amount, transaction_type, tax_status, entity_type
        )
        
        # Calculate Sales Tax Withholding
        sales_tax = self._calculate_sales_tax(
            gross_amount, transaction_type, tax_status, sales_tax_invoice_amount
        )
        
        # Calculate Stamp Duty (Works Contracts only)
        stamp_duty = self._calculate_stamp_duty(
            gross_amount, transaction_type
        )
        
        # Calculate totals
        total_tax = income_tax + sales_tax + stamp_duty
        net_amount = gross_amount - total_tax
        
        return {
            'income_tax': income_tax,
            'sales_tax': sales_tax,
            'stamp_duty': stamp_duty,
            'total_tax': total_tax,
            'net_amount': net_amount
        }
    
    def _calculate_income_tax(
        self,
        gross_amount: Decimal,
        transaction_type: str,
        tax_status: str,
        entity_type: str
    ) -> Decimal:
        """
        Calculate income tax based on transaction type and vendor status.
        
        Args:
            gross_amount: Total bill amount
            transaction_type: GOODS/SERVICES/WORKS
            tax_status: FILER/NON_FILER/EXEMPT
            entity_type: COMPANY/INDIVIDUAL
        
        Returns:
            Income tax amount (deducted from gross)
        """
        rate_matrix = self.INCOME_TAX_RATES.get(transaction_type, {})
        
        if transaction_type == TransactionType.SERVICES:
            # Services: rate doesn't depend on entity type
            rate = rate_matrix.get(tax_status, Decimal('0.00'))
        else:
            # Goods/Works: rate depends on both status and entity type
            status_rates = rate_matrix.get(tax_status, {})
            rate = status_rates.get(entity_type, Decimal('0.00'))
        
        return (gross_amount * rate).quantize(Decimal('0.01'))
    
    def _calculate_sales_tax(
        self,
        gross_amount: Decimal,
        transaction_type: str,
        tax_status: str,
        sales_tax_invoice_amount: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate sales tax withholding.
        
        The "1/5th Rule" for Goods:
        - Active Filer: Withhold 20% (1/5th) of sales tax shown on invoice
        - Non-Filer: Withhold 100% (whole) of sales tax
        
        For Services (KPRA):
        - Active Filer: Withhold 50% of sales tax
        - Non-Filer: Withhold 100%
        
        Args:
            gross_amount: Total bill amount
            transaction_type: GOODS/SERVICES/WORKS
            tax_status: FILER/NON_FILER
            sales_tax_invoice_amount: Sales tax from vendor invoice (optional)
        
        Returns:
            Sales tax withholding amount
        """
        # Determine sales tax base amount
        if sales_tax_invoice_amount:
            sales_tax_base = sales_tax_invoice_amount
        else:
            # Assume standard 18% sales tax if not provided
            sales_tax_base = (gross_amount * self.SALES_TAX_RATE).quantize(Decimal('0.01'))
        
        # Get withholding percentage
        withholding_matrix = self.SALES_TAX_WITHHOLDING.get(transaction_type, {})
        withholding_rate = withholding_matrix.get(tax_status, Decimal('0.00'))
        
        return (sales_tax_base * withholding_rate).quantize(Decimal('0.01'))
    
    def _calculate_stamp_duty(
        self,
        gross_amount: Decimal,
        transaction_type: str
    ) -> Decimal:
        """
        Calculate stamp duty (1% for Works Contracts only).
        
        As per Stamp Act, 1899 (Schedule I, Article 22A):
        Works contracts require 1% stamp duty on contract value.
        
        Args:
            gross_amount: Total contract value
            transaction_type: GOODS/SERVICES/WORKS
        
        Returns:
            Stamp duty amount (only for WORKS, otherwise 0)
        """
        if transaction_type == TransactionType.WORKS:
            return (gross_amount * self.STAMP_DUTY_RATE).quantize(Decimal('0.01'))
        return Decimal('0.00')
