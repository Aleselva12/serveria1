import type { CapabilityContract } from "../types/contracts";

// Optional only for API/planned catalog entries and compatibility with older servers.
export function contractsValid(value: unknown): boolean {
  if (value === undefined) return true;
  const object = (v: unknown) => !!v && typeof v === "object" && !Array.isArray(v);
  const strings = (v: unknown) => Array.isArray(v) && v.every(x => typeof x === "string");
  return Array.isArray(value) && value.every((c: CapabilityContract) => c &&
    typeof c.id === "string" && /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$/.test(c.id) &&
    Number.isInteger(c.version) && c.version > 0 && typeof c.actor === "string" &&
    ["read", "compute", "write", "delegate"].includes(c.effect) && ["safe", "never"].includes(c.retry) &&
    ["generic", "calendar"].includes(c.approval) && typeof c.connected === "boolean" &&
    typeof c.contract_digest === "string" && typeof c.implementation_revision === "string" &&
    strings(c.required_actions) && strings(c.conditional_actions) &&
    object(c.input_schema) && object(c.output_schema) && object(c.native_output_schema) &&
    Array.isArray(c.permissions) && c.permissions.every(p => p && typeof p.action === "string" &&
      ["auto", "confirm", "blocked"].includes(p.policy)));
}
