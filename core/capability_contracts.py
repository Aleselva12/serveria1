"""Versioned executable contracts, independent from LangChain or frontend diagrams."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, JsonValue, model_validator

class CapabilityContract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    version: int = Field(default=1, ge=1)
    actor: str
    name: str
    description: str
    required_actions: tuple[str, ...]
    conditional_actions: tuple[str, ...] = ()
    effect: Literal['read', 'compute', 'write', 'delegate']
    retry: Literal['safe', 'never']
    response_mode: Literal["data", "final"] = "data"
    approval: Literal['generic', 'calendar'] = 'generic'
    input_schema: dict[str, Any]
    native_output_schema: dict[str, Any]
    output_schema: dict[str, Any]

class CapabilityError(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str
    message: str

class CapabilityResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    capability_id: str
    contract_version: int
    status: Literal['ok', 'pending', 'error']
    value: JsonValue = None
    error: CapabilityError | None = None
    approval_id: str | None = None
    @model_validator(mode='after')
    def valid_outcome(self):
        if self.status == 'error' and self.error is None: raise ValueError('Errors need an error descriptor')
        if self.status != 'error' and self.error is not None: raise ValueError('Successful/pending results cannot carry errors')
        if self.status == 'pending' and not self.approval_id: raise ValueError('Pending results need an approval identity')
        return self

    # Compatibility adapters retain domain-native output; never part of the wire contract.
    _native: Any = PrivateAttr(default=None)

    @property
    def native(self): return self._native

    @native.setter
    def native(self, value): self._native = value
