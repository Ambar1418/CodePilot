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
