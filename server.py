# ==============================================
# server.py
# ==============================================
import json
from urllib.parse import parse_qs
from modules.import_tidal import get_tracks, get_albums



# ==============================================
#  CORE ASGI APP  (DO NOT CHANGE)
# ==============================================
async def app(scope, receive, send):

    """Main ASGI entry point."""
    if scope["type"] != "http":
        return
    try:
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "/").strip("/")
        segments = path.split("/")
        params = {}
        query_bytes = scope.get("query_string", b"")
        # --- Handle OPTIONS preflight ---
        if method == "OPTIONS":
            status, data = 200, {"message": "CORS preflight"}

        # --- Default root ---
        elif method == "GET" and path == "":
            status, data = 200, {"message": "Server is running"}

        # --- Ignore favicon.ico ---
        elif method == "GET" and path == "favicon.ico":
            status, data = 200, {}

        # --- Route handling (EDITABLE VIA match_route / routes) ---
        else:
            segments, params, handler = await match_route(path, query_bytes)
            data = await handler(params)
            status = 200

        # Send final response
        await send_response(send, status, data)

    except Exception as e:
        status, data = 500, {"error": str(e)}


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



# ==============================================
#  ROUTE MATCHING LAYER  (RARELY CHANGE)
# ==============================================
async def match_route(path, query_string: bytes):
    """
    Determine which handler and params to use.
    You usually won't need to edit this.
    """
    # Split URL path into segments
    segments = path.strip("/").split("/")

    # Flatten query string into dict
    query_params = parse_qs(query_string.decode())

    # Build numeric segment dictionary
    segment_dict = {}
    for i, value in enumerate(segments):
        segment_dict[str(i + 1)] = value

    # Look up handler
    route_key = segments[0] if segments else None
    handler = routes.get(route_key)

    if not handler:
        return None, segment_dict, lambda _: {"error": f"No route for {route_key}"}

    return segment_dict, dict(query_params), handler



# ==============================================
#  HANDLERS (SAFE TO MODIFY / ADD)
# ==============================================
async def track_handler(params):
    """
    Example handler for /gettracks?artist={artist}
    """
    artist = params.get("artist")
    album = params.get("album")  # may be None
    print(f"Handler called")
    # return {"handler": "artist_handler", "artist": params.get("artist")}
    # print(f"artist: {artist}, album: {album}")
    tracks = await get_top_tracks(artist)
    return tracks

async def album_handler(params):
    """
    Example handler for /getalbums?artist={artist}
    """
    artist = params.get("artist")
    album = params.get("album")  # may be None
    # return {"handler": , "artist": params.get("artist")}
    tracks = await get_albums(artist)
    return tracks


# ==============================================
# 📤 RESPONSE SENDER (DO NOT CHANGE)
# ==============================================
async def send_response(send, status, data):
    """Send JSON response with CORS headers."""
    body = json.dumps(data).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"access-control-allow-origin", b"*"),
        (b"access-control-allow-methods", b"GET,POST,OPTIONS"),
        (b"access-control-allow-headers", b"*"),
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})



# ==============================================
#  ROUTES TABLE (EDIT HERE)
# ==============================================
routes = {
    "gettracks": track_handler,
    "getalbums": album_handler,
    # Add more routes below:
    # "getartist": artist_handler,
    # "search": search_handler,
}