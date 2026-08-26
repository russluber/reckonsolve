"""Safe plain-text helpers shared by CLI presentation modules."""


def terminal_text(value: str) -> str:
    """Escape terminal control characters while preserving ordinary text."""

    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    characters: list[str] = []
    for character in normalized:
        codepoint = ord(character)
        if character == "\n":
            characters.append(character)
        elif character == "\t":
            characters.append("    ")
        elif codepoint < 32 or 127 <= codepoint < 160:
            characters.append(
                f"\\x{codepoint:02x}" if codepoint <= 0xFF else f"\\u{codepoint:04x}"
            )
        else:
            characters.append(character)
    return "".join(characters)
