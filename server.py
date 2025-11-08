# ==============================================
# server.py
# ==============================================
import json
from urllib.parse import parse_qs
from modules.import_tidal import get_tracks, get_top_tracks, get_albums, get_favorites

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
        print(data)
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


# Scope → tells you everything about the request.

# Receive → lets you read the client’s messages.

# Send → lets you send responses (headers + body) back.

# ASGI is async-first, supports multiple protocols.

# Frameworks like FastAPI make it easy to work with, but the underlying mechanism is exactly what you’ve coded in your echo example.


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
    print(query_params)

    if not handler:
        async def fallback(params):
            return {"error": f"No route for {route_key}"}
        handler = fallback

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
    # return {"handler": "artist_handler", "artist": params.get("artist")}
    print(f"artist: {artist}, album: {album}")
    try:
        tracks = await get_top_tracks(artist, album)
    except Exception as e:
        print("Error in get_tracks:", e)
        tracks = []
    # tracks = await get_tracks(artist,album)
    print(f"tracks are {tracks}")
    return tracks

async def album_handler(params):
    """
    Example handler for /getalbums?artist={artist}
    """
    artist = params.get("artist")
    print(artist)
    albums = await get_albums(artist)
    return {"albums": albums}


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