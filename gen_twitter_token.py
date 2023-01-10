import base64
import hashlib
import json
import os
import re

from flask import Flask, redirect, request, session

from post_song import make_token, token_url

app = Flask(__name__)
app.secret_key = os.urandom(50)


def get_twitter_secrets(path: str) -> dict:
    with open(path, "r") as f:
        secrets = json.load(f)
    return secrets


TOKEN_PATH = "twitter_token.json"
SECRETS_PATH = "twitter_secrets.json"
auth_url = "https://twitter.com/i/oauth2/authorize"

code_verifier = base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8")
code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)

code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
code_challenge = code_challenge.replace("=", "")

secrets = get_twitter_secrets(SECRETS_PATH)
client_id = secrets["client_id"]
client_secret = secrets["client_secret"]

twitter_session = make_token(client_id=client_id)


def save_token(path: str, token: dict) -> None:
    """
    Saves twitter token in path.
    It has been serialized as a str before, so a str is actually saved
    """
    with open(path, "w") as token_f:
        json.dump(token, token_f)


@app.route("/")
def demo():
    authorization_url, state = twitter_session.authorization_url(
        auth_url, code_challenge=code_challenge, code_challenge_method="S256"
    )
    session["oauth_state"] = state
    return redirect(authorization_url)


@app.route("/oauth/callback", methods=["GET"])
def callback():
    code = request.args.get("code")
    token = twitter_session.fetch_token(
        token_url=token_url,
        client_secret=client_secret,
        code_verifier=code_verifier,
        code=code,
    )
    print()
    print(token["refresh_token"])
    print()
    st_token = '"{}"'.format(token)
    j_token = json.loads(st_token)
    save_token(TOKEN_PATH, j_token)
    fact = "a"
    payload = {"text": "{}".format(fact)}
    # response = post_tweet(payload, token).json()
    # return response
    return {}


if __name__ == "__main__":
    app.run()
