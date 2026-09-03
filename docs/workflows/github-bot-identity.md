# GitHub bot identity

Public writes the pipeline makes on GitHub are attributed to the `pocketpal-dev-team[bot]` GitHub App, so anyone reading a PR can tell automation from the maintainer. The app is owned by the maintainer's account: <https://github.com/settings/apps/pocketpal-dev-team>.

| Action | Identity | How |
| --- | --- | --- |
| `pr create`, `pr comment`, `issue comment`, `pr review --comment` / `--request-changes` | bot | `tools/ghb <gh args>` |
| `pr review --approve`, `pr merge`, releases | operator | plain `gh` (`ghb` refuses these) |
| commits, pushes | operator | unchanged (SSH) |
| reads (`pr view`, `api`, …) | either | plain `gh` is fine |

## App configuration (GitHub side)

- Repository permissions: Pull requests **read & write**, Issues **read & write**, Contents **read**, Metadata **read**, Actions **read**. No account permissions, no webhook.
- Install on the maintainer account, "Only select repositories": `a-ghorbani/pocketpal-ai` (add `pocketpal-dev-team` if bot comments are wanted there).
- Profile: avatar, description, and the homepage pointing at this repo, so the `[bot]` badge links back to the workflow that produced the write.

## Machine setup (once per operator machine)

```bash
mkdir -p ~/.config/pocketpal-dev-team
# 1. download a private key from the app's settings page into that directory
#    (keeps its name, e.g. pocketpal-dev-team.<date>.private-key.pem); chmod 600 it
# 2. record the App ID shown at the top of the settings page
printf 'GH_APP_ID=%s\n' <App ID> > ~/.config/pocketpal-dev-team/env
# 3. verify
tools/gh-app-token.sh --info
```

The installation id is discovered from the key; set `GH_APP_INSTALLATION_ID` in the env file only if the app is installed on more than one account.

`tools/gh-app-token.sh` mints an installation token (one-hour lifetime) and caches it under `~/.cache/pocketpal-dev-team/`. `tools/ghb` runs `gh` with that token. The key and the cache are under `Read` deny rules in `.claude/settings.json`; agents never see either.

## Behaviour to know

- Writes made with the installation token trigger Actions workflows normally, unlike the in-workflow `GITHUB_TOKEN`. CI on bot-created PRs runs.
- The bot has its own API rate limit, separate from the operator's.
- The bot cannot approve a PR it authored, and `ghb` refuses approvals anyway. Approval and merge remain a human decision on the operator's account.
- `ghb` exits 3 when the bot is not configured. Callers must record the write as a pending condition, not fall back to plain `gh`: a write posted as the operator defeats the purpose.
- `tools/fetch-pr-apk.sh` can use the same token when needed: `GH_TOKEN=$(tools/gh-app-token.sh) tools/fetch-pr-apk.sh <pr>`.
- Key rotation: generate a new key on the settings page, drop it in the config directory, delete the old one there and on GitHub, then `tools/gh-app-token.sh --force`.
