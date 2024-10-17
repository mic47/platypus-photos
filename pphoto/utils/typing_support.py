import typing as t


def assert_never(x: t.NoReturn) -> t.NoReturn:
    assert False, f"Unhandled type: {type(x).__name__}"
