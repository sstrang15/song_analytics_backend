# Create a session (login)
# Save the session token
# Load a session using the saved token
# Get all of a user's favorites

import tidalapi
import json
import os
import requests
import asyncio
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
async def get_top_tracks(artists, albums=None):
    """
    Return tracks for the given artist.
    If album is provided, filter tracks for that album.
    """
    # return "ARE WE HERE"
    session = get_session()
    results = session.search(query=artists,models=[tidalapi.Artist],limit=300)
    artist = results["artists"][0]
    tracks = artist.get_top_tracks(limit = 60)
    # Make a filter for album if provided
    return [track_to_dict(track) for track in tracks]

async def get_favorites(artists=None, albums=None):
    """
    Return favorited tracks that match filter
    If album is provided, filter tracks for that album.
    """
    session = get_session()         
    tracks = session.user.favorites.tracks(limit=600)  # get all favorite tracks

    filtered_tracks = []  

    artist_set = set()
    album_set = set()

    for track in tracks:
        # Collect all artists and albums    
        artist_set.add(track.artist.name)
        album_set.add(track.album.name)        

        track_album = track.album.name
        track_artist = track.artist.name
        
        # No filters → append everything
        if not artists and not albums:# and track.album == "OK Computer OKNOTOK 1997 2017":
            raw_track = track.__dict__
            # print(f"Raw track is type ${type(raw_track)}")
            clean_track = clean_object(raw_track)
            # print(f"Cleaned track is type ${type(clean_track)}")
            # print(clean_track)
            filtered_tracks.append(clean_track)
            continue  # skip to next track

        # Determine match inside the loop
        match = False

        # Albums have highest priority
        if albums:
            for a in albums:
                if a.lower() in track_album.lower():
                    match = True
                    break
        # If no album filter, check artist
        elif artists:
            for a in artists:
                if track_artist == a:
                    match = True
                    break

        if match:
            raw_track = track.__dict__
            clean_track = clean_object(raw_track)
            # print(clean_track)
            filtered_tracks.append(clean_track)
        # print(track.__dict__)
    # Convert sets to list of dicts at the end
    artist_favorites = []
    for a in sorted(artist_set):
        artist_favorites.append({"Artist": a})

    album_favorites = []
    for a in sorted(album_set):
        album_favorites.append({"Album": a})

    # print(type(filtered_tracks))

    return filtered_tracks# , artist_favorites, album_favorites]

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
    track_list = []
    clean_track_list = []
    albums = []
    clean_albums = []

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
            clean_track = clean_object(track)
            clean_track_list.append(clean_track)

    return clean_track_list

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
        print(len(ep_catalog))
        print("Artist was located")
        albums.extend(album_catalog)
        albums.extend(ep_catalog)
    else:
        print(f"Artist was not located")
        # albums = album_catalog

    for album in albums:
        album_results = clean_object(album)
        # print(clean_album)

    # print(len(albums))

    return album_results

# Given an album return the fist artist object corresponding to that album
def get_artist_byalbum(album):
    session = get_session()
    results = session.search(query=album,models=[tidalapi.Album],limit=300)
    artist = []
    for keys, albums in results.items():
        if (keys == "albums"):
            for album in albums:
                raw_artist = album.__dict__["artist"].__dict__
                
    lean_artist = clean_object(raw_artist)            
    artist.append(clean_artist)
    return artist

# Given an album return the fist artist object corresponding to that album
async def get_artist_bytrack(album):
    session = get_session()
    results = session.search(query=album,models=[tidalapi.Album],limit=300)
    # artist = results["artists"][0]
    # album_catalog = artist._get_albums()
    # print(results)
    artist = {}
    firstcounter = 1
    for keys, albums in results.items():
        if (keys == "albums"):
            for album in albums:
                if firstcounter == 1:
                    artist = album.__dict__["artist"]
                    firstcounter += 1
                else:
                    continue
    return  artist

def flatten_track(track):

    for key, value in track.__dict__.items():
        print(key, type(value))

    return {
        "track": {
            "id": track.id,
            "title": track.title,
            "duration": track.duration,
        }
    }

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
# albums = get_albums("Radiohead")
album_tracks = get_album_tracks(["OK COmput","In R"])
# print(f"Number of Albums: {len(albums)}")
# print(album_tracks)
# tracks = get_tracks("Radiohead")
# print(tracks)
# print(len(album_tracks))
# print(f"Number of Tracks: {len(tracks)}")
# print(top_tracks)
# favs = get_favorites()
# print(type(favs)[0])
artist = get_artist_byalbum("OK Comptu")
print(artist)
# need to have an array of dictionaries