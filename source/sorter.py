import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml

from . import paths

MASTERLIST_URL = "https://raw.githubusercontent.com/PetricaT/IsaacMM/main/masterlist.yaml"
CACHE_FILE = os.path.join(paths.appdata, "masterlist.yaml")
USER_RULES_FILE = os.path.join(paths.appdata, "user_rules.yaml")
CACHE_TTL = timedelta(hours=24)
WORKSHOP_ID_RE = re.compile(r"_(\d+)$")

_masterlist = None


def get_masterlist():
    global _masterlist
    if _masterlist is not None:
        return _masterlist

    data = None
    if _is_cache_fresh():
        data = _try_cache()

    if data is None:
        data = _try_fetch()

    if data is None:
        data = _try_cache()

    if data is None:
        data = _try_bundled()

    _masterlist = data if data else {"groups": [], "mods": []}
    return _masterlist


def fetch_initial():
    get_masterlist()
    if not os.path.exists(USER_RULES_FILE):
        os.makedirs(paths.appdata, exist_ok=True)
        with open(USER_RULES_FILE, "w") as f:
            f.write(
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


def _is_cache_fresh():
    try:
        if not os.path.exists(CACHE_FILE):
            return False
        mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        return datetime.now() - mtime <= CACHE_TTL
    except OSError:
        return False


def _try_fetch():
    try:
        req = Request(MASTERLIST_URL, headers={"User-Agent": "IsaacMM/1.0"})
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        data = yaml.safe_load(raw)
        os.makedirs(paths.appdata, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            f.write(raw)
        return data
    except (URLError, OSError, yaml.YAMLError):
        return None


def _try_cache():
    try:
        with open(CACHE_FILE) as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None


def _try_bundled():
    bundled = os.path.join(paths.BASE_DIR, "masterlist.yaml")
    try:
        with open(bundled) as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None


def _load_user_rules():
    try:
        with open(USER_RULES_FILE) as f:
            data = yaml.safe_load(f)
            return data.get("rules", []) if data else []
    except (OSError, yaml.YAMLError):
        return []


def _merge_user_rules(lookup, rules):
    for rule in rules:
        rid = rule.get("id")
        if rid is None:
            continue
        if rid in lookup:
            entry = lookup[rid]
            for key in ("after", "before"):
                if key in rule:
                    entry.setdefault(key, [])
                    for dep in rule[key]:
                        if dep not in entry[key]:
                            entry[key].append(dep)
        else:
            entry = {"id": rid, "group": "unknown"}
            if "after" in rule:
                entry["after"] = list(rule["after"])
            if "before" in rule:
                entry["before"] = list(rule["before"])
            lookup[rid] = entry


def _extract_workshop_id(folder_name):
    m = WORKSHOP_ID_RE.search(folder_name)
    return int(m.group(1)) if m else None


def _read_tags(mod_path):
    try:
        tree = ET.parse(os.path.join(mod_path, "metadata.xml"))
        root = tree.getroot()
        tags = root.find("tags")
        if tags is not None:
            return [t.get("id", "") for t in tags.findall("tag")]
    except Exception:
        pass
    return []


def _build_group_index(masterlist):
    return {g["name"]: g["priority"] for g in masterlist.get("groups", [])}


def _build_mod_lookup(masterlist):
    lookup = {}
    patterns = []
    tag_entries = []
    for mod in masterlist.get("mods", []):
        if "id" in mod:
            if mod["id"] not in lookup:
                lookup[mod["id"]] = mod
        if "pattern" in mod:
            patterns.append((re.compile(mod["pattern"], re.IGNORECASE), mod))
        if "tag" in mod:
            tag_entries.append((mod["tag"], mod))
    return lookup, patterns, tag_entries


def _match_mod(folder_name, mod_path, mod_name, lookup, patterns, tag_entries):
    wid = _extract_workshop_id(folder_name)
    if wid is not None and wid in lookup:
        return lookup[wid]

    for pat, entry in patterns:
        if pat.search(folder_name):
            return entry

    tags = _read_tags(mod_path)
    for tag, entry in tag_entries:
        if tag in tags:
            return entry

    return None


def _topological_sort(items, key_fn, before_fn, after_fn):
    if not items:
        return []

    item_map = {key_fn(item): item for item in items}
    all_keys = set(item_map.keys())

    in_degree = {k: 0 for k in all_keys}
    graph = defaultdict(list)

    for item in items:
        k = key_fn(item)
        for dep in after_fn(item):
            if dep in all_keys:
                graph[dep].append(k)
                in_degree[k] += 1
        for dep in before_fn(item):
            if dep in all_keys:
                graph[k].append(dep)
                in_degree[dep] += 1

    queue = deque([k for k in all_keys if in_degree[k] == 0])
    result = []

    while queue:
        k = queue.popleft()
        result.append(item_map[k])
        for neighbor in graph[k]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    remaining = [item for item in items if key_fn(item) not in {key_fn(r) for r in result}]
    result.extend(remaining)

    return result


def auto_sort(loaded_mods, mods_path):
    ml = get_masterlist()
    group_priorities = _build_group_index(ml)
    lookup, patterns, tag_entries = _build_mod_lookup(ml)

    rules = _load_user_rules()
    if rules:
        _merge_user_rules(lookup, rules)

    classified = []
    for name, folder in loaded_mods:
        mod_path = os.path.join(mods_path, folder)
        entry = _match_mod(folder, mod_path, name, lookup, patterns, tag_entries)
        group_name = entry["group"] if entry else "unknown"
        classified.append((name, folder, group_name, entry))

    groups = defaultdict(list)
    for name, folder, group_name, entry in classified:
        groups[group_name].append((name, folder, entry))

    sorted_groups = sorted(groups.items(), key=lambda x: group_priorities.get(x[0], 99))

    result = []
    for group_name, group_items in sorted_groups:
        def key_fn(item):
            entry = item[2]
            if entry and "id" in entry:
                return ("id", entry["id"])
            return ("folder", item[1])

        def after_fn(item):
            entry = item[2]
            if entry and "after" in entry:
                return [("id", dep) for dep in entry["after"]]
            return []

        def before_fn(item):
            entry = item[2]
            if entry and "before" in entry:
                return [("id", dep) for dep in entry["before"]]
            return []

        sorted_items = _topological_sort(group_items, key_fn, before_fn, after_fn)
        result.extend([(item[0], item[1]) for item in sorted_items])

    return result
