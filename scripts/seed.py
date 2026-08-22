import asyncio
import random
import argparse
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faker import Faker

from db.session import AsyncSessionLocal
from db.models import Official, LetterType

fake = Faker("en_IN")

ROLES = [
    "Faculty Coordinator",
    "HOD - Computer Science",
    "Principal",
    "Director",
    "Club Coordinator",
    "Assistant Director",
    "Warden - Hostel",
    "Head of Strategy and Planning",
]

ROLE_ORGANIZATION = {
    "Faculty Coordinator": "Department of Computer Science",
    "HOD - Computer Science": "Department of Computer Science",
    "Principal": "Office of the Principal",
    "Director": "Office of the Director",
    "Club Coordinator": "Department of Student Affairs",
    "Assistant Director": "Office of the Assistant Director",
    "Warden - Hostel": "Hostel Office",
    "Head of Strategy and Planning": "Office of Strategy and Planning",
}


def generate_official(role: str | None = None) -> dict:
    return {
        "id": str(uuid4()),
        "name": fake.name(),
        "address": fake.address().replace("\n", ", "),
        "role": role if role else random.choice(ROLES),
        "organization": ROLE_ORGANIZATION.get(
            role, random.choice(list(ROLE_ORGANIZATION.values()))
        ),
        "signature": f"https://drive.google.com/signatures/{uuid4()}",
    }


LETTER_TYPES = [
    {
        "id": "fund_release_request",
        "name": "Fund Release Request",
        "description": "Requests release of funds BEFORE spending, for procurement (hardware, software/subscriptions) or event/participation budgets. Includes justification paragraph and itemized budget table with a Total row. Closes with a formal authorization request line.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 3, "role": "Principal", "action": "Review & Forward"},
            {"step": 4, "role": "Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "fund_advance_request",
        "name": "Advance Fund Request",
        "description": "Requests a partial advance ahead of an event, explicitly citing a prior reference letter/budget. Shorter than a standard fund release letter; assumes prior context is known to the approver.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 3, "role": "Principal", "action": "Review & Forward"},
            {"step": 4, "role": "Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "reimbursement_request",
        "name": "Reimbursement Request",
        "description": "Requests reimbursement for money already spent against a previously approved budget. Always includes a vendor / date-of-billing / bill-number / purpose / amount table with a TOTAL EXPENSES row, and a line noting bills will be submitted for verification.",
        "approval_chain": [
            {"step": 1, "role": "Club Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 3, "role": "Principal", "action": "Review & Forward"},
            {"step": 4, "role": "Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "fund_transfer_request",
        "name": "Fund Transfer / Reallocation Request",
        "description": "Requests moving previously sanctioned funds from one approved purpose/event to a new one, sometimes with an additional top-up amount requested.",
        "approval_chain": [
            {"step": 1, "role": "Club Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 3, "role": "Principal", "action": "Review & Forward"},
            {"step": 4, "role": "Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "prize_disbursement_request",
        "name": "Prize/Winner Disbursement Request",
        "description": "Requests transfer of an already-approved prize amount to a specific winner. Includes winner name, bank account number, and IFSC code, referencing the original fund-approval letter.",
        "approval_chain": [
            {"step": 1, "role": "Club Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 3, "role": "Principal", "action": "Review & Forward"},
            {"step": 4, "role": "Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "event_permission_request",
        "name": "Event/Session Permission Request",
        "description": "Requests permission to conduct a workshop, session, or competition for students. States date/time, objective, and an assurance that regular academic activities won't be disrupted.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 3, "role": "Principal", "action": "Review & Forward"},
            {"step": 4, "role": "Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "venue_booking_request",
        "name": "Venue/Hall Booking Request",
        "description": "Short, separate letter requesting a specific hall/venue for an already-permitted event. Cross-references the related event permission letter's reference number.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 3, "role": "Assistant Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "materials_request",
        "name": "Materials/Items Request",
        "description": "Requests physical items or stationery (not funds) needed for an event, given as a simple bullet list rather than a budget table.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "Assistant Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "hostel_late_stay_permission",
        "name": "Hostel Late-Stay & Vehicle Permission",
        "description": "Requests permission for hostel students to stay past curfew for club work, plus vehicle entry/exit clearance. Addressed to the Warden rather than the Director/Principal chain; includes a student details table.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "Warden - Hostel", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "infrastructure_request",
        "name": "Infrastructure/Renovation Request",
        "description": "Requests renovation or repair of club facilities. Includes a numbered list of current issues/safety concerns and a separate bullet list of facility requirements.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "Head of Strategy and Planning", "action": "Review"},
            {"step": 3, "role": "Assistant Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "status_followup_request",
        "name": "Follow-up / Escalation Request",
        "description": "Follows up on a previously approved but delayed request, citing the original reference number and elapsed time. Tone is more urgent/grievance-style than a fresh request, and typically re-lists the still-pending items.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "Head of Strategy and Planning", "action": "Review"},
            {"step": 3, "role": "Assistant Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
    {
        "id": "payment_logistics_request",
        "name": "Payment Process Request",
        "description": "Narrow procedural letter about how an already-approved payment will be executed operationally (e.g. arranging for an accountant to process an online payment). References the original fund-release letter.",
        "approval_chain": [
            {"step": 1, "role": "Faculty Coordinator", "action": "Endorsement"},
            {"step": 2, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 3, "role": "Principal", "action": "Review & Forward"},
            {"step": 4, "role": "Director", "action": "Final Approval"},
        ],
        "template": "[SAMPLE_LINK]",
    },
]


async def seed(count: int = 0):
    async with AsyncSessionLocal() as session:
        await session.execute(Official.__table__.delete())
        print("Cleared existing officials")

        roles = set()
        for lt in LETTER_TYPES:
            for step in lt["approval_chain"]:
                roles.add(step["role"])

        for role in sorted(roles):
            session.add(Official(**generate_official(role=role)))
        print(f"Seeded {len(roles)} officials by role")

        if count > 0:
            extra = [generate_official() for _ in range(count)]
            session.add_all(Official(**o) for o in extra)
            await session.commit()
            print(f"Seeded {count} additional random officials")
        else:
            await session.commit()

        await session.execute(LetterType.__table__.delete())
        print("Cleared existing letter types")

        for lt in LETTER_TYPES:
            session.add(LetterType(**lt))
        await session.commit()
        print(f"Seeded {len(LETTER_TYPES)} letter types")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of extra random officials to seed (beyond role-mapped ones)",
    )
    args = parser.parse_args()

    asyncio.run(seed(args.count))
