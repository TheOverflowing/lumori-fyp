#!/usr/bin/env python3
"""Offline freeze of licensed source excerpts and AI-prepared DEV learning needs.

No API calls. Review fields must never be included in generation prompts.
"""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from pathlib import Path
from extract_paragraphs import ParagraphParser

PACK = Path(__file__).resolve().parent
ROOT = PACK.parents[1]
SOURCES = PACK / 'sources'

# Indices refer to nonempty h1-h4/p elements in the archived HTML, not pages.
DOCUMENTS = [
 ('os_context', 'operating_systems', 'xv6: CPU multiplexing and context switching', [('xv6-sched', [1,3,4,5,6,7,8,9,10,11,14,15])], 'xv6'),
 ('os_races', 'operating_systems', 'xv6: Races, critical sections, and atomic lock acquisition', [('xv6-lock', [1,4,6,10,11,12,13,14,15,17,19,20,21,22,23])], 'xv6'),
 ('os_interrupt_locks', 'operating_systems', 'xv6: Lock ordering and interrupts', [('xv6-lock', [33,34,35,36,39,40,41,42,43,44,45])], 'xv6'),
 ('os_wakeup', 'operating_systems', 'xv6: Condition synchronization and lost wakeups', [('xv6-sleep', [1,3,5,6,7,10,11,12,14,15,16,17,18,19])], 'xv6'),
 ('db_atomicity', 'databases', 'PostgreSQL 18: Transactions and atomicity', [('postgres-transactions', [0,1,3,4,5,6,7,8,11,12,13])], 'postgres'),
 ('db_read_committed', 'databases', 'PostgreSQL 18: Read Committed statement snapshots', [('postgres-isolation', [14,15,24,25])], 'postgres'),
 ('db_repeatable_read', 'databases', 'PostgreSQL 18: Repeatable Read and snapshot isolation', [('postgres-isolation', [26,27,28,29,30,31,32,33,34,35])], 'postgres'),
 ('db_retry', 'databases', 'PostgreSQL 18: Serializable transactions and retry handling', [('postgres-isolation', [38,39,45,48]), ('postgres-retry', [0,1,3,4,5])], 'postgres'),
 ('net_reliability', 'computer_networks', 'Computer Networks: A Systems Approach — Reliable transmission', [('network-reliable', [1,2,3,4,5,6,7,11])], 'systems_approach'),
 ('net_byte_stream', 'computer_networks', 'Computer Networks: A Systems Approach — TCP byte-stream service', [('network-tcp', [1,2,3,4,5,17,18,20,24])], 'systems_approach'),
 ('net_ack', 'computer_networks', 'Computer Networks: A Systems Approach — TCP sequence and acknowledgement numbers', [('network-tcp', [24,34,51,52,53,54,56,61,62,68])], 'systems_approach'),
 ('net_windows', 'computer_networks', 'Computer Networks: A Systems Approach — Flow and congestion control', [('network-tcp', [3,4,5,11,12,52,68,71,75]), ('network-congestion', [1,2,4,7,8,9])], 'systems_approach'),
]
ATTRIBUTION = {
 'xv6': {'authors':'Russ Cox, Frans Kaashoek, and Robert Morris; Massachusetts Institute of Technology', 'license':'MIT', 'license_file':'xv6-license.txt', 'repository':'https://github.com/mit-pdos/xv6-riscv-book', 'license_revision':'2d689eee47087bea267914123b8b1172583cbb0e'},
 'postgres': {'authors':'The PostgreSQL Global Development Group', 'license':'PostgreSQL', 'license_file':'postgres-license.txt', 'repository':'https://github.com/postgres/postgres', 'license_revision':'ce2648b16ab8d18bd4fb4ac6fed5e260ac309f6d'},
 'systems_approach': {'authors':'Larry Peterson and Bruce Davie', 'copyright':'Elsevier, 2012', 'license':'CC-BY-4.0', 'license_file':'systems-approach-license.txt', 'repository':'https://github.com/SystemsApproach/book', 'license_revision':'5deec5e741e2b8c0bc44566108a24cb783c2c7de'},
}
# Need, source, level, format, EN objective, ZH objective, evidence anchors, review rubric.
NEEDS = [
 ('os_context_switch','os_context','easy','short_answer',
  'Explain what a context switch preserves and the role of the scheduler in xv6 CPU multiplexing.',
  '解释 xv6 的上下文切换需要保存什么，以及调度器在 CPU 复用中的作用。',
  ['it saves the switched-from thread’s CPU registers, and restores the previously-saved registers of the switched-to thread', 'a kernel thread gives up the CPU by context-switching to that CPU’s “scheduler thread,”'],
  ['Do not confuse a switch between kernel threads with saving an entire address space.', 'The explanation must identify saved/restored CPU registers and scheduling through the per-CPU scheduler.', 'Use the frozen xv6 description, not an unannounced alternative operating system.']),
 ('os_race_condition','os_races','medium','mcq',
  'Apply mutual exclusion to a short shared-data update scenario, distinguishing a critical section from an unsafe check-then-set lock.',
  '在一个简短的共享数据更新场景中应用互斥，区分临界区保护与不安全的先检查再设置锁。',
  ['The sequence of instructions between acquire and release is often called a critical section.', 'What we need is a way to make lines 25 and 26 execute as an atomic (indivisible) step.'],
  ['Provide the complete relevant interleaving or update operations, not omitted source-code line numbers.', 'Exactly one option must correctly identify or repair the race under the stated atomicity assumptions.', 'The reasoning must distinguish locking an invariant from only guarding an individual write.']),
 ('os_interrupt_deadlock','os_interrupt_locks','hard','short_answer',
  'Analyze and justify a synchronization design when a kernel thread and an interrupt handler share a spinlock, including local and multiprocessor effects.',
  '分析内核线程与中断处理程序共享自旋锁时的同步设计，并论证本 CPU 与多处理器情况下的影响。',
  ['only sys_pause can release it, but sys_pause will not continue running until clockintr returns.', 'Interrupts may still occur on other CPUs, so an interrupt’s acquire can wait for a thread to release a spinlock; just not on the same CPU.'],
  ['The scenario must state which CPU is interrupted and who owns the spinlock.', 'Reason through why the interrupted owner cannot release the lock while its same-CPU interrupt handler spins.', 'Disabling local interrupts does not replace mutual exclusion against other CPUs; preserve the role of atomic locks.', 'Difficulty requires linked reasoning about the deadlock and the limits of the proposed repair, not obscure terminology.']),
 ('os_lost_wakeup','os_wakeup','hard','mcq',
  'Evaluate a producer-consumer wait protocol for lost wakeups and condition rechecking using the supplied xv6 sleep_prepare/sleep/wakeup interface.',
  '使用资料中的 xv6 sleep_prepare/sleep/wakeup 接口，评价生产者与消费者等待协议的丢失唤醒风险及条件复查。',
  ['sleep_prepare(chan) must be called either before checking the condition, or before releasing the lock that protects the condition.', 'For this reason sleeping always occurs inside a loop that re-checks the condition'],
  ['Use the frozen sleep_prepare/sleep interface rather than silently substituting an older xv6 API.', 'Give enough scheduling and lock details for every candidate protocol to be evaluated.', 'The unique answer must both avoid the check-to-sleep gap and handle a wakeup that does not guarantee the condition remains true.', 'Reject explanations that hold the condition lock while sleeping and thereby prevent the producer from making progress.']),
 ('db_atomicity','db_atomicity','easy','mcq',
  'Recognize transaction atomicity and the effect of COMMIT versus ROLLBACK in a simple PostgreSQL transfer.',
  '识别简单 PostgreSQL 转账中的事务原子性，以及 COMMIT 和 ROLLBACK 的作用。',
  ['A transaction is said to be atomic: from the point of view of other transactions, it either happens completely or not at all.', 'we can issue the command ROLLBACK instead of COMMIT, and all our updates so far will be canceled.'],
  ['State the transaction boundary and whether COMMIT or ROLLBACK is reached.', 'Exactly one answer must preserve the all-or-nothing treatment of the transfer.', 'Do not present atomicity as a guarantee that every business rule or every concurrent invariant is automatically enforced.']),
 ('db_statement_snapshot','db_read_committed','medium','short_answer',
  'Trace what ordinary SELECT statements may observe under PostgreSQL Read Committed in a two-session schedule.',
  '在两个会话的执行顺序中，推演 PostgreSQL Read Committed 下普通 SELECT 可观察到的数据。',
  ['a SELECT query (without a FOR UPDATE/SHARE clause) sees only data committed before the query began', 'two successive SELECT commands can see different data, even though they are within a single transaction'],
  ['Supply initial values, each statement start, relevant commit times, and all modifications.', 'Use ordinary non-locking SELECT and explicitly identify the isolation level.', 'Each read must be evaluated against its statement snapshot while allowing the transaction to see its own earlier writes.', 'Do not incorrectly infer one fixed snapshot for the whole Read Committed transaction.']),
 ('db_transaction_snapshot','db_repeatable_read','medium','short_answer',
  'Trace consecutive reads under PostgreSQL Repeatable Read and distinguish snapshot stability from serializable execution.',
  '推演 PostgreSQL Repeatable Read 下的连续读取，并区分快照稳定与可序列化执行。',
  ['a query in a repeatable read transaction sees a snapshot as of the start of the first non-transaction-control statement', 'this view will not necessarily always be consistent with some serial (one at a time) execution of concurrent transactions'],
  ['State the first non-transaction-control statement and relevant other-session commits.', 'Do not substitute BEGIN time for the first snapshot-taking statement.', 'Explain that snapshot stability alone is not a proof of serializability.', 'Avoid attributing another DBMS Repeatable Read implementation to PostgreSQL.']),
 ('db_serialization_retry','db_retry','hard','mcq',
  'Evaluate an application retry design after a PostgreSQL serialization failure when reads determine later writes.',
  '当读取结果决定后续写入时，评价 PostgreSQL 序列化失败后的应用重试设计。',
  ['retry the complete transaction, including all logic that decides which SQL to issue and/or which values to use.', 'Transaction retry does not guarantee that the retried transaction will complete; multiple retries may be needed.'],
  ['Specify transaction boundaries and the read-dependent application decision; do not rely on hidden external side effects.', 'Exactly one option must correctly rerun both reads/decisions and writes rather than only the failed statement.', 'A valid explanation distinguishes correctness of retry scope from any guarantee of immediate or eventual completion.', 'Do not conflate all persistent constraint errors with retryable serialization failures.']),
 ('net_reliable_delivery','net_reliability','easy','mcq',
  'Recognize the roles of acknowledgement, timeout, and a sequence number in stop-and-wait reliable delivery.',
  '识别停止等待可靠传输中确认、超时和序号各自的作用。',
  ['After transmitting one frame, the sender waits for an acknowledgment before transmitting the next frame.', 'when the sender retransmits frame 0, the receiver can determine that it is seeing a second copy of frame 0'],
  ['Do not assume a lost ACK means the data frame was never delivered.', 'The unique answer must distinguish retransmission from duplicate suppression.', 'Keep scope to the supplied stop-and-wait model, not an unspecified TCP variant.']),
 ('net_tcp_service','net_byte_stream','easy','short_answer',
  'Describe the reliable, ordered, full-duplex byte-stream service that TCP offers applications and distinguish it from segment transmission.',
  '描述 TCP 向应用提供的可靠、有序、全双工字节流服务，并区分字节流服务与报文段传输。',
  ['TCP guarantees the reliable, in-order delivery of a stream of bytes.', 'TCP does not, itself, transmit individual bytes over the Internet.'],
  ['The answer must distinguish the application byte stream from buffered segment transfer.', 'Do not claim an application write has an inherently preserved message boundary at the receiving application.', 'Do not claim full duplex means one unidirectional byte stream alternates direction.']),
 ('net_cumulative_ack','net_ack','medium','mcq',
  'Apply TCP byte sequence numbers and cumulative acknowledgements to a short arrival sequence with a missing range.',
  '在存在缺失字节区间的简短到达序列中，应用 TCP 字节序号与累积确认规则。',
  ['the Acknowledgement field actually identifies the “next sequence number expected,” thereby implicitly acknowledging all earlier sequence numbers.', 'if data has arrived out of order, then NextByteExpected points to the start of the first gap in the data'],
  ['Provide the initial expected byte and lengths/ranges of all relevant arriving data segments.', 'State whether SYN/FIN, wraparound, delayed ACK, or SACK are in scope; avoid introducing them implicitly.', 'Cumulative ACK must stop at the first missing byte even if later bytes have arrived.', 'Check all arithmetic independently and ensure exactly one option is correct.']),
 ('net_flow_congestion','net_windows','hard','short_answer',
  'Compare receiver flow control and network congestion control, then justify the active sending constraint in contrasting TCP situations.',
  '比较接收端流量控制与网络拥塞控制，并在不同 TCP 场景中论证实际限制发送的约束。',
  ['Flow control involves preventing senders from over-running the capacity of receivers.', 'the maximum number of bytes of unacknowledged data allowed is now the minimum of the congestion window and the advertised window.'],
  ['Separate receiver buffer pressure from congestion along the network path.', 'If numeric windows are used, provide their units and outstanding unacknowledged data; distinguish total allowed in-flight bytes from additional send allowance.', 'A justified comparison must identify which constraint is active in each case and why changing the other limit alone may not help.', 'Do not infer that a large advertised receive window proves the path is uncongested.']),
]


def sha(data: bytes) -> str:
 return hashlib.sha256(data).hexdigest()


def build():
 manifest=json.loads((SOURCES/'download-manifest.json').read_text())
 downloads={Path(x['path']).name:x for x in manifest['files']}
 docs=[]
 for id_,course,title,selections,group in DOCUMENTS:
  attribution=ATTRIBUTION[group]
  parts=[]; extraction=[]
  for name,indices in selections:
   raw=SOURCES/(name+'.html'); expected=downloads[raw.name]
   if sha(raw.read_bytes())!=expected['sha256']:raise ValueError(f'Changed source: {raw.name}')
   parser=ParagraphParser();parser.feed(raw.read_text())
   parts.extend(parser.nodes[i]['text'] for i in indices)
   extraction.append({'path':str(raw.relative_to(ROOT)),'url':expected['url'],'sha256':expected['sha256'],'paragraph_indices':indices})
  text='\n\n'.join(parts)
  target=SOURCES/(id_+'.txt');target.write_text(text+'\n')
  docs.append({'id':id_,'course':course,'title':title,'language':'en','text':text,'text_sha256':sha(text.encode()),'path':str(target.relative_to(ROOT)),'url':extraction[0]['url'],'license':attribution['license'],'authors':attribution['authors'],'license_path':str((SOURCES/attribution['license_file']).relative_to(ROOT)), 'provenance':{'kind':'official_openly_licensed_text_excerpt','repository':attribution['repository'],'license_revision':attribution['license_revision'],'retrieved_at_utc':manifest['retrieved_at_utc'],'html_snapshots':extraction,'transformations':'Selected complete h1-h4/p text blocks; HTML entities decoded; inline text preserved; whitespace normalized. No figures, code blocks, tables, or displayed equations included. Gaps between selected paragraphs are intentional.','revision_note':'HTML publication snapshot is frozen by SHA-256; license_revision identifies the archived license revision only, not a claim that the live HTML was built from that exact commit.'}})
 byid={d['id']:d for d in docs};cases=[]
 for need,source,level,kind,en,zh,quotes,criteria in NEEDS:
  for language,topic in [('en',en),('zh',zh)]:
   cases.append({'id':f'{need}_{language}','need_id':need,'course':byid[source]['course'],'language':language,'difficulty':level,'question_type':kind,'topic':topic,'learner_profile':('Undergraduate computer science student who has studied the supplied course material and introductory concepts; no unstated implementation-specific knowledge is assumed.' if language=='en' else '已学习所给课程资料和入门概念的计算机专业本科生；不假定题目未说明的特定实现知识。'),'source_ids':[source],'expected_evidence':[{'source_id':source,'quote':q} for q in quotes],'review_criteria':criteria,'grading_expectations':{'reviewer_type':'AI_prepared_provisional','human_validated':False,'difficulty_label_status':'requested_target_not_empirical_student_difficulty','format':kind,'core_topic':need,'must_meet_all_criteria':True},'split':'dev','pilot':True})
 dataset={'version':'quality-latency-v1','dataset_id':'q1_undergraduate_cs_bilingual_dev_v1','created_at':'2026-09-22','label_status':'ai_prepared_pending_independent_review','purpose':'Paired bilingual 24-task DEV pilot for real RAG assessment generation quality and latency; not an unseen holdout or human-labeled benchmark.','generation_field_allowlist':['course','language','difficulty','question_type','topic','learner_profile'],'review_only_fields':['source_ids','expected_evidence','review_criteria','grading_expectations'],'source_language_scope':'English original course/documentation excerpts shared by each EN/ZH need pair; evaluates EN/EN and ZH/EN input/source settings, not Chinese original material parsing or EN/ZH retrieval.','source_documents':docs,'cases':cases}
 validate(dataset)
 path=PACK/'dataset.json';path.write_text(json.dumps(dataset,ensure_ascii=False,indent=2)+'\n')
 files=[path,SOURCES/'download-manifest.json',PACK/'build_dataset.py',PACK/'extract_paragraphs.py']+[SOURCES/a['license_file'] for a in ATTRIBUTION.values()]+[SOURCES/(d['id']+'.txt') for d in docs]+[ROOT/d['path'] for d in manifest['files']]
 frozen={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in dict.fromkeys(files)}
 (PACK/'manifest.json').write_text(json.dumps({'version':'quality-latency-manifest-v1','dataset_sha256':sha(path.read_bytes()),'counts':{'cases':len(cases),'needs':len(NEEDS),'source_documents':len(docs),'course':dict(Counter(c['course'] for c in cases)),'difficulty':dict(Counter(c['difficulty'] for c in cases)),'question_type':dict(Counter(c['question_type'] for c in cases)),'language':dict(Counter(c['language'] for c in cases))},'files':frozen},indent=2)+'\n')
 return dataset


def validate(d):
 assert len(d['cases'])==24 and len({c['id'] for c in d['cases']})==24
 assert len({c['need_id'] for c in d['cases']})==12
 assert Counter(c['difficulty'] for c in d['cases'])=={'easy':8,'medium':8,'hard':8}
 assert Counter(c['question_type'] for c in d['cases'])=={'mcq':12,'short_answer':12}
 assert Counter(c['language'] for c in d['cases'])=={'en':12,'zh':12}
 byid={x['id']:x for x in d['source_documents']}
 for c in d['cases']:
  assert c['split']=='dev' and not c['grading_expectations']['human_validated']
  assert set(c['source_ids'])<=byid.keys()
  for q in c['expected_evidence']:
   assert q['quote'] in byid[q['source_id']]['text'],(c['id'],q['quote'])
   assert byid[q['source_id']]['course']==c['course']
 for need in {c['need_id'] for c in d['cases']}:
  pair=[c for c in d['cases'] if c['need_id']==need]
  assert {x['language'] for x in pair}=={'en','zh'}
  for key in ['course','difficulty','question_type','source_ids','expected_evidence','review_criteria']:
   assert pair[0][key]==pair[1][key],(need,key)
 for doc in d['source_documents']:
  assert sha(doc['text'].encode())==doc['text_sha256']

if __name__=='__main__':
 d=build();print(json.dumps({'path':str(PACK/'dataset.json'),'cases':len(d['cases']),'sources':len(d['source_documents']),'label_status':d['label_status']}))
