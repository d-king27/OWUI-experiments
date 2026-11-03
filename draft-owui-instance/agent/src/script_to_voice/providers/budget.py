"""Persistent, conservative text-planning reservations in millionths of a dollar."""
from decimal import Decimal,InvalidOperation,ROUND_CEILING
import os
import time
import uuid


class BudgetError(ValueError):
    pass


def amount(value):
    try:
        result=Decimal(str(value))
        if not result.is_finite() or result<=0: raise ValueError()
        return result
    except (InvalidOperation,ValueError):
        raise BudgetError('Planner budget/rates must be positive finite numbers') from None


class PlannerBudget:
    def __init__(self,repo,*,total='1.00',per_request='0.05',pricing_model='',input_rate=None,output_rate=None,
                 max_input_bytes=16000,max_output_tokens=1000):
        self.repo=repo
        self.total=int(amount(total)*1000000)
        self.per_request=int(amount(per_request)*1000000)
        if self.total<1 or self.per_request<1: raise BudgetError('Planner budget is too small')
        self.model=pricing_model
        self.input_rate=amount(input_rate) if input_rate is not None else None
        self.output_rate=amount(output_rate) if output_rate is not None else None
        if not 1<=max_input_bytes<=60000 or not 1<=max_output_tokens<=4000:
            raise BudgetError('Planner token/context limits are invalid')
        self.max_input_bytes=max_input_bytes; self.max_output_tokens=max_output_tokens

    @classmethod
    def from_environment(cls,repo):
        return cls(repo,total=os.environ.get('STV_LLM_TOTAL_BUDGET_USD','1.00'),
            per_request=os.environ.get('STV_LLM_MAX_REQUEST_USD','0.05'),
            pricing_model=os.environ.get('STV_LLM_PRICING_MODEL',''),
            input_rate=os.environ.get('STV_LLM_INPUT_USD_PER_MILLION') or None,
            output_rate=os.environ.get('STV_LLM_OUTPUT_USD_PER_MILLION') or None,
            max_input_bytes=int(os.environ.get('STV_LLM_MAX_INPUT_BYTES','16000')),
            max_output_tokens=int(os.environ.get('STV_LLM_MAX_OUTPUT_TOKENS','1000')))

    def reserve(self,model,messages):
        if model!=self.model or not self.input_rate or not self.output_rate:
            raise BudgetError('Verify and configure prices for this exact planner model before enabling paid planning')
        size=len(messages.encode('utf-8'))
        if size>self.max_input_bytes: raise BudgetError('Planner input exceeds the demo limit; narrow the selection')
        # Budget by UTF-8 bytes as a conservative text token estimate plus protocol/schema headroom.
        # Future providers with different token accounting must supply a verified preflight calculation.
        upper_input=size+2048
        estimate=int((upper_input*self.input_rate+self.max_output_tokens*self.output_rate).to_integral_value(rounding=ROUND_CEILING))
        if estimate>self.per_request: raise BudgetError('Planner request exceeds the per-request dollar limit')
        with self.repo.connect(immediate=True) as db:
            committed=db.execute('SELECT COALESCE(SUM(reserved),0) FROM planner_budget').fetchone()[0]
            # Reserve the entire request allowance, not just the estimate. Never refund automatically:
            # malformed responses, retries and ambiguous timeouts may all be billable.
            if committed+self.per_request>self.total: raise BudgetError('Text-planning demo allowance exhausted; no request sent')
            ident=uuid.uuid4().hex
            db.execute('INSERT INTO planner_budget VALUES(?,?,?,?)',(ident,model,self.per_request,time.time()))
        return ident

    def status(self):
        with self.repo.connect() as db:
            row=db.execute('SELECT COALESCE(SUM(reserved),0),COUNT(*) FROM planner_budget').fetchone()
            usage=db.execute('SELECT COALESCE(SUM(estimated_microdollars),0),COUNT(*) FROM planner_usage WHERE estimated_microdollars IS NOT NULL').fetchone()
        return {'allowance_usd':self.total/1000000,'reserved_usd':row[0]/1000000,
                'remaining_usd':max(0,self.total-row[0])/1000000,'requests_reserved':row[1],
                'per_request_usd':self.per_request/1000000,
                'reported_usage_estimate_usd':usage[0]/1000000,'requests_with_reported_usage':usage[1]}

    def record(self,reservation,*,outcome,usage=None,request_id=None,elapsed=0,stop_reason=None):
        usage=usage or {}
        counts=[usage.get(k,0) for k in ('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')]
        valid=all(type(v) is int and v>=0 for v in counts) and bool(usage)
        cost=None
        if valid and self.input_rate and self.output_rate:
            i,o,write,read=counts
            # No cache writes are requested; use the conservative 1h write rate if unexpectedly reported.
            cost=int(((i+Decimal('2')*write+Decimal('0.1')*read)*self.input_rate+o*self.output_rate).to_integral_value(rounding=ROUND_CEILING))
        with self.repo.connect(immediate=True) as db:
            db.execute('INSERT INTO planner_usage VALUES(?,?,?,?,?,?,?,?)',
                (reservation,outcome,counts[0] if valid else None,counts[1] if valid else None,cost,
                 request_id,elapsed,stop_reason))
