#!/usr/bin/env python3
"""Post-run heuristic structure audit; reads frozen results, makes no API calls.

This is not a Markdown/RST parser or human annotation. It records an independent
line-based inventory of fenced blocks and pipe tables, including MkDocs-style
indented fences in a separate scope. Never writes inside the frozen run directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / 'docs/rag/chunk-experiments/20260912T062952243934Z'
DEFAULT_OUTPUT = ROOT / 'docs/rag/chunking-structure-audit-20260912.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def line_offsets(text):
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return lines, offsets


def trim(text, start, end):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def identify_blocks(text, max_indent=None):
    """Heuristic only: closed backtick/tilde fences and header+delimiter pipe tables.

    A fence closes at a same-character marker at least as long as its opener.
    Arbitrary space indentation is allowed only for the expanded MkDocs scope.
    Nested list/blockquote semantics, escaped pipes and rendering are not parsed.
    """
    lines, offsets = line_offsets(text)
    blocks, index = [], 0
    while index < len(lines):
        line = lines[index].rstrip('\r\n')
        opener = re.match(r'^( *)(`{3,}|~{3,})(.*)$', line)
        if opener and (max_indent is None or len(opener.group(1)) <= max_indent):
            indent, marker = len(opener.group(1)), opener.group(2)
            last = index + 1
            while last < len(lines):
                if re.fullmatch(r' *' + re.escape(marker[0]) + '{' + str(len(marker)) + r',} *', lines[last].rstrip('\r\n')):
                    break
                last += 1
            if last < len(lines):
                start, end = trim(text, offsets[index], offsets[last + 1])
                blocks.append({'start': start, 'end': end, 'line_start': index + 1, 'line_end': last + 1,
                               'kind': 'code_fence', 'indent_spaces': indent})
                index = last + 1
                continue
        if '|' in line and index + 1 < len(lines):
            cells = lines[index + 1].strip().strip('|').split('|')
            if len(cells) >= 2 and all(re.fullmatch(r'\s*:?-{3,}:?\s*', cell) for cell in cells):
                last = index + 2
                while last < len(lines) and '|' in lines[last] and lines[last].strip():
                    last += 1
                start, end = trim(text, offsets[index], offsets[last])
                blocks.append({'start': start, 'end': end, 'line_start': index + 1, 'line_end': last,
                               'kind': 'markdown_table', 'indent_spaces': 0})
                index = last
                continue
        index += 1
    return blocks


def containment(chunks, source_id, block):
    return [chunk['id'] for chunk in chunks if chunk['parent_id'] == source_id
            and chunk['source_start'] <= block['start'] and chunk['source_end'] >= block['end']]


def summarize(blocks):
    outcomes = Counter('gain' if not block['old_contained'] and block['new_contained']
                       else 'loss' if block['old_contained'] and not block['new_contained']
                       else 'tie' for block in blocks)
    return {'blocks': len(blocks), 'old_contained': sum(block['old_contained'] for block in blocks),
            'new_contained': sum(block['new_contained'] for block in blocks),
            'gain': outcomes['gain'], 'tie': outcomes['tie'], 'loss': outcomes['loss'],
            'kinds': dict(sorted(Counter(block['kind'] for block in blocks).items()))}


def coverage(sources, chunks):
    missing_whitespace, missing_nonwhitespace, total_nonwhitespace = 0, 0, 0
    for source in sources:
        covered = set()
        for chunk in chunks:
            if chunk['parent_id'] != source['id']:
                continue
            start, end = chunk['source_start'], chunk['source_end']
            if source['text'][start:end] != chunk['text']:
                raise ValueError('Frozen chunk does not exactly match source span')
            covered.update(range(start, end))
        for index, character in enumerate(source['text']):
            total_nonwhitespace += not character.isspace()
            if index not in covered:
                missing_whitespace += character.isspace()
                missing_nonwhitespace += not character.isspace()
    return {'total_nonwhitespace_characters': total_nonwhitespace,
            'missing_nonwhitespace_characters': missing_nonwhitespace,
            'missing_whitespace_characters': missing_whitespace}


def audit(run):
    manifest = load(run / 'manifest.json')
    for name, expected in manifest['artifacts_sha256'].items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen artifact hash mismatch: {name}')
    sources, chunks = load(run / 'course-sources.json'), load(run / 'course-chunks.json')
    scopes = {}
    for scope, max_indent in [('standard_markdown_max_3_spaces', 3), ('including_mkdocs_indented_fences', None)]:
        records, oversized = [], []
        for source in sources:
            if not source['id'].endswith('.md'):
                continue
            for block in identify_blocks(source['text'], max_indent):
                block = {'source_id': source['id'], 'source_url': source['source_url'], **block,
                         'characters': block['end'] - block['start']}
                if block['characters'] > 1200:
                    oversized.append(block)
                    continue
                old = containment(chunks['legacy1200'], source['id'], block)
                new = containment(chunks['recursive1200'], source['id'], block)
                records.append(block | {'old_contained': bool(old), 'new_contained': bool(new),
                                        'old_containing_chunk_ids': old, 'new_containing_chunk_ids': new})
        scopes[scope] = {'summary': summarize(records), 'blocks': records, 'oversized_excluded': oversized}

    rst_markers = []
    for source in sources:
        if not source['id'].endswith('.rst'):
            continue
        lines, offsets = line_offsets(source['text'])
        for index, line in enumerate(lines):
            if re.fullmatch(r' {0,3}~{3,}\s*', line):
                rst_markers.append({'source_id': source['id'], 'source_url': source['source_url'],
                                    'line': index + 1, 'start': offsets[index],
                                    'end': offsets[index] + len(line.rstrip('\r\n')),
                                    'marker_text': line.rstrip('\r\n'),
                                    'preceding_heading_text': lines[index - 1].strip() if index else '',
                                    'kind': 'rst_heading_underline_matching_markdown_fence_pattern'})
    split_chunks = [
        {'chunk_id': chunk['id'], 'source_id': chunk['parent_id'],
         'start': chunk['source_start'], 'end': chunk['source_end'],
         'protected_block_types': chunk['metadata']['protected_block_types']}
        for chunk in chunks['recursive1200'] if chunk['metadata']['protected_block_split']
    ]
    dataset = load(run / 'dataset.json')
    mlqa_chunks = load(run / 'chunks.json')
    all_coverage = {'course_sources': {name: coverage(sources, group) for name, group in chunks.items()},
                    'mlqa': {name: coverage(dataset['documents'], group) for name, group in mlqa_chunks.items()}}
    expanded = scopes['including_mkdocs_indented_fences']['blocks']
    result = {
        'schema_version': 'post-run-chunk-structure-audit-v1',
        'audit_date': '2026-09-12', 'frozen_run': str(run.relative_to(ROOT)) if run.is_relative_to(ROOT) else str(run),
        'audit_type': 'post_run_heuristic_structure_diagnostic', 'human_annotation': False,
        'api_calls': 0, 'algorithm_or_parameters_changed': False,
        'frozen_artifact_hashes_verified': len(manifest['artifacts_sha256']),
        'manifest_sha256': hashlib.sha256((run / 'manifest.json').read_bytes()).hexdigest(),
        'method': {
            'implementation': 'scripts/audit_chunk_structure.py',
            'character_coordinates': 'Python Unicode characters, zero-based half-open source intervals; block surrounding whitespace trimmed',
            'line_coordinates': 'One-based inclusive source lines including opening and closing marker lines',
            'intact_definition': 'At least one output chunk from the same source contains the entire original block interval',
            'inventory': 'Independent line regex inventory of closed backtick/tilde fences and header+delimiter pipe tables, restricted to six .md sources and blocks <=1200 characters',
            'scope_distinction': 'Standard scope accepts opening fences indented at most three spaces; expanded scope also accepts indented MkDocs tab fences',
            'limitations': 'Heuristic, not a rendering parser or human code-quality judgment. It does not fully parse nested lists, blockquotes, escaped pipes, or imported code macros. Several src fences contain external-code import directives, not expanded executable code. RST marker matches are heading underlines, not genuine Markdown code blocks.',
            'production_boundary': 'Production imports PDF/TXT/MD; direct RST source chunking was limited to this offline course structure experiment.',
        },
        'scopes': scopes,
        'expanded_scope_losses': [block for block in expanded if block['old_contained'] and not block['new_contained']],
        'expanded_scope_not_intact_in_recursive1200': [block for block in expanded if not block['new_contained']],
        'rst_heading_markers': rst_markers,
        'rst_false_protected_split_chunks': split_chunks,
        'rst_interpretation': 'Four RST underline lines match the Markdown fence pattern; all ten stored protected_block_split chunks occur in the three affected RST sources. These flags must not be used as real code-splitting quality or improvement evidence.',
        'source_character_coverage': all_coverage,
    }
    standard, expanded_summary = (scopes[name]['summary'] for name in scopes)
    if (standard['blocks'], standard['old_contained'], standard['new_contained']) != (21, 21, 21):
        raise ValueError('Standard inventory differs from the reported frozen R3 audit')
    if (expanded_summary['blocks'], expanded_summary['old_contained'], expanded_summary['new_contained'],
            expanded_summary['gain'], expanded_summary['tie'], expanded_summary['loss']) != (47, 41, 43, 5, 39, 3):
        raise ValueError('Expanded inventory differs from the reported frozen R3 audit')
    if len(rst_markers) != 4 or len(split_chunks) != 10 or any(not row['source_id'].endswith('.rst') for row in split_chunks):
        raise ValueError('RST diagnostics differ from the reported frozen R3 audit')
    if any(value['missing_nonwhitespace_characters'] for corpus in all_coverage.values() for value in corpus.values()):
        raise ValueError('Non-whitespace source character coverage differs from the reported audit')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run, output = args.run.resolve(), args.output.resolve()
    if output.is_relative_to(run):
        parser.error('Audit output must be outside the frozen run directory')
    result = audit(run)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'scopes': {name: value['summary'] for name, value in result['scopes'].items()},
                      'losses': len(result['expanded_scope_losses']), 'rst_markers': len(result['rst_heading_markers']),
                      'frozen_artifact_hashes_verified': result['frozen_artifact_hashes_verified'], 'api_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
