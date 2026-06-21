import asyncio
import random
import argparse
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faker import Faker

from db.session import AsyncSessionLocal
from db.models import Official

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


async def seed(count: int = 15):
    async with AsyncSessionLocal() as session:
        await session.execute(Official.__table__.delete())
        print("Cleared existing officials")

        officials = [generate_official() for _ in range(count)]
        session.add_all(Official(**o) for o in officials)
        await session.commit()
        print(f"Seeded {count} officials")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count", type=int, default=15, help="Number of officials to seed"
    )
    args = parser.parse_args()

    asyncio.run(seed(args.count))
