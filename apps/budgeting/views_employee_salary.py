"""
Views for Employee Salary Structure Management
"""
import csv
import io
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView,
    FormView, TemplateView, DetailView
)

from apps.budgeting.models import ScheduleOfEstablishment, FiscalYear, Department
from apps.budgeting.models_employee import BudgetEmployee
from apps.budgeting.forms_employee_salary import (
    EmployeeSalaryForm,
    EmployeeSalaryCSVUploadForm,
    BulkIncrementForm,
    AutoCalculateAllowancesForm
)
from apps.finance.models import FunctionCode
from apps.users.permissions import MakerRequiredMixin, AdminRequiredMixin


class EmployeeSalaryListView(LoginRequiredMixin, ListView):
    """List all employees with salary details"""
    model = BudgetEmployee
    template_name = 'budgeting/employee_salary/list.html'
    context_object_name = 'employees'
    paginate_by = 50
    
    def get_queryset(self):
        qs = BudgetEmployee.objects.select_related(
            'fiscal_year', 'department', 'function'
        ).filter(is_vacant=False).order_by(
            'department__name', 'designation', 'name'
        )
        
        # Filter by department
        dept = self.request.GET.get('department')
        if dept:
            qs = qs.filter(department_id=dept)
        
        # Filter by fiscal year
        fy = self.request.GET.get('fiscal_year')
        if fy:
            qs = qs.filter(fiscal_year_id=fy)
        
        # Search by name
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fiscal_years'] = FiscalYear.objects.all().order_by('-start_date')
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        
        # Summary statistics
        queryset = self.get_queryset()
        context['total_employees'] = queryset.count()
        context['total_monthly_cost'] = queryset.aggregate(
            total=Sum('running_basic')
        )['total'] or Decimal('0.00')
        
        # Calculate total annual cost and projected annual cost
        total_annual = Decimal('0.00')
        total_projected_annual = Decimal('0.00')
        for employee in queryset:
            total_annual += employee.annual_cost
            total_projected_annual += employee.get_projected_annual_cost()
        
        context['total_annual_cost'] = total_annual
        context['total_projected_annual_cost'] = total_projected_annual
        context['total_annual_increase'] = total_projected_annual - total_annual
        
        return context


class EmployeeSalaryCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """Create new employee salary record"""
    model = BudgetEmployee
    form_class = EmployeeSalaryForm
    template_name = 'budgeting/employee_salary/form.html'
    success_url = reverse_lazy('budgeting:employee_salary_list')
    
    def get_initial(self):
        """Set default fiscal year"""
        initial = super().get_initial()
        active_fy = FiscalYear.objects.filter(is_active=True).first()
        if active_fy:
            initial['fiscal_year'] = active_fy
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schedule_id = self.request.GET.get('schedule')
        if schedule_id:
            context['schedule'] = get_object_or_404(ScheduleOfEstablishment, id=schedule_id)
        return context
    
    def form_valid(self, form):
        # Set fiscal year if not provided
        if not form.instance.fiscal_year:
            form.instance.fiscal_year = FiscalYear.objects.filter(is_active=True).first()
        
        # Optional: Link to schedule if provided
        schedule_id = self.request.GET.get('schedule') or self.request.POST.get('schedule')
        if schedule_id:
            form.instance.schedule = get_object_or_404(ScheduleOfEstablishment, id=schedule_id)
        
        messages.success(self.request, f"Employee '{form.instance.name}' created successfully")
        return super().form_valid(form)


class EmployeeSalaryUpdateView(LoginRequiredMixin, MakerRequiredMixin, UpdateView):
    """Update employee salary record"""
    model = BudgetEmployee
    form_class = EmployeeSalaryForm
    template_name = 'budgeting/employee_salary/form.html'
    success_url = reverse_lazy('budgeting:employee_salary_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Employee '{form.instance.name}' updated successfully")
        return super().form_valid(form)


class EmployeeSalaryDetailView(LoginRequiredMixin, DetailView):
    """View employee salary details"""
    model = BudgetEmployee
    template_name = 'budgeting/employee_salary/detail.html'
    context_object_name = 'employee'


class EmployeeSalaryDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete employee salary record"""
    model = BudgetEmployee
    template_name = 'budgeting/employee_salary/confirm_delete.html'
    success_url = reverse_lazy('budgeting:employee_salary_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Employee '{self.object.name}' deleted successfully")
        return super().form_valid(form)


class EmployeeSalaryCSVImportView(LoginRequiredMixin, AdminRequiredMixin, FormView):
    """Import employee salary data from CSV"""
    template_name = 'budgeting/employee_salary/csv_import.html'
    form_class = EmployeeSalaryCSVUploadForm
    success_url = reverse_lazy('budgeting:employee_salary_list')
    
    def form_valid(self, form):
        schedule = form.cleaned_data['schedule']
        csv_file = form.cleaned_data['csv_file']
        overwrite = form.cleaned_data['overwrite_existing']
        
        try:
            # Read CSV
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            created_count = 0
            updated_count = 0
            error_count = 0
            errors = []
            
            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Extract and clean data
                        personnel_number = row.get('personnel_number', '').strip()
                        name = row.get('name', '').strip()
                        
                        if not name:
                            errors.append(f"Row {row_num}: Name is required")
                            error_count += 1
                            continue
                        
                        # Convert decimal fields
                        def to_decimal(value):
                            try:
                                return Decimal(value.replace(',', '')) if value else Decimal('0.00')
                            except (InvalidOperation, ValueError):
                                return Decimal('0.00')
                        
                        employee_data = {
                            'name': name,
                            'father_name': row.get('father_name', '').strip(),
                            'designation': row.get('designation', '').strip(),
                            'date_of_birth': row.get('date_of_birth') or None,
                            'qualification': row.get('qualification', '').strip(),
                            'bps': int(row.get('bps', '1')) if row.get('bps', '').isdigit() else 1,
                            'running_basic': to_decimal(row.get('running_basic', '0')),
                            'city_category': row.get('city_category', 'OTHER'),
                            'is_govt_accommodation': row.get('is_govt_accommodation', 'false').lower() == 'true',
                            'is_house_hiring': row.get('is_house_hiring', 'false').lower() == 'true',
                            'dra_amount': to_decimal(row.get('dra_amount', '0')),
                            'frozen_ara_2022_input': to_decimal(row.get('frozen_ara_2022_input', '0')),
                            'joining_date': row.get('joining_date') or None,
                            'remarks': row.get('remarks', '').strip(),
                        }
                        
                        # Check if employee exists
                        if personnel_number and overwrite:
                            employee, created = BudgetEmployee.objects.update_or_create(
                                schedule=schedule,
                                personnel_number=personnel_number,
                                defaults=employee_data
                            )
                            if created:
                                created_count += 1
                            else:
                                updated_count += 1
                        else:
                            employee = BudgetEmployee.objects.create(
                                schedule=schedule,
                                **employee_data
                            )
                            created_count += 1
                    
                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")
                        error_count += 1
            
            # Show results
            if created_count > 0:
                messages.success(self.request, f"✓ Created {created_count} employee records")
            if updated_count > 0:
                messages.success(self.request, f"✓ Updated {updated_count} employee records")
            if error_count > 0:
                messages.warning(self.request, f"⚠ {error_count} errors encountered")
                for error in errors[:10]:  # Show first 10 errors
                    messages.error(self.request, error)
            
            return redirect(self.success_url)
        
        except Exception as e:
            messages.error(self.request, f"CSV import failed: {str(e)}")
            return self.form_invalid(form)


class EmployeeSalaryCSVTemplateView(LoginRequiredMixin, TemplateView):
    """Generate CSV template for employee salary data"""
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="employee_salary_template.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'personnel_number', 'name', 'cnic', 'joining_date',
            'basic_pay', 'hra', 'conveyance', 'medical',
            'adhoc_relief', 'special_allowance', 'utility', 'entertainment',
            'annual_increment', 'gpf', 'income_tax', 'remarks'
        ])
        
        # Add sample row
        writer.writerow([
            'EMP001', 'John Doe', '12345-1234567-1', '2024-01-01',
            '50000', '22500', '3000', '1500',
            '25000', '0', '0', '0',
            '2500', '4000', '1000', 'Sample employee'
        ])
        
        return response


class BulkApplyIncrementView(LoginRequiredMixin, AdminRequiredMixin, FormView):
    """Apply annual increments to multiple employees"""
    template_name = 'budgeting/employee_salary/bulk_increment.html'
    form_class = BulkIncrementForm
    success_url = reverse_lazy('budgeting:employee_salary_list')
    
    def form_valid(self, form):
        fiscal_year = form.cleaned_data['fiscal_year']
        department = form.cleaned_data.get('department')
        effective_date = form.cleaned_data['effective_date']
        
        # Get eligible employees
        queryset = BudgetEmployee.objects.filter(
            schedule__fiscal_year=fiscal_year,
            is_vacant=False,
            annual_increment_amount__gt=0
        )
        
        if department:
            queryset = queryset.filter(schedule__department=department)
        
        count = 0
        with transaction.atomic():
            for employee in queryset:
                # Apply increment to running basic
                from apps.budgeting.models_employee import get_running_basic
                from apps.budgeting.models import BPSSalaryScale
                
                scale = BPSSalaryScale.objects.filter(bps_grade=employee.bps).first()
                if scale:
                    # Calculate new running basic with one additional increment
                    increments_earned = (employee.running_basic - scale.basic_pay_min) / scale.annual_increment if scale.annual_increment > 0 else 0
                    new_running_basic = get_running_basic(
                        scale.basic_pay_min,
                        scale.annual_increment,
                        scale.basic_pay_max,
                        int(increments_earned) + 1
                    )
                    employee.running_basic = new_running_basic
                    employee.save(update_fields=['running_basic', 'updated_at'])
                    count += 1
        
        messages.success(
            self.request,
            f"✓ Applied annual increment to {count} employees effective {effective_date}"
        )
        return super().form_valid(form)


class BudgetBookReportView(LoginRequiredMixin, TemplateView):
    """
    Budget Book Report - Summary and detailed employee list
    """
    template_name = 'budgeting/employee_salary/budget_book.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        fiscal_year_id = self.request.GET.get('fiscal_year')
        if fiscal_year_id:
            fiscal_year = get_object_or_404(FiscalYear, id=fiscal_year_id)
        else:
            fiscal_year = FiscalYear.objects.filter(is_active=True).first()
        
        context['fiscal_year'] = fiscal_year
        
        if fiscal_year:
            # Get all employees for this fiscal year
            employees = BudgetEmployee.objects.filter(
                schedule__fiscal_year=fiscal_year,
                is_vacant=False
            ).select_related('schedule').order_by(
                'schedule__department', 'schedule__designation_name', 'name'
            )
            
            context['employees'] = employees
            
            # Summary by department
            dept_summary = {}
            for emp in employees:
                dept = emp.schedule.department
                if dept not in dept_summary:
                    dept_summary[dept] = {
                        'count': 0,
                        'basic_total': Decimal('0.00'),
                        'allowances_total': Decimal('0.00'),
                        'gross_total': Decimal('0.00'),
                        'annual_total': Decimal('0.00')
                    }
                
                dept_summary[dept]['count'] += 1
                dept_summary[dept]['basic_total'] += emp.running_basic
                dept_summary[dept]['allowances_total'] += emp.monthly_allowances
                dept_summary[dept]['gross_total'] += emp.monthly_gross
                dept_summary[dept]['annual_total'] += emp.annual_cost
            
            context['dept_summary'] = dept_summary
            
            # Grand totals
            context['grand_totals'] = {
                'employees': employees.count(),
                'basic': sum(d['basic_total'] for d in dept_summary.values()),
                'allowances': sum(d['allowances_total'] for d in dept_summary.values()),
                'gross': sum(d['gross_total'] for d in dept_summary.values()),
                'annual': sum(d['annual_total'] for d in dept_summary.values()),
            }
        
        context['fiscal_years'] = FiscalYear.objects.all().order_by('-start_date')
        
        return context


class BudgetBookExportView(LoginRequiredMixin, TemplateView):
    """Export Budget Book to CSV"""
    
    def get(self, request, *args, **kwargs):
        fiscal_year_id = request.GET.get('fiscal_year')
        if fiscal_year_id:
            fiscal_year = get_object_or_404(FiscalYear, id=fiscal_year_id)
        else:
            fiscal_year = FiscalYear.objects.filter(is_active=True).first()
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="budget_book_{fiscal_year.year_name}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Department', 'Designation', 'BPS', 'Name', 'Personnel No', 'CNIC',
            'Basic Pay', 'HRA', 'Conveyance', 'Medical', 'Adhoc Relief',
            'Special', 'Utility', 'Entertainment',
            'Total Allowances', 'Monthly Gross', 'GPF', 'Tax',
            'Monthly Net', 'Annual Cost'
        ])
        
        employees = BudgetEmployee.objects.filter(
            schedule__fiscal_year=fiscal_year,
            is_vacant=False
        ).select_related('schedule').order_by(
            'schedule__department', 'schedule__designation_name'
        )
        
        for emp in employees:
            writer.writerow([
                emp.schedule.department,
                emp.schedule.designation_name,
                emp.schedule.bps_scale,
                emp.name,
                emp.personnel_number,
                emp.cnic,
                f"{emp.current_basic_pay:.2f}",
                f"{emp.house_rent_allowance:.2f}",
                f"{emp.conveyance_allowance:.2f}",
                f"{emp.medical_allowance:.2f}",
                f"{emp.adhoc_relief_2024:.2f}",
                f"{emp.special_allowance:.2f}",
                f"{emp.utility_allowance:.2f}",
                f"{emp.entertainment_allowance:.2f}",
                f"{emp.total_monthly_allowances:.2f}",
                f"{emp.monthly_gross:.2f}",
                f"{emp.gpf_contribution:.2f}",
                f"{emp.income_tax:.2f}",
                f"{emp.monthly_net:.2f}",
                f"{emp.annual_cost:.2f}",
            ])
        
        return response


def load_department_functions(request):
    """AJAX endpoint to load functions for selected department"""
    department_id = request.GET.get('department_id')
    
    if not department_id:
        return JsonResponse({'functions': []})
    
    try:
        department = Department.objects.get(id=department_id)
        functions = department.related_functions.all().order_by('code')
        default_id = department.default_function_id if department.default_function else None
        
        function_list = [
            {
                'id': func.id,
                'code': func.code,
                'name': func.name,
                'is_default': func.id == default_id,
                'usage_notes': func.usage_notes or ''
            }
            for func in functions
        ]
        
        return JsonResponse({'functions': function_list})
    
    except Department.DoesNotExist:
        return JsonResponse({'functions': []})
