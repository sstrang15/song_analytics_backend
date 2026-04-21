# Create a session (login)
# Save the session token
# Load a session using the saved token
# Get all of a user's favorites

import tidalapi
import json
import os
import requests
import asyncio
import datetime
import pandas as pd
from pathlib import Path
import pathlib

# ---------------- Session Management ----------------
SESSION_FILE = Path("tidal_session_oauth.json")
_session = None  # cached session

async def get_playlists(session):
    # Make sure you have a loaded session (from step 2 or 3)
    # get all favorites tracks, albums and artists

    # users playlists
    my_playlists = session.user.playlists()
    # tidal_data = []
    for playlist in my_playlists:
        tracks = playlist.items()
        for track in tracks: 
            # print(f"{playlist.name} - {track.name} - {track.album.name} - {track.artist.name} - {track.popularity}")
            playlist_tracks.append({
                'Track Name': track.name,
                'Artist Name': track.artist.name,
                'Album Name': track.album.name,
                'Duration': track.duration,
                'Popularity': track.popularity,
                'Playlist': playlist.name
            })

    # tidal_df = pd.DataFrame(tidal_data)
    # tidal_favorites = tidal_df.to_csv('~/Desktop/music_project/web_application/tidal_favorites.csv', index=False)
    return playlist_tracks
# tracks = session.user.favorites.tracks()

def track_to_dict(track):
    # name is mandatory
    name = track.name

    # everything else with safe defaults
    album = getattr(track, "album", "")
    
    # artist is an object, get its name safely
    artist = getattr(track, "artist", None)
    artist_name = getattr(artist, "name", "") if artist else ""

    popularity = getattr(track, "popularity", 0)


    return {
        "name": name,
        "album": album.name,
        "artist": artist_name,
        "popularity": popularity,
    }

# ---------------- Track Endpoint -------------------
def get_top_tracks(artists, albums=None):
    """
    Return tracks for the given artist.
    If album is provided, filter tracks for that album.
    """
    # return "ARE WE HERE"
    session = get_session()
    results = session.search(query=artists,models=[tidalapi.Artist],limit=300)
    artist = results["artists"][0]
    tracks = artist.get_top_tracks(limit = 60)
    # print(tracks)
    # Make a filter for album if provided
    return tracks

async def get_favorites(artists=None, albums=None):
    """
    Return favorited tracks that match filter
    If album is provided, filter tracks for that album.
    """
    
    session = get_session()         
    
    favorites = session.user.favorites.tracks(limit=600)  # creates a list of media objects
    filtered_tracks = []  

    if isinstance(artists, str):
        artists = [artists] 

    if isinstance(albums, str):
        albums = [albums]

    artists = [a.lower().strip() for a in artists] if artists else []
    albums = [a.lower().strip() for a in albums] if albums else []

    for favorite in favorites:
        # Collect all artists and albums    

        track_artist = favorite.artist.name.lower().strip()
        track_album = favorite.album.name.lower().strip()

        # No filters
        if not artists and not albums:
            filtered_tracks.append(favorite)
            continue

        match = True

        # Artist filter (substring match)
        if artists:
            match = any(a in track_artist for a in artists)

        # Album filter (substring match)
        if albums:
            match = match and any(a in track_album for a in albums)

        if match:
            filtered_tracks.append(favorite)

    return flatten_track(filtered_tracks)

# Only takes custom object classes
def clean_object(obj):
    cleaned = {}
    new_object = obj.__dict__
    # print(type(obj))
    for key, value in new_object.items():
        if isinstance(value, (str,int,float,bool)) or value is None:
            # this is your "object-like" thing → drop it
            cleaned[key] = value

    # print(type(cleaned))
    return cleaned

async def get_tracks(artists): # add an ep flag later
    """
    Return tracks for the given artist.
    """
    session = get_session() 
    albums = []
    results = session.search(query=artists, models=[tidalapi.Artist], limit=300)
    artist = results["artists"][0] # pick the top result as the searchable artist

    # below is where you call tidalapi to get lists of album and epsingles
    album_catalog = artist._get_albums()
    ep_catalog = artist.get_ep_singles()

    albums.extend(ep_catalog)     
    albums.extend(album_catalog)

    for album in albums:
        tracks = album.tracks()

        for track in tracks:
            track_list.append(track)

    # FLATTEN HERE
    flattened_tracks = flatten_track(track_list)

    return flattened_tracks

async def get_album_tracks(albums):
    """
    Return tracks for the given album.
    """
    session = get_session()
    tracks = []
    track_results = []
    results = []
    album_filter = []
    if isinstance(albums, (str)):
        albums = [albums]

    for album in albums:
        results = session.search(query=album, models=[tidalapi.Album], limit=1)
        # print(results)
        album_filter = results["albums"]
        for album in album_filter:
            print(album.name)
            tracks = album.tracks()

            for track in tracks:
                clean_track = clean_object(track)
                track_results.append(clean_track)

    return track_results

async def get_albums(artists):
    """
    Return albums for the given artist with associated popularity
    """
    session = get_session() 
    albums = []
    album_results = []
    # ---------------- Entry check ----------------
    # If neither artist nor album list is provided, there's nothing to fetch
    results = session.search(query=artists, models=[tidalapi.Artist], limit=300)
    if results["artists"]:
        artist = results["artists"][0]
        album_catalog = artist._get_albums()
        ep_catalog = artist.get_ep_singles()
        print("Artist was located")
        albums.extend(album_catalog)
        # albums.extend(ep_catalog)
    else:
        print(f"Artist was not located")
        # albums = album_catalog

    for album in albums:
        album_results.append(clean_object(album))

    return album_results

# Given an artist return the fist artist object corresponding to search
async def get_artist(artists):
    session = get_session()
    artist_results = []
    if isinstance(artists, (str)):
        artists = [artists]
    for artist in artists:
        results = session.search(query=artists,models=[tidalapi.Artist],limit=300)
        artist_results.append(clean_object(results["artists"][0]))

    return artist_results

# Given an album return the fist artist object corresponding to that album search
async def get_artist_byalbum(albums):
    session = get_session()
    if isinstance(albums, (str)):
        print(f"Y: {albums}")
        albums = [albums]
        print(albums)

    results = session.search(query=albums,models=[tidalapi.Album],limit=300)
    album = results["albums"][0]
    artist = clean_object(album.artist)
    
    return artist


# Given a track return the fist artist object corresponding to that album
async def get_artist_bytrack(tracks):
    session = get_session()
    if isinstance(track, (str)):
        print(f"Y: {tracks}")
        tracks = [tracks]
        print(tracks)

#     results = session.search(query=tracks,models=[tidalapi.Track],limit=300)
#     artist = clean_object(results["albums"][0]["name"])
    return  artist

def normalize_value(value):

    # unwrap single-item list
    if isinstance(value, list) and len(value) == 1:
        value = value[0]

    if isinstance(value, (str, int, float, bool, dict)) or value is None:
        return value

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return value if isinstance(value, (str, int, float, bool, dict)) or value is None else None

# Given a class turned into a dictionary, transform into a flattened dictionary
def flatten_track(data):
    master_tracks = [];
    # print(f"Data is {len(data)} long")
    compiled_count = 0
    ENTITY_KEYS = {"artist", "album"}
    for track in data:
        parent_key = type(track).__name__.lower()
        compiled_tracks = []
        for p_key, p_value in track.__dict__.items():

            # lists FIRST
            if isinstance(p_value, list):
                simple = True

                for v in p_value:
                    if not (isinstance(v, (str, int, float, bool, dict, datetime.datetime)) or v is None):
                        simple = False
                        break

                # simple list
                if simple:
                    normalized = normalize_value(p_value)

                    if normalized is not None:
                        compiled_tracks.append({
                            parent_key: {p_key: normalized}
                        })

                # list of objects
                else:
                    for obj in p_value:
                        if hasattr(obj, "__dict__"):
                            child_key = type(obj).__name__.lower()

                            if child_key in ENTITY_KEYS:
                                for c_key, c_value in obj.__dict__.items():

                                    normalized = normalize_value(c_value)

                                    if normalized is not None:
                                        compiled_tracks.append({
                                            child_key: {c_key: normalized}
                                        })

            # single object (like album)
            elif hasattr(p_value, "__dict__"):
                child_key = type(p_value).__name__.lower()

                if child_key in ENTITY_KEYS:
                    for c_key, c_value in p_value.__dict__.items():

                        normalized = normalize_value(c_value)

                        if normalized is not None:
                            compiled_tracks.append({
                                child_key: {c_key: normalized}
                            })

            # PRIMITIVES LAST
            else:
                normalized = normalize_value(p_value)

                if normalized is not None:
                    compiled_tracks.append({
                        parent_key: {p_key: normalized}
                    })

        master_tracks.append(compiled_tracks)
    # at this point we have hopefully created a list of dictionaries with 1 key and 1 value
    
    # print(master_tracks[0:2])
    # Rebuild phase
    flattened_result = []

    for track_fragments in master_tracks:
        track_result = {}

        for fragment in track_fragments:
            for parent_key, inner in fragment.items():

                if parent_key not in track_result:
                    track_result[parent_key] = {}

                for key, value in inner.items():
                    # track_result[parent_key][key] = value
                    # print("REBUILD:", key, type(value), value)
                    track_result[parent_key][key] = value

        flattened_result.append(track_result)

    # debug output
    # for track in flattened_result:
    #     print(track["track"]["full_name"])
    # print(flattened_result)
    # print(jso)
    # print(track.__dict__)
    # print(json.dumps(flattened_result,indent=4))
    return flattened_result

def get_session():

    """
    Return a logged-in Tidal session, creating it if needed.
    Cached globally for reuse across requests.
    """
    session = tidalapi.Session()
    login_flag = False

    while not login_flag:
        try:
            # Try loading existing session
            session.login_session_file(SESSION_FILE)
            login_flag = True
        except Exception as e:
            print("Session file failed", e)
            try:
                # Fall back to OAuth simple login
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

                session_id = data["session_id"]["data"]
                print(f"Session opened: {session_id}")
                login_flag = True  # session created successfully
            except Exception as e:
                raise RuntimeError("Tidal OAuth login failed") from e

    _session = session
    return _session

# top_tracks = get_top_tracks("Radiohead")
# print(len(top_tracks))
# albums = get_albums("Radiohead")
# album_tracks = get_album_tracks(["OK COmput","In R"])
# print(f"Number of Albums: {len(albums)}")
# print(album_tracks)
# tracks = get_tracks("Radiohead")
# print(len(album_tracks))
# print(f"Number of Tracks: {len(tracks)}")
# print(top_tracks)
# favs = get_favorites(albums={"Kid"})
# print(favs)
# artist = get_artist_byalbum("Ok COmp")
# print(artist)
# artist = get_artist("xxyy")
# print(artist)
# need to have an array of dictionaries

# top = flatten_track(top_tracks)
# print(type(top))