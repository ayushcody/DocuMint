from __future__ import annotations

from pathlib import Path

import fitz

GOLDEN_SET = Path("golden_set")


def main() -> None:
    GOLDEN_SET.mkdir(exist_ok=True)
    _sec_10k(GOLDEN_SET / "sec_10k.pdf")
    _invoice(GOLDEN_SET / "invoice.pdf")
    _bank_statement(GOLDEN_SET / "bank_statement.pdf")
    _scanned_contract(GOLDEN_SET / "scanned_contract.pdf")
    _academic_paper(GOLDEN_SET / "academic_paper.pdf")
    _phone_photo(GOLDEN_SET / "phone_photo.pdf")
    _handwritten(GOLDEN_SET / "handwritten.pdf")
    print("Generated 7 golden PDFs in golden_set/")


def _new_doc(page_count: int) -> fitz.Document:
    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page(width=612, height=792)
    return doc


def _write_page(page: fitz.Page, title: str, lines: list[str], y: float = 72) -> None:
    page.insert_text((72, y), title, fontsize=22, fontname="helv")
    cursor = y + 42
    for line in lines:
        page.insert_text((72, cursor), line, fontsize=11, fontname="helv")
        cursor += 18


def _draw_table(page: fitz.Page, x: float, y: float, rows: list[list[str]]) -> None:
    col_width = 110
    row_height = 24
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            rect = fitz.Rect(
                x + col_index * col_width,
                y + row_index * row_height,
                x + (col_index + 1) * col_width,
                y + (row_index + 1) * row_height,
            )
            page.draw_rect(rect, color=(0, 0, 0), width=0.7)
            page.insert_text(
                (rect.x0 + 4, rect.y0 + 15),
                value,
                fontsize=9,
                fontname="helv",
            )


def _save(doc: fitz.Document, path: Path) -> None:
    doc.save(path)
    doc.close()


def _invoice(path: Path) -> None:
    doc = _new_doc(2)
    page = doc[0]
    _write_page(
        page,
        "INVOICE",
        [
            "Invoice No: INV-912371",
            "Date: 2024-01-15",
            "Vendor: Acme Corp",
            "Total Amount Due: $4,250.00",
        ],
    )
    _draw_table(
        page,
        72,
        180,
        [
            ["Item", "Qty", "Price"],
            ["Professional services", "1", "4250.00"],
        ],
    )
    _write_page(doc[1], "Payment Terms", ["Please remit payment within 30 days."], y=72)
    _save(doc, path)


def _sec_10k(path: Path) -> None:
    doc = _new_doc(12)
    _write_page(
        doc[0],
        "Example Holdings Inc. Form 10-K",
        ["Fiscal Year: 2024", "Company Name: Example Holdings Inc."],
    )
    _write_page(doc[1], "Risk Factors", ["Risk factors include revenue concentration."])
    _write_page(doc[3], "Financial Statements", ["Total Revenue: 1000000"])
    _draw_table(
        doc[3],
        72,
        160,
        [["Fiscal Year", "Revenue", "Net Income"], ["2024", "1000000", "125000"]],
    )
    _write_page(doc[11], "Footer", ["Footer: Example Holdings 2024 annual report."])
    _save(doc, path)


def _bank_statement(path: Path) -> None:
    doc = _new_doc(3)
    _write_page(
        doc[0],
        "Bank Statement",
        ["Account Holder: Jordan Lee", "Account Last4: 4821", "Statement Period: 2024-02"],
    )
    _draw_table(
        doc[1],
        72,
        120,
        [
            ["Date", "Description", "Amount", "Balance"],
            ["2024-02-01", "Deposit", "1200.00", "5200.00"],
        ],
    )
    _write_page(doc[2], "Ending Balance", ["Ending Balance: 5200.00"])
    _save(doc, path)


def _scanned_contract(path: Path) -> None:
    doc = _new_doc(8)
    _write_page(
        doc[0],
        "Services Agreement",
        [
            "Effective Date: 2024-03-01",
            "Party A: Northwind LLC",
            "Party B: Contoso Ltd.",
            "Signature: __________________",
        ],
    )
    _write_page(doc[5], "Termination Clause", ["Either party may terminate with notice."])
    _save(doc, path)


def _academic_paper(path: Path) -> None:
    doc = _new_doc(10)
    _write_page(
        doc[0],
        "Efficient Document Understanding",
        ["A. Researcher", "Year: 2024", "Formula: E = mc^2"],
    )
    _write_page(doc[4], "Experimental Results", ["Accuracy is reported below."])
    _draw_table(doc[4], 72, 150, [["Model", "Accuracy"], ["Baseline", "0.81"]])
    _save(doc, path)


def _phone_photo(path: Path) -> None:
    doc = _new_doc(1)
    _write_page(
        doc[0],
        "Corner Market Receipt",
        ["Merchant: Corner Market", "Date: 2024-04-12", "Receipt Total: 38.42"],
    )
    _draw_table(doc[0], 72, 170, [["Description", "Total"], ["Receipt total", "38.42"]])
    _save(doc, path)


def _handwritten(path: Path) -> None:
    doc = _new_doc(2)
    _write_page(doc[0], "Meeting Notes", ["Author: Sam Rivera", "Date: 2024-05-03"])
    _write_page(doc[1], "Action Items", ["Follow up with design review."])
    _save(doc, path)


if __name__ == "__main__":
    main()
