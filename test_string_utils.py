# pyrefly: ignore [missing-import]
import pytest
from backend.utils.string_utils import reverse_string, is_palindrome, capitalize_words

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

def test_capitalize_words():
    assert capitalize_words("") == ""
    assert capitalize_words("hello world") == "Hello World"
    assert capitalize_words("HELLO WORLD") == "Hello World"
    assert capitalize_words("  multiple  spaces  ") == "  Multiple  Spaces  "
    assert capitalize_words("こんにちは world") == "こんにちは World"
    
    with pytest.raises(TypeError):
        capitalize_words(123)
