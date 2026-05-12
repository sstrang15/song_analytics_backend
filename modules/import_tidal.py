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
import re
import time
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
async def get_top_tracks(
    artists,
    albums=None,
    limit=15,
    sort_fields=None,
    collections=False,
):
    session = get_session()

    raw_tracks = []

    if isinstance(artists, str):
        artists = [artists]

    # -------- FETCH --------
    for artist in artists:

        results = session.search(
            query=artist,
            models=[tidalapi.Artist],
            limit=1
        )

        artist_results = results.get("artists", [])

        if not artist_results:
            continue

        artist_obj = artist_results[0]

        raw_tracks.extend(
            artist_obj.get_top_tracks(limit=limit)
        )

    # -------- FLATTEN --------
    tracks = flatten_track(raw_tracks)

    # -------- OPTIONAL DERIVED COLLECTIONS --------
    if collections:

        derived = build_collections(tracks)

        return {
            "tracks": tracks,
            "albums": derived["albums"],
            "eps": derived["eps"],
            "artists": derived["artists"]
        }

    # -------- DEFAULT RETURN --------
    return {
        "tracks": tracks
    }

# -------- TRACK DATASET PIPELINE --------
# fetch → flatten → sort → derive collections → attach assets
async def get_tracks(
    artists,
    top,
    limit,
    sort_fields=None,
    collections=True,
    mode="all"
):
    """
    Fetch and structure artist track data into a frontend-ready music dataset.

    Flow:
    - fetch albums / eps from artist
    - collect raw track objects
    - flatten relational data
    - optionally derive collections
    - attach render assets

    Returns:
    {
        "tracks": [...],
        "albums": [...],
        "eps": [...],
        "artists": [...],

        "assets": {
            "album_images": [...],
            "artist_images": [...]
        }
    }

    Notes:
    - tracks are the canonical relational dataset
    - albums / eps / artists are derived collections
    - assets support frontend rendering
    """

# fetch → flatten → sort → derive collections
# → attach assets
    session = get_session()

    raw_tracks = []

    alb_images = []
    art_images = []

    if isinstance(artists, str):
        artists = [artists]
        
    fetch_start = time.perf_counter()
    # -------------FETCH-------------------
    for artist in artists:

        results = session.search(
            query=artist,
            models=[tidalapi.Artist],
            limit=1
        )

        artist_results = results.get("artists",[])

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

            alb_images.append(album.image(160))
            art_images.append(artist_obj.image(160))
            raw_tracks.extend(album.tracks())


    fetch_end = time.perf_counter()
    print(fetch_end - fetch_start)
    # -------------FLATTEN-------------------
    entities = flatten_track(raw_tracks)

    # -------------SORTING-------------------
    if top:

        sort_fields = [
            ("track.popularity", "desc")
        ]

    elif not sort_fields:

        sort_fields = [
            ("album.release_date", "desc"),
            ("track.track_num", "asc")
        ]

    entities = sort_items(
        entities,
        sort_fields
    )

    # ----------------------------------------------
    # COLLECTIONS
    # ----------------------------------------------

    if collections:

        derived = build_collections(entities)

        return {
            "tracks": derived["tracks"],
            "albums": derived["albums"],
            "eps": derived["eps"],
            "live": derived["live"],
            "compilations": derived["compilations"],
            "artists": derived["artists"],
            # "assets": {
            #     "album_images": alb_images,
            #     "artist_images": art_images
            # }
        }

    # ----------------------------------------------
    # RAW ENTITY RETURN
    # ----------------------------------------------
    return {
        "entities": entities,

        # "assets": {
        #     "album_images": alb_images,
        #     "artist_images": art_images
        # }
    }

# ----------------------------------------------
#  TRACK FETCH (ALBUM-LEVEL)
# ----------------------------------------------
async def get_album_tracks(
    albums,
    top=None,
    sort_fields=None,
    collections=False
):
    session = get_session()

    track_list = []

    if isinstance(albums, str):
        albums = [albums]

    # -------- FETCH --------
    for album in albums:

        results = session.search(
            query=album,
            models=[tidalapi.Album],
            limit=1
        )

        album_results = results.get("albums", [])

        for alb in album_results:
            track_list.extend(alb.tracks())

    # -------- FLATTEN --------
    tracks = flatten_track(track_list)

    # -------- SORTING --------
    if top:

        sort_fields = [
            ("track.popularity", "desc")
        ]

    elif not sort_fields:

        sort_fields = [
            ("album.release_date", "desc"),
            ("track.track_num", "asc")
        ]

    tracks = sort_items(
        tracks,
        sort_fields
    )

    # -------- LIMIT --------
    if top and isinstance(top, int):
        tracks = limit_results(tracks, top)

    # -------- DERIVED COLLECTIONS --------
    if collections:

        derived = build_collections(tracks)

        return {
            "tracks": tracks,
            "albums": derived["albums"],
            "eps": derived["eps"],
            "artists": derived["artists"]
        }

    # -------- DEFAULT RETURN --------
    return {
        "tracks": tracks
    }

# ----------------------------------------------
#  USER DATA FETCH (FAVORITES FILTER)
# ----------------------------------------------
async def get_favorites(
    artists=None,
    albums=None,
    top=None,
    collections=False
):
    session = get_session()

    favorites = session.user.favorites.tracks(
        limit=8000
    )

    # filtering unchanged...

    # -------- FLATTEN --------
    entities = flatten_track(favorites)

    # -------- SORTING --------
    sort_fields = [
        ("track.popularity", "desc")
    ]

    entities = sort_items(
        entities,
        sort_fields
    )

    # -------- LIMIT --------
    if top and isinstance(top, int):

        entities = limit_results(
            entities,
            top
        )

    # -------- DERIVED COLLECTIONS --------
    if collections:

        derived = build_collections(
            entities
        )

        return {
            "tracks": derived["tracks"],
            "albums": derived["albums"],
            "eps": derived["eps"],
            "live": derived["live"],
            "compilations":
                derived["compilations"],
            "artists":
                derived["artists"]
        }

    # -------- DEFAULT RETURN --------
    return {
        "entities": entities
    }


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
    Flatten Tidal track objects into pure entity-friendly track objects.

    Track output:
    {
        "id": ...,
        "name": ...,
        "album_id": ...,
        "artist_id": ...
    }

    Core idea:
    - walk through track object
    - inspect every field
    - flatten only track-level primitives
    - preserve relational ids
    - skip deep relationship objects

    Important distinction:
    - tracks become pure track entities
    - album / artist objects are NOT embedded into tracks
    - collections are built separately later

    Rules:
    - 1 level deep only
    - primitives + datetime only
    - skip deep relationship objects
    """

    master_data = []

    ENTITY_KEYS = {
        "album",
        "artist"
    }

    SKIP_KEYS = {
        "session",
        "request"
    }

    PRIMITIVE_TYPES = (
        str,
        int,
        float,
        bool,
        dict,
        datetime.datetime,
        type(None)
    )

    for track in data:

        composed_data = {
            "track": {},
            "album": {},
            "artist": {}
        }

        compiled_fragments = []

        # ---------------------------------
        # RELATIONSHIP STORAGE
        # ---------------------------------
        track_album_id = None
        track_artist_id = None
        album_artist_id = None

        # ---------------------------------
        # HEAD ENTITY
        # ---------------------------------
        head_key = type(track).__name__.lower()

        # ---------------------------------
        # WALK HEAD ENTITY
        # ---------------------------------
        for field_name, field_value in track.__dict__.items():

            if field_name in SKIP_KEYS:
                continue

            # ---------------------------------
            # PRIMITIVE
            # ---------------------------------
            if isinstance(
                field_value,
                PRIMITIVE_TYPES
            ):
                compiled_fragments.append({
                    head_key: {
                        field_name:
                            normalize(field_value)
                    }
                })

            # ---------------------------------
            # LIST
            # ---------------------------------
            elif isinstance(field_value, list):

                # ---------------------------------
                # LIST OF PRIMITIVES
                # ---------------------------------
                if (
                    not field_value or
                    isinstance(
                        field_value[0],
                        PRIMITIVE_TYPES
                    )
                ):
                    compiled_fragments.append({
                        head_key: {
                            field_name: [
                                normalize(v)
                                for v in field_value
                            ]
                        }
                    })

                # ---------------------------------
                # LIST OF OBJECTS
                # ---------------------------------
                else:

                    # FUTURE:
                    # track.artists
                    # contributors
                    # collaboration graphs
                    pass

            # ---------------------------------
            # NESTED OBJECT
            # ---------------------------------
            elif hasattr(field_value, "__dict__"):

                child_key = (
                    type(field_value)
                    .__name__
                    .lower()
                )

                if child_key not in ENTITY_KEYS:
                    continue

                # ---------------------------------
                # WALK CHILD ENTITY
                # ---------------------------------
                for child_field, child_value in (
                    field_value.__dict__.items()
                ):

                    if child_field in SKIP_KEYS:
                        continue

                    if not isinstance(
                        child_value,
                        PRIMITIVE_TYPES
                    ):
                        continue

                    compiled_fragments.append({
                        child_key: {
                            child_field:
                                normalize(child_value)
                        }
                    })

                # ---------------------------------
                # RELATIONSHIPS
                # ---------------------------------

                # TRACK → ALBUM
                if child_key == "album":

                    track_album_id = getattr(
                        field_value,
                        "id",
                        None
                    )

                    embedded_artist = getattr(
                        field_value,
                        "artist",
                        None
                    )

                    if embedded_artist:

                        album_artist_id = getattr(
                            embedded_artist,
                            "id",
                            None
                        )

                # TRACK → ARTIST
                elif child_key == "artist":

                    track_artist_id = getattr(
                        field_value,
                        "id",
                        None
                    )

        # ---------------------------------
        # SYNTHESIZED RELATIONSHIPS
        # ---------------------------------

        if track_album_id:
            compiled_fragments.append({
                "track": {
                    "album_id":
                        track_album_id
                }
            })

        if track_artist_id:
            compiled_fragments.append({
                "track": {
                    "artist_id":
                        track_artist_id
                }
            })

        if album_artist_id:
            compiled_fragments.append({
                "album": {
                    "artist_id":
                        album_artist_id
                }
            })

        # ---------------------------------
        # COMPOSE DATA
        # ---------------------------------
        for fragment in compiled_fragments:

            for parent_key, payload in (fragment.items()):

                composed_data[parent_key].update(payload)

        master_data.append(composed_data)

    return master_data

# ----------------------------------------------
#  COLLECTION DERIVATION
# ----------------------------------------------
def build_collections(entities):
    """
    Build derived entity collections from
    normalized relational rows.

    Input row shape:
    {
        "track": {...},
        "album": {...},
        "artist": {...}
    }

    Core idea:
    - entities are canonical relational rows
    - collections are derived entity views
    - deduplicate entities by ids
    """

    collections = {
        "tracks": {},
        "albums": {},
        "eps": {},
        "live": {},
        "compilations": {},
        "artists": {}
    }

    for row in entities:

        track = row.get("track", {})
        album = row.get("album", {})
        artist = row.get("artist", {})

        # ---------------------------------
        # TRACKS
        # ---------------------------------
        track_id = track.get("id")

        if track_id:

            if track_id not in collections["tracks"]:

                collections["tracks"][track_id] = track

        # ---------------------------------
        # ALBUMS / EPS / LIVE / COMPILATIONS
        # ---------------------------------
        album_id = album.get("id")

        if album_id:

            album_type = album.get("type")

            album_name = (
                album.get("name", "")
                .lower()
            )

            # -------- LIVE --------
            if re.search(
                r"\([^)]*live[^)]*\)",
                album_name
            ):

                if album_id not in collections["live"]:

                    collections["live"][album_id] = album

            # -------- COMPILATIONS --------
            elif (
                "greatest hits" in album_name or
                "best of" in album_name or
                "collection" in album_name or
                "complete" in album_name
            ):

                if album_id not in collections["compilations"]:

                    collections["compilations"][album_id] = album

            # -------- EPS / SINGLES --------
            elif album_type in ["EP", "SINGLE"]:

                if album_id not in collections["eps"]:

                    collections["eps"][album_id] = album

            # -------- ALBUMS --------
            else:

                if album_id not in collections["albums"]:

                    collections["albums"][album_id] = album
        # ---------------------------------
        # ARTISTS
        # ---------------------------------
        artist_id = artist.get("id")

        if artist_id:

            if artist_id not in collections["artists"]:

                collections["artists"][artist_id] = artist

    # ---------------------------------
    # MAPS → LISTS
    # ---------------------------------
    return {
        "tracks": list(
            collections["tracks"].values()
        ),

        "albums": list(
            collections["albums"].values()
        ),

        "eps": list(
            collections["eps"].values()
        ),

        "live": list(
            collections["live"].values()
        ),

        "compilations": list(
            collections["compilations"].values()
        ),

        "artists": list(
            collections["artists"].values()
        )
    }

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


# tracks = get_tracks(
#     ["Radiohead"],
#     top=True,
#     limit=True,
#     collections=True
# )

# # track_data = tracks["tracks"]

# print("\n======== TRACK FIELD INSPECTION ========\n")

# count = 0

# for track in tracks.keys():
#     print(f"{track}")


# ----------------------------------------------
#  RELATIONAL INTEGRITY TEST
# ----------------------------------------------

# tracks = get_tracks(
#     ["Radiohead"],
#     top=True,
#     limit=True,
#     collections=True
# )

# track_data = tracks["tracks"]
# album_data = tracks["albums"]
# artist_data = tracks["artists"]

# ----------------------------------------------
# TEST: RAW ENTITY STRUCTURE
# collections=False
# ----------------------------------------------
# tracks = get_tracks(
#     ["Radiohead"],
#     top=True,
#     limit=True,
#     collections=False
# )

# entity_data = tracks["entities"]

# print("\n======== RELATIONAL ROWS ========\n")

# count = 0

# for row in entity_data[:2]:

#     count += 1

#     print(f"\n--- ROW {count} ---\n")

#     for parent_key, entity_data in (
#         row.items()
#     ):

#         print(f"{parent_key.upper()}")

#         for child_key, child_value in (
#             entity_data.items()
#         ):
#             print(
#                 f"    {child_key}: "
#                 f"{child_value}"
#             )

#         print()

# # ----------------------------------------------
# #  VERIFY ALBUM COLLECTION
# # ----------------------------------------------

# print("\n======== ALBUM COLLECTION ========\n")

# count = 0

# for album in album_data:

#     count += 1

#     print(f"\n--- ALBUM {count} ---")

#     for key, value in album.items():

#         print(f"{key}: {value}")

# # ----------------------------------------------
# #  VERIFY EP COLLECTION
# # ----------------------------------------------

# print("\n======== EP COLLECTION ========\n")

# count = 0

# for ep in ep_data:

#     count += 1

#     print(f"\n--- EP {count} ---")

#     for key, value in ep.items():

#         print(f"{key}: {value}")

# ----------------------------------------------
# TEST: TRACK → ALBUM RELATIONSHIP INTEGRITY
# verify all track album_ids map to album entities
# ----------------------------------------------
tracks = get_tracks(
    ["Radiohead"],
    top=True,
    limit=True,
    collections=True
)

# entities = tracks["entities"]

# album_ids = set()

# # collect album ids from tracks
# for row in entities:

#     track = row.get("track", {})

#     album_id = track.get("album_id")

#     if album_id:
#         album_ids.add(album_id)

# # collect actual album entities
# albums = {}

# for row in entities:

#     album = row.get("album", {})

#     album_id = album.get("id")

#     if album_id:
#         albums[album_id] = album

# print("track album_ids:", len(album_ids))
# print("album entities:", len(albums))

# missing = album_ids - set(albums.keys())

# print("\nmissing album ids:")
# print(missing)

# ----------------------------------------------
# TEST: ALL ALBUM CLASSIFICATIONS
# collections=True
# ----------------------------------------------
# tracks = get_tracks(
#     ["Radiohead"],
#     top=True,
#     limit=True,
#     collections=True
# )

# print("tracks:", len(tracks["tracks"]))
# print("albums:", len(tracks["albums"]))
# print("eps:", len(tracks["eps"]))
# print("artists:", len(tracks["artists"]))

# print("\nAlbums\n")

# for album in tracks["albums"]:
#     print(album.get("name"))

# print("\nEPs\n")

# for album in tracks["eps"]:
#     print(album.get("name"))

# print("\nLive\n")

# for album in tracks["live"]:
#     print(album.get("name"))

# print("\nCompilations\n")

# for album in tracks["compilations"]:
#     print(album.get("name"))
