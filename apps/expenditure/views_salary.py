"""
Salary Bill Generation Views

Automates monthly salary bill creation from employee records.
"""

from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, FormView
from django import forms

from apps.budgeting.models import FiscalYear
from apps.expenditure.services_salary import SalaryBillGenerator
from apps.users.permissions import MakerRequiredMixin


class SalaryBillGenerationForm(forms.Form):
    """Form for salary bill generation"""
    
    month = forms.ChoiceField(
        choices=[(i, f"{i:02d}") for i in range(1, 13)],
        label="Month",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    year = forms.IntegerField(
        min_value=2020,
        max_value=2050,
        label="Year",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, fiscal_year=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fiscal_year = fiscal_year
        
        # Set initial values from fiscal year if provided
        if fiscal_year and not args and not kwargs.get('data'):
            import datetime
            today = datetime.date.today()
            self.fields['month'].initial = today.month
            self.fields['year'].initial = today.year


class SalaryBillGenerateView(LoginRequiredMixin, MakerRequiredMixin, TemplateView):
    """
    View for generating monthly salary bills.
    Shows preview of salary breakdown and allows bill creation.
    """
    template_name = 'expenditure/salary_bill_generate.html'
    
    def get_fiscal_year(self):
        """Get current operating fiscal year"""
        org = getattr(self.request.user, 'organization', None)
        if org:
            return FiscalYear.get_current_operating_year(org)
        return None
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        org = getattr(self.request.user, 'organization', None)
        fiscal_year = self.get_fiscal_year()
        
        context['fiscal_year'] = fiscal_year
        context['form'] = SalaryBillGenerationForm(fiscal_year=fiscal_year)
        context['preview_data'] = None
        context['validation_errors'] = None
        
        # If preview requested
        if self.request.GET.get('preview'):
            month = int(self.request.GET.get('month', 1))
            year = int(self.request.GET.get('year', 2026))
            
            generator = SalaryBillGenerator(org, fiscal_year, month, year)
            
            try:
                breakdown = generator.calculate_breakdown()
                is_valid, errors = generator.validate_budget_availability()
                
                context['preview_data'] = breakdown
                context['validation_errors'] = errors if not is_valid else None
                context['is_valid'] = is_valid
                context['month'] = month
                context['year'] = year
                context['bill_description'] = generator.generate_bill_description()
                
            except Exception as e:
                messages.error(self.request, f"Error generating preview: {str(e)}")
        
        return context
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """Handle bill creation"""
        form = SalaryBillGenerationForm(request.POST)
        
        if not form.is_valid():
            messages.error(request, "Invalid form data")
            return self.get(request, *args, **kwargs)
        
        month = int(form.cleaned_data['month'])
        year = int(form.cleaned_data['year'])
        
        org = getattr(request.user, 'organization', None)
        fiscal_year = self.get_fiscal_year()
        
        if not org or not fiscal_year:
            messages.error(request, "No active fiscal year found")
            return redirect('expenditure:bill_list')
        
        try:
            generator = SalaryBillGenerator(org, fiscal_year, month, year)
            bill = generator.create_bill(created_by=request.user)
            
            messages.success(
                request,
                f"Salary bill created successfully! "
                f"Bill for {generator.generate_bill_description()} - "
                f"Total: Rs {bill.gross_amount:,.2f}"
            )
            
            return redirect('expenditure:bill_detail', pk=bill.pk)
            
        except Exception as e:
            messages.error(request, f"Error creating bill: {str(e)}")
            return self.get(request, *args, **kwargs)


class SalaryBillPreviewAPI(LoginRequiredMixin, TemplateView):
    """API endpoint for AJAX preview"""
    
    def get(self, request, *args, **kwargs):
        month = int(request.GET.get('month', 1))
        year = int(request.GET.get('year', 2026))
        
        org = getattr(request.user, 'organization', None)
        fiscal_year = FiscalYear.get_current_operating_year(org) if org else None
        
        if not org or not fiscal_year:
            return JsonResponse({'error': 'No active fiscal year'}, status=400)
        
        try:
            generator = SalaryBillGenerator(org, fiscal_year, month, year)
            breakdown = generator.calculate_breakdown()
            is_valid, errors = generator.validate_budget_availability()
            
            # Format for JSON
            by_function = {}
            for func_code, data in breakdown['by_function'].items():
                by_function[func_code] = {
                    'function_name': data['function_name'],
                    'employee_count': data['employee_count'],
                    'total': float(data['total']),
                    'components': {k: float(v) for k, v in data['components'].items()}
                }
            
            by_component = {}
            for code, data in breakdown['by_component'].items():
                by_component[code] = {
                    'name': data['name'],
                    'amount': float(data['amount']),
                    'employees': data['employees']
                }
            
            return JsonResponse({
                'success': True,
                'total_employees': breakdown['total_employees'],
                'total_amount': float(breakdown['total_amount']),
                'by_function': by_function,
                'by_component': by_component,
                'is_valid': is_valid,
                'errors': errors,
                'description': generator.generate_bill_description()
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
