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


def search(patterns, text):
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def parse_money(value):
    if not value:
        return None

    value = value.replace(",", "")
    value = re.sub(r"(Rs\.?|INR|USD|EUR|GBP|\$|₹)", "", value, flags=re.I)
    value = value.strip()

    try:
        return float(value)
    except:
        return None


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    # ---------------- Invoice Number ----------------

    invoice_no = None

    invoice_patterns = [
        r"Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Za-z0-9\/\-]+)",
        r"Invoice\s*Reference\s*[:\-]?\s*([A-Za-z0-9\/\-]+)",
        r"Invoice\s*Ref(?:erence)?\s*[:\-]?\s*([A-Za-z0-9\/\-]+)",
        r"Inv(?:oice)?\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Za-z0-9\/\-]+)",
        r"Bill\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Za-z0-9\/\-]+)",
    ]

    for p in invoice_patterns:
        m = re.search(p, text, re.I)
        if m:
            invoice_no = m.group(1)
            break

    if invoice_no is None:
        for line in text.splitlines():
            if "invoice" in line.lower():
                m = re.search(r"([A-Z]{1,10}-\d+(?:-\d+)?)", line)
                if m:
                    invoice_no = m.group(1)
                    break

    # ---------------- Vendor ----------------

    vendor = search([
        r"Vendor\s*:\s*(.+)",
        r"Seller\s*:\s*(.+)",
        r"Supplier\s*:\s*(.+)",
        r"From\s*:\s*(.+)",
        r"Issued\s*By\s*:\s*(.+)",
        r"Company\s*:\s*(.+)",
    ], text)

    if vendor:
        vendor = vendor.split("\n")[0].strip()

    # ---------------- Date ----------------

    date_text = search([
        r"Invoice\s*Date\s*:\s*(.+)",
        r"Date\s*:\s*(.+)",
        r"Issued\s*On\s*:\s*(.+)",
    ], text)

    date = None

    if date_text:
        try:
            date = parser.parse(date_text, fuzzy=True).date().isoformat()
        except:
            pass

# ---------------- Amount ----------------

    amount = None

    amount_patterns = [
        r"Subtotal\s*[:\-]?\s*(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Sub\s*Total\s*[:\-]?\s*(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Net\s*Amount\s*[:\-]?\s*(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Amount\s*[:\-]?\s*(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Taxable\s*Amount\s*[:\-]?\s*(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Base\s*Amount\s*[:\-]?\s*(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Value\s*[:\-]?\s*(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+(?:\.\d+)?)",
    ]

    for p in amount_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
           amount = parse_money(m.group(1))
           break

    # ---------------- Tax ----------------

    tax = parse_money(search([
        r"GST.*?(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+\.\d+)",
        r"VAT.*?(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+\.\d+)",
        r"Tax.*?(?:Rs\.?|INR|USD|EUR|GBP|\$|₹)?\s*([\d,]+\.\d+)",
    ], text))

    # ---------------- Currency ----------------

    currency = search([
        r"Currency\s*:\s*([A-Z]{3})",
    ], text)

    if currency is None:
        if "USD" in text or "$" in text:
            currency = "USD"
        elif "EUR" in text:
            currency = "EUR"
        elif "GBP" in text:
            currency = "GBP"
        elif "INR" in text or "Rs" in text or "₹" in text:
            currency = "INR"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency,
    }