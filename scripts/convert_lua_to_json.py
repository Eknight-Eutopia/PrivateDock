#!/usr/bin/env python3
"""Convert Azur Lane Lua data files to JSON.
Reads from: LUA_DIR
Writes to:  OUT_DIR
"""

import argparse
import os, sys, re, json
from concurrent.futures import ProcessPoolExecutor, as_completed

from slpp import slpp as lua

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AZURE_LANE_ROOT = os.path.dirname(REPO_ROOT)

DEFAULT_LUA_ROOT = os.path.join(AZURE_LANE_ROOT, 'AzurLaneLuaScripts')
DEFAULT_OUT_ROOT = os.path.join(REPO_ROOT, 'data')

REGION = 'EN'

LUA_DIR = os.path.join(DEFAULT_LUA_ROOT, REGION)
OUT_DIR = os.path.join(DEFAULT_OUT_ROOT, REGION)

# Number of parallel worker processes; 0 = auto (CPU count), 1 = sequential.
WORKERS = 0

# ── skip lists / maps (module-level so pool workers can reference them) ──
SKIP_NAMES = set()  # sharecfg main files to skip entirely
SUBLIST_ONLY = {'ship_skin_template', 'enemy_data_statistics', 'word_template', 'word_legal_template'}
SUBLIST_MAIN_MAP = {'word_sublist': 'word_template', 'word_legal_sublist': 'word_legal_template'}
GAMECFG_SKIP_DIRS = ('guide', 'backhillgraphs', 'activity', 'backyardtheme', 'useragreems')


def log(msg):
    print(msg, flush=True)


def run_parallel(tasks, worker):
    """Run ``worker(task)`` for each task across a process pool.

    Yields results as they complete (streaming). Falls back to running the
    worker inline when WORKERS == 1 or there is only one task. Worker
    exceptions are re-raised in the caller; queued tasks are then cancelled.
    """
    if not tasks:
        return
    max_workers = WORKERS if WORKERS > 0 else (os.cpu_count() or 1)
    max_workers = max(1, min(max_workers, len(tasks)))
    if max_workers == 1:
        for t in tasks:
            yield worker(t)
        return
    ex = ProcessPoolExecutor(max_workers=max_workers)
    try:
        futures = [ex.submit(worker, t) for t in tasks]
        for fut in as_completed(futures):
            yield fut.result()
    except BaseException:
        ex.shutdown(wait=False, cancel_futures=True)
        raise
    ex.shutdown(wait=True)


def strip_comments(text):
    result = []
    i = 0
    n = len(text)
    in_long_string = False
    in_string = False
    str_char = None
    while i < n:
        if in_long_string:
            result.append(text[i])
            if text[i:i+2] == ']]':
                in_long_string = False
                result.append(']')
                i += 2
            else:
                i += 1
            continue
        if in_string:
            result.append(text[i])
            if text[i] == '\\':
                i += 1
                if i < n:
                    result.append(text[i])
                    i += 1
                continue
            if text[i] == str_char:
                in_string = False
            i += 1
            continue
        # block comment
        if text[i:i+4] == '--[[':
            end = text.find(']]', i+4)
            if end >= 0:
                i = end + 2
                continue
        # long string [[...]]
        if text[i:i+2] == '[[':
            in_long_string = True
            result.append('[')
            result.append('[')
            i += 2
            continue
        # line comment
        if text[i:i+2] == '--':
            end = text.find('\n', i+2)
            if end >= 0:
                i = end + 1
            else:
                i = n
            continue
        # string start
        if text[i] in ('"', "'"):
            in_string = True
            str_char = text[i]
            result.append(text[i])
            i += 1
            continue
        result.append(text[i])
        i += 1
    return ''.join(result)


def find_matching_brace(text, start):
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def extract_name(text):
    for pat in [
        r'pg\.(\w+)\.all\s*=',
        r'_G\.pg\.base\.(\w+)\[\d+\]',
        r'pg\.base\.(\w+)\s*\[',
        r'pg\.base\.(\w+)\s*\.\w+\s*=',
    ]:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def extract_all_ids(text, name):
    pattern = r'pg\.' + re.escape(name) + r'\.all\s*=\s*(\{.*?\})'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    raw_close = body.rfind('}')
    if raw_close > 0:
        body = body[:raw_close + 1]
    return _decode_array(body)


def _decode_array(body):
    try:
        result = lua.decode(body)
    except Exception:
        return []
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return list(result.values())
    return []


# ── format parsers ────────────────────────────────────────────────────


def parse_return_table(text):
    m = re.search(r'return\s+(\{.*)', text, re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    close = find_matching_brace(body, 0)
    body = body[:close]
    return lua.decode(body)


def parse_iife(text, name):
    esc_name = re.escape(name)
    entries = {}
    for m in re.finditer(r'\(function\s*\(\s*\)\s*(.*?)end\s*\)\s*\(\)', text, re.DOTALL):
        body = m.group(1)
        idx = 0
        while True:
            m2 = re.search(r'pg\.base\s*\.\s*' + esc_name + r'\s*\[\s*(\d+)\s*\]\s*=\s*\{', body[idx:])
            if not m2:
                break
            tbl_start = idx + m2.start() + m2.group(0).find('{')
            close = find_matching_brace(body, tbl_start)
            key = int(m2.group(1))
            tbl_body = body[tbl_start:close]
            try:
                entries[key] = lua.decode(tbl_body)
            except Exception as e:
                log(f'  [warn] IIFE entry [{key}] parse error: {e}')
            idx = close
        idx2 = 0
        while True:
            m3 = re.search(r'pg\.base\s*\.\s*' + esc_name + r'\s*\.\s*(\w+)\s*=\s*\{', body[idx2:])
            if not m3:
                break
            tbl_start = idx2 + m3.start() + m3.group(0).find('{')
            close = find_matching_brace(body, tbl_start)
            key = m3.group(1)
            tbl_body = body[tbl_start:close]
            try:
                entries[key] = lua.decode(tbl_body)
            except Exception as e:
                log(f'  [warn] IIFE entry [{key}] parse error: {e}')
            idx2 = close
    return entries


def parse_stream(text, name):
    pattern = r'cs\.' + re.escape(name) + r'\s*=\s*(\{.*)'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return {}
    body = m.group(1)
    close = find_matching_brace(body, 0)
    body = body[:close]
    try:
        result = lua.decode(body)
    except Exception as e:
        log(f'  stream parse error for {name}: {e}')
        return {}
    if isinstance(result, list):
        return {i + 1: v for i, v in enumerate(result)}
    return result


def parse_gbase(text, name):
    entries = {}
    pattern = r'_G\.pg\.base\.' + re.escape(name) + r'\s*\[\s*(\d+)\s*\]\s*=\s*\{'
    for m in re.finditer(pattern, text):
        tbl_start = m.start() + m.group(0).find('{')
        close = find_matching_brace(text, tbl_start)
        id_str = m.group(1)
        tbl_body = text[tbl_start:close]
        try:
            entries[int(id_str)] = lua.decode(tbl_body)
        except Exception as e:
            log(f'  gbase parse error for {name}[{id_str}]: {e}')
    return entries


def parse_sublist_table(text):
    m = re.search(r'pg(?:\.base)?\.(\w+_\d+)\s*=\s*(\{.*)', text, re.DOTALL)
    if not m:
        return {}
    body = m.group(2)
    close = find_matching_brace(body, 0)
    body = body[:close]
    try:
        return lua.decode(body)
    except Exception as e:
        log(f'  sublist parse error: {e}')
        return {}


def parse_direct_table(text):
    """Parse pg.<name> = { ... } format (no IIFE, no stream)."""
    m = re.search(r'pg\.\w+\s*=\s*(\{.*)', text, re.DOTALL)
    if not m:
        return None, None
    body = m.group(1)
    close = find_matching_brace(body, 0)
    body = body[:close]
    try:
        result = lua.decode(body)
    except Exception:
        return None, None
    name_m = re.search(r'pg\.([a-zA-Z_]\w*)\s*=', text)
    name = name_m.group(1) if name_m else None
    if isinstance(result, list):
        return name, {i + 1: v for i, v in enumerate(result)}
    return name, result


# ── file-level dispatcher ─────────────────────────────────────────────


def parse_sharecfg_file(filepath, text=None):
    """Parse a sharecfg/ Lua file. Returns (name, all_ids, entries_dict)."""
    if text is None:
        raw = open(filepath, 'r', encoding='utf-8').read()
        text = strip_comments(raw)
    name = extract_name(text)
    if not name:
        base = os.path.splitext(os.path.basename(filepath))[0]
        name = base
    all_ids = extract_all_ids(text, name) or []
    if '__stream__ = true' in text or re.search(r'cs\.' + re.escape(name) + r'\s*=', text):
        entries = parse_stream(text, name)
    elif '(function' in text:
        entries = parse_iife(text, name)
    elif 'return {' in text:
        result = parse_return_table(text)
        entries = result if isinstance(result, dict) else ({} if result is None else {i+1: v for i, v in enumerate(result)})
    else:
        _, entries = parse_direct_table(text)
        if entries is None:
            entries = {}
    return name, all_ids, entries


def parse_gbase_file(filepath):
    """Parse a sharecfgdata/ Lua file (_G.pg.base format)."""
    raw = open(filepath, 'r', encoding='utf-8').read()
    text = strip_comments(raw)
    name = extract_name(text)
    if not name:
        base = os.path.splitext(os.path.basename(filepath))[0]
        name = base
    all_ids = extract_all_ids(text, name) or []
    entries = parse_gbase(text, name)
    return name, all_ids, entries


def parse_gamecfg_file(filepath):
    """Parse a gamecfg/ subdirectory file (return { ... } format)."""
    raw = open(filepath, 'r', encoding='utf-8').read()
    text = strip_comments(raw)
    return parse_return_table(text)


# ── JSON writers ──────────────────────────────────────────────────────


def write_ordered_list(output_path, entries, all_ids):
    """Write entries as a list ordered by all_ids, or dict if all_ids empty.
    Returns the number of ids dropped as nulls (0 when a dict was written)."""
    if all_ids:
        result = [entries.get(id) for id in all_ids]
    else:
        result = entries
    nulls = 0
    if isinstance(result, list):
        nulls = sum(1 for x in result if x is None)
        if nulls:
            result = [x for x in result if x is not None]
    json.dump(result, open(output_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=None, separators=(',', ':'))
    return nulls


def write_keyed_dict(output_path, entries):
    """Write entries as a dict (caller controls key order)."""
    json.dump(entries, open(output_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=None, separators=(',', ':'))


# ── main conversion ────────────────────────────────────────────────────


def _convert_sharecfg_file(task):
    """Worker: convert one sharecfg main file plus its sublist dirs.
    Returns (name, n_entries, n_ids, nulls)."""
    src_dir, out_dir, name, filepath, subdir_names = task
    raw_text = open(filepath, 'r', encoding='utf-8').read()
    text = strip_comments(raw_text)
    all_ids = extract_all_ids(text, name) or []
    if name in SUBLIST_ONLY:
        entries = {}
    else:
        _, _, entries = parse_sharecfg_file(filepath, text)
    for subdir_name in subdir_names:
        subdir_path = os.path.join(src_dir, subdir_name)
        for subfile in sorted(os.listdir(subdir_path)):
            if not subfile.endswith('.lua'):
                continue
            subfp = os.path.join(subdir_path, subfile)
            sub_raw = open(subfp, 'r', encoding='utf-8').read()
            sub_text = strip_comments(sub_raw)
            sub_entries = parse_sublist_table(sub_text)
            records = sub_entries if isinstance(sub_entries, dict) else {}
            for k, v in records.items():
                if k not in entries:
                    entries[k] = v
    outpath = os.path.join(out_dir, name + '.json')
    nulls = write_ordered_list(outpath, entries, all_ids)
    return name, len(entries), len(all_ids), nulls


def convert_sharecfg():
    src = os.path.join(LUA_DIR, 'sharecfg')
    out = os.path.join(OUT_DIR, 'ShareCfg')
    os.makedirs(out, exist_ok=True)
    main_files = {}
    sublist_dirs = {}

    for entry in os.listdir(src):
        path = os.path.join(src, entry)
        if os.path.isfile(path) and entry.endswith('.lua'):
            main_files[entry[:-4]] = path
        elif os.path.isdir(path) and entry.endswith('_sublist'):
            main_name = SUBLIST_MAIN_MAP.get(entry, entry[:-8])
            sublist_dirs.setdefault(main_name, []).append(entry)

    tasks = []
    for name, filepath in sorted(main_files.items()):
        if name in SKIP_NAMES:
            log(f'  [skip] {name}')
            continue
        tasks.append((src, out, name, filepath, sublist_dirs.get(name, [])))

    for name, n_entries, n_ids, nulls in run_parallel(tasks, _convert_sharecfg_file):
        line = f'  {name} -> {n_entries} entries, {n_ids} ids'
        if nulls:
            line += f' [skip {nulls} nulls]'
        log(line)
    log(f'  [done] {len(main_files)} files -> {out}')


def _convert_sharecfgdata_file(task):
    """Worker: convert one sharecfgdata/ file. Returns (name, n_entries, n_ids, nulls)."""
    src_dir, out_dir, entry = task
    name = entry[:-4]
    _, all_ids, entries = parse_gbase_file(os.path.join(src_dir, entry))
    outpath = os.path.join(out_dir, name + '.json')
    nulls = write_ordered_list(outpath, entries, all_ids)
    return name, len(entries), len(all_ids), nulls


def convert_sharecfgdata():
    src = os.path.join(LUA_DIR, 'sharecfgdata')
    out = os.path.join(OUT_DIR, 'sharecfgdata')
    os.makedirs(out, exist_ok=True)
    tasks = []
    for entry in sorted(os.listdir(src)):
        if entry.endswith('.lua'):
            tasks.append((src, out, entry))
    for name, n_entries, n_ids, nulls in run_parallel(tasks, _convert_sharecfgdata_file):
        line = f'  {name} -> {n_entries} entries, {n_ids} ids'
        if nulls:
            line += f' [skip {nulls} nulls]'
        log(line)


def _convert_gamecfg_file(task):
    """Worker: parse one gamecfg/ lua file. Returns (subdir_name, key, result_or_None)."""
    name, key, filepath = task
    result = parse_gamecfg_file(filepath)
    return name, key, result


def convert_gamecfg():
    src = os.path.join(LUA_DIR, 'gamecfg')
    out = os.path.join(OUT_DIR, 'GameCfg')
    os.makedirs(out, exist_ok=True)
    tasks = []
    total_by_name = {}
    ordered_keys = {}
    for entry in sorted(os.listdir(src)):
        path = os.path.join(src, entry)
        if not os.path.isdir(path):
            continue
        if entry in GAMECFG_SKIP_DIRS:
            log(f'  [skip subdir] {entry}')
            continue
        if entry == 'minigametile':
            # each sub-subdir becomes its own output file
            for sub in sorted(os.listdir(path)):
                subpath = os.path.join(path, sub)
                if not os.path.isdir(subpath):
                    continue
                files = [f for f in sorted(os.listdir(subpath)) if f.endswith('.lua')]
                total_by_name[sub] = len(files)
                ordered_keys[sub] = [f[:-4] for f in files]
                for f in files:
                    tasks.append((sub, f[:-4], os.path.join(subpath, f)))
            continue
        files = [f for f in sorted(os.listdir(path)) if f.endswith('.lua')]
        total_by_name[entry] = len(files)
        ordered_keys[entry] = [f[:-4] for f in files]
        for f in files:
            tasks.append((entry, f[:-4], os.path.join(path, f)))

    # Merge results per subdir and write the JSON as soon as a subdir completes.
    # Keys are laid out in the same order the sequential script produced
    # (sorted(os.listdir) then .lua filter), so output is byte-identical
    # regardless of completion order.
    pending = {}
    counts = {n: 0 for n in total_by_name}
    for name, key, result in run_parallel(tasks, _convert_gamecfg_file):
        counts[name] += 1
        if result is not None:
            pending.setdefault(name, {})[key] = result
        if counts[name] == total_by_name[name]:
            merged = pending.pop(name, {})
            entries = {k: merged[k] for k in ordered_keys[name] if k in merged}
            if entries:
                write_keyed_dict(os.path.join(out, name + '.json'), entries)
                log(f'  {name} -> {len(entries)} entries')


def convert_versions():
    """Build data/versions.json from AzurLaneLuaScripts/versions/<REGION>.txt.

    Derives the source/output paths by stripping the trailing 'EN' from
    LUA_DIR / OUT_DIR, so the existing EN conversion is unaffected.
    """
    src = os.path.join(os.path.dirname(LUA_DIR), 'versions')
    out = os.path.join(os.path.dirname(OUT_DIR), 'versions.json')
    if not os.path.isdir(src):
        log(f'  [skip] versions dir not found: {src}')
        return
    order = ['TW', 'KR', 'CN', 'JP', 'EN']
    versions = {}
    for region in order:
        txt = os.path.join(src, region + '.txt')
        if not os.path.isfile(txt):
            continue
        with open(txt, 'r', encoding='utf-8') as f:
            val = f.read().strip()
        if val:
            versions[region] = val
    for fn in sorted(os.listdir(src)):
        if not fn.endswith('.txt'):
            continue
        region = fn[:-4]
        if region in versions:
            continue
        with open(os.path.join(src, fn), 'r', encoding='utf-8') as f:
            val = f.read().strip()
        if val:
            versions[region] = val
    if not versions:
        log('  [skip] no version .txt files found')
        return
    json.dump(versions, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=4, separators=(',', ':'))
    log(f'  [done] {out} -> {versions}')


def main():
    global LUA_DIR, OUT_DIR, WORKERS
    parser = argparse.ArgumentParser(
        description='Convert Azur Lane Lua data files (AzurLaneLuaScripts) to JSON (PrivateDock/data).')
    parser.add_argument('--input', default=None, metavar='DIR',
                        help='root of unpacked Lua data (default: <PrivateDock parent>/AzurLaneLuaScripts); region subdir is appended')
    parser.add_argument('--output', default=None, metavar='DIR',
                        help='output data root (default: <PrivateDock repo>/data); region subdir is appended')
    parser.add_argument('--region', default=REGION, help='region subfolder (default: EN)')
    parser.add_argument('--workers', type=int, default=0, metavar='N',
                        help='parallel worker processes (default: CPU count; 1 = sequential)')
    args = parser.parse_args()

    lua_root = args.input or DEFAULT_LUA_ROOT
    out_root = args.output or DEFAULT_OUT_ROOT
    LUA_DIR = os.path.join(lua_root, args.region)
    OUT_DIR = os.path.join(out_root, args.region)
    WORKERS = args.workers
    if WORKERS == 1:
        log('parallel workers: 1 (sequential)')
    elif WORKERS > 1:
        log(f'parallel workers: {WORKERS}')
    else:
        log(f'parallel workers: auto ({os.cpu_count() or 1})')
    log(f'input: {LUA_DIR}')
    log(f'output: {OUT_DIR}')

    log('=== sharecfg -> ShareCfg ===')
    convert_sharecfg()
    log('=== sharecfgdata -> sharecfgdata ===')
    convert_sharecfgdata()
    log('=== gamecfg -> GameCfg ===')
    convert_gamecfg()
    log('=== versions -> versions.json ===')
    convert_versions()
    log('=== Done ===')


if __name__ == '__main__':
    main()
