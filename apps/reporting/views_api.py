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
        
        # Search in code, name, function, sub-code, and ID
        budget_heads = BudgetHead.objects.filter(
            is_active=True
        ).filter(
            Q(id__icontains=query) |
            Q(nam_head__code__icontains=query) |
            Q(nam_head__name__icontains=query) |
            Q(function__code__icontains=query) |
            Q(function__name__icontains=query) |
            Q(sub_code__icontains=query)
        ).select_related(
            'fund', 'function', 'nam_head'
        ).distinct()[:50]  # Limit to 50 results
        
        results = []
        for head in budget_heads:
            # Show full code with function name and sub-code to differentiate similar budget heads
            # e.g., "FGEN-AD-H01105-01 - Retained Earnings [Admin] (Sub: 01)"
            function_name = head.function.name if head.function else ""
            display_text = f"{head.code} - {head.nam_head.name}"
            if function_name:
                display_text += f" [{function_name}]"
            if head.sub_code:
                display_text += f" (Sub: {head.sub_code})"
            
            results.append({
                'id': head.id,
                'text': display_text
            })
        
        return JsonResponse({'results': results})
