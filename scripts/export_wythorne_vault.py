#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

SRC_VAULT = Path('/Users/radorrans/Downloads/Wythorne')
DEST_CONTENT = Path('/Users/radorrans/Documents/GitHub/obsidian-quartz-template/source/content')

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]')
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n?', re.S)
DATAVIEW_BLOCK_RE = re.compile(r'```\s*dataview(?:js)?\n.*?```', re.S)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == '':
        return ''
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return []
        parts = [part.strip() for part in inner.split(',')]
        return [parse_scalar(part) for part in parts]
    if re.fullmatch(r'-?\d+', value):
        return int(value)
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text = m.group(1)
    body = text[m.end():]
    lines = fm_text.splitlines()
    data: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if ':' not in line:
            i += 1
            continue
        key, rest = line.split(':', 1)
        key = key.strip()
        rest = rest.strip()
        if rest:
            data[key] = parse_scalar(rest)
            i += 1
            continue
        items: list[Any] = []
        j = i + 1
        while j < len(lines):
            sub = lines[j]
            if not sub.startswith('  - '):
                break
            items.append(parse_scalar(sub[4:]))
            j += 1
        data[key] = items if items else ''
        i = j
    return data, body


def ensure_list(value: Any) -> list[Any]:
    if value in ('', None):
        return []
    if isinstance(value, list):
        return value
    return [value]


def extract_link_target(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            target = extract_link_target(item)
            if target:
                return target
        return None
    if not isinstance(value, str):
        return str(value)
    m = WIKILINK_RE.search(value)
    if m:
        return m.group(1).strip()
    return value.strip() or None


def extract_link_targets(value: Any) -> list[str]:
    result: list[str] = []
    for item in ensure_list(value):
        target = extract_link_target(item)
        if target:
            result.append(target)
    return result


def load_notes(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, list[str]]]:
    notes: dict[str, dict[str, Any]] = {}
    by_name: dict[str, str] = {}
    folders: dict[str, list[str]] = {}
    for path in sorted(root.rglob('*.md')):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(text)
        stem = path.stem
        notes[rel] = {
            'path': rel,
            'stem': stem,
            'folder': path.parent.relative_to(root).as_posix() if path.parent != root else '',
            'frontmatter': frontmatter,
            'body': body,
            'text': text,
        }
        by_name[stem] = rel
        folders.setdefault(path.parent.relative_to(root).as_posix() if path.parent != root else '', []).append(rel)
    return notes, by_name, folders


def fmt_link(target: str) -> str:
    return f'[[{target}]]'


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return '_None found._'
    out = [
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(['---'] * len(headers)) + ' |',
    ]
    for row in rows:
        out.append('| ' + ' | '.join(str(item) for item in row) + ' |')
    return '\n'.join(out)


def replace_dataview(rel: str, note: dict[str, Any], notes: dict[str, dict[str, Any]], by_name: dict[str, str], folders: dict[str, list[str]]) -> str:
    body = note['body']
    stem = note['stem']
    folder = note['folder']

    if folder == 'Classes':
        aides = []
        students = []
        professors = []
        for other in notes.values():
            if other['folder'] != 'Muses':
                continue
            fm = other['frontmatter']
            tags = {str(t) for t in ensure_list(fm.get('tags'))}
            if 'student' in tags:
                if stem in extract_link_targets(fm.get('studying')):
                    students.append([fmt_link(other['stem']), ', '.join(fmt_link(x) for x in extract_link_targets(fm.get('specialty'))), fm.get('year', ''), ', '.join(fmt_link(x) for x in extract_link_targets(fm.get('writer')))])
                if stem in extract_link_targets(fm.get('aide')):
                    aides.append([fmt_link(other['stem']), ', '.join(fmt_link(x) for x in extract_link_targets(fm.get('specialty'))), fm.get('year', ''), ', '.join(fmt_link(x) for x in extract_link_targets(fm.get('writer')))])
            if 'professor' in tags and stem in extract_link_targets(fm.get('teaching')):
                professors.append(other)

        parts = []
        if professors:
            prof = professors[0]
            prof_fm = prof['frontmatter']
            parts.append(f'**This class is taught by:** {fmt_link(prof["stem"])} *({", ".join(fmt_link(x) for x in extract_link_targets(prof_fm.get("specialty")))}, {", ".join(fmt_link(x) for x in extract_link_targets(prof_fm.get("writer")))})*')
        parts.append('## Aides\n\n' + markdown_table(['Aide', 'Specialty', 'Year', 'Written By'], sorted(aides, key=lambda r: str(r[0]))))
        parts.append('## Students\n\n' + markdown_table(['Student', 'Specialty', 'Year', 'Written By'], sorted(students, key=lambda r: str(r[0]))))
        replacement = '\n\n'.join(parts)
        return DATAVIEW_BLOCK_RE.sub(replacement, body)

    if folder == 'Dorms' and stem.startswith('Dorm '):
        roomies = []
        for other in notes.values():
            if other['folder'] != 'Muses':
                continue
            fm = other['frontmatter']
            tags = {str(t) for t in ensure_list(fm.get('tags'))}
            if 'student' in tags and stem == extract_link_target(fm.get('room')):
                roomies.append([fmt_link(other['stem']), ', '.join(fmt_link(x) for x in extract_link_targets(fm.get('specialty'))), fm.get('year', ''), ', '.join(fmt_link(x) for x in extract_link_targets(fm.get('writer')))])
        replacement = '## Residents\n\n' + markdown_table(['Student', 'Specialty', 'Year', 'Written By'], sorted(roomies, key=lambda r: str(r[0])))
        return DATAVIEW_BLOCK_RE.sub(replacement, body)

    if rel == 'Viewing/Dorms.md':
        dorms = sorted((Path(p).stem for p in folders.get('Dorms', [])), key=lambda x: x)
        replacement = '## Dorm Directory\n\n' + '\n'.join(f'- {fmt_link(name)}' for name in dorms)
        return DATAVIEW_BLOCK_RE.sub(replacement, body)

    if rel == 'Viewing/Offered courses.md':
        specialties = ['verdancy', 'canticry', 'glyphistry', 'entropy', 'emissary', 'general']
        sections = ['i.', 'ii.', 'iii.', 'iv.', 'v.', 'vi.']
        parts = ['> click on the links to see further info, such as teachers, aides, and students *!*', '---']
        for numeral, spec in zip(sections, specialties):
            title = f'{numeral} {fmt_link(spec)}'
            classes = []
            for other in notes.values():
                if other['folder'] != 'Classes':
                    continue
                if spec in extract_link_targets(other['frontmatter'].get('specialty')):
                    classes.append(other['stem'])
            classes = sorted(classes)
            parts.append(f'# {title}')
            if classes:
                parts.extend(f'- {fmt_link(name)}' for name in classes)
            else:
                parts.append('_No courses found._')
        return '\n'.join(parts) + '\n'

    if folder == 'Specialties':
        related_classes = []
        related_professors = []
        related_students = []
        for other in notes.values():
            ofm = other['frontmatter']
            tags = {str(t) for t in ensure_list(ofm.get('tags'))}
            if other['folder'] == 'Classes' and stem in extract_link_targets(ofm.get('specialty')):
                related_classes.append(other['stem'])
            if other['folder'] == 'Muses' and stem in extract_link_targets(ofm.get('specialty')):
                if 'professor' in tags:
                    related_professors.append(other['stem'])
                if 'student' in tags:
                    related_students.append(other['stem'])
        parts = [f'# {stem.title()}', '', '## Classes', '']
        if related_classes:
            parts.extend(f'- {fmt_link(name)}' for name in sorted(related_classes))
        else:
            parts.append('_None found._')
        parts.extend(['', '## Professors', ''])
        if related_professors:
            parts.extend(f'- {fmt_link(name)}' for name in sorted(related_professors))
        else:
            parts.append('_None found._')
        parts.extend(['', '## Students', ''])
        if related_students:
            parts.extend(f'- {fmt_link(name)}' for name in sorted(related_students))
        else:
            parts.append('_None found._')
        replacement = '\n'.join(parts)
        if DATAVIEW_BLOCK_RE.search(body):
            return DATAVIEW_BLOCK_RE.sub(replacement, body)
        if body.strip():
            return body.rstrip() + '\n\n' + replacement + '\n'
        return replacement + '\n'

    return DATAVIEW_BLOCK_RE.sub('_Dataview block omitted in static export._', body)


def build_homepage(notes: dict[str, dict[str, Any]], folders: dict[str, list[str]]) -> str:
    def links(folder: str, limit: int | None = None) -> list[str]:
        items = sorted(Path(p).stem for p in folders.get(folder, []))
        if limit is not None:
            items = items[:limit]
        return [f'- {fmt_link(name)}' for name in items]

    total_notes = len(notes)
    classes = len(folders.get('Classes', []))
    dorms = len(folders.get('Dorms', []))
    muses = len(folders.get('Muses', []))
    specialties = len(folders.get('Specialties', []))

    lines = [
        '---',
        'title: Wythorne',
        '---',
        '',
        '# Wythorne',
        '',
        'A published export of the Wythorne Obsidian vault.',
        '',
        f'- Total notes: **{total_notes}**',
        f'- Classes: **{classes}**',
        f'- Muses: **{muses}**',
        f'- Dorms: **{dorms}**',
        f'- Specialties: **{specialties}**',
        '',
        '## Start here',
        '',
        '- [[Viewing/Offered courses|Offered courses]]',
        '- [[Viewing/Dorms|Dorms]]',
        '- [[Specialties/verdancy|Verdancy]]',
        '- [[Specialties/canticry|Canticry]]',
        '- [[Specialties/glyphistry|Glyphistry]]',
        '- [[Specialties/entropy|Entropy]]',
        '- [[Specialties/emissary|Emissary]]',
        '- [[Specialties/general|General]]',
        '',
        '## Sample classes',
        '',
    ]
    lines.extend(links('Classes', 10))
    lines.extend(['', '## Sample muses', ''])
    lines.extend(links('Muses', 10))
    lines.extend(['', '## Dorms', ''])
    lines.extend(links('Dorms'))
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    if DEST_CONTENT.exists():
        shutil.rmtree(DEST_CONTENT)
    DEST_CONTENT.mkdir(parents=True, exist_ok=True)

    for src in SRC_VAULT.rglob('*'):
        rel = src.relative_to(SRC_VAULT)
        if any(part.startswith('.') for part in rel.parts):
            continue
        if 'Templates' in rel.parts:
            continue
        if src.name == '.DS_Store' or src.suffix == '.base':
            continue
        dest = DEST_CONTENT / rel
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    notes, by_name, folders = load_notes(DEST_CONTENT)

    for rel, note in notes.items():
        path = DEST_CONTENT / rel
        fm_text = ''
        if note['frontmatter']:
            original_text = path.read_text(encoding='utf-8')
            m = FRONTMATTER_RE.match(original_text)
            if m:
                fm_text = original_text[:m.end()]
        new_body = replace_dataview(rel, note, notes, by_name, folders)
        path.write_text(fm_text + new_body, encoding='utf-8')

    notes, _, folders = load_notes(DEST_CONTENT)
    (DEST_CONTENT / 'index.md').write_text(build_homepage(notes, folders), encoding='utf-8')
    print(f'Exported vault from {SRC_VAULT} to {DEST_CONTENT}')


if __name__ == '__main__':
    main()
