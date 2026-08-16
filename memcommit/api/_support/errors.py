"""Stable projection helpers for public API failures."""


def raise_public(error_type: type[Exception], error: BaseException) -> None:
    raise error_type(str(error)) from error


__all__ = ["raise_public"]

