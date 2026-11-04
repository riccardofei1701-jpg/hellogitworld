from etl_job import transform


def make_doc():
    return {
        "document": {
            "id": "1",
            "type": "invoice",
            "issueDate": "2024-01-02",
            "currency": "EUR",
            "seller": {
                "name": "Name 1",
                "vatNumber": "VAT1",
                "address": {"street": "Street 1", "city": "City 1", "zip": "00001",
                            "province": "P1", "country": "C1"},
            },
            "buyer": {
                "name": "Name 2",
                "vatNumber": "VAT2",
                "fiscalCode": "FC2",
                "address": {"street": "Street 2", "city": "City 2", "zip": "00002",
                            "province": "P2", "country": "C2"},
            },
            "lines": [
                {"lineNo": 1, "sku": "SKU-1", "description": "Item 1", "quantity": 2,
                 "unitPrice": 10.0, "vatRate": 22, "netAmount": 20.0,
                 "vatAmount": 4.4, "grossAmount": 24.4},
                {"lineNo": 2, "sku": "SKU-2", "description": "Item 2", "quantity": 1,
                 "unitPrice": 5.0, "vatRate": 4, "netAmount": 5.0,
                 "vatAmount": 0.2, "grossAmount": 5.2},
            ],
            "vatSummary": [
                {"rate": 22, "taxable": 20.0, "tax": 4.4},
                {"rate": 4, "taxable": 5.0, "tax": 0.2},
            ],
            "totals": {"net": 25.0, "vat": 4.6, "gross": 29.6},
            "payments": [
                {"method": "card", "amount": 20.0},
                {"method": "cash", "amount": 9.6},
            ],
        }
    }


def test_happy_path():
    out = transform(make_doc())
    assert out["doc_number"] == "1"
    assert out["doc_kind"] == "invoice"
    assert out["doc_date"] == "2024-01-02"
    assert out["currency_code"] == "EUR"
    assert out["items"]["SKU-1"] == {
        "pos": 1, "text": "Item 1", "qty": 2, "price": 10.0, "iva_pct": 22,
        "amounts": {"imponibile": 20.0, "imposta": 4.4, "totale": 24.4},
    }
    assert out["items"]["SKU-2"]["iva_pct"] == 4
    assert out["riepilogo_iva"]["22"] == {"imponibile": 20.0, "imposta": 4.4}
    assert out["riepilogo_iva"]["4"] == {"imponibile": 5.0, "imposta": 0.2}
    assert (out["total_net"], out["total_vat"], out["total_gross"]) == (25.0, 4.6, 29.6)
    assert out["paid_card"] == 20.0
    assert out["paid_cash"] == 9.6


def test_parties_and_nullable_cf():
    out = transform(make_doc())
    seller, buyer = out["parties"]
    assert buyer["cf"] == "FC2"
    assert buyer["piva"] == "VAT2"
    assert buyer["company_name"] == "Name 2"
    assert seller["cf"] is None
    assert seller["full_address"] == "Street 1, 00001 City 1 (P1), C1"


def test_buyer_cf_absent_is_null():
    d = make_doc()
    del d["document"]["buyer"]["fiscalCode"]
    assert transform(d)["parties"][1]["cf"] is None


def test_type_coercion():
    d = make_doc()
    line = d["document"]["lines"][0]
    line["quantity"] = "3"
    line["unitPrice"] = 10
    line["vatRate"] = "22"
    out = transform(d)
    item = out["items"]["SKU-1"]
    assert item["qty"] == 3 and isinstance(item["qty"], int)
    assert item["price"] == 10.0 and isinstance(item["price"], float)
    assert item["iva_pct"] == 22 and isinstance(item["iva_pct"], int)


def test_list_input():
    out = transform([make_doc(), make_doc()])
    assert isinstance(out, list) and len(out) == 2


def test_unresolved_payment_best_effort():
    d = make_doc()
    d["document"]["payments"] = [{"method": "Card", "amount": 3},
                                 {"method": "wire", "amount": 7.0}]
    out = transform(d)
    assert out["paid_card"] == 3.0
    assert out["paid_cash"] == 0.0


def test_unresolved_role_best_effort():
    out = transform(make_doc())
    assert [p["role"] for p in out["parties"]] == ["seller", "buyer"]