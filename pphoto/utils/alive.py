from __future__ import annotations

import contextlib
import dataclasses as dc
import datetime as dt
import enum
import functools
import traceback
import typing as t
import types as tp

import dataclasses_json as dj
import typing_extensions as te


class StateEnum(enum.Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    # Following are end states
    FINISHED = "finished"
    UNEXPECTED_FINISH = "unexpected finish"
    ERROR = "error"


@dc.dataclass
class ExceptionInfo(dj.DataClassJsonMixin):
    exc_type: str | None
    exc_val: str | None
    exc_tb: t.List[str] | None


@dc.dataclass
class State(dj.DataClassJsonMixin):
    name: str
    state: StateEnum
    when: float  # noqa: F841
    exception: ExceptionInfo | None  # noqa: F841


class Register:
    def __init__(self) -> None:
        self.log: t.List[State] = []
        self.current_state: t.Dict[str, State] = {}

    def _update(self, item: State) -> None:
        self.log.append(item)
        # TODO: check that transition is valid
        self.current_state[item.name] = item

    def initialize(self, name: str) -> None:
        self._update(State(name, StateEnum.INITIALIZED, dt.datetime.now().timestamp(), None))

    def running(self, name: str) -> None:
        self._update(State(name, StateEnum.RUNNING, dt.datetime.now().timestamp(), None))

    def finished(self, name: str, expected: bool) -> None:
        self._update(
            State(
                name,
                StateEnum.FINISHED if expected else StateEnum.UNEXPECTED_FINISH,
                dt.datetime.now().timestamp(),
                None,
            )
        )

    def error(
        self,
        name: str,
        exc_type: t.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: tp.TracebackType | None,
    ) -> None:
        self._update(
            State(
                name,
                StateEnum.ERROR,
                dt.datetime.now().timestamp(),
                ExceptionInfo(
                    exc_type.__name__ if exc_type is not None else None,
                    str(exc_val) if exc_val is not None else None,
                    traceback.format_list(traceback.extract_tb(exc_tb)) if exc_tb is not None else None,
                ),
            )
        )


def get_state() -> t.Dict[str, State]:
    return _REGISTER.current_state


_REGISTER = Register()

_P = te.ParamSpec("_P")
_OUT = t.TypeVar("_OUT")


class Alive:
    def __init__(self, /, persistent: bool, key: t.List[str | int]) -> None:
        self.persistent = persistent
        self.key = key

    def __call__(
        self, func: t.Callable[_P, t.Coroutine[None, None, _OUT]]
    ) -> t.Callable[_P, t.Coroutine[None, None, _OUT]]:
        @functools.wraps(func)
        async def inner(*args: _P.args, **kwargs: _P.kwargs) -> _OUT:
            key: t.List[t.Any] = []
            for k in self.key:
                if isinstance(k, int):
                    key.append(args[k])
                else:
                    key.append(f"{k}={kwargs[k]}")
            key_str = ", ".join(str(x) for x in key)
            name = f"{func.__name__}({key_str})"
            async with ItIsAlive(name, self.persistent):
                return await func(*args, **kwargs)

        return inner


class ItIsAlive(contextlib.AsyncContextDecorator):

    def __init__(self, name: str, persistent: bool, register: Register | None = None) -> None:
        if register is None:
            self.register = _REGISTER
        else:
            self.register = register
        self.name = name
        self.persistent = persistent
        self.register.initialize(self.name)

    async def __aenter__(self) -> None:
        self.register.running(self.name)

    async def __aexit__(
        self,
        exc_type: t.Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: tp.TracebackType | None,
    ) -> None:
        if exc_tb is None and exc_val is None and exc_type is None:
            self.register.finished(self.name, expected=not self.persistent)
        else:
            self.register.error(self.name, exc_type, exc_val, exc_tb)
