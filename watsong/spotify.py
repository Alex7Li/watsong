"""
A file to communicate with the spotify API
"""
import pickle
from typing import Any, Dict, List, Optional

import spotipy
import heapq
from spotipy.oauth2 import SpotifyOAuth

from . import util
from .structures import Album, AlbumDescription, Feel, Song

# These are also stored in the environment but it's easier to leave them here
# since it causes some problems in how I run it if I use the environment variables
CLIENT_ID = "8170c7110cfb4503af349a6a8ea22fd3"
CLIENT_SECRET = "0be6c71210bd495ab3f75e9b7f8a8935"
USERNAME = "rp5ukikcsq2vjzakx29pxazlq"

cached_sp = None


def get_spotify() -> spotipy.Spotify:
    global cached_sp
    if cached_sp is None:
        cached_sp = spotipy.Spotify(
            oauth_manager=SpotifyOAuth(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                redirect_uri="http://localhost:7233/callback",
                scope="playlist-modify-public playlist-modify-private",
                show_dialog=True,
            )
        )
    return cached_sp


def query(title: str, artists: List[str]) -> str:
    return f"{title}"


def get_memo(name: str) -> Any:
    try:
        with open(f"{name}.pickle", "rb") as file:
            return pickle.load(file)
    except IOError:
        return {}


def set_memo(structure: Any, name: str) -> None:
    try:
        with open(f"{name}.pickle", "wb") as file:
            pickle.dump(structure, file, protocol=4)
    except IOError:
        print(f"Error with saving {name}.pickle when trying to save {structure}")


search_memo = get_memo("search")
album_tracks_memo = get_memo("tracks")
feature_memo = get_memo("features")


def cache(
        album_descriptions: List[AlbumDescription], sp: spotipy.Spotify = get_spotify()
) -> None:
    """
    Cache the results for the given album descriptions for fast lookup later.
    Calling this before using the spotify methods on a list of albums will improve
    performance.
    """
    global search_memo
    global album_tracks_memo
    global feature_memo
    missed = [False, False, False]
    for title, artists in album_descriptions:
        q = query(title, artists)
        try:
            search_result = search_memo[q]
        except KeyError:
            missed[0] = True
            search_result = sp.search(query(title, artists), type="album", limit=50)
            search_memo[q] = search_result
        album_id = find_album_id_from_search(search_result, artists)
        if album_id:
            try:
                album_tracks_memo[album_id] = album_tracks_memo[album_id]
            except KeyError:
                missed[1] = True
                album_tracks_memo[album_id] = sp.album_tracks(album_id)
    if missed[0]:
        set_memo(search_memo, "search")
    if missed[1]:
        set_memo(album_tracks_memo, "tracks")

    songs = get_songs(album_descriptions)
    for songs_chunk in util.chunks(iter(songs), 100):
        seenAllSongs = True
        song_links = [song["uri"] for song in songs_chunk]
        for link in song_links:
            if link not in feature_memo:
                seenAllSongs = False
        if not seenAllSongs:
            missed[2] = True
            feature_list = sp.audio_features(song_links)
            for uri, features in zip(song_links, feature_list):
                feature_memo[uri] = features

    if missed[2]:
        set_memo(feature_memo, "features")


def find_album_id_from_search(
        search: Dict[str, Any], artists: List[str]
) -> Optional[str]:
    results = search["albums"]["items"]

    album_id = None
    if len(results) > 0:
        # Go through results and find the album with the desired artist
        for result in results:
            artist = result["artists"][0]["name"]
            if artist in artists:
                album_id = result["id"]
                break

        if album_id is None:
            album_id = results[0]["id"]
    return album_id


def album_from_title_artist(
        title: str, artists: List[str], sp: spotipy.Spotify = get_spotify()
) -> Optional[Album]:
    """
    Return an album
    :return:
    """
    q = query(title, artists)
    try:
        search_result = search_memo[q]
    except KeyError:
        search_result = sp.search(q, type="album", limit=50)
        print(f"Key error looking up the query {q}")
    album_id = find_album_id_from_search(search_result, artists)
    if album_id:
        try:
            tracks = album_tracks_memo[album_id]
        except KeyError:
            tracks = sp.album_tracks(album_id)
            print(f"Key error looking up the track with id {album_id}")
        return Album(
            title,
            album_id,
            artists,
            [
                Song(
                    title=item["name"],
                    uri=item["uri"],
                    features={},
                    artists=[artist["name"] for artist in item["artists"]],
                )
                for item in tracks["items"]
            ],
        )

    return None


def get_songs(
        album_descriptions: List[AlbumDescription], sp: spotipy.Spotify = get_spotify()
) -> List[Song]:
    """
    Given a list of albums, find all the songs in those albums according to Spotify.
    """
    songs = []
    for title, artistList in album_descriptions:
        result = album_from_title_artist(title, artistList, sp)

        if not result:
            continue

        title, id, artists, tracks = result
        songs.extend(tracks)

    return songs


def add_audio_features(
        songs: List[Song], sp: spotipy.Spotify = get_spotify()
) -> List[Song]:
    if not songs:
        return []

    annotated_songs = []
    feature_list = []
    for song in songs:
        try:
            features = feature_memo[song["uri"]]
        except KeyError:
            features = sp.audio_features(song["uri"])[0]
        feature_list.append(features)

    for song, features in zip(songs, feature_list):
        feel = {
            "energy": features["energy"],
            "dance": features["danceability"],
            "lyrics": features["speechiness"],
            "valence": features["valence"],
        }

        song["features"] = feel
        annotated_songs.append(song)

    return annotated_songs


def filter_songs(feel: Feel, songs: List[Song], n: int = 25) -> List[Song]:
    # Find the N songs closest to the given feel, measured by the L2 distance.
    def dist(x: Song) -> float:
        song_feel = x["features"]
        diff = [
            feel["energy"] - song_feel["energy"],
            feel["dance"] - song_feel["dance"],
            feel["lyrics"] - song_feel["lyrics"],
            feel["valence"] - song_feel["valence"],
        ]
        return sum([d * d for d in diff])

    print("First song in filter_songs: ", heapq.nsmallest(n, songs, key=dist)[0])
    return heapq.nsmallest(n, songs, key=dist)


def create_playlist(
        songs: List[Song], full_url: bool = True, sp: spotipy.Spotify = get_spotify()
) -> str:
    # Find the watsong playlist and use it if possible
    playlist = sp.user_playlist_create(
        sp.current_user()["id"],
        "Watsong Playlist",
        public=False,
        collaborative=True,
        description="A playlist created by watsong just for you",
    )
    sp.playlist_add_items(playlist["id"], [song["uri"] for song in songs[:100]])
    # Unsubscribe from the playlist immediately. The user can subscribe later by hitting the
    # Subscribe button.
    sp.current_user_unfollow_playlist(playlist["id"])
    return (
        f'https://open.spotify.com/embed/playlist/{playlist["id"]}'
        if full_url
        else str(playlist["id"])
    )


def subscribe_to_playlist(id: str, sp: spotipy.Spotify = get_spotify()) -> None:
    """
    Take the current playlist and save it so that it isn't overwritten later.
    """
    sp.current_user_follow_playlist(id)


if __name__ == "__main__":
    album_list = [
        AlbumDescription("A girl between worlds", []),
    ]
    album_songs = get_songs(album_list)
    add_audio_features(album_songs)
    x = create_playlist(album_songs, full_url=False)
    subscribe_to_playlist(x)
    print(x)
