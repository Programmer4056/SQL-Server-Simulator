"""Professional SSMS-inspired appearance without Microsoft assets."""
DARK = dict(bg='#0b1220', surface='#111d2e', panel='#152438', secondary='#1d3048',
            line='#2b425b', text='#e7eff9', muted='#99aec7', accent='#4b9ef5',
            editor='#0d1725', kw='#60a5fa', string='#a5d6a7', comment='#8195aa',
            error='#f87171', selection='#254f7b')
LIGHT = dict(bg='#edf2f8', surface='#ffffff', panel='#f7f9fc', secondary='#e8f0fa',
             line='#d1dae6', text='#17253b', muted='#66778d', accent='#1769bf',
             editor='#ffffff', kw='#0958ac', string='#18794e', comment='#6b7280',
             error='#c2410c', selection='#b9d8f6')

def palette(theme):
    return DARK if theme == 'dark' else LIGHT

def make_qss(theme):
    p=palette(theme)
    return '''
    QWidget {background:%(surface)s; color:%(text)s; font-size:10pt;}
    QMainWindow, QDialog, QWizard {background:%(bg)s;}
    QMenuBar {background:%(surface)s; border-bottom:1px solid %(line)s; padding:3px;}
    QMenuBar::item {padding:6px 12px; border-radius:5px;}
    QMenuBar::item:selected {background:%(secondary)s;}
    QMenu {background:%(surface)s; border:1px solid %(line)s; padding:5px;}
    QMenu::item {padding:7px 20px; border-radius:4px;}
    QMenu::item:selected {background:%(selection)s;}
    QToolBar {background:%(surface)s; border-bottom:1px solid %(line)s; spacing:8px; padding:8px;}
    QToolButton {background:transparent; color:%(text)s; border-radius:5px; padding:7px;}
    QToolButton:hover {background:%(secondary)s;}
    QPushButton {background:%(secondary)s; border:1px solid %(line)s; border-radius:7px; padding:8px 14px; font-weight:500;}
    QPushButton:hover {border:1px solid %(accent)s; background:%(selection)s;}
    QPushButton:pressed {background:%(line)s;}
    QPushButton[role="primary"] {background:%(accent)s; color:white; border:1px solid %(accent)s; font-weight:600;}
    QPushButton[role="primary"]:hover {background:%(selection)s; color:%(text)s;}
    QLineEdit, QComboBox, QSpinBox {background:%(panel)s; color:%(text)s; border:1px solid %(line)s; border-radius:6px; padding:8px 10px; min-height:18px; selection-background-color:%(selection)s;}
    QLineEdit:focus, QComboBox:focus {border:1px solid %(accent)s;}
    QComboBox::drop-down {border:none; width:24px;}
    QCheckBox {spacing:8px;}
    QCheckBox::indicator {width:17px; height:17px;}
    QPlainTextEdit {background:%(editor)s; color:%(text)s; border:0; selection-background-color:%(selection)s;}
    QTextEdit {background:%(panel)s; border:1px solid %(line)s; color:%(text)s; border-radius:6px;}
    QTreeWidget, QTableWidget {background:%(surface)s; alternate-background-color:%(panel)s; color:%(text)s; border:none; gridline-color:%(line)s; selection-background-color:%(selection)s; selection-color:%(text)s;}
    QTreeWidget::item {height:26px; padding:2px 4px;}
    QTreeWidget::item:hover {background:%(secondary)s;}
    QHeaderView::section {background:%(secondary)s; color:%(text)s; border:0; border-right:1px solid %(line)s; border-bottom:1px solid %(line)s; padding:8px; font-weight:600;}
    QTabWidget::pane {border:1px solid %(line)s; background:%(surface)s;}
    QTabBar::tab {background:%(panel)s; color:%(muted)s; border-right:1px solid %(line)s; padding:10px 19px; min-width:90px;}
    QTabBar::tab:selected {background:%(surface)s; color:%(accent)s; border-top:2px solid %(accent)s; font-weight:600;}
    QDockWidget {color:%(text)s; font-weight:600;}
    QDockWidget::title {background:%(panel)s; border-bottom:1px solid %(line)s; padding:10px;}
    QSplitter::handle {background:%(line)s;}
    QStatusBar {background:%(accent)s; color:white; padding:2px 8px;}
    QStatusBar QLabel {background:transparent; color:white;}
    QWizard QLabel {background:transparent;}
    QGraphicsView {border:0; background:%(bg)s;}
    QScrollBar:vertical {background:%(panel)s; width:11px;}
    QScrollBar::handle:vertical {background:%(line)s; border-radius:5px; min-height:35px;}
    QScrollBar:horizontal {background:%(panel)s; height:11px;}
    QScrollBar::handle:horizontal {background:%(line)s; border-radius:5px; min-width:35px;}
    QLabel[role="muted"] {color:%(muted)s;}
    QLabel[role="heading"] {font-size:21pt; font-weight:700;}
    QLabel[role="eyebrow"] {font-size:9pt; color:%(accent)s; font-weight:700;}
    QScrollArea#welcomeScroll, QWidget#welcomeContainer {background:%(bg)s; border:none;}
    QFrame#welcomeCard {background:%(surface)s; border:1px solid %(line)s; border-radius:14px;}
    QLabel#welcomeTitle {background:transparent; border:none; font-size:19pt; font-weight:700; color:%(text)s; padding:0px;}
    QLabel#welcomeDescription {background:transparent; border:none; color:%(muted)s; font-size:10.5pt; padding:0px;}
    QLabel#welcomeAuthor {background:transparent; color:%(text)s; border:none; font-size:10pt; font-weight:600;}
    QLabel#welcomeNotice {background:transparent; color:%(muted)s; border:none; font-size:9pt;}
    QFrame#welcomeDivider {background:%(line)s; border:none; max-height:1px;}
    QPushButton#welcomeBugButton {background:transparent; border:none; color:%(accent)s; text-decoration:underline;}
    ''' % p
