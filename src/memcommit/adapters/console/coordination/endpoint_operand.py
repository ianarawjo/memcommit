"""Console coordination for directional endpoint operand spellings."""

from __future__ import annotations


def choose_endpoint_operand(
    positional: str | None,
    *,
    role: str,
    options: tuple[tuple[str, str | None], ...],
) -> str | None:
    """Choose one endpoint spelling without allowing silent precedence.

    Directional commands may expose both positional operands and explicit
    compatibility options. Mutation-capable adapters reject duplicate
    spellings before capturing current Context state so argv order cannot
    silently select a different Source, Target, Criteria, or Result.
    """

    supplied: list[tuple[str, str]] = []
    if positional is not None:
        supplied.append(("positionally", positional))
    supplied.extend((label, value) for label, value in options if value is not None)
    if len(supplied) > 1:
        labels = [label for label, _value in supplied]
        if labels[0] == "positionally":
            option_labels = " and ".join(labels[1:])
            raise ValueError(
                f"{role} was supplied both positionally and with {option_labels}."
            )
        raise ValueError(
            f"{role} was supplied with more than one option: "
            + " and ".join(labels)
            + "."
        )
    return supplied[0][1] if supplied else None


__all__ = ["choose_endpoint_operand"]
