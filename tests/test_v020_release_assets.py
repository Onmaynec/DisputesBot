import json
from urllib.request import Request, urlopen


def test_v020_release_is_published_with_expected_assets() -> None:
    request = Request(
        "https://api.github.com/repos/Onmaynec/DisputesBot/releases/tags/v0.20.0",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DisputesBot-release-verification",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)

    assert payload["tag_name"] == "v0.20.0"
    assert payload["draft"] is False
    assert payload["prerelease"] is False
    assets = {asset["name"] for asset in payload["assets"]}
    assert "disputes_bot-0.20.0-py3-none-any.whl" in assets
    assert "disputes_bot-0.20.0.tar.gz" in assets
