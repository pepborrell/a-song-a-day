import base64
import os

import requests


def get_spotify_token(client_id: str, client_secret: str) -> str:
    token_req_url = "https://accounts.spotify.com/api/token"
    secret_str = f"{client_id}:{client_secret}"

    headers = {"Authorization": "Basic " + base64.b64encode(secret_str.encode("ascii")).decode("ascii")}

    body = {"grant_type": "client_credentials"}

    response = requests.post(token_req_url, headers=headers, data=body)
    if response.status_code != 200:
        print(f"API request failed with status {response.status_code}")
        raise Exception()

    token = response.json()["access_token"]
    return token


def get_playlist_tracks(playlist_id: str, token: str) -> dict:
    request_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {"Authorization": "Bearer " + token}

    response = requests.get(request_url, headers=headers)
    if response.status_code != 200:
        print(f"API request failed with status {response.status_code}")
        raise Exception()
    tracks = response.json()["items"]
    return tracks


def get_track_info(track: dict) -> dict:
    t = track["track"]
    song_info = {
        "name": t["name"],
        "artists": [artist["name"] for artist in t["artists"]],
        "album": t["album"]["name"],
        "uri": t["uri"],
        "url": t["external_urls"]["spotify"],
        "added_at": track["added_at"],
    }
    return song_info


def extract_info(tracks: dict) -> list:
    info = list(map(get_track_info, tracks))
    info = sorted(info, key=lambda t: t["added_at"])
    return info


def get_playlist_info(playlist_id: str, client_id: str, client_secret: str) -> list:
    token = get_spotify_token(client_id=client_id, client_secret=client_secret)
    tracks = get_playlist_tracks(playlist_id, token)
    info = extract_info(tracks)
    return info


if __name__ == "__main__":
    playlist = "4AdQ3isdewnA8odZ1JtfTr"
    client_id = os.environ["SPOTIFY_CLIENT_ID"]
    client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
    print(get_playlist_info(playlist, client_id=client_id, client_secret=client_secret))
