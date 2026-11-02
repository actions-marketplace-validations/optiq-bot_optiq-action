"""The GitHub token a run works with, and who that token is.

Normally a short-lived token for this one repository from the optiq-bot App, through
OptiQ Cloud: the run proves which repository it is with GitHub's identity token, and
its Cloud key says who is asking. A `github-token` input replaces all of that.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request

TOKEN_URL = "https://cloud.mlx-optiq.com/api/github/token"
AUDIENCE = "optiq-cloud"
APP_LOGIN = "optiq-bot[bot]"


class AuthError(Exception):
    """Why a run has no GitHub token, in words its log can show."""


def _identity_token() -> str:
    url, bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"), os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not url or not bearer:
        raise AuthError("this workflow needs `permissions: id-token: write` for the optiq-bot app")
    req = urllib.request.Request(f"{url}&audience={AUDIENCE}", headers={"Authorization": f"Bearer {bearer}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["value"]


def app_token() -> str:
    body = json.dumps({"identity_token": _identity_token()}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {os.environ['OPTIQ_CLOUD_KEY']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["token"]
    except urllib.error.HTTPError as e:
        try:
            why = json.load(e)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            why = f"HTTP {e.code}"
        raise AuthError(why) from None


def use_token() -> bool:
    """Put the token in GH_TOKEN for every `gh` call, hidden in logs. True when it came
    from the App, which means it should be revoked when the run ends."""
    given = os.environ.get("INPUT_GITHUB_TOKEN")
    token = given or app_token()
    print(f"::add-mask::{token}", flush=True)
    os.environ["GH_TOKEN"] = token
    return not given


def revoke() -> None:
    """A token that is gone cannot leak. It would expire within the hour anyway."""
    subprocess.run(["gh", "api", "-X", "DELETE", "installation/token"], capture_output=True)


def identity() -> dict:
    """{login, id, names}: `names` holds every way GitHub prints this account, since
    an App signs its comments differently in different places."""
    user = subprocess.run(["gh", "api", "user"], text=True, capture_output=True)
    if user.returncode == 0:
        me = json.loads(user.stdout)
        return {"login": me["login"], "id": me["id"], "names": {me["login"]}}
    bot = json.loads(subprocess.run(["gh", "api", f"users/{APP_LOGIN}"], check=True, text=True, capture_output=True).stdout)
    slug = APP_LOGIN.removesuffix("[bot]")
    return {"login": APP_LOGIN, "id": bot["id"], "names": {APP_LOGIN, slug, f"app/{slug}"}}
