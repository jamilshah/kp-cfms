import csv
import os

# Define PIFRA Mappings (Standard Pakistan Chart of Accounts)
PIFRA_MAP = {
    # MAJOR HEADS
    "A01": "Employee Related Expenses",
    "A03": "Operating Expenses",
    "A04": "Employees Retirement Benefits",
    "A05": "Grants Subsidies & Write Off Loans",
    "A06": "Transfers",
    "A09": "Physical Assets",
    "A12": "Civil Works",
    "A13": "Repairs & Maintenance",
    "C02": "Receipts from Civil Admin",
    "C03": "Miscellaneous Receipts",
    
    # MINOR HEADS (Common subset)
    "A011": "Pay",
    "A012": "Allowances",
    "A032": "Communications",
    "A033": "Utilities",
    "A034": "Occupancy Costs",
    "A036": "Motor Vehicles",
    "A038": "Travel & Transportation",
    "A039": "General",
    "A041": "Pension",
    "A052": "Grants Domestic",
    "A063": "Transfer Payments",
    "A092": "Computer Equipment",
    "A095": "Purchase of Transport",
    "A096": "Purchase of Plant & Machinery",
    "A097": "Purchase of Furniture",
    "A124": "Buildings & Structures",
    "A130": "Transport",
    "A131": "Machinery & Equipment",
    "A132": "Furniture & Fixture",
    "A133": "Buildings",
    "A137": "Computer Equipment",
    "C023": "General Administration Receipts",
    "C027": "Community Services Receipts", # e.g. Building plans
    "C038": "Other Receipts",
}

def get_pifra_desc(code):
    return PIFRA_MAP.get(code, "Others/Misc")

def process_coa(input_file='docs/CoA.csv', output_file='docs/CoA_Updated.csv'):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, mode='r', encoding='utf-8-sig') as infile, \
         open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
        
        reader = csv.DictReader(infile)
        # Create new header with Major/Minor columns inserted
        fieldnames = [
            'Entity', 'Fund', 'Function', 
            'Major_Object', 'Major_Description', 
            'Minor_Object', 'Minor_Description', 
            'PIFRA_Object', 'PIFRA_Description', 
            'TMA_Sub_Object', 'TMA_Sub_Description', 
            'Account_Type', 'Budget_Control', 'Project_Required', 'Posting_Allowed'
        ]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            pifra_obj = row.get('PIFRA_Object', '').strip()
            
            # Derive Codes
            major_code = pifra_obj[:3] if len(pifra_obj) >= 3 else ""
            minor_code = pifra_obj[:4] if len(pifra_obj) >= 4 else ""
            
            # Map Descriptions
            row['Major_Object'] = major_code
            row['Major_Description'] = get_pifra_desc(major_code)
            row['Minor_Object'] = minor_code
            row['Minor_Description'] = get_pifra_desc(minor_code)
            
            # Write row
            writer.writerow(row)

    print(f"Success! Updated CoA saved to {output_file}")

if __name__ == "__main__":
    process_coa()