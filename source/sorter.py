import os
import re
import ssl
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Callable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

import certifi
import yaml

from . import logger, paths

_ssl_context = ssl.create_default_context(cafile=certifi.where())

MASTERLIST_URL: str = "https://raw.githubusercontent.com/PetricaT/IsaacMM/main/masterlist.yaml"
CACHE_FILE: str = os.path.join(paths.appdata, "masterlist.yaml")
USER_RULES_FILE: str = os.path.join(paths.config_dir, "user_rules.yaml")
LAST_ORDER_FILE: str = os.path.join(paths.appdata, "last_order.yaml")
CACHE_TTL: timedelta = timedelta(hours=24)

_masterlist: Optional[dict] = None


def get_masterlist() -> dict:
    global _masterlist
    if _masterlist is not None:
        return _masterlist

    yaml_data = None
    if _is_cache_fresh():
        yaml_data = _try_cache()

    if yaml_data is None:
        yaml_data = _try_fetch()

    if yaml_data is None:
        yaml_data = _try_cache()

    if yaml_data is None:
        yaml_data = _try_bundled()

    _masterlist = yaml_data if yaml_data else {"groups": [], "mods": []}
    return _masterlist


def fetch_initial() -> None:
    get_masterlist()
    if not os.path.exists(USER_RULES_FILE):
        os.makedirs(paths.config_dir, exist_ok=True)
        with open(USER_RULES_FILE, "w") as rules_file:
            rules_file.write(
                "# User-defined load order rules\n"
                "# -----------------------------------------------\n"
                "# Add custom before/after constraints by Steam Workshop ID.\n"
                "# These merge with masterlist.yaml on every auto-sort.\n"
                "# Uncomment and edit the example below.\n"
                "# -----------------------------------------------------------\n"
                "rules:\n"
                "  # - id: 1234567890\n"
                "  #   after: [9876543210]\n"
            )


def _is_cache_fresh() -> bool:
    try:
        if not os.path.exists(CACHE_FILE):
            return False
        file_mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        return datetime.now() - file_mtime <= CACHE_TTL
    except OSError:
        return False


def _try_fetch() -> Optional[dict]:
    try:
        request = Request(MASTERLIST_URL, headers={"User-Agent": "IsaacMM/1.0"})
        with urlopen(request, timeout=10, context=_ssl_context) as response:
            raw_content = response.read().decode("utf-8")
        yaml_data = yaml.safe_load(raw_content)
        os.makedirs(paths.appdata, exist_ok=True)
        with open(CACHE_FILE, "w") as cache_file:
            cache_file.write(raw_content)
        return yaml_data
    except URLError:
        logger.log("warning", "No network, cannot fetch latest masterlist")
        return None
    except (OSError, yaml.YAMLError) as exc:
        logger.log("error", f"Error loading masterlist: {exc}")
        return None


def _try_cache() -> Optional[dict]:
    try:
        with open(CACHE_FILE) as cache_file:
            return yaml.safe_load(cache_file)
    except (OSError, yaml.YAMLError):
        return None


def _try_bundled() -> Optional[dict]:
    bundled_path = os.path.join(paths.BASE_DIR, "masterlist.yaml")
    try:
        with open(bundled_path) as bundled_file:
            return yaml.safe_load(bundled_file)
    except (OSError, yaml.YAMLError):
        return None


def save_last_order(folder_order: list) -> None:
    try:
        os.makedirs(paths.appdata, exist_ok=True)
        with open(LAST_ORDER_FILE, "w") as order_file:
            yaml.dump({"ordered_folders": folder_order}, order_file, default_flow_style=False)
    except OSError as exc:
        logger.log("error", f"Failed to save last order: {exc}")


def load_last_order() -> Optional[list]:
    try:
        with open(LAST_ORDER_FILE) as order_file:
            yaml_data = yaml.safe_load(order_file)
            return yaml_data.get("ordered_folders") if yaml_data else None
    except (OSError, yaml.YAMLError):
        return None


def _load_user_rules() -> list:
    try:
        with open(USER_RULES_FILE) as rules_file:
            yaml_data = yaml.safe_load(rules_file)
            return yaml_data.get("rules", []) if yaml_data else []
    except (OSError, yaml.YAMLError):
        return []


def _merge_user_rules(mod_lookup: dict, rules: list) -> None:
    for rule in rules:
        rule_id = rule.get("id")
        if rule_id is None:
            continue
        if rule_id in mod_lookup:
            existing_entry = mod_lookup[rule_id]
            for key in ("after", "before"):
                if key in rule:
                    existing_entry.setdefault(key, [])
                    for dependency in rule[key]:
                        if dependency not in existing_entry[key]:
                            existing_entry[key].append(dependency)
        else:
            new_entry: dict = {"id": rule_id, "group": "unknown"}
            if "after" in rule:
                new_entry["after"] = list(rule["after"])
            if "before" in rule:
                new_entry["before"] = list(rule["before"])
            mod_lookup[rule_id] = new_entry


def _extract_workshop_id(folder_name: str) -> Optional[int]:
    workshop_match = paths.WORKSHOP_ID_RE.search(folder_name)
    return int(workshop_match.group(1)) if workshop_match else None


def _read_tags(mod_path: str) -> list:
    try:
        metadata_tree = ET.parse(os.path.join(mod_path, "metadata.xml"))
        xml_root = metadata_tree.getroot()
        tags_element = xml_root.find("tags")
        if tags_element is not None:
            return [tag.get("id", "") for tag in tags_element.findall("tag")]
    except Exception as exc:
        logger.log("error", f"Failed to read tags from {mod_path}: {exc}")
    return []


def _build_group_index(masterlist: dict) -> dict:
    return {group["name"]: group["priority"] for group in masterlist.get("groups", [])}


def _build_mod_lookup(masterlist: dict) -> tuple[dict, list, list]:
    mod_lookup: dict = {}
    pattern_entries: list = []
    tag_entries: list = []
    for mod_entry in masterlist.get("mods", []):
        if "id" in mod_entry:
            if mod_entry["id"] not in mod_lookup:
                mod_lookup[mod_entry["id"]] = mod_entry
        if "pattern" in mod_entry:
            pattern_entries.append((re.compile(mod_entry["pattern"], re.IGNORECASE), mod_entry))
        if "tag" in mod_entry:
            tag_entries.append((mod_entry["tag"], mod_entry))
    return mod_lookup, pattern_entries, tag_entries


def _match_mod(
    folder_name: str,
    mod_path: str,
    mod_name: str,
    mod_lookup: dict,
    pattern_entries: list,
    tag_entries: list,
) -> Optional[dict]:
    workshop_id = _extract_workshop_id(folder_name)
    if workshop_id is not None and workshop_id in mod_lookup:
        return mod_lookup[workshop_id]

    for compiled_pattern, mod_entry in pattern_entries:
        if compiled_pattern.search(folder_name):
            return mod_entry

    mod_tags = _read_tags(mod_path)
    for tag_name, mod_entry in tag_entries:
        if tag_name in mod_tags:
            return mod_entry

    return None


def _topological_sort(
    items: list,
    key_function: Callable,
    before_function: Callable,
    after_function: Callable,
) -> list:
    if not items:
        return []

    item_map = {key_function(item): item for item in items}
    all_keys = set(item_map.keys())

    in_degree = {key: 0 for key in all_keys}
    graph: dict = defaultdict(list)

    for item in items:
        current_key = key_function(item)
        for dependency in after_function(item):
            if dependency in all_keys:
                graph[dependency].append(current_key)
                in_degree[current_key] += 1
        for dependency in before_function(item):
            if dependency in all_keys:
                graph[current_key].append(dependency)
                in_degree[dependency] += 1

    traversal_queue = deque([key for key in all_keys if in_degree[key] == 0])
    sorted_items = []

    while traversal_queue:
        current_key = traversal_queue.popleft()
        sorted_items.append(item_map[current_key])
        for adjacent_key in graph[current_key]:
            in_degree[adjacent_key] -= 1
            if in_degree[adjacent_key] == 0:
                traversal_queue.append(adjacent_key)

    result_keys = {key_function(item) for item in sorted_items}
    remaining_items = [item for item in items if key_function(item) not in result_keys]
    sorted_items.extend(remaining_items)

    return sorted_items


def auto_sort(mod_entries: list, mods_path: str) -> list:
    masterlist = get_masterlist()
    group_priorities = _build_group_index(masterlist)
    mod_lookup, pattern_entries, tag_entries = _build_mod_lookup(masterlist)

    user_rules = _load_user_rules()
    if user_rules:
        _merge_user_rules(mod_lookup, user_rules)

    classified_mods = []
    for mod_name, mod_folder in mod_entries:
        full_mod_path = os.path.join(mods_path, mod_folder)
        matched_entry = _match_mod(mod_folder, full_mod_path, mod_name, mod_lookup, pattern_entries, tag_entries)
        group_name = matched_entry["group"] if matched_entry else "unknown"
        classified_mods.append((mod_name, mod_folder, group_name, matched_entry))

    groups: dict = defaultdict(list)
    for mod_name, mod_folder, group_name, matched_entry in classified_mods:
        groups[group_name].append((mod_name, mod_folder, matched_entry))

    sorted_groups = sorted(groups.items(), key=lambda group_item: group_priorities.get(group_item[0], 99))

    result: list = []
    for group_name, group_mods in sorted_groups:

        def key_function(item: tuple) -> tuple:
            matched_entry = item[2]
            if matched_entry and "id" in matched_entry:
                return ("id", matched_entry["id"])
            return ("folder", item[1])

        def after_function(item: tuple) -> list:
            matched_entry = item[2]
            if matched_entry and "after" in matched_entry:
                return [("id", dependency) for dependency in matched_entry["after"]]
            return []

        def before_function(item: tuple) -> list:
            matched_entry = item[2]
            if matched_entry and "before" in matched_entry:
                return [("id", dependency) for dependency in matched_entry["before"]]
            return []

        sorted_items = _topological_sort(group_mods, key_function, before_function, after_function)
        result.extend([(item[0], item[1]) for item in sorted_items])

    return result
