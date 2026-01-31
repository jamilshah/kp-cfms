import re

# Read the file
with open('apps/expenditure/tests_signals.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find Bill.objects.create with bill_date but no fiscal_year
# Captures the indentation and preserves it
pattern = r'(Bill\.objects\.create\(\s*\n\s+bill_number="[^"]+",\s*\n\s+bill_date=date\.today\(\),)(\s*\n\s+organization=)'

def add_fiscal_year(match):
    before = match.group(1)
    after = match.group(2)
    # Extract indentation from the organization line
    indent = after.split('organization=')[0].strip('\n')
    return f"{before}\n{indent}fiscal_year=self.fiscal_year,{after}"

# Apply replacement
new_content = re.sub(pattern, add_fiscal_year, content)

# Write back
with open('apps/expenditure/tests_signals.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Updated Bill.objects.create calls")
