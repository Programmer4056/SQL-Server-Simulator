"""SQL Server Simulator cross-platform desktop UI: official Qt / PySide6 bindings.

Educational SQLite engine with real key enforcement. This is NOT Microsoft SQL Server.
Designed and developed by Ali Sayyadi.
"""
from __future__ import annotations
import sys
import platform
from pathlib import Path
from urllib.parse import urlencode
import webbrowser
from PySide6.QtCore import Qt,QSettings,QTimer,QSize,QPointF
from PySide6.QtGui import QAction, QShortcut, QFont,QFontDatabase,QIcon,QKeySequence,QColor,QPixmap,QPainter,QPen,QPolygonF,QTextOption
from PySide6.QtWidgets import (QApplication,QMainWindow,QTabWidget,QDockWidget,QTreeWidget,
    QTreeWidgetItem,QTextEdit,QToolBar,QComboBox,QLabel,QWidget,QVBoxLayout,QHBoxLayout,
    QPushButton,QMessageBox,QFileDialog,QSplitter,QTableWidget,QTableWidgetItem,
    QHeaderView,QAbstractItemView,QStyle,QFrame,QMenu,QTabBar,QScrollArea,QSizePolicy)
from core import LabDatabase, LabError
from tsql_compat import run_script
from sql_script_loader import read_sql_script
from tsql_modules import list_modules, views, drop_module
from model_ext import get_rows,is_identity,editable_records,delete_record
from widgets import SQLEditor,Diagram,WelcomePanel
from dialogs import NewDatabaseWizard,TableDesigner,RelationshipWizard,DataEntryDialog,GridRowEditor,ScriptExportWizard,LanguageChoice,RecordEditDialog,error,info
from i18n import tr
from version_info import APP_VERSION, REPORT_EMAIL
from locale_support import ui, error_summary
from qt_localized import LocalizedMessageBox as QMessageBox
from grid_edit import cell_value
from model_ext import update_record
from style import make_qss,palette,apply_palette

EMAIL=REPORT_EMAIL
# Use a user-writable folder on every desktop OS (not the installed app directory).
USER_DOCUMENTS=Path.home()/'Documents'
APP_FOLDER=(USER_DOCUMENTS if USER_DOCUMENTS.is_dir() else Path.home())/'SQL Server Simulator Projects'

class ClearDockTitleBar(QWidget):
    """Large, theme-aware panel controls with an obvious hide/reopen workflow.

    The dock remains alive when hidden; View -> Panels shows it again.
    """
    def __init__(self, dock: QDockWidget, language='en'):
        super().__init__(dock)
        self.dock = dock
        self.language = language
        self.setObjectName('clearDockTitleBar')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 5, 3)
        layout.setSpacing(3)
        self.caption = QLabel(dock.windowTitle(), self)
        self.caption.setObjectName('clearDockCaption')
        self.caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.caption, 1)
        self.float_button = QPushButton('↗', self)
        self.float_button.setObjectName('dockFloatButton')
        self.float_button.setFixedSize(32, 30)
        self.float_button.clicked.connect(lambda: self.dock.setFloating(not self.dock.isFloating()))
        layout.addWidget(self.float_button)
        self.close_button = QPushButton('×', self)
        self.close_button.setObjectName('dockCloseButton')
        self.close_button.setFixedSize(32, 30)
        self.close_button.clicked.connect(dock.hide)
        layout.addWidget(self.close_button)
        dock.windowTitleChanged.connect(self.caption.setText)
        dock.topLevelChanged.connect(self._update_float_glyph)
        self.set_language(language)

    def set_language(self, language):
        self.language = language
        self.close_button.setToolTip('بستن این پنل (بازکردن مجدد از منوی نمایش)' if language == 'fa' else
                                     'Hide this panel (reopen from View menu)')
        self.float_button.setToolTip('جدا کردن یا بازگرداندن پنل' if language == 'fa' else
                                     'Float / dock panel')

    def _update_float_glyph(self, floating):
        self.float_button.setText('↙' if floating else '↗')

    def mousePressEvent(self, event):
        event.ignore()  # Let Qt drag the dock from the unused title-bar area.

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        event.ignore()  # Qt handles double-click to float or dock.


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.prefs=QSettings('Ali Sayyadi','SQL Server Simulator')
        self.lang=self.prefs.value('language','en')
        if self.lang not in ('fa','en'):self.lang='en'
        self.theme=self.prefs.value('theme','dark')
        if self.theme not in ('light','dark'):self.theme='dark'
        self.db=None
        self.data_tabs={}
        self.setMinimumSize(640,420)
        self.resize(1360,850)
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks |
                            QMainWindow.DockOption.AllowNestedDocks |
                            QMainWindow.DockOption.AllowTabbedDocks)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setWindowTitle(tr('app_name',self.lang)+'  |  v'+APP_VERSION)
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
        # macOS/Linux do not reliably use .ico assets; keep .ico for Windows.
        icon_name='app.ico' if sys.platform=='win32' else 'app.png'
        icon_file=root/'assets'/icon_name
        if not icon_file.exists():icon_file=root/'assets'/'app.ico'
        if icon_file.exists():self.setWindowIcon(QIcon(str(icon_file)))
        apply_palette(QApplication.instance(),self.theme)
        self.set_fonts()
        self.init_shell()
        self.build_commands()
        self.refresh_explorer()
        if self.prefs.contains('window/geometry'):
            self.restoreGeometry(self.prefs.value('window/geometry'))
        if self.prefs.contains('window/docks'):
            self.restoreState(self.prefs.value('window/docks'))
        self._schema_seen=None
        self.schema_timer=QTimer(self)
        self.schema_timer.timeout.connect(self.check_external_schema_changes)
        self.schema_timer.start(2000)
    def text(self,key,**kwargs):return tr(key,self.lang,**kwargs)
    def set_fonts(self):
        app=QApplication.instance()
        fonts=set(QFontDatabase.families())
        if self.lang=='fa':
            face=next((f for f in ('Vazirmatn','Vazir','Noto Sans Arabic','Noto Naskh Arabic','IRANSans','Tahoma','Arial','DejaVu Sans') if f in fonts),app.font().family())
            app.setFont(QFont(face,11))
        else:
            # Use native UI typefaces on Windows, macOS, and Linux.
            choices=('Segoe UI','Arial','Noto Sans','DejaVu Sans') if sys.platform=='win32' else (('SF Pro Text','Helvetica Neue','Arial','DejaVu Sans') if sys.platform=='darwin' else ('Noto Sans','DejaVu Sans','Liberation Sans','Arial'))
            face=next((f for f in choices if f in fonts),app.font().family())
            app.setFont(QFont(face,11))
    def icon(self,kind):
        """Draw consistent vector-like icons with palette-aware strokes.

        Native system icons were dark even on our custom dark theme.
        """
        pix=QPixmap(28,28)
        pix.fill(Qt.GlobalColor.transparent)
        painter=QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        ink=QColor(palette(self.theme)['text'])
        painter.setPen(QPen(ink,2.2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        if kind in ('new','save'):
            painter.drawRoundedRect(6,4,16,20,2,2)
            if kind=='new':painter.drawLine(10,14,19,14);painter.drawLine(14,10,14,19)
            else:painter.drawLine(9,18,19,18);painter.drawRect(10,6,8,6)
        elif kind=='open':
            painter.drawRect(4,9,20,14)
            painter.drawLine(4,9,9,5);painter.drawLine(9,5,17,5)
        elif kind=='table':
            painter.drawRect(4,5,20,18)
            painter.drawLine(4,11,24,11);painter.drawLine(11,5,11,23)
            painter.drawLine(4,17,24,17)
        elif kind=='relation':
            painter.drawRoundedRect(3,5,8,8,2,2);painter.drawRoundedRect(17,15,8,8,2,2)
            painter.drawLine(11,10,17,19)
        elif kind=='run':
            painter.setBrush(ink)
            painter.drawPolygon(QPolygonF([QPointF(8,5),QPointF(23,14),QPointF(8,23)]))
        elif kind=='refresh':
            painter.drawArc(6,6,16,16,40*16,285*16)
            painter.drawLine(20,5,23,9);painter.drawLine(23,9,18,10)
        else:
            painter.drawEllipse(5,5,18,18);painter.drawLine(14,12,14,18)
            painter.drawPoint(14,9)
        painter.end()
        return QIcon(pix)

    def init_shell(self):
        self.tabs=QTabWidget()
        self.tabs.setMovable(False)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_data_tab)
        self.setCentralWidget(self.tabs)
        self.welcome=WelcomePanel(self.lang,self.new_database,self.open_dialog,self.report_bug)
        self.tabs.addTab(self.welcome,ui('Welcome',self.lang))
        self.query_page=QWidget()
        qlayout=QVBoxLayout(self.query_page)
        qlayout.setContentsMargins(0,0,0,0)
        self.editor=SQLEditor(self.theme)
        query_controls=QHBoxLayout()
        query_controls.setContentsMargins(8,5,8,3)
        query_controls.setSpacing(7)
        self.query_hint_label=QLabel(ui('SQL Editor  ·  IntelliSense: Ctrl+Space',self.lang))
        query_controls.addWidget(self.query_hint_label)
        query_controls.addStretch(1)
        self.query_zoom_out_button=QPushButton('−')
        self.query_zoom_out_button.setObjectName('queryZoomOutButton')
        self.query_zoom_out_button.setToolTip('Decrease SQL editor font (Ctrl+-)')
        self.query_zoom_out_button.setMinimumWidth(40)
        self.query_zoom_out_button.clicked.connect(self.editor.zoom_out_text)
        query_controls.addWidget(self.query_zoom_out_button)
        self.query_zoom_percent=QLabel('100%')
        self.query_zoom_percent.setObjectName('queryZoomPercent')
        self.query_zoom_percent.setMinimumWidth(50)
        self.query_zoom_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        query_controls.addWidget(self.query_zoom_percent)
        self.query_zoom_in_button=QPushButton('+')
        self.query_zoom_in_button.setObjectName('queryZoomInButton')
        self.query_zoom_in_button.setToolTip('Increase SQL editor font (Ctrl++ or Ctrl+=)')
        self.query_zoom_in_button.setMinimumWidth(40)
        self.query_zoom_in_button.clicked.connect(self.editor.zoom_in_text)
        query_controls.addWidget(self.query_zoom_in_button)
        self.query_zoom_reset_button=QPushButton('100%')
        self.query_zoom_reset_button.setObjectName('queryZoomResetButton')
        self.query_zoom_reset_button.setToolTip('Reset SQL font size (Ctrl+0)')
        self.query_zoom_reset_button.clicked.connect(self.editor.zoom_reset_text)
        query_controls.addWidget(self.query_zoom_reset_button)
        self.editor.on_zoom_changed=self.update_query_zoom_label
        self.editor.set_zoom(int(self.prefs.value('editor/font_size',11)))
        self.update_query_zoom_label(self.editor.font_point_size)
        qlayout.addLayout(query_controls)
        self._query_shortcuts=[]
        for sequence,handler in (('Ctrl++',self.editor.zoom_in_text),
                                 ('Ctrl+=',self.editor.zoom_in_text),
                                 ('Ctrl+-',self.editor.zoom_out_text),
                                 ('Ctrl+0',self.editor.zoom_reset_text)):
            shortcut=QShortcut(QKeySequence(sequence),self.query_page)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._query_shortcuts.append(shortcut)
        self.editor.setPlainText('-- '+self.text('tip')+'\n\n-- '+self.text('try_sql')+'\n')
        qlayout.addWidget(self.editor)
        self.output_tabs=QTabWidget()
        self.results=QTableWidget()
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setAlternatingRowColors(True)
        self.results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.results.verticalHeader().setVisible(False)
        self.messages=QTextEdit()
        self.messages.setReadOnly(True)
        self.output_tabs.addTab(self.results,self.text('results'))
        self.output_tabs.addTab(self.messages,self.text('messages'))
        self.tabs.addTab(self.query_page,self.text('sql_editor'))
        self.diagram_page=QWidget()
        diagram_layout=QVBoxLayout(self.diagram_page)
        diagram_layout.setContentsMargins(7,7,7,7)
        actions=QHBoxLayout()
        make_table=QPushButton('＋  '+self.text('new_table'))
        make_table.setObjectName('diagramNewTableButton')
        make_table.clicked.connect(self.new_table)
        actions.addWidget(make_table)
        linkbtn=QPushButton('🔗  '+self.text('new_relation'))
        linkbtn.setObjectName('diagramConnectButton')
        linkbtn.setProperty('role','primary')
        linkbtn.clicked.connect(self.new_relation)
        actions.addWidget(linkbtn)
        self.link_mode_button=QPushButton('↗  '+self.text('diagram_drag'))
        self.link_mode_button.setCheckable(True)
        self.link_mode_button.setToolTip('Enable, then drag with the left mouse button from the parent table to the child table. Drag onto the same table for a hierarchy.')
        actions.addWidget(self.link_mode_button)
        self.restore_diagram_button=QPushButton('↺  '+self.text('diagram_reopen'))
        self.restore_diagram_button.setObjectName('diagramRestoreButton')
        self.restore_diagram_button.clicked.connect(self.reopen_diagram_tables)
        actions.addWidget(self.restore_diagram_button)
        self.auto_layout_button=QPushButton(self.text('diagram_auto_layout'))
        self.auto_layout_button.setToolTip('Put highly connected tables in the center and arrange related tables around them.')
        self.auto_layout_button.clicked.connect(self.diagram_auto_layout)
        actions.addWidget(self.auto_layout_button)
        actions.addStretch(1)
        # Horizontal scrolling prevents the many diagram controls from imposing
        # an enormous minimum width on small laptop screens.
        action_host=QWidget()
        action_host.setLayout(actions)
        self.diagram_actions_scroll=QScrollArea()
        self.diagram_actions_scroll.setObjectName('diagramToolbarScroll')
        self.diagram_actions_scroll.setWidgetResizable(False)
        self.diagram_actions_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.diagram_actions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.diagram_actions_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.diagram_actions_scroll.setMinimumHeight(72)
        self.diagram_actions_scroll.setMaximumHeight(90)
        self.diagram_actions_scroll.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        diagram_layout.addWidget(self.diagram_actions_scroll)
        self.diagram_hint=QLabel(self.text('diagram_hint'))
        self.diagram_hint.setProperty('role','muted')
        self.diagram_hint.setWordWrap(True)
        diagram_layout.addWidget(self.diagram_hint)
        self.diagram=Diagram(self.theme)
        self.diagram.set_language(self.lang)
        self.diagram.set_actions(self.design_table,self.new_table,self.new_relation_between,
                                 self.new_relation_columns,self.delete_diagram_relationship,
                                 self.diagram_relationship_selected)
        self.link_mode_button.toggled.connect(self.diagram.start_connect)
        self.draw_link_button=QPushButton('✎  '+self.text('diagram_draw'))
        self.draw_link_button.setObjectName('diagramDrawLinkButton')
        self.draw_link_button.setCheckable(True)
        self.draw_link_button.setToolTip('Click the parent PRIMARY KEY field, then click the matching child FOREIGN KEY field. Escape cancels.')
        self.draw_link_button.toggled.connect(self.toggle_manual_draw)
        self.diagram.on_manual_cancel=lambda:self.draw_link_button.setChecked(False)
        self.diagram.on_manual_activate=lambda:self.draw_link_button.setChecked(True)
        self.diagram.on_link_progress=self.set_diagram_hint
        actions.insertWidget(3,self.draw_link_button)
        self.delete_link_button=QPushButton('×  '+self.text('diagram_delete'))
        self.delete_link_button.setObjectName('diagramDeleteLinkButton')
        self.delete_link_button.setEnabled(False)
        self.delete_link_button.setToolTip('Select an existing relationship line first. Deletion changes the actual database FK, not just the drawing.')
        self.delete_link_button.clicked.connect(self.diagram.delete_selected_edge)
        actions.insertWidget(4,self.delete_link_button)
        fit_button=QPushButton(self.text('diagram_fit'))
        fit_button.setObjectName('diagramFitButton')
        fit_button.setToolTip('Zoom out to show every table at once. Use 100% for easier field selection.')
        fit_button.clicked.connect(self.diagram.fit_diagram)
        actions.addWidget(fit_button)
        # Dedicated zoom controls remain useful when Auto Layout fits many
        # tables at an exceptionally small scale (Ctrl+wheel also works).
        self.zoom_out_button=QPushButton('−  '+self.text('diagram_zoom_out'))
        self.zoom_out_button.setObjectName('diagramZoomOutButton')
        self.zoom_out_button.setToolTip('Zoom out one step. Shortcut: Ctrl + mouse wheel down in the diagram.')
        self.zoom_out_button.clicked.connect(self.diagram.zoom_out)
        actions.addWidget(self.zoom_out_button)
        self.zoom_in_button=QPushButton('+  '+self.text('diagram_zoom_in'))
        self.zoom_in_button.setObjectName('diagramZoomInButton')
        self.zoom_in_button.setToolTip('Zoom in one step. Works even after Fit / Auto Layout makes many tables tiny.')
        self.zoom_in_button.clicked.connect(self.diagram.zoom_in)
        actions.addWidget(self.zoom_in_button)
        self.diagram_zoom_percent=QLabel('100%')
        self.diagram_zoom_percent.setObjectName('diagramZoomPercent')
        self.diagram_zoom_percent.setMinimumWidth(56)
        self.diagram_zoom_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diagram_zoom_percent.setToolTip('Current diagram zoom level')
        self.diagram.on_zoom_changed=self.update_diagram_zoom_percent
        actions.addWidget(self.diagram_zoom_percent)
        zoom_button=QPushButton('100%')
        zoom_button.setObjectName('diagramZoomButton')
        zoom_button.setToolTip('Show readable field sizes for direct column linking.')
        zoom_button.clicked.connect(self.diagram.zoom_actual)
        actions.addWidget(zoom_button)
        # Qt takes the content widget's size when setWidget() is called. Setting
        # it before inserting the later Draw/Delete/Fit buttons clipped labels.
        # Keep the natural content width and scroll rather than shrinking text.
        self.diagram_action_host=action_host
        self.diagram_button_layout=actions
        self.diagram_actions_scroll.setWidget(action_host)
        self.resize_diagram_toolbar()
        self.diagram.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._diagram_shortcuts=[]
        for sequence,handler in (('Ctrl++',self.diagram.zoom_in),
                                 ('Ctrl+=',self.diagram.zoom_in),
                                 ('Ctrl+-',self.diagram.zoom_out),
                                 ('Ctrl+0',self.diagram.zoom_actual)):
            shortcut=QShortcut(QKeySequence(sequence),self.diagram_page)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._diagram_shortcuts.append(shortcut)
        diagram_layout.addWidget(self.diagram,1)
        self.tabs.addTab(self.diagram_page,self.text('diagram'))
        # Main pages may be hidden using their tab ×; View reopens them safely.
        for page in (self.welcome,self.query_page,self.diagram_page):
            self.install_tab_close_button(page)
        self.explorer=QTreeWidget()
        self.explorer.setHeaderHidden(True)
        self.explorer.setAnimated(True)
        self.explorer.setAlternatingRowColors(False)
        self.explorer.itemDoubleClicked.connect(self.tree_double)
        self.explorer.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.explorer.customContextMenuRequested.connect(self.explorer_menu)
        self.explorer.currentItemChanged.connect(self.tree_current)
        self.leftdock=QDockWidget(self.text('object_explorer'),self)
        self.leftdock.setObjectName('explorerDock')
        self.leftdock.setWidget(self.explorer)
        self.leftdock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                                  QDockWidget.DockWidgetFeature.DockWidgetFloatable |
                                  QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,self.leftdock)
        self.leftdock.setTitleBarWidget(ClearDockTitleBar(self.leftdock,self.lang))
        self.explorer.setMinimumWidth(110)
        self.propetext=QTextEdit()
        self.propetext.setReadOnly(True)
        # Long FK paths and messages must not disappear beyond narrow docks.
        self.propetext.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.propetext.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.propetext.setPlainText(self.text('guide_empty'))
        self.rightdock=QDockWidget(self.text('properties'),self)
        self.rightdock.setObjectName('propertyDock')
        self.rightdock.setWidget(self.propetext)
        self.rightdock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                                   QDockWidget.DockWidgetFeature.DockWidgetFloatable |
                                   QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.rightdock)
        self.rightdock.setTitleBarWidget(ClearDockTitleBar(self.rightdock,self.lang))
        self.propetext.setMinimumWidth(165)
        self.bottomdock=QDockWidget('Query Results / Messages',self)
        self.bottomdock.setObjectName('outputDock')
        self.bottomdock.setWidget(self.output_tabs)
        self.bottomdock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                                    QDockWidget.DockWidgetFeature.DockWidgetFloatable |
                                    QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.output_tabs.setMinimumHeight(100)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,self.bottomdock)
        self.bottomdock.setTitleBarWidget(ClearDockTitleBar(self.bottomdock,self.lang))
        self.resizeDocks([self.leftdock,self.rightdock],[225,235],Qt.Orientation.Horizontal)
        self.resizeDocks([self.bottomdock],[225],Qt.Orientation.Vertical)
        self.bottom_line=QLabel(self.text('v_notice'))
        self.statusBar().addPermanentWidget(self.bottom_line)
        self.statusBar().showMessage(self.text('ready'))
        self.activate_main_tab(self.welcome)
    def install_tab_close_button(self, page):
        """Explicit visible ×; close only the view and never drop table/data."""
        index=self.tabs.indexOf(page)
        if index<0:return
        tabbar=self.tabs.tabBar()
        existing=tabbar.tabButton(index,QTabBar.ButtonPosition.RightSide)
        if existing and existing.objectName()=='clearTabCloseButton':
            existing.setToolTip('بستن این زبانه؛ از منوی نمایش دوباره باز کنید' if self.lang=='fa'
                                else 'Close tab; use View to reopen')
            return
        button=QPushButton('×',tabbar)
        button.setObjectName('clearTabCloseButton')
        button.setFixedSize(25,25)
        button.setToolTip('بستن این زبانه؛ از منوی نمایش دوباره باز کنید' if self.lang=='fa'
                          else 'Close tab; use View to reopen')
        def hide_tab():
            current=self.tabs.indexOf(page)
            if current>=0:self.close_data_tab(current)
        button.clicked.connect(hide_tab)
        tabbar.setTabButton(index,QTabBar.ButtonPosition.RightSide,button)

    def activate_main_tab(self, page):
        """Reopen a hidden central page, preserving its editor/diagram state."""
        if page is None:
            return
        if self.tabs.indexOf(page) < 0:
            if page is self.welcome:
                # Recreate to reflect language changes made while Welcome was hidden.
                self.welcome.deleteLater()
                self.welcome = WelcomePanel(self.lang,self.new_database,
                                            self.open_dialog,self.report_bug)
                page = self.welcome
                self.tabs.insertTab(0,page,ui('Welcome',self.lang))
            elif page is self.query_page:
                self.tabs.insertTab(0,page,self.text('sql_editor'))
            elif page is self.diagram_page:
                position=1 if self.tabs.indexOf(self.query_page)>=0 else 0
                self.tabs.insertTab(position,page,self.text('diagram'))
        self.install_tab_close_button(page)
        self.tabs.setCurrentWidget(page)

    def resize_diagram_toolbar(self):
        """Never compress diagram actions below their complete label width."""
        if not hasattr(self, 'diagram_action_host'):
            return
        from PySide6.QtGui import QFontMetrics
        for button in self.diagram_action_host.findChildren(QPushButton):
            metrics=QFontMetrics(button.font())
            # Font-dependent width plus the actual QSS padding and borders.
            button.setMinimumWidth(max(button.sizeHint().width(),
                                       metrics.horizontalAdvance(button.text())+38))
            button.setMinimumHeight(42)
            button.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed)
        self.diagram_button_layout.invalidate()
        needed=self.diagram_button_layout.sizeHint()
        self.diagram_action_host.setMinimumWidth(needed.width())
        self.diagram_action_host.resize(needed)
        self.diagram_actions_scroll.setMinimumHeight(max(70,needed.height()+18))
        self.diagram_actions_scroll.setMaximumHeight(max(90,needed.height()+24))

    def action(self,label,func,icon_name=None,shortcut=None):
        a=QAction(self.icon(icon_name) if icon_name else QIcon(),label,self)
        a.triggered.connect(func)
        if shortcut:a.setShortcut(QKeySequence(shortcut))
        return a
    def build_commands(self):
        self.menuBar().clear()
        filemenu=self.menuBar().addMenu(self.text('file'))
        self.act_new=self.action(self.text('new_database'),self.new_database,'new','Ctrl+N')
        self.act_open=self.action(self.text('open_database'),self.open_dialog,'open','Ctrl+O')
        self.act_close=self.action(self.text('close_database'),self.close_database)
        self.act_exit=self.action(self.text('exit'),self.close)
        for a in [self.act_new,self.act_open,self.act_close]:filemenu.addAction(a)
        self.act_open_script=self.action(ui('Open SQL Script…',self.lang),self.open_sql_file,'open','Ctrl+Shift+O')
        filemenu.addAction(self.act_open_script)
        filemenu.addSeparator()
        filemenu.addAction(self.act_exit)
        dbmenu=self.menuBar().addMenu(self.text('database'))
        self.act_table=self.action(self.text('new_table'),self.new_table,'table','Ctrl+T')
        self.act_relation=self.action(self.text('new_relation'),self.new_relation,'relation','Ctrl+R')
        self.act_design_table=self.action(ui('Design Selected Table…',self.lang),self.design_selected_table,'table','Ctrl+D')
        self.act_demo=self.action(self.text('demo'),self.create_demo)
        self.act_refresh=self.action(self.text('refresh'),self.refresh_all,'refresh','Ctrl+F5')
        self.act_integrity=self.action(ui('Check Referential Integrity…',self.lang),self.check_integrity)
        self.act_add=self.action(self.text('add_record'),self.insert_selected)
        self.act_edit_record=self.action(ui('Edit Selected Record…',self.lang),self.edit_selected_record)
        self.act_delete_record=self.action(ui('Delete Selected Record…',self.lang),self.delete_selected_record)
        for a in [self.act_table,self.act_design_table,self.act_relation,self.act_demo,self.act_add,self.act_edit_record,self.act_delete_record,self.act_integrity,self.act_refresh]:dbmenu.addAction(a)
        design=self.menuBar().addMenu(self.text('design'))
        self.act_export=self.action(self.text('export_erd'),self.export_diagram,'save')
        self.act_script=self.action(self.text('generate_scripts'),self.generate_scripts,'save')
        design.addAction(self.act_export)
        design.addAction(self.act_script)
        filemenu.insertAction(self.act_exit,self.act_script)
        filemenu.insertSeparator(self.act_exit)
        self.act_run=self.action(self.text('execute'),self.execute_sql,'run','F5')
        design.addAction(self.act_run)
        view=self.menuBar().addMenu(self.text('view'))
        view.addAction(self.leftdock.toggleViewAction())
        view.addAction(self.rightdock.toggleViewAction())
        view.addAction(self.bottomdock.toggleViewAction())
        view.addSeparator()
        view.addAction(self.action(ui('Show SQL Editor',self.lang),
                                   lambda:self.activate_main_tab(self.query_page)))
        view.addAction(self.action(ui('Show Database Diagram',self.lang),
                                   lambda:self.activate_main_tab(self.diagram_page)))
        view.addAction(self.action(ui('Show Welcome Screen',self.lang),
                                   lambda:self.activate_main_tab(self.welcome)))
        view.addSeparator()
        view.addAction(self.action(ui('Show All Panels',self.lang),self.show_all_panels))
        view.addAction(self.action(ui('Reset Window Layout',self.lang),self.reset_window_layout))
        helpmenu=self.menuBar().addMenu(self.text('help'))
        helpmenu.addAction(self.action(self.text('report_bug'),self.report_bug,'help'))
        helpmenu.addAction(self.action(self.text('email_app'),self.report_mailto))
        helpmenu.addSeparator()
        helpmenu.addAction(self.action(self.text('about'),self.about,'help'))
        if hasattr(self,'toolbar'):
            self.removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
        self.toolbar=QToolBar('Quick actions',self)
        self.toolbar.setObjectName('actionsToolbar')
        self.toolbar.setMovable(True)
        self.toolbar.setIconSize(QSize(22,22))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea,self.toolbar)
        view.insertAction(view.actions()[0],self.toolbar.toggleViewAction())
        view.insertSeparator(view.actions()[1])
        for a in (self.act_new,self.act_open,self.act_table,self.act_relation,self.act_script,self.act_run,self.act_refresh):
            self.toolbar.addAction(a)
            if a==self.act_open or a==self.act_relation:self.toolbar.addSeparator()
        filler=QWidget()
        from PySide6.QtWidgets import QSizePolicy
        filler.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(filler)
        tag=QLabel(self.text('subtitle')+'   ')
        tag.setProperty('role','eyebrow')
        self.toolbar.addWidget(tag)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(QLabel(self.text('language')+': '))
        self.language_combo=QComboBox()
        self.language_combo.addItem('English','en')
        self.language_combo.addItem('فارسی','fa')
        self.language_combo.setCurrentIndex(0 if self.lang=='en' else 1)
        self.language_combo.currentIndexChanged.connect(self.language_changed)
        self.toolbar.addWidget(self.language_combo)
        self.toolbar.addWidget(QLabel('  '+self.text('theme')+': '))
        self.theme_combo=QComboBox()
        self.theme_combo.addItem(self.text('dark'),'dark')
        self.theme_combo.addItem(self.text('light'),'light')
        self.theme_combo.setCurrentIndex(0 if self.theme=='dark' else 1)
        self.theme_combo.currentIndexChanged.connect(self.theme_changed)
        self.toolbar.addWidget(self.theme_combo)
        self.act_close.setEnabled(self.db is not None)
        for a in [self.act_table,self.act_design_table,self.act_relation,self.act_demo,self.act_add,self.act_edit_record,self.act_delete_record,self.act_integrity,self.act_refresh,self.act_export,self.act_script,self.act_run]:
            a.setEnabled(self.db is not None or a is self.act_run)
    def language_changed(self):
        new=self.language_combo.currentData()
        if new and new!=self.lang:
            self.lang=new
            self.prefs.setValue('language',new)
            self.set_fonts()
            self.retranslate()
    def theme_changed(self):
        new=self.theme_combo.currentData()
        if new and new!=self.theme:
            self.theme=new
            self.prefs.setValue('theme',new)
            apply_palette(QApplication.instance(),new)
            self.editor.set_theme(new)
            self.diagram.set_theme(new)
            self.build_commands()
            self.resize_diagram_toolbar()
            self.refresh_explorer()
    def retranslate(self):
        self.diagram.set_language(self.lang)
        self.setWindowTitle(self.text('app_name')+('  •  '+self.db.path.stem if self.db else '')+'  |  v'+APP_VERSION)
        self.build_commands()
        self.output_tabs.setTabText(0,self.text('results'))
        self.output_tabs.setTabText(1,self.text('messages'))
        for page,label in ((self.query_page,self.text('sql_editor')),
                           (self.diagram_page,self.text('diagram'))):
            idx=self.tabs.indexOf(page)
            if idx>=0:self.tabs.setTabText(idx,label)
        self.bottomdock.setWindowTitle('Query Results / Messages' if self.lang=='en' else 'نتایج و پیام‌های پرس‌وجو')
        for dock in (self.leftdock,self.rightdock,self.bottomdock):
            header=dock.titleBarWidget()
            if isinstance(header,ClearDockTitleBar):header.set_language(self.lang)
        connect=self.diagram_page.findChild(QPushButton,'diagramConnectButton')
        if connect:connect.setText('🔗  '+self.text('new_relation'))
        for name,key,prefix in (
            ('diagramNewTableButton','new_table','＋  '),
            ('diagramDrawLinkButton','diagram_draw','✎  '),
            ('diagramDeleteLinkButton','diagram_delete','×  '),
            ('diagramRestoreButton','diagram_reopen','↺  '),
            ('diagramFitButton','diagram_fit','')):
            button=self.diagram_page.findChild(QPushButton,name)
            if button:button.setText(prefix+self.text(key))
        self.link_mode_button.setText('↗  '+self.text('diagram_drag'))
        self.auto_layout_button.setText(self.text('diagram_auto_layout'))
        self.zoom_in_button.setText('+  '+self.text('diagram_zoom_in'))
        self.zoom_out_button.setText('−  '+self.text('diagram_zoom_out'))
        self.query_hint_label.setText(ui('SQL Editor  ·  IntelliSense: Ctrl+Space',self.lang))
        self.query_zoom_in_button.setToolTip(ui('Increase SQL editor font (Ctrl++ or Ctrl+=)',self.lang))
        self.query_zoom_out_button.setToolTip(ui('Decrease SQL editor font (Ctrl+-)',self.lang))
        self.query_zoom_reset_button.setToolTip(ui('Reset SQL font size (Ctrl+0)',self.lang))
        self.diagram_hint.setText(self.text('diagram_hint'))
        self.link_mode_button.setToolTip(ui('Enable, then drag with the left mouse button from the parent table to the child table. Drag onto the same table for a hierarchy.',self.lang))
        self.draw_link_button.setToolTip(ui('Click the parent PRIMARY KEY field, then click the matching child FOREIGN KEY field. Escape cancels.',self.lang))
        self.delete_link_button.setToolTip(ui('Select an existing relationship line first. Deletion changes the actual database FK, not just the drawing.',self.lang))
        self.auto_layout_button.setToolTip(ui('Put highly connected tables in the center and arrange related tables around them.',self.lang))
        self.diagramZoomButtonTooltip()
        self.leftdock.setWindowTitle(self.text('object_explorer'))
        self.rightdock.setWindowTitle(self.text('properties'))
        self.bottom_line.setText(self.text('v_notice'))
        self.resize_diagram_toolbar()
        for ix in range(self.tabs.count()):
            self.install_tab_close_button(self.tabs.widget(ix))
        if self.welcome and self.tabs.indexOf(self.welcome)>=0:
            ix=self.tabs.indexOf(self.welcome)
            self.tabs.removeTab(ix)
            self.welcome.deleteLater()
            self.welcome=WelcomePanel(self.lang,self.new_database,self.open_dialog,self.report_bug)
            self.tabs.insertTab(0,self.welcome,'Welcome' if self.lang=='en' else 'خوش‌آمدید')
            self.install_tab_close_button(self.welcome)
        for table,tab in self.data_tabs.items():
            button_names={'editRowsButton':'Edit Rows','editSelectedRecordButton':'Edit Record',
                          'deleteSelectedRecordButton':'Delete Record','closeDataViewButton':'Close View'}
            for object_name,english in button_names.items():
                button=tab.findChild(QPushButton,object_name)
                if button:button.setText(ui(english,self.lang))
            idx=self.tabs.indexOf(tab)
            if idx>=0:self.tabs.setTabText(idx,self.text('data_title',table=table))
            for button in tab.findChildren(QPushButton):
                if button.objectName()=='addRowButton':button.setText('＋  '+self.text('add_record'))
                if button.objectName()=='refreshDataButton':button.setText(self.text('refresh'))
        self.refresh_explorer()
    def diagramZoomButtonTooltip(self):
        for name,english in (
            ('diagramFitButton','Zoom out to show every table at once. Use 100% for easier field selection.'),
            ('diagramZoomInButton','Zoom in one step. Works even after Fit / Auto Layout makes many tables tiny.'),
            ('diagramZoomOutButton','Zoom out one step. Shortcut: Ctrl + mouse wheel down in the diagram.'),
            ('diagramZoomButton','Show readable field sizes for direct column linking.'),
            ('diagramZoomPercent','Current diagram zoom level')
        ):
            target=self.diagram_page.findChild(QWidget,name)
            if target:target.setToolTip(ui(english,self.lang))

    def language_prompt_first_run(self):
        if not self.prefs.contains('language'):
            dlg=LanguageChoice('en',self)
            if dlg.exec():
                self.lang=dlg.language
                self.prefs.setValue('language',self.lang)
                self.set_fonts()
                self.retranslate()
            else:
                self.prefs.setValue('language','en')
    def require_db(self):
        if self.db is None:
            QMessageBox.information(self,self.text('no_db'),self.text('select_database'))
            return False
        return True
    def new_database(self):
        APP_FOLDER.mkdir(parents=True,exist_ok=True)
        dlg=NewDatabaseWizard(self.lang,APP_FOLDER,self)
        if dlg.exec() and dlg.created_path:
            self.load_database(dlg.created_path)
    def open_dialog(self):
        path,_=QFileDialog.getOpenFileName(self,self.text('open_database'),str(APP_FOLDER),
                'Database Files (*.db *.sqlite *.sqlite3);;All Files (*)')
        if path:self.load_database(path)
    def load_database(self,path):
        try:
            incoming=LabDatabase(path)
        except Exception as exc:
            error(self,self.lang,exc)
            return
        if self.db:self.db.close()
        self.db=incoming
        self.editor.set_database(incoming)
        self._schema_seen=incoming.schema_version()
        self.setWindowTitle(self.text('app_name')+'  •  '+Path(path).stem+'  |  v'+APP_VERSION)
        if self.welcome is not None and self.tabs.indexOf(self.welcome)>=0:
            self.tabs.removeTab(self.tabs.indexOf(self.welcome))
        for table,tab in list(self.data_tabs.items()):
            index=self.tabs.indexOf(tab)
            if index>=0:self.tabs.removeTab(index)
            tab.deleteLater()
        self.data_tabs.clear()
        self.refresh_all()
        self.build_commands()
        self.activate_main_tab(self.query_page)
        self.statusBar().showMessage(str(path))
    def close_database(self):
        if self.db:self.db.close()
        self.db=None
        self.editor.set_database(None)
        self._schema_seen=None
        for table,tab in list(self.data_tabs.items()):
            index=self.tabs.indexOf(tab)
            if index>=0:self.tabs.removeTab(index)
            tab.deleteLater()
        self.data_tabs.clear()
        self.diagram.set_db(None)
        if self.welcome is not None and self.tabs.indexOf(self.welcome)<0:
            self.welcome=WelcomePanel(self.lang,self.new_database,self.open_dialog,self.report_bug)
            self.tabs.insertTab(0,self.welcome,'Welcome' if self.lang=='en' else 'خوش‌آمدید')
            self.install_tab_close_button(self.welcome)
        self.activate_main_tab(self.welcome)
        self.refresh_explorer()
        self.build_commands()
        self.setWindowTitle(self.text('app_name')+'  |  v'+APP_VERSION)
    def check_external_schema_changes(self):
        """Refresh only when schema cookie changes; no hidden stale UI references."""
        if not self.db:return
        try:
            version=self.db.schema_version()
        except Exception as exc:
            self.statusBar().showMessage('Database schema could not be refreshed: '+str(exc),8000)
            return
        if self._schema_seen is None:self._schema_seen=version
        elif version!=self._schema_seen:
            self._schema_seen=version
            try:
                self.db.reconcile_schema()
                self.refresh_all()
            except Exception as exc:
                self.statusBar().showMessage('Schema update error: '+str(exc),10000)

    def show_all_panels(self):
        for dock in (self.leftdock,self.rightdock,self.bottomdock):
            dock.show()

    def reset_window_layout(self):
        for dock,area in ((self.leftdock,Qt.DockWidgetArea.LeftDockWidgetArea),
                          (self.rightdock,Qt.DockWidgetArea.RightDockWidgetArea),
                          (self.bottomdock,Qt.DockWidgetArea.BottomDockWidgetArea)):
            dock.setFloating(False)
            self.addDockWidget(area,dock)
            dock.show()
        self.resizeDocks([self.leftdock,self.rightdock],[225,235],Qt.Orientation.Horizontal)
        self.resizeDocks([self.bottomdock],[200],Qt.Orientation.Vertical)
        self.statusBar().showMessage(ui('Dock layout restored. Drag separators to resize, or float panels by their title bars.',self.lang),7000)

    def update_query_zoom_label(self,size):
        self.query_zoom_percent.setText(f'{round(size/self.editor.DEFAULT_FONT*100)}%')
        self.prefs.setValue('editor/font_size',size)

    def update_diagram_zoom_percent(self, scale):
        """Show precise percentage for very large auto-fitted diagrams."""
        percent=scale*100
        value=f'{percent:.1f}%' if percent<10 else f'{percent:.0f}%'
        self.diagram_zoom_percent.setText(value)

    def diagram_auto_layout(self):
        if not self.require_db():return
        try:
            self.diagram.auto_layout()
        except Exception as exc:error(self,self.lang,exc)

    def drop_table_ui(self,table):
        if not self.require_db():return
        if table not in self.db.tables():
            self.refresh_all();return
        check=QMessageBox.question(self,ui('Permanently DROP TABLE',self.lang),
            f'DROP TABLE {table}?\n\nAll rows in this table will be deleted permanently. '
            'This cannot be undone. Tables referenced by other tables are protected.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if check!=QMessageBox.StandardButton.Yes:return
        try:
            message=self.db.drop_table(table)
            self.refresh_all()
            self.statusBar().showMessage(message,10000)
        except Exception as exc:error(self,self.lang,exc)

    def drop_column_ui(self,table):
        if not self.require_db() or table not in self.db.tables():return
        from PySide6.QtWidgets import QInputDialog
        columns=[c['name'] for c in self.db.columns(table) if not c['pk']]
        if not columns:
            QMessageBox.information(self,ui('Drop Column',self.lang),'No removable non-primary column exists.')
            return
        column,accepted=QInputDialog.getItem(self,'Drop Column',f'Select a column to remove from {table}:',columns,0,False)
        if not accepted:return
        if QMessageBox.question(self,ui('Permanently DROP COLUMN',self.lang),
              f'DROP {table}.{column}? All stored values in this column will be permanently lost.',
              QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
              QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:
            message=self.db.drop_column(table,column)
            self.refresh_all()
            self.statusBar().showMessage(message,10000)
        except Exception as exc:error(self,self.lang,exc)

    def new_table(self):
        if not self.require_db():return
        dlg=TableDesigner(self.db,self.lang,self.refresh_all,self)
        dlg.exec()
    def check_integrity(self):
        if not self.require_db():return
        try:issues=self.db.check_integrity()
        except Exception as exc:error(self,self.lang,exc);return
        if not issues:
            QMessageBox.information(self,ui('Referential Integrity',self.lang),'All foreign-key constraints are valid. No orphan references were found.')
        else:
            details='\n'.join(f"{r['table']} rowid={r['rowid']} → {r['parent']}" for r in issues[:50])
            QMessageBox.warning(self,'Referential Integrity',f'{len(issues)} invalid reference(s) found:\n'+details)
    def design_selected_table(self):
        table=self.selected_table()
        if table:self.design_table(table)
        else:QMessageBox.information(self,ui('Design Table',self.lang),'Select a table in Object Explorer or double-click one in the diagram.')
    def design_table(self,table):
        if not self.require_db() or table not in self.db.tables():return
        dlg=TableDesigner(self.db,self.lang,self.refresh_all,self,table=table)
        dlg.exec()
    def set_diagram_hint(self,message):
        self.diagram_hint.setText(message)
        self.statusBar().showMessage(message,10000)

    def toggle_manual_draw(self,active):
        if active and hasattr(self,'link_mode_button'):
            self.link_mode_button.setChecked(False)
        self.diagram.start_manual_drawing(active)
        if active:
            self.statusBar().showMessage(ui('Draw Link: click the parent PK field and then the child FK field. Press Esc to cancel.',self.lang),12000)

    def diagram_relationship_selected(self,link):
        self.delete_link_button.setEnabled(bool(link))
        if link:
            text=(f"{link['kind']}  |  {link['parent']} → {link['child']}  |  "
                  f"{link.get('fk','')}")
            self.statusBar().showMessage(ui('Selected relationship: ',self.lang)+text)
            self.propetext.setPlainText(ui('RELATIONSHIP SELECTED',self.lang)+'\n'+'─'*35+'\n'
                +text+'\n\n'+ui('Right-click the line or press Delete to remove this FK. Columns, records and tables will be kept.',self.lang)
                +'\n\n'+ui('WARNING: removing the FK removes its referential-integrity enforcement.',self.lang))

    def delete_diagram_relationship(self,link):
        if not self.require_db():return
        semantic=bool(link.get('semantic'))
        if semantic:
            detail=(ui('Delete both foreign keys of the N:M relationship via {bridge}?',self.lang).format(bridge=link.get('bridge'))
                    +'\n\n'+ui('The junction table, its columns, and all existing records will be kept.',self.lang))
        else:
            detail=(ui('Delete the relationship {relation}?',self.lang).format(relation=f"{link.get('parent')} → {link.get('child')} ({link.get('fk')})")
                    +'\n\n'+ui('The foreign key rule will be removed, but all tables, columns and rows will be preserved.',self.lang))
        detail+='\n\n'+ui('Future orphan references will no longer be blocked by the removed FK.',self.lang)
        response=QMessageBox.question(self,ui('Delete Relationship',self.lang),detail,
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if response!=QMessageBox.StandardButton.Yes:return
        try:
            if semantic:
                result=self.db.remove_many_to_many_link(link['bridge'])
            else:
                result=self.db.remove_relationship(link['child'],link['fk_id'])
        except Exception as exc:
            error(self,self.lang,exc);return
        self.refresh_all()
        self.activate_main_tab(self.diagram_page)
        self.statusBar().showMessage(result,12000)
        QMessageBox.information(self,ui('Relationship removed',self.lang),result)

    def new_relation_columns(self,source_table,source_field,target_table,target_field):
        if not self.require_db():return
        if (source_table,source_field)==(target_table,target_field):return
        try:
            spk=self.db.primary_key(source_table)['name']
            tpk=self.db.primary_key(target_table)['name']
        except Exception as exc:
            error(self,self.lang,exc);return
        # Allow dragging FK -> PK too. Internally normalize to PK -> FK.
        if source_field.casefold()!=spk.casefold() and target_field.casefold()==tpk.casefold():
            source_table,source_field,target_table,target_field=(
                target_table,target_field,source_table,source_field)
        elif source_field.casefold()!=spk.casefold():
            QMessageBox.warning(self,ui('Field Mapping',self.lang),
                ui('Start the link from the PRIMARY KEY field of the parent table, or drag the child foreign-key field onto a parent PRIMARY KEY.',self.lang))
            return
        dlg=RelationshipWizard(self.db,self.lang,self.refresh_all,self,
                               source_table=source_table,target_table=target_table,
                               source_field=source_field,target_field=target_field)
        created=bool(dlg.exec())
        self.link_mode_button.setChecked(False)
        if hasattr(self,'draw_link_button'):self.draw_link_button.setChecked(False)
        if created:
            self.activate_main_tab(self.diagram_page)

    def reopen_diagram_tables(self):
        if not self.require_db():return
        hidden=sorted(self.diagram.hidden_tables & set(self.db.tables()))
        if not hidden:
            QMessageBox.information(self,ui('Reopen Tables',self.lang),'No tables are hidden in the diagram.')
            return
        menu=QMenu(self)
        menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.lang=='fa' else Qt.LayoutDirection.LeftToRight)
        for name in hidden:
            menu.addAction(name,lambda checked=False,n=name:self.diagram.show_table(n))
        menu.addSeparator()
        menu.addAction(('نمایش همه جدول‌ها' if self.lang=='fa' else 'Show All Tables'),self.diagram.show_all_tables)
        menu.exec(self.restore_diagram_button.mapToGlobal(
            self.restore_diagram_button.rect().bottomLeft()))

    def close_data_page(self,table):
        page=self.data_tabs.get(table)
        if page is not None:
            index=self.tabs.indexOf(page)
            if index>=0:self.close_data_tab(index)

    def close_data_tab(self,index):
        page=self.tabs.widget(index)
        if page in (self.welcome,self.query_page,self.diagram_page):
            # Only hide; never destroy SQL editor text or the live diagram.
            self.tabs.removeTab(index)
            return
        for table,tab in list(self.data_tabs.items()):
            if tab is page:
                self.data_tabs.pop(table,None)
                self.tabs.removeTab(index)
                tab.deleteLater()
                return

    def new_relation(self):
        self.new_relation_between(None,None)
    def new_relation_between(self,source=None,target=None):
        if hasattr(self,'link_mode_button'):self.link_mode_button.setChecked(False)
        if not self.require_db():return
        if not self.db.tables():
            QMessageBox.information(self,self.text('new_relation'),ui('Create at least one table first.',self.lang))
            return
        if len(self.db.tables())<2 and not (source and target and source==target):
            QMessageBox.information(self,self.text('new_relation'),
                ui('Create two tables to link them, or right-click the existing table for a self-referencing relationship.',self.lang))
            return
        dlg=RelationshipWizard(self.db,self.lang,self.refresh_all,self,
                               source_table=source,target_table=target)
        if dlg.exec():
            self.activate_main_tab(self.diagram_page)
            if hasattr(self,'link_mode_button'):self.link_mode_button.setChecked(False)
    def create_demo(self):
        if not self.require_db():return
        if QMessageBox.question(self,self.text('demo'),self.text('confirm_demo')) != QMessageBox.StandardButton.Yes:return
        try:self.db.demo()
        except Exception as exc:error(self,self.lang,exc);return
        self.refresh_all()
        self.activate_main_tab(self.diagram_page)
        info(self,self.lang,self.text('sample_ok'))
    def refresh_all(self):
        if not self.db:return
        self.editor.refresh_completion_source()
        self.refresh_explorer()
        self.diagram.set_db(self.db)
        self._schema_seen=self.db.schema_version()
        if hasattr(self,'delete_link_button'):self.delete_link_button.setEnabled(False)
        if hasattr(self,'draw_link_button'):self.draw_link_button.setChecked(False)
        if hasattr(self,'link_mode_button'):self.link_mode_button.setChecked(False)
        for name in list(self.data_tabs):
            if name in self.db.tables():
                self.update_data_tab(name)
            else:
                tab=self.data_tabs.pop(name)
                idx=self.tabs.indexOf(tab)
                if idx>=0:self.tabs.removeTab(idx)
                tab.deleteLater()
        self.statusBar().showMessage(f'{self.db.path.name}  |  '+ui('{count} tables',self.lang).format(count=len(self.db.tables())))
    def refresh_explorer(self):
        self.explorer.clear()
        if not self.db:
            top=QTreeWidgetItem([self.text('no_db')])
            self.explorer.addTopLevelItem(top)
            self.propetext.setPlainText(self.text('guide_empty'))
            return
        root=QTreeWidgetItem([self.db.path.stem])
        root.setIcon(0,self.icon('open'))
        self.explorer.addTopLevelItem(root)
        folder=QTreeWidgetItem([self.text('tables')+f' ({len(self.db.tables())})'])
        folder.setIcon(0,self.icon('open'))
        root.addChild(folder)
        for name in self.db.tables():
            table=QTreeWidgetItem([name])
            table.setData(0,Qt.ItemDataRole.UserRole,('table',name))
            table.setIcon(0,self.icon('table'))
            folder.addChild(table)
            fks={row['from'] for row in self.db.foreign_keys(name)}
            for col in self.db.columns(name):
                tags=[]
                if col['pk']:tags.append('PK')
                if col['name'] in fks:tags.append('FK')
                if is_identity(self.db,name,col['name']):tags.append('AI')
                text=f"{col['name']}  :  {self.db.logical_type(name,col['name'])}"+('  ['+'/'.join(tags)+']' if tags else '')
                column=QTreeWidgetItem([text])
                column.setData(0,Qt.ItemDataRole.UserRole,('column',name))
                table.addChild(column)
        # Routine objects belong in Object Explorer, not among physical ERD tables.
        for category,label,items in (
            ('view','نماها' if self.lang=='fa' else 'Views',views(self.db)),
            ('procedure','رویه‌های ذخیره‌شده' if self.lang=='fa' else 'Stored Procedures',list_modules(self.db,'PROCEDURE')),
            ('function','توابع اسکالر' if self.lang=='fa' else 'Scalar Functions',list_modules(self.db,'FUNCTION')),
        ):
            branch=QTreeWidgetItem([f'{label} ({len(items)})'])
            branch.setIcon(0,self.icon('open'))
            root.addChild(branch)
            for name in items:
                node=QTreeWidgetItem([name])
                node.setData(0,Qt.ItemDataRole.UserRole,(category,name))
                branch.addChild(node)
            branch.setExpanded(bool(items))
        root.setExpanded(True)
        folder.setExpanded(True)
        self.propetext.setPlainText(self.text('guide_hint')+'\n\n'+self.text('table_note'))
    def selected_table(self):
        item=self.explorer.currentItem()
        while item:
            data=item.data(0,Qt.ItemDataRole.UserRole)
            if data and data[0]=='table':return data[1]
            item=item.parent()
        return None
    def selected_module(self):
        item=self.explorer.currentItem()
        if item:
            data=item.data(0,Qt.ItemDataRole.UserRole)
            if data and data[0] in ('view','procedure','function'):
                return data
        return None

    def open_module(self,kind,name):
        # Query views directly; show non-executing templates for parameterized routines.
        if kind=='view':
            example=f'SELECT * FROM "{name}";'
        elif kind=='procedure':
            example=f'EXEC dbo.{name};  -- supply input arguments if required'
        else:
            example=f'SELECT dbo.{name}(/* arguments */);'
        self.editor.setPlainText(example)
        self.activate_main_tab(self.query_page)
        if kind=='view':self.execute_sql()

    def tree_current(self,current,previous):
        module=self.selected_module()
        if module and self.db:
            kind,name=module
            self.propetext.setPlainText(
                f'{kind.upper()}  {name}\n'+'─'*32+'\n\n'
                +'Educational SQL module. Double-click to open a query template.\n'
                +'Views execute as SQLite views; procedures and scalar functions '
                +'use a documented, limited T-SQL compatibility layer.')
            return
        table=self.selected_table()
        if not self.db or not table:return
        if table not in self.db.tables():
            self.refresh_explorer();return
        cols=self.db.columns(table)
        fks=self.db.foreign_keys(table)
        lines=[(('جدول' if self.lang=='fa' else 'TABLE')+'  '+table),'─'*33,'', ('ستون‌ها' if self.lang=='fa' else 'COLUMNS')]
        for c in cols:
            label=('PK  ' if c['pk'] else '    ')+c['name']+'  :  '+self.db.logical_type(table,c['name'])
            if is_identity(self.db,table,c['name']):
                identity=self.db.identity_settings(table)
                if identity:label+=f'   [IDENTITY({identity["seed"]},{identity["increment"]}): DB generated]'
            if c['notnull']:label+='   NOT NULL'
            lines.append(label)
        lines+=['',('کلیدهای خارجی' if self.lang=='fa' else 'FOREIGN KEYS')]
        if not fks:lines.append('(وجود ندارد)' if self.lang=='fa' else '(none)')
        for fk in fks:lines.append(f"{fk['from']}  →  {fk['table']}.{fk['to']}")
        lines+=['',self.text('guide_hint'),'',self.text('table_note')]
        self.propetext.setPlainText('\n'.join(lines))
    def drop_module_ui(self,kind,name):
        """Delete an actual view or an educational stored routine after approval."""
        if not self.require_db():return
        noun={'view':'VIEW','procedure':'PROCEDURE','function':'FUNCTION'}.get(kind)
        if noun is None:return
        answer=QMessageBox.question(self,'Delete SQL object',
            f'DROP {noun} {name}?\n\nThis definition will be removed. '
            'Views referenced by other objects may become invalid.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:return
        try:
            result=drop_module(self.db,f'DROP {noun} {name}')
            self.refresh_all()
            self.statusBar().showMessage(result,9000)
        except Exception as exc:error(self,self.lang,exc)

    def explorer_menu(self,pos):
        if not self.db:return
        clicked=self.explorer.itemAt(pos)
        if clicked:self.explorer.setCurrentItem(clicked)
        menu=QMenu(self)
        menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.lang=='fa' else Qt.LayoutDirection.LeftToRight)
        table=self.selected_table()
        module=self.selected_module()
        if module:
            kind,name=module
            menu.addAction(ui('Open SQL query for ',self.lang)+kind,lambda:self.open_module(kind,name))
            menu.addAction(ui('Delete {type}…',self.lang).format(type=ui({'view':'View','procedure':'Stored Procedure','function':'Function'}[kind],self.lang)),lambda:self.drop_module_ui(kind,name))
            menu.addSeparator()
        if table:
            menu.addAction(self.text('open_data'),lambda:self.show_data(table))
            menu.addAction(ui('Design Table…',self.lang),lambda:self.design_table(table))
            menu.addAction(self.text('add_record'),lambda:self.insert_row(table))
            menu.addAction(ui('Edit Rows (Grid)',self.lang),lambda:self.edit_rows(table))
            menu.addAction(ui('Edit Selected Record…',self.lang),lambda:self.edit_selected_record(table))
            menu.addAction(ui('Delete Selected Record…',self.lang),lambda:self.delete_selected_record(table))
            menu.addSeparator()
            menu.addAction(ui('Drop Column…',self.lang),lambda:self.drop_column_ui(table))
            menu.addAction(ui('Drop Table…',self.lang),lambda:self.drop_table_ui(table))
            menu.addSeparator()
        menu.addAction(self.text('new_table'),self.new_table)
        menu.addAction(self.text('new_relation'),self.new_relation)
        menu.addAction(self.text('generate_scripts'),self.generate_scripts)
        menu.addSeparator()
        menu.addAction(self.text('refresh'),self.refresh_all)
        menu.exec(self.explorer.viewport().mapToGlobal(pos))
    def tree_double(self,item,column):
        module=self.selected_module()
        if module:
            self.open_module(*module)
            return
        table=self.selected_table()
        if table:self.show_data(table)
    def show_data(self,table):
        if not self.db or table not in self.db.tables():
            self.refresh_all()
            QMessageBox.warning(self,ui('Table not found',self.lang),
                f'Table {table} does not exist in the active database. Explorer has been refreshed.')
            return
        if table not in self.data_tabs:
            page=QWidget()
            layout=QVBoxLayout(page)
            top=QHBoxLayout()
            label=QLabel(table)
            label.setProperty('role','eyebrow')
            top.addWidget(label)
            top.addStretch()
            add=QPushButton('＋  '+self.text('add_record'))
            add.setObjectName('addRowButton')
            add.setProperty('role','primary')
            add.clicked.connect(lambda: self.insert_row(table))
            # The regular Add button remains an optional detailed form.
            # Inline entry is always available on the last (NEW) grid row.
            save_inline=QPushButton(ui('Save New Row',self.lang))
            save_inline.setObjectName('saveInlineRowButton')
            save_inline.clicked.connect(lambda:self.save_inline_row(table))
            refresh=QPushButton(self.text('refresh'))
            refresh.setObjectName('refreshDataButton')
            refresh.clicked.connect(lambda:self.update_data_tab(table))
            top.addWidget(add)
            top.addWidget(save_inline)
            grid_edit=QPushButton('▦  '+ui('Edit Rows',self.lang))
            grid_edit.setObjectName('editRowsButton')
            grid_edit.clicked.connect(lambda:self.edit_rows(table))
            top.addWidget(grid_edit)
            edit_record=QPushButton('✎  '+ui('Edit Record',self.lang))
            edit_record.setObjectName('editSelectedRecordButton')
            edit_record.clicked.connect(lambda:self.edit_selected_record(table))
            top.addWidget(edit_record)
            delete_record_btn=QPushButton('×  '+ui('Delete Record',self.lang))
            delete_record_btn.setObjectName('deleteSelectedRecordButton')
            delete_record_btn.clicked.connect(lambda:self.delete_selected_record(table))
            top.addWidget(delete_record_btn)
            top.addWidget(refresh)
            closeview=QPushButton('×  '+ui('Close View',self.lang))
            closeview.setObjectName('closeDataViewButton')
            closeview.setToolTip(ui('Closes this view only; table and records stay in the database.',self.lang))
            closeview.clicked.connect(lambda:self.close_data_page(table))
            top.addWidget(closeview)
            layout.addLayout(top)
            grid=QTableWidget()
            grid.setObjectName('dataGrid')
            grid.setAlternatingRowColors(True)
            grid.setTabKeyNavigation(True)
            grid.setToolTip(ui('Tab = next field; enter values in the last NEW row, then Save New Row.',self.lang))
            grid.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                                 QAbstractItemView.EditTrigger.SelectedClicked |
                                 QAbstractItemView.EditTrigger.EditKeyPressed)
            grid.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
            grid.verticalHeader().setVisible(False)
            grid.itemChanged.connect(lambda item,t=table:self._edit_data_cell(t,item))
            grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            grid.customContextMenuRequested.connect(lambda pos,t=table:self.data_grid_menu(t,pos))
            grid._saveShortcut=QShortcut(QKeySequence('Ctrl+Return'),grid)
            grid._saveShortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            grid._saveShortcut.activated.connect(
                lambda t=table,g=grid:(g.setFocus(), QTimer.singleShot(0,lambda:self.save_inline_row(t))))
            layout.addWidget(grid)
            self.data_tabs[table]=page
            self.tabs.addTab(page,self.text('data_title',table=table))
            self.install_tab_close_button(page)
        self.update_data_tab(table)
        self.tabs.setCurrentWidget(self.data_tabs[table])
    def update_data_tab(self,table):
        if not self.db or table not in self.data_tabs:return
        page=self.data_tabs[table]
        grid=page.findChild(QTableWidget,'dataGrid')
        try:
            names,rows,locators=editable_records(self.db,table)
        except (LabError,Exception) as exc:
            self.close_data_page(table)
            self.statusBar().showMessage(f'{table}: {exc}. The stale data tab has been closed.',12000)
            return
        page._row_locators=locators
        page._loading=True
        grid.setUpdatesEnabled(False)
        grid.clear()
        # Keep one always-present editable NEW row, as in the SSMS data grid.
        grid.setRowCount(len(rows)+1)
        grid.setColumnCount(len(names))
        grid.setHorizontalHeaderLabels(names)
        identity_names={name for name in names if is_identity(self.db,table,name)}
        for r,values in enumerate(rows):
            for c,value in enumerate(values):
                cell=QTableWidgetItem('NULL' if value is None else str(value))
                if value is None:cell.setForeground(QColor(palette(self.theme)['muted']))
                if names[c] not in identity_names and not isinstance(value,(bytes,bytearray,memoryview)):
                    cell.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable)
                else:
                    cell.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
                grid.setItem(r,c,cell)
        new_row=len(rows)
        for col,name in enumerate(names):
            if name in identity_names:
                cell=QTableWidgetItem(ui('(DB GENERATED)',self.lang))
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
            else:
                cell=QTableWidgetItem('')
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable)
                cell.setToolTip(ui('Enter a value, then Tab to the next column.',self.lang))
            grid.setItem(new_row,col,cell)
        grid.verticalHeader().setVisible(True)
        grid.setVerticalHeaderItem(new_row,QTableWidgetItem(ui('NEW  *',self.lang)))
        grid.resizeColumnsToContents()
        grid.setUpdatesEnabled(True)
        page._loading=False

    def save_inline_row(self,table):
        """Commit the NEW grid row only after all model/database checks succeed."""
        if not self.require_existing_table(table):return
        page=self.data_tabs.get(table)
        if page is None:return
        grid=page.findChild(QTableWidget,'dataGrid')
        new_row=len(getattr(page,'_row_locators',[]))
        if new_row>=grid.rowCount():return
        values={}
        try:
            for col,spec in enumerate(self.db.columns(table)):
                name=spec['name']
                if is_identity(self.db,table,name):continue
                cell=grid.item(new_row,col)
                raw=cell.text() if cell else ''
                if not raw.strip():
                    # Absent nullable inputs become NULL. Required blanks are
                    # detected by insert_data, with a column-specific message.
                    continue
                values[name]=cell_value(self.db,table,name,raw)
            from model_ext import insert_data
            insert_data(self.db,table,values)
        except Exception as exc:
            error(self,self.lang,exc)
            grid.setFocus()
            return
        self.refresh_all()
        page=self.data_tabs.get(table)
        if page:
            grid=page.findChild(QTableWidget,'dataGrid')
            last=grid.rowCount()-1
            first=next((j for j,c in enumerate(self.db.columns(table)) if not is_identity(self.db,table,c['name'])), -1)
            if last>=0 and first>=0:
                grid.setCurrentCell(last,first)
                grid.setFocus()
        self.statusBar().showMessage(ui('New record saved. Enter the next one in the NEW row.',self.lang),8000)

    def _edit_data_cell(self,table,item):
        page=self.data_tabs.get(table)
        if not page or getattr(page,'_loading',False) or not self.db:return
        row,col=item.row(),item.column()
        locators=getattr(page,'_row_locators',[])
        if row<0 or row>=len(locators):return
        columns=self.db.columns(table)
        if col<0 or col>=len(columns):return
        name=columns[col]['name'];old=locators[row]['original'][name]
        if is_identity(self.db,table,name):
            self._restore_data_cell(page,item,old)
            return
        try:
            value=cell_value(self.db,table,name,item.text())
            if value==old:return
            update_record(self.db,table,locators[row],{name:value})
        except Exception as exc:
            self._restore_data_cell(page,item,old)
            error(self,self.lang,exc)
            return
        self.statusBar().showMessage('رکورد ذخیره شد.' if self.lang=='fa' else 'Record updated.',7000)
        QTimer.singleShot(0,lambda:self.refresh_all())

    def _restore_data_cell(self,page,item,old):
        page._loading=True
        try:item.setText('NULL' if old is None else str(old))
        finally:page._loading=False

    def _record_target(self,table=None):
        if not self.require_db():return None
        table=table or self.selected_table()
        if not table:
            QMessageBox.information(self,ui('Select a table',self.lang),'Open a table from Object Explorer first.')
            return None
        if not self.require_existing_table(table):return None
        if table not in self.data_tabs:
            self.show_data(table)
        page=self.data_tabs.get(table)
        if page is None:return None
        grid=page.findChild(QTableWidget,'dataGrid')
        locators=getattr(page,'_row_locators',[])
        row=grid.currentRow()
        if row<0 or row>=len(locators):
            QMessageBox.information(self,ui('Select a record',self.lang),
                'Select a row in the table view to edit or delete it.')
            return None
        return table,locators[row]

    def edit_selected_record(self,table=None):
        selection=self._record_target(table)
        if not selection:return
        name,_=selection
        page=self.data_tabs[name]
        grid=page.findChild(QTableWidget,'dataGrid')
        row,col=grid.currentRow(),grid.currentColumn()
        cols=self.db.columns(name)
        if col<0 or is_identity(self.db,name,cols[col]['name']):
            col=next((n for n,c in enumerate(cols) if not is_identity(self.db,name,c['name'])), -1)
        if col<0:return
        cell=grid.item(row,col)
        if cell and (cell.flags() & Qt.ItemFlag.ItemIsEditable):
            self.tabs.setCurrentWidget(page)
            grid.setCurrentCell(row,col)
            grid.editItem(cell)

    def delete_selected_record(self,table=None):
        selection=self._record_target(table)
        if not selection:return
        name,locator=selection
        if QMessageBox.question(self,ui('Delete record',self.lang),
            f'Permanently delete the selected row from {name}? This cannot be undone.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:delete_record(self.db,name,locator)
        except Exception as exc:error(self,self.lang,exc);return
        self.refresh_all()
        self.statusBar().showMessage(ui('One record deleted from ',self.lang)+name,8000)

    def data_grid_menu(self,table,pos):
        page=self.data_tabs.get(table)
        if not page:return
        grid=page.findChild(QTableWidget,'dataGrid')
        row=grid.rowAt(pos.y())
        if row>=0:grid.selectRow(row)
        menu=QMenu(self)
        menu.addAction(ui('Insert Record…',self.lang),lambda:self.insert_row(table))
        menu.addAction(ui('Edit Selected Record…',self.lang),lambda:self.edit_selected_record(table))
        menu.addAction(ui('Delete Selected Record…',self.lang),lambda:self.delete_selected_record(table))
        menu.exec(grid.viewport().mapToGlobal(pos))

    def open_sql_file(self):
        """Review SQL file in Query Editor and require consent before execution."""
        path,_=QFileDialog.getOpenFileName(self,ui('Open SQL Script',self.lang),str(APP_FOLDER),
                                         'SQL scripts (*.sql);;Text files (*.txt);;All files (*)')
        if not path:return
        try:
            script=read_sql_script(path)
        except (OSError,UnicodeError,LabError) as exc:
            error(self,self.lang,exc);return
        self.editor.setPlainText(script)
        self.activate_main_tab(self.query_page)
        self.statusBar().showMessage(('اسکریپت بارگذاری شد: ' if self.lang=='fa' else 'Loaded SQL script: ')+Path(path).name,12000)
        answer=QMessageBox.question(self,ui('Execute imported SQL script?',self.lang),
            'Script loaded into the Query Editor for review.\n\n'
            'Execution may CREATE, ALTER or DROP databases, tables, rows and relationships. '
            'Only the documented T-SQL subset is supported; the simulator uses SQLite. '
            'Scripts can partially run before an unsupported command fails.\n\n'
            'Review the script and make a backup of existing databases. Execute now?',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:
            self.execute_sql()

    def insert_selected(self):
        if not self.require_db():return
        name=self.selected_table()
        if not name:
            QMessageBox.information(self,self.text('add_record'),self.text('table_note'))
            return
        self.insert_row(name)
    def require_existing_table(self,table):
        """Guard stale UI actions after another connection drops a table."""
        if not self.require_db():
            return False
        if table not in self.db.tables():
            self.refresh_all()
            QMessageBox.warning(self,self.text('err'),
                f'Table {table} no longer exists in the active database. The view was refreshed.')
            return False
        return True

    def edit_rows(self,table):
        if not self.require_existing_table(table):return
        try:
            GridRowEditor(self.db,table,self.lang,self.refresh_all,self).exec()
        except Exception as exc:
            self.refresh_all()
            error(self,self.lang,exc)

    def insert_row(self,table):
        if not self.require_existing_table(table):return
        try:
            DataEntryDialog(self.db,table,self.lang,self.refresh_all,self).exec()
        except Exception as exc:
            self.refresh_all()
            error(self,self.lang,exc)
    def execute_sql(self):
        statement=self.editor.textCursor().selectedText().replace('\u2029','\n') or self.editor.toPlainText()
        if not statement.strip():return
        original=self.db
        try:
            result=run_script(self.db,statement,APP_FOLDER)
        except Exception as exc:
            self.bottomdock.show()
            self.output_tabs.setCurrentWidget(self.messages)
            self.messages.setPlainText(str(exc))
            error(self,self.lang,exc)
            # CREATE/USE before the failing statement may have already committed.
            if self.db:self.refresh_all()
            return
        if result.database is not original:
            # The runner preserves the old connection until a successful USE.
            if original is not None:original.close()
            self.db=result.database
            self.editor.set_database(self.db)
            if self.welcome is not None and self.tabs.indexOf(self.welcome)>=0:
                self.tabs.removeTab(self.tabs.indexOf(self.welcome))
            for table,page in list(self.data_tabs.items()):
                index=self.tabs.indexOf(page)
                if index>=0:self.tabs.removeTab(index)
                page.deleteLater()
            self.data_tabs.clear()
            self.setWindowTitle(self.text('app_name')+'  •  '+self.db.path.stem+'  |  v'+APP_VERSION)
            self.build_commands()
        self.results.clear()
        self.results.setColumnCount(len(result.columns))
        self.results.setHorizontalHeaderLabels(result.columns)
        self.results.setRowCount(len(result.rows))
        for r,rec in enumerate(result.rows):
            for c,cell in enumerate(rec):
                self.results.setItem(r,c,QTableWidgetItem('NULL' if cell is None else str(cell)))
        self.results.resizeColumnsToContents()
        self.messages.setPlainText(result.messages)
        self.bottomdock.show()
        self.output_tabs.setCurrentWidget(self.results if result.columns else self.messages)
        if self.db:self.refresh_all()

    def generate_scripts(self):
        if not self.require_db():return
        if not self.db.tables():
            QMessageBox.information(self,self.text('generate_scripts'),'Create at least one table first.')
            return
        ScriptExportWizard(self.db,self.lang,self,on_open=self.open_export_in_editor).exec()
    def open_export_in_editor(self,script: str):
        """Generate Scripts -> Open in new query editor (without executing)."""
        self.editor.setPlainText(script)
        self.activate_main_tab(self.query_page)
        self.editor.setFocus()
        self.statusBar().showMessage(ui('Script opened in Query Editor. Review it before execution.',self.lang),9000)

    def export_diagram(self):
        if not self.require_db():return
        path,_=QFileDialog.getSaveFileName(self,self.text('export_erd'),'Database_Diagram.png','PNG Image (*.png)')
        if path:
            try:
                if not path.lower().endswith('.png'):path+='.png'
                if not self.diagram.export_png(path):raise RuntimeError('Could not save PNG file.')
                info(self,self.lang,path)
            except Exception as exc:error(self,self.lang,exc)
    def bug_email_draft(self):
        if self.lang=='fa':
            subject=f'گزارش خطای شبیه‌ساز SQL Server | نسخه {APP_VERSION}'
            body=('با سلام،\n\nشرح خطا:\n\nمراحل بازتولید خطا:\n۱. \n۲. \n\n'
                  'نتیجه مورد انتظار:\n\nنتیجه مشاهده‌شده:\n\n'
                  f'نسخه نرم‌افزار: {APP_VERSION}\nسیستم‌عامل: {platform.platform()} / {platform.machine()}\n\n')
        else:
            subject=f'Bug report | SQL Server Simulator v{APP_VERSION} | Ali Sayyadi'
            body=('Hello,\n\nBug description:\n\nSteps to reproduce:\n1. \n2. \n\n'
                  'Expected result:\n\nActual result:\n\n'
                  f'Application version: {APP_VERSION}\nOS and architecture: {platform.platform()} / {platform.machine()}\n\n')
        return subject,body

    def report_bug(self):
        subject,body=self.bug_email_draft()
        webbrowser.open('https://mail.google.com/mail/?'+urlencode({'view':'cm','fs':'1','to':EMAIL,'su':subject,'body':body}))

    def report_mailto(self):
        subject,body=self.bug_email_draft()
        webbrowser.open('mailto:'+EMAIL+'?'+urlencode({'subject':subject,'body':body}))
    def about(self):
        QMessageBox.about(self,self.text('about'),self.text('about_text'))
    def closeEvent(self,event):
        self.prefs.setValue('window/geometry',self.saveGeometry())
        self.prefs.setValue('window/docks',self.saveState())
        self.prefs.sync()
        if self.db:self.db.close()
        super().closeEvent(event)

def run():
    app=QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setOrganizationName('Ali Sayyadi')
    app.setApplicationName('SQL Server Simulator')
    app.setApplicationVersion(APP_VERSION)
    window=MainWindow()
    window.show()
    QTimer.singleShot(150,window.language_prompt_first_run)
    return app.exec()

if __name__=='__main__':sys.exit(run())
