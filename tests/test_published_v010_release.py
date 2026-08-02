import json
import urllib.request

RELEASE_API = (
    "https://api.github.com/repos/Onmaynec/DisputesBot/releases/tags/v0.10.0"
)


def test_published_v010_release_contains_distributions() -> None:
    request = urllib.request.Request(
        RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DisputesBot-release-verification",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
        payload = json.load(response)

    asset_names = {asset["name"] for asset in payload["assets"]}
    print(f"Release URL: {payload['html_url']}")
    print(f"Release assets: {sorted(asset_names)}")

    assert payload["tag_name"] == "v0.10.0"
    assert payload["draft"] is False
    assert payload["prerelease"] is False
    assert "disputes_bot-0.10.0-py3-none-any.whl" in asset_names
    assert "disputes_bot-0.10.0.tar.gz" in asset_names
