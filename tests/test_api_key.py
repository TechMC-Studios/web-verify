import sys
import re
import time

sys.path.insert(0, '/workspaces/ubuntu')

from web.utils import api_key


def test_generate_length_and_prefix():
    key = api_key.generate_api_key(length=32)
    assert key.startswith('sk_')
    # token length should be >= requested (prefix excluded)
    token = key[len('sk_'):]
    assert len(token) >= 32


def test_hash_and_verify():
    key = api_key.generate_api_key(length=40)
    stored = api_key.hash_api_key(key)
    assert stored.startswith('pbkdf2_sha256$')
    assert api_key.verify_api_key(key, stored)
    # wrong key fails
    assert not api_key.verify_api_key(key + 'x', stored)


def test_new_api_key_record_and_pair():
    kid, plain, stored = api_key.new_api_key_record(length=24)
    assert isinstance(kid, str) and re.fullmatch(r"[0-9a-f]{32}", kid)
    assert isinstance(plain, str)
    assert api_key.verify_api_key(plain, stored)

    # deprecated pair
    p, s = api_key.new_api_key_pair(length=24)
    assert api_key.verify_api_key(p, s)


def test_iter_edge_cases():
    # iterations must be respected - produce different stored for different iteration counts
    key = api_key.generate_api_key(length=30)
    s1 = api_key.hash_api_key(key, iterations=100_000)
    s2 = api_key.hash_api_key(key, iterations=200_000)
    assert s1 != s2


def test_invalid_stored_format():
    assert not api_key.verify_api_key('abc', '')
    assert not api_key.verify_api_key('abc', 'not_a_hash')
