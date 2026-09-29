"""Project reviewed occurrence mappings; never infer ancestry from similar text."""

import hashlib

from memcommit.application.operations.merge.records import LiteralMergeRound
from memcommit.application.operations.resolve.decisions import (
    resolution_input_uid,
)
from memcommit.core.context import Memory


def project_merge_lineage(rounds, source_uid, target_uid):
    """Follow exact choices and instruction-linked effects across review rounds.

    A provider's reference to an authored instruction proves review derivation,
    not verbatim copying. Only exact dispositions may feed occurrence matching.
    """
    candidate = rounds[0].candidate
    origins = {
        origin.uid: origin
        for origin in candidate.origins
        if isinstance(candidate.original_item(origin.uid), Memory)
    }
    parents = {uid: {uid} for uid in origins}
    dispositions = {}
    retained_targets = {}
    for round in rounds:
        before, after = round.before().memories, round.after().memories
        mapping = dict(round.input_result_uids or ((uid, uid) for uid in before))
        round_candidate = (
            round.candidate if isinstance(round, LiteralMergeRound) else None
        )
        report = round.report if round_candidate else None
        for incoming, baseline in report.memory_matches if report else ():
            if incoming not in mapping and baseline in mapping:
                mapping[incoming] = mapping[baseline]
                for origin in parents.get(incoming, ()):
                    dispositions[(origin, mapping[baseline])] = "ALREADY_PRESENT"
        next_parents = {}
        for uid, result_uid in mapping.items():
            if result_uid in after:
                next_parents.setdefault(result_uid, set()).update(parents.get(uid, ()))
        issues = {issue.uid: issue for issue in round.issues}
        decisions = round.decisions
        instructions = {}
        exact = set()
        round_origins = {
            origin.uid: origin
            for origin in (round_candidate.origins if round_candidate else ())
        }
        for decision in decisions.decisions:
            issue = issues[decision.issue_uid]
            members = issue.item_uids
            if decision.kind in {"CONFIRM", "INTENT"}:
                instructions[resolution_input_uid(decisions, decision.issue_uid)] = (
                    members
                )
                continue
            if decision.kind not in {"KEEP_TARGET", "TAKE_SOURCE", "KEEP_BOTH"}:
                continue
            incoming = [
                uid
                for uid in members
                if uid in round_origins and round_origins[uid].context_uid == source_uid
            ]
            baseline = [
                uid
                for uid in members
                if uid in round_origins and round_origins[uid].context_uid == target_uid
            ]
            for uid in incoming:
                destinations = (
                    [mapping.get(uid, uid)]
                    if decision.kind == "KEEP_BOTH"
                    else [mapping.get(value, value) for value in baseline]
                )
                for dest in destinations:
                    if dest not in after:
                        continue
                    exact.add(dest)
                    if decision.kind == "KEEP_TARGET":
                        # Record the rejected Source association without treating
                        # it as an ancestor of a later semantic rewrite.
                        if isinstance(after[dest], Memory):
                            for origin in parents.get(uid, ()):
                                retained_targets[(origin, dest)] = after[dest].content
                        continue
                    if decision.kind == "TAKE_SOURCE":
                        next_parents[dest] = set(parents.get(uid, ()))
                    else:
                        next_parents.setdefault(dest, set()).update(
                            parents.get(uid, ())
                        )
                    for origin in parents.get(uid, ()):
                        dispositions[(origin, dest)] = decision.kind
        for effect in round.effects:
            dest = effect.memory_uid
            if dest not in after or dest in exact:
                continue
            inherited = next_parents.setdefault(dest, set())
            for ref in effect.source_refs:
                for uid in instructions.get(ref.memory_uid, (ref.memory_uid,)):
                    inherited.update(parents.get(uid, ()))
            # A later semantic edit supersedes an earlier exact disposition.
            for origin in inherited:
                dispositions[(origin, dest)] = "TRANSFORMED"
        parents = next_parents
    final = rounds[-1].after().memories
    for (origin, dest), retained in retained_targets.items():
        if isinstance(final.get(dest), Memory) and final[dest].content == retained:
            parents.setdefault(dest, set()).add(origin)
            dispositions[(origin, dest)] = "KEEP_TARGET"
    edges = []

    def sha(text):
        return hashlib.sha256(text.encode()).hexdigest()

    for dest, ancestors in parents.items():
        if not isinstance(final[dest], Memory):
            continue
        for uid in sorted(ancestors):
            origin = origins[uid]
            if origin.context_uid != source_uid:
                continue
            content = candidate.original_item(origin.uid).content
            disposition = dispositions.get((uid, dest))
            if disposition is None:
                disposition = "NEW" if content == final[dest].content else "TRANSFORMED"
            if (
                disposition not in {"KEEP_TARGET", "TRANSFORMED"}
                and content != final[dest].content
            ):
                disposition = "TRANSFORMED"
            edges.append(
                dict(
                    source_context_uid=source_uid,
                    source_memory_uid=origin.item_uid,
                    target_context_uid=target_uid,
                    target_memory_uid=dest,
                    source_content_sha256=sha(content),
                    target_content_sha256=sha(final[dest].content),
                    disposition=disposition,
                )
            )
    return sorted(
        edges, key=lambda edge: (edge["source_memory_uid"], edge["target_memory_uid"])
    )
