"""Materialize the assistant's retrospective review without altering original evidence."""
from pathlib import Path
import csv, hashlib, json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/thesis/review'
FILES={
'L':'docs/ca1/evidence/live-20260912T040126795872Z/lesson-draft-v1.json',
'A':'docs/ca1/evidence/live-20260912T040126795872Z/assignment-draft-v1.json',
'Q':'docs/ca1/evidence/live-20260912T040126795872Z/quiz-draft-v1.json',
'H':'docs/ca1/evidence/difficulty-20260912T042551358609Z/all_hard-draft.json',
'M':'docs/ca1/evidence/difficulty-20260912T042551358609Z/mixed-draft.json'}
# Assessments were made by reading the archived text and cited source snapshots.
NOTES={
'L-S1':('supported','Directly supported ingestion, metadata and embedding description. Overlap is described as a possible trade-off, not as the current deployed default.','No factual revision identified; frame this as historical teaching material.'),
'L-S2':('supported','The cited passage states query embedding, similarity ranking and the distinction between retrieval and parameter updates.','No factual revision identified.'),
'L-S3':('supported','The eight-passage example and warning about uncalibrated similarity are directly supported.','No factual revision identified.'),
'L-S4':('supported','The refusal example and equal-dimension compatibility limitation are present in the cited excerpts.','No factual revision identified.'),
'L-S5':('supported','The cited source explicitly separates reindexing from generated-text revision and approval.','No factual revision identified.'),
'A-S1':('supported','The two cited excerpts support embedding signatures and version-bound approval, including the credential-change distinction.','No factual revision identified.'),
'A-S2':('supported','The quoted source directly supports immutable earlier evidence and renewed review after editing.','No factual revision identified.'),
'A-Q1':('supported','The reference answer distinguishes re-embedding source passages from resetting approval after a content edit. The multi-part scenario is answerable from the cited excerpts.','For stronger discrimination, supply a concrete before/after state and require the learner to order the changes. Intended demand: medium to hard, not empirically calibrated.'),
'Q-S1':('supported','The source explicitly distinguishes citation identifier membership from semantic support.','No factual revision identified.'),
'Q-Q1':('supported','The answer follows the source and identifies the unsupported inference correctly. The example is almost identical to the source, limiting evidence of transfer.','Use a new source-supported example if the target is application rather than rehearsal. Intended demand: easy to medium.'),
'H-S1':('revise','The refusal and non-human-approval statements are supported, but the sentence about retrieval supplying evidence is not directly established by the listed excerpts.','Attach the actual ingestion/retrieval passage to this section, rather than relying on unstated course context.'),
'H-S2':('revise','Equal dimensions not guaranteeing the same semantic space is directly supported. The index-rebuild instruction is an engineering inference from that passage.','Add the explicit embedding-signature/reindexing passage and distinguish the inference from directly quoted requirements.'),
'H-S3':('revise','The export and credential statements are supported. The claim about absent authenticated roles appears in e9cd2063..., not in this section\'s two cited excerpts; it is also historical.','Add the appropriate historical excerpt and date the example. Do not describe the current authenticated application as lacking accounts.'),
'H-Q1':('revise','The distinction between identifier checks and approval is reasonable. The proposed remedies mainly create ratings and logs; they do not explicitly repair an irrelevant citation or unsupported conclusion.','Require semantic comparison against the source, correction or withdrawal of the unsupported answer, and only then a recorded review. Intended demand: medium to hard.'),
'H-Q2':('revise','The compatibility reasoning is sound, but updating review records is underspecified and could be read as overwriting historical approval. The retrieved evidence does not fully state the review state transition.','Specify a new draft revision, retain the old review unchanged, and require approval of the new version; add the versioning excerpt. Intended demand: hard if the state-transition constraints are explicit.'),
'H-Q3':('revise','The historical role limitation is supported by e9cd2063.... However, retrieved passages and configuration signatures are not inherently secrets, and their automatic exclusion from all student handouts is not established by the source.','Separate pedagogical relevance and source permissions from credential secrecy. Keep justified citations; identify the old prototype as a dated scenario. Intended demand: hard as a constrained design task.'),
'M-S1':('revise','The listed excerpts support non-human-approval and insufficient-evidence statements, but do not explicitly provide the retrieval mechanism or the full identifier-versus-support distinction.','Cite the retrieval and citation-support passages themselves; a correct general claim still needs the appropriate source.'),
'M-S2':('revise','Changing embedding models can require new source vectors. The added suggestion that related course materials need review is not tied to an actual content edit and is not supported by the cited compatibility excerpt.','State that reindexing alone does not invalidate an existing text approval; a subsequent edit creates a separate review requirement.'),
'M-S3':('supported','The listed excerpts support draft/approved export labels, preserved revisions, excluded credentials and separate operational failures.','No factual revision identified.'),
'M-S4':('supported','The cognitive-demand definitions and absence of learner calibration are directly supported by the cited source.','No factual revision identified.'),
'M-Q1':('revise','The answer is conceptually reasonable, but the two cited excerpts do not explicitly answer what retrieval supplies or fully justify the citation-support distinction.','Add the missing source excerpts and either simplify to one direct relationship or retain it as a compound comprehension item. Intended demand: easy to medium.'),
'M-Q2':('supported','The same-dimensional semantic-space mismatch is directly supported; re-embedding affected documents is a reasonable engineering inference.','Label reindexing as the inferred action or cite the explicit signature/rebuild passage. Intended demand: medium.'),
'M-Q3':('revise','The answer conditionally mentions indexes dependent on edited text, but the scenario never establishes that the generated teaching text is an indexed source. That ambiguity obscures the source-index versus generated-version separation.','Identify the edited object explicitly. Re-embed source documents for the model change; return edited generated content to draft and preserve earlier evidence. Reindex edited content only if it is separately ingested as a source. Intended demand: hard after clarification.')}

def main():
 OUT.mkdir(parents=True,exist_ok=True);records=[];inputs=[]
 for label,rel in FILES.items():
  p=ROOT/rel;d=json.loads(p.read_text());h=hashlib.sha256(p.read_bytes()).hexdigest();inputs.append({'file':rel,'sha256':h,'content_id':d['id'],'version':d['version']})
  source_ids={s['id'] for s in d['sources']}
  for typ,key in [('S','sections'),('Q','questions')]:
   for i,unit in enumerate(d['asset'][key],1):
    uid=f'{label}-{typ}{i}';decision,rationale,revision=NOTES[uid]
    records.append(dict(review_id=uid,reviewer_type='ai_assistant',reviewer='Codex AI assistant',review_date='2026-09-19',source_file=rel,source_sha256=h,content_id=d['id'],version=d['version'],unit_type='section' if typ=='S' else 'question',unit_index=i,title_or_stem=unit.get('heading',unit.get('stem')),citation_ids=unit['citation_ids'],citation_membership_valid=all(s in source_ids for s in unit['citation_ids']),decision=decision,rationale=rationale,proposed_revision=revision,original_unit=unit,source_snapshots=[s for s in d['sources'] if s['id'] in unit['citation_ids']]))
 data=dict(review_type='retrospective_nonblind_ai_assisted_content_audit',human_review=False,student_calibration=False,independent_raters=0,scope='Five archived version-one assets, fifteen explanatory sections and eight short-answer questions. Self-authored demonstration course only; no MCQs and no student outcomes.',method='Read each original unit and its cited retrieved excerpts. Distinguish identifier membership, semantic support, engineering inference, historical scope and intended cognitive demand. Targets and original model judgments were not hidden. No production ratings or approval states changed.',inputs=inputs,summary={'assets':5,'sections':15,'questions':8,'units':len(records),'supported_without_required_revision':sum(r['decision']=='supported' for r in records),'revision_recommended':sum(r['decision']=='revise' for r in records)},records=records)
 (OUT/'ai_content_review_20260919.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 fields=['review_id','reviewer_type','reviewer','review_date','source_file','source_sha256','content_id','version','unit_type','unit_index','title_or_stem','citation_ids','citation_membership_valid','decision','rationale','proposed_revision']
 with (OUT/'ai_content_review_20260919.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in records:w.writerow({k:';'.join(r[k]) if k=='citation_ids' else r[k] for k in fields})
 lines=['# AI assisted content review','',data['scope'],'',data['method'],'','This is not human or teacher review. It is not blind and does not estimate student difficulty. Original archived files and application approvals are unchanged.','',json.dumps(data['summary']),'']
 for r in records:lines.extend([f"## {r['review_id']} {r['decision']}",r['title_or_stem'],'',r['rationale'],'','Suggested revision: '+r['proposed_revision'],'','Evidence: `'+r['source_file']+'`; citations: '+', '.join(r['citation_ids']), ''])
 (OUT/'AI_Content_Review.md').write_text('\n'.join(lines))
 print(data['summary'])
if __name__=='__main__':main()
