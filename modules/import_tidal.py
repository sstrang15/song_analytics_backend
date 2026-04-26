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
async def get_tracks(artists, top, limit, sort_fields=None):
    session = get_session()
    track_list = []

    if isinstance(artists, str):
        artists = [artists]

    for artist in artists:
        results = session.search(query=artist, models=[tidalapi.Artist], limit=1)
        artist_results = results.get("artists", [])

        if not artist_results:
            continue

        artist_obj = artist_results[0]

        albums = []
        # albums.extend(artist_obj.get_ep_singles())
        albums.extend(artist_obj._get_albums())

        for album in albums:
            track_list.extend(album.tracks())

    # ---------------- PIPELINE ----------------

    tracks = flatten_track(track_list)

    # -------- sorting logic --------
    if top:
        # force popularity sort if requesting top tracks
        sort_fields = [("track.popularity", "desc")]
    elif not sort_fields:
        # default behavior
        sort_fields = [
            ("album.release_date", "desc"),
            ("track.track_num", "asc")
        ]


    tracks = sort_items(tracks, sort_fields)

    # limiting
    if limit:
        tracks = limit_results(tracks, limit)

    return tracks


# ----------------------------------------------
#  TRACK FETCH (ALBUM-LEVEL)
# ----------------------------------------------
async def get_album_tracks(albums):
    session = get_session()
    track_list = []

    if isinstance(albums, str):
        albums = [albums]

    for album in albums:
        results = session.search(query=album, models=[tidalapi.Album], limit=1)
        album_results = results.get("albums", [])

        for alb in album_results:
            track_list.extend(alb.tracks())

    return flatten_track(track_list)


# ----------------------------------------------
#  USER DATA FETCH (FAVORITES FILTER)
# ----------------------------------------------
async def get_favorites(artists=None, albums=None, top=None):
    session = get_session()
    favorites = session.user.favorites.tracks(limit=600)
    filtered_tracks = []

    # normalize inputs
    if isinstance(artists, str):
        artists = [artists]

    if isinstance(albums, str):
        albums = [albums]

    artists = [a.lower().strip() for a in artists] if artists else []
    albums = [a.lower().strip() for a in albums] if albums else []

    # -------- FILTERING --------
    for favorite in favorites:
        track_artist = favorite.artist.name.lower().strip()
        track_album = favorite.album.name.lower().strip()

        if not artists and not albums:
            filtered_tracks.append(favorite)
            continue

        match = True

        if artists:
            match = any(a in track_artist for a in artists)

        if albums:
            match = match and any(a in track_album for a in albums)

        if match:
            filtered_tracks.append(favorite)

    # -------- PIPELINE --------

    tracks = flatten_track(filtered_tracks)

    # sort by popularity (desc)
    sort_fields = [("track.popularity", "desc")]
    tracks = sort_items(tracks, sort_fields)

    # limit results if requested
    # if top:
    #     tracks = limit_results(tracks, top)

    return tracks


# ----------------------------------------------
#  ALBUM FETCH (ARTIST CATALOG)
# ----------------------------------------------
async def get_albums(artists):
    session = get_session()
    albums = []
    album_results = []

    results = session.search(query=artists, models=[tidalapi.Artist], limit=300)

    if results["artists"]:
        artist = results["artists"][0]
        albums.extend(artist._get_albums())
    else:
        print("Artist not found")

    for album in albums:
        album_results.append(clean_object(album))

    return album_results


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

    return artist_results


# ----------------------------------------------
#  ENTITY RESOLUTION (ALBUM → ARTIST)
# ----------------------------------------------
async def get_artist_byalbum(albums):
    session = get_session()

    if isinstance(albums, str):
        albums = [albums]

    results = session.search(query=albums, models=[tidalapi.Album], limit=300)
    album = results["albums"][0]

    return clean_object(album.artist)


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

    for track in data:
        parent_key = type(track).__name__.lower()
        compiled_tracks = []

        # -------- TRACK LEVEL --------
        for p_key, p_value in track.__dict__.items():
            # DEBUG: track level
            # print(f"[TRACK] {p_key} → {type(p_value)}")
            if p_key in SKIP_KEYS:
                continue

            # ---- CASE 1: list ----
            if isinstance(p_value, list):

                # print(f"🔍 TRACK LIST: {p_key}")
                # skip lists of objects (relationships)
                if any(hasattr(v, "__dict__") for v in p_value):
                    # print(f"⛔ SKIPPING TRACK OBJECT LIST: {p_key}")
                    continue

                simple = all(
                    isinstance(v, (str, int, float, bool, dict, datetime.datetime)) or v is None
                    for v in p_value
                )

                if simple:
                    normalized = [normalize(v) for v in p_value]
                    compiled_tracks.append({parent_key: {p_key: normalized}})

                continue

            # ---- CASE 2: nested object (album / artist) ----
            elif hasattr(p_value, "__dict__"):

                child_key = type(p_value).__name__.lower()

                if child_key not in ENTITY_KEYS:
                    continue

                for c_key, c_value in p_value.__dict__.items():

                    if c_key in SKIP_KEYS:
                        continue

                    # ---- list inside nested object ----
                    if isinstance(c_value, list):

                        # skip relationship lists (e.g. artists)
                        if any(hasattr(v, "__dict__") for v in c_value):

                            # TODO: handle nested entities later (album.artists)
                            continue

                        simple = all(
                            isinstance(v, (str, int, float, bool, dict, datetime.datetime)) or v is None
                            for v in c_value
                        )

                        if simple:
                            normalized = [normalize(v) for v in c_value]
                            compiled_tracks.append({child_key: {c_key: normalized}})

                        continue

                    # ---- skip deeper objects ----
                    if hasattr(c_value, "__dict__"):
                        continue

                    # ---- primitive ----
                    normalized = normalize(c_value)
                    compiled_tracks.append({child_key: {c_key: normalized}})

            # ---- CASE 3: primitive ----
            else:
                normalized = normalize(p_value)
                compiled_tracks.append({parent_key: {p_key: normalized}})

        # -------- MERGE --------
        track_result = {}

        for fragment in compiled_tracks:
            for key, inner in fragment.items():
                if key not in track_result:
                    track_result[key] = {}
                track_result[key].update(inner)

        master_tracks.append(track_result)

    return master_tracks

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

# for track in tracks:

    # 🔍 DEBUG STRUCTURE
    # print("TRACK KEYS:", track.keys())
    # print("ALBUM KEYS:", track.get("album", {}).keys())

    # existing print
    # print(
    #     f"{track['album'].get('name')} is album and "
    #     f"{track['track'].get('name')} is song, "
    #     f"{track['track'].get('track_num')}"
    # )

    # print("-" * 40)