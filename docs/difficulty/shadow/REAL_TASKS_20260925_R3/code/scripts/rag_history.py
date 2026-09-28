"""Rebuild a chronological RAG experiment index without changing frozen runs."""
import csv
import json
from pathlib import Path


def refresh_history(directory):
    directory = Path(directory)
    rows = []
    for path in sorted(directory.glob('*/manifest.json')):
        manifest = json.loads(path.read_text())
        base = {key: manifest.get(key) for key in ('run_id', 'status', 'started_at', 'finished_at',
                 'dataset_sha256', 'label_status', 'embedding_model', 'embedding_cache_sha256',
                 'cache_replay', 'new_api_attempts')}
        result_path = path.parent / 'metrics.json'
        if not result_path.exists():
            rows.append(base)
            continue
        for strategy, result in json.loads(result_path.read_text()).items():
            for split, summary in result['metrics']['groups']['split'].items():
                rows.append(base | {'strategy': strategy, 'split': split,
                    'answerable_queries': summary['denominators']['answerable_queries'],
                    'missing_rankings': summary['denominators']['missing_rankings'],
                    'recall_at_5': summary['answerable_metrics']['recall@5'],
                    'all_evidence_at_5': summary['answerable_metrics']['all_evidence@5'],
                    'ndcg_at_5': summary['answerable_metrics']['ndcg@5']})
    fields = ['run_id', 'status', 'started_at', 'finished_at', 'strategy', 'split', 'label_status',
              'answerable_queries', 'missing_rankings', 'recall_at_5', 'all_evidence_at_5', 'ndcg_at_5',
              'new_api_attempts', 'cache_replay', 'embedding_model', 'dataset_sha256', 'embedding_cache_sha256']
    with (directory / 'experiment-history.csv').open('w', newline='', encoding='utf-8-sig') as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return rows


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    print(f'Indexed {len(refresh_history(parser.parse_args().directory))} rows.')
