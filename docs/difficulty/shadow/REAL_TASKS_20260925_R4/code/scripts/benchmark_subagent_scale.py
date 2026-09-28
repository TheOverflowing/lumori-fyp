"""Isolated real multi-question runs at selected per-question concurrency caps.

Uses frozen, openly licensed undergraduate CS excerpts already archived for
the quality/latency pilot. Internal gate passes are recorded, not relabelled as
independent answer correctness or human review.
"""
import argparse
import asyncio
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings  # noqa: E402
from app.generation_agent import GenerationAgent, fingerprint  # noqa: E402
from app.assessment_contracts import FLEXIBLE_PLANNER_REVISION, validate_flexible_plan  # noqa: E402
from app.question_planning import normalized_brief_key  # noqa: E402
from app import job_progress  # noqa: E402
from app.models import GenerateRequest  # noqa: E402
from app.pipeline import Pipeline  # noqa: E402
from app.providers import ApiProviders  # noqa: E402
from app.store import Store, now  # noqa: E402

DATASET = ROOT / 'benchmarks/quality_latency_v1/dataset.json'
SELECTED_IDS = ('os_context', 'os_races', 'os_interrupt_locks', 'os_wakeup',
    'db_atomicity', 'db_read_committed', 'db_repeatable_read', 'db_retry',
    'net_reliability', 'net_byte_stream', 'net_ack', 'net_windows')

# The same assistant-authored, mechanically checked brief for each slot in
# every condition. This isolates worker dispatch from stochastic planning.
FOCI = {
    'os_context': ('voluntary versus timer-driven process switches', 'saved CPU registers during a context switch',
        'the scheduler thread between two process threads', 'the role of timer interrupts in CPU sharing'),
    'os_races': ('a concurrent read/write race', 'mutual exclusion for shared kernel data',
        'a critical section and its invariant', 'why a plain check-then-set lock is unsafe'),
    'os_interrupt_locks': ('a spinlock shared with an interrupt handler', 'local interrupt handling while holding a lock',
        'the purpose of a spinlock', 'interrupt-related lock ordering'),
    'os_wakeup': ('a lost-wakeup risk', 'the condition checked before sleeping',
        'the role of wakeup in producer-consumer coordination', 'why a condition is rechecked after waking'),
    'db_atomicity': ('transaction atomicity', 'the effect of COMMIT',
        'the effect of ROLLBACK', 'a two-step transfer as one transaction'),
    'db_read_committed': ('the per-statement Read Committed snapshot', 'visibility of a concurrent committed update',
        'two SELECT statements in one Read Committed transaction', 'the start of a Read Committed snapshot'),
    'db_repeatable_read': ('the Repeatable Read transaction snapshot', 'visibility of later committed changes',
        'consistent repeated reads', 'a concurrent update conflict'),
    'db_retry': ('a serialization failure', 'a complete transaction retry',
        'why retrying only one statement is insufficient', 'retrying after a transaction abort'),
    'net_reliability': ('retransmission after missing acknowledgment', 'duplicate packet handling',
        'reliable ordered delivery', 'a sender timeout'),
    'net_byte_stream': ('TCP as a byte stream', 'byte sequence numbers',
        'ordered byte delivery', 'the absence of application message boundaries'),
    'net_ack': ('the next-byte meaning of an acknowledgment', 'the SYN and ACK handshake',
        'acknowledgment of the starting sequence number', 'the retransmission timer during setup'),
    'net_windows': ('receiver-advertised flow control', 'buffer space and advertised window',
        'the limit on unacknowledged bytes', 'what a zero advertised window signals'),
}


def fixed_briefs(count, slots, source_ids):
    ordered = [(document_id, FOCI[document_id][index])
        for index in range(4) for document_id in SELECTED_IDS]
    briefs = []
    for slot, (document_id, focus) in zip(slots, ordered[:count]):
        source_id = 'scale-' + document_id
        briefs.append({'slot_id': slot['slot_id'], 'difficulty': slot['difficulty'],
            'kind': 'short_answer', 'focus': focus,
            'learning_goal': 'Explain ' + focus + ' using the assigned course excerpt.',
            'requirements': [{'id': 'r1', 'kind': 'knowledge',
                'description': 'Explain ' + focus + ' accurately from the assigned excerpt.',
                'source_ids': [source_id]}],
            'source_ids': [source_id], 'answer_policy': 'single_outcome'})
    seen = set()
    for offset in range(0, count, 5):
        group = briefs[offset:offset + 5]
        validate_flexible_plan({'questions': group}, slots[offset:offset + 5],
            'short_answer', source_ids)
        for brief in group:
            key = normalized_brief_key(brief['focus'], brief['learning_goal'])
            if key in seen:
                raise ValueError('Duplicate fixed brief')
            seen.add(key)
    return briefs


async def install_fixed_plan(agent):
    slots = agent.state['slots']
    briefs = fixed_briefs(len(slots), slots, {source['id'] for source in agent.evidence['sources']})
    supervisor = agent.state.setdefault('supervisor', {'revision': FLEXIBLE_PLANNER_REVISION,
        'status': 'planning', 'batches': [], 'dispatch': 'bounded_parallel_workers_v1'})
    supervisor['plan_origin'] = 'assistant_authored_frozen_benchmark_fixture'
    supervisor['batches'] = []
    for offset in range(0, len(slots), 5):
        group = briefs[offset:offset + 5]
        supervisor['batches'].append({'number': offset // 5 + 1,
            'status': 'validated_fixture', 'briefs_sha256': fingerprint(group)})
    for slot, brief in zip(slots, briefs):
        slot['brief'] = brief
        slot['worker'] = {'id': f'{agent.job_id}:{slot["slot_id"]}',
            'status': 'pending', 'brief_sha256': fingerprint(brief),
            'source_ids': brief['source_ids'], 'context_policy': 'fresh_role_sessions',
            'dispatch_count': 0}
    supervisor.update(status='planned', question_count=len(briefs),
        plan_sha256=fingerprint(briefs))
    job_progress.event(agent.store, agent.job_id, 'planning', 'plan_ready', total=len(briefs))
    agent.save()


def frozen_sources():
    dataset = json.loads(DATASET.read_text(encoding='utf-8'))
    documents = {document['id']: document for document in dataset['source_documents']}
    sources, manifest = [], []
    for document_id in SELECTED_IDS:
        document = documents[document_id]
        paragraphs = document['text'].split('\n\n')
        excerpt = ''
        for paragraph in paragraphs:
            next_excerpt = (excerpt + '\n\n' + paragraph).strip()
            if len(next_excerpt) > 1500:
                break
            excerpt = next_excerpt
        if len(excerpt) < 250:
            excerpt = document['text'][:1500]
            cut = max(excerpt.rfind('. '), excerpt.rfind('。'))
            if cut > 250:
                excerpt = excerpt[:cut + 1]
        if not excerpt:
            raise ValueError(f'Empty frozen excerpt for {document_id}')
        source_id = 'scale-' + document_id
        digest = hashlib.sha256(excerpt.encode()).hexdigest()
        sources.append({'id': source_id, 'document_id': 'scale-document-' + document_id,
            'document_name': document['title'], 'page': 1, 'text': excerpt,
            'metadata': {'source_kind': 'text', 'extraction_method': 'frozen_official_course_excerpt',
                'extraction_status': 'ready', 'extraction_warnings': []}})
        manifest.append({'id': source_id, 'title': document['title'],
            'course': document['course'], 'url': document['url'],
            'license': document['license'], 'text_sha256': digest,
            'excerpt_chars': len(excerpt), 'source_dataset_id': document_id})
    return sources, manifest


async def one(count, limit, repeat, root, sources, plan_mode, continue_after_failure):
    settings = Settings.from_env()
    settings.data_dir = root / f'q{count}-c{limit}-r{repeat}'
    settings.generation_workflow = 'agent_v1'
    settings.agent_runtime = 'native'
    settings.agent_orchestration = 'sequential_v1'
    settings.agent_max_parallel_questions = limit
    settings.agent_plan_batch_size = 5
    settings.agent_max_calls = min(300, count * 6 + 20)
    settings.max_daily_calls = 500
    store = Store(settings.data_dir)
    store.execute('INSERT INTO courses VALUES(?,?,?)', ('scale-course', 'Undergraduate CS scale test', now()))
    provider = ApiProviders(settings, store)
    pipeline = Pipeline(settings, store, provider, enforce_account_ownership=False)

    async def retrieve(request, job_id, *, with_trace=False):
        assert with_trace
        return sources, {'configuration': {'strategy': 'frozen_archived_cs_excerpts'},
            'selected_count': len(sources)}

    pipeline.retrieve = retrieve
    request = GenerateRequest(course_id='scale-course',
        topic=('Create distinct, concise undergraduate practice questions grounded in the supplied '
               'operating systems, database transaction, and computer networking excerpts. Cover different '
               'concepts across the set; avoid relying on facts absent from the learner-facing question.'),
        material='quiz', difficulty='easy', count=count, language='en',
        learner_profile='Undergraduate computer science students who have read the supplied excerpts',
        question_type='short_answer', include_explanations=False,
        use_subagents=True, request_key=f'scale-q{count}-c{limit}-r{repeat}')
    job, _ = store.job(request.request_key, 'generate', request.model_dump())
    original = provider.generate
    active = peak = 0

    async def observed(messages, job_id):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            return await original(messages, job_id)
        finally:
            active -= 1

    provider.generate = observed
    started = time.perf_counter()
    original_plan = GenerationAgent.plan_questions
    original_continue = getattr(GenerationAgent, 'continue_after_worker_failure', False)
    GenerationAgent.continue_after_worker_failure = continue_after_failure
    if plan_mode == 'frozen':
        GenerationAgent.plan_questions = install_fixed_plan
    try:
        await pipeline.run(job['id'])
    finally:
        GenerationAgent.plan_questions = original_plan
        GenerationAgent.continue_after_worker_failure = original_continue
        await provider.close()
    elapsed = round(time.perf_counter() - started, 2)
    final = store.one('SELECT status FROM jobs WHERE id=?', (job['id'],))
    evidence_row = store.one('SELECT evidence FROM job_evidence WHERE job_id=?', (job['id'],))
    evidence = json.loads(evidence_row['evidence']) if evidence_row else {}
    agent = evidence.get('agent', {})
    calls = store.all('SELECT capability,status,duration_ms,usage,http_status FROM calls WHERE job_id=?', (job['id'],))
    text_calls = [call for call in calls if call['capability'] == 'text']
    usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    for call in text_calls:
        item = json.loads(call['usage'] or '{}')
        for key in usage:
            usage[key] += item.get(key, 0) if isinstance(item.get(key, 0), int) else 0
    slots = agent.get('slots', [])
    slot_rows = []
    for slot in slots:
        question = slot.get('accepted_asset', {}).get('questions', [None])[0]
        slot_rows.append({'slot_id': slot['slot_id'], 'status': slot.get('status'),
            'difficulty': slot.get('difficulty'),
            'brief_focus': slot.get('brief', {}).get('focus'),
            'attempt_count': len(slot.get('attempts', [])),
            'failed_gate_codes': sorted({issue for attempt in slot.get('attempts', [])
                for issue in attempt.get('feedback', {}).get('issues', [])}),
            'question': question})
    return {'question_count': count, 'parallel_limit': limit, 'repeat': repeat,
        'plan_mode': plan_mode, 'continue_after_failure': continue_after_failure,
        'status': final['status'], 'agent_status': agent.get('status'),
        'elapsed_seconds': elapsed, 'peak_model_calls_in_flight': peak,
        'text_calls': len(text_calls),
        'successful_text_calls': sum(c['status'] == 'succeeded' for c in text_calls),
        'http_statuses': [c['http_status'] for c in text_calls if c['http_status'] and c['http_status'] != 200],
        'median_text_call_ms': round(statistics.median(c['duration_ms'] for c in text_calls), 1)
            if text_calls else None,
        'usage': usage, 'passed_questions': sum(s['status'] == 'passed' for s in slot_rows),
        'published': bool(store.one('SELECT id FROM contents WHERE job_id=?', (job['id'],))),
        'slots': slot_rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, required=True)
    parser.add_argument('--limits', type=str, required=True)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--plan-mode', choices=('model', 'frozen'), default='frozen')
    parser.add_argument('--continue-after-failure', action='store_true',
        help='Research-only full exposure of every slot; production stops dispatch after a failure.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        limits = tuple(int(value) for value in args.limits.split(','))
    except ValueError:
        parser.error('limits must be comma-separated integers')
    if (not 1 <= args.count <= 50 or not 1 <= args.repeats <= 3 or not limits or
            len(set(limits)) != len(limits) or any(not 1 <= n <= min(40, args.count) for n in limits)):
        parser.error('count 1..50, repeats 1..3, unique limits 1..min(40,count)')
    settings = Settings.from_env()
    if not settings.text.configured:
        raise SystemExit('Text model is not configured; no calls started.')
    sources, manifest = frozen_sources()
    record = {'type': 'live_multi_question_scale', 'model': settings.text.model,
        'date': now(), 'source_dataset': str(DATASET.relative_to(ROOT)),
        'source_manifest': manifest, 'plan_mode': args.plan_mode,
        'continue_after_failure': args.continue_after_failure,
        'interpretation_boundary': ('One or more stochastic model runs; internal gate pass is not independent '
            'correctness, human review, empirical difficulty, or student outcome.'),
        'results': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lumori-subagent-scale-') as temp:
        for repeat in range(1, args.repeats + 1):
            order = limits if repeat % 2 else tuple(reversed(limits))
            for limit in order:
                result = asyncio.run(one(args.count, limit, repeat, Path(temp), sources,
                    args.plan_mode, args.continue_after_failure))
                record['results'].append(result)
                args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                print(json.dumps({key: value for key, value in result.items() if key != 'slots'},
                    ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
