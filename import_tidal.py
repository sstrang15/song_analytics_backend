# from dotenv import load_dotenv
# from pathlib import Path
# import tidalapi
# from datetime import datetime
# import json
# import pandas as pd
# import requests


# Create a session (login)

# Save the session token

# Load a session using the saved token

# Get all of a user's favorites

import tidalapi
import json
import os
import requests
from pathlib import Path
import pathlib

# Step 1: Create session and login with credentials




def get_favorites(session):
    # Make sure you have a loaded session (from step 2 or 3)
    # get all favorites tracks, albums and artists
    my_tracks = session.user.favorites.tracks()
    my_albums = session.user.favorites.albums()
    my_artists = session.user.favorites.artists()
    # users playlists
    my_playlists = session.user.playlists()
    for playlist in my_playlists:
        tracks = playlist.items()
        for track in tracks: 
           print(f"{playlist.name} - {track.name} - {track.album.name} - {track.artist.name} - {track.popularity}")

# def main():
#     # Try to load a session
#     session = load_session()
#     # If loading fails, login with credentials
#     if not session:
#         email = input("Enter your TIDAL email: ") #sstrang11@gatech.edu
#         password = input("Enter your TIDAL password: ") #theBeatles21
#         session = login_and_save(email, password)

#     if session:
#         get_favorites(session)


# if __name__ == "__main__":
#     main()
# # login, future = session.login_oauth()
# oauth_file = Path("tidal_session_oauth.json")



# session.login_oauth_simple()
# # # # Step 1: Load the .env file
# # load_dotenv()
# }

# print(my_artists)
# # Initialization parameters
# all_tracks = []
# offset = 0
# limit = 1000

# Prepare headers for manual API call
# country_code = session.country_code
# email = session.user
# session.load_oauth_session('session.json')
# print(f"Loaded session for user: {session.user.username}")
# user_tracks = session.get_user_tracks()

# Log in (via OAuth)
# session.login_oauth_simple()

# headers = {
#     'X-Tidal-Token': token,
# }

#Make a request to the hidden history endpoint
# url = f"https://api.tidal.com/v1/users/{tidal_user}/history/tracks?countryCode=US&limit=1000&offset={offset}"  # up to 1000 tracks

# Now you can access your playlists, favorites, etc.

# response = requests.get(url, headers=headers)

#Check and parse response
# if response.status_code == 200:
#     history_data = response.json()['items']
#     for item in history_data:
#         track = item['item']
#         print(f"{track['title']} - {track['artist']['name']} [{item['playedTime']}]")

# Fetch your favorite tracks
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

# tidal_df = pd.DataFrame(tidal_data)

# tidal_favorites = tidal_df.to_csv('~/Desktop/music_project/song_listening_tidal/tidal_favorites.csv', index=True)

def main():
    session = tidalapi.Session()
    session_file = Path("tidal_session_oauth.json") # Where to store session file
    login_flag = False
    while not login_flag:
        # the code that makes sure you can log into a session exists when session file is created
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
    # opens session file so you can see the session id
    with open(session_file, 'r') as f:
        file = json.load(f)
        session_id = file["session_id"]["data"]
        print(f"Session opened: {session_id}")
    # get user track
    return get_favorites(session)


if __name__ == "__main__":
    main()