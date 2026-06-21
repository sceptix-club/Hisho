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
    "Principal",
    "Vice Principal",
    "Dean of Academics",
    "Dean of Students",
    "Registrar",
    "Finance Officer",
    "HOD - Computer Science",
    "HOD - Electronics",
    "HOD - Mechanical",
    "HOD - Civil",
    "HOD - Business Administration",
    "HOD - Mathematics",
    "HOD - Physics",
    "HOD - Chemistry",
    "HOD - English",
]

ORGANIZATIONS = [
    "Department of Computer Science",
    "Department of Electronics",
    "Department of Mechanical Engineering",
    "Department of Civil Engineering",
    "Department of Business Administration",
    "Department of Mathematics",
    "Department of Physics",
    "Department of Chemistry",
    "Department of English",
    "Office of the Principal",
    "Office of the Registrar",
    "Office of the Finance Officer",
]


def generate_official() -> dict:
    return {
        "id": str(uuid4()),
        "name": fake.name(),
        "address": fake.address().replace("\n", ", "),
        "role": random.choice(ROLES),
        "organization": random.choice(ORGANIZATIONS),
        "signature": f"https://drive.google.com/signatures/{uuid4()}",
    }


LETTER_TYPES = [
    {
        "id": "event_permission",
        "name": "Event Permission",
        "description": "Permission letters for organizing college events, fests, cultural programs, and departmental functions.",
        "approval_chain": [
            {"step": 1, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 2, "role": "Dean of Academics", "action": "Review & Forward"},
            {"step": 3, "role": "Principal", "action": "Final Approval"},
        ],
        "template": "https://drive.google.com/document/d/1_event_permission/edit",
    },
    {
        "id": "leave_request",
        "name": "Leave Request",
        "description": "Leave or absence requests for students and staff including medical, casual, and duty leave.",
        "approval_chain": [
            {"step": 1, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 2, "role": "Dean of Academics", "action": "Approval"},
        ],
        "template": "https://drive.google.com/document/d/2_leave_request/edit",
    },
    {
        "id": "budget_approval",
        "name": "Budget Approval",
        "description": "Budget and funding approval letters for events, projects, equipment, and departmental initiatives.",
        "approval_chain": [
            {"step": 1, "role": "HOD - Computer Science", "action": "Verify & Recommend"},
            {"step": 2, "role": "Dean of Academics", "action": "Review"},
            {"step": 3, "role": "Finance Officer", "action": "Budget Check"},
            {"step": 4, "role": "Principal", "action": "Final Approval"},
        ],
        "template": "https://drive.google.com/document/d/3_budget_approval/edit",
    },
    {
        "id": "fest_sponsorship",
        "name": "Fest Sponsorship",
        "description": "Sponsorship request letters for college fests and events seeking financial or in-kind support.",
        "approval_chain": [
            {"step": 1, "role": "Dean of Students", "action": "Recommendation"},
            {"step": 2, "role": "Finance Officer", "action": "Feasibility Check"},
            {"step": 3, "role": "Principal", "action": "Final Approval"},
        ],
        "template": "https://drive.google.com/document/d/4_fest_sponsorship/edit",
    },
    {
        "id": "guest_lecture",
        "name": "Guest Lecture Invitation",
        "description": "Invitation letters for guest lectures, seminars, and expert talks by external speakers.",
        "approval_chain": [
            {"step": 1, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 2, "role": "Dean of Academics", "action": "Approval"},
        ],
        "template": "https://drive.google.com/document/d/5_guest_lecture/edit",
    },
    {
        "id": "equipment_procurement",
        "name": "Equipment Procurement",
        "description": "Letters requesting purchase or procurement of equipment, materials, or software for labs and departments.",
        "approval_chain": [
            {"step": 1, "role": "HOD - Computer Science", "action": "Requirement Verification"},
            {"step": 2, "role": "Finance Officer", "action": "Budget Allocation"},
            {"step": 3, "role": "Principal", "action": "Final Approval"},
        ],
        "template": "https://drive.google.com/document/d/6_equipment_procurement/edit",
    },
    {
        "id": "workshop_proposal",
        "name": "Workshop Proposal",
        "description": "Proposal letters for organizing workshops, training programs, hackathons, and skill development sessions.",
        "approval_chain": [
            {"step": 1, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 2, "role": "Dean of Academics", "action": "Review"},
            {"step": 3, "role": "Principal", "action": "Approval"},
        ],
        "template": "https://drive.google.com/document/d/7_workshop_proposal/edit",
    },
    {
        "id": "internship_letter",
        "name": "Internship Letter",
        "description": "Internship request and completion letters for students undertaking industrial or research internships.",
        "approval_chain": [
            {"step": 1, "role": "HOD - Computer Science", "action": "Recommendation"},
            {"step": 2, "role": "Dean of Academics", "action": "Approval"},
        ],
        "template": "https://drive.google.com/document/d/8_internship_letter/edit",
    },
    {
        "id": "general_representation",
        "name": "General Representation",
        "description": "General representations, petitions, or requests to authorities on any matter not covered by other letter types.",
        "approval_chain": [
            {"step": 1, "role": "HOD - Computer Science", "action": "Review & Forward"},
            {"step": 2, "role": "Principal", "action": "Decision"},
        ],
        "template": "https://drive.google.com/document/d/9_general_representation/edit",
    },
]


async def seed(count: int = 15):
    async with AsyncSessionLocal() as session:
        await session.execute(Official.__table__.delete())
        print("Cleared existing officials")

        officials = [generate_official() for _ in range(count)]
        session.add_all(Official(**o) for o in officials)
        await session.commit()
        print(f"Seeded {count} officials")

        await session.execute(LetterType.__table__.delete())
        print("Cleared existing letter types")

        for lt in LETTER_TYPES:
            session.add(LetterType(**lt))
        await session.commit()
        print(f"Seeded {len(LETTER_TYPES)} letter types")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count", type=int, default=15, help="Number of officials to seed"
    )
    args = parser.parse_args()

    asyncio.run(seed(args.count))
