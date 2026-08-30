# Future SaaS Architecture

A future control plane coordinates isolated trading nodes; it does not become the broker execution
process.

```text
Control Plane
  |-- configuration / entitlements / signed strategy packages / telemetry
  |-- Trading Node fx01 -> one isolated broker account
  |-- Trading Node fx02 -> one isolated broker account
  `-- Trading Node fx03 -> one isolated broker account
```

The control plane will own customer/tenant identity, node enrollment and identity, licensing,
subscriptions/billing, approved strategy packages, remote configuration, aggregate telemetry, and
secure signed updates. Each node owns broker-account isolation, local broker credentials, risk and
execution state, local safety controls, and degraded/offline fail-closed behavior.

Broker passwords should remain on the customer node and never be transmitted to the control plane.
Remote configuration must be authenticated, versioned, authorized, rollback-capable, and unable to
weaken node-local hard limits without explicit policy. Multi-tenancy, billing, and licensing are not
implemented in the bootstrap.
