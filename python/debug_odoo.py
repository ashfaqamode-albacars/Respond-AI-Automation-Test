import sys
sys.path.insert(0, '.')
from utils.odoo import authenticate, search_read, get_lead_by_phone, get_activities_for_lead

# Test 1: authenticate
print("=== Test 1: Authenticate ===")
try:
    uid = authenticate()
    print("UID:", uid)
except Exception as e:
    print("FAILED:", e)

# Test 2: simple search_read on a known model
print("\n=== Test 2: search_read res.users ===")
try:
    result = search_read(
        model="x_sales_crm",
        domain=[["id", "=", 187670]],
        fields=["x_name"],
        limit=1
    )
    print("Result:", result)
except Exception as e:
    print("FAILED:", e)

# Test 3: search on x_sales_crm
print("\n=== Test 3: search x_sales_crm ===")
try:
    leads = search_read(
        model="x_sales_crm",
        domain=[["id", "=", 187670]],
        fields=["id", "x_name", "x_studio_stage_id"],
        limit=3
    )
    print("Leads found:", len(leads))
    for l in leads:
        print(" -", l)
except Exception as e:
    print("FAILED:", e)

# Test 4: get lead by your phone number
print("\n=== Test 4: get_lead_by_phone ===")
try:
    lead = get_lead_by_phone("504450876")
    print("Lead:", lead)
except Exception as e:
    print("FAILED:", e)