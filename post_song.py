import datetime
import json
import os
from typing import Tuple, Union

import modal
import requests
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from fetch_songs import get_playlist_info

stub = modal.Stub("a-song-a-day")
image = modal.Image.debian_slim().pip_install_from_requirements(requirements_txt="requirements.txt")

TWITTER_USER_ID = "1232195996"
playlist_id = "4AdQ3isdewnA8odZ1JtfTr"
epoch_first_tweet = 1673136000

redirect_uri = "http://127.0.0.1:5000/oauth/callback"
token_url = "https://api.twitter.com/2/oauth2/token"

scopes = ["tweet.read", "users.read", "tweet.write", "offline.access"]


def make_token(client_id: str) -> OAuth2Session:
    """
    Creates an access token with the required parameters
    """
    return OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)


def load_token(token: str) -> dict:
    """
    Loads twitter token serialized as a str in path
    """
    bb_t = token.replace("'", '"')
    data = json.loads(bb_t)
    return data


def refresh_token(twitter_session: OAuth2Session, data: dict, client_id: str, client_secret: str) -> Tuple[dict, str]:
    """
    Gets token at input, refreshes token so it can be used
    """
    refreshed_token = twitter_session.refresh_token(
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
        refresh_token=data["refresh_token"],
        auth=HTTPBasicAuth(client_id, client_secret),
    )
    st_refreshed_token = '"{}"'.format(refreshed_token)
    serialized_refreshed_token = json.loads(st_refreshed_token)

    return refreshed_token, serialized_refreshed_token


def post_tweet(payload, token) -> str:
    """
    Gets a json payload (needs at least a `text` field)
    Sends the payload to the twitter api using the oauth2 token for auth purposes
    """
    print("Tweeting!")
    print(payload["text"])
    response = requests.request(
        "POST",
        "https://api.twitter.com/2/tweets",
        json=payload,
        headers={
            "Authorization": "Bearer {}".format(token["access_token"]),
            "Content-Type": "application/json",
        },
    )

    tweet_id = response.json()["data"]["id"]
    return tweet_id


def choose_track(tracks: list) -> dict:
    """
    Given a list of tracks, it selects the first one.
    Assumes list is of not-yet-posted tracks.
    """
    if len(tracks) == 0:
        raise Exception("Track list is empty. Add new songs to playlist.")
    track = tracks[0]
    return track


def track_to_text(track: dict) -> str:
    """
    Typesets a track into some text.
    Text is of form:
        {name} - {artists separated by commas}
    """
    return f"{track['name']} - {', '.join(track['artists'])}\n{track['url']}"


def calculate_tweet_number() -> int:
    """
    Because we post a song every day, computes song number in the list as a diff between today and initial date.
    """
    t_first_tweet = datetime.datetime.utcfromtimestamp(epoch_first_tweet)
    now = datetime.datetime.utcnow()
    delta = now - t_first_tweet
    n_days = delta.days + 1  # offset one because we already tweeted on the first day
    return n_days


def compose_tweet_text(track: dict) -> str:
    """
    Gets a track and puts all tweet text together.
    Text is:
        header
        track description
        spotify link to track
    """
    track_text = track_to_text(track)
    text = f"a song a day, day {calculate_tweet_number()}\n{track_to_text(track)}"
    return text


def format_tweet_payload(text: str, reply_to: Union[str, None] = None) -> dict:
    """
    Formats a json payload to send to twitter api
    Gets: text as a str, optional tweet id to reply to
    """
    payload = {"text": f"{text}"}
    if reply_to is not None:
        payload.update({"reply": {"in_reply_to_tweet_id": reply_to}})
    return payload


def post_track(token: dict, track: dict, reply_to: Union[str, None] = None) -> str:
    """
    Handles operations to post a track,
    given a twitter api oauth2 token, track info dict and optional tweet id to reply to.
    """
    text = compose_tweet_text(track=track)
    payload = format_tweet_payload(text=text, reply_to=reply_to)
    return post_tweet(payload=payload, token=token)


def get_all_my_tweets(token: dict) -> list:
    """
    Source all tweets from my profile, handling pagination to download all of them.
    A search would be better, but twitter requires special permissions to do a full search from an arbitrary date.
    """
    all_results = []
    url = f"https://api.twitter.com/2/users/{TWITTER_USER_ID}/tweets"
    query_params = {"max_results": 100}
    response = requests.get(
        url=url, params=query_params, headers={"Authorization": "Bearer {}".format(token["access_token"])}
    )
    response_j = response.json()
    if response_j["meta"]["result_count"] > 0:
        # Check that there is tweet information
        all_results.extend([t["text"] for t in response_j["data"]])
    while "next_token" in response_j["meta"]:
        query_params = {"max_results": 100, "pagination_token": response_j["meta"]["next_token"]}
        response = requests.get(
            url=url, params=query_params, headers={"Authorization": "Bearer {}".format(token["access_token"])}
        )
        response_j = response.json()
        if response_j["meta"]["result_count"] > 0:
            # Check that there is tweet information
            all_results.extend([t["text"] for t in response_j["data"]])

    return all_results


def update_twitter_token(token: str) -> None:
    file_contents = '''import modal

stub = modal.Stub("twitter-token")
stub["twitter-token"] = modal.Secret({"TWITTER_TOKEN":"'''
    file_contents += token + '"})'

    print(f"{file_contents=}")

    with open("update_token.py", "w") as f:
        f.write(file_contents)

    os.system("modal deploy update_token.py")


@stub.function(
    schedule=modal.Cron("15 12 * * *"),
    image=image,
    secrets=[modal.Secret.from_name("a-song-a-day-secrets"), modal.Secret.from_name("twitter-token")],
)
def post_next_song() -> None:
    TW_TOKEN = os.environ["TWITTER_TOKEN"]
    TW_CLIENT_ID = os.environ["TWITTER_CLIENT_ID"]
    TW_CLIENT_SECRET = os.environ["TWITTER_CLIENT_SECRET"]
    j_TW_TOKEN = load_token(TW_TOKEN)

    twitter_session = make_token(client_id=TW_CLIENT_ID)
    refreshed_token, serialized_refreshed_tk = refresh_token(
        twitter_session=twitter_session, data=j_TW_TOKEN, client_id=TW_CLIENT_ID, client_secret=TW_CLIENT_SECRET
    )
    update_twitter_token(serialized_refreshed_tk)

    # Query spotify playlist to get info about all tracks in it
    track_info = get_playlist_info(
        playlist_id=playlist_id,
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
    )

    # Getting all tweets published by me, then get only tweets that have 'day' and 'song' in the name
    all_tweets = get_all_my_tweets(token=refreshed_token)
    series_tweets = " | ".join(list(filter(lambda x: ("day" in x) and ("song" in x), all_tweets)))

    # Select first track that hasn't been published yet
    not_published_tracks = list(filter(lambda track: track["name"] not in series_tweets, track_info))
    selected = choose_track(not_published_tracks)

    # tweet track, no thread structure anymore
    tweet_id = post_track(token=refreshed_token, track=selected)


if __name__ == "__main__":
    with stub.run():
        post_next_song.call()
