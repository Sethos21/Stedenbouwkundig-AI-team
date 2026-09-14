import json
import os
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from bvc_ai.application.design_workflow import DesignWorkflow
from bvc_ai.application.workflow import Workflow
from bvc_ai.application.approval import HumanApprovalService, _HUMAN_CAPABILITY
from bvc_ai.agents.provider import DeterministicTestProvider
from bvc_ai.infrastructure.store import Store
from bvc_ai.adapters.design_presentation import DesignPresentation
from bvc_ai.domain.design import STEPS, current_output

ROOT = Path(__file__).resolve().parents[1]
TID = "DESIGN-TEST-001"


class ChangedProvider(DeterministicTestProvider):
    def __init__(self, change):
        self.change = change

    def design_step(self, step, context, inputs):
        proposal = super().design_step(step, context, inputs)
        self.change(step, proposal, context)
        return proposal


class DesignTests(unittest.TestCase):
    def setUp(self):
        directory = ROOT / '.tools/test-runs'
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.store = Store(self.temp.name)
        self.workflow = DesignWorkflow(self.store, DeterministicTestProvider(), ROOT)
        self.workflow.create()
        self.counter = 0

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def step(self, step, **kwargs):
        self.counter += 1
        return self.workflow.step(TID, step, f'test-{self.counter}', **kwargs)

    def through(self, end):
        for step in STEPS:
            self.step(step)
            if step == end:
                break
        return self.store.get(TID)

    def service(self):
        return HumanApprovalService(self.store, capability=_HUMAN_CAPABILITY)

    def fails_unchanged(self, call):
        before = self.store.get(TID)
        count = len(self.store.events())
        with self.assertRaises((ValueError, PermissionError, TypeError, RuntimeError)):
            call()
        self.assertEqual(self.store.get(TID), before)
        self.assertEqual(len(self.store.events()), count + 1)
        self.assertEqual(self.store.events()[-1]['action'], 'step_failed')

    def mutate(self, change):
        self.workflow.provider = ChangedProvider(change)

    def test_complete_chain_and_capacity(self):
        task = self.workflow.run()
        self.assertEqual(task['status'], 'AWAITING_HUMAN_APPROVAL')
        self.assertIsNone(task['human_approval'])
        self.assertEqual([o['step'] for o in task['outputs']], list(STEPS))
        self.assertEqual({o['agent_id'] for o in task['outputs']}, {f'A{i:02}' for i in range(1,9)})
        self.assertEqual(task['iteration_count'], 1)
        self.assertEqual(len(task['decision_requests']), 1)
        self.assertEqual(len(task['decision_requests'][0]['variants']), 2)
        self.assertTrue(task['decision_requests'][0]['uncertainties'])
        fields = [o for o in task['objects'] if o['object_type'] == 'DEVELOPMENT_FIELD']
        self.assertEqual([o['properties']['capacity'] for o in fields], [167, 35, 95])
        self.assertTrue(all(o['source_status'] == 'TESTDATA' for o in task['objects']))
        self.assertEqual(task['reviews'][-1]['verdict'], 'PASS_WITH_FINDINGS')
        self.assertTrue(task['reviews'][-1]['findings'])
        self.assertFalse(task['stale_reviews'])
        self.assertEqual(self.workflow.report(TID)['audit_event_count'], len(self.store.events(TID)))

    def test_a03_before_environment_gate_denied(self):
        self.through('A06')
        self.fails_unchanged(lambda: self.step('A03_HYPOTHESIS'))

    def test_a03_cannot_write_existing(self):
        self.through('A08_GATE')
        self.mutate(lambda s,p,c: p['objects'][0].update(geometry_status='EXISTING_VALIDATED'))
        self.fails_unchanged(lambda: self.step('A03_HYPOTHESIS'))

    def test_a04_a05_stale_review_denied(self):
        self.through('A03_INTEGRATION')
        old = self.store.get(TID)['active_revisions']['A03_INTEGRATION']
        self.step('A03_INTEGRATION')
        self.mutate(lambda s,p,c: p['review'].update(revision_id=old))
        for step in ('A04_REVIEW', 'A05_REVIEW'):
            self.fails_unchanged(lambda: self.step(step))

    def test_integration_requires_both_specialists(self):
        self.through('A03_HYPOTHESIS')
        self.fails_unchanged(lambda: self.step('A03_INTEGRATION'))
        self.step('A04')
        self.fails_unchanged(lambda: self.step('A03_INTEGRATION'))

    def test_specialists_can_finish_in_reverse_order(self):
        self.through('A03_HYPOTHESIS')
        self.step('A05')
        self.step('A04')
        self.assertEqual(self.step('A03_INTEGRATION')['iteration_count'], 1)

    def test_specialist_revision_mismatch_blocks_integration(self):
        self.through('A05')
        old = self.workflow.inputs(self.store.get(TID), 'A04')
        self.step('A03_HYPOTHESIS')
        self.step('A05')
        self.fails_unchanged(lambda: self.step('A04', expected_inputs=old))
        self.fails_unchanged(lambda: self.step('A03_INTEGRATION'))

    def test_critical_environment_finding_blocks_downstream(self):
        self.through('A06')
        self.mutate(lambda s,p,c: p['findings'][0].update(severity='CRITICAL'))
        self.step('A08_GATE')
        self.workflow.provider = DeterministicTestProvider()
        self.fails_unchanged(lambda: self.step('A03_HYPOTHESIS'))

    def test_a07_cannot_mutate_design_objects(self):
        self.through('A08_REVIEW')
        obj = DeterministicTestProvider().design_step('A03_HYPOTHESIS', {}, {})['objects'][0]
        self.mutate(lambda s,p,c: p['objects'].append(obj))
        self.fails_unchanged(lambda: self.step('A07'))

    def test_a01_cannot_write_specialist_geometry(self):
        obj = DeterministicTestProvider().design_step('A03_HYPOTHESIS', {}, {})['objects'][0]
        self.mutate(lambda s,p,c: p['objects'].append(obj))
        self.fails_unchanged(lambda: self.step('A01_START'))

    def test_provider_approved_and_accepted_risk_denied(self):
        for value in ('APPROVED', 'ACCEPTED_RISK'):
            self.mutate(lambda s,p,c: p.update(summary=value))
            self.fails_unchanged(lambda: self.step('A01_START'))

    def test_fourth_cycle_escalates_without_objects(self):
        def revise(step, proposal, context):
            if step == 'A04_REVIEW':
                proposal['review']['verdict'] = 'REVISE'
                proposal['review']['resolved_findings'] = []
        self.mutate(revise)
        task = self.workflow.run()
        self.assertEqual(task['iteration_count'], 3)
        self.assertEqual(task['status'], 'REQUIRES_HUMAN_DECISION')
        self.assertEqual(sum(o['step'] == 'A03_INTEGRATION' for o in task['outputs']), 3)
        self.assertEqual(sum(e['action'] == 'iteration_limit' for e in self.store.events()), 1)
        self.assertIsNone(task['human_approval'])
        self.fails_unchanged(lambda: self.step('A03_INTEGRATION'))

    def test_a02_revision_stales_downstream_retains_history(self):
        before = self.workflow.run()
        after = self.step('A02')
        self.assertEqual(after['reviews'], before['reviews'])
        self.assertEqual(set(after['stale_reviews']), {r['review_id'] for r in before['reviews']})
        self.assertNotIn('A01_PACKAGE', after['active_revisions'])
        self.assertEqual(after['status'], 'READY')
        self.assertEqual(after['objects'][:len(before['objects'])], before['objects'])
        self.fails_unchanged(lambda: self.step('A03_INTEGRATION'))

    def test_old_review_cannot_release_new_revision(self):
        self.workflow.run()
        self.step('A03_INTEGRATION')
        self.fails_unchanged(lambda: self.step('A01_PACKAGE'))
        self.fails_unchanged(lambda: self.step('A07'))
        with self.assertRaises(ValueError):
            self.service().decide(TID, 'Testmens', 'APPROVED')

    def test_presentation_cannot_modify_source_or_geometry(self):
        self.workflow.run()
        presentation = DesignPresentation(self.store)
        before = self.store.get(TID)
        for change in ({'source_status':'VERIFIED_SOURCE'}, {'geometry_status':'EXISTING_VALIDATED'}, {'png':'fake'}):
            with self.assertRaises(PermissionError):
                presentation.update(TID, change)
            self.assertEqual(self.store.get(TID), before)
        snapshot = presentation.snapshot(TID)
        snapshot['objects'].clear()
        self.assertEqual(self.store.get(TID), before)

    def test_malformed_provider_no_partial_state(self):
        self.through('A08_GATE')
        self.mutate(lambda s,p,c: p['objects'].append({'local_id':'bad'}))
        self.fails_unchanged(lambda: self.step('A03_HYPOTHESIS'))

    def test_provider_exception_rolls_back_and_audits(self):
        def fail(s,p,c):
            c['objects'].append({'malicious':'context mutation'})
            raise RuntimeError('simulated failure')
        self.mutate(fail)
        self.fails_unchanged(lambda: self.step('A01_START'))

    def test_transaction_failure_after_writes_rolls_back_audit_and_domain(self):
        self.through('A01_START')
        original = self.store._save
        def fail(task):
            original(task)
            raise RuntimeError('injected after state SQL, before commit')
        self.store._save = fail
        self.fails_unchanged(lambda: self.step('A02'))
        self.store._save = original
        self.assertEqual(len(self.step('A02')['objects']), 5)

    def test_successful_step_idempotent_and_conflicting_key_denied(self):
        self.workflow.step(TID, 'A01_START', 'same')
        before = self.store.get(TID)
        events = self.store.events()
        self.workflow.step(TID, 'A01_START', 'same')
        self.assertEqual(self.store.get(TID), before)
        self.assertEqual(self.store.events(), events)
        self.fails_unchanged(lambda: self.workflow.step(TID, 'A02', 'same'))

    def test_all_steps_idempotent_including_package(self):
        for step in STEPS:
            self.workflow.step(TID, step, step)
            before = self.store.get(TID)
            events = self.store.events()
            self.workflow.step(TID, step, step)
            self.assertEqual(self.store.get(TID), before)
            self.assertEqual(self.store.events(), events)

    def test_a08_and_all_agents_denied_human_route(self):
        self.workflow.run()
        fid = self.store.get(TID)['findings'][0]['finding_id']
        for actor in [f'A{i:02}' for i in range(1,9)] + [' a08 ']:
            for decision in ('APPROVED', 'REJECTED', 'ACCEPTED_RISK'):
                with self.assertRaises(PermissionError):
                    self.service().decide(TID, actor, decision, 'Test', finding_id=fid if decision == 'ACCEPTED_RISK' else None)
        self.assertIsNone(self.store.get(TID)['human_approval'])
        self.assertEqual(self.store.get(TID)['human_decisions'], [])

    def test_human_risk_acceptance_requires_reason_and_rebuilds_package(self):
        self.workflow.run()
        fid = self.store.get(TID)['findings'][0]['finding_id']
        with self.assertRaises(ValueError):
            self.service().decide(TID, 'Testmens', 'ACCEPTED_RISK', finding_id=fid)
        self.service().decide(TID, 'Testmens', 'ACCEPTED_RISK', 'Uitsluitend geïsoleerd testbesluit', finding_id=fid, idempotency_key='risk')
        task = self.store.get(TID)
        self.assertEqual(task['findings'][0]['status'], 'ACCEPTED_RISK')
        self.assertNotIn('A01_PACKAGE', task['active_revisions'])
        self.assertIsNone(task['human_approval'])
        self.service().decide(TID, 'Testmens', 'ACCEPTED_RISK', 'Uitsluitend geïsoleerd testbesluit', finding_id=fid, idempotency_key='risk')
        self.assertEqual(self.store.get(TID), task)
        self.workflow.run()
        self.service().decide(TID, 'Testmens', 'APPROVED', 'Alleen test', idempotency_key='approve')
        approved = self.store.get(TID)
        self.service().decide(TID, 'Testmens', 'APPROVED', 'Alleen test', idempotency_key='approve')
        self.assertEqual(self.store.get(TID), approved)
        self.fails_unchanged(lambda: self.step('A02'))

    def test_workflow_scoped_roles_and_agent_capabilities(self):
        old = Workflow(self.store, DeterministicTestProvider(), ROOT)
        for actor in ('A03','A04','A05','A06'):
            with self.assertRaises(PermissionError):
                old.agent(actor)
        for actor in (f'A{i:02}' for i in range(1,9)):
            session = self.workflow.agent(actor)
            self.assertFalse(hasattr(session, 'store'))
            self.assertFalse(hasattr(session, 'approve'))
        self.fails_unchanged(lambda: self.workflow.agent('A08').step(TID, 'A01_START', 'wrong'))
        self.fails_unchanged(lambda: self.step('APPROVED'))

    def test_k00_and_raster_registration_denied(self):
        self.through('A01_START')
        for changes in ({'local_id':' k00 '}, {'geometry_ref':'map.png'}, {'geometry_ref':'map.pdf'}, {'geometry_ref':'map.jpg'}):
            self.mutate(lambda s,p,c: p['objects'][0].update(changes))
            self.fails_unchanged(lambda: self.step('A02'))

    def test_agent_cannot_downgrade_finding_status_or_severity(self):
        self.through('A06')
        self.mutate(lambda s,p,c: p['findings'][0].update(status='RESOLVED'))
        self.fails_unchanged(lambda: self.step('A08_GATE'))
        self.mutate(lambda s,p,c: p['findings'][0].update(finding_id='existing'))
        self.fails_unchanged(lambda: self.step('A08_GATE'))

    def test_resolution_requires_owner_and_integration_evidence(self):
        self.through('A03_INTEGRATION')
        fid = self.store.get(TID)['findings'][0]['finding_id']
        self.mutate(lambda s,p,c: p['review'].update(resolved_findings=[fid]))
        self.fails_unchanged(lambda: self.step('A04_REVIEW'))

    def test_two_store_conflict_cannot_commit_stale_proposal(self):
        def change(s,p,c):
            other = Store(self.temp.name)
            try:
                with other.db:
                    task = other.get(TID)
                    task['updated_at'] = 'concurrent change'
                    other._save(task)
            finally:
                other.close()
        self.mutate(change)
        with self.assertRaises(ValueError):
            self.step('A01_START')
        task = self.store.get(TID)
        self.assertEqual(task['outputs'], [])
        self.assertEqual(task['updated_at'], 'concurrent change')
        self.assertEqual(self.store.events()[-1]['action'], 'step_failed')

    def test_cli_demo_isolated_repeatable_and_no_approval(self):
        command = [sys.executable, str(ROOT/'bvc_ai.py'), '--data', self.temp.name, 'demo', 'design-test-001']
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        first = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        report = json.loads(first.stdout)
        self.assertEqual(report['workflowstate'], 'AWAITING_HUMAN_APPROVAL')
        self.assertIsNone(report['human_approval'])
        second = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(json.loads(second.stdout), report)
        self.assertEqual(self.store.get(TID)['outputs'], [])

    def test_a08_denied_in_legacy_human_service(self):
        Workflow(self.store, DeterministicTestProvider(), ROOT).demo()
        with self.assertRaises(PermissionError):
            self.service().decide('GIS-001', 'A08', 'APPROVED')
        self.assertIsNone(self.store.get('GIS-001')['human_approval'])
    def test_revise_after_other_specialist_resolution_reopens_and_recovers(self):
        def revise_once(step, proposal, context):
            if step == 'A05_REVIEW' and context['iteration_count'] == 1:
                proposal['review']['verdict'] = 'REVISE'
                proposal['review']['resolved_findings'] = []
        self.mutate(revise_once)
        task = self.workflow.run()
        self.assertEqual(task['status'], 'AWAITING_HUMAN_APPROVAL')
        self.assertEqual(task['iteration_count'], 2)
        self.assertTrue(any(e['action'] == 'finding_reopened' for e in self.store.events()))
        self.assertTrue(task['stale_reviews'])
        integration = current_output(task, 'A03_INTEGRATION')
        a04_ids = {f['finding_id'] for f in task['findings'] if f['created_by'] == 'A04'}
        self.assertTrue(a04_ids <= {r['finding_id'] for r in integration['output']['responses']})
        self.assertTrue(all(f['status'] == 'RESOLVED' for f in task['findings'] if f['created_by'] == 'A04'))

    def test_existing_review_cannot_be_replaced_to_bypass_revise(self):
        self.through('A03_INTEGRATION')
        self.mutate(lambda s,p,c: p['review'].update(verdict='REVISE', resolved_findings=[]))
        self.step('A04_REVIEW')
        self.workflow.provider = DeterministicTestProvider()
        self.fails_unchanged(lambda: self.step('A04_REVIEW'))
        task = self.step('A05_REVIEW')
        self.assertEqual(task['status'], 'A03_INTEGRATION')
        self.fails_unchanged(lambda: self.step('A07'))

    def test_upstream_change_reopens_stale_resolutions(self):
        self.workflow.run()
        task = self.step('A02')
        self.assertTrue(all(f['status'] == 'OPEN' for f in task['findings'] if f['created_by'] in {'A04','A05'}))
        self.assertTrue(any(e['action'] == 'finding_reopened' for e in self.store.events()))

    def test_missing_input_failure_audit_identifies_gate(self):
        self.fails_unchanged(lambda: self.step('A03_INTEGRATION'))
        details = self.store.events()[-1]['details']
        self.assertEqual(details['failure_phase'], 'gate')
        self.assertIn('Ontbrekende of stale input', details['reason'])

    def test_policy_and_environment_classifications_required(self):
        self.through('A02')
        self.mutate(lambda s,p,c: p['conditions'][0].update(classification='PERMITTED'))
        self.fails_unchanged(lambda: self.step('A06'))
        self.workflow.provider = DeterministicTestProvider()
        self.step('A06')
        self.mutate(lambda s,p,c: p['conditions'].pop())
        self.fails_unchanged(lambda: self.step('A08_GATE'))

    def test_geometry_capacity_cannot_be_provider_input(self):
        self.through('A08_GATE')
        self.mutate(lambda s,p,c: p['objects'][0]['properties'].update(capacity=10000))
        self.fails_unchanged(lambda: self.step('A03_HYPOTHESIS'))

    def test_identical_spatial_variants_denied(self):
        self.through('A08_GATE')
        self.mutate(lambda s,p,c: p['objects'][1].update(geometry_ref=p['objects'][0]['geometry_ref']))
        self.fails_unchanged(lambda: self.step('A03_HYPOTHESIS'))

    def test_blocked_review_retains_findings_and_blocks_package(self):
        self.through('A03_INTEGRATION')
        self.mutate(lambda s,p,c: p['review'].update(verdict='BLOCKED', resolved_findings=[]))
        task = self.step('A04_REVIEW')
        self.assertEqual(task['status'], 'BLOCKED')
        self.assertTrue(any(f['status'] == 'BLOCKED' for f in task['findings']))
        self.fails_unchanged(lambda: self.step('A01_PACKAGE'))

    def test_empty_pass_with_open_obligations_denied(self):
        self.through('A08_REVIEW')
        def empty(s,p,c):
            p['findings'] = []
            p['review']['verdict'] = 'PASS'
        self.mutate(empty)
        self.fails_unchanged(lambda: self.step('A07'))

    def test_cli_human_routes_only_in_isolated_storage(self):
        self.workflow.run()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        command = [sys.executable, str(ROOT/'bvc_ai.py'), '--data', self.temp.name]
        def cli(*args):
            return subprocess.run(command + list(args), cwd=ROOT, env=env, text=True, encoding='utf-8', capture_output=True)
        denied = cli('approve', TID, '--actor', 'A08')
        self.assertEqual(denied.returncode, 2, denied.stdout + denied.stderr)
        risk = cli('accept-risk', TID, self.store.get(TID)['findings'][0]['finding_id'], '--actor', 'Testmens', '--reason', 'Geïsoleerd testbesluit', '--idempotency-key', 'cli-risk')
        self.assertEqual(risk.returncode, 0, risk.stdout + risk.stderr)
        self.assertIsNone(self.store.get(TID)['human_approval'])
        resume = cli('resume', TID)
        self.assertEqual(resume.returncode, 0, resume.stdout + resume.stderr)
        approved = cli('approve', TID, '--actor', 'Testmens', '--reason', 'Geïsoleerd testbesluit', '--idempotency-key', 'cli-approval')
        self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
        first = self.store.get(TID)['human_approval']
        rejected = cli('reject', TID, '--actor', 'Testmens')
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(self.store.get(TID)['human_approval'], first)
    def test_approval_at_iteration_limit_is_denied_and_audited(self):
        def revise(s,p,c):
            if s == 'A04_REVIEW':
                p['review'].update(verdict='REVISE', resolved_findings=[])
        self.mutate(revise)
        task = self.workflow.run()
        self.assertEqual(task['decision_requests'][-1]['decision_id'], 'iteration-limit/4')
        with self.assertRaises(ValueError):
            self.service().decide(TID, 'Testmens', 'APPROVED')
        self.assertEqual(self.store.get(TID), task)
        self.assertEqual(self.store.events()[-1]['action'], 'blocked_transition')

    def test_approval_token_in_free_text_is_denied(self):
        self.mutate(lambda s,p,c: p.update(summary='Dit plan is APPROVED door de agent.'))
        self.fails_unchanged(lambda: self.step('A01_START'))

    def test_specialist_update_keeps_independent_branch_current(self):
        self.workflow.run()
        old = current_output(self.store.get(TID), 'A05')
        task = self.step('A04')
        self.assertEqual(current_output(task, 'A05'), old)
        self.assertNotIn('A03_INTEGRATION', task['active_revisions'])
        task = self.step('A03_INTEGRATION')
        self.assertEqual(task['iteration_count'], 2)
