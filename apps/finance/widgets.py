"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Description: Custom widgets for finance app including hierarchical
             budget head selection
-------------------------------------------------------------------------
"""
from django import forms
from django.utils.html import format_html


class HierarchicalBudgetHeadWidget(forms.Select):
    """
    Dropdown widget with hierarchical grouping and indentation.
    
    Displays budget heads in a hierarchical structure:
    - Major Heads as optgroups
    - NAM Heads (Level 4) as selectable options
    - NAM Heads with Sub-Heads shown as disabled with sub-heads indented below
    - Sub-Heads (Level 5) as indented selectable options
    
    Usage:
        field.widget = HierarchicalBudgetHeadWidget(
            department=department,
            function=function,
            fund=fund
        )
    """
    
    def __init__(self, department=None, function=None, fund=None, **kwargs):
        """
        Initialize widget with context for filtering budget heads.
        
        Args:
            department: Department instance for filtering
            function: FunctionCode instance for filtering
            fund: Fund instance for filtering
        """
        self.department = department
        self.function = function
        self.fund = fund
        super().__init__(**kwargs)
    
    def optgroups(self, name, value, attrs=None):
        """
        Group options by Major Head with sub-heads indented.
        
        Returns hierarchical structure:
        
        A01 - Employee Related Expenses
            A01101 - Basic Pay - Officers
            A01151 - Basic Pay - Other Staff
        
        A12 - Physical Assets
            A12001 - Roads (Select below)
                └─ A12001-01 - PCC Streets
                └─ A12001-02 - Shingle Roads
        """
        if not self.department or not self.function:
            return []
        
        from apps.finance.models import BudgetHead
        
        try:
            tree = BudgetHead.objects.get_hierarchy_tree(
                self.department,
                self.function,
                self.fund
            )
        except Exception:
            # Fallback to empty if error
            return []
        
        groups = []
        
        for major_code, major_data in sorted(tree.items()):
            options = []
            
            for head in major_data.get('heads', []):
                if head['type'] == 'NAM':
                    # Simple NAM head (no sub-heads) - selectable
                    label = f"{head['code']} - {head['name']}"
                    options.append(
                        self.create_option(
                            name,
                            head['id'],
                            label,
                            [value] if isinstance(value, (str, int)) else value,
                            0
                        )
                    )
                
                elif head['type'] == 'NAM_WITH_SUBS':
                    # NAM with sub-heads - show as disabled parent
                    label = f"{head['code']} - {head['name']} (Select below)"
                    opt = self.create_option(
                        name,
                        '',  # Empty value
                        label,
                        [],
                        0
                    )
                    opt['attrs']['disabled'] = True
                    opt['attrs']['style'] = 'font-weight: bold; color: #666; background-color: #f5f5f5;'
                    options.append(opt)
                    
                    # Add sub-heads indented
                    for sub in head.get('sub_heads', []):
                        sub_label = f"    └─ {sub['code']} - {sub['name']}"
                        sub_opt = self.create_option(
                            name,
                            sub['id'],
                            sub_label,
                            [value] if isinstance(value, (str, int)) else value,
                            0
                        )
                        sub_opt['attrs']['style'] = 'padding-left: 30px;'
                        options.append(sub_opt)
            
            if options:
                group_label = f"{major_code} - {major_data.get('name', 'Unknown')}"
                groups.append((
                    group_label,
                    options,
                    0
                ))
        
        return groups
    
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        """
        Create a single option element.
        
        Overrides parent to ensure proper option structure.
        """
        if attrs is None:
            attrs = {}
        
        option_value = '' if value is None else str(value)
        option_attrs = {
            'value': option_value,
            **self.build_attrs(self.attrs if index == 0 and subindex is None else {}, attrs),
        }
        
        if value in selected or (isinstance(value, str) and str(value) in map(str, selected)):
            option_attrs['selected'] = True
        
        return {
            'name': name,
            'value': option_value,
            'label': label,
            'selected': option_attrs.get('selected', False),
            'index': str(index),
            'attrs': option_attrs,
            'type': self.input_type,
            'template_name': self.option_template_name,
            'wrap_label': True,
        }


class SimpleHierarchicalWidget(forms.Select):
    """
    Simplified hierarchical widget without department/function filtering.
    
    Useful for admin forms where you want basic grouping by Major Head
    without complex context-aware filtering.
    """
    
    def __init__(self, group_by='major', **kwargs):
        """
        Initialize simple hierarchical widget.
        
        Args:
            group_by: Grouping level ('major' or 'minor')
        """
        self.group_by = group_by
        super().__init__(**kwargs)
    
    def optgroups(self, name, value, attrs=None):
        """Simple grouping by major or minor head."""
        from apps.finance.models import BudgetHead
        from collections import defaultdict
        
        groups = defaultdict(list)
        queryset = self.choices.queryset if hasattr(self.choices, 'queryset') else []
        
        for head in queryset:
            if self.group_by == 'major':
                group_key = f"{head.major_code} - {head.nam_head.minor.major.name if head.nam_head else head.sub_head.nam_head.minor.major.name}"
            else:
                group_key = f"{head.minor_code} - {head.nam_head.minor.name if head.nam_head else head.sub_head.nam_head.minor.name}"
            
            label = f"{head.code} - {head.name}"
            groups[group_key].append(
                self.create_option(
                    name,
                    head.id,
                    label,
                    [value] if isinstance(value, (str, int)) else value,
                    0
                )
            )
        
        return [(group_name, options, 0) for group_name, options in sorted(groups.items())]
