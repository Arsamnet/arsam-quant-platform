# Synthetic broker-validation fixtures

These files are synthetic engineering data. They are **not FIBOGroup data**, are not captured from
any broker, and provide no broker-compatibility evidence. The valid snapshot is the base for tests
that deterministically derive tick-size, contract-size, volume-step, unsupported calculation-mode,
netting-account, missing-currency, dynamic-quote, and tamper cases. The malformed fixture exercises
strict schema rejection.
