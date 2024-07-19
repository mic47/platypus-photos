from dataclasses import dataclass


@dataclass
class IdentityRowPayload:
    identity: str
    example_md5: str | None
    example_extension: str | None
    updates: int
    last_update: int
