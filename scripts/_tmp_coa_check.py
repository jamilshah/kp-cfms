from apps.finance.models import GlobalHead, BudgetHead, AccountType

print('GlobalHead counts by account_type:')
for k,label in AccountType.choices:
    print(k, GlobalHead.objects.filter(account_type=k).count())

print('\nBudgetHead counts by global_head.account_type:')
for k,label in AccountType.choices:
    print(k, BudgetHead.objects.filter(global_head__account_type=k).count())
