"""
-------------------------------------------------------------------------
Example: Using HierarchicalBudgetHeadWidget in Forms
-------------------------------------------------------------------------

This file shows how to use the new hierarchical widget for budget head selection
with the clean 5-level NAM structure.
"""

from django import forms
from apps.finance.models import BudgetHead
from apps.finance.widgets import HierarchicalBudgetHeadWidget


class ExampleVoucherLineForm(forms.Form):
    """
    Example form showing hierarchical budget head selection.
    
    The widget automatically groups by Major Head and indents sub-heads
    for easy visual navigation.
    """
    
    budget_head = forms.ModelChoiceField(
        queryset=BudgetHead.objects.none(),  # Will be filtered by init
        label="Budget Head",
        help_text="Select the account head to post this transaction"
    )
    description = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    debit = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    credit = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    def __init__(self, department=None, function=None, fund=None, *args, **kwargs):
        """
        Initialize form with context for filtering budget heads.
        
        Args:
            department: Department instance (required for filtering)
            function: FunctionCode instance (required for filtering)
            fund: Fund instance (optional additional filter)
        """
        super().__init__(*args, **kwargs)
        
        if department and function:
            # Use hierarchical widget with filtering
            self.fields['budget_head'].widget = HierarchicalBudgetHeadWidget(
                department=department,
                function=function,
                fund=fund
            )
            
            # Filter queryset
            self.fields['budget_head'].queryset = BudgetHead.objects.for_transaction_entry(
                department=department,
                function=function,
                fund=fund
            )


class ExampleBudgetHeadCreateForm(forms.ModelForm):
    """
    Example form for creating budget heads using the clean NAM/SubHead structure.
    
    Key points:
    1. User selects EITHER nam_head OR sub_head (not both)
    2. Validation ensures NAM head allows direct posting
    3. Sub-heads automatically disable parent NAM posting
    """
    
    class Meta:
        model = BudgetHead
        fields = [
            'department',
            'fund',
            'function',
            'nam_head',
            'sub_head',
            'budget_control',
            'posting_allowed',
            'is_active'
        ]
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'fund': forms.Select(attrs={'class': 'form-select'}),
            'function': forms.Select(attrs={'class': 'form-select'}),
            'nam_head': forms.Select(attrs={'class': 'form-select'}),
            'sub_head': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add help text
        self.fields['nam_head'].help_text = (
            'Select a NAM Head (Level 4) if it has no sub-heads. '
            'Leave empty if using Sub-Head.'
        )
        self.fields['sub_head'].help_text = (
            'Select a Sub-Head (Level 5) for granular tracking. '
            'Leave empty if using NAM Head directly.'
        )
        
        # Add JavaScript to make fields mutually exclusive
        self.fields['nam_head'].widget.attrs.update({
            'onchange': 'if(this.value) document.getElementById("id_sub_head").value = "";'
        })
        self.fields['sub_head'].widget.attrs.update({
            'onchange': 'if(this.value) document.getElementById("id_nam_head").value = "";'
        })
    
    def clean(self):
        """Validate that exactly one of nam_head or sub_head is set."""
        cleaned_data = super().clean()
        nam_head = cleaned_data.get('nam_head')
        sub_head = cleaned_data.get('sub_head')
        
        if not nam_head and not sub_head:
            raise forms.ValidationError(
                'Please select either a NAM Head or a Sub-Head'
            )
        
        if nam_head and sub_head:
            raise forms.ValidationError(
                'Cannot select both NAM Head and Sub-Head. Choose one.'
            )
        
        return cleaned_data


# ============================================================================
# Usage Example in Views
# ============================================================================
"""
# In your view:

def journal_entry_view(request):
    # Get context from user/session
    department = request.user.profile.department
    function = FunctionCode.objects.get(code='AD')  # Or from form selection
    fund = Fund.objects.get(code='GEN')
    
    if request.method == 'POST':
        form = ExampleVoucherLineForm(
            department=department,
            function=function,
            fund=fund,
            data=request.POST
        )
        if form.is_valid():
            # Process form...
            pass
    else:
        form = ExampleVoucherLineForm(
            department=department,
            function=function,
            fund=fund
        )
    
    return render(request, 'template.html', {'form': form})


# The widget will render a dropdown like this:
# 
# A01 - Employee Related Expenses
#   A01101 - Basic Pay - Officers
#   A01151 - Basic Pay - Other Staff
# 
# A12 - Physical Assets
#   A12001 - Roads (Select below)       [disabled]
#     └─ A12001-01 - PCC Streets        [selectable]
#     └─ A12001-02 - Shingle Roads      [selectable]
#     └─ A12001-03 - Tough Tiles        [selectable]
"""
