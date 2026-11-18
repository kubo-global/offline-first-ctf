"""
An example challenge pack: three small challenges that show every part of the format.
Copy this folder, change it, and point PACK in .env at your copy.

A pack is a folder with:
  catalog.py       this file: the challenges, and optionally the text of the Rules page
  files/<slug>/    files for a challenge: attached to it on the game site, and placed in
                   every player's box under ~/challenges/<slug>/
                   (a .c file next to a program of the same name is compiled inside the
                   box image and then removed, so players only get the program)
  tutorials/       a static site, served on port 8080
  web-challenge/   a Docker build folder for a web target, served on port 8081

The flags are in this file. provision.py reads it on the organiser's machine; it is never
copied into a container.
"""
import os

_S = os.environ.get("SERVER_ADDR", "127.0.0.1")
TUT = f"http://{_S}:8080/"
WEB = f"http://{_S}:8081/"

CHALLENGES = [
    dict(slug="submit-a-flag", name="Submit a flag", category="Warm-up", value=100,
         tier="Easy",                                  # optional, shown as a tag
         skill="How the game works.",                  # optional, shown as a tag
         flag="FLAG{welcome_to_the_game}",
         desc=("Every flag looks like FLAG{...}. Here is one, free: "
               "**FLAG{welcome_to_the_game}**\n\nPaste it below and submit it.")),

    dict(slug="decode-me", name="Decode me", category="Encodings", value=150, tier="Easy",
         skill="Recognising and decoding base64.",
         flag="FLAG{base64_is_not_encryption}",
         any_case=True,                                # optional: capitals do not matter
         hints=[("Letters, digits and a = at the end: this is base64.", 20),   # (text, cost)
                ("Try: base64 -d message.txt", 40)],
         files=["message.txt"],                        # from files/decode-me/
         desc=f"A message, scrambled but not encrypted. Decode it.\n\nGuide: {TUT}"),

    dict(slug="read-the-source", name="Read the source", category="Web", value=200, tier="Medium",
         skill="A web page holds more than it shows.",
         flag="FLAG{view_source_first}",
         hints=[("Right-click the page and choose View Page Source.", 30)],
         connection_info=WEB,
         desc=f"The page at {WEB} shows nothing useful. Or does it?"),
]

# Optional: the Rules page on the game site (Markdown).
RULES = """# Rules

- Every challenge hides a flag that looks like `FLAG{...}`. Find it and submit it.
- Attack only the challenges: never another player, the network or the server.
- Explaining an idea to your neighbour is welcome. Handing over a flag is not.
- Hints cost points. The cost shows before you open one.
"""
