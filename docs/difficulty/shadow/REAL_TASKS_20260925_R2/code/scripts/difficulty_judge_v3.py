"""Residual-demand audit. Experimental; no human gold or automatic production gate."""
import json
from typing import Literal
from pydantic import Field, model_validator
from scripts.difficulty_judge_v2 import Judgement, Evidence, SYSTEM as V2_SYSTEM

REVISION = 'difficulty-judge-v3-residual-20260924'

class DemandAudit(Evidence):
    support_quotes: list[str] = Field(max_length=4)
    supplied_extent: Literal['fully_supplied', 'partly_supplied', 'not_supplied']
    residual_task: str = Field(max_length=1000)

    @model_validator(mode='after')
    def consistent_extent(self):
        if self.supplied_extent == 'not_supplied' and self.support_quotes:
            raise ValueError('not_supplied cannot cite supplied solution support')
        if self.supplied_extent != 'not_supplied' and not self.support_quotes:
            raise ValueError('Supplied work needs supporting quotes')
        if self.supplied_extent == 'fully_supplied' and self.residual_task.strip():
            raise ValueError('Fully supplied task cannot also be counted as independent work')
        if self.supplied_extent != 'fully_supplied' and not self.residual_task.strip():
            raise ValueError('Unsupplied work needs a concrete residual task')
        return self

class ResidualJudgement(Judgement):
    demand_audit: list[DemandAudit] = Field(min_length=1, max_length=6)
    minimum_sufficient_response: str = Field(min_length=1, max_length=2000)
    hard_basis_quote: str | None = Field(max_length=600)
    learner_relative_basis: str = Field(min_length=1, max_length=1200)

    @model_validator(mode='after')
    def account_for_demands(self):
        quotes = [d.quote for d in self.demand_audit]
        if quotes != [d.quote for d in self.remaining_demands] or len(set(quotes)) != len(quotes):
            raise ValueError('Audit must cover each declared demand exactly once, in order')
        if self.estimated_difficulty == 'hard':
            audit = next((d for d in self.demand_audit if d.quote == self.hard_basis_quote), None)
            if audit is None or audit.supplied_extent == 'fully_supplied':
                raise ValueError('Hard requires a specific unsupplied demand')
        elif self.hard_basis_quote is not None:
            raise ValueError('Only hard judgements select a hard basis')
        return self

SYSTEM = V2_SYSTEM + '''
Additional residual-demand audit:
For each declared remaining_demands entry, add exactly one demand_audit entry with the identical quote, in identical order. Consider both the question's instructions and all visible teaching notes. List exact support_quotes that supply the method, interpretive alternatives, intermediate result or conclusion for THAT demand. Background facts and generic advice alone do not constitute a supplied solution. Set supplied_extent=fully_supplied only if the entire quoted task is already done and no additional explanation/justification is needed; residual_task must then be empty. Use partly_supplied when a scaffold does some but not all of the work. Use not_supplied with support_quotes=[] when none of that task's solution is provided. Describe only the genuinely remaining work in residual_task. The inherited remaining_demands is a list of candidate requirements to audit, not proof that each is independent.
Provide a short minimum_sufficient_response demonstrating how a learner could meet ALL requirements, including evidence, alternative interpretations, universality or equality conditions when required. This is a concise sample answer, not private chain-of-thought. Do not add optional sophistication then judge that sophistication as required. For invalid items state why no valid answer is possible; missing learner background does not prevent solving a complete question.
Reconcile the answer with the audit before assigning difficulty: if the answer selects or restates a supplied interpretation, do not call it invention of a new interpretation. If a hint supplies a proof, assess the remaining explanation rather than discovery of the proof. Conversely, supplied factual data or a broad hint may still leave a substantial nonroutine proof or adjudication; scaffolding alone does not force a low label.
For hard, hard_basis_quote must exactly match a demand_audit quote with a nonempty residual task. learner_relative_basis must identify the concrete remaining bottleneck and explain why the declared prior learning does not make it a familiar application. Calling something synthesis, proof, evaluation, or multiple steps is insufficient. For other labels hard_basis_quote=null. A cognitively strategic task may still be medium for prepared learners. It is permissible for supported and unsupported variants to share a broad difficulty category.
No fixed difficulty labels from previous AI reviews are supplied. Do not aim for any distribution or systematically lower all labels. Fully or partially supplied support is not a score; make a justified holistic estimate, or abstain where an adjacent-level boundary cannot be resolved.'''

def messages(case):
    return [{'role':'system','content':SYSTEM}, {'role':'user','content':json.dumps({
        'learner_profile':case['learner_profile'],'student_visible_text':case['student_visible_text'],
        'schema':ResidualJudgement.model_json_schema()},ensure_ascii=False)}]

def validate(raw,case):
    result=ResidualJudgement.model_validate(raw)
    text=case['student_visible_text']
    quotes=[e.quote for e in result.supplied_support+result.remaining_demands]
    quotes += [q for e in result.demand_audit for q in [e.quote]+e.support_quotes]
    if any(not q.strip() or q not in text for q in quotes):
        raise ValueError('All audit evidence must be exact student-visible text')
    return result.model_dump()
