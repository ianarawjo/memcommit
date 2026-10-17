"""Effective exact/subtree/Profile policies and one selected-set toggle."""

from memcommit.application.operations.mem_sync.model import AutomaticSyncChange


def automatic_sync_enabled(name, uid, policies, inventory):
    matching = []
    for rule in policies:
        scope, root = rule["scope"], rule["name"]
        if scope == "all":
            matching.append((0, rule))
            continue
        bound_uid = inventory.get(root)
        if bound_uid is not None and bound_uid != rule["uid"]:
            continue
        if scope == "recursive" and bound_uid is None and name != root:
            continue
        if scope == "exact":
            if root == name and rule["uid"] == uid:
                matching.append((len(root.split("/")) * 2 + 1, rule))
        elif name == root or name.startswith(root + "/"):
            matching.append((len(root.split("/")) * 2, rule))
    return max(matching, key=lambda pair: pair[0])[1]["enabled"] if matching else False


def automatic_document_exclusions(connections, policies, inventory):
    """Disabled documents stay outside a parent's automatic mirror claim."""
    enabled = {
        name
        for name, uid in inventory.items()
        if automatic_sync_enabled(name, uid, policies, inventory)
    }
    paths = {
        path
        for connection in connections
        if not any(name in enabled for name in connection.member_names)
        for path in connection.paths
    }
    paths.update(
        name if name.lower().endswith(".md") else name + ".md"
        for name in inventory
        if name not in enabled
    )
    prefixes = {
        rule["name"]
        for rule in policies
        if rule["scope"] == "recursive"
        and not rule["enabled"]
        and inventory.get(rule["name"]) == rule["uid"]
        and not any(
            name == rule["name"] or name.startswith(rule["name"] + "/")
            for name in enabled
        )
    }
    return paths, prefixes


def set_automatic_selection(selection, policies, *, enabled):
    """Set a reviewed value explicitly, including an empty Profile-wide scope."""
    if type(enabled) is not bool:
        raise TypeError("Automatic Sync enabled state must be boolean.")
    inventory = dict(selection.inventory)
    states = [
        automatic_sync_enabled(
            name=name,
            uid=inventory[name],
            policies=policies,
            inventory=inventory,
        )
        for name in selection.names
    ]
    chosen = set(selection.names)
    # Clear opposite narrow exceptions inside the selected scope in one save.
    updated = [
        rule
        for rule in policies
        if selection.scope != "all"
        and not (
            rule["name"] in chosen
            and (selection.scope != "exact" or rule["scope"] == "exact")
        )
    ]
    if selection.scope in {"all", "recursive"}:
        updated.append(
            {
                "scope": selection.scope,
                "name": selection.root_name,
                "uid": inventory.get(selection.root_name),
                "enabled": enabled,
            }
        )
    else:
        for name in selection.names:
            updated.append(
                {
                    "scope": "exact",
                    "name": name,
                    "uid": inventory[name],
                    "enabled": enabled,
                }
            )
    return updated, AutomaticSyncChange(
        enabled=enabled,
        context_names=selection.names,
        newly_enabled=sum(not value for value in states) if enabled else 0,
        already_enabled=sum(states) if enabled else 0,
    )


def toggle_automatic_selection(selection, policies):
    inventory = dict(selection.inventory)
    if selection.names:
        enabled = not all(
            automatic_sync_enabled(
                name=name,
                uid=inventory[name],
                policies=policies,
                inventory=inventory,
            )
            for name in selection.names
        )
    else:
        # An empty Profile still owns a future-Context policy that can be disabled.
        enabled = not any(rule["scope"] == "all" and rule["enabled"] for rule in policies)
    return set_automatic_selection(selection=selection, policies=policies, enabled=enabled)
