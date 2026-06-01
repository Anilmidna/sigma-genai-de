import csv
import os

src_path = "/Users/as-mac-1122/Downloads/GenAI_D6/sigma-genai-de/day11/lab/manual_first_exercise.csv"
dest_path = "/Users/as-mac-1122/Downloads/GenAI_D6/sigma-genai-de/day11/lab/manual_first_annotated.csv"

with open(src_path, mode='r', newline='', encoding='utf-8') as infile:
    reader = csv.reader(infile)
    header = next(reader)
    rows = list(reader)

for row in rows:
    # row index mapping:
    # 0: transaction_id, 1: merchant_name, 2: category, 3: amount, 4: currency
    # 5: transaction_date, 6: status, 7: customer_id, 8: payment_method
    # 9: merchant_city, 10: issue_found, 11: severity, 12: auto_fixable
    
    tx_id = row[0]
    m_name = row[1]
    amount = row[3]
    currency = row[4]
    date = row[5]
    status = row[6]
    
    # If the annotation is already set, don't overwrite it
    if row[10]:
        continue
        
    # Check Row 34: date is "99-99-9999"
    if date == "99-99-9999":
        row[10] = "invalid date format"
        row[11] = "H"
        row[12] = "No"
        
    # Check Row 42: currency is "IND"
    elif currency == "IND":
        row[10] = "invalid currency code"
        row[11] = "M"
        row[12] = "Yes"
        
    # Check Row 49: date is "2026/06/02" (contains slashes)
    elif "/" in date:
        row[10] = "invalid date format (slashes)"
        row[11] = "L"
        row[12] = "Yes"
        
    # Check Row 80: amount contains comma/quotes
    elif "," in amount:
        row[10] = "amount contains commas/quotes"
        row[11] = "L"
        row[12] = "Yes"
        
    # Check Row 86: status is "Completed" (capitalized)
    elif status == "Completed":
        row[10] = "status is capitalized"
        row[11] = "L"
        row[12] = "Yes"
        
    # Check Row 98: future date "2026-12-31"
    elif date == "2026-12-31":
        row[10] = "future transaction date"
        row[11] = "M"
        row[12] = "No"

with open(dest_path, mode='w', newline='', encoding='utf-8') as outfile:
    writer = csv.writer(outfile)
    writer.writerow(header)
    writer.writerows(rows)

print("Annotated file generated successfully at", dest_path)
