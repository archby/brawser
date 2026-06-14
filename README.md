# brawser

`brawser` is a lightweight, persistent, and multi-profile web browser built with Python, PyQt5, and QtWebEngine. It is designed for efficiency and user privacy, featuring custom profile management, incognito mode, and integrated bookmark handling.

## Key Features

* **Persistent Profiles:** Automatically saves cookies, cache, and settings in `AppData/Local/brawser` (or `~/.local/share/brawser` on Linux) using isolated directories per profile.
* **Multi-Profile Support:** Easily create and switch between different profiles, each maintaining its own bookmarks, history, and configuration.
* **Incognito Mode:** Dedicated off-the-record browsing sessions that do not persist history or cookies.
* **History & Suggestions:** Built-in history tracking with an intelligent URL/Search bar that provides autocomplete suggestions based on your past activity.
* **Customizable UI:** Toggle between Light and Dark themes, with language support for English, Spanish, and French.
* **Bookmark Management:** Save your favorite pages with visual icons and easily manage them via the integrated menu.

## Prerequisites

You will need Python 3 installed. This application relies on the following libraries:

```bash
pip install PyQt5 PyQtWebEngine
