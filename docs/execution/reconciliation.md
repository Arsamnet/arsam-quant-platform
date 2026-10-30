# Demo Execution Reconciliation

The durable Python state machine begins at `pending`, becomes `claimed` exactly once, and then
accepts only reviewed forward transitions. Filled/partially-filled work remains unresolved until a
matching magic/comment order, deal, or position is confirmed. Conflicting IDs, intent facts,
overfills, backwards transitions, and unknown broker status fail closed.

On EA restart, the latest journal entry for every execution is loaded. For claimed, submitted,
filled, partially-filled, or unknown entries, the EA inspects positions and deal history using magic
5050001 and the correlation marker. A match is reported as `position_confirmed`; absence or API
report failure blocks polling. Python independently refuses to deliver more work while claimed,
submitted, filled, partially-filled, unknown, or reconciliation-failed state remains.

This deliberately handles the crash window where the broker accepted an order but Python missed the
response. The same intent is never blindly sent again. Operator resolution must preserve the
execution/intent IDs, retcode, order/deal IDs, fill, prices, protection, and confirmed position state
without recording account login or raw sensitive logs.
