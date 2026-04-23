# ==============================================
# server.py
# ==============================================
import json
import time
from urllib.parse import parse_qs
from modules.import_tidal import get_tracks, get_top_tracks, get_albums, get_artist, get_favorites, get_artist_byalbum, get_album_tracks

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
        # print(data[1])
        print("Data Received ...")
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
    # print(query_params)

    if not handler:
        async def fallback(params):
            return {"error": f"No route for {route_key}"}
        handler = fallback

    return segment_dict, dict(query_params), handler

# ==============================================
#  CORE UTILITIES
# ==============================================
# Shared functions that support request handling and data transformation.
# Acts as a foundation layer for keeping code consistent and maintainable.

def parameter_splitter(value):
    """
    Input is always a list from the request layer.
    This function flattens and splits comma-separated values.
    """
    if not value:
        return []

    result = []

    for item in value or []:
        result.extend(
            v.strip() for v in item.split(",") if v.strip()
        )

    return result

# ==============================================
#  HANDLERS (SAFE TO MODIFY / ADD)
# ==============================================
# This is for getting user specific information, eventually, favorite artists, favorite albums, but for now tracks is enough
# Eventually will be used to get playlists
async def favorites_handler(params):
    """
    Example handler for /gettracks?artist={artist}
    """
    artist = params.get("artist")
    album = params.get("album")  
    top = params.get("top")

    # may be None
    # return {"handler": "artist_handler", "artist": params.get("artist")}
    print(f"artist: {artist}, album: {album}, top: {top}")
    start = time.perf_counter()
    try:
        tracks = await get_favorites(artist, album)
    except Exception as e:
        print("Error in get_tracks:", e)
        tracks = []

    end = time.perf_counter()
    print(f"[TIMER] took {end - start:.3f}s")
    # print(f"tracks are {tracks}")
    return [tracks, 'getfavorites']

# This is for getting tracks and track information
async def track_handler(params): 
    """
    Example handler for /gettracks?artist={artist}
    """
    artist = parameter_splitter(params.get("artist"))
    album = parameter_splitter(params.get("album"))
    track = parameter_splitter(params.get("track"))
    if params.get("top"):
        top = True
        limit = 50
    else:
        top= False
        limit=100
    # return {"handler": "artist_handler", "artist": params.get("artist")}
    print(f"artist: {artist}, album: {album}, track {track}, top: {top}")
    start = time.perf_counter()
    try:
        if top:
            tracks = await get_top_tracks(artist, album, limit)
        else:
            if not artist and album:
                # print("albums")
                tracks = await get_album_tracks(album)
            elif artist:
                # print("artist")
                tracks = await get_tracks(artist,top,limit)
            elif track:
                # print("track")
                tracks = await get_tracks(track,top,limit)
            else:
                tracks = []
            
    except Exception as e:
        print("Error in get_tracks:", e)
        tracks = []
    end = time.perf_counter()
    print(f"[TIMER] took {end - start:.3f}s")
    # print(f"tracks are {tracks}")
    return [tracks, 'gettracks']

# This is for getting albums and album information
async def album_handler(params):
    """
    Example handler for /getalbums?artist={artist}&track={tracks}
    """
    artist = params.get("artist")
    album = params.get("album")
    tracks = params.get("tracks")
    top = params.get("top")
    print(f"Artist is ${artist}")
    try:
        if artist:
            albums = await get_albums(artist)
        elif tracks:
            albums = await get_albums(tracks)
    except Exception as e:
        print("Error in getalbums:", e)
        albums = []
    end = time.perf_counter()
    print(f"[TIMER] took {end - start:.3f}s")
    return [albums, 'getalbums']

# This is for getting artist information
async def artist_handler(params):
    """
    Example handler for /getartist?artist={artist}&album={album}&track={track}
    """
    artist = params.get("artist")
    track = params.get("track")
    album = params.get("album")
    print(f"Album is {album}, Artist is {artist}, Track is {track}")
    try:
        if album is not None:
            print(f"get_artist_byalbum was called")
            artists = await get_artist_byalbum(album)
        elif track is not None:
            print(f"get_artist_bytrack was called")
            artists = await get_artist_bytrack(track)
        elif artist is not None:
            print(f"get_artist was called")
            artists = await get_artist(artist)

    except Exception as e:
        print("Error in getartist:", e)
        artists = []

    print(artists)
    return [artists, 'getartist']

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
    print("Data sent ...\n")

    print(body)
    # print()
    # print(f"The text is ... ${body}")




# ==============================================
#  ROUTES TABLE (EDIT HERE)
# ==============================================
routes = {
    "gettracks": track_handler,
    "getalbums": album_handler,
    # Add more routes below:
    "getartist": artist_handler,
    "getfavorites": favorites_handler,
}