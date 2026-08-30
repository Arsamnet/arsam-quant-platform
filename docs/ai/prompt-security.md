# Prompt Security

Financial news, calendar descriptions, scraped pages, support text, and model output are untrusted
data. They are never concatenated as authority-bearing instructions. Provider adapters extract a
small normalized schema and separate system policy from data fields.

Defenses include allowlisted fields/enums, decimal bounds, length/count limits, extra-field
rejection, no executable/tool/URL fields, no secrets in prompts, output validation before domain
conversion, and deterministic risk after AI. Instructions embedded in news cannot change trading
mode, limits, identity, configuration, or execution behavior.

Future red-team tests should cover instruction injection, delimiter confusion, oversized input,
Unicode obfuscation, data exfiltration requests, tool/URL smuggling, schema expansion, and model
unavailability. Any ambiguity fails closed.
