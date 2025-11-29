# ADK Project Guidelines & Conventions

This doc outlines conventions used in this skeleton:
- Agents live in `src/agents/` and are thin orchestrators.
- Tools live in `src/tools/` and wrap external services (vector DB, KG).
- API layer in `src/api/` interacts with RootAgent (only orchestration).
- Use async/await throughout agents for IO-bound operations.
- Configuration via `adk_config.yaml` and environment variables (.env).
- Keep side effects in tools; agents should be testable with mocks.
