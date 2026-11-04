import json
import sys


def _full_address(addr):
    # Best-effort: destination has a single free-text address string, so the
    # structured source address is joined as "street, zip city (province), country".
    addr = addr or {}
    street = addr.get("street") or ""
    city_part = " ".join(p for p in (addr.get("zip") or "", addr.get("city") or "") if p)
    if addr.get("province"):
        city_part = f"{city_part} ({addr['province']})".strip()
    country = addr.get("country") or ""
    return ", ".join(p for p in (street, city_part, country) if p)


def _party(role, src, with_cf):
    src = src or {}
    cf = src.get("fiscalCode") if with_cf else None
    return {
        "role": role,  # best-effort: literal "seller"/"buyer" (no destination vocabulary given)
        "company_name": src.get("name"),
        "piva": src.get("vatNumber"),
        # cf is nullable; the seller has no fiscal code in the source, so null.
        "cf": cf if cf else None,
        "full_address": _full_address(src.get("address")),
    }


def _item(line):
    return {
        "pos": int(line["lineNo"]),
        "text": line.get("description"),
        "qty": int(line["quantity"]),
        "price": float(line["unitPrice"]),
        "iva_pct": int(line["vatRate"]),
        "amounts": {
            "imponibile": float(line["netAmount"]),
            "imposta": float(line["vatAmount"]),
            "totale": float(line["grossAmount"]),
        },
    }


def _paid(payments, method):
    # Best-effort: payments whose method equals "card"/"cash" (case-insensitive)
    # are summed; any other method is ignored; no payments -> 0.0.
    total = 0.0
    for p in payments or []:
        if str(p.get("method", "")).strip().lower() == method:
            total += float(p.get("amount", 0))
    return total


def transform_record(record):
    doc = record["document"]
    totals = doc.get("totals") or {}
    payments = doc.get("payments") or []
    # Items are keyed by SKU (dynamic keys).
    items = {line["sku"]: _item(line) for line in doc.get("lines") or []}
    # VAT summary keyed by rate as a string.
    riepilogo = {
        str(int(s["rate"])): {
            "imponibile": float(s["taxable"]),
            "imposta": float(s["tax"]),
        }
        for s in doc.get("vatSummary") or []
    }
    return {
        "doc_number": doc.get("id"),
        "doc_kind": doc.get("type"),
        "doc_date": doc.get("issueDate"),  # destination format is "date": unchanged
        "currency_code": doc.get("currency"),
        "parties": [
            _party("seller", doc.get("seller"), False),
            _party("buyer", doc.get("buyer"), True),
        ],
        "items": items,
        "riepilogo_iva": riepilogo,
        "total_net": float(totals.get("net", 0)),
        "total_vat": float(totals.get("vat", 0)),
        "total_gross": float(totals.get("gross", 0)),
        "paid_card": _paid(payments, "card"),
        "paid_cash": _paid(payments, "cash"),
    }


def transform(data):
    if isinstance(data, list):
        return [transform_record(r) for r in data]
    return transform_record(data)


def main():
    data = json.load(sys.stdin)
    sys.stdout.write(json.dumps(transform(data)))


if __name__ == "__main__":
    main()