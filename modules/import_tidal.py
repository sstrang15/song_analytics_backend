# Create a session (login)
# Save the session token
# Load a session using the saved token
# Get all of a user's favorites

import tidalapi
import json
import os
import requests
import pandas as pd
from pathlib import Path
import pathlib

# Step 1: Create session and login with credentials

def get_playlists(session):
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
        for track in tracks: 
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


def main():
    session = tidalapi.Session()
    session_file = Path("tidal_session_oauth.json") # Where to store session file
    login_flag = False
    while not login_flag:
        # the code that makes sure you can log into an existing session when session file is created
        try:
            # tries to open an existing session
            session.login_session_file(session_file)
            login_flag = True
        except Exception as e:
            print("Session file failed", e)
            try:
                session.login_oauth_simple()
                data = {
                    "token_type": {"data": session.token_type},
                    "session_id": {"data": session.session_id},
                    "access_token": {"data": session.access_token},
                    "refresh_token": {"data": session.refresh_token},
                    "is_pkce": {"data": session.is_pkce},
                    "user": session.user
                }
                with session_file.open("w") as outfile:
                    json.dump(data, outfile)
                login_flag = True
            except Exception as e:
                print("Oauth login failed", e)
    # shows session information
    with open(session_file, 'r') as f:
        file = json.load(f)
        session_id = file["session_id"]["data"]
        print(f"Session opened: {session_id}")

    # data = get_favorites(session)
    data = get_playlists(session)
    return data

if __name__ == "__main__":
    main()
