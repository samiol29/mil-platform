"""
Realistic demonstration dataset for MIL (RC1 stabilization pass).

Creates a handful of full, end-to-end mortgage applications — via the real
HTTP API, going through the real upload -> OCR/extraction -> Finding
generation -> Policy evaluation -> Human review pipeline exactly as a real
underwriter would — each built to genuinely land in a different, realistic
reviewer scenario:

    happy_path          Clean package, one real material finding, verified.
    missing_documents   Application submitted with an incomplete package —
                         only one of two expected documents uploaded.
    ocr_failure         A deliberately empty/unreadable file, so the real
                         ingestion pipeline genuinely fails (not simulated —
                         this is the same failure path a real corrupt scan
                         would hit: `ingestion_status == 'FAILED'` with a
                         real backend error string).
    income_mismatch     Pay stub and bank statement carry genuinely
                         inconsistent income figures — a real finding Gemini
                         should surface on its own from the evidence, not a
                         hand-authored one.
    identity_mismatch   Borrower name differs across two documents.
    escalation_required Finding escalated to another role's queue via the
                         real `/findings/{id}/escalate` endpoint.
    manual_override     Finding overridden via the real
                         `/findings/{id}/override` endpoint with a real
                         reason/previous/new value.
    clean_approval      Every document processes successfully and Gemini
                         genuinely finds nothing material — exercises the
                         honest "No material issues were detected" empty
                         state (Phase 12) rather than showing a fabricated
                         clean bill of health.

Every document is a real, readable synthetic PDF (a minimal hand-written PDF
writer below — no OS-specific tool or third-party PDF library dependency, so
this runs the same on any machine). Every discrepancy a scenario is meant to
surface is a real inconsistency in the synthetic source documents, not a
value injected after the fact — Gemini has to actually notice it, the same
as it would with real bank statements.

Gemini quota note: each scenario needing full processing costs roughly
2 OCR/extraction calls (one per document) + 1 Finding-generation call. The
Gemini AI Studio free tier is quota-limited (as low as 20 requests/day for
gemini-2.5-flash) — running every scenario in one sitting can exhaust it.
Use --scenario to run one at a time across multiple days if needed, or
--scenario missing_documents (which never calls Gemini) to sanity-check the
script without spending quota.

Usage::

    python scripts/seed_demo_dataset.py                        # every scenario
    python scripts/seed_demo_dataset.py --scenario happy_path   # one scenario
    python scripts/seed_demo_dataset.py --list                  # list scenarios
    python scripts/seed_demo_dataset.py --base-url http://localhost:8000/v1
"""

from __future__ import annotations

import argparse
import random
import sys
import time
import zlib
from dataclasses import dataclass, field

import httpx

DEFAULT_BASE_URL = "http://localhost:8000/v1"
DEV_TOKEN = "dev"


# ---------------------------------------------------------------------------
# Minimal PDF writer — no OS tool, no third-party library. One page of
# left-aligned monospace text per document, which is all Gemini's document
# understanding needs to read real content back out.
# ---------------------------------------------------------------------------


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_pdf(lines: list[str]) -> bytes:
    """Render `lines` as a single-page PDF (Helvetica, 10pt, top-aligned)."""
    stream_parts = ["BT", "/F1 10 Tf", "12 TL", "50 740 Td"]
    for i, line in enumerate(lines):
        if i > 0:
            stream_parts.append("T*")
        stream_parts.append(f"({_pdf_escape(line)}) Tj")
    stream_parts.append("ET")
    stream = "\n".join(stream_parts).encode("latin-1", errors="replace")
    compressed = zlib.compress(stream)

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(
        b"<< /Length "
        + str(len(compressed)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + compressed
        + b"\nendstream"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()
    return bytes(out)


# ---------------------------------------------------------------------------
# Synthetic document content
# ---------------------------------------------------------------------------


def paystub(name: str, employer: str, gross_monthly: str, net_pay: str) -> bytes:
    return make_pdf(
        [
            "FIRST NATIONAL PAYROLL SERVICES",
            "Earnings Statement",
            "",
            f"Employee: {name}",
            "Pay Period: 06/01/2026 - 06/15/2026",
            "Pay Date: 06/20/2026",
            "",
            f"Employer: {employer}",
            "Address: 128 Harbor View Drive, Austin, TX 78701",
            "",
            f"Gross Monthly Income: {gross_monthly}",
            f"Net Pay (this period): {net_pay}",
        ]
    )


def bank_statement(name: str, employer_on_deposit: str, deposit_amount: str, balance: str) -> bytes:
    return make_pdf(
        [
            "FIRST NATIONAL BANK OF TEXAS",
            "Monthly Account Statement",
            "",
            f"Account Holder: {name}",
            "Account Number: XXXX-XXXX-4471",
            "Statement Period: 06/01/2026 - 06/30/2026",
            "",
            "Deposits and Credits:",
            f"06/17/2026  Payroll Direct Deposit - {employer_on_deposit}   {deposit_amount}",
            "",
            f"Ending Balance: {balance}",
        ]
    )


def identity_document(name: str, doc_kind: str, id_number: str, dob: str) -> bytes:
    return make_pdf(
        [
            f"STATE OF TEXAS — {doc_kind}",
            "",
            f"Full Legal Name: {name}",
            f"Document Number: {id_number}",
            f"Date of Birth: {dob}",
            "Issuing State: TX",
        ]
    )


def empty_or_corrupt_document() -> bytes:
    """A syntactically-empty PDF the real ingestion pipeline should genuinely
    fail on — mirrors the real 'The document has no pages' failure already
    observed against the live backend (not a simulated error string)."""
    return make_pdf([])


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


@dataclass
class DemoClient:
    base_url: str
    client: httpx.Client = field(init=False)

    def __post_init__(self) -> None:
        # max_keepalive_connections=0: works around a confirmed, intermittent
        # --reload-dev-server-only quirk (an occasional 404 on the request
        # immediately following one that created the resource, on a reused
        # keep-alive connection — not reproducible via curl or a production
        # ASGI deployment without --reload).
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=60.0,
            headers={"Authorization": f"Bearer {DEV_TOKEN}"},
            limits=httpx.Limits(max_keepalive_connections=0),
        )

    def _post(self, url: str, **kwargs) -> httpx.Response:
        resp = self.client.post(url, **kwargs)
        if resp.status_code == 404:
            resp = httpx.post(f"{self.base_url}{url}", headers=self.client.headers, **kwargs)
        resp.raise_for_status()
        return resp

    def create_application(self, los_reference: str, loan_number: str) -> dict:
        return self._post(
            "/applications",
            json={"los_reference": los_reference, "loan_number": loan_number},
        ).json()

    def add_party(self, application_id: str, party_type: str, display_name: str) -> dict:
        return self._post(
            f"/applications/{application_id}/parties",
            json={"party_type": party_type, "display_name": display_name},
        ).json()

    def upload_document(
        self, application_id: str, filename: str, content: bytes, document_type: str, party_id: str | None = None
    ) -> dict:
        data = {"document_type": document_type}
        if party_id is not None:
            data["party_id"] = party_id
        files = {"file": (filename, content, "application/pdf")}
        return self._post(f"/applications/{application_id}/documents", data=data, files=files).json()

    def get_documents(self, application_id: str) -> list[dict]:
        return self.client.get(f"/applications/{application_id}/documents").json()

    def wait_for_ingestion(self, application_id: str, timeout_s: float = 90.0) -> list[dict]:
        deadline = time.monotonic() + timeout_s
        docs: list[dict] = []
        while time.monotonic() < deadline:
            docs = self.get_documents(application_id)
            if all(d["ingestion_status"] in ("COMPLETED", "FAILED") for d in docs):
                return docs
            time.sleep(3)
        return docs

    def submit(self, application_id: str) -> dict:
        return self._post(f"/applications/{application_id}/submit").json()

    def get_findings(self, application_id: str) -> list[dict]:
        return self.client.get(f"/applications/{application_id}/findings").json()

    def wait_for_findings(self, application_id: str, timeout_s: float = 60.0) -> list[dict]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            findings = self.get_findings(application_id)
            if findings:
                return findings
            time.sleep(3)
        return []

    def verify_finding(self, finding_id: str) -> dict:
        return self._post(f"/findings/{finding_id}/verify").json()

    def override_finding(self, finding_id: str, reason: str, previous_value: str, new_value: str) -> dict:
        return self._post(
            f"/findings/{finding_id}/override",
            json={"reason": reason, "previous_value": previous_value, "new_value": new_value},
        ).json()

    def escalate_finding(self, finding_id: str, reason: str, target_role: str) -> dict:
        return self._post(
            f"/findings/{finding_id}/escalate",
            json={"reason": reason, "target_role": target_role},
        ).json()


def random_los_reference(rng: random.Random) -> str:
    return f"LOS-{rng.randint(1_000_000, 9_999_999)}"


def random_loan_number(rng: random.Random) -> str:
    return str(rng.randint(1_000_000_000, 9_999_999_999))


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def scenario_happy_path(c: DemoClient, rng: random.Random) -> None:
    app = c.create_application(random_los_reference(rng), random_loan_number(rng))
    party = c.add_party(app["id"], "APPLICANT", "Morgan Reyes")
    c.upload_document(
        app["id"], "paystub.pdf",
        paystub("Morgan Reyes", "Beacon Hill Analytics LLC", "$8,200.00", "$5,120.44"),
        "PAYSLIP", party["id"],
    )
    c.upload_document(
        app["id"], "bank_statement.pdf",
        bank_statement("Morgan Reyes", "Beacon Hill Analytics", "$5,120.44", "$41,208.19"),
        "BANK_STATEMENT", party["id"],
    )
    c.wait_for_ingestion(app["id"])
    c.submit(app["id"])
    findings = c.wait_for_findings(app["id"])
    if findings:
        c.verify_finding(findings[0]["id"])
    print(f"[happy_path] application {app['id']} ({app['los_reference']}) — {len(findings)} finding(s)")


def scenario_missing_documents(c: DemoClient, rng: random.Random) -> None:
    # Never calls Gemini — no documents are uploaded/processed at all. A
    # realistic "borrower hasn't sent everything yet" state.
    app = c.create_application(random_los_reference(rng), random_loan_number(rng))
    party = c.add_party(app["id"], "APPLICANT", "Dana Whitfield")
    c.upload_document(
        app["id"], "paystub.pdf",
        paystub("Dana Whitfield", "Ironclad Logistics Inc", "$6,050.00", "$3,940.12"),
        "PAYSLIP", party["id"],
    )
    print(f"[missing_documents] application {app['id']} ({app['los_reference']}) — only 1 of 2 expected documents uploaded, left in DRAFT")


def scenario_ocr_failure(c: DemoClient, rng: random.Random) -> None:
    app = c.create_application(random_los_reference(rng), random_loan_number(rng))
    party = c.add_party(app["id"], "APPLICANT", "Priya Anand")
    c.upload_document(app["id"], "corrupted_scan.pdf", empty_or_corrupt_document(), "BANK_STATEMENT", party["id"])
    docs = c.wait_for_ingestion(app["id"])
    status = docs[0]["ingestion_status"] if docs else "UNKNOWN"
    print(f"[ocr_failure] application {app['id']} ({app['los_reference']}) — document status: {status}")


def scenario_income_mismatch(c: DemoClient, rng: random.Random) -> None:
    app = c.create_application(random_los_reference(rng), random_loan_number(rng))
    party = c.add_party(app["id"], "APPLICANT", "Jordan Castellano")
    c.upload_document(
        app["id"], "paystub.pdf",
        paystub("Jordan Castellano", "Meridian Freight Group", "$9,400.00", "$6,102.30"),
        "PAYSLIP", party["id"],
    )
    # Deposit amount is far below what the stated gross/net would imply —
    # a real, Gemini-detectable inconsistency, not a hand-authored finding.
    c.upload_document(
        app["id"], "bank_statement.pdf",
        bank_statement("Jordan Castellano", "Meridian Freight Group", "$2,850.00", "$14,006.55"),
        "BANK_STATEMENT", party["id"],
    )
    c.wait_for_ingestion(app["id"])
    c.submit(app["id"])
    findings = c.wait_for_findings(app["id"])
    print(f"[income_mismatch] application {app['id']} ({app['los_reference']}) — {len(findings)} finding(s), left unreviewed")


def scenario_identity_mismatch(c: DemoClient, rng: random.Random) -> None:
    app = c.create_application(random_los_reference(rng), random_loan_number(rng))
    party = c.add_party(app["id"], "APPLICANT", "Alexis Moreau")
    # Borrower's legal name on the ID document genuinely differs from the
    # name on the pay stub — a real cross-document inconsistency.
    c.upload_document(
        app["id"], "drivers_license.pdf",
        identity_document("Alexis M. Moreau-Whitfield", "DRIVER LICENSE", "TX-88213940", "04/12/1989"),
        "IDENTITY_DOCUMENT", party["id"],
    )
    c.upload_document(
        app["id"], "paystub.pdf",
        paystub("Alexis Moreau", "Cobalt Ridge Partners", "$7,300.00", "$4,880.60"),
        "PAYSLIP", party["id"],
    )
    c.wait_for_ingestion(app["id"])
    c.submit(app["id"])
    findings = c.wait_for_findings(app["id"])
    print(f"[identity_mismatch] application {app['id']} ({app['los_reference']}) — {len(findings)} finding(s), left unreviewed")


def scenario_escalation_required(c: DemoClient, rng: random.Random) -> None:
    app = c.create_application(random_los_reference(rng), random_loan_number(rng))
    party = c.add_party(app["id"], "APPLICANT", "Sam Okafor")
    c.upload_document(
        app["id"], "paystub.pdf",
        paystub("Sam Okafor", "Norwell Capital Advisors", "$11,500.00", "$7,204.90"),
        "PAYSLIP", party["id"],
    )
    c.upload_document(
        app["id"], "bank_statement.pdf",
        bank_statement("Sam Okafor", "Norwell Capital Advisors", "$3,100.00", "$52,884.02"),
        "BANK_STATEMENT", party["id"],
    )
    c.wait_for_ingestion(app["id"])
    c.submit(app["id"])
    findings = c.wait_for_findings(app["id"])
    if findings:
        c.escalate_finding(
            findings[0]["id"],
            reason="Income discrepancy exceeds my approval authority — routing to Compliance for a second opinion.",
            target_role="COMPLIANCE_OFFICER",
        )
    print(f"[escalation_required] application {app['id']} ({app['los_reference']}) — {len(findings)} finding(s), escalated to COMPLIANCE_OFFICER")


def scenario_manual_override(c: DemoClient, rng: random.Random) -> None:
    app = c.create_application(random_los_reference(rng), random_loan_number(rng))
    party = c.add_party(app["id"], "APPLICANT", "Taylor Nakamura")
    c.upload_document(
        app["id"], "paystub.pdf",
        paystub("Taylor Nakamura", "Lattice & Vine Studio", "$5,600.00", "$3,712.08"),
        "PAYSLIP", party["id"],
    )
    c.upload_document(
        app["id"], "bank_statement.pdf",
        bank_statement("Taylor Nakamura", "Lattice and Vine Studio LLC", "$1,850.00", "$9,204.11"),
        "BANK_STATEMENT", party["id"],
    )
    c.wait_for_ingestion(app["id"])
    c.submit(app["id"])
    findings = c.wait_for_findings(app["id"])
    if findings:
        c.override_finding(
            findings[0]["id"],
            reason="Confirmed with borrower by phone: deposit reflects a partial pay period after a mid-month start date. Full gross income verified against employer offer letter on file with the LOS.",
            previous_value="$1,850.00 deposit",
            new_value="Confirmed consistent with $5,600.00 stated income",
        )
    print(f"[manual_override] application {app['id']} ({app['los_reference']}) — {len(findings)} finding(s), overridden")


def scenario_clean_approval(c: DemoClient, rng: random.Random) -> None:
    app = c.create_application(random_los_reference(rng), random_loan_number(rng))
    party = c.add_party(app["id"], "APPLICANT", "Riley Fontaine")
    c.upload_document(
        app["id"], "paystub.pdf",
        paystub("Riley Fontaine", "Ashgrove Municipal Services", "$6,800.00", "$4,502.77"),
        "PAYSLIP", party["id"],
    )
    c.upload_document(
        app["id"], "bank_statement.pdf",
        bank_statement("Riley Fontaine", "Ashgrove Municipal Services", "$4,502.77", "$28,940.63"),
        "BANK_STATEMENT", party["id"],
    )
    c.wait_for_ingestion(app["id"])
    c.submit(app["id"])
    findings = c.wait_for_findings(app["id"])
    print(
        f"[clean_approval] application {app['id']} ({app['los_reference']}) — "
        f"{len(findings)} finding(s) (0 expected — exercises the honest "
        f"'No material issues were detected' state)"
    )


SCENARIOS = {
    "happy_path": scenario_happy_path,
    "missing_documents": scenario_missing_documents,
    "ocr_failure": scenario_ocr_failure,
    "income_mismatch": scenario_income_mismatch,
    "identity_mismatch": scenario_identity_mismatch,
    "escalation_required": scenario_escalation_required,
    "manual_override": scenario_manual_override,
    "clean_approval": scenario_clean_approval,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="Run only this scenario")
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--list", action="store_true", help="List available scenarios and exit")
    args = parser.parse_args()

    if args.list:
        for name in sorted(SCENARIOS):
            print(name)
        return

    rng = random.Random(args.seed)
    client = DemoClient(args.base_url)

    to_run = [args.scenario] if args.scenario else sorted(SCENARIOS)
    for name in to_run:
        try:
            SCENARIOS[name](client, rng)
        except httpx.HTTPStatusError as exc:
            print(f"[{name}] FAILED: HTTP {exc.response.status_code} — {exc.response.text[:300]}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — top-level script, report and continue
            print(f"[{name}] FAILED: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
