"""
AJAX API views for reporting module.
"""
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db.models import Q

from apps.core.mixins import TenantAwareMixin
from apps.finance.models import BudgetHead


class BudgetHeadAutocompleteView(LoginRequiredMixin, TenantAwareMixin, View):
    """
    AJAX endpoint for budget head autocomplete.
    
    Returns JSON list of budget heads matching the search query.
    """
    
    def get(self, request):
        query = request.GET.get('q', '').strip()
        
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        # Search in code and name
        budget_heads = BudgetHead.objects.filter(
            is_active=True
        ).filter(
            Q(global_head__code__icontains=query) |
            Q(global_head__name__icontains=query) |
            Q(function__code__icontains=query)
        ).select_related(
            'fund', 'function', 'global_head'
        ).distinct()[:50]  # Limit to 50 results
        
        results = []
        for head in budget_heads:
            # Show full code with function name to differentiate similar budget heads
            # e.g., "FGEN-AD-H01105 - Retained Earnings [Admin]"
            function_name = head.function.name if head.function else ""
            display_text = f"{head.code} - {head.global_head.name}"
            if function_name:
                display_text += f" [{function_name}]"
            
            results.append({
                'id': head.id,
                'text': display_text
            })
        
        return JsonResponse({'results': results})
