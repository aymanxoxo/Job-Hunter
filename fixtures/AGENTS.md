# fixtures - deterministic sample data

## Contents
- `jobs.json` - mock connector job fixture used by C-018 and still suitable for the C-039 walking
  skeleton.

## Contracts
- Fixtures are deterministic and contain no credentials or real private user data.
- Keep fixture records small, explicit, and valid against `core.models.Job`.
- `jobs.json` records use `source = "mock"`; `MockConnector` also enforces this on load.

## Pointers
- Parent: [../AGENTS.md](../AGENTS.md)
- Job model: [../core/models/job.py](../core/models/job.py)
