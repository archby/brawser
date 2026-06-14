import sys
import os
import json
from pathlib import Path
from PyQt5.QtCore import QUrl, Qt, QStringListModel
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLineEdit, QToolBar,
                             QAction, QTabWidget, QMenu, QWidget, QFormLayout,
                             QComboBox, QPushButton, QHBoxLayout, QInputDialog, QListWidget, QVBoxLayout)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEnginePage


class CustomWebEngineView(QWebEngineView):
    def __init__(self, main_window, profile):
        super().__init__()
        self.main_window = main_window
        self.setPage(QWebEnginePage(profile, self))

    def contextMenuEvent(self, event):
        menu = self.page().createStandardContextMenu()
        selected_text = self.page().contextMenuData().selectedText()
        if selected_text:
            menu.addSeparator()
            display_text = selected_text[:20] + '...' if len(selected_text) > 20 else selected_text
            search_url = QUrl(self.main_window.get_search_url(selected_text))
            search_action = QAction(f'Search {self.main_window.settings["search_engine"]} for "{display_text}"', self)
            search_action.triggered.connect(lambda: self.main_window.add_new_tab(search_url, 'Search'))
            menu.addAction(search_action)
        menu.exec_(event.globalPos())


class SettingsTab(QWidget):
    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        main_layout = QHBoxLayout()
        form_layout = QFormLayout()

        # Profile Manager
        profile_layout = QHBoxLayout()
        self.profile_cb = QComboBox()
        self.profile_cb.addItems(self.browser.global_config['profiles'])
        self.profile_cb.setCurrentText(self.browser.global_config['current_profile'])
        self.profile_cb.currentTextChanged.connect(self.change_profile)

        add_profile_btn = QPushButton("New Profile")
        add_profile_btn.clicked.connect(self.add_profile)

        profile_layout.addWidget(self.profile_cb)
        profile_layout.addWidget(add_profile_btn)
        form_layout.addRow("Profile:", profile_layout)

        # Theme
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(['Light', 'Dark'])
        self.theme_cb.setCurrentText(self.browser.settings['theme'])
        self.theme_cb.currentTextChanged.connect(lambda v: self.browser.update_setting('theme', v))
        form_layout.addRow("Theme:", self.theme_cb)

        # New Tab Action
        self.nt_cb = QComboBox()
        self.nt_cb.addItems(['Homepage', 'Search Engine'])
        self.nt_cb.setCurrentText(self.browser.settings['new_tab_action'])
        self.nt_cb.currentTextChanged.connect(lambda v: self.browser.update_setting('new_tab_action', v))
        form_layout.addRow("New Tab Opens:", self.nt_cb)

        # Search Engine
        self.se_cb = QComboBox()
        self.se_cb.addItems(self.browser.search_engines)
        self.se_cb.setCurrentText(self.browser.settings['search_engine'])
        self.se_cb.currentTextChanged.connect(lambda v: self.browser.update_setting('search_engine', v))
        form_layout.addRow("Search Engine:", self.se_cb)

        # Language
        self.lang_cb = QComboBox()
        self.lang_cb.addItems(list(self.browser.langs.keys()))
        self.lang_cb.setCurrentText(self.browser.settings['language'])
        self.lang_cb.currentTextChanged.connect(lambda v: self.browser.update_setting('language', v))
        form_layout.addRow("Language:", self.lang_cb)

        # History Manager
        history_layout = QVBoxLayout()
        self.history_list = QListWidget()
        self.history_list.addItems(self.browser.history)

        clear_history_btn = QPushButton("Clear History")
        clear_history_btn.clicked.connect(self.clear_history)

        history_layout.addWidget(self.history_list)
        history_layout.addWidget(clear_history_btn)

        main_layout.addLayout(form_layout, 1)
        main_layout.addLayout(history_layout, 1)
        self.setLayout(main_layout)

    def change_profile(self, profile_name):
        if profile_name and profile_name != self.browser.global_config['current_profile']:
            self.browser.switch_profile(profile_name)

    def add_profile(self):
        text, ok = QInputDialog.getText(self, 'New Profile', 'Enter profile name:')
        if ok and text and text not in self.browser.global_config['profiles']:
            self.browser.global_config['profiles'].append(text)
            self.profile_cb.addItem(text)
            self.profile_cb.setCurrentText(text)

    def clear_history(self):
        self.browser.history.clear()
        self.browser.save_history()
        self.browser.update_completer()
        self.history_list.clear()


class Browser(QMainWindow):
    def __init__(self, is_incognito=False):
        super().__init__()
        self.is_incognito = is_incognito

        # Static Configuration
        self.search_engines = ['Google', 'DuckDuckGo', 'Bing']
        self.langs = {
            'English': {'back': 'Back', 'fwd': 'Forward', 'rel': 'Reload', 'bm': 'Bookmarks', 'hp': 'Homepage',
                        'sch': 'Search', 'add': 'Add Bookmark'},
            'Spanish': {'back': 'Atrás', 'fwd': 'Adelante', 'rel': 'Recargar', 'bm': 'Marcadores', 'hp': 'Inicio',
                        'sch': 'Buscar', 'add': 'Añadir Marcador'},
            'French': {'back': 'Retour', 'fwd': 'Avant', 'rel': 'Recharger', 'bm': 'Favoris', 'hp': 'Accueil',
                       'sch': 'Chercher', 'add': 'Ajouter Favori'}
        }
        self.http_langs = {'English': 'en-US,en;q=0.9', 'Spanish': 'es-ES,es;q=0.9', 'French': 'fr-FR,fr;q=0.9'}
        self.search_langs = {'English': {'google': 'en', 'ddg': 'us-en', 'bing': 'en'},
                             'Spanish': {'google': 'es', 'ddg': 'es-es', 'bing': 'es'},
                             'French': {'google': 'fr', 'ddg': 'fr-fr', 'bing': 'fr'}}

        # Setup Storage Paths
        local_app_data = os.getenv('LOCALAPPDATA') or os.path.expanduser('~/.local/share')
        self.brawser_dir = Path(local_app_data) / "brawser"
        self.brawser_dir.mkdir(parents=True, exist_ok=True)

        self.global_config_path = self.brawser_dir / "global.json"
        self.load_global_config()

        # Build UI structure
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        self.tabs.tabBarDoubleClicked.connect(self.tab_open_doubleclick)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.setCentralWidget(self.tabs)

        self.navbar = QToolBar("Navigation")
        self.addToolBar(self.navbar)

        self.btn_back = QAction('Back', self)
        self.btn_back.triggered.connect(self.navigate_back)
        self.navbar.addAction(self.btn_back)

        self.btn_fwd = QAction('Forward', self)
        self.btn_fwd.triggered.connect(self.navigate_forward)
        self.navbar.addAction(self.btn_fwd)

        self.btn_reload = QAction('Reload', self)
        self.btn_reload.triggered.connect(self.navigate_reload)
        self.navbar.addAction(self.btn_reload)

        self.btn_new_tab = QAction('+', self)
        self.btn_new_tab.triggered.connect(self.handle_plus_button)
        self.navbar.addAction(self.btn_new_tab)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.navbar.addWidget(self.url_bar)

        # History Completer logic
        self.history = []
        self.completer_model = QStringListModel(self.history, self)
        from PyQt5.QtWidgets import QCompleter
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.url_bar.setCompleter(self.completer)

        self.btn_bookmark = QAction('⭐', self)
        self.btn_bookmark.triggered.connect(self.add_bookmark)
        self.navbar.addAction(self.btn_bookmark)

        self.btn_incognito = QAction('🕵️', self)
        self.btn_incognito.setToolTip("New Incognito Window")
        self.btn_incognito.triggered.connect(self.open_incognito)
        self.navbar.addAction(self.btn_incognito)

        if not self.is_incognito:
            self.btn_settings = QAction('⚙️', self)
            self.btn_settings.triggered.connect(self.open_settings_tab)
            self.navbar.addAction(self.btn_settings)

        self.bookmark_menu = QMenu("Bookmarks", self)
        self.menuBar().addMenu(self.bookmark_menu)

        # Load Profile Data & Init WebEngine
        self.load_profile_data(self.global_config['current_profile'])

        self.setWindowTitle(f"brawser{' (Incognito)' if self.is_incognito else ''}")
        self.resize(1024, 768)
        self.show()

    def open_incognito(self):
        self.incognito_browser = Browser(is_incognito=True)
        self.incognito_browser.show()

    # --- Data Persistence ---
    def load_global_config(self):
        if self.global_config_path.exists():
            with open(self.global_config_path, 'r') as f:
                self.global_config = json.load(f)
        else:
            self.global_config = {"current_profile": "Default", "profiles": ["Default"]}
            self.save_global_config()

    def save_global_config(self):
        if self.is_incognito: return
        with open(self.global_config_path, 'w') as f:
            json.dump(self.global_config, f)

    def load_profile_data(self, profile_name):
        self.global_config['current_profile'] = profile_name
        self.save_global_config()

        self.profile_dir = self.brawser_dir / "profiles" / profile_name
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        # Load Settings
        settings_file = self.profile_dir / "settings.json"
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                self.settings = json.load(f)
        else:
            self.settings = {'theme': 'Light', 'new_tab_action': 'Homepage', 'search_engine': 'Google',
                             'language': 'English'}
            self.save_settings()

        # Load Bookmarks
        bookmarks_file = self.profile_dir / "bookmarks.json"
        if bookmarks_file.exists():
            with open(bookmarks_file, 'r') as f:
                self.bookmarks = json.load(f)
        else:
            self.bookmarks = {"Google": "https://www.google.com"}
            self.save_bookmarks()

        # Load History
        history_file = self.profile_dir / "history.json"
        if history_file.exists():
            with open(history_file, 'r') as f:
                self.history = json.load(f)
        else:
            self.history = []
        self.update_completer()

        # Init Profile (OffTheRecord if Incognito)
        if self.is_incognito:
            self.profile = QWebEngineProfile(self)  # Passing parent only creates OffTheRecord profile
            self.settings['theme'] = 'Dark'  # Force dark theme for incognito
        else:
            self.profile = QWebEngineProfile(profile_name, self)
            self.profile.setPersistentStoragePath(str(self.profile_dir / "webdata"))
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)

        self.update_bookmark_menu()
        self.apply_theme()
        self.update_ui_language()

        # Reset UI context to new profile
        self.tabs.clear()
        self.add_new_tab()

    def save_settings(self):
        if self.is_incognito: return
        with open(self.profile_dir / "settings.json", 'w') as f:
            json.dump(self.settings, f)

    def save_bookmarks(self):
        if self.is_incognito: return
        with open(self.profile_dir / "bookmarks.json", 'w') as f:
            json.dump(self.bookmarks, f)

    def save_history(self):
        if self.is_incognito: return
        with open(self.profile_dir / "history.json", 'w') as f:
            json.dump(self.history, f)

    def switch_profile(self, profile_name):
        self.load_profile_data(profile_name)

    # --- UI Updaters ---
    def t(self, key):
        return self.langs[self.settings['language']][key]

    def update_ui_language(self):
        self.profile.setHttpAcceptLanguage(self.http_langs[self.settings['language']])
        self.btn_back.setText(self.t('back'))
        self.btn_fwd.setText(self.t('fwd'))
        self.btn_reload.setText(self.t('rel'))
        self.btn_bookmark.setToolTip(self.t('add'))
        self.bookmark_menu.setTitle(self.t('bm'))
        self.refresh_homepages()

    def apply_theme(self):
        if self.settings['theme'] == 'Dark':
            self.setStyleSheet("""QMainWindow, QToolBar, QMenu, QMenuBar, QTabWidget::pane { background-color: #2b2b2b; color: #a9b7c6; }
                QLineEdit { background-color: #3c3f41; color: #a9b7c6; border: 1px solid #555; padding: 2px; }
                QTabBar::tab { background: #3c3f41; color: #a9b7c6; padding: 5px; border: 1px solid #2b2b2b; }
                QTabBar::tab:selected { background: #555; }
                QWidget { color: #a9b7c6; }
                QComboBox, QPushButton, QListWidget { background: #3c3f41; color: #a9b7c6; border: 1px solid #555; padding: 2px; }""")
        else:
            self.setStyleSheet("")
        self.refresh_homepages()

    def update_setting(self, category, value):
        self.settings[category] = value
        self.save_settings()
        if category == 'language':
            self.update_ui_language()
        elif category == 'theme':
            self.apply_theme()
        elif category == 'search_engine':
            self.refresh_homepages()

    # --- Navigation Logic ---
    def open_settings_tab(self):
        if self.is_incognito: return
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Settings":
                self.tabs.setCurrentIndex(i)
                return
        settings_tab = SettingsTab(self)
        i = self.tabs.addTab(settings_tab, "Settings")
        self.tabs.setCurrentIndex(i)

    def navigate_back(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, QWebEngineView): widget.back()

    def navigate_forward(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, QWebEngineView): widget.forward()

    def navigate_reload(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, QWebEngineView): widget.reload()

    def get_search_url(self, query=""):
        engine, lang = self.settings['search_engine'], self.settings['language']
        q = query.replace(' ', '+')
        if engine == 'Google': return f"https://www.google.com/search?hl={self.search_langs[lang]['google']}&q={q}"
        if engine == 'DuckDuckGo': return f"https://duckduckgo.com/?kl={self.search_langs[lang]['ddg']}&q={q}"
        return f"https://www.bing.com/search?setlang={self.search_langs[lang]['bing']}&q={q}"

    def handle_plus_button(self):
        if self.settings['new_tab_action'] == 'Homepage':
            self.add_new_tab()
        else:
            self.add_new_tab(QUrl(self.get_search_url("").split('?')[0]))

    def generate_homepage_html(self):
        is_dark = self.settings['theme'] == 'Dark'
        bg_color = "#202124" if is_dark else "#f0f0f0"
        text_color = "#ffffff" if is_dark else "#000000"
        link_color = "#8ab4f8" if is_dark else "#0000ee"

        engine_name = self.settings['search_engine']

        html = f"""
        <html>
        <head>
            <title>{self.t('hp')}</title>
            <style>
                body {{ background-color: {bg_color}; font-family: "Segoe UI", Tahoma, sans-serif; color: {text_color}; }}
                a {{ color: {link_color}; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                input {{ font-family: inherit; }}
            </style>
        </head>
        <body>
            <center>
            <br><br>
            <h1>{engine_name} {self.t('sch')}</h1>
            <form action="{self.get_search_url('').split('?')[0]}" method="get">
                <input type="text" name="q" size="50" autofocus autocomplete="off">
                <input type="submit" value="{self.t('sch')}">
            </form>
            <br><hr width="50%"><br>
            <h3>{self.t('bm')}</h3>
        """

        if self.bookmarks:
            html += f'<table border="1" cellpadding="8" bgcolor="{"#3c4043" if is_dark else "#ffffff"}" style="border-collapse: collapse;"><tr>'
            for title, url in reversed(list(self.bookmarks.items())[-6:]):
                domain = QUrl(url).host()
                favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=16"
                html += f'<td align="center"><img src="{favicon}"><br><a href="{url}">{title[:15]}</a></td>'
            html += "</tr></table>"
        else:
            html += f"<p>No bookmarks yet.</p>"

        html += "</center></body></html>"
        return html

    def add_to_history(self, item):
        if self.is_incognito or not item or item.startswith("data:"): return
        if item in self.history:
            self.history.remove(item)
        self.history.insert(0, item)
        self.history = self.history[:500]  # Limit cache size
        self.save_history()
        self.update_completer()

    def update_completer(self):
        self.completer_model.setStringList(self.history)

    def add_new_tab(self, qurl=None, label=None):
        browser = CustomWebEngineView(self, self.profile)
        i = self.tabs.addTab(browser, label or self.t('hp'))
        self.tabs.setCurrentIndex(i)
        if qurl:
            browser.setUrl(qurl)
        else:
            browser.setHtml(self.generate_homepage_html())
            self.url_bar.clear()

        browser.urlChanged.connect(lambda q, b=browser: self.update_urlbar(q, b))
        browser.loadFinished.connect(lambda ok, b=browser: self.update_tab_title(ok, b))

    def update_tab_title(self, ok, browser):
        if ok:
            idx = self.tabs.indexOf(browser)
            if idx != -1:
                title = browser.page().title() or self.t('hp')
                self.tabs.setTabText(idx, title)
                if not browser.url().isEmpty() and not browser.url().toString().startswith("data:"):
                    self.add_to_history(browser.url().toString())

    def tab_open_doubleclick(self, i):
        if i == -1: self.handle_plus_button()

    def current_tab_changed(self, i):
        widget = self.tabs.currentWidget()
        if isinstance(widget, QWebEngineView):
            self.update_urlbar(widget.url(), widget)
        elif isinstance(widget, SettingsTab):
            self.url_bar.setText("brawser://settings")

    def close_current_tab(self, i):
        if self.tabs.count() == 1:
            self.add_new_tab()
            self.tabs.removeTab(0)
        else:
            self.tabs.removeTab(i)

    def update_urlbar(self, q, b):
        if b == self.tabs.currentWidget():
            self.url_bar.setText(q.toString() if not q.toString().startswith("data:") else "")

    def navigate_to_url(self):
        u = self.url_bar.text()
        if not u: return

        if not u.startswith('http') and not u.startswith("brawser://"):
            if '.' in u and ' ' not in u:
                u = 'https://' + u
            else:
                self.add_to_history(u)  # Log search queries to history too
                u = self.get_search_url(u)

        if isinstance(self.tabs.currentWidget(), QWebEngineView):
            self.tabs.currentWidget().setUrl(QUrl(u))

    # --- Bookmark Logic ---
    def add_bookmark(self):
        title = self.tabs.tabText(self.tabs.currentIndex())
        url = self.url_bar.text()
        if title != "Settings" and url and not url.startswith("brawser://"):
            self.bookmarks[title] = url
            self.save_bookmarks()
            self.update_bookmark_menu()
            self.refresh_homepages()

    def remove_bookmark(self, title):
        if title in self.bookmarks:
            del self.bookmarks[title]
            self.save_bookmarks()
            self.update_bookmark_menu()
            self.refresh_homepages()

    def update_bookmark_menu(self):
        self.bookmark_menu.clear()
        for t, u in self.bookmarks.items():
            sub = self.bookmark_menu.addMenu(t[:30])
            open_act = QAction('Open', self)
            open_act.triggered.connect(lambda _, url=u: self.add_new_tab(QUrl(url)))
            sub.addAction(open_act)
            remove_act = QAction('Remove', self)
            remove_act.triggered.connect(lambda _, title=t: self.remove_bookmark(title))
            sub.addAction(remove_act)

    def refresh_homepages(self):
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, QWebEngineView):
                if widget.url().isEmpty() or widget.url().toString().startswith("data:text/html"):
                    widget.setHtml(self.generate_homepage_html())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Browser()
    sys.exit(app.exec_())