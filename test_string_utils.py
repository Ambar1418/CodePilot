# pyrefly: ignore [missing-import]
import pytest
from backend.utils.string_utils import reverse_string, is_palindrome, capitalize_words, truncate_text

def test_reverse_string():
    assert reverse_string("") == ""
    assert reverse_string("hello") == "olleh"
    assert reverse_string("こんにちは") == "はちにんこ"
    
    with pytest.raises(TypeError):
        reverse_string(123)

def test_is_palindrome():
    assert is_palindrome("") == True
    assert is_palindrome("a") == True
    assert is_palindrome("racecar") == True
    assert is_palindrome("hello") == False
    assert is_palindrome("こんにちははちにんこ") == True
    
    with pytest.raises(TypeError):
        is_palindrome(123)

def test_truncate_text_short() -> None:
    assert truncate_text("", 50) == ""
    assert truncate_text("hello") == "hello"
    assert truncate_text("hello", 5) == "hello"
    assert truncate_text("short", 10) == "short"


def test_truncate_text_long() -> None:
    text = "a" * 60
    expected = "a" * 47 + "..."
    actual = truncate_text(text)
    assert actual == expected
    assert len(actual) == 50
    assert actual.endswith("...")


def test_truncate_text_exact_length() -> None:
    text = "x" * 50
    assert truncate_text(text) == text
    assert truncate_text(text, 50) == text


def test_truncate_text_default_max_length_is_50() -> None:
    text = "b" * 30 + "c" * 25
    result = truncate_text(text)
    assert len(result) == 50
    assert result.endswith("...")
    assert result.startswith(text[:47])


def test_truncate_text_max_length_zero_or_negative() -> None:
    assert truncate_text("hello", 0) == ""
    assert truncate_text("hello", -5) == ""


def test_truncate_text_very_small_max_length() -> None:
    # max_length 1..3: no room for '...' suffix, return prefix.
    assert truncate_text("hello", 1) == "h"
    assert truncate_text("hello", 2) == "he"
    assert truncate_text("hello", 3) == "hel"
    # max_length == 4: 1-char prefix + "..."
    result = truncate_text("hello", 4)
    assert result == "h..."
    assert len(result) == 4


def test_truncate_text_unicode() -> None:
    # Japanese + emoji; truncation is character-based, not byte-based.
    text = "あいうえおかきくけ"  # 10 chars
    result = truncate_text(text, 6)
    assert result == "あいう..."
    assert len(result) == 6

    emoji_text = "🐍" * 10  # 10 characters
    result = truncate_text(emoji_text, 5)
    assert result == "🐍🐍..."
    assert len(result) == 5


def test_truncate_text_type_errors() -> None:
    with pytest.raises(TypeError):
        truncate_text(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        truncate_text(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        truncate_text("hello", "5")  # type: ignore[arg-type]
