"""List loaded Act sections with no official crosswalk entry."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import get_session_factory  # noqa: E402
from backend.models import Act, Section, SectionMap  # noqa: E402


def main() -> None:
    with get_session_factory()() as session:
        old_sections = (
            session.query(Section)
            .join(Act)
            .filter(Act.year == 1961)
            .order_by(Section.number)
            .all()
        )
        new_sections = (
            session.query(Section)
            .join(Act)
            .filter(Act.year == 2025)
            .order_by(Section.number)
            .all()
        )
        map_rows = session.query(SectionMap).all()
        mapped_old = {row.old_section_id for row in map_rows if row.old_section_id}
        mapped_new = {row.new_section_id for row in map_rows if row.new_section_id}

        missing_old = [row for row in old_sections if row.id not in mapped_old]
        missing_new = [row for row in new_sections if row.id not in mapped_new]
        print(
            f"Loaded {len(old_sections)} sections from 1961 and "
            f"{len(new_sections)} sections from 2025."
        )
        print(f"Sections without a mapping: {len(missing_old) + len(missing_new)}")
        for year, rows in ((1961, missing_old), (2025, missing_new)):
            for row in rows:
                print(f"{year}\t{row.number}\t{row.title}\t{row.id}")


if __name__ == "__main__":
    main()