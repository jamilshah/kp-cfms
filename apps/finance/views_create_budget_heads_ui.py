"""
View to create budget heads from configuration via UI.
"""
import json
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import render

from apps.users.permissions import SuperAdminRequiredMixin
from apps.finance.models import (
    DepartmentFunctionConfiguration,
    BudgetHead,
    Fund
)


class CreateBudgetHeadsFromConfigUIView(LoginRequiredMixin, SuperAdminRequiredMixin, View):
    """
    UI to create budget heads from configuration matrix.
    
    This provides a UI-friendly way to run the create_budget_heads_from_config
    management command without requiring terminal access.
    """
    template_name = 'finance/create_budget_heads_from_config.html'
    
    def get(self, request, *args, **kwargs):
        """Display the bulk creation form."""
        # Get available funds
        funds = Fund.objects.filter(is_active=True).order_by('code')
        
        # Get configuration statistics
        configs_count = DepartmentFunctionConfiguration.objects.filter(
            allowed_nam_heads__isnull=False
        ).distinct().count()
        
        # Count total NAM heads that would be created
        total_nam_heads = 0
        for config in DepartmentFunctionConfiguration.objects.filter(
            allowed_nam_heads__isnull=False
        ).prefetch_related('allowed_nam_heads').distinct():
            total_nam_heads += config.allowed_nam_heads.count()
        
        context = {
            'funds': funds,
            'configs_count': configs_count,
            'total_nam_heads': total_nam_heads,
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            fund_code = data.get('fund')
            overwrite = data.get('overwrite', False)
            
            if not fund_code:
                return JsonResponse({
                    'success': False,
                    'error': 'Fund code is required'
                }, status=400)
            
            try:
                fund = Fund.objects.get(code=fund_code, is_active=True)
            except Fund.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Fund "{fund_code}" not found or inactive'
                }, status=404)
            
            # Get all configurations with allowed NAM heads
            configs = DepartmentFunctionConfiguration.objects.filter(
                allowed_nam_heads__isnull=False
            ).prefetch_related('allowed_nam_heads').distinct()
            
            if not configs.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'No configurations found with allowed NAM heads'
                }, status=400)
            
            created_count = 0
            updated_count = 0
            skipped_count = 0
            errors = []
            
            with transaction.atomic():
                for config in configs:
                    dept = config.department
                    func = config.function
                    allowed_heads = config.allowed_nam_heads.all()
                    
                    if not allowed_heads:
                        continue
                    
                    for nam_head in allowed_heads:
                        try:
                            # Check if budget head already exists
                            existing = BudgetHead.objects.filter(
                                department=dept,
                                function=func,
                                fund=fund,
                                nam_head=nam_head,
                                sub_head__isnull=True  # Only NAM heads, not sub-heads
                            ).first()
                            
                            if existing:
                                if overwrite:
                                    existing.is_active = True
                                    existing.save(update_fields=['is_active'])
                                    updated_count += 1
                                else:
                                    skipped_count += 1
                            else:
                                BudgetHead.objects.create(
                                    department=dept,
                                    function=func,
                                    fund=fund,
                                    nam_head=nam_head,
                                    sub_head=None,
                                    is_active=True,
                                    budget_control=True,
                                    posting_allowed=True  # Allow posting by default for usability
                                )
                                created_count += 1
                        
                        except Exception as e:
                            error_msg = f'{dept.code}+{func.code}+{nam_head.code}: {str(e)}'
                            errors.append(error_msg)
            
            return JsonResponse({
                'success': True,
                'created': created_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'errors': errors,
                'fund': fund_code
            })
        
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
