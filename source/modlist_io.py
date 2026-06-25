"""Mod list import/export to CSV."""

import csv
import re
from typing import Dict, List, Optional, Tuple

WORKSHOP_ID_RE: re.Pattern = re.compile(r"_(\d+)$")


def _extract_workshop_id(folder_name: str) -> Optional[str]:
    match = WORKSHOP_ID_RE.search(folder_name)
    return match.group(1) if match else None


def export_modlist_csv(file_path: str, items: List[Tuple[str, str]]) -> int:
    with open(file_path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["mod_order", "mod_id", "mod_name", "mod_workshop_link"])
        for sort_index, (folder_name, display_name) in enumerate(items, start=1):
            workshop_id = _extract_workshop_id(folder_name) or ""
            workshop_link = (
                f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
                if workshop_id
                else "DEV_NON_STEAM"
            )
            writer.writerow([sort_index, workshop_id, display_name, workshop_link])
    return len(items)


def import_modlist_csv(
    file_path: str,
    known_mods: Dict[str, Tuple[str, str]],
) -> List[str]:
    with open(file_path, newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or "mod_id" not in reader.fieldnames:
            raise ValueError("Invalid CSV: missing mod_id column")
        rows = list(reader)

    if not rows:
        raise ValueError("CSV contains no mod entries")

    wsid_to_folder: Dict[str, str] = {}
    name_to_folder: Dict[str, str] = {}
    for folder_name, (wsid, display_name) in known_mods.items():
        if wsid:
            wsid_to_folder[wsid] = folder_name
        name_to_folder[display_name] = folder_name

    ordered: List[str] = []
    for row in rows:
        workshop_id = row.get("mod_id", "").strip()
        display_name = row.get("mod_name", "").strip()
        if workshop_id and workshop_id in wsid_to_folder:
            ordered.append(wsid_to_folder[workshop_id])
        elif display_name and display_name in name_to_folder:
            ordered.append(name_to_folder[display_name])

    return ordered
