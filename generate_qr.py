"""
Run this once to pre-generate QR images for each plan.
Usage: python generate_qr.py
"""
import qrcode, os

UPI_ID = "vansh@upi"
MERCHANT_NAME = "EHealth"

plans = [
    (1, "Basic Plan",   299),
    (2, "Premium Plan", 799),
    (3, "Family Plan",  1499),
]

os.makedirs("static/qr", exist_ok=True)

for plan_id, plan_name, amount in plans:
    upi_url = f"upi://pay?pa={UPI_ID}&pn={MERCHANT_NAME}&am={amount}&cu=INR&tn={plan_name.replace(' ', '%20')}"
    img = qrcode.make(upi_url)
    img.save(f"static/qr/plan_{plan_id}.png")
    print(f"Generated: static/qr/plan_{plan_id}.png  →  {upi_url}")

print("Done.")
