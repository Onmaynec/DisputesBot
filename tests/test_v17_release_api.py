from __future__ import annotations

import json
from urllib.request import Request, urlopen


def test_v17_release_is_published_with_distributions() -> None:
    request = Request(
        "https://api.github.com/repos/Onmaynec/DisputesBot/releases/tags/v0.17.0",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DisputesBot-release-verification",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20) as response:
        payload = json.load(response)

    assert payload["tag_name"] == "v0.17.0"
    assert payload["draft"] is False
    assert payload["prerelease"] is False
    asset_names = {asset["name"] for asset in payload["assets"]}
    assert "disputes_bot-0.17.0-py3-none-any.whl" in asset_names
    assert "disputes_bot-0.17.0.tar.gz" in asset_names
