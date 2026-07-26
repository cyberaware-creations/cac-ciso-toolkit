# Security Policy

Thanks for helping keep this project and the people who use it safe. This repository contains Claude plugins and skills — installable bundles that run in others' environments — so we take reports about them seriously.

## Reporting a Vulnerability

Please **do not** open a public issue for security problems, as that discloses the issue before a fix is available.

Instead, use one of the following private channels:

- **Preferred — GitHub private vulnerability reporting:** Go to the **Security** tab of this repository and click **Report a vulnerability**. This opens a private advisory visible only to the maintainers.
- **Email:** ceo@cyberawarecreations.net

When you report, please include as much of the following as you can:

- A description of the issue and why you believe it is a security risk
- The affected plugin, skill, file, or path
- Steps to reproduce, or a proof of concept
- The impact you were able to demonstrate (e.g. data exposure, arbitrary command execution, credential leakage)
- Any suggested remediation, if you have one

## What to Expect

- **Acknowledgement** within 3 business days of your report.
- **An initial assessment** (severity and whether we can reproduce it) within 10 business days.
- **Progress updates** as we work toward a fix.
- **Credit** for your report once the issue is resolved, if you'd like it — let us know how you'd prefer to be named.

We ask that you give us a reasonable window to address the issue before any public disclosure. We're happy to coordinate timing with you.

## Scope

In scope:

- Plugins and skills published in this repository
- Configuration, scripts, and workflows that ship as part of those plugins and skills
- Handling of secrets, tokens, or credentials by anything in this repo

Out of scope:

- Vulnerabilities in third-party dependencies that have no exploitable path through this project (please report those upstream — though we're glad to hear about them so we can update)
- Issues in the Claude platform, Claude Code, or Cowork themselves — report those to Anthropic
- Social engineering, physical attacks, or denial of service against infrastructure not owned by this project

## Safe Harbor

We will not pursue or support legal action against anyone who reports a vulnerability in good faith, follows this policy, avoids privacy violations and data destruction, and gives us a reasonable time to respond before disclosing.

## Supported Versions

This repository tracks the latest published state of each plugin and skill. Security fixes are applied to the current `main` branch; there are no separately maintained release branches. If you're running an older copy, please update to the latest version before reporting.
