#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'requirements/progress-06-r2-traceability-audit.json'
SCOPE=ROOT/'requirements/MILESTONE_SCOPE_PROGRESS_06_R2.json'
REQ=re.compile(r'\b[A-Z][A-Z0-9]+-\d{3}\b')

def tests():
    out={}
    for path in sorted((ROOT/'tests').rglob('test_*.py')):
        tree=ast.parse(path.read_text(),filename=str(path)); rel=path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                out[f'{rel}::{node.name}']=set(REQ.findall(ast.get_docstring(node) or ''))
    return out

def build():
    scope=json.loads(SCOPE.read_text()); ledger_doc=json.loads((ROOT/'requirements/requirements-ledger.json').read_text()); ledger={r['requirement_id']:r for r in ledger_doc['requirements']}; impl=json.loads((ROOT/'requirements/implementation-map.json').read_text())['requirements']; found=[]; records=[]; catalog=tests(); entries=[*scope.get('included_requirements',[]),*scope.get('deferred_requirements',[])]
    for entry in sorted(entries,key=lambda x:x['requirement_id']):
        rid=entry['requirement_id']; item=ledger.get(rid)
        if item is None: found.append({'code':'REQUIREMENT_MISSING','requirement_id':rid}); continue
        direct=[]
        for raw in entry.get('direct_tests',[]):
            tid=raw.get('test_id') if isinstance(raw,dict) else str(raw); declared=catalog.get(tid); exists=declared is not None; declares=exists and rid in declared; mapped=tid in impl.get(rid,{}).get('test_ids',[])
            direct.append({'test_id':tid,'exists':exists,'declares_requirement_id':declares,'present_in_implementation_map':mapped,'declared_requirement_ids':sorted(declared or [])})
            if not exists: found.append({'code':'DIRECT_TEST_MISSING','requirement_id':rid,'test_id':tid})
            elif not declares: found.append({'code':'DIRECT_TEST_DECLARATION_MISSING','requirement_id':rid,'test_id':tid})
            if not mapped: found.append({'code':'DIRECT_TEST_MAPPING_MISSING','requirement_id':rid,'test_id':tid})
        if not direct: found.append({'code':'DIRECT_TEST_REQUIRED','requirement_id':rid})
        records.append({'requirement_id':rid,'priority':item['priority'],'status':item['implementation_status'],'requirement':item['text'],'verification_method':item.get('verification_method'),'implementation_files':item.get('implementation_files',[]),'direct_tests':direct,'evidence_paths':item.get('test_result_evidence_paths',[])})
    if ledger.get('PLTVIEW-007',{}).get('implementation_status')!='IMPLEMENTED_UNVERIFIED': found.append({'code':'VIEWER_STATUS','requirement_id':'PLTVIEW-007'})
    return {'accepted_base_commit':scope['accepted_base_commit'],'milestone':'Progress 06-R2 restricted-data, evidence-truth, verification-transition, and provenance remediation','status':'passed_complete' if not found else 'failed','requirement_count':len(records),'requirements_audited':records,'finding_count':len(found),'findings':found,'progress_07_authorized':False,'production_authorized':False}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args(); value=build(); text=json.dumps(value,indent=2,sort_keys=True)+'\n'
    if args.check:
        if not AUDIT.is_file() or AUDIT.read_text()!=text: raise SystemExit('Progress 06-R2 traceability audit drift detected')
    else: AUDIT.write_text(text)
    print(json.dumps({'status':value['status'],'requirements':value['requirement_count'],'findings':value['finding_count']},sort_keys=True)); raise SystemExit(0 if value['status']=='passed_complete' else 1)
if __name__=='__main__': main()
