#!/usr/bin/env python3
"""
ARIA Integration Smoke Test

Run:
  python test_aria_integration.py --base-url http://localhost:10000 --username admin --password YOUR_PASSWORD

Optional:
  python test_aria_integration.py --base-url http://localhost:10000 --username admin --password YOUR_PASSWORD --include-send-email
  python test_aria_integration.py --base-url http://localhost:10000 --username admin --password YOUR_PASSWORD --include-permanent-delete
"""

import argparse
import base64
import csv
import io
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests


class AriaTester:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        include_send_email: bool = False,
        include_permanent_delete: bool = False,
        timeout: int = 90,
        delay: float = 1.5,
        max_retries: int = 6,
        sheets_quota_sleep: int = 70,
        app_rate_limit_sleep: int = 35,
    ):
        self.base_url = base_url.rstrip("/")
        self.include_send_email = include_send_email
        self.include_permanent_delete = include_permanent_delete
        self.timeout = timeout
        self.delay = delay
        self.max_retries = max_retries
        self.sheets_quota_sleep = sheets_quota_sleep
        self.app_rate_limit_sleep = app_rate_limit_sleep

        auth_raw = f"{username}:{password}".encode("utf-8")
        auth_b64 = base64.b64encode(auth_raw).decode("utf-8")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Basic {auth_b64}",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

        self.results = []
        self.client_id = None
        self.event_id = None
        self.draft_id = None

        self.test_suffix = uuid.uuid4().hex[:8]
        self.test_email = f"aria.test.{self.test_suffix}@example.com"

    def log(self, name: str, ok: bool, status: Optional[int] = None, detail: str = ""):
        icon = "PASS" if ok else "FAIL"
        status_text = f" [{status}]" if status else ""
        print(f"{icon}: {name}{status_text} {detail}")
        self.results.append(
            {
                "name": name,
                "ok": ok,
                "status": status,
                "detail": detail,
            }
        )

    def request(
        self,
        method: str,
        path: str,
        name: Optional[str] = None,
        expected=(200, 201, 202, 204),
        **kwargs,
    ):
        url = f"{self.base_url}{path}"
        label = name or f"{method.upper()} {path}"

        last_response = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    timeout=self.timeout,
                    **kwargs,
                )
                last_response = response

                body_text = response.text or ""
                is_sheets_quota = (
                    response.status_code == 429
                    or "Quota exceeded" in body_text
                    or "sheets.googleapis.com" in body_text
                )
                is_app_rate_limit = (
                    response.status_code == 429
                    and "Rate limit reached" in body_text
                )

                if is_sheets_quota and response.status_code not in expected and attempt < self.max_retries:
                    if is_app_rate_limit:
                        wait_seconds = self.app_rate_limit_sleep
                    elif "sheets.googleapis.com" in body_text or "Quota exceeded" in body_text:
                        wait_seconds = self.sheets_quota_sleep
                    else:
                        wait_seconds = int(response.headers.get("Retry-After", "10"))

                    print(
                        f"WAIT: {label} hit rate/quota limit. "
                        f"Sleeping {wait_seconds}s before retry {attempt + 1}/{self.max_retries}..."
                    )
                    time.sleep(wait_seconds)
                    continue

                ok = response.status_code in expected
                detail = ""

                if not ok:
                    detail = body_text[:800].replace("\n", " ")

                self.log(label, ok, response.status_code, detail)

                if self.delay > 0:
                    time.sleep(self.delay)

                if body_text:
                    try:
                        return response.json()
                    except Exception:
                        return body_text

                return None

            except Exception as exc:
                if attempt < self.max_retries:
                    wait_seconds = min(5 * (attempt + 1), 30)
                    print(
                        f"WAIT: {label} request error: {exc}. "
                        f"Sleeping {wait_seconds}s before retry {attempt + 1}/{self.max_retries}..."
                    )
                    time.sleep(wait_seconds)
                    continue

                self.log(label, False, None, str(exc))
                return None

        if last_response is not None:
            detail = (last_response.text or "")[:800].replace("\n", " ")
            self.log(label, False, last_response.status_code, detail)
            return None

        self.log(label, False, None, "Unknown request failure")
        return None

    def find_id(self, payload: Any, keys=("client_id", "id", "event_id", "draft_id")):
        if isinstance(payload, dict):
            for key in keys:
                if key in payload and payload[key]:
                    return payload[key]

            for value in payload.values():
                found = self.find_id(value, keys)
                if found:
                    return found

        if isinstance(payload, list):
            for item in payload:
                found = self.find_id(item, keys)
                if found:
                    return found

        return None

    def health_and_pages(self):
        self.request("GET", "/health", "Health check")

        pages = [
            "/aria",
            "/aria/",
            "/aria/dashboard",
            "/aria/clients",
            "/aria/chat",
            "/aria/calendar",
            "/aria/email",
            "/aria/reports",
            "/aria/intel",
            "/aria/search",
            "/aria/import",
        ]

        for page in pages:
            self.request("GET", page, f"Page {page}")

    def cache(self):
        self.request("POST", "/cache/clear", "Clear cache")

    def clients(self):
        payload = {
            "name": f"ARIA Test Client {self.test_suffix}",
            "company": "ARIA Test Company",
            "email": self.test_email,
            "phone": "555-0100",
            "service": "AI workflow automation",
            "priority": "High",
            "stage": "New",
            "notes": "Automated integration test client. Safe to delete.",
        }

        created = self.request("POST", "/clients", "Create client", json=payload)
        self.client_id = self.find_id(created, keys=("client_id", "id"))

        if not self.client_id:
            self.log("Extract client_id", False, None, "Could not find client_id in create response")
            return

        self.log("Extract client_id", True, None, self.client_id)

        self.request("GET", "/clients", "List clients")
        self.request("GET", f"/clients/{self.client_id}", "Get client")

        self.request(
            "PUT",
            f"/clients/{self.client_id}",
            "Update client",
            json={
                "phone": "555-0199",
                "notes": "Updated by integration test.",
                "priority": "Medium",
            },
        )

        self.request(
            "PUT",
            f"/clients/{self.client_id}/stage",
            "Update client stage",
            json={"stage": "Contacted"},
        )

        followup_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

        self.request(
            "PUT",
            f"/clients/{self.client_id}/followup",
            "Update follow-up",
            json={"follow_up_date": followup_date},
        )

        self.request("GET", f"/clients/{self.client_id}/audit", "Get audit history")
        self.request("GET", f"/clients/{self.client_id}/activity", "Get client activity")
        self.request("GET", "/activities", "Search activities")

        self.request(
            "POST",
            f"/clients/{self.client_id}/rollback/stage",
            "Rollback stage field",
            expected=(200, 201, 202, 204, 400, 404),
        )

        self.request(
            "POST",
            f"/clients/{self.client_id}/rollback",
            "Rollback last change",
            expected=(200, 201, 202, 204, 400, 404),
        )

    def bulk(self):
        if not self.client_id:
            return

        self.request(
            "POST",
            "/clients/bulk/stage",
            "Bulk update stage",
            json={"client_ids": [self.client_id], "stage": "Proposal Sent"},
        )

        self.request(
            "POST",
            "/clients/bulk/archive",
            "Bulk archive",
            json={"client_ids": [self.client_id]},
        )

        self.request("GET", "/clients/archived", "Get archived clients")
        self.request("POST", f"/clients/{self.client_id}/restore", "Restore archived client")

    def import_preview(self):
        csv_text = io.StringIO()
        writer = csv.DictWriter(
            csv_text,
            fieldnames=[
                "name",
                "company",
                "email",
                "phone",
                "service",
                "priority",
                "stage",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "name": f"ARIA CSV Test {self.test_suffix}",
                "company": "CSV Test Co",
                "email": f"csv.{self.test_suffix}@example.com",
                "phone": "555-0200",
                "service": "Document automation",
                "priority": "Medium",
                "stage": "New",
                "notes": "CSV preview/import test",
            }
        )

        files = {
            "file": (
                "aria_test_import.csv",
                csv_text.getvalue().encode("utf-8"),
                "text/csv",
            )
        }

        self.request(
            "POST",
            "/clients/import/preview",
            "Import preview CSV",
            files=files,
            expected=(200, 201, 202, 400, 422),
        )

    def pipeline(self):
        endpoints = [
            ("/pipeline", "Get pipeline"),
            ("/pipeline/report", "Pipeline report"),
            ("/followups/due", "Followups due"),
        ]

        for path, name in endpoints:
            self.request("GET", path, name)

    def documents(self):
        if not self.client_id:
            return

        self.request("POST", f"/clients/{self.client_id}/report", "Generate client report")

        self.request(
            "POST",
            f"/clients/{self.client_id}/contract",
            "Create contract",
            json={
                "service_description": "AI workflow automation implementation",
                "start_date": datetime.now().strftime("%Y-%m-%d"),
                "end_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                "total_amount": 1000,
                "payment_terms": "Due on receipt",
            },
            expected=(200, 201, 202, 400, 422),
        )

        self.request(
            "POST",
            f"/clients/{self.client_id}/invoice",
            "Create invoice",
            json={
                "invoice_number": f"INV-{self.test_suffix}",
                "due_date": (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d"),
                "line_items": [
                    {
                        "description": "AI workflow automation consultation",
                        "quantity": 1,
                        "unit_price": 1000,
                    }
                ],
                "notes": "Integration test invoice",
            },
            expected=(200, 201, 202, 400, 422),
        )

        self.request(
            "POST",
            f"/clients/{self.client_id}/proposal",
            "Create proposal",
            json={
                "project_title": "AI CRM Automation Proposal",
                "problem_statement": "Client needs workflow automation.",
                "proposed_solution": "Implement AI CRM workflow automation.",
                "timeline": "2 weeks",
                "pricing_tier": "Standard",
                "total_amount": 1000,
            },
            expected=(200, 201, 202, 400, 422),
        )

        self.request(
            "POST",
            f"/clients/{self.client_id}/ai-proposal",
            "AI proposal",
            expected=(200, 201, 202, 400, 422),
        )

    def email(self):
        if not self.client_id:
            return

        self.request(
            "POST",
            "/agent/draft-email",
            "Agent draft email",
            json={
                "client_id": self.client_id,
                "instruction": "Draft a short follow-up email. Sender name is Aria.",
            },
            expected=(200, 201, 202, 400, 422),
        )

        email_payload = {
            "client_id": self.client_id,
            "to": self.test_email,
            "subject": f"ARIA Test Draft {self.test_suffix}",
            "body": (
                "Hi,\n\n"
                "This is an automated ARIA Gmail draft integration test.\n\n"
                "Best regards,\n"
                "Aria"
            ),
        }

        draft = self.request(
            "POST",
            "/email/draft",
            "Create Gmail draft",
            json=email_payload,
            expected=(200, 201, 202, 400, 422),
        )

        self.draft_id = self.find_id(draft, keys=("draft_id", "id"))
        if self.draft_id:
            self.log("Extract draft_id", True, None, self.draft_id)

        self.request("GET", "/email/drafts", "Get Gmail drafts", expected=(200, 201, 202, 400))

        if self.include_send_email:
            self.request(
                "POST",
                "/email/send",
                "Send real email",
                json=email_payload,
                expected=(200, 201, 202, 400, 422),
            )
        else:
            self.log("Send real email", True, None, "Skipped by default")

        if self.draft_id:
            self.request(
                "DELETE",
                f"/email/draft/{self.draft_id}",
                "Delete Gmail draft",
                expected=(200, 201, 202, 204, 400, 404),
            )

    def calendar(self):
        if not self.client_id:
            return

        start = datetime.now(timezone.utc) + timedelta(days=2)
        end = start + timedelta(minutes=30)

        payload = {
            "client_id": self.client_id,
            "title": f"ARIA Test Meeting {self.test_suffix}",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "description": "Automated ARIA calendar integration test.",
            "location": "Google Meet",
            "invite_client": False,
            "meeting_notes": "Created by integration test. Should be cancelled automatically.",
        }

        created = self.request(
            "POST",
            "/meetings",
            "Create meeting",
            json=payload,
            expected=(200, 201, 202, 400, 422),
        )

        self.event_id = self.find_id(created, keys=("event_id", "id"))

        if self.event_id:
            self.log("Extract event_id", True, None, self.event_id)

            self.request("GET", "/meetings", "Upcoming meetings")
            self.request("GET", f"/meetings/{self.event_id}", "Get meeting details")

            self.request(
                "POST",
                f"/meetings/{self.event_id}/notes",
                "Add meeting notes",
                json={"notes": "Integration test note."},
                expected=(200, 201, 202, 400, 422),
            )

            self.request(
                "PUT",
                f"/meetings/{self.event_id}",
                "Update meeting",
                json={
                    "title": f"ARIA Updated Test Meeting {self.test_suffix}",
                    "location": "Updated test location",
                },
                expected=(200, 201, 202, 400, 422),
            )

            self.request(
                "GET",
                f"/clients/{self.client_id}/meetings",
                "Get client meetings",
                expected=(200, 201, 202, 400, 404),
            )

            self.request(
                "DELETE",
                f"/meetings/{self.event_id}",
                "Cancel meeting",
                expected=(200, 201, 202, 204, 400, 404),
            )
        else:
            self.log("Extract event_id", False, None, "Meeting creation did not return event_id")

    def ai_and_chat(self):
        if not self.client_id:
            return

        self.request(
            "POST",
            "/agent/chat",
            "Agent chat",
            json={
                "message": "Summarize the current CRM pipeline in one sentence.",
                "client_id": self.client_id,
            },
            expected=(200, 201, 202, 400, 422),
        )

        self.request(
            "POST",
            f"/agent/analyze/{self.client_id}",
            "Agent analyze client",
            expected=(200, 201, 202, 400, 404),
        )

        self.request(
            "POST",
            "/aria/chat",
            "ARIA chat",
            json={
                "message": "What should I do next for this client?",
                "history": [],
            },
            expected=(200, 201, 202, 400, 422),
        )

    def intelligence(self):
        if not self.client_id:
            return

        endpoints = [
            (f"/clients/{self.client_id}/score", "Score client"),
            ("/pipeline/score", "Score pipeline"),
            (f"/clients/{self.client_id}/similar", "Find similar clients"),
            ("/recommendations/daily", "Daily recommendations"),
            ("/recommendations/stale", "Stale clients"),
            ("/insights/patterns", "Pipeline patterns"),
            ("/insights/revenue-forecast", "Revenue forecast"),
            ("/insights/win-loss", "Win/loss analysis"),
        ]

        for path, name in endpoints:
            self.request("GET", path, name, expected=(200, 201, 202, 400, 404))

    def search(self):
        self.request(
            "POST",
            "/search",
            "Natural language search",
            json={"query": "high priority AI automation clients"},
            expected=(200, 201, 202, 400, 422),
        )

        self.request(
            "POST",
            "/search/filter",
            "Smart filter",
            json={"criteria": "clients in proposal stage"},
            expected=(200, 201, 202, 400, 422),
        )

    def reports(self):
        endpoints = [
            ("/reports/weekly", "Weekly report"),
            ("/reports/monthly", "Monthly report"),
            ("/reports/acquisition", "Acquisition report"),
            ("/reports/agent-activity", "Agent activity report"),
        ]

        for path, name in endpoints:
            self.request("GET", path, name, expected=(200, 201, 202, 400))

    def cleanup(self):
        if not self.client_id:
            return

        if self.include_permanent_delete:
            self.request(
                "DELETE",
                f"/clients/{self.client_id}/permanent",
                "Permanent delete test client",
                expected=(200, 201, 202, 204, 400, 404),
            )
        else:
            self.request(
                "DELETE",
                f"/clients/{self.client_id}",
                "Archive test client cleanup",
                expected=(200, 201, 202, 204, 400, 404),
            )

    def run_all(self):
        print("\n=== ARIA Integration Test Start ===\n")

        self.health_and_pages()
        self.cache()
        self.clients()
        self.bulk()
        self.import_preview()
        self.pipeline()
        self.documents()
        self.email()
        self.calendar()
        self.ai_and_chat()
        self.intelligence()
        self.search()
        self.reports()
        self.cleanup()

        print("\n=== Summary ===\n")

        passed = sum(1 for result in self.results if result["ok"])
        failed = sum(1 for result in self.results if not result["ok"])

        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if failed:
            print("\nFailed tests:")
            for result in self.results:
                if not result["ok"]:
                    print(f"- {result['name']} [{result['status']}]: {result['detail']}")
            sys.exit(1)

        print("\nAll tests passed.")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:10000")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--include-send-email", action="store_true")
    parser.add_argument("--include-permanent-delete", action="store_true")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds to wait after each request. Increase to reduce Google Sheets 429s.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=6,
        help="Retries for 429/quota responses.",
    )
    parser.add_argument(
        "--sheets-quota-sleep",
        type=int,
        default=70,
        help="Seconds to wait when Google Sheets per-minute quota is hit.",
    )
    parser.add_argument(
        "--app-rate-limit-sleep",
        type=int,
        default=35,
        help="Seconds to wait when ARIA chat rate limit is hit.",
    )

    args = parser.parse_args()

    tester = AriaTester(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        include_send_email=args.include_send_email,
        include_permanent_delete=args.include_permanent_delete,
        timeout=args.timeout,
        delay=args.delay,
        max_retries=args.max_retries,
        sheets_quota_sleep=args.sheets_quota_sleep,
        app_rate_limit_sleep=args.app_rate_limit_sleep,
    )

    tester.run_all()


if __name__ == "__main__":
    main()
