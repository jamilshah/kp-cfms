#!/usr/bin/env python
"""
Analyze BudgetHead to Function mappings and identify issues.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import BudgetHead, GlobalHead, FunctionCode
from apps.budgeting.models import Department
from django.db.models import Count, Q

def main():
    print("=" * 100)
    print("BUDGET HEAD TO FUNCTION MAPPING ANALYSIS")
    print("=" * 100)
    
    # 1. Function distribution
    print("\n1. HOW MANY BUDGET HEADS PER FUNCTION?")
    print("-" * 100)
    func_counts = BudgetHead.objects.values(
        'function__code', 'function__name'
    ).annotate(count=Count('id')).order_by('function__code')
    
    for f in func_counts:
        print(f"   {f['function__code']:<10} {f['function__name'][:45]:<47} : {f['count']:>4} heads")
    
    # 2. Global Head Scope Distribution
    print("\n2. GLOBAL HEAD SCOPE DISTRIBUTION:")
    print("-" * 100)
    scope_counts = GlobalHead.objects.values('scope').annotate(count=Count('id'))
    for s in scope_counts:
        print(f"   {s['scope']:<15} : {s['count']:>4} global heads")
    
    # 3. Universal heads (should be available to all functions)
    print("\n3. UNIVERSAL GLOBAL HEADS (Should work with ANY function):")
    print("-" * 100)
    universal = GlobalHead.objects.filter(scope='UNIVERSAL').order_by('code')[:20]
    for gh in universal:
        budget_head_count = BudgetHead.objects.filter(global_head=gh).values('function').distinct().count()
        print(f"   {gh.code:<10} {gh.name[:50]:<52} -> {budget_head_count:>2} functions")
    
    # 4. Departmental heads (should be limited to specific departments/functions)
    print("\n4. DEPARTMENTAL GLOBAL HEADS (Should be limited to specific functions):")
    print("-" * 100)
    departmental = GlobalHead.objects.filter(scope='DEPARTMENTAL').order_by('code')[:20]
    for gh in departmental:
        budget_head_count = BudgetHead.objects.filter(global_head=gh).values('function').distinct().count()
        functions = BudgetHead.objects.filter(global_head=gh).values_list('function__code', flat=True).distinct()
        func_str = ', '.join(list(functions)[:5])
        print(f"   {gh.code:<10} {gh.name[:40]:<42} -> {budget_head_count:>2} funcs ({func_str})")
    
    # 5. Check for redundant mappings
    print("\n5. CHECKING FOR REDUNDANT MAPPINGS:")
    print("-" * 100)
    
    # A. Universal heads mapped to multiple functions (expected, but check if ALL functions have them)
    universal_heads = GlobalHead.objects.filter(scope='UNIVERSAL')
    all_functions = FunctionCode.objects.filter(is_active=True).count()
    
    print(f"   Total active functions: {all_functions}")
    print(f"   Total universal global heads: {universal_heads.count()}")
    
    missing_mappings = []
    for gh in universal_heads[:10]:
        func_count = BudgetHead.objects.filter(global_head=gh).values('function').distinct().count()
        if func_count < all_functions and func_count > 0:
            missing_mappings.append((gh.code, gh.name, func_count, all_functions))
    
    if missing_mappings:
        print("\n   ⚠️  UNIVERSAL HEADS WITH INCOMPLETE MAPPINGS:")
        for code, name, has, should in missing_mappings:
            print(f"      {code:<10} {name[:40]:<42} : {has}/{should} functions")
    
    # B. Departmental heads that might be over-mapped
    print("\n   DEPARTMENTAL HEADS MAPPED TO MANY FUNCTIONS (Potential redundancy):")
    dept_heads = BudgetHead.objects.filter(
        global_head__scope='DEPARTMENTAL'
    ).values('global_head__code', 'global_head__name').annotate(
        func_count=Count('function', distinct=True)
    ).filter(func_count__gt=5).order_by('-func_count')[:10]
    
    for dh in dept_heads:
        print(f"      {dh['global_head__code']:<10} {dh['global_head__name'][:40]:<42} : {dh['func_count']:>2} functions")
    
    # 6. Sample mappings for major account types
    print("\n6. SAMPLE BUDGET HEAD MAPPINGS BY ACCOUNT TYPE:")
    print("-" * 100)
    
    sample_codes = ['A01151', 'A02201', 'A03303', 'C03803']
    for code in sample_codes:
        try:
            gh = GlobalHead.objects.get(code=code)
            heads = BudgetHead.objects.filter(global_head=gh).select_related('function')[:5]
            print(f"\n   {code} - {gh.name} (Scope: {gh.scope}):")
            for h in heads:
                print(f"      -> Function: {h.function.code} - {h.function.name}")
        except GlobalHead.DoesNotExist:
            print(f"\n   {code} - Not found")
    
    # 7. Department-Function relationship check
    print("\n7. DEPARTMENT TO FUNCTION ASSIGNMENTS:")
    print("-" * 100)
    departments = Department.objects.prefetch_related('related_functions').all()
    for dept in departments:
        func_count = dept.related_functions.count()
        default_func = dept.default_function.code if dept.default_function else 'None'
        print(f"   {dept.code:<8} {dept.name[:35]:<37} : {func_count:>2} functions (default: {default_func})")
    
    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    main()
