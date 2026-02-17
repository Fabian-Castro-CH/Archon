# Archon Skills Catalog

Project-specific and framework skills available for this repository.

## Project Automation Entry Points

- `make dev` / `make dev-docker`: start local development modes.
- `make lint`, `make lint-fe`, `make lint-be`: quality gates.
- `make test`, `make test-fe`, `make test-be`: test workflows.
- `make agent-work-orders`: run the agent work-orders service locally.

## SIA Framework Skills (Available in this repo)

- `create_expert_agent.md`: generate specialized agents.
- `create_agent_cli.py`: CLI scaffolding for expert agents.
- `file_readers/read_docx.py`, `read_xlsx.py`, `read_pdf.py`: zero-setup file extraction tools.
- `read_file.py`: format auto-detection wrapper for file readers.

## Usage Notes

- Keep project-specific process notes in `.sia/knowledge/active/`.
- Add new reusable project automations to this catalog as they are introduced.

## Placeholder for Future Custom Skills

- `TBD`: Archon migration safety verifier.
- `TBD`: MCP contract consistency checker.
- `TBD`: Frontend feature-slice scaffold helper.
