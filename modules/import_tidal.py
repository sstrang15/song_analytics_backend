# ==============================================
#  MODULE: DATA ACCESS + TRANSFORMATION LAYER
# ==============================================
# - Handles all interaction with Tidal API
# - Transforms raw objects into structured data
# - Provides reusable utilities for filtering and ranking
# - Does NOT handle request routing (server responsibility)


import tidalapi
import json
import os
import requests
import asyncio
import datetime
import pandas as pd
from pathlib import Path
import pathlib


# ==============================================
#  SESSION MANAGEMENT
# ==============================================

SESSION_FILE = Path("tidal_session_oauth.json")
_session = None


def get_session():
    session = tidalapi.Session()
    login_flag = False

    while not login_flag:
        try:
            session.login_session_file(SESSION_FILE)
            login_flag = True
        except Exception:
            try:
                session.login_oauth_simple()
                data = {
                    "token_type": {"data": session.token_type},
                    "session_id": {"data": session.session_id},
                    "access_token": {"data": session.access_token},
                    "refresh_token": {"data": session.refresh_token},
                    "is_pkce": {"data": session.is_pkce},
                    "user": str(session.user)
                }
                with SESSION_FILE.open("w") as f:
                    json.dump(data, f)
                login_flag = True
            except Exception as e:
                raise RuntimeError("Tidal OAuth login failed") from e

    return session


# ==============================================
#  FILTER / RANKING UTILITIES
# ==============================================
# Pure transformation functions (input → output)

def get_value(item, path):
    """
    path = "track.popularity"
    """
    keys = path.split(".")
    value = item

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None

    return value

def sort_items(items, fields, descending=True):
    """
    fields = ["track.popularity", "album.release_date"]
    """

    def key_func(item):
        result = []

        for field, direction in fields:
            val = get_value(item, field)
            val = normalize(val)
            val = apply_direction(val, direction)
            result.append(val)

        return tuple(result)

    return sorted(items, key=key_func)

def sort_albums_by_popularity(albums):
    return sorted(
        albums,
        key=get_album_popularity,
        reverse=True
    )

# ----------------------------------------------
#  POPULARITY LIMITING
# ----------------------------------------------
def limit_results(items, limit=None):
    """
    Limit results to top N items.
    """

    if not items:
        return []

    if limit is None:
        return items

    limited_items = items[:limit]

    return limited_items

def get_popularity(item):
    """
    Return popularity score from a flattened track.
    """
    track = item.get("track", {})

    if not track:
        return 0

    popularity = track.get("popularity", 0)

    return popularity

def compute_artist_popularity(tracks):
    """
    Compute average popularity for an artist from track list.
    """

    if not tracks:
        return 0

    total = 0
    count = 0

    for track in tracks:
        popularity = get_popularity(track)

        if popularity > 0:
            total += popularity
            count += 1

    if count == 0:
        return 0

    average = total / count

    return average

def compute_album_popularity(tracks):
    """
    Compute average popularity for an album from track list.
    """

    if not tracks:
        return 0

    total = 0
    count = 0

    for track in tracks:
        popularity = get_popularity(track)

        if popularity > 0:
            total += popularity
            count += 1

    if count == 0:
        return 0

    average = total / count

    return average

def build_albums_from_tracks(tracks):
    album_map = {}

    for track in tracks:
        album = track.get("album", {})
        album_id = album.get("id")

        if not album_id:
            continue

        if album_id not in album_map:
            album_map[album_id] = {
                "album": album,
                "tracks": []
            }

        album_map[album_id]["tracks"].append(track)

    return list(album_map.values())

# ==============================================
#  FETCH LAYER (EXTERNAL DATA RETRIEVAL)
# ==============================================


# ----------------------------------------------
#  PLAYLIST FETCH
# ----------------------------------------------
async def get_playlists(session):
    playlist_tracks = []
    my_playlists = session.user.playlists()

    for playlist in my_playlists:
        tracks = playlist.items()
        for track in tracks:
            playlist_tracks.append({
                'Track Name': track.name,
                'Artist Name': track.artist.name,
                'Album Name': track.album.name,
                'Duration': track.duration,
                'Popularity': track.popularity,
                'Playlist': playlist.name
            })

    return playlist_tracks


# ----------------------------------------------
#  TRACK FETCH (FAST PATH - TOP TRACKS)
# ----------------------------------------------
async def get_top_tracks(artists, albums=None, limit=15):
    session = get_session()
    tracks = []

    if isinstance(artists, str):
        artists = [artists]

    for artist in artists:
        results = session.search(query=artist, models=[tidalapi.Artist], limit=1)
        artist_results = results.get("artists", [])

        if not artist_results:
            continue

        artist_obj = artist_results[0]
        tracks.extend(artist_obj.get_top_tracks(limit=limit))

    return flatten_track(tracks)[:15]


# ----------------------------------------------
#  TRACK FETCH (FULL DISCOGRAPHY)
# ----------------------------------------------
async def get_tracks(
    artists,
    top,
    limit,
    sort_fields=None,
    buckets=False,
    mode="all"
):
    session = get_session()
    track_list = []

    if isinstance(artists, str):
        artists = [artists]

    # -------- FETCH --------
    for artist in artists:
        results = session.search(query=artist, models=[tidalapi.Artist], limit=1)
        artist_results = results.get("artists", [])

        if not artist_results:
            continue

        artist_obj = artist_results[0]

        albums = []

        if mode == "albums":
            albums.extend(artist_obj._get_albums())

        elif mode == "eps":
            albums.extend(artist_obj.get_ep_singles())

        else:
            albums.extend(artist_obj._get_albums())
            # albums.extend(artist_obj.get_ep_singles())

        for album in albums:
            track_list.extend(album.tracks())

    # ---------------- PIPELINE ----------------
    print("Before flatten:", len(track_list))
    tracks = flatten_track(track_list)
    print("After flatten:", len(tracks))

    # -------- SORTING LOGIC --------
    if top:
        sort_fields = [("track.popularity", "desc")]
    elif not sort_fields:
        sort_fields = [
            ("album.release_date", "desc"),
            ("track.track_num", "asc")
        ]

    # -------- SORT --------
    tracks = sort_items(tracks, sort_fields)

    # -------- LIMIT --------
    if top and isinstance(top, int) and not isinstance(top, bool):
        tracks = limit_results(tracks, top)

    # -------- BUCKET --------
    if buckets:
        bucketed = build_buckets(tracks)
        return {
            "buckets": bucketed
        }

    # -------- DEFAULT RETURN --------
    return {
        "data": tracks
    }


# ----------------------------------------------
#  TRACK FETCH (ALBUM-LEVEL)
# ----------------------------------------------
async def get_album_tracks(albums, top=None, sort_fields=None, buckets=False):
    session = get_session()
    track_list = []

    if isinstance(albums, str):
        albums = [albums]

    # -------- FETCH --------
    for album in albums:
        results = session.search(query=album, models=[tidalapi.Album], limit=1)
        album_results = results.get("albums", [])

        for alb in album_results:
            track_list.extend(alb.tracks())

    # -------- PIPELINE --------
    tracks = flatten_track(track_list)

    if top:
        sort_fields = [("track.popularity", "desc")]
    elif not sort_fields:
        sort_fields = [
            ("album.release_date", "desc"),
            ("track.track_num", "asc")
        ]

    tracks = sort_items(tracks, sort_fields)

    if top and isinstance(top, int):
        tracks = limit_results(tracks, top)

    if buckets:
        return {"buckets": build_buckets(tracks)}

    return {"data": tracks}

# ----------------------------------------------
#  USER DATA FETCH (FAVORITES FILTER)
# ----------------------------------------------
async def get_favorites(artists=None, albums=None, top=None, buckets=False):
    session = get_session()
    favorites = session.user.favorites.tracks(limit=600)

    # filtering unchanged...

    # -------- PIPELINE --------
    tracks = flatten_track(favorites)

    sort_fields = [("track.popularity", "desc")]
    tracks = sort_items(tracks, sort_fields)

    if top and isinstance(top, int):
        tracks = limit_results(tracks, top)

    if buckets:
        return {"buckets": build_buckets(tracks)}

    return {"data": tracks}


# ----------------------------------------------
#  ALBUM FETCH (ARTIST CATALOG)
# ----------------------------------------------
async def get_albums(artists):
    session = get_session()
    albums = []

    results = session.search(query=artists, models=[tidalapi.Artist], limit=300)

    if results["artists"]:
        artist = results["artists"][0]
        albums.extend(artist._get_albums())

    cleaned = [clean_object(album) for album in albums]

    return {"data": cleaned}


# ----------------------------------------------
#  ENTITY FETCH (ARTIST LOOKUP)
# ----------------------------------------------
async def get_artist(artists):
    session = get_session()
    artist_results = []

    if isinstance(artists, str):
        artists = [artists]

    for artist in artists:
        results = session.search(query=artist, models=[tidalapi.Artist], limit=300)
        artist_results.append(clean_object(results["artists"][0]))

    return {"data": artist_results}


# ----------------------------------------------
#  ENTITY RESOLUTION (ALBUM → ARTIST)
# ----------------------------------------------
async def get_artist_byalbum(albums):
    session = get_session()

    if isinstance(albums, str):
        albums = [albums]

    results = session.search(query=albums, models=[tidalapi.Album], limit=300)
    album = results["albums"][0]

    return {"data": clean_object(album.artist)}


# ----------------------------------------------
#  ENTITY RESOLUTION (TRACK → ARTIST)
# ----------------------------------------------
async def get_artist_bytrack(tracks):
    session = get_session()
    return None


# ==============================================
#  TRANSFORMATION LAYER (DATA SHAPING)
# ==============================================


# ----------------------------------------------
#  TRACK FLATTENING
# ----------------------------------------------
def flatten_track(data):
    """
    Flatten Tidal track objects into:

    {
        "track": {...},
        "album": {...},
        "artist": {...}
    }

    Rules:
    - 1 level deep only
    - primitives + datetime only
    - skip nested objects / relationships
    """

    master_tracks = []

    ENTITY_KEYS = {"artist", "album"}
    SKIP_KEYS = {"session", "request"}

    PRIMITIVE_TYPES = (str, int, float, bool, dict, datetime.datetime, type(None))

    for track in data:
        head_key = type(track).__name__.lower()
        compiled_tracks = []

        # -------- TRACK LEVEL --------
        for field_name, field_value in track.__dict__.items():
            # DEBUG: track level
            # print(f"[TRACK] {field_name} → {type(field_value)}")

            if field_name in SKIP_KEYS:
                continue

            # ---- CASE 1: list ----
            if isinstance(field_value, list):

                # skip lists of objects (relationships) — FAST CHECK
                if field_value and not isinstance(field_value[0], PRIMITIVE_TYPES):
                    # print(f"⛔ SKIPPING TRACK OBJECT LIST: {field_name}")
                    continue

                # no full scan — trust first element
                if not field_value or isinstance(field_value[0], PRIMITIVE_TYPES):
                    normal_value = [normalize(v) for v in field_value]
                    compiled_tracks.append({head_key: {field_name: normal_value}})

                continue

            # ---- CASE 2: nested object (album / artist) ----
            elif hasattr(field_value, "__dict__"):

                child_key = type(field_value).__name__.lower()

                if child_key not in ENTITY_KEYS:
                    continue

                for child_field, child_value in field_value.__dict__.items():

                    if child_field in SKIP_KEYS:
                        continue

                    # ---- list inside nested object ----
                    if isinstance(child_value, list):

                        # fast relationship skip
                        if child_value and not isinstance(child_value[0], PRIMITIVE_TYPES):
                            # TODO: handle nested entities later (album.artists)
                            continue

                        if not child_value or isinstance(child_value[0], PRIMITIVE_TYPES):
                            normal_value = [normalize(v) for v in child_value]
                            compiled_tracks.append({child_key: {child_field: normal_value}})

                        continue

                    # ---- skip deeper objects ----
                    if hasattr(child_value, "__dict__"):
                        continue

                    # ---- primitive ----
                    normal_value = normalize(child_value)
                    compiled_tracks.append({child_key: {child_field: normal_value}})

            # ---- CASE 3: primitive ----
            else:
                normal_value = normalize(field_value)
                compiled_tracks.append({head_key: {field_name: normal_value}})

        # -------- MERGE --------
        track_result = {}

        for fragment in compiled_tracks:
            for key, inner in fragment.items():
                if key not in track_result:
                    track_result[key] = {}
                track_result[key].update(inner)

        master_tracks.append(track_result)

    return master_tracks

def build_buckets(tracks):
    buckets = {
        "tracks": [],
        "albums": {},
        "eps": {},
        "artists": {}
    }

    for item in tracks:
        track = item.get("track", {})
        album = item.get("album", {})
        artist = item.get("artist", {})

        # -------- TRACKS --------
        buckets["tracks"].append(track)

        # -------- ALBUMS / EPS --------
        album_id = album.get("id")
        album_type = album.get("type")  # <-- comes from Tidal ("ALBUM", "EP", etc)

        if album_id and album_id not in buckets["albums"] and album_id not in buckets["eps"]:

            if album_type == "EP":
                buckets["eps"][album_id] = album
            else:
                buckets["albums"][album_id] = album

        # -------- ARTISTS --------
        artist_id = artist.get("id")
        if artist_id and artist_id not in buckets["artists"]:
            buckets["artists"][artist_id] = artist

    # convert dicts → lists
    buckets["albums"] = list(buckets["albums"].values())
    buckets["eps"] = list(buckets["eps"].values())
    buckets["artists"] = list(buckets["artists"].values())

    return buckets

# ----------------------------------------------
#  VALUE NORMALIZATION
# ----------------------------------------------

def normalize(val):
    if val is None:
        return 0

    # datetime → string (API safe)
    if isinstance(val, datetime.datetime):
        return val.isoformat()

    # leave strings as-is
    if isinstance(val, str):
        return val

    return val

def apply_direction(val, direction):
    if direction == "desc":
        if isinstance(val, (int, float)):
            return -val
        if isinstance(val, datetime.datetime):
            return -val.toordinal()
    return val
# ----------------------------------------------
#  OBJECT CLEANING
# ----------------------------------------------
def clean_object(obj):
    return {
        k: v for k, v in obj.__dict__.items()
        if isinstance(v, (str, int, float, bool)) or v is None
    }


# ----------------------------------------------
#  TRACK → DICT (LIGHT FORMAT)
# ----------------------------------------------
def track_to_dict(track):
    return {
        "name": track.name,
        "album": getattr(track.album, "name", ""),
        "artist": getattr(track.artist, "name", ""),
        "popularity": getattr(track, "popularity", 0),
    }


# tracks = get_tracks(["Radiohead"], top=False, limit=False)

# for track in tracks[0:6]:

#     # 🔍 DEBUG STRUCTURE
#     for k in track.keys():
#         for key, val in track[k].items():
#             print(f"[{k}] {key}: {val}")
    # print(f"TRACK KEYS: {track.keys()}")
    # print("ALBUM KEYS:", track.get("album", {}).keys())

    # existing print
    # print(
        # f"{track['album'].get('name')} is album and "
        # f"{track['track'].get('name')} is song, "
        # f"{track['track'].get('track_num')}"
    # )

    # print("-" * 40)