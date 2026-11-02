# OptiQ Code for GitHub

Mention `@optiq-bot` on an issue and OptiQ Code, running on [OptiQ Cloud](https://mlx-optiq.com/cloud?utm_source=github&utm_medium=readme&utm_campaign=optiq_action), answers with a pull request. It then keeps going on the same pull request when someone comments, reviews it, or CI fails.

## Setup

1. Install the [optiq-bot app](https://github.com/apps/optiq-bot) on the repository.
2. Create a key on your [OptiQ Cloud dashboard](https://cloud.mlx-optiq.com/dashboard/keys?utm_source=github&utm_medium=readme&utm_campaign=optiq_action) and add it as the repository secret `OPTIQ_CLOUD_API_KEY`. New accounts start with free credit.
3. Add this file as `.github/workflows/optiq.yml`:

```yaml
name: OptiQ Code
on:
  issues:
    types: [opened]
  issue_comment:
    types: [created]
  pull_request_review:
    types: [submitted]
  # Name the workflows whose failure the agent should fix.
  workflow_run:
    workflows: [CI]
    types: [completed]
jobs:
  optiq:
    # Skips without using a runner when nobody mentioned the bot.
    if: >-
      github.event_name == 'pull_request_review' ||
      (github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'failure') ||
      contains(github.event.comment.body || github.event.issue.body, '@optiq-bot')
    runs-on: ubuntu-latest
    timeout-minutes: 90
    concurrency: optiq-${{ github.event.issue.number || github.event.pull_request.number || github.event.workflow_run.head_branch }}
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: optiq-bot/optiq-action@v1
        with:
          cloud-api-key: ${{ secrets.OPTIQ_CLOUD_API_KEY }}
          setup: pip install -r requirements.txt
```

Change `setup` to whatever installs your project's dependencies, and `workflows: [CI]` to the name of your own workflow.

## Using it

Write `@optiq-bot` and the request on a new issue or in a comment on one. The bot reacts with 👀, works on a branch called `optiq/issue-<number>`, opens a pull request and links it on the issue.

After that:

- **Comments:** mention `@optiq-bot` on the pull request and it continues the same work.
- **Reviews:** a review with comments or requested changes needs no mention. Approvals do not start a run.
- **CI:** when a workflow you named fails on its pull request, it reads the log and tries to fix it, up to three times. Then it stops and says a person is needed.

The pull request says `Refs #<number>`, not `Closes`, so a person decides when the issue is done. It never merges anything.

## Who can start a run

People with write access to the repository, and anyone listed in `allowed-users`. Everyone else is ignored, as are other bots, quoted text, and pull requests from forks.

## Inputs

| Input | Default | What it does |
| --- | --- | --- |
| `cloud-api-key` | required | Your OptiQ Cloud key. Runs are billed to its account, per token |
| `model` | `glm-5.3-flash` | Which OptiQ Cloud model does the work |
| `setup` | none | Shell command that installs dependencies before the agent starts |
| `trigger` | `@optiq-bot` | The mention that starts a run |
| `allowed-users` | none | Comma-separated logins allowed besides people with write access |
| `max-ci-rounds` | `3` | Attempts at fixing failing CI on one pull request |
| `timeout-minutes` | `60` | When the agent stops |
| `optiq-version` | latest | The `mlx-optiq` version to install |
| `github-token` | the app's token | Use your own token instead of the app. A pull request opened with the default `GITHUB_TOKEN` does not start CI |

## What the agent can reach

Issue text is untrusted, so the design assumes the agent may be misled.

- The GitHub token covers this one repository, expires within the hour and is revoked when the run ends. The agent's commands never receive it; a separate step pushes after the agent finishes.
- The agent's commands run in a sandbox: writes stay in the repository, temp and package caches, credential files are unreadable, secret environment variables are removed, and network access is limited to package registries and git hosts.
- Changes to `.github/workflows` are refused before pushing, and the app has no workflow permission.
- Conversations are saved between runs as encrypted artifacts for 30 days. Deleting them or rotating your Cloud key only means the next run starts fresh.

## Limits

- Runs on Linux runners. Private repositories use your Actions minutes.
- It answers on issues and its own pull requests, not on other pull requests.
- GitHub keeps one waiting run per thread, so a message can lose its run while another is going. The next run reads everything written since the bot last spoke.

## License

[MIT](LICENSE). This covers the code in this repository. OptiQ Cloud has its own terms.
