"""Versioned ordinary checkpoints for accepted external document changes."""

from uuid import UUID


def validate_external_change_identity(args):
    record = args.get("sync_operation")
    try:
        if (
            not isinstance(record, dict)
            or set(record)
            != {"version", "uid", "direction", "origin", "trigger", "files"}
            or type(record["version"]) is not int
            or record["version"] not in {1, 2}
            or record["direction"] != "inbound"
            or record["origin"] != "external_file_change"
            or str(UUID(record["uid"])) != record["uid"]
            or set(record["trigger"]) != {"kind", "operation"}
            or record["trigger"]["kind"]
            not in {"MANUAL", "OPERATION_START", "OPERATION_END"}
            or not isinstance(record["trigger"]["operation"], str)
            or not record["trigger"]["operation"]
            or not isinstance(record["files"], list)
            or not record["files"]
            or any(not isinstance(path, str) or not path for path in record["files"])
            or not isinstance(args.get("command_contexts"), list)
            or not args["command_contexts"]
            or any(
                not isinstance(member, dict)
                or set(member) != {"uid", "name"}
                or not isinstance(member["name"], str)
                or not member["name"]
                or str(UUID(member["uid"])) != member["uid"]
                for member in args["command_contexts"]
            )
            or len({member["uid"] for member in args["command_contexts"]})
            != len(args["command_contexts"])
            or len({member["name"] for member in args["command_contexts"]})
            != len(args["command_contexts"])
        ):
            raise ValueError("Invalid external-change checkpoint identity.")
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid external-change checkpoint identity.") from error
    return record["uid"]
