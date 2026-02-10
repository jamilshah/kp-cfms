"""
API view to fetch sub-heads for a NAM head.
"""
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404

from apps.finance.models import NAMHead


class NAMHeadSubHeadsAPIView(LoginRequiredMixin, View):
    """
    AJAX endpoint to fetch sub-heads for a specific NAM head.
    
    Returns JSON with list of sub-heads.
    """
    
    def get(self, request, nam_head_id, *args, **kwargs):
        try:
            nam_head = get_object_or_404(NAMHead, pk=nam_head_id)
            
            # Get all sub-heads for this NAM head
            sub_heads = nam_head.sub_heads.all().order_by('sub_code')
            
            sub_heads_data = []
            for sub_head in sub_heads:
                sub_heads_data.append({
                    'id': sub_head.id,
                    'code': sub_head.code,  # Full code like A01101-01
                    'sub_code': sub_head.sub_code,  # Just the sub part like 01
                    'name': sub_head.name,
                    'description': sub_head.description,
                    'is_active': sub_head.is_active,
                })
            
            return JsonResponse({
                'success': True,
                'nam_head': {
                    'id': nam_head.id,
                    'code': nam_head.code,
                    'name': nam_head.name,
                },
                'sub_heads': sub_heads_data,
                'count': len(sub_heads_data)
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
