"""Fetch a pinned, small, independently annotated OmniDocBench research pilot.

Run with the bundled Python (Pillow/reportlab) or an environment providing them.
No LLM labels, cloud OCR calls, production uploads or RAG archives are involved.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'docs/parsing/benchmarks/omnidocbench-pilot-v1'
REVISION = 'aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec'
PDF_REVISION = 'f15134380fc1835bbb9eff38883023f79a54bc06'
ANNOTATION_SHA256 = 'a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496'
BASE = 'https://huggingface.co/datasets/opendatalab/OmniDocBench/resolve/'
TEXT_CATEGORIES = {'text_block', 'title', 'header', 'footer', 'page_number',
                   'reference', 'page_footnote', 'figure_caption', 'table_caption',
                   'figure_footnote', 'table_footnote', 'equation_caption', 'code_txt'}
ALLOWED_SOURCES = {'academic_literature', 'book', 'colorful_textbook', 'exam_paper'}


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def download(url, path, expected=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urlopen(url, timeout=120) as response:
            raw = response.read(100_000_001)
        if len(raw) > 100_000_000:
            raise ValueError('Refusing an unexpectedly large benchmark file.')
        if expected and sha256(raw) != expected:
            raise ValueError('Upstream checksum mismatch.')
        path.write_bytes(raw)
    raw = path.read_bytes()
    if expected and sha256(raw) != expected:
        raise ValueError('Cached checksum mismatch.')
    return {'url': url, 'sha256': sha256(raw), 'bytes': len(raw)}


def reference_text(page):
    blocks = [b for b in page['layout_dets']
              if b['category_type'] in TEXT_CATEGORIES and not b.get('ignore', False)
              and b.get('text')]
    # Published reading-order annotations, never parser-generated order or labels.
    return '\n'.join(b['text'] for b in sorted(blocks,
                    key=lambda b: (b.get('order') is None, b.get('order') or 0)))


def choose_pages(data, original_names):
    candidates = []
    for page in data:
        info = page['page_info']
        attrs = info['page_attribute']
        if (Path(info['image_path']).stem not in original_names
                or attrs['data_source'] not in ALLOWED_SOURCES
                or attrs['language'] not in ('english', 'simplified_chinese')):
            continue
        if any('mask' in b['category_type'] or b.get('ignore') for b in page['layout_dets']):
            continue
        if len(''.join(reference_text(page).split())) < 200:
            continue
        candidates.append(page)
    # Hash ordering avoids choosing examples after observing parser scores.
    candidates.sort(key=lambda p: sha256(p['page_info']['image_path'].encode()))
    selected, used = [], set()
    for language in ('english', 'simplified_chinese'):
        for stratum, count in [('prose', 3), ('table', 1), ('formula', 1), ('figure', 1)]:
            matched = []
            for page in candidates:
                name = page['page_info']['image_path']
                if name in used or page['page_info']['page_attribute']['language'] != language:
                    continue
                cats = {b['category_type'] for b in page['layout_dets']}
                if stratum == 'prose':
                    qualifies = not cats.intersection({'table', 'figure', 'equation_isolated'})
                    qualifies = qualifies and '$' not in reference_text(page) and '\\' not in reference_text(page)
                else:
                    qualifies = {'formula': 'equation_isolated'}.get(stratum, stratum) in cats
                if qualifies:
                    matched.append(page)
                    used.add(name)
                    if len(matched) == count:
                        break
            if len(matched) != count:
                raise ValueError(f'Insufficient candidates for {language}/{stratum}.')
            selected.extend((stratum, p) for p in matched)
    return selected


def prepare(destination=DEFAULT):
    from PIL import Image
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.utils import ImageReader

    destination = Path(destination)
    annotation_path = destination / 'upstream-OmniDocBench.json'
    annotation_source = download(BASE + REVISION + '/OmniDocBench.json', annotation_path, ANNOTATION_SHA256)
    terms = download(BASE + REVISION + '/README.md', destination / 'upstream-README.md')
    tree_path = destination / 'upstream-old-tree.json'
    tree_source = download('https://huggingface.co/api/datasets/opendatalab/OmniDocBench/revision/'
                           + PDF_REVISION, tree_path)
    original_names = {Path(x['rfilename']).stem for x in json.loads(tree_path.read_text())['siblings']
                      if x['rfilename'].startswith('ori_pdfs/')}
    selected = choose_pages(json.loads(annotation_path.read_text()), original_names)
    manifest = {
        'schema_version': 'document-parsing-pilot-v1',
        'source': 'OpenDataLab/OmniDocBench', 'annotation_revision': REVISION,
        'original_pdf_revision': PDF_REVISION, 'annotation_index': annotation_source,
        'dataset_terms': terms, 'original_pdf_tree': tree_source,
        'usage_terms': 'Upstream dataset copyright statement: research purposes only, not commercial use. '
                       'No blanket Apache/CC license for source documents is assumed.',
        'annotation_provenance': 'Released OmniDocBench annotations; upstream manual annotation and '
            'expert quality review process. No labels were generated or corrected by this project.',
        'selection': 'Intersect pinned image/annotation page IDs with pinned original PDFs; '
            'English and simplified Chinese; academic_literature/book/colorful_textbook/exam_paper; '
            'no ignore or mask regions; >=200 reference non-whitespace characters; ascending SHA256(filename). '
            'Per language choose 3 plain prose pages without table/figure/display equation/LaTeX text, '
            'then 1 table, 1 display equation, 1 figure page, without reuse. Fixed before scoring.',
        'variants': {
            'native_pdf': 'Official original PDF at older pinned revision, exact page ID matched; '
                'not guaranteed born-digital. Original vs benchmark masks/rendering may differ.',
            'page_image': 'Unmodified official benchmark page image; not a claim of camera-photo provenance.',
            'image_only_pdf': 'Controlled variant: same official image embedded once in a PDF, without text layer.',
            'degraded_image': 'Controlled variant: RGB, 65% dimensions Lanczos; +2 degree rotation, '
                'expand white canvas, bicubic; JPEG quality55. Simulates some degradation, not a real photo.'},
        'metric_contract': {
            'text_accuracy_scope': 'prose stratum only, to avoid confusing table HTML/formula LaTeX with text OCR errors',
            'cer': 'Levenshtein(NFKC(text) with whitespace removed) / normalized GT character count; '
                'case and punctuation preserved, raw CER may exceed 1; empty/error prediction has CER=1.',
            'wer': 'English prose only; NFKC then Unicode word-or-punctuation tokens, case preserved.',
            'usable_page': 'Custom pilot rule fixed before scores: CER<=0.10 and prediction length >=0.80*GT length. '
                'Includes all prose failures in denominator; not an industry standard or a semantic correctness guarantee.',
            'structure': 'Table/figure/formula gold regions preserved; TEDS, CDM, region recall and image semantic '
                'accuracy are NOT computed by this pilot.',
            'aggregation': 'Equal-weight macro CER and edit-sum/GT-character-sum micro CER; '
                'language and source-page counts reported. Variants are paired observations, not independent new documents.'},
        'samples': []}
    for index, (stratum, page) in enumerate(selected, 1):
        info = page['page_info']
        sample_id = f'p{index:02d}'
        prefix = destination / 'samples' / sample_id
        prefix.mkdir(parents=True, exist_ok=True)
        name = info['image_path']
        image_path = prefix / ('page' + Path(name).suffix)
        image_source = download(BASE + REVISION + '/images/' + quote(name, safe=''), image_path)
        pdf_path = prefix / 'native.pdf'
        pdf_source = download(BASE + PDF_REVISION + '/ori_pdfs/'
                              + quote(Path(name).stem + '.pdf', safe=''), pdf_path)
        (prefix / 'annotation.json').write_text(json.dumps(page, ensure_ascii=False, indent=2) + '\n')
        (prefix / 'reference.txt').write_text(reference_text(page) + '\n')
        image = Image.open(image_path).convert('RGB')
        scan_path = prefix / 'image-only.pdf'
        canvas = Canvas(str(scan_path), pagesize=(image.width * 72 / 200, image.height * 72 / 200), invariant=1)
        canvas.drawImage(ImageReader(image), 0, 0, width=image.width * 72 / 200,
                         height=image.height * 72 / 200)
        canvas.showPage()
        canvas.save()
        damaged = image.resize((round(image.width * .65), round(image.height * .65)), Image.Resampling.LANCZOS)
        damaged = damaged.rotate(2, Image.Resampling.BICUBIC, expand=True, fillcolor='white')
        degraded_path = prefix / 'degraded.jpg'
        damaged.save(degraded_path, quality=55, optimize=False)
        files = {variant: {'path': str(path.relative_to(destination)), 'sha256': sha256(path.read_bytes()),
                           'bytes': path.stat().st_size}
                 for variant, path in [('native_pdf', pdf_path), ('page_image', image_path),
                                       ('image_only_pdf', scan_path), ('degraded_image', degraded_path)]}
        manifest['samples'].append({
            'id': sample_id, 'stratum': stratum, 'cer_eligible': stratum == 'prose',
            'language': info['page_attribute']['language'], 'page_attributes': info['page_attribute'],
            'source_page_id': name, 'image_source': image_source, 'pdf_source': pdf_source,
            'annotation': str((prefix / 'annotation.json').relative_to(destination)),
            'annotation_sha256': sha256((prefix / 'annotation.json').read_bytes()),
            'reference': str((prefix / 'reference.txt').relative_to(destination)),
            'reference_sha256': sha256((prefix / 'reference.txt').read_bytes()),
            'category_counts': {c: sum(b['category_type'] == c for b in page['layout_dets'])
                                for c in sorted({b['category_type'] for b in page['layout_dets']})},
            'files': files})
        print(f'{sample_id}: {info["page_attribute"]["language"]} / {stratum}', flush=True)
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT)
    arguments = parser.parse_args()
    prepare(arguments.output)
