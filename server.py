# # server.py

import json
from urllib.parse import parse_qs
from modules.import_tidal import get_tracks, get_albums


# ---------------- App --------------------------
async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    try:
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "/").strip("/")
        segments = path.split("/")
        params = {}
        query_bytes = scope.get("query_string", b"")
        # queries = parse_qs(query_bytes.decode()) 
        # print(segments)
        # Handle OPTIONS preflight
        if method == "OPTIONS":
            status, data = 200, {"message": "CORS preflight"}

        # Default root GET
        elif method == "GET" and path == "":
            status, data = 200, {"message": "Server is running"}

        # Ignore favicon.ico
        elif method == "GET" and path == "favicon.ico":
            status, data = 200, {}

        # Try to find a matching route
        # elif method == "GET"
        #     if route_name in routes:
        #         handler = routes[route_name]
        #         if len(segments) > 1:
        #             params["artist"] = segments[1]
        #         data = await handler(params)
        #         status = 200
        #     else:
        #         status, data = 404, {"error": f"No route for {route_name}"}

        # Delegate to route layer
        else:
            parts, params, handler = await match_route(path,query_bytes)
            print(params)
            data = await handler(params)
            print(data)
        # make parts into a key value
        # if handler:
        #     response = await artist_handler(params)
        # else:
        #     status, data = 404, {"error": "Not Found"}

    except Exception as e:
        status, data = 500, {"error": str(e)}


    # await send_response(send, status, data)


# ---------------- Route Matching Layer ----------------
# Responsible for:
# 1. Parsing the incoming URL path and query string.
# 2. Determining which handler function should be called.
# 3. Extracting parameters from query strings and optional path segments.
#
# Inputs:
#   - path (str): The URL path from ASGI scope, e.g., "/gettracks"
#   - query_string (bytes): The raw query string from ASGI scope, e.g., b"artist=Radiohead&album=OK+Computer"
#
# Output:
#   - handler (callable or None): The function to handle the route
#   - params (dict): Flattened dictionary of parameters to pass to the handler
async def match_route(path, query_string: bytes):
    """
    Determine the handler and parameters from path and query string.
    """
    # Remove leading/trailing slashes and split segments
    segments = path.strip("/").split("/")
    if not segments and segments[0] in routes:
        return None, {}, 404, {"error": f"No route for {path}"}

    # Flatten query string: b"artist=Radiohead&album=OK+Computer" -> dict
    query_params = parse_qs(query_string.decode())

     # Build segment dict (1-based index)
    segment_dict = {str(i + 1): value for i, value in enumerate(segments)}
    # Loop through routes table to find handler
    handler = routes.get(segments[0])
    if not handler:
        return None, segment_dict, 404, {"error": f"No route for {segments[0]}"}

    return segment_dict, dict(query_params), handler

# ---------------- Handlers ---------------------
async def track_handler(params):
    """
    Handler for /artist={artist}/album={album} style routes.
    Album is optional.
    """
    artist = params.get("artist")
    album = params.get("album")  # may be None
    print(f"Handler called")
    # return {"handler": "artist_handler", "artist": params.get("artist")}
    # print(f"artist: {artist}, album: {album}")
    something = await get_tracks(artist)
    print(something)

async def album_handler(params):
    """
    Handler for /artist={artist}/album={album} style routes.
    Album is optional.
    """
    album = params.get("album")  # may be None
    # return {"handler": "artist_handler", "artist": params.get("artist")}
    return await get_albums(artist, album)
    # ---------------- Response Sender --------------
async def send_response(send, status, data):
    body = json.dumps(data).encode()

    headers = [
        (b"content-type", b"application/json"),
        (b"access-control-allow-origin", b"*"),        # CORS
        (b"access-control-allow-methods", b"GET,POST,OPTIONS"),
        (b"access-control-allow-headers", b"*"),
    ]
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })

    # ---------------- Routes Table -----------------
# Now just two patterns, album optional
# Key = first path segment, Value = handler function
routes = {
    "gettracks": track_handler,
    "getalbum": album_handler,
}
    # you can add more routes like "getalbum": album_handler