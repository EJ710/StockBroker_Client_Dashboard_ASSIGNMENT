"""Stock Broker Client Web Dashboard — backend package.

A small FastAPI application that provides:

  * Passwordless email + OTP authentication (JWT sessions)
  * A catalogue of 5 supported stocks
  * Per-user stock subscriptions (watchlists)
  * A server-side price engine that random-walks prices once per second
  * A WebSocket stream that pushes live prices to each connected client for
    *their* subscribed stocks, so multiple users update asynchronously.

See ../README.md and ../docs/ARCHITECTURE.md for the full picture.
"""
