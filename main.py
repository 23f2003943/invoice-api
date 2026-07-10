from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


def find(patterns, text):
    for p in patterns:
        m = re.search(p, text, re.I | re.M)
        if m:
            return m.group(1).strip()
    return None


def money(value):
    if value is None:
        return None
    value = value.replace(",", "")
    value = re.sub(r"(Rs\.?|INR|USD|\$)", "", value, flags=re.I).strip()
    try:
        return float(value)
    except:
        return None


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    invoice_no = find([
        r"Invoice\s*(?:No|#)?\s*[:#]\s*([A-Za-z0-9\-\/]+)",
    ], text)

    vendor = find([
        r"Vendor\s*:\s*(.+)",
        r"Seller\s*:\s*(.+)",
        r"Supplier\s*:\s*(.+)",
    ], text)

    date_text = find([
        r"Date\s*:\s*(.+)"
    ], text)

    date = None
    if date_text:
        try:
            date = parser.parse(date_text).date().isoformat()
        except:
            pass

    amount = money(find([
        r"Subtotal.*?([A-Z]{3}\s*[\d,]+\.\d+)",
        r"Subtotal.*?(Rs\.?\s*[\d,]+\.\d+)",
        r"Subtotal.*?([\d,]+\.\d+)",
    ], text))

    tax = money(find([
        r"(?:GST|VAT|Tax).*?([A-Z]{3}\s*[\d,]+\.\d+)",
        r"(?:GST|VAT|Tax).*?(Rs\.?\s*[\d,]+\.\d+)",
        r"(?:GST|VAT|Tax).*?([\d,]+\.\d+)",
    ], text))

    currency = find([
    r"Currency\s*:\s*([A-Z]{3})",
    r"Subtotal\s*:\s*(USD)",
    r"Subtotal\s*:\s*(INR)",
    r"Subtotal\s*:\s*(Rs)",
    ], text)

    if currency == "Rs":
        currency = "INR"

    if currency is None:
        if "USD" in text:
            currency = "USD"
        elif "Rs" in text or "INR" in text:
            currency = "INR"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency,
    }