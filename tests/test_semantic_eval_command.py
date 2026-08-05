"""CLI contracts for staged semantic evaluation campaigns."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import memcommit.commands.semantic_eval as command
from memcommit.provider_types import ProviderIdentity
from memcommit.query_provider import QueryProviderError


runner = CliRunner(mix_stderr=False)


class FakeProvider:
    identity = ProviderIdentity(
        provider="ollama",
        model="qwen3.6:35b-a3b",
        model_digest="abcdef0123456789",
        runtime="ollama/test",
    )
    timeout = 10.0
    last_run = None

    def complete(self, prompt, *, operation, output_schema=None):
        raise AssertionError("the mocked campaign owns provider completion")

    def query(self, source_name, source_content, question):
        raise AssertionError("semantic eval never queries a source")


def _distribution() -> dict[str, dict[str, int]]:
    return {
        "SINGLE": {"NONE": 2, "HELPFUL": 1, "REQUIRED": 1},
        "DOMINANT": {"NONE": 1, "HELPFUL": 1, "REQUIRED": 1},
        "COMPETING": {"NONE": 1, "HELPFUL": 1, "REQUIRED": 1},
    }


def _run_record(
    *,
    run_id: str = "20260803T120000Z-a1b2c3d4",
    provider: str = "ollama",
    model: str = "qwen3.6:35b-a3b",
    passed: int = 10,
    failed: int = 0,
    started_at: str = "2026-08-03T12:00:00Z",
    ledger_path: str | None = None,
    reasoning: str | None = None,
    thinking: bool | None = None,
    runs_per_case: int = 1,
    selected_case_count: int = 10,
    corpus_role: str = "CALIBRATION",
    operation: str = "find-ambiguities",
) -> dict:
    failure_counts = {} if failed == 0 else {"LABEL_MISMATCH": failed}
    if operation == "find-duplicates":
        expected_distributions = {
            "expected_relation": {
                relation: 1
                for relation in (
                    "EXACT",
                    "SURFACE_EQUIVALENT",
                    "SEMANTIC_EQUIVALENT",
                    "OVERLAP",
                    "UNKNOWN",
                    "DISTINCT",
                )[:selected_case_count]
            }
        }
    elif selected_case_count == 10:
        expected_joint = {
            f"{interpretation}/{clarification}": count
            for interpretation, row in _distribution().items()
            for clarification, count in row.items()
        }
        expected_distributions = {"expected_joint": expected_joint}
    else:
        expected_joint = {"SINGLE/NONE": selected_case_count}
        expected_distributions = {"expected_joint": expected_joint}
    if passed + failed != selected_case_count:
        raise AssertionError("test score must match its selected case count")
    value = {
        "schema_version": 1,
        "kind": "memcommit.semantic-eval.run",
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": "2026-08-03T12:01:00Z",
        "ledger_path": ledger_path or f"/tmp/{run_id}.json",
        "status": "COMPLETED",
        "provider": {
            "provider": provider,
            "model": model,
            "model_digest": "a" * 64 if provider == "ollama" else None,
            "reasoning_effort": reasoning,
            "effective_thinking": thinking,
        },
        "pipeline": {
            "id": (
                "duplicate-relation-v1"
                if operation == "find-duplicates"
                else "ambiguity-classify-v1"
            ),
            "version": 1,
        },
        "corpus": {
            "operation": operation,
            "role": corpus_role,
            "calibration_mode": (
                "FIXED_CALIBRATION"
                if corpus_role == "HOLDOUT"
                else "LEAVE_ONE_OUT"
            ),
            "independent_holdout": corpus_role == "HOLDOUT",
            "fixture_digest": "f" * 64,
            "fixture_case_count": (
                selected_case_count if operation == "find-duplicates" else 10
            ),
            "selected_case_ids": [
                f"case-{index}" for index in range(selected_case_count)
            ],
        },
        "settings": {"runs_per_case": runs_per_case},
        "attempts": [],
        "summary": {
            "campaign_passed": failed == 0,
            "cases": {
                "total": passed + failed,
                "passed": passed,
                "failed": failed,
            },
            "attempts": {
                "exact_matches": passed * runs_per_case,
                "structurally_valid": (passed + failed) * runs_per_case,
                "total": (passed + failed) * runs_per_case,
            },
            "failures": failure_counts,
            "distributions": expected_distributions,
            "completion_seconds": {
                "mean": 1.0,
                "median": 0.9,
                "p95": 1.4,
                "max": 1.5,
            },
        },
        "timing": {
            "provider_connection_seconds": 0.125,
            "campaign_seconds": 10.0,
            "total_seconds": 10.125,
        },
    }
    return value


def _task2_v3_record(*, contract_valid: bool = True) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-retrieval-v3",
        "schema_version": 1,
        "run_id": "20260803T230000000000Z-" + "a" * 32,
        "started_at": "2026-08-03T23:00:00Z",
        "status": "VALID" if contract_valid else "INVALID_OUTPUT",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one fixed call was invalid",
        "pipeline": "task2-group-co-membership-retrieval-v3",
        "batch_size": 15,
        "expected_provider_call_count": 4,
        "provider_call_count": 4,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
            "model_digest": "a" * 64,
            "reasoning_effort": None,
        },
        "effective_thinking": False,
        "corpus": {
            "selected_group_count": 26,
            "selected_left_count": 29,
            "selected_right_count": 27,
            "input_digest": "b" * 64,
        },
        "score": {
            "group_co_membership_retrieval": {
                "reviewed_one_to_one_subset": {
                    "overall": {
                        "exact": 48,
                        "total": 48,
                        "macro_jaccard": 1.0,
                    }
                },
                "group_co_membership": {
                    "overall": {
                        "exact": 56,
                        "total": 56,
                        "macro_jaccard": 1.0,
                    },
                    "micro": {"recall": 1.0},
                },
            },
            "grouping_diagnostics": {
                "reciprocal": {
                    "score": {
                        "exact_groups": 26,
                        "expected_groups": 26,
                        "exact_group_f1": 1.0,
                        "multi_member_group_recall": 1.0,
                    }
                },
                "union": {"score": {"exact_groups": 26, "expected_groups": 26}},
            },
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "pipeline_seconds": 4.0,
            "total_seconds": 4.1,
        },
        "ledger_path": "/tmp/task2-v3.json",
    }


def _task2_v4_record(*, contract_valid: bool = True) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-retrieval-v4",
        "schema_version": 1,
        "status": "VALID" if contract_valid else "INVALID_OUTPUT",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one fixed call was invalid",
        "pipeline": "task2-candidate-then-verify-v4",
        "expected_provider_call_count": 8,
        "provider_call_count": 8,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
        },
        "corpus": {
            "selected_group_count": 26,
            "selected_left_count": 29,
            "selected_right_count": 27,
            "input_digest": "b" * 64,
        },
        "score": {
            "candidate_retrieval": {
                "recalled": 56,
                "expected": 56,
                "recall_at_3": 1.0,
                "macro_source_recall_at_3": 1.0,
            },
            "final_group_co_membership": {
                "reviewed_one_to_one_subset": {
                    "overall": {
                        "exact": 48,
                        "total": 48,
                        "macro_jaccard": 1.0,
                    }
                },
                "all_reviewed_groups": {
                    "overall": {
                        "exact": 56,
                        "total": 56,
                        "macro_jaccard": 1.0,
                    }
                },
            },
            "grouping_diagnostics": {
                "reciprocal": {
                    "score": {
                        "exact_groups": 26,
                        "expected_groups": 26,
                        "exact_group_f1": 1.0,
                        "multi_member_group_recall": 1.0,
                    }
                },
                "union": {"score": {"exact_groups": 26, "expected_groups": 26}},
            },
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "candidate_stage_call_seconds": 2.0,
            "verifier_stage_call_seconds": 1.5,
            "pipeline_seconds": 4.0,
            "total_seconds": 4.1,
        },
        "ledger_path": "/tmp/task2-v4.json",
    }


def _task2_candidate_v5_record(
    *, contract_valid: bool = True
) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-candidate-ablation-v5",
        "schema_version": 1,
        "run_id": "candidate-v5-run",
        "started_at": "2026-08-03T23:30:00Z",
        "status": "VALID" if contract_valid else "INVALID_OUTPUT",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one candidate call was invalid",
        "pipeline": "task2-candidate-only-top-k-ablation-v5",
        "expected_provider_call_count": 4,
        "provider_call_count": 4,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
        },
        "effective_thinking": False,
        "condition": {"id": "TOP_5", "candidate_count": 5},
        "corpus": {
            "selected_group_count": 26,
            "selected_left_count": 29,
            "selected_right_count": 27,
            "input_digest": "b" * 64,
        },
        "lock": {"corpus_locked": True},
        "score": {
            "overall": {
                "recovered_directed_edges": 63,
                "expected_directed_edges": 64,
                "micro_recall_at_k": 63 / 64,
                "macro_source_recall_at_k": 55 / 56,
                "one_to_one": {"recovered": 47, "expected": 48},
                "multi_member_groups": {"recovered": 16, "expected": 16},
                "source_hit_distribution": {
                    "complete": 55,
                    "partial": 0,
                    "zero_hit": 1,
                },
            },
            "unique_undirected_gold_edge_recoverability": {
                "recovered": 32,
                "expected": 32,
            },
            "exact_group_recoverability": {
                "recoverable": 25,
                "expected": 26,
                "multi_member": {"recoverable": 2, "expected": 2},
            },
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "provider_call_seconds": 3.5,
            "pipeline_seconds": 4.0,
            "total_seconds": 4.1,
        },
        "ledger_path": "/tmp/task2-candidate-v5.json",
    }


def _task2_judge_v5_record(*, contract_valid: bool = True) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-judge-replay-v5",
        "schema_version": 1,
        "run_id": "judge-v5-run",
        "started_at": "2026-08-03T23:40:00Z",
        "status": "VALID" if contract_valid else "INVALID_OUTPUT",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one judge call was invalid",
        "pipeline": "task2-fixed-candidate-judge-replay-v5",
        "expected_provider_call_count": 11,
        "provider_call_count": 11,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
        },
        "effective_thinking": False,
        "corpus": {
            "group_count": 26,
            "input_digest": "b" * 64,
        },
        "candidate_bundle": {
            "pair_count": 249,
            "digest": "c" * 64,
            "replay_freeze_digest": "d" * 64,
        },
        "score": {
            "candidate_ceiling": {
                "recovered_directed_group_edges": 64,
                "expected_directed_group_edges": 64,
                "recoverable_groups": 26,
                "group_total": 26,
            },
            "binary_same_hypergroup": {
                "true_positive": 62,
                "false_positive": 1,
                "true_negative": 184,
                "false_negative": 2,
                "precision": 62 / 63,
                "recall": 62 / 64,
                "f1": 0.976,
            },
            "multi_member_binary": {
                "true_positive": 14,
                "false_positive": 8,
                "true_negative": 7,
                "false_negative": 2,
                "recall": 0.875,
            },
            "group_induced_enum": {"exact": 230, "total": 249},
            "reviewed_one_to_one_direct_subset": {"exact": 45, "total": 48},
            "source_accepted_set": {"exact": 53, "total": 56},
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "input_preparation_seconds": 0.2,
            "pipeline_seconds": 9.0,
            "total_seconds": 9.3,
        },
        "ledger_path": "/tmp/task2-judge-v5.json",
    }


def _task2_judge_v6_record(*, contract_valid: bool = True) -> dict[str, object]:
    record = _task2_judge_v5_record(contract_valid=contract_valid)
    record.update(
        {
            "kind": "memcommit.semantic-eval.task2-judge-replay-v6",
            "run_id": "judge-v6-run",
            "started_at": "2026-08-03T23:50:00Z",
            "pipeline": "task2-fixed-candidate-judge-replay-v6-strict-boundary",
            "prompt_ablation": {
                "prompt_revision": "STRICT_RELATIONSHIP_UNIT_TWO_STEP_V1",
                "prompt_protocol_digest": "e" * 64,
                "ablation_freeze_digest": "f" * 64,
            },
            "score": {
                "candidate_ceiling": {
                    "recovered_directed_group_edges": 64,
                    "expected_directed_group_edges": 64,
                    "recoverable_groups": 26,
                    "group_total": 26,
                },
                "binary_same_hypergroup": {
                    "true_positive": 58,
                    "false_positive": 20,
                    "true_negative": 165,
                    "false_negative": 6,
                    "precision": 58 / 78,
                    "recall": 58 / 64,
                    "f1": 0.817,
                },
                "multi_member_binary": {
                    "true_positive": 13,
                    "false_positive": 3,
                    "true_negative": 12,
                    "false_negative": 3,
                    "recall": 13 / 16,
                },
                "group_induced_enum": {"exact": 205, "total": 249},
                "reviewed_one_to_one_direct_subset": {
                    "exact": 43,
                    "total": 48,
                },
                "source_accepted_set": {"exact": 45, "total": 56},
            },
            "timing": {
                "provider_connection_seconds": 0.1,
                "input_preparation_seconds": 0.2,
                "pipeline_seconds": 12.0,
                "total_seconds": 12.3,
            },
            "ledger_path": "/tmp/task2-judge-v6.json",
        }
    )
    return record


def _task2_judge_v7_record(*, contract_valid: bool = True) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-judge-replay-v7",
        "schema_version": 1,
        "run_id": "judge-v7-run",
        "started_at": "2026-08-04T00:10:00Z",
        "status": "VALID" if contract_valid else "PROVIDER_ERROR",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one provider call failed",
        "pipeline": "task2-canonical-evidence-judge-replay-v7",
        "expected_provider_call_count": 8,
        "provider_call_count": 8,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
            "model_digest": "a" * 64,
            "runtime": "ollama/test",
            "endpoint": "http://127.0.0.1:11434",
            "reasoning_effort": None,
        },
        "effective_thinking": False,
        "corpus": {"input_digest": "b" * 64, "group_count": 26},
        "evidence_protocol": {
            "prompt_revision": "CANONICAL_DECOMPOSED_EVIDENCE_V1",
            "prompt_protocol_digest": "1" * 64,
            "projection_protocol_digest": "2" * 64,
            "schema_protocol_digest": "3" * 64,
            "evidence_freeze_digest": "4" * 64,
        },
        "evaluation_boundary": {
            "role": "JUDGE_ABLATION_ONLY",
            "scale_promotion_eligible": False,
        },
        "candidate_bundle": {
            "directed_pair_count": 249,
            "digest": "c" * 64,
            "replay_freeze_digest": "d" * 64,
        },
        "canonical_bundle": {
            "pair_count": 169,
            "digest": "e" * 64,
            "evidence_freeze_digest": "4" * 64,
        },
        "score": {
            "canonical_judge": {
                "binary_same_hypergroup": {
                    "true_positive": 60,
                    "false_positive": 10,
                    "true_negative": 94,
                    "false_negative": 5,
                    "precision": 60 / 70,
                    "recall": 60 / 65,
                },
                "multi_member_binary": {
                    "true_positive": 14,
                    "false_positive": 2,
                    "true_negative": 12,
                    "false_negative": 2,
                    "recall": 0.875,
                },
                "group_induced_enum": {"exact": 140, "total": 169},
                "reviewed_one_to_one_direct_subset": {
                    "exact": 42,
                    "total": 48,
                },
            },
            "canonical_evidence": {
                "canonical_pair_count": 169,
                "evidence_returned": 169,
                "resolved": 160,
                "explicit_abstain": 9,
                "missing_due_invalid_call": 0,
            },
            "projected_directed_v5": {
                "source_accepted_set": {"exact": 50, "total": 56},
            },
            "direction_invariance": {
                "invariant_resolved_bidirectional_pairs": 80,
                "comparable_resolved_bidirectional_pairs": 80,
                "invariance_rate": 1.0,
                "resolved_bidirectional_coverage": 0.95,
            },
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "input_preparation_seconds": 0.2,
            "pipeline_seconds": 14.0,
            "total_seconds": 14.3,
        },
        "ledger_path": "/tmp/task2-judge-v7.json",
    }


def _task2_judge_v8_record(*, contract_valid: bool = True) -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-judge-replay-v8",
        "schema_version": 1,
        "run_id": "judge-v8-run",
        "started_at": "2026-08-04T00:20:00Z",
        "status": "VALID" if contract_valid else "PROVIDER_ERROR",
        "contract_valid": contract_valid,
        "validation_error": None if contract_valid else "one stage call failed",
        "pipeline": "task2-hierarchical-canonical-judge-replay-v8",
        "expected_provider_call_count": 18,
        "provider_call_count": 18,
        "provider": {
            "provider": "ollama",
            "model": "qwen3.6:35b-a3b",
            "model_digest": "a" * 64,
            "runtime": "ollama/test",
            "endpoint": "http://127.0.0.1:11434",
            "reasoning_effort": None,
        },
        "effective_thinking": False,
        "corpus": {"input_digest": "b" * 64, "group_count": 26},
        "staged_protocol": {
            "protocol_revision": "HIERARCHICAL_SCOPE_UNIT_BRANCH_V1",
            "prompt_protocol_digests": {
                "STAGE_A_SCOPE_GATE": "1" * 64,
                "STAGE_B_UNIT_KIND": "2" * 64,
                "STAGE_C_CLAIM_OR_RULE": "3" * 64,
                "STAGE_C_PRIMARY_OR_JOINT_UNIT": "4" * 64,
            },
            "schema_protocol_digests": {
                "STAGE_A_SCOPE_GATE": "5" * 64,
                "STAGE_B_UNIT_KIND": "6" * 64,
                "STAGE_C_CLAIM_OR_RULE": "7" * 64,
                "STAGE_C_PRIMARY_OR_JOINT_UNIT": "8" * 64,
            },
            "projection_digest": "9" * 64,
            "stage_a_schedule_digest": "a" * 64,
            "input_freeze_digest": "f" * 64,
        },
        "evaluation_boundary": {
            "role": "JUDGE_ABLATION_ONLY",
            "scale_promotion_eligible": False,
        },
        "candidate_bundle": {
            "directed_pair_count": 249,
            "digest": "c" * 64,
            "replay_freeze_digest": "d" * 64,
        },
        "canonical_bundle": {"pair_count": 169, "digest": "e" * 64},
        "stage_schedules": {
            "stage_a": {"pair_count": 169, "schedule_digest": "a" * 64},
            "stage_b": {"pair_count": 120, "freeze_digest": "b" * 64},
            "stage_c_claim": {"pair_count": 70, "freeze_digest": "c" * 64},
            "stage_c_primary": {"pair_count": 40, "freeze_digest": "d" * 64},
        },
        "calls": {
            "stage_a": [{} for _ in range(8)],
            "stage_b": [{} for _ in range(5)],
            "stage_c_claim": [{} for _ in range(3)],
            "stage_c_primary": [{} for _ in range(2)],
        },
        "score": {
            "canonical_judge": {
                "binary_same_hypergroup": {
                    "true_positive": 60,
                    "false_positive": 10,
                    "true_negative": 85,
                    "false_negative": 5,
                    "precision": 60 / 70,
                    "recall": 60 / 65,
                },
                "multi_member_binary": {
                    "true_positive": 14,
                    "false_positive": 2,
                    "true_negative": 12,
                    "false_negative": 2,
                    "recall": 0.875,
                },
                "group_induced_enum": {"exact": 138, "total": 169},
                "reviewed_one_to_one_direct_subset": {
                    "exact": 41,
                    "total": 48,
                },
            },
            "projected_directed_v5": {
                "source_accepted_set": {"exact": 49, "total": 56},
            },
            "direction_invariance": {
                "invariant_resolved_bidirectional_pairs": 79,
                "comparable_resolved_bidirectional_pairs": 79,
                "invariance_rate": 1.0,
            },
            "staged_pipeline": {
                "outcome_counts": {
                    "FINAL": 160,
                    "ABSTAIN": 9,
                    "INVALID_EVIDENCE": 0,
                    "MISSING_DUE_CALL": 0,
                },
                "call_anomalies": {
                    "attributable_invalid_item_count": 0,
                    "invalid_pair_count": 0,
                    "unattributable_item_count": 0,
                    "missing_pair_count": 0,
                    "response_count_mismatch_calls": 0,
                },
            },
        },
        "timing": {
            "provider_connection_seconds": 0.1,
            "input_preparation_seconds": 0.2,
            "stage_a_seconds": 8.0,
            "stage_b_seconds": 5.0,
            "stage_c_claim_seconds": 3.0,
            "stage_c_primary_seconds": 2.0,
            "pipeline_seconds": 18.0,
            "total_seconds": 18.3,
        },
        "ledger_path": "/tmp/task2-judge-v8.json",
    }


def _task2_adjudication_report() -> dict[str, object]:
    return {
        "kind": "memcommit.semantic-eval.task2-judge-adjudication-queue-v5",
        "schema_version": 1,
        "source_kind": "memcommit.semantic-eval.task2-judge-replay-v5",
        "mode": "READ_ONLY_NO_RELABELING",
        "replay_freeze_digest": "d" * 64,
        "candidate_bundle_digest": "c" * 64,
        "group_count": 26,
        "reference_teacher_model_id": "m01",
        "model_identities": [],
        "expected_boundary_notes": {
            "teacher_is_gold": False,
            "queue_can_relabel": False,
        },
        "summary": {
            "ledger_count": 3,
            "candidate_pair_count": 249,
            "queue_item_count": 17,
            "counts_by_priority": {"P2": 2, "P0": 5, "P1": 10},
            "counts_by_reason": {"Z_REASON": 4, "A_REASON": 13},
            "counts_by_existing_boundary": {"Z_BOUNDARY": 9, "A_BOUNDARY": 8},
        },
        "items": [],
    }


def test_nested_cli_exposes_run_and_status_options():
    result = runner.invoke(
        command.eval_app,
        ["semantic", "run", "ambiguity", "--help"],
    )

    assert result.exit_code == 0, result.output
    help_text = " ".join(result.output.split())
    for option in (
        "--provider",
        "--model",
        "--preset",
        "--reasoning",
        "--thinking",
        "--pipeline",
        "--corpus",
        "--runs",
        "--case",
        "--ledger-dir",
    ):
        assert option in help_text

    status = runner.invoke(command.eval_app, ["semantic", "status", "--help"])
    assert status.exit_code == 0, status.output
    assert "--ledger-dir" in status.output

    duplicate = runner.invoke(
        command.eval_app,
        ["semantic", "run", "duplicate", "--help"],
    )
    assert duplicate.exit_code == 0, duplicate.output
    assert "--provider" in duplicate.output
    assert "--runs" in duplicate.output


def test_run_uses_transient_selection_and_passes_frozen_campaign_arguments(
    monkeypatch,
    tmp_path,
):
    connected: list[dict] = []
    campaign_calls: list[tuple[object, dict]] = []

    def connect(**kwargs):
        connected.append(kwargs)
        return FakeProvider()

    def run_campaign(provider, **kwargs):
        campaign_calls.append((provider, kwargs))
        kwargs["progress_fn"](
            {
                "index": 1,
                "total": 2,
                "case_id": "single-none-main-entrance-hours",
                "repetition": 1,
                "status": "pass",
                "completion_seconds": 0.625,
            }
        )
        return _run_record(
            ledger_path=str(tmp_path / "runs" / "run.json"),
            runs_per_case=2,
        )

    monkeypatch.setattr(command, "_connect_transient_provider", connect)
    monkeypatch.setattr(command, "run_ambiguity_campaign", run_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "ambiguity",
            "--provider",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--thinking",
            "on",
            "--runs",
            "2",
            "--case",
            "first",
            "--case",
            "second",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert connected == [
        {
            "provider_id": "ollama",
            "model": "qwen3.6:35b-a3b",
            "preset": None,
            "reasoning": None,
            "thinking": "on",
        }
    ]
    provider, kwargs = campaign_calls[0]
    assert isinstance(provider, FakeProvider)
    assert kwargs["ledger_dir"] == tmp_path
    assert kwargs["runs"] == 2
    assert kwargs["pipeline"] == "v2"
    assert kwargs["corpus_role"] == "calibration"
    assert kwargs["case_ids"] == ["first", "second"]
    assert kwargs["known_error_types"] == (QueryProviderError,)
    assert kwargs["provider_connection_seconds"] >= 0
    assert (
        "single-none-main-entrance-hours · run 1 · PASS · 0.625s"
        in result.output
    )
    assert "CALIBRATION · leave-one-out" in result.output
    assert "Score: 10/10 cases passed" in result.output
    assert "Attempts: exact 20/20 · structurally valid 20/20" in result.output
    assert "mean/median/p95/max" in result.output
    assert "SINGLE" in result.output
    assert "Ledger:" in result.output


def test_failed_cases_return_nonzero_after_rendering_saved_ledger(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: FakeProvider(),
    )
    monkeypatch.setattr(
        command,
        "run_ambiguity_campaign",
        lambda provider, **kwargs: _run_record(
            passed=9,
            failed=1,
            ledger_path=str(tmp_path / "runs" / "failed.json"),
        ),
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "run", "ambiguity", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Score: 9/10 cases passed" in result.output
    assert "LABEL_MISMATCH 1" in result.output
    assert "Ledger:" in result.output


def test_run_selects_and_labels_the_frozen_holdout(monkeypatch, tmp_path):
    captured: list[dict] = []
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: FakeProvider(),
    )

    def run_campaign(provider, **kwargs):
        captured.append(kwargs)
        return _run_record(
            corpus_role="HOLDOUT",
            ledger_path=str(tmp_path / "runs" / "holdout.json"),
        )

    monkeypatch.setattr(command, "run_ambiguity_campaign", run_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "ambiguity",
            "--corpus",
            "holdout",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured[0]["corpus_role"] == "holdout"
    assert "Corpus: HOLDOUT · independent · fixed calibration" in result.output


def test_run_duplicate_uses_the_host_first_campaign(monkeypatch, tmp_path):
    captured: list[dict] = []
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: FakeProvider(),
    )

    def run_campaign(provider, **kwargs):
        captured.append(kwargs)
        return _run_record(
            operation="find-duplicates",
            selected_case_count=6,
            passed=6,
            ledger_path=str(tmp_path / "runs" / "duplicate.json"),
        )

    monkeypatch.setattr(command, "run_duplicate_campaign", run_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "duplicate",
            "--provider",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--thinking",
            "off",
            "--runs",
            "3",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured[0]["runs"] == 3
    assert "Semantic eval · duplicate · classification gate" in result.output
    assert "Relation distribution:" in result.output


class ReadOnlyConfig:
    """Enough Config surface to prove transient selection never writes it."""

    def semantic_provider(self):
        return "ollama"

    def model_for_provider(self, provider):
        return {
            "ollama": "saved-local",
            "openrouter": "saved/remote",
            "codex_chatgpt": None,
        }.get(provider)

    def codex_reasoning_effort(self):
        return None

    def semantic_timeout_seconds(self):
        return 60.0

    def ollama_base_url(self):
        return "http://127.0.0.1:11434"

    def semantic_context_tokens(self):
        return 4096

    def semantic_max_output_tokens(self):
        return 1024

    def openrouter_zdr(self):
        return True


def test_transient_ollama_connection_reads_config_without_updating_it(monkeypatch):
    captured: dict = {}
    sentinel = FakeProvider()
    monkeypatch.setattr(command, "Config", ReadOnlyConfig)

    def connect(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(command.OllamaProvider, "connect", connect)

    provider = command._connect_transient_provider(
        provider_id="ollama",
        model="qwen3.6:35b-a3b",
        preset=None,
        reasoning=None,
        thinking="on",
    )

    assert provider is sentinel
    assert captured == {
        "model": "qwen3.6:35b-a3b",
        "base_url": "http://127.0.0.1:11434",
        "timeout": 60.0,
        "context_tokens": 4096,
        "max_output_tokens": 1024,
        "thinking": True,
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"provider_id": "unknown"}, "--provider must be one of"),
        (
            {"provider_id": "codex_chatgpt", "preset": "luna-low", "model": "x"},
            "--preset cannot be combined",
        ),
        (
            {"provider_id": "codex_chatgpt", "thinking": "on"},
            "applies only to Ollama",
        ),
        (
            {"provider_id": "openrouter", "reasoning": "low"},
            "apply only to Codex",
        ),
    ],
)
def test_transient_provider_options_fail_closed(kwargs, message):
    values = {
        "provider_id": None,
        "model": None,
        "preset": None,
        "reasoning": None,
        "thinking": "auto",
    }
    values.update(kwargs)

    with pytest.raises(typer.BadParameter, match=message):
        command._resolve_transient_selection(ReadOnlyConfig(), **values)


def test_luna_low_preset_is_a_transient_codex_model_selection():
    selection = command._resolve_transient_selection(
        ReadOnlyConfig(),
        provider_id=None,
        model=None,
        preset="luna-low",
        reasoning=None,
        thinking="auto",
    )

    assert selection.provider_id == "codex_chatgpt"
    assert selection.model == "gpt-5.6-luna"
    assert selection.reasoning_effort == "low"


def test_connection_error_never_exposes_environment_credential(
    monkeypatch,
    tmp_path,
):
    secret = "openrouter-secret-that-must-not-appear"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)

    def fail(**kwargs):
        raise QueryProviderError(f"authentication failed for {secret}")

    monkeypatch.setattr(command, "_connect_transient_provider", fail)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "ambiguity",
            "--provider",
            "openrouter",
            "--model",
            "author/model",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert secret not in result.output
    assert secret not in result.stderr
    assert "[redacted]" in result.stderr


def _write_record(root: Path, name: str, value: dict) -> None:
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / name).write_text(json.dumps(value), encoding="utf-8")


def test_status_is_provider_free_and_shows_latest_per_provider_model_pipeline(
    monkeypatch,
    tmp_path,
):
    _write_record(
        tmp_path,
        "001.json",
        _run_record(
            run_id="001",
            passed=7,
            failed=3,
            started_at="2026-08-01T00:00:00Z",
        ),
    )
    _write_record(
        tmp_path,
        "002.json",
        _run_record(
            run_id="002",
            passed=9,
            failed=1,
            started_at="2026-08-02T00:00:00Z",
        ),
    )
    _write_record(
        tmp_path,
        "003.json",
        _run_record(
            run_id="003",
            provider="codex_chatgpt",
            model="gpt-5.6-luna",
            passed=10,
            failed=0,
            started_at="2026-08-03T00:00:00Z",
        ),
    )
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("status must not connect a provider"),
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "ollama:qwen3.6:35b-a3b" in result.output
    assert "CALIBRATION score 9/10" in result.output
    assert "CALIBRATION score 7/10" not in result.output
    assert "codex_chatgpt:gpt-5.6-luna" in result.output
    assert "CALIBRATION score 10/10" in result.output
    assert "attempts exact=10/10 · structurally-valid=10/10" in result.output
    assert "completion(mean/median/p95/max)" in result.output
    assert "Label distribution:" in result.output


def test_scoreboard_separates_thinking_and_prefers_full_corpus_over_newer_subset():
    auto_full = command._validate_run_record(
        _run_record(
            run_id="auto-full",
            started_at="2026-08-01T00:00:00Z",
            thinking=True,
        )
    )
    auto_subset = command._validate_run_record(
        _run_record(
            run_id="auto-subset",
            started_at="2026-08-03T00:00:00Z",
            thinking=True,
            selected_case_count=1,
            passed=1,
            failed=0,
        )
    )
    off_full = command._validate_run_record(
        _run_record(
            run_id="off-full",
            started_at="2026-08-02T00:00:00Z",
            thinking=False,
        )
    )

    latest = command._latest_records([auto_full, auto_subset, off_full])

    assert len(latest) == 2
    assert {record["effective_thinking"] for record in latest} == {True, False}
    selected = {
        record["effective_thinking"]: record["run_id"] for record in latest
    }
    assert selected[True] == "auto-full"


def test_status_with_no_runs_is_a_normal_read_only_state(tmp_path):
    result = runner.invoke(
        command.eval_app,
        ["semantic", "status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "No semantic evaluation campaigns yet" in result.output
    assert "mem eval semantic run ambiguity" in result.output


@pytest.mark.parametrize(
    "raw",
    [
        "{not-json",
        '{"schema_version":1,"schema_version":1}',
        json.dumps(
            {
                "schema_version": 999,
                "kind": "memcommit.semantic-eval.run",
                "run_id": "bad",
                "status": "COMPLETED",
            }
        ),
    ],
)
def test_status_fails_closed_on_corrupt_or_unknown_run_schema(tmp_path, raw):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "bad.json").write_text(raw, encoding="utf-8")

    result = runner.invoke(
        command.eval_app,
        ["semantic", "status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Semantic eval status error" in result.stderr


def test_runs_option_is_bounded_before_provider_connection(monkeypatch, tmp_path):
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("invalid runs must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "ambiguity",
            "--runs",
            "21",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "20" in result.stderr


def test_task2_v3_rejects_unfrozen_rung_before_provider_connection(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("invalid rung must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-retrieval-v3",
            "--groups",
            "27",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "26, 50, 100, or 138" in result.stderr


@pytest.mark.parametrize(
    ("contract_valid", "exit_code"),
    [(True, 0), (False, 1)],
)
def test_task2_v3_command_renders_retained_result(
    monkeypatch, tmp_path, contract_valid, exit_code
):
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    captured: dict[str, object] = {}

    def fake_campaign(provider, **kwargs):
        captured.update(kwargs)
        return _task2_v3_record(contract_valid=contract_valid)

    monkeypatch.setattr(command, "run_task2_retrieval_v3_campaign", fake_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-retrieval-v3",
            "--provider",
            "ollama",
            "--groups",
            "26",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == exit_code
    assert "Group co-membership: exact 56/56" in result.output
    assert "Reviewed 1:1 subset: exact 48/48" in result.output
    assert "reciprocal 26/26" in result.output
    assert captured["group_count"] == 26
    assert captured["known_error_types"] == (QueryProviderError,)


def test_task2_v4_rejects_unfrozen_rung_before_provider_connection(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("invalid rung must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-retrieval-v4",
            "--groups",
            "27",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "26, 50, 100, or 138" in result.stderr


@pytest.mark.parametrize(
    ("contract_valid", "exit_code"),
    [(True, 0), (False, 1)],
)
def test_task2_v4_command_renders_candidate_and_verifier_results(
    monkeypatch, tmp_path, contract_valid, exit_code
):
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    captured: dict[str, object] = {}

    def fake_campaign(provider, **kwargs):
        captured.update(kwargs)
        return _task2_v4_record(contract_valid=contract_valid)

    monkeypatch.setattr(command, "run_task2_retrieval_v4_campaign", fake_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-retrieval-v4",
            "--provider",
            "ollama",
            "--groups",
            "26",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == exit_code
    assert "Stage A candidate recall@3: 56/56" in result.output
    assert "Stage B group co-membership: exact 56/56" in result.output
    assert "Reviewed 1:1 subset: exact 48/48" in result.output
    assert "Stage A calls 2.000s" in result.output
    assert "Stage B calls 1.500s" in result.output
    assert "Single-run rung gate: " in result.output
    assert captured["group_count"] == 26
    assert captured["known_error_types"] == (QueryProviderError,)


@pytest.mark.parametrize(
    ("contract_valid", "exit_code"),
    [(True, 0), (False, 1)],
)
def test_task2_candidate_v5_command_renders_ablation_result(
    monkeypatch, tmp_path, contract_valid, exit_code
):
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    captured: dict[str, object] = {}

    def fake_campaign(provider, **kwargs):
        captured.update(kwargs)
        return _task2_candidate_v5_record(contract_valid=contract_valid)

    monkeypatch.setattr(
        command, "run_task2_candidate_ablation_v5_campaign", fake_campaign
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-candidate-v5",
            "--provider",
            "ollama",
            "--candidate-count",
            "5",
            "--groups",
            "26",
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == exit_code
    assert "Candidate ablation TOP_5: directed co-member recall 63/64" in result.output
    assert "reviewed 1:1 47/48" in result.output
    assert "exact groups 25/26" in result.output
    assert "provider calls 3.500s" in result.output
    assert captured["candidate_count"] == 5
    assert captured["group_count"] == 26
    assert captured["known_error_types"] == (QueryProviderError,)


@pytest.mark.parametrize(
    ("contract_valid", "exit_code"),
    [(True, 0), (False, 1)],
)
def test_task2_judge_v5_command_renders_one_common_ceiling_and_scores(
    monkeypatch, tmp_path, contract_valid, exit_code
):
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    parents = [tmp_path / "first-v4.json", tmp_path / "second-v4.json"]
    for parent in parents:
        parent.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_campaign(provider, **kwargs):
        captured.update(kwargs)
        return _task2_judge_v5_record(contract_valid=contract_valid)

    monkeypatch.setattr(command, "run_task2_judge_replay_v5_campaign", fake_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v5",
            "--provider",
            "ollama",
            "--candidate-ledger",
            str(parents[0]),
            "--candidate-ledger",
            str(parents[1]),
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == exit_code
    assert "Fixed judge bundle: 249 directed candidate pairs" in result.output
    assert result.output.count("Candidate ceiling:") == 1
    assert "directed Gold co-members 64/64" in result.output
    assert "Partition-induced binary proxy: TP/FP/TN/FN 62/1/184/2" in result.output
    assert "not independently reviewed negative-pair accuracy" in result.output
    assert "Group-induced enum: exact 230/249" in result.output
    assert captured["parent_ledgers"] == parents
    assert captured["known_error_types"] == (QueryProviderError,)


def test_task2_judge_v5_requires_two_parent_ledgers_before_connection(
    monkeypatch, tmp_path
):
    parent = tmp_path / "first-v4.json"
    parent.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("parent count must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v5",
            "--candidate-ledger",
            str(parent),
        ],
    )

    assert result.exit_code != 0
    assert "at least two V4" in result.stderr
    assert "parents" in result.stderr


@pytest.mark.parametrize(
    ("contract_valid", "exit_code"),
    [(True, 0), (False, 1)],
)
def test_task2_judge_v6_command_renders_strict_ablation_and_proxy_scores(
    monkeypatch, tmp_path, contract_valid, exit_code
):
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    parents = [tmp_path / "first-v4.json", tmp_path / "second-v4.json"]
    for parent in parents:
        parent.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_campaign(provider, **kwargs):
        captured.update(kwargs)
        return _task2_judge_v6_record(contract_valid=contract_valid)

    monkeypatch.setattr(command, "run_task2_judge_replay_v6_campaign", fake_campaign)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v6",
            "--provider",
            "ollama",
            "--candidate-ledger",
            str(parents[0]),
            "--candidate-ledger",
            str(parents[1]),
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == exit_code
    assert "Fixed judge bundle: 249 directed candidate pairs" in result.output
    assert "Strict prompt: revision STRICT_RELATIONSHIP_UNIT_TWO_STEP_V1" in result.output
    assert "protocol eeeeeeeeeeee · ablation ffffffffffff" in result.output
    assert "Partition-induced binary proxy: TP/FP/TN/FN 58/20/165/6" in result.output
    assert "not independently reviewed negative-pair accuracy" in result.output
    assert "multi-member recall 0.812" in result.output
    assert "judge pipeline 12.000s" in result.output
    assert captured["parent_ledgers"] == parents
    assert captured["known_error_types"] == (QueryProviderError,)


def test_task2_judge_v6_requires_two_parent_ledgers_before_connection(
    monkeypatch, tmp_path
):
    parent = tmp_path / "first-v4.json"
    parent.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("parent count must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v6",
            "--candidate-ledger",
            str(parent),
        ],
    )

    assert result.exit_code != 0
    assert "at least two V4" in result.stderr
    assert "parents" in result.stderr


def test_task2_judge_v7_command_self_validates_and_renders_qwen_thinking_off(
    monkeypatch, tmp_path
):
    parents = [tmp_path / "first-v4.json", tmp_path / "second-v4.json"]
    for parent in parents:
        parent.write_text("{}", encoding="utf-8")
    connection: dict[str, object] = {}
    campaign: dict[str, object] = {}
    events: list[str] = []
    record = _task2_judge_v7_record()

    def fake_connect(**kwargs):
        connection.update(kwargs)
        return FakeProvider()

    def fake_campaign(provider, **kwargs):
        events.append("campaign")
        campaign.update(kwargs)
        return record

    def fake_validate(value):
        events.append("validate")
        assert value is record
        return {
            "valid": True,
            "canonical_pair_count": 169,
            "call_count": 8,
            "evidence_freeze_digest": "4" * 64,
        }

    monkeypatch.setattr(command, "_connect_transient_provider", fake_connect)
    monkeypatch.setattr(command, "run_task2_judge_replay_v7_campaign", fake_campaign)
    monkeypatch.setattr(command, "validate_task2_judge_replay_v7_record", fake_validate)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v7",
            "--provider",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--thinking",
            "off",
            "--candidate-ledger",
            str(parents[0]),
            "--candidate-ledger",
            str(parents[1]),
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert events == ["campaign", "validate"]
    assert connection["thinking"] == "off"
    assert campaign["parent_ledgers"] == parents
    assert campaign["known_error_types"] == (QueryProviderError,)
    assert "strict self-validation VALID · thinking=false" in result.output
    assert "canonicalization 249→169 canonical pairs · calls 8/8" in result.output
    assert "prompt 111111111111 · projection 222222222222" in result.output
    assert "schema 333333333333 · freeze 444444444444" in result.output
    assert "resolved/abstain/missing 160/9/0" in result.output
    assert "TP/FP/TN/FN 60/10/94/5 · precision 0.857 · recall 0.923" in result.output
    assert "canonical enum 140/169 · reviewed 1:1 direct 42/48" in result.output
    assert "multi TP/FP/TN/FN 14/2/12/2" in result.output
    assert "projected directed source sets 50/56" in result.output
    assert "direction invariance 80/80 · rate 1.000" in result.output
    assert "pipeline 14.000s · total 14.300s" in result.output
    assert "evaluation JUDGE_ABLATION_ONLY · no scale promotion" in result.output


def test_task2_judge_v7_failure_schedule_is_forwarded_then_self_validation_fails(
    monkeypatch, tmp_path
):
    parents = [tmp_path / "first-v4.json", tmp_path / "second-v4.json"]
    for parent in parents:
        parent.write_text("{}", encoding="utf-8")
    failed_record = _task2_judge_v7_record(contract_valid=False)
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )

    def fake_campaign(provider, **kwargs):
        observed["known_error_types"] = kwargs["known_error_types"]
        observed["completed_calls"] = failed_record["provider_call_count"]
        return failed_record

    def reject_invalid(value):
        observed["validated_after_campaign"] = value is failed_record
        raise command.Task2JudgeReplayV7Error(
            "provider failure retained after the full fixed schedule"
        )

    monkeypatch.setattr(command, "run_task2_judge_replay_v7_campaign", fake_campaign)
    monkeypatch.setattr(command, "validate_task2_judge_replay_v7_record", reject_invalid)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v7",
            "--provider",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--thinking",
            "off",
            "--candidate-ledger",
            str(parents[0]),
            "--candidate-ledger",
            str(parents[1]),
        ],
    )

    assert result.exit_code == 1
    assert observed == {
        "known_error_types": (QueryProviderError,),
        "completed_calls": 8,
        "validated_after_campaign": True,
    }
    assert "full fixed schedule" in result.stderr


def test_task2_judge_v7_rejects_sol_luna_before_connection(monkeypatch, tmp_path):
    parents = [tmp_path / "first-v4.json", tmp_path / "second-v4.json"]
    for parent in parents:
        parent.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("Sol/Luna policy must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v7",
            "--provider",
            "codex_chatgpt",
            "--preset",
            "luna-low",
            "--candidate-ledger",
            str(parents[0]),
            "--candidate-ledger",
            str(parents[1]),
        ],
    )

    assert result.exit_code != 0
    assert "Qwen-only" in result.stderr
    assert "Sol" in result.stderr


def test_task2_judge_v8_command_self_validates_before_rendering_thinking_off(
    monkeypatch, tmp_path
):
    parents = [tmp_path / "first-v4.json", tmp_path / "second-v4.json"]
    for parent in parents:
        parent.write_text("{}", encoding="utf-8")
    record = _task2_judge_v8_record()
    events: list[str] = []
    captured: dict[str, object] = {}

    def fake_connect(**kwargs):
        captured["connect"] = kwargs
        return FakeProvider()

    def fake_campaign(provider, **kwargs):
        events.append("campaign")
        captured["campaign"] = kwargs
        return record

    def fake_validate(value):
        events.append("validate")
        assert value is record
        return {
            "integrity_valid": True,
            "contract_valid": True,
            "status": "VALID",
            "canonical_pair_count": 169,
            "provider_call_count": 18,
            "input_freeze_digest": "f" * 64,
        }

    monkeypatch.setattr(command, "_connect_transient_provider", fake_connect)
    monkeypatch.setattr(command, "run_task2_judge_replay_v8_campaign", fake_campaign)
    monkeypatch.setattr(command, "validate_task2_judge_replay_v8_record", fake_validate)

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v8",
            "--provider",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--thinking",
            "off",
            "--candidate-ledger",
            str(parents[0]),
            "--candidate-ledger",
            str(parents[1]),
            "--ledger-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert events == ["campaign", "validate"]
    assert captured["connect"]["thinking"] == "off"
    assert captured["campaign"]["parent_ledgers"] == parents
    assert captured["campaign"]["known_error_types"] == (QueryProviderError,)
    assert "strict integrity VALID · contract VALID · thinking=false" in result.output
    assert "canonicalization 249→169 canonical pairs" in result.output
    assert "stage pairs A/B/C 169/120/110 · C claim/primary 70/40" in result.output
    assert "stage calls A/B/C 8/5/5 · C claim/primary 3/2 · total 18/18" in result.output
    assert "projection 999999999999 · input freeze ffffffffffff" in result.output
    assert "prompt digests A/B/C-claim/C-primary" in result.output
    assert "schema digests A/B/C-claim/C-primary" in result.output
    assert "outcomes FINAL/ABSTAIN/INVALID_EVIDENCE/MISSING_DUE_CALL 160/9/0/0" in result.output
    assert "call anomalies invalid-items/invalid-pairs/unattributable/missing/" in result.output
    assert "TP/FP/TN/FN 60/10/85/5 · precision 0.857 · recall 0.923" in result.output
    assert "reviewed 1:1 direct 41/48" in result.output
    assert "multi TP/FP/TN/FN 14/2/12/2" in result.output
    assert "projected directed source sets 49/56" in result.output
    assert "direction invariance 79/79 · rate 1.000" in result.output
    assert "stage time A/B/C-claim/C-primary 8.000s/5.000s/3.000s/2.000s" in result.output
    assert "pipeline 18.000s · total 18.300s" in result.output
    assert "evaluation JUDGE_ABLATION_ONLY · no scale promotion" in result.output


def test_task2_judge_v8_integrity_valid_contract_failure_is_unavailable(
    monkeypatch, tmp_path
):
    parents = [tmp_path / "first-v4.json", tmp_path / "second-v4.json"]
    for parent in parents:
        parent.write_text("{}", encoding="utf-8")
    record = _task2_judge_v8_record(contract_valid=False)
    monkeypatch.setattr(
        command, "_connect_transient_provider", lambda **kwargs: FakeProvider()
    )
    monkeypatch.setattr(
        command,
        "run_task2_judge_replay_v8_campaign",
        lambda provider, **kwargs: record,
    )
    monkeypatch.setattr(
        command,
        "validate_task2_judge_replay_v8_record",
        lambda value: {
            "integrity_valid": True,
            "contract_valid": False,
            "status": "PROVIDER_ERROR",
            "provider_call_count": 18,
        },
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v8",
            "--provider",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--thinking",
            "off",
            "--candidate-ledger",
            str(parents[0]),
            "--candidate-ledger",
            str(parents[1]),
        ],
    )

    assert result.exit_code == 1
    assert "strict integrity VALID · contract INVALID · metrics UNAVAILABLE" in result.stderr
    assert "schedule completed 18/18 calls" in result.stderr
    assert "non-performance outcomes FINAL/ABSTAIN/INVALID_EVIDENCE/" in result.stderr
    assert "MISSING_DUE_CALL 160/9/0/0" in result.stderr
    assert "Retained call anomalies" in result.stderr
    assert "stage time A/B/C-claim/C-primary 8.000s/5.000s/3.000s/2.000s" in result.stderr
    assert "pipeline 18.000s · total 18.300s" in result.stderr
    assert "Validation error: one stage call failed" in result.stderr
    assert "JUDGE_ABLATION_ONLY · no scale promotion" in result.stderr
    assert "Ledger: /tmp/task2-judge-v8.json" in result.stderr
    assert "canonical partition-induced binary" not in result.output


def test_task2_judge_v8_rejects_sol_luna_before_connection(monkeypatch, tmp_path):
    parents = [tmp_path / "first-v4.json", tmp_path / "second-v4.json"]
    for parent in parents:
        parent.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "_connect_transient_provider",
        lambda **kwargs: pytest.fail("Sol/Luna policy must fail before connection"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "run",
            "task2-judge-replay-v8",
            "--provider",
            "codex_chatgpt",
            "--preset",
            "luna-low",
            "--candidate-ledger",
            str(parents[0]),
            "--candidate-ledger",
            str(parents[1]),
        ],
    )

    assert result.exit_code != 0
    assert "Qwen-only" in result.stderr
    assert "Sol" in result.stderr


@pytest.mark.parametrize("passed", [True, False])
def test_task2_v3_parity_command_uses_co_membership_result(
    monkeypatch, tmp_path, passed
):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_retrieval_v3_records",
        lambda _first, _second: {
            "first_contract_valid": True,
            "second_contract_valid": True,
            "group_co_membership_agreement": {
                "overall": {
                    "exact": 56 if passed else 55,
                    "total": 56,
                    "macro_jaccard": 1.0 if passed else 0.98,
                }
            },
            "reviewed_one_to_one_agreement": {
                "overall": {
                    "both_gold": 48 if passed else 47,
                    "first_only_gold": 0 if passed else 1,
                    "second_only_gold": 0,
                    "both_wrong_same": 0,
                    "both_wrong_different": 0,
                }
            },
            "grouping_agreement": {
                "reciprocal": {"jaccard": 1.0 if passed else 0.9},
                "union": {"jaccard": 1.0 if passed else 0.9},
            },
            "parity_gate_passed": passed,
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-retrieval-v3-parity", str(first), str(second)],
    )

    assert result.exit_code == (0 if passed else 1)
    assert "group co-membership sets" in result.output
    assert "Reviewed 1:1 Gold split" in result.output


@pytest.mark.parametrize("passed", [True, False])
def test_task2_v4_parity_command_separates_candidate_and_final_agreement(
    monkeypatch, tmp_path, passed
):
    first = tmp_path / "first-v4.json"
    second = tmp_path / "second-v4.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_retrieval_v4_records",
        lambda _first, _second: {
            "first_contract_valid": True,
            "second_contract_valid": True,
            "candidate_set_agreement": {
                "overall": {
                    "exact": 56 if passed else 20,
                    "total": 56,
                    "macro_jaccard": 1.0 if passed else 0.6,
                }
            },
            "final_group_co_membership_agreement": {
                "overall": {
                    "exact": 56 if passed else 40,
                    "total": 56,
                    "macro_jaccard": 1.0 if passed else 0.75,
                }
            },
            "reviewed_one_to_one_gold_quadrants": {
                "overall": {
                    "both_gold": 48 if passed else 30,
                    "first_only_gold": 0 if passed else 5,
                    "second_only_gold": 0 if passed else 4,
                    "both_wrong_same": 0 if passed else 6,
                    "both_wrong_different": 0 if passed else 3,
                }
            },
            "grouping_agreement": {
                "reciprocal": {"jaccard": 1.0 if passed else 0.7},
                "union": {"jaccard": 1.0 if passed else 0.3},
            },
            "parity_gate_passed": passed,
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-retrieval-v4-parity", str(first), str(second)],
    )

    assert result.exit_code == (0 if passed else 1)
    assert "candidate sets" in result.output
    assert "final co-membership sets" in result.output
    assert "Reviewed 1:1 Gold split" in result.output


@pytest.mark.parametrize("passed", [True, False])
def test_task2_judge_v5_parity_command_compares_identical_call_inputs(
    monkeypatch, tmp_path, passed
):
    first = tmp_path / "first-judge-v5.json"
    second = tmp_path / "second-judge-v5.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_judge_replay_v5_records",
        lambda _first, _second: {
            "fixed_call_inputs_identical": True,
            "binary_accept_reject_agreement": {
                "exact": 249 if passed else 240,
                "total": 249,
                "exact_accuracy": 1.0 if passed else 240 / 249,
            },
            "exact_enum_agreement": {
                "exact": 249 if passed else 220,
                "total": 249,
                "exact_accuracy": 1.0 if passed else 220 / 249,
            },
            "source_accepted_set_agreement": {
                "exact": 56 if passed else 50,
                "total": 56,
                "exact_accuracy": 1.0 if passed else 50 / 56,
                "macro_jaccard": 1.0 if passed else 0.91,
            },
            "multi_member_agreement": {
                "pair_binary_accept_reject": {
                    "exact": 16 if passed else 14,
                    "total": 16,
                },
                "pair_enum": {
                    "exact": 16 if passed else 12,
                    "total": 16,
                },
                "source_accepted_set": {
                    "exact": 8 if passed else 6,
                    "total": 8,
                },
            },
            "reviewed_one_to_one_direct_enum_quadrants": {
                "expected_directed_sources": 48,
                "recovered_directed_sources": 48,
                "both_gold": 48 if passed else 42,
                "first_only_gold": 0 if passed else 2,
                "second_only_gold": 0 if passed else 1,
                "both_wrong_same": 0 if passed else 2,
                "both_wrong_different": 0 if passed else 1,
            },
            "parity_gate": {"passed": passed, "criteria": {}},
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-judge-v5-parity", str(first), str(second)],
    )

    assert result.exit_code == (0 if passed else 1)
    assert "fixed common call inputs true" in result.output
    assert "binary accept/reject" in result.output
    assert "exact relation enum" in result.output
    assert "Multi-member agreement: binary" in result.output
    assert "Reviewed 1:1 direct Gold split" in result.output
    assert "Parity gate: " + ("PASS" if passed else "FAIL") in result.output


@pytest.mark.parametrize("passed", [True, False])
def test_task2_judge_v6_parity_command_compares_strict_ablation(
    monkeypatch, tmp_path, passed
):
    first = tmp_path / "first-judge-v6.json"
    second = tmp_path / "second-judge-v6.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_judge_replay_v6_records",
        lambda _first, _second: {
            "prompt_revision": "STRICT_RELATIONSHIP_UNIT_TWO_STEP_V1",
            "ablation_freeze_digest": "f" * 64,
            "fixed_call_inputs_identical": True,
            "binary_accept_reject_agreement": {
                "exact": 249 if passed else 241,
                "total": 249,
            },
            "exact_enum_agreement": {
                "exact": 249 if passed else 223,
                "total": 249,
            },
            "source_accepted_set_agreement": {
                "exact": 56 if passed else 51,
                "total": 56,
                "macro_jaccard": 1.0 if passed else 0.93,
            },
            "multi_member_agreement": {
                "pair_binary_accept_reject": {
                    "exact": 33 if passed else 30,
                    "total": 33,
                },
                "pair_enum": {
                    "exact": 33 if passed else 27,
                    "total": 33,
                },
                "source_accepted_set": {
                    "exact": 8 if passed else 6,
                    "total": 8,
                },
            },
            "reviewed_one_to_one_direct_enum_quadrants": {
                "expected_directed_sources": 48,
                "recovered_directed_sources": 48,
                "both_gold": 48 if passed else 41,
                "first_only_gold": 0 if passed else 2,
                "second_only_gold": 0 if passed else 1,
                "both_wrong_same": 0 if passed else 3,
                "both_wrong_different": 0 if passed else 1,
            },
            "parity_gate": {"passed": passed, "criteria": {}},
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-judge-v6-parity", str(first), str(second)],
    )

    assert result.exit_code == (0 if passed else 1)
    assert "strict prompt STRICT_RELATIONSHIP_UNIT_TWO_STEP_V1" in result.output
    assert "ablation ffffffffffff" in result.output
    assert "fixed common call inputs true" in result.output
    assert "binary accept/reject" in result.output
    assert "exact relation enum" in result.output
    assert "Accepted source sets: exact" in result.output
    assert "Multi-member agreement: binary" in result.output
    assert "Reviewed 1:1 direct Gold split" in result.output
    assert "Parity gate: " + ("PASS" if passed else "FAIL") in result.output


def test_task2_judge_v5_adjudication_renders_read_only_summary(
    monkeypatch, tmp_path
):
    ledgers = [tmp_path / name for name in ("teacher.json", "a.json", "b.json")]
    for ledger in ledgers:
        ledger.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_build(values, *, teacher_run_id):
        captured["ledgers"] = values
        captured["teacher_run_id"] = teacher_run_id
        return _task2_adjudication_report()

    monkeypatch.setattr(
        command, "build_task2_judge_adjudication_queue_v5", fake_build
    )
    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "task2-judge-v5-adjudication",
            "--teacher-run-id",
            "teacher-run",
            *[
                argument
                for ledger in ledgers
                for argument in ("--judge-ledger", str(ledger))
            ],
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "ledgers": ledgers,
        "teacher_run_id": "teacher-run",
    }
    assert "Adjudication queue: total 17 · 3 judge ledgers" in result.output
    assert "249 candidate pairs · replay dddddddddddd" in result.output
    assert "teacher is a reference only, not Gold" in result.output
    assert "no relabeling · existing labels remain unchanged" in result.output


def test_task2_judge_v5_adjudication_summary_orders_distributions(
    monkeypatch, tmp_path
):
    ledgers = [tmp_path / "first.json", tmp_path / "second.json"]
    for ledger in ledgers:
        ledger.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "build_task2_judge_adjudication_queue_v5",
        lambda values, *, teacher_run_id: _task2_adjudication_report(),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "task2-judge-v5-adjudication",
            "--teacher-run-id",
            "teacher-run",
            "--judge-ledger",
            str(ledgers[0]),
            "--judge-ledger",
            str(ledgers[1]),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Priorities: P0=5 · P1=10 · P2=2" in result.output
    assert "Reasons: A_REASON=13 · Z_REASON=4" in result.output
    assert "Existing boundaries: A_BOUNDARY=8 · Z_BOUNDARY=9" in result.output


def test_task2_judge_v5_adjudication_reports_builder_error(
    monkeypatch, tmp_path
):
    ledgers = [tmp_path / "first.json", tmp_path / "second.json"]
    for ledger in ledgers:
        ledger.write_text("{}", encoding="utf-8")

    def fail_build(values, *, teacher_run_id):
        raise command.Task2AdjudicationQueueV5Error("different replay freezes")

    monkeypatch.setattr(
        command, "build_task2_judge_adjudication_queue_v5", fail_build
    )
    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "task2-judge-v5-adjudication",
            "--teacher-run-id",
            "teacher-run",
            "--judge-ledger",
            str(ledgers[0]),
            "--judge-ledger",
            str(ledgers[1]),
        ],
    )

    assert result.exit_code == 1
    assert "Task 2 judge v5 adjudication error" in result.stderr
    assert "different replay freezes" in result.stderr


def test_task2_judge_v5_adjudication_json_is_deterministic_full_report(
    monkeypatch, tmp_path
):
    ledgers = [tmp_path / "first.json", tmp_path / "second.json"]
    for ledger in ledgers:
        ledger.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "build_task2_judge_adjudication_queue_v5",
        lambda values, *, teacher_run_id: _task2_adjudication_report(),
    )
    arguments = [
        "semantic",
        "task2-judge-v5-adjudication",
        "--teacher-run-id",
        "teacher-run",
        "--judge-ledger",
        str(ledgers[0]),
        "--judge-ledger",
        str(ledgers[1]),
        "--json",
    ]

    first = runner.invoke(command.eval_app, arguments)
    second = runner.invoke(command.eval_app, arguments)

    assert first.exit_code == second.exit_code == 0
    assert first.output == second.output
    decoded = json.loads(first.output)
    assert decoded == _task2_adjudication_report()
    assert "Adjudication queue:" not in first.output


def test_task2_judge_v5_adjudication_requires_two_ledgers_before_build(
    monkeypatch, tmp_path
):
    ledger = tmp_path / "only.json"
    ledger.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        command,
        "build_task2_judge_adjudication_queue_v5",
        lambda *args, **kwargs: pytest.fail("minimum must fail before build"),
    )

    result = runner.invoke(
        command.eval_app,
        [
            "semantic",
            "task2-judge-v5-adjudication",
            "--teacher-run-id",
            "teacher-run",
            "--judge-ledger",
            str(ledger),
        ],
    )

    assert result.exit_code != 0
    assert "at least two V5 judge" in result.stderr


def test_task2_status_renders_v3_when_no_v1_ledgers_exist(tmp_path):
    directory = tmp_path / "task2-retrieval-v3"
    directory.mkdir()
    record = _task2_v3_record()
    record["lock"] = {"corpus_locked": True}
    (directory / "v3.json").write_text(json.dumps(record), encoding="utf-8")

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "No Task 2 V1 discovery runs found" in result.output
    assert "V3 retrieval · ollama:qwen3.6:35b-a3b" in result.output
    assert "UNVERIFIED" in result.output
    assert "LOCKED" not in result.output
    assert "group co-membership 56/56" in result.output


def test_task2_status_renders_v4_candidate_and_verifier_rows(tmp_path):
    directory = tmp_path / "task2-retrieval-v4"
    directory.mkdir()
    record = _task2_v4_record()
    record["lock"] = {"corpus_locked": True}
    (directory / "v4.json").write_text(json.dumps(record), encoding="utf-8")

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "V4 candidate→verify · ollama:qwen3.6:35b-a3b" in result.output
    assert "UNVERIFIED" in result.output
    assert "candidate recall@3 56/56" in result.output
    assert "final co-membership 56/56" in result.output
    assert "Stage A 2.000s · Stage B 1.500s" in result.output


def test_task2_status_renders_candidate_and_judge_v5_rows(tmp_path):
    candidate_directory = tmp_path / "task2-candidate-ablation-v5"
    candidate_directory.mkdir()
    candidate = _task2_candidate_v5_record()
    (candidate_directory / "candidate.json").write_text(
        json.dumps(candidate), encoding="utf-8"
    )
    judge_directory = tmp_path / "task2-judge-replay-v5"
    judge_directory.mkdir()
    judge = _task2_judge_v5_record()
    (judge_directory / "judge.json").write_text(json.dumps(judge), encoding="utf-8")

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "V5 candidate-only TOP_5 · ollama:qwen3.6:35b-a3b" in result.output
    assert "directed recall 63/64" in result.output
    assert "V5 common-candidate judge · ollama:qwen3.6:35b-a3b" in result.output
    assert "249 pairs · contract VALID" in result.output
    assert "partition-induced binary proxy TP/FP/TN/FN 62/1/184/2" in result.output
    assert "group-induced enum 230/249" in result.output
    assert "calls 11/11 · input 0.200s · pipeline 9.000s" in result.output


def test_task2_status_renders_judge_v5_pairwise_parity(monkeypatch, tmp_path):
    directory = tmp_path / "task2-judge-replay-v5"
    directory.mkdir()
    first = _task2_judge_v5_record()
    second = _task2_judge_v5_record()
    second["run_id"] = "judge-v5-run-2"
    second["started_at"] = "2026-08-03T23:41:00Z"
    second["provider"] = {"provider": "codex_chatgpt", "model": "gpt-5.6-sol"}
    (directory / "first.json").write_text(json.dumps(first), encoding="utf-8")
    (directory / "second.json").write_text(json.dumps(second), encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_judge_replay_v5_records",
        lambda _first, _second: {
            "fixed_call_inputs_identical": True,
            "binary_accept_reject_agreement": {"exact": 244, "total": 249},
            "exact_enum_agreement": {"exact": 225, "total": 249},
            "source_accepted_set_agreement": {
                "exact": 52,
                "total": 56,
                "macro_jaccard": 0.95,
            },
            "multi_member_agreement": {
                "pair_binary_accept_reject": {"exact": 14, "total": 16},
                "pair_enum": {"exact": 12, "total": 16},
                "source_accepted_set": {"exact": 7, "total": 8},
            },
            "reviewed_one_to_one_direct_enum_quadrants": {
                "recovered_directed_sources": 48,
                "both_gold": 44,
            },
            "parity_gate": {"passed": False},
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert (
        "V5 judge parity · ollama:qwen3.6:35b-a3b ↔ "
        "codex_chatgpt:gpt-5.6-sol · fixed common inputs true · gate FAIL"
        in result.output
    )
    assert "binary accept/reject 244/249" in result.output
    assert "exact enum 225/249" in result.output
    assert "reviewed 1:1 both Gold 44/48" in result.output
    assert "multi-member binary 14/16 · enum 12/16" in result.output


def test_task2_status_renders_v6_and_same_provider_v5_ablation(tmp_path):
    v5_directory = tmp_path / "task2-judge-replay-v5"
    v5_directory.mkdir()
    (v5_directory / "v5.json").write_text(
        json.dumps(_task2_judge_v5_record()), encoding="utf-8"
    )
    v6_directory = tmp_path / "task2-judge-replay-v6"
    v6_directory.mkdir()
    (v6_directory / "v6.json").write_text(
        json.dumps(_task2_judge_v6_record()), encoding="utf-8"
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "V6 strict-boundary judge · ollama:qwen3.6:35b-a3b" in result.output
    assert "prompt STRICT_RELATIONSHIP_UNIT_TWO_STEP_V1" in result.output
    assert "protocol eeeeeeeeeeee · ablation ffffffffffff" in result.output
    assert "partition-induced binary proxy TP/FP/TN/FN 58/20/165/6" in result.output
    assert "V5→V6 prompt ablation · ollama:qwen3.6:35b-a3b" in result.output
    assert "identical replay dddddddddddd" in result.output
    assert "binary proxy ΔTP/FP/TN/FN -4/+19/-19/+4" in result.output
    assert "not independently reviewed semantic-pair accuracy" in result.output
    assert "Δenum exact -25 · Δsource-set exact -8" in result.output
    assert "multi ΔTP/FP/TN/FN -1/-5/+5/+1" in result.output
    assert "pipeline ×1.333 (V6/V5)" in result.output


def test_task2_status_suppresses_v5_v6_ablation_for_different_replay(tmp_path):
    v5_directory = tmp_path / "task2-judge-replay-v5"
    v5_directory.mkdir()
    (v5_directory / "v5.json").write_text(
        json.dumps(_task2_judge_v5_record()), encoding="utf-8"
    )
    v6 = _task2_judge_v6_record()
    v6_bundle = v6["candidate_bundle"]
    assert isinstance(v6_bundle, dict)
    v6_bundle["replay_freeze_digest"] = "9" * 64
    v6_directory = tmp_path / "task2-judge-replay-v6"
    v6_directory.mkdir()
    (v6_directory / "v6.json").write_text(json.dumps(v6), encoding="utf-8")

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "V6 strict-boundary judge" in result.output
    assert "V5→V6 prompt ablation" not in result.output


def test_task2_status_renders_v6_pairwise_parity_for_same_ablation(
    monkeypatch, tmp_path
):
    directory = tmp_path / "task2-judge-replay-v6"
    directory.mkdir()
    first = _task2_judge_v6_record()
    second = _task2_judge_v6_record()
    second["run_id"] = "judge-v6-run-2"
    second["started_at"] = "2026-08-03T23:51:00Z"
    second["provider"] = {"provider": "codex_chatgpt", "model": "gpt-5.6-sol"}
    (directory / "first.json").write_text(json.dumps(first), encoding="utf-8")
    (directory / "second.json").write_text(json.dumps(second), encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_judge_replay_v6_records",
        lambda _first, _second: {
            "ablation_freeze_digest": "f" * 64,
            "fixed_call_inputs_identical": True,
            "binary_accept_reject_agreement": {"exact": 243, "total": 249},
            "exact_enum_agreement": {"exact": 226, "total": 249},
            "source_accepted_set_agreement": {
                "exact": 52,
                "total": 56,
                "macro_jaccard": 0.96,
            },
            "multi_member_agreement": {
                "pair_binary_accept_reject": {"exact": 31, "total": 33},
                "pair_enum": {"exact": 28, "total": 33},
                "source_accepted_set": {"exact": 7, "total": 8},
            },
            "reviewed_one_to_one_direct_enum_quadrants": {
                "recovered_directed_sources": 48,
                "both_gold": 43,
            },
            "parity_gate": {"passed": False},
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert (
        "V6 judge parity · ollama:qwen3.6:35b-a3b ↔ "
        "codex_chatgpt:gpt-5.6-sol · ablation ffffffffffff · "
        "fixed common inputs true · gate FAIL"
        in result.output
    )
    assert "binary accept/reject 243/249 · exact enum 226/249" in result.output
    assert "accepted source sets 52/56 · Jaccard 0.960" in result.output
    assert "reviewed 1:1 both Gold 43/48" in result.output
    assert "multi-member binary 31/33 · enum 28/33" in result.output


def test_task2_status_suppresses_v6_parity_for_different_ablation(
    monkeypatch, tmp_path
):
    directory = tmp_path / "task2-judge-replay-v6"
    directory.mkdir()
    first = _task2_judge_v6_record()
    second = _task2_judge_v6_record()
    second["run_id"] = "judge-v6-run-2"
    second["started_at"] = "2026-08-03T23:51:00Z"
    second["provider"] = {"provider": "codex_chatgpt", "model": "gpt-5.6-sol"}
    second_prompt = second["prompt_ablation"]
    assert isinstance(second_prompt, dict)
    second_prompt["ablation_freeze_digest"] = "8" * 64
    (directory / "first.json").write_text(json.dumps(first), encoding="utf-8")
    (directory / "second.json").write_text(json.dumps(second), encoding="utf-8")
    monkeypatch.setattr(
        command,
        "compare_task2_judge_replay_v6_records",
        lambda _first, _second: pytest.fail(
            "different ablation freezes must not be compared"
        ),
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert result.output.count("V6 strict-boundary judge") == 2
    assert "V6 judge parity" not in result.output


def test_task2_status_strictly_self_validates_and_renders_v7(
    monkeypatch, tmp_path
):
    directory = tmp_path / "task2-judge-replay-v7"
    directory.mkdir()
    record = _task2_judge_v7_record()
    (directory / "v7.json").write_text(json.dumps(record), encoding="utf-8")
    validated: list[object] = []

    def fake_validate(value):
        validated.append(value)
        return {
            "valid": True,
            "canonical_pair_count": 169,
            "call_count": 8,
            "evidence_freeze_digest": "4" * 64,
        }

    monkeypatch.setattr(command, "validate_task2_judge_replay_v7_record", fake_validate)

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert len(validated) == 1
    assert validated[0]["run_id"] == "judge-v7-run"
    assert "V7 canonical evidence judge · ollama:qwen3.6:35b-a3b" in result.output
    assert "strict self-validation VALID · thinking=false" in result.output
    assert "canonicalization 249→169 canonical pairs · calls 8/8" in result.output
    assert "canonical evidence resolved/abstain/missing 160/9/0" in result.output
    assert "projected directed source sets 50/56" in result.output
    assert "evaluation JUDGE_ABLATION_ONLY · no scale promotion" in result.output


def test_task2_status_reports_v7_invalid_record_as_unavailable(
    monkeypatch, tmp_path
):
    directory = tmp_path / "task2-judge-replay-v7"
    directory.mkdir()
    record = _task2_judge_v7_record(contract_valid=False)
    (directory / "v7-invalid.json").write_text(json.dumps(record), encoding="utf-8")

    def reject_record(value):
        raise command.Task2JudgeReplayV7Error("retained call evidence is invalid")

    monkeypatch.setattr(command, "validate_task2_judge_replay_v7_record", reject_record)

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "strict self-validation UNAVAILABLE · contract INVALID" in result.output
    assert "retained call evidence is invalid" in result.output
    assert "canonicalization 249→169" not in result.output


def test_task2_status_strictly_validates_and_renders_contract_valid_v8(
    monkeypatch, tmp_path
):
    directory = tmp_path / "task2-judge-replay-v8"
    directory.mkdir()
    record = _task2_judge_v8_record()
    (directory / "v8.json").write_text(json.dumps(record), encoding="utf-8")
    validated: list[object] = []

    def fake_validate(value):
        validated.append(value)
        return {
            "integrity_valid": True,
            "contract_valid": True,
            "status": "VALID",
            "canonical_pair_count": 169,
            "provider_call_count": 18,
            "input_freeze_digest": "f" * 64,
        }

    monkeypatch.setattr(command, "validate_task2_judge_replay_v8_record", fake_validate)

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert len(validated) == 1
    assert validated[0]["run_id"] == "judge-v8-run"
    assert "V8 staged canonical judge · ollama:qwen3.6:35b-a3b" in result.output
    assert "strict integrity VALID · contract VALID · thinking=false" in result.output
    assert "canonicalization 249→169 canonical pairs" in result.output
    assert "outcomes FINAL/ABSTAIN/INVALID_EVIDENCE/MISSING_DUE_CALL" in result.output
    assert "evaluation JUDGE_ABLATION_ONLY · no scale promotion" in result.output


def test_task2_status_v8_integrity_valid_contract_failure_is_unavailable(
    monkeypatch, tmp_path
):
    directory = tmp_path / "task2-judge-replay-v8"
    directory.mkdir()
    record = _task2_judge_v8_record(contract_valid=False)
    (directory / "v8-invalid.json").write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(
        command,
        "validate_task2_judge_replay_v8_record",
        lambda value: {
            "integrity_valid": True,
            "contract_valid": False,
            "status": "PROVIDER_ERROR",
            "canonical_pair_count": 169,
            "provider_call_count": 18,
        },
    )

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "strict integrity VALID · contract INVALID · metrics UNAVAILABLE" in result.output
    assert "retained status PROVIDER_ERROR · calls 18/18" in result.output
    assert "canonicalization 249→169" not in result.output


def test_task2_status_v8_tamper_validation_failure_is_unavailable(
    monkeypatch, tmp_path
):
    directory = tmp_path / "task2-judge-replay-v8"
    directory.mkdir()
    record = _task2_judge_v8_record()
    (directory / "v8-tampered.json").write_text(json.dumps(record), encoding="utf-8")

    def reject(value):
        raise command.Task2JudgeReplayV8Error("retained stage schedule was altered")

    monkeypatch.setattr(command, "validate_task2_judge_replay_v8_record", reject)

    result = runner.invoke(
        command.eval_app,
        ["semantic", "task2-status", "--ledger-dir", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "strict integrity UNAVAILABLE · metrics UNAVAILABLE" in result.output
    assert "retained stage schedule was altered" in result.output
    assert "canonicalization 249→169" not in result.output
