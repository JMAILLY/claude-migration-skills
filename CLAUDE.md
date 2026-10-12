# Repository rules

## No real project names — ever

This repository is public. Never mention any real project, client, site,
agency, internal host or ticket/MR number in anything committed or published:
skill files, references, templates, README, CHANGELOG, commit messages, tags,
GitHub release notes.

- Refer to a real-world run generically: "Project A", "a client project",
  "one reference project". Keep the lesson, drop the origin.
- Use placeholders for hosts and identifiers (`gitlab.example.com`, `my_theme`,
  `my_module`).
- Before every commit and release, check the diff, the message and the notes
  for names of local projects (directories under `~/Documents/projects/`).
  The local `pre-commit` / `commit-msg` hooks enforce this.
