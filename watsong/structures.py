from typing import Dict

"""
This file defines application-level types, such as a "Song" or an "Album".
It also includes some generic types that can be used for error handling, such as Result.
"""

from typing import List, NamedTuple, Optional, Tuple, TypeVar

from typing_extensions import TypedDict  # because we support 3.6.5


class Song(TypedDict):
    title: str
    artists: List[str]
    uri: str
    features: Dict[str, float]


"""
Named tuples like a normal python tuple, but the attributes can be accessed via . notation.
So this Song could be used like this:

```python
good_song = Song("House of the Rising Sun")

print(good_song.title) # -> House of the Rising Sun
print(good_song[0]) # -> House of the Rising Sun
```

By importing NamedTuple instead of namedtuple, we get type checking for free.
"""

AlbumDescription = NamedTuple(
    "AlbumDescription", [("title", str), ("artists", List[str])]
)

Album = NamedTuple(
    "Album",
    [
        ("title", str),
        ("spotify_id", str),
        ("artists", List[str]),
        ("songs", List[Song]),
    ],
)


class Feel(TypedDict):
    energy: float
    lyrics: float
    dance: float
    valence: float


def default_feel() -> Feel:
    # 0.02 because the frontend starts at 0.02
    return Feel(energy=0.02, lyrics=0.02, dance=0.02, valence=0.02)


def assert_feel(feel: Feel) -> None:
    """
    Checks that a feel doesn't have any negative values. This indicates a bug in the code somewhere.
    """
    assert feel["energy"] >= 0, f"{feel}['energy'] is less than 0."
    assert feel["lyrics"] >= 0, f"{feel}['lyrics'] is less than 0."
    assert feel["dance"] >= 0, f"{feel}['dance'] is less than 0."
    assert feel["valence"] >= 0, f"{feel}['valence'] is less than 0."


# This is a generic type variable, like T in Java generics. Python makes us define it ourselves.
T = TypeVar("T")

"""
Result is now a generic type that can be used with other types. For example, Result[int]
is a Tuple with an int and a possible exception. So if we had a function that returns
Result[int], we could get it and use it like this:

```python
myint, error = foo()

if error is not None: # something went wrong
    raise error

# use myint here
```
"""
Result = Tuple[T, Optional[Exception]]
