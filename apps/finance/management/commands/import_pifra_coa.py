import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from apps.finance.models import MajorHead, MinorHead, GlobalHead, BudgetHead, Fund, AccountType

class Command(BaseCommand):
    help = 'Import PIFRA Chart of Accounts from Excel into normalized structure (MajorHead, MinorHead, GlobalHead, BudgetHead)'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the Excel file')
        parser.add_argument('--fund_code', type=str, required=False, help='Code of the Fund (GEN, DEV, PEN)')
        parser.add_argument('--fund_id', type=int, required=False, help='ID of the Fund')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        fund_id = kwargs['fund_id']
        fund_code = kwargs['fund_code']
        
        # 1. Validate Fund
        try:
            if fund_code:
                fund_instance = Fund.objects.get(code=fund_code.upper())
            elif fund_id:
                fund_instance = Fund.objects.get(id=fund_id)
            else:
                self.stderr.write(self.style.ERROR("You must provide either --fund_id or --fund_code"))
                return
                
            self.stdout.write(f"Linking to Fund: {fund_instance.name} ({fund_instance.code})")
        except Fund.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Fund not found. Please check your ID or Code."))
            return

        self.stdout.write("Reading Excel file... this might take a moment.")
        
        # Load Excel - expecting standard PIFRA format
        df = pd.read_excel(file_path, engine='openpyxl')

        # 2. Normalize Columns
        # Skip first row if it contains "Code", "Description" headers
        if df.iloc[0, 0] == 'Code':
            df = df.iloc[1:]  # Skip header row
            df = df.reset_index(drop=True)
        
        # Expected order: Major Code, Major Desc, Minor Code, Minor Desc, Detailed Code, Detailed Desc
        if len(df.columns) >= 6:
            # Drop any extra columns, keep first 6
            df = df.iloc[:, :6]
            df.columns = [
                'major_code', 'major_desc', 
                'minor_code', 'minor_desc', 
                'detailed_code', 'detailed_desc'
            ]
        else:
            self.stderr.write(self.style.ERROR(f"Excel file must have at least 6 columns. Found {len(df.columns)}."))
            return

        # 3. Data Cleaning
        # Forward fill parent categories (Major/Minor) for empty cells
        df['major_code'] = df['major_code'].ffill()
        df['major_desc'] = df['major_desc'].ffill()
        df['minor_code'] = df['minor_code'].ffill()
        df['minor_desc'] = df['minor_desc'].ffill()

        # Drop rows where 'detailed_code' is empty (these are usually headers or blank lines)
        df = df.dropna(subset=['detailed_code'])

        major_created = 0
        minor_created = 0
        global_created = 0
        budget_created = 0
        budget_updated = 0

        self.stdout.write("Processing rows...")

        # 4. Import Loop
        with transaction.atomic():
            for index, row in df.iterrows():
                code = str(row['detailed_code']).strip()
                description = str(row['detailed_desc']).strip()
                major_code = str(row['major_code']).strip()
                major_desc = str(row['major_desc']).strip()
                minor_code = str(row['minor_code']).strip()
                minor_desc = str(row['minor_desc']).strip()
                
                # Skip grouping headers (e.g., "A011-1 Pay of Officers")
                if 'Pay of Officers' in description or 'Pay of Other Staff' in description:
                    self.stdout.write(self.style.WARNING(f"Skipping grouping header: {description}"))
                    continue
                
                # Skip if code is not a valid detailed object (e.g. A011-1)
                # Valid codes are usually alphanumeric without dashes (A01101)
                if '-' in code or not code[0].isalnum():
                    continue

                # Determine Account Type based on first letter
                first_char = code[0].upper()
                if first_char == 'A':
                    ac_type = AccountType.EXPENDITURE
                elif first_char == 'C':
                    ac_type = AccountType.REVENUE
                elif first_char == 'F':
                    ac_type = AccountType.ASSET
                elif first_char == 'G':
                    ac_type = AccountType.LIABILITY
                else:
                    ac_type = AccountType.EXPENDITURE  # Default fallback

                try:
                    # Step 1: Create/Get MajorHead
                    major_head, created = MajorHead.objects.get_or_create(
                        code=major_code,
                        defaults={'name': major_desc}
                    )
                    if created:
                        major_created += 1
                        self.stdout.write(f"  Created Major: {major_code}")
                    
                    # Step 2: Create/Get MinorHead
                    minor_head, created = MinorHead.objects.get_or_create(
                        code=minor_code,
                        defaults={
                            'name': minor_desc,
                            'major': major_head
                        }
                    )
                    if created:
                        minor_created += 1
                        self.stdout.write(f"  Created Minor: {minor_code}")
                    
                    # Step 3: Create/Get GlobalHead
                    global_head, created = GlobalHead.objects.get_or_create(
                        code=code,
                        defaults={
                            'name': description,
                            'minor': minor_head,
                            'account_type': ac_type
                        }
                    )
                    if created:
                        global_created += 1
                        self.stdout.write(f"  Created Global: {code} - {description}")
                    
                    # Step 4: Create/Update BudgetHead (Fund-specific link)
                    budget_head, created = BudgetHead.objects.update_or_create(
                        fund=fund_instance,
                        global_head=global_head,
                        defaults={
                            'is_active': True,
                            'posting_allowed': True,
                            'budget_control': True
                        }
                    )
                    
                    if created:
                        budget_created += 1
                    else:
                        budget_updated += 1
                
                except IntegrityError as e:
                    self.stderr.write(f"Skipping duplicate or error on {code}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Done! Major: {major_created}, Minor: {minor_created}, "
            f"Global: {global_created}, BudgetHead Created: {budget_created}, Updated: {budget_updated}"
        ))