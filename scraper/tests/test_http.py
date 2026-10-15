import httpx
import pytest

from bolidolar.http import FetchError, HttpFetcher


def fetcher(handler, **kwargs) -> tuple[HttpFetcher, list[float]]:  # type: ignore[no-untyped-def]
    sleeps: list[float] = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpFetcher(client=client, sleep=sleeps.append, **kwargs), sleeps


def test_returns_body_on_success() -> None:
    f, _ = fetcher(lambda request: httpx.Response(200, text="hola"))
    assert f.get_text("https://example.com/") == "hola"


def test_retries_server_errors_then_succeeds() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500) if len(calls) < 3 else httpx.Response(200, text="ok")

    f, sleeps = fetcher(handler)
    assert f.get_text("https://example.com/") == "ok"
    assert len(calls) == 3
    assert sleeps == [2.0, 4.0]


def test_does_not_retry_client_errors() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(404)

    f, _ = fetcher(handler)
    with pytest.raises(FetchError):
        f.get_text("https://example.com/")
    assert len(calls) == 1


def test_gives_up_after_retries_on_network_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("reset")

    f, _ = fetcher(handler)
    with pytest.raises(FetchError):
        f.get_text("https://example.com/")


def test_waits_between_requests_to_the_same_host() -> None:
    now = [100.0]
    sleeps: list[float] = []
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="x")))
    f = HttpFetcher(
        client=client,
        host_delays={"slow.example": 10.0},
        sleep=sleeps.append,
        clock=lambda: now[0],
    )
    f.get_text("https://slow.example/a")
    now[0] += 3.0
    f.get_text("https://slow.example/b")
    f.get_text("https://fast.example/c")
    assert sleeps == [pytest.approx(7.0)]


def test_post_sends_json_and_headers() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["origin"] = request.headers.get("origin")
        seen["body"] = request.content
        return httpx.Response(200, text="{}")

    f, _ = fetcher(handler)
    f.post_json("https://example.com/api", {}, headers={"Origin": "https://example.com"})
    assert seen == {"method": "POST", "origin": "https://example.com", "body": b"{}"}
