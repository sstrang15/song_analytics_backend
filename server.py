# # server.py

HTML = """
<html>
    <head><title>Hello</title></head>
    <body><h1>Hello from ASGI!</h1></body>
</html>
"""


async def app(scope, receive, send):
    assert scope['type'] == 'http'

    path = scope.get("path", "/")
    method = scope.get("method", "GET")

    # --- First route: GET /hello ---
    path_dict = { 
        "html": "/site",
        "text": "/raw",
    }
    if path == path_dict["html"]:
        header_type = "text/html"
    elif path == path_dict["text"]:
        header_type = "text/plain"

    body = HTML.encode("utf-8")

    headers = [
        [b"content-type", f"{header_type}; charset=utf-8".encode("ascii")],  # treat as plain text
        [b"content-length", str(len(body)).encode("ascii")],
                # CORS header – allow all origins for dev
        [b"access-control-allow-origin", b"*"],
    ]

      # Send response – status code varies by path
    status = 200 if path in ("/site", "/raw") else 404

    await send({
        "type": 'http.response.start',
        "status": status,
        "headers": headers,
    })
    await send({
        "type": 'http.response.body',
        "body": body,
        "more_body": False
    })