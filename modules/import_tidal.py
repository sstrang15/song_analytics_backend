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
    my_tracks = session.user.favorites.tracks()
    my_albums = session.user.favorites.albums()
    my_artists = session.user.favorites.artists()

    # users playlists
    my_playlists = session.user.playlists()
    # tidal_data = []
    for playlist in my_playlists:
        tracks = playlist.items()
        # for track in tracks: 
    #         # print(f"{playlist.name} - {track.name} - {track.album.name} - {track.artist.name} - {track.popularity}")
    #         tidal_data.append({
    #             'Track Name': track.name,
    #             'Artist Name': track.artist.name,
    #             'Album Name': track.album.name,
    #             'Duration': track.duration,
    #             'Popularity': track.popularity,
    #             'Playlist': playlist.name
    #         })

    # tidal_df = pd.DataFrame(tidal_data)
    # tidal_favorites = tidal_df.to_csv('~/Desktop/music_project/web_application/tidal_favorites.csv', index=False)

# tracks = session.user.favorites.tracks()

# tidal_data = []
# for track in tracks:
#     tidal_data.append({
#         'Id': track.id,
#         'Track Name': track.name,
#         'Artist Name': track.artist.name,
#         'Album Name': track.album.name,
#         'Duration': track.duration,
#         'Popularity': track.popularity
#     })

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
    tracks = artist.get_top_tracks(limit = 20)
    return [track_to_dict(track) for track in tracks]

async def get_favorites(artists, albums=[]):
    """
    Return tracks for the given artist.
    If album is provided, filter tracks for that album.
    """
    session = get_session()         
    tracks = session.user.favorites.tracks()  # get all favorite tracks
    artist_tracks = []
    album_tracks = []
    print("function called")
    for track in tracks:
        for artist in artists:
            if track.artist.name == artist:
                artist_tracks.append(track.name)
        for album in albums:
            if track.album.name == artist:
                album_tracks.append(track.name)            
            album_tracks.append(track.artist.name, track.album.name) 
    return album_tracks

async def get_tracks(artists, albums=None):
    """
    Return tracks for the given artist.
    If album is provided, filter tracks for that album.
    """
    if albums is None:
        albums = []

    matches_found = False
    session = get_session() 
    track_list = []
    # ---------------- Entry check ----------------
    # If neither artist nor album list is provided, there's nothing to fetch
    # if artists:
    #     results = session.search(query=artists, models=[tidalapi.Artist], limit=300)
    #     if results["artists"]:
    #         artist = results["artists"][0]
    #         album_catalog = artist._get_albums()
    #         print("Artist was located")
    #     else:
    #         print(f"Artist was not located")
    #         album_catalog = []
    # else:
    #     # Can't match albums without an artist
    #     return []
    
    # Make album filter case-insensitive
    # albums_lower = [a.name.lower() for a in album_catalog]
    # print(album_catalog)
    # print(albums_lower)
    # print(albums)
    # Iterate through all albums in album_catalog.
    # If no album filter is provided, include all albums.
    # If albums are specified, include only tracks from matching albums.
    # for album in album_catalog:
    #     album_name_lower = album.name.lower()

    #     # include all if albums list is empty, otherwise check substring match
    #     # If albums filter exists, skip albums that don't match
    #     if not albums_lower or any(a in album_name_lower for a in albums_lower):
    #         print(albums.lower())
    #         matches_found = True
    #         print(album.name.lower())
    #         tracks = album.tracks()
    #         for track in tracks:
    #             # print(f"Album {album.name} was found")
    #             track_info = {
    #                 "name": track.name,
    #                 "popularity": track.popularity,
    #                 "album": album.name
    #             }
    #             track_list.append(track_info)

    # if not matches_found:
    #     return []  # or handle no matches

    return track_list

async def get_albums(artists):
    """
    Return albums for the given artist with associated popularity
    """
    session = get_session()
    results = session.search(query=artists,models=[tidalapi.Artist],limit=300)
    artist = results["artists"][0]
    album_catalog = artist._get_albums()
    album_list = []
    for album in album_catalog:
        tracks = album.tracks()
        popularity = 0
        for track in tracks:
            popularity += track.popularity
        album_info = {
            "name": album.name,
            "universal_product_number": album.universal_product_number,     
            "audiomodes": album.audio_modes,
            "media": album.media_metadata_tags,
            "popularity": popularity/len(tracks),
            "version":album.version,
            }
        album_list.append(album_info)

    return album_list

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
# tracks = get_tracks("Radiohead","OK Computer")
# print(tracks)