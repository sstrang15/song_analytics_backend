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


# ----------------------------------------------
#  POPULARITY LIMITING
# ----------------------------------------------
def limit_by_popularity(tracks, limit=20):
    if not tracks:
        return []

    def get_popularity(t):
        if hasattr(t, "popularity"):
            return t.popularity or 0
        elif isinstance(t, dict):
            return t.get("track", {}).get("popularity", 0)
        return 0

    sorted_tracks = sorted(tracks, key=get_popularity, reverse=True)
    return sorted_tracks[:limit] if limit else sorted_tracks


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
async def get_top_tracks(artists, albums=None):
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
        tracks.extend(artist_obj.get_top_tracks(limit=60))

    return flatten_track(tracks)


# ----------------------------------------------
#  TRACK FETCH (FULL DISCOGRAPHY)
# ----------------------------------------------
async def get_tracks(artists, top=None):
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
        albums.extend(artist_obj.get_ep_singles())
        albums.extend(artist_obj._get_albums())

        for album in albums:
            track_list.extend(album.tracks())

    if top:
        track_list = limit_by_popularity(track_list, top)

    return flatten_track(track_list)


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

    if isinstance(artists, str):
        artists = [artists]

    if isinstance(albums, str):
        albums = [albums]

    artists = [a.lower().strip() for a in artists] if artists else []
    albums = [a.lower().strip() for a in albums] if albums else []

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

    return flatten_track(filtered_tracks)


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
    master_tracks = []
    ENTITY_KEYS = {"artist", "album"}

    for track in data:
        parent_key = type(track).__name__.lower()
        compiled_tracks = []

        for p_key, p_value in track.__dict__.items():

            if isinstance(p_value, list):
                simple = all(
                    isinstance(v, (str, int, float, bool, dict, datetime.datetime)) or v is None
                    for v in p_value
                )

                if simple:
                    normalized = normalize_value(p_value)
                    if normalized is not None:
                        compiled_tracks.append({parent_key: {p_key: normalized}})
                else:
                    for obj in p_value:
                        if hasattr(obj, "__dict__"):
                            child_key = type(obj).__name__.lower()
                            if child_key in ENTITY_KEYS:
                                for c_key, c_value in obj.__dict__.items():
                                    normalized = normalize_value(c_value)
                                    if normalized is not None:
                                        compiled_tracks.append({child_key: {c_key: normalized}})

            elif hasattr(p_value, "__dict__"):
                child_key = type(p_value).__name__.lower()
                if child_key in ENTITY_KEYS:
                    for c_key, c_value in p_value.__dict__.items():
                        normalized = normalize_value(c_value)
                        if normalized is not None:
                            compiled_tracks.append({child_key: {c_key: normalized}})

            else:
                normalized = normalize_value(p_value)
                if normalized is not None:
                    compiled_tracks.append({parent_key: {p_key: normalized}})

        master_tracks.append(compiled_tracks)

    flattened_result = []

    for track_fragments in master_tracks:
        track_result = {}
        for fragment in track_fragments:
            for parent_key, inner in fragment.items():
                if parent_key not in track_result:
                    track_result[parent_key] = {}
                track_result[parent_key].update(inner)
        flattened_result.append(track_result)

    return flattened_result


# ----------------------------------------------
#  VALUE NORMALIZATION
# ----------------------------------------------
def normalize_value(value):
    if isinstance(value, list) and len(value) == 1:
        value = value[0]

    if isinstance(value, (str, int, float, bool, dict)) or value is None:
        return value

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return None


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