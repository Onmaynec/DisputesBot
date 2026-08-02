import json
from urllib.request import Request, urlopen


def test_v019_release_is_published_with_distributions() -> None:
    request = Request(
        "https://api.github.com/repos/Onmaynec/DisputesBot/releases/tags/v0.19.0",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DisputesBot-release-verification",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)

    assert payload["tag_name"] == "v0.19.0"
    assert payload["draft"] is False
    assert payload["prerelease"] is False
    asset_names = {asset["name"] for asset in payload["assets"]}
    assert asset_names == {
        "disputes_bot-0.19.0-py3-none-any.whl",
        "disputes_bot-0.19.0.tar.gz",
    }
