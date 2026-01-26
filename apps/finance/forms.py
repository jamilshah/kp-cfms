"""
Forms for the Finance module.
"""
from django import forms
from apps.finance.models import BudgetHead, FunctionCode

class BudgetHeadForm(forms.ModelForm):
    """
    Form for creating/editing Budget Heads (Chart of Accounts).
    """
    
    class Meta:
        model = BudgetHead
        fields = [
            'function', 'pifra_object', 'pifra_description',
            'tma_sub_object', 'tma_description',
            'account_type', 'fund',
            'is_active', 'is_charged',
            'budget_control', 'posting_allowed'
        ]
        widgets = {
            'function': forms.Select(attrs={'class': 'form-select'}),
            'pifra_object': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. A01101'}),
            'pifra_description': forms.TextInput(attrs={'class': 'form-control'}),
            'tma_sub_object': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. A01101-000'}),
            'tma_description': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'fund': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_charged': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'budget_control': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'posting_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
