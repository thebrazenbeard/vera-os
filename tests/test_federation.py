"""Behavioral qualification for unity without erasing node-level individuality."""
import dataclasses
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest

from veraos.federation import (
    AuthorityError, FederationError, LocalEvent, NodeJournal, Participant,
    SharedOrientation, StaleState,
)


class FederationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder=Path(self.tmp.name)
        self.vn=NodeJournal(folder/"vn1.sqlite",node_id="VN1")
        self.lappy=NodeJournal(folder/"lappy.sqlite",node_id="Lappy")
        self.allowed=True
        self.calls=[]
        def governor(node,agent,epoch,revision,event):
            self.calls.append((node,agent,epoch,revision,event))
            return self.allowed and node=="VN1" and agent=="vera:integrator"
        self.shared=SharedOrientation(folder/"global.sqlite",leader_node="VN1",
                                      authorize=governor)
        self.vnp=Participant("Vera","VN1","agent:vn1",None)
        self.lappyp=Participant("Vera","Lappy","agent:lappy","model:mosaic-local")

    def record(self,node,participant,event_id,kind,confidence,value):
        return node.record(participant,event_id=event_id,kind=kind,entity="system:link",
                           predicate="link_is_healthy",value=value,
                           confidence_ppm=confidence)

    def test_two_distinct_local_agents_share_identity_without_merging_hypotheses(self):
        first=self.record(self.vn,self.vnp,"vn1-h1","HYPOTHESIS",700000,True)
        second=self.record(self.lappy,self.lappyp,"lappy-h1","HYPOTHESIS",900000,False)
        self.assertEqual(first.node_id,"VN1")
        self.assertEqual(second.node_id,"Lappy")
        self.assertIsNone(first.model_ref)
        self.assertEqual(second.model_ref,"model:mosaic-local")
        self.assertEqual(len(self.vn.events()),1)
        self.assertEqual(len(self.lappy.events()),1)
        self.assertEqual(self.vn.events()[0].value,True)
        self.assertEqual(self.lappy.events()[0].value,False)
        self.shared.stage(first,authenticated_node_id="VN1")
        self.shared.stage(second,authenticated_node_id="Lappy")
        self.assertIsNone(self.shared.latest("system:link","link_is_healthy"))
        with self.assertRaises(FederationError):
            self.shared.accept(source_node="VN1",event_id="vn1-h1",
                               accepted_by="vera:integrator",expected_epoch=1,
                               expected_revision=0)

    def test_offline_proposal_can_reconcile_without_becoming_accepted_automatically(self):
        offline=self.record(self.lappy,self.lappyp,"lappy-offline","PROPOSAL",
                            950000,{"answer":False,"evidence_refs":[17,42]})
        # While Lappy is disconnected, VN1 knows no proposal.
        self.assertIsNone(self.shared.latest("system:link","link_is_healthy"))
        self.assertEqual(self.shared.orientation().revision,0)
        # Explicit synchronization, not automatically inheriting Lappy's belief.
        self.shared.stage(offline,authenticated_node_id="Lappy")
        self.assertIsNone(self.shared.latest("system:link","link_is_healthy"))
        self.assertEqual(self.shared.accept(source_node="Lappy",
            event_id="lappy-offline",accepted_by="vera:integrator",
            expected_epoch=1,expected_revision=0),1)
        self.assertEqual(self.shared.latest("system:link","link_is_healthy"),
                         {"answer":False,"evidence_refs":[17,42]})
        self.assertEqual(self.shared.decisions()[0][2],"Lappy")

    def test_stale_revision_requires_reconciliation_after_concurrent_decision(self):
        a=self.record(self.lappy,self.lappyp,"l-1","PROPOSAL",990000,False)
        b=self.record(self.vn,self.vnp,"v-1","PROPOSAL",800000,True)
        self.shared.stage(a,authenticated_node_id="Lappy")
        self.shared.stage(b,authenticated_node_id="VN1")
        self.shared.accept(source_node="VN1",event_id="v-1",accepted_by="vera:integrator",
                           expected_epoch=1,expected_revision=0)
        with self.assertRaises(StaleState):
            self.shared.accept(source_node="Lappy",event_id="l-1",
                accepted_by="vera:integrator",expected_epoch=1,expected_revision=0)
        self.assertEqual(self.shared.latest("system:link","link_is_healthy"),True)
        self.assertEqual(len(self.shared.decisions()),1)

    def test_unknown_authority_and_wrong_agent_fail_closed(self):
        proposal=self.record(self.vn,self.vnp,"p-1","PROPOSAL",500000,True)
        self.shared.stage(proposal,authenticated_node_id="VN1")
        self.allowed=False
        with self.assertRaises(AuthorityError):
            self.shared.accept(source_node="VN1",event_id="p-1",
                accepted_by="vera:integrator",expected_epoch=1,expected_revision=0)
        self.allowed=True
        with self.assertRaises(AuthorityError):
            self.shared.accept(source_node="VN1",event_id="p-1",
                accepted_by="agent:vn1",expected_epoch=1,expected_revision=0)
        self.assertIsNone(self.shared.latest("system:link","link_is_healthy"))
        self.assertEqual(self.shared.orientation().revision,0)

    def test_origin_and_semantic_collisions_are_rejected(self):
        event=self.record(self.lappy,self.lappyp,"id-1","PROPOSAL",600000,True)
        with self.assertRaises(AuthorityError):
            self.shared.stage(event,authenticated_node_id="VN1")
        self.shared.stage(event,authenticated_node_id="Lappy")
        self.shared.stage(event,authenticated_node_id="Lappy")
        with self.assertRaises(FederationError):
            self.record(self.lappy,self.lappyp,"id-1","PROPOSAL",600000,False)
        counterfeit=dataclasses.replace(event,digest="0"*64)
        with self.assertRaises(FederationError):
            self.shared.stage(counterfeit,authenticated_node_id="Lappy")

    def test_restart_reloads_local_experience_and_shared_orientation(self):
        proposal=self.record(self.lappy,self.lappyp,"p-1","PROPOSAL",810000,
                             {"decision_id":42})
        self.shared.stage(proposal,authenticated_node_id="Lappy")
        self.shared.accept(source_node="Lappy",event_id="p-1",
                           accepted_by="vera:integrator",
                           expected_epoch=1,expected_revision=0)
        fresh_local=NodeJournal(Path(self.tmp.name)/"lappy.sqlite",node_id="Lappy")
        fresh_global=SharedOrientation(Path(self.tmp.name)/"global.sqlite",
                leader_node="VN1")
        self.assertEqual(fresh_local.events()[0].digest,proposal.digest)
        self.assertEqual(fresh_global.orientation().revision,1)
        self.assertEqual(fresh_global.latest("system:link","link_is_healthy"),
                         {"decision_id":42})
        with self.assertRaisesRegex(FederationError,"already been adopted"):
            fresh_global.accept(source_node="Lappy",event_id="p-1",
                accepted_by="vera:integrator",expected_epoch=1,expected_revision=1)

    def test_local_and_global_identity_mismatches_fail(self):
        with self.assertRaises(FederationError):
            NodeJournal(Path(self.tmp.name)/"vn1.sqlite",node_id="Lappy")
        with self.assertRaises(FederationError):
            SharedOrientation(Path(self.tmp.name)/"global.sqlite",
                              leader_node="Lappy")
        bad=Participant("SomeoneElse","VN1","agent:bad")
        with self.assertRaises(FederationError):
            self.record(self.vn,bad,"p-1","OBSERVATION",100000,True)

    def test_no_model_required_for_local_agent_and_numeric_semantics(self):
        no_model=self.record(self.vn,self.vnp,"p-1","PROPOSAL",800000,
                             {"entities":[17,42],"predicates":[3,7],
                              "edges":[[3,17,42]],"uncertainty":True})
        self.assertEqual(no_model.value["edges"],[[3,17,42]])
        with self.assertRaises(FederationError):
            self.record(self.vn,self.vnp,"p-2","PROPOSAL",800000,{"floats":0.5})


class FederationAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)
        self.node=NodeJournal(self.path/"p.sqlite",node_id="VN1")
        self.owner=Participant("Vera","VN1","agent:observer","model:x")

    def test_broker_must_see_exact_candidate_and_may_reject_content(self):
        seen=[]
        def checker(leader,agent,epoch,revision,proposal):
            seen.append(proposal)
            return (leader=="VN1" and agent=="vera:integrator"
                    and proposal.digest == authorized_digest
                    and proposal.entity=="research:answer"
                    and proposal.value == {"answer_id":42})
        shared=SharedOrientation(self.path/"shared.db",authorize=checker)
        candidate=self.node.record(self.owner,event_id="prop-42",
            kind="PROPOSAL",entity="research:answer",predicate="answer_id",
            value={"answer_id":42},confidence_ppm=900000)
        authorized_digest=candidate.digest
        shared.stage(candidate,authenticated_node_id="VN1")
        self.assertEqual(shared.accept(source_node="VN1",event_id="prop-42",
            accepted_by="vera:integrator",expected_epoch=1,expected_revision=0),1)
        self.assertEqual(seen[0].digest,authorized_digest)
        self.assertEqual(seen[0].identity,"Vera")
        self.assertEqual(seen[0].agent_id,"agent:observer")
        self.assertEqual(seen[0].model_ref,"model:x")

    def test_different_shared_identity_cannot_be_laundered_in(self):
        other=NodeJournal(self.path/"other.sqlite",node_id="VN1",identity="Other")
        event=other.record(Participant("Other","VN1","agent:other"),
            event_id="other-e",kind="PROPOSAL",entity="topic:one",
            predicate="value",value=23,confidence_ppm=300000)
        shared=SharedOrientation(self.path/"shared.db",identity="Vera")
        with self.assertRaisesRegex(FederationError,"another shared identity"):
            shared.stage(event,authenticated_node_id="VN1")

    def test_broker_rejects_unapproved_semantics_without_fallback(self):
        shared=SharedOrientation(self.path/"shared.db",authorize=lambda *args:False)
        event=self.node.record(self.owner,event_id="p-1",kind="PROPOSAL",
            entity="system:setting",predicate="network",value={"action_id":99},
            confidence_ppm=900000)
        shared.stage(event,authenticated_node_id="VN1")
        with self.assertRaises(AuthorityError):
            shared.accept(source_node="VN1",event_id="p-1",
                accepted_by="vera:integrator",expected_epoch=1,expected_revision=0)
        self.assertEqual(shared.decisions(),[])

    def test_forged_digest_is_rejected_before_broker(self):
        shared=SharedOrientation(self.path/"shared.db",authorize=lambda *args:True)
        event=self.node.record(self.owner,event_id="p-1",kind="PROPOSAL",
            entity="system:setting",predicate="network",value={"action_id":99},
            confidence_ppm=900000)
        forged=dataclasses.replace(event,value_json='{"action_id":17}')
        with self.assertRaisesRegex(FederationError,"digest mismatch"):
            shared.stage(forged,authenticated_node_id="VN1")

    def test_epoch_mismatch_blocks_adoption_even_if_broker_would_allow(self):
        shared=SharedOrientation(self.path/"shared.db",authorize=lambda *args:True)
        event=self.node.record(self.owner,event_id="p-1",kind="PROPOSAL",
            entity="system:setting",predicate="network",value=1,
            confidence_ppm=900000)
        shared.stage(event,authenticated_node_id="VN1")
        for stale in (0,2):
            with self.subTest(epoch=stale),self.assertRaises(StaleState):
                shared.accept(source_node="VN1",event_id="p-1",
                    accepted_by="vera:integrator",expected_epoch=stale,
                    expected_revision=0)
        self.assertEqual(shared.orientation().revision,0)

    def test_node_local_history_is_append_only_under_an_event_collision(self):
        a=self.node.record(self.owner,event_id="one",kind="HYPOTHESIS",
            entity="problem:1",predicate="solution",value={"solution_id":14},
            confidence_ppm=550000)
        same=self.node.record(self.owner,event_id="one",kind="HYPOTHESIS",
            entity="problem:1",predicate="solution",value={"solution_id":14},
            confidence_ppm=550000)
        self.assertEqual(a.digest,same.digest)
        self.assertEqual(len(self.node.events()),1)
        with self.assertRaises(FederationError):
            self.node.record(self.owner,event_id="one",kind="HYPOTHESIS",
                entity="problem:1",predicate="solution",value={"solution_id":15},
                confidence_ppm=550000)
        self.assertEqual(self.node.events()[0].value,{"solution_id":14})


class NoDoubleAdoptionTests(unittest.TestCase):
    def test_replay_cannot_reapprove_same_semantic_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            node=NodeJournal(Path(td)/"local.sqlite",node_id="VN1")
            shared=SharedOrientation(Path(td)/"global.sqlite",
                        authorize=lambda leader,actor,epoch,rev,event: True)
            event=node.record(Participant("Vera","VN1","agent:one"),
                event_id="once",kind="PROPOSAL",entity="project:one",
                predicate="commitment",value={"decision_id":17},
                confidence_ppm=800000)
            shared.stage(event,authenticated_node_id="VN1")
            self.assertEqual(shared.accept(source_node="VN1",event_id="once",
                accepted_by="vera:integrator",expected_epoch=1,expected_revision=0),1)
            with self.assertRaisesRegex(FederationError,"already been adopted"):
                shared.accept(source_node="VN1",event_id="once",
                    accepted_by="vera:integrator",expected_epoch=1,expected_revision=1)
            self.assertEqual(len(shared.decisions()),1)

if __name__=="__main__":
    unittest.main()
