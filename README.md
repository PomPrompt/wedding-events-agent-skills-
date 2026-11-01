# PomPrompt — Wedding & Events Agent Skills

A collection of eight AI Agent Skill workflows for wedding planning, budgets, guest RSVP reviews, seating, invitation wording, creative direction, photography briefs, and event-day coordination.

**Official Skills Library:** [Browse all PomPrompt Agent Skills](https://pomprompt.com/skills/)

Each Skill is a self-contained folder with `SKILL.md` and any required accompanying references or optional local scripts. These are **agent instructions and helper files**, not a hosted wedding-planning application. Access to external software, local execution, editing, or image generation depends on the user’s own agent environment and permissions.

## Browse the eight Skills

Each GitHub folder contains the Skill files. The linked PomPrompt pages are intended for human-readable documentation and guidance; check their availability separately before announcing a release.

| Skill | Purpose | Skill files on GitHub | Official PomPrompt page |
| --- | --- | --- | --- |
| Wedding Brief & Timeline | Organize planning decisions, milestones and dependencies | [View files](skills/wedding-brief-timeline/) | [Wedding Brief & Timeline guide](https://pomprompt.com/skills/wedding-brief-timeline/) |
| Wedding Budget Scenarios | Reconcile known costs and compare scenarios | [View files](skills/wedding-budget-scenario/) | [Wedding Budget Scenarios guide](https://pomprompt.com/skills/wedding-budget-scenario/) |
| Wedding Guest RSVP Audit | Review authorized guest CSV data and count conflicts | [View files](skills/wedding-guest-rsvp-audit/) | [Wedding Guest RSVP Audit guide](https://pomprompt.com/skills/wedding-guest-rsvp-audit/) |
| Wedding Seating Constraints | Prepare and review table allocations against user-provided rules | [View files](skills/wedding-seating-constraints/) | [Wedding Seating Constraints guide](https://pomprompt.com/skills/wedding-seating-constraints/) |
| Wedding Invitation Wording | Draft invitation copy with factual placeholders | [View files](skills/wedding-invitation-wording/) | [Wedding Invitation Wording guide](https://pomprompt.com/skills/wedding-invitation-wording/) |
| Wedding Invitation Art Direction | Prepare visual design briefs, background prompts and print handoffs | [View files](skills/wedding-invitation-art-direction/) | [Wedding Invitation Art Direction guide](https://pomprompt.com/skills/wedding-invitation-art-direction/) |
| Wedding Photo Concept Editor | Prepare photo-session concepts and authorized image-edit briefs | [View files](skills/wedding-photo-concept-editor/) | [Wedding Photo Concept Editor guide](https://pomprompt.com/skills/wedding-photo-concept-editor/) |
| Wedding Day Run Sheet | Structure wedding-day operations, handoffs and scheduling conflicts | [View files](skills/wedding-day-run-sheet/) | [Wedding Day Run Sheet guide](https://pomprompt.com/skills/wedding-day-run-sheet/) |

## Folder layout

```text
skills/
  wedding-brief-timeline/
  wedding-budget-scenario/
  wedding-guest-rsvp-audit/
  wedding-seating-constraints/
  wedding-invitation-wording/
  wedding-invitation-art-direction/
  wedding-photo-concept-editor/
  wedding-day-run-sheet/
```

## How to use

1. Open the folder for the Skill you want.
2. Read its `SKILL.md` and any associated files in `references/`.
3. Follow the installation instructions for your own agent tool, adding the **whole Skill directory** to the appropriate skills location when that tool supports Agent Skills.
4. If a Skill includes `scripts/`, inspect the script and its input requirements before optionally running it in an authorized local Python environment. Simply opening the Skill on GitHub does not execute the script.
5. Provide only the event data necessary for your task. Avoid publishing personal guest details, private photographs, or credentials.

The canonical format is described by the [Agent Skills specification](https://agentskills.io/specification). Product-specific setup depends on your selected agent application.

## Included local helper scripts

Four Skills include optional Python scripts for deterministic checks. Run them only in a local environment you trust, after reviewing the code, input schema, and permissions:

| Skill | Optional script | Purpose |
| --- | --- | --- |
| Wedding Budget Scenarios | `scripts/budget_engine.py` | Calculate and compare provided budget amounts and scenarios. |
| Wedding Guest RSVP Audit | `scripts/audit_rsvp.py` | Review authorized CSV records and reconcile counts. |
| Wedding Seating Constraints | `scripts/seat_solver.py` | Attempt table allocations within specified constraints. |
| Wedding Day Run Sheet | `scripts/audit_run_sheet.py` | Flag timing, resource, handoff, and travel-related scheduling issues. |

These scripts do not run merely because the repository or Skill files are viewed. Availability and execution depend on the agent host and a permitted Python environment. They must not be given personal data unnecessarily.

## Testing and compatibility status

These files are shared for review and use, **not as certified or independently host-tested integrations**. There is no documented end-to-end test evidence here for Claude Code, Codex, Cursor, or any other agent host. Do not assume that a given host will load a Skill or execute its scripts without the appropriate setup, tools, and permissions. Review scheduling, privacy-sensitive, or financial outputs before relying on them.

## What these Skills do not do

They do not automatically book venues, contact guests or vendors, process payments, certify legal or venue requirements, or generate images without the relevant authorized tools. Wedding-day timing and budget decisions still require appropriate human review.

## License and permissions

**MIT License** — see the repository [LICENSE](LICENSE) file. The Skill instructions, original reference documents, and Python helper scripts in this repository are offered under MIT, subject to the publisher having the rights to license the respective content. Each Skill folder also includes a copy of the MIT license for distribution outside this repository.

MIT allows personal and commercial use, modification, and redistribution provided the copyright and license notices are retained. The software and documentation are supplied **as-is**, without warranty. This grant does not transfer ownership of the PomPrompt brand, logo, or trademarks and does not confer rights in separately owned third-party materials.

**Publisher note:** PomPrompt is used here as the publication and copyright attribution. Before making the repository public, the rights holder should confirm that this attribution is accurate and that all included material may be released under MIT. A public repository alone does not establish ownership or remove third-party restrictions.

## Contact

For product information, visit [PomPrompt.com](https://pomprompt.com/). Please do not post real guest lists or private event details in public GitHub issues.
