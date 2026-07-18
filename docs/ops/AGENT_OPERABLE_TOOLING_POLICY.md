# Agent-Operable Tooling Policy

Project operations must prefer tools controlled through a CLI, SDK, API, SSH, or reproducible scripts. A provider UI is reserved for account creation, authentication, and explicit approval of sensitive operations.

The agent owns routine resource creation, configuration, execution, result recovery, and shutdown. Platforms that repeatedly require manual navigation should be penalized or rejected. Users must not be required to learn provider interfaces.

No phone number, payment card, or new account may be requested without explicit approval. Every paid resource must have a hard limit, watchdog, result-recovery path, and provider-level shutdown mechanism. An in-container process stop, `shutdown`, or `poweroff` is not evidence that billing stopped.

GitHub activity must represent real, validated work. Empty commits, fabricated activity, invented metrics, placeholder results, and misleading green checks are prohibited.
