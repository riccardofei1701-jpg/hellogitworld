import sys
import json


def full_address(addr):
    addr = addr or {}
    street = addr.get("street", "")
    zip_ = addr.get("zip", "")
    city = addr.get("city", "")
    prov = addr.get("province", "")
    country = addr.get("country", "")
    locality = " ".join(p for p in [zip_, city] if p)
    if prov:
        locality = f"{locality} ({prov})" if locality else f"({prov})"
    return ", ".join(p for p in [street, locality, country] if p)


def party(role, p, with_cf):
    p = p or {}
    return {
        "role": role,
        "company_name": p.get("name", ""),
        "piva": p.get("vatNumber", ""),
        # cf is nullable in destination; the seller has no fiscalCode in source -> null
        "cf": p.get("fiscalCode") if with_cf else None,
        "full_address": full_address(p.get("address")),
    }


def transform(rec):
    d = rec.get("document", rec)

    items = {}
    for ln in d.get("lines", []) or []:
        # destination items is keyed by SKU (dynamic keys built from source lines)
        items[ln.get("sku")] = {
            "pos": ln.get("lineNo"),
            "text": ln.get("description"),
            "qty": ln.get("quantity"),
            "price": ln.get("unitPrice"),
            "iva_pct": ln.get("vatRate"),
            "amounts": {
                "imponibile": ln.get("netAmount"),
                "imposta": ln.get("vatAmount"),
                "totale": ln.get("grossAmount"),
            },
        }

    riepilogo = {}
    for s in d.get("vatSummary", []) or []:
        riepilogo[str(s.get("rate"))] = {
            "imponibile": s.get("taxable"),
            "imposta": s.get("tax"),
        }

    paid_card = 0
    paid_cash = 0
    for pay in d.get("payments", []) or []:
        m = str(pay.get("method", "")).lower()
        amt = pay.get("amount", 0) or 0
        # best effort: method names containing "card" or "cash" are bucketed accordingly
        if "card" in m or "credit" in m or "debit" in m:
            paid_card += amt
        elif "cash" in m:
            paid_cash += amt

    totals = d.get("totals", {}) or {}

    return {
        "doc_number": d.get("id"),
        "doc_kind": d.get("type"),
        "doc_date": d.get("issueDate"),  # format is "date" in destination, keep as is
        "currency_code": d.get("currency"),
        "parties": [
            party("seller", d.get("seller"), False),
            party("buyer", d.get("buyer"), True),
        ],
        "items": items,
        "riepilogo_iva": riepilogo,
        "total_net": totals.get("net"),
        "total_vat": totals.get("vat"),
        "total_gross": totals.get("gross"),
        "paid_card": paid_card,
        "paid_cash": paid_cash,
    }


def main():
    data = json.load(sys.stdin)
    if isinstance(data, list):
        out = [transform(r) for r in data]
    else:
        out = transform(data)
    sys.stdout.write(json.dumps(out))


main()