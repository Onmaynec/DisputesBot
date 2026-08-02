import urllib.request
from json import load

RELEASE_API = (
    "https://api.github.com/repos/Onmaynec/DisputesBot/releases/tags/v0.12.0"
)


def test_published_v012_release_contains_distributions() -> None:
    request = urllib.request.Request(
        RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DisputesBot-release-verification",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
        payload = load(response)

    asset_names = {asset["name"] for asset in payload["assets"]}

    assert payload["tag_name"] == "v0.12.0"
    assert payload["draft"] is False
    assert payload["prerelease"] is False
    assert "disputes_bot-0.12.0-py3-none-any.whl" in asset_names
    assert "disputes_bot-0.12.0.tar.gz" in asset_names
