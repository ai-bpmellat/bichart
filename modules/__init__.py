"""
BiChart domain modules (modular monolith).

Each package is a bounded context with a public API. Modules talk through
imports of public surfaces only — not each other's private helpers.
Later, any package can be extracted into its own microservice.
"""
