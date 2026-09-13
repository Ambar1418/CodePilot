def reverse_string(text: str) -> str:
    """
    Reverse the given string.

    Args:
        text (str): The string to reverse.

    Returns:
        str: The reversed string.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    return text[::-1]

def is_palindrome(text: str) -> bool:
    """
    Check if the given string is a palindrome.

    Args:
        text (str): The string to check.

    Returns:
        bool: True if the string is a palindrome, False otherwise.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    return text == text[::-1]

def capitalize_words(text: str) -> str:
    """
    Capitalize the first letter of each word in the string.

    Args:
        text (str): The string to capitalize.

    Returns:
        str: The string with capitalized words.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    if not text:
        return ""
    # Using title() might lowercase other letters, or we can use split and capitalize
    return " ".join(word.capitalize() for word in text.split(" "))

def truncate_text(text: str, max_length: int = 50) -> str:
    """
    Truncate the given string to a maximum length, appending an ellipsis
    ('...') if it had to be shortened.

    Args:
        text (str): The string to truncate.
        max_length (int): Maximum allowed length of the returned string.
            Defaults to 50. If zero or negative, returns an empty string.

    Returns:
        str: The original string if it is already within ``max_length``;
            otherwise ``prefix...`` where the total returned length never
            exceeds ``max_length``.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    if not isinstance(max_length, int) or isinstance(max_length, bool):
        raise TypeError("max_length must be an integer")
    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        # Not enough room for a prefix plus '...'
        return text[:max_length]
    return text[:max_length - 3] + "..."
