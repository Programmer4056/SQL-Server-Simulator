"""SQL Server Simulator 0.6.1 desktop UI: official Qt / PySide6 bindings.

Educational SQLite engine with real key enforcement. This is NOT Microsoft SQL Server.
Designed and developed by Ali Sayyadi.
"""
from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urlencode
import webbrowser
from PySide6.QtCore import Qt,QSettings,QTimer,QSize
from PySide6.QtGui import QAction, QFont,QFontDatabase,QIcon,QKeySequence,QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QTabWidget,QDockWidget,QTreeWidget,
    QTreeWidgetItem,QTextEdit,QToolBar,QComboBox,QLabel,QWidget,QVBoxLayout,QHBoxLayout,
    QPushButton,QMessageBox,QFileDialog,QSplitter,QTableWidget,QTableWidgetItem,
    QHeaderView,QAbstractItemView,QStyle,QFrame,QMenu,QTabBar)
from core import LabDatabase, LabError
from model_ext import get_rows,is_identity
from widgets import SQLEditor,Diagram,WelcomePanel
from dialogs import NewDatabaseWizard,TableDesigner,RelationshipWizard,DataEntryDialog,GridRowEditor,ScriptExportWizard,LanguageChoice,error,info
from i18n import tr
from style import make_qss,palette

APP_VERSION='0.6.1'
EMAIL='Ali.sayyadi200@gmail.com'
APP_FOLDER=Path.home()/'Documents'/'SQL Server Simulator Projects'

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
        self.setMinimumSize(1024,700)
        self.resize(1440,900)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setWindowTitle(tr('app_name',self.lang)+'  |  v'+APP_VERSION)
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
        icon_file=root/'assets'/'app.ico'
        if icon_file.exists():self.setWindowIcon(QIcon(str(icon_file)))
        QApplication.instance().setStyleSheet(make_qss(self.theme))
        self.set_fonts()
        self.init_shell()
        self.build_commands()
        self.refresh_explorer()
        if self.prefs.contains('window/geometry'):
            self.restoreGeometry(self.prefs.value('window/geometry'))
    def text(self,key,**kwargs):return tr(key,self.lang,**kwargs)
    def set_fonts(self):
        app=QApplication.instance()
        fonts=set(QFontDatabase.families())
        if self.lang=='fa':
            face=next((f for f in ('Vazirmatn','Vazir','IRANSans','Tahoma','Segoe UI') if f in fonts),'Tahoma')
            app.setFont(QFont(face,10))
        else:
            app.setFont(QFont('Segoe UI',10))
    def icon(self,kind):
        specs={'new':QStyle.StandardPixmap.SP_FileIcon,
               'open':QStyle.StandardPixmap.SP_DialogOpenButton,
               'table':QStyle.StandardPixmap.SP_FileDialogDetailedView,
               'relation':QStyle.StandardPixmap.SP_DirLinkIcon,
               'run':QStyle.StandardPixmap.SP_MediaPlay,
               'refresh':QStyle.StandardPixmap.SP_BrowserReload,
               'save':QStyle.StandardPixmap.SP_DialogSaveButton,
               'help':QStyle.StandardPixmap.SP_MessageBoxInformation}
        return self.style().standardIcon(specs[kind])
    def init_shell(self):
        self.tabs=QTabWidget()
        self.tabs.setMovable(False)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_data_tab)
        self.setCentralWidget(self.tabs)
        self.welcome=WelcomePanel(self.lang,self.new_database,self.open_dialog,self.report_bug)
        self.tabs.addTab(self.welcome,'Welcome')
        self.query_page=QWidget()
        qlayout=QVBoxLayout(self.query_page)
        qlayout.setContentsMargins(0,0,0,0)
        query_stack=QSplitter(Qt.Orientation.Vertical)
        self.editor=SQLEditor(self.theme)
        self.editor.setPlainText('-- '+self.text('tip')+'\n\n-- '+self.text('try_sql')+'\n')
        query_stack.addWidget(self.editor)
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
        query_stack.addWidget(self.output_tabs)
        query_stack.setStretchFactor(0,7)
        query_stack.setStretchFactor(1,3)
        qlayout.addWidget(query_stack)
        self.tabs.addTab(self.query_page,self.text('sql_editor'))
        self.diagram_page=QWidget()
        diagram_layout=QVBoxLayout(self.diagram_page)
        diagram_layout.setContentsMargins(7,7,7,7)
        actions=QHBoxLayout()
        make_table=QPushButton('＋  New Table')
        make_table.clicked.connect(self.new_table)
        actions.addWidget(make_table)
        linkbtn=QPushButton('🔗  '+self.text('new_relation'))
        linkbtn.setObjectName('diagramConnectButton')
        linkbtn.setProperty('role','primary')
        linkbtn.clicked.connect(self.new_relation)
        actions.addWidget(linkbtn)
        self.link_mode_button=QPushButton('↗  Connect by Drag')
        self.link_mode_button.setCheckable(True)
        self.link_mode_button.setToolTip('Enable, then drag with the left mouse button from the parent table to the child table. Drag onto the same table for a hierarchy.')
        actions.addWidget(self.link_mode_button)
        self.restore_diagram_button=QPushButton('↺  Reopen Tables')
        self.restore_diagram_button.setObjectName('diagramRestoreButton')
        self.restore_diagram_button.clicked.connect(self.reopen_diagram_tables)
        actions.addWidget(self.restore_diagram_button)
        actions.addStretch(1)
        diagram_layout.addLayout(actions)
        self.diagram_hint=QLabel('Tip: select Draw Link, then click two fields to create a relationship.')
        self.diagram_hint.setProperty('role','muted')
        self.diagram_hint.setWordWrap(True)
        diagram_layout.addWidget(self.diagram_hint)
        self.diagram=Diagram(self.theme)
        self.diagram.set_actions(self.design_table,self.new_table,self.new_relation_between,
                                 self.new_relation_columns,self.delete_diagram_relationship,
                                 self.diagram_relationship_selected)
        self.link_mode_button.toggled.connect(self.diagram.start_connect)
        self.draw_link_button=QPushButton('✎  Draw Link (2 clicks)')
        self.draw_link_button.setObjectName('diagramDrawLinkButton')
        self.draw_link_button.setCheckable(True)
        self.draw_link_button.setToolTip('Click the parent PRIMARY KEY field, then click the matching child FOREIGN KEY field. Escape cancels.')
        self.draw_link_button.toggled.connect(self.toggle_manual_draw)
        self.diagram.on_manual_cancel=lambda:self.draw_link_button.setChecked(False)
        self.diagram.on_manual_activate=lambda:self.draw_link_button.setChecked(True)
        self.diagram.on_link_progress=self.set_diagram_hint
        actions.insertWidget(3,self.draw_link_button)
        self.delete_link_button=QPushButton('×  Delete Link')
        self.delete_link_button.setObjectName('diagramDeleteLinkButton')
        self.delete_link_button.setEnabled(False)
        self.delete_link_button.setToolTip('Select an existing relationship line first. Deletion changes the actual database FK, not just the drawing.')
        self.delete_link_button.clicked.connect(self.diagram.delete_selected_edge)
        actions.insertWidget(4,self.delete_link_button)
        fit_button=QPushButton('Fit Diagram')
        fit_button.setToolTip('Zoom out to show every table at once. Use 100% for easier field selection.')
        fit_button.clicked.connect(self.diagram.fit_diagram)
        actions.addWidget(fit_button)
        zoom_button=QPushButton('100%')
        zoom_button.setToolTip('Show readable field sizes for direct column linking.')
        zoom_button.clicked.connect(self.diagram.zoom_actual)
        actions.addWidget(zoom_button)
        self.diagram.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        diagram_layout.addWidget(self.diagram,1)
        self.tabs.addTab(self.diagram_page,self.text('diagram'))
        # Query, Diagram and Welcome are permanent. Only opened data views close.
        for ix in range(self.tabs.count()):
            self.tabs.tabBar().setTabButton(ix,QTabBar.ButtonPosition.RightSide,None)
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
        self.leftdock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,self.leftdock)
        self.leftdock.setMinimumWidth(260)
        self.propetext=QTextEdit()
        self.propetext.setReadOnly(True)
        self.propetext.setPlainText(self.text('guide_empty'))
        self.rightdock=QDockWidget(self.text('properties'),self)
        self.rightdock.setObjectName('propertyDock')
        self.rightdock.setWidget(self.propetext)
        self.rightdock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.rightdock)
        self.rightdock.setMinimumWidth(240)
        self.bottom_line=QLabel(self.text('v_notice'))
        self.statusBar().addPermanentWidget(self.bottom_line)
        self.statusBar().showMessage(self.text('ready'))
        self.tabs.setCurrentWidget(self.welcome)
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
        filemenu.addSeparator()
        filemenu.addAction(self.act_exit)
        dbmenu=self.menuBar().addMenu(self.text('database'))
        self.act_table=self.action(self.text('new_table'),self.new_table,'table','Ctrl+T')
        self.act_relation=self.action(self.text('new_relation'),self.new_relation,'relation','Ctrl+R')
        self.act_design_table=self.action('Design Selected Table…',self.design_selected_table,'table','Ctrl+D')
        self.act_demo=self.action(self.text('demo'),self.create_demo)
        self.act_refresh=self.action(self.text('refresh'),self.refresh_all,'refresh','Ctrl+F5')
        self.act_integrity=self.action('Check Referential Integrity…',self.check_integrity)
        self.act_add=self.action(self.text('add_record'),self.insert_selected)
        for a in [self.act_table,self.act_design_table,self.act_relation,self.act_demo,self.act_add,self.act_integrity,self.act_refresh]:dbmenu.addAction(a)
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
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(18,18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea,self.toolbar)
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
        for a in [self.act_table,self.act_design_table,self.act_relation,self.act_demo,self.act_add,self.act_integrity,self.act_refresh,self.act_export,self.act_script,self.act_run]:
            a.setEnabled(self.db is not None)
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
            QApplication.instance().setStyleSheet(make_qss(new))
            self.editor.set_theme(new)
            self.diagram.set_theme(new)
    def retranslate(self):
        self.setWindowTitle(self.text('app_name')+'  |  v'+APP_VERSION)
        self.build_commands()
        self.output_tabs.setTabText(0,self.text('results'))
        self.output_tabs.setTabText(1,self.text('messages'))
        self.tabs.setTabText(self.tabs.indexOf(self.query_page),self.text('sql_editor'))
        self.tabs.setTabText(self.tabs.indexOf(self.diagram_page),self.text('diagram'))
        connect=self.diagram_page.findChild(QPushButton,'diagramConnectButton')
        if connect:connect.setText('🔗  '+self.text('new_relation'))
        self.leftdock.setWindowTitle(self.text('object_explorer'))
        self.rightdock.setWindowTitle(self.text('properties'))
        self.bottom_line.setText(self.text('v_notice'))
        if self.welcome and self.tabs.indexOf(self.welcome)>=0:
            ix=self.tabs.indexOf(self.welcome)
            self.tabs.removeTab(ix)
            self.welcome.deleteLater()
            self.welcome=WelcomePanel(self.lang,self.new_database,self.open_dialog,self.report_bug)
            self.tabs.insertTab(0,self.welcome,'Welcome' if self.lang=='en' else 'خوش‌آمدید')
        for table,tab in self.data_tabs.items():
            idx=self.tabs.indexOf(tab)
            if idx>=0:self.tabs.setTabText(idx,self.text('data_title',table=table))
            for button in tab.findChildren(QPushButton):
                if button.objectName()=='addRowButton':button.setText('＋  '+self.text('add_record'))
                if button.objectName()=='refreshDataButton':button.setText(self.text('refresh'))
        self.refresh_explorer()
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
        self.tabs.setCurrentWidget(self.query_page)
        self.statusBar().showMessage(str(path))
    def close_database(self):
        if self.db:self.db.close()
        self.db=None
        for table,tab in list(self.data_tabs.items()):
            index=self.tabs.indexOf(tab)
            if index>=0:self.tabs.removeTab(index)
            tab.deleteLater()
        self.data_tabs.clear()
        self.diagram.set_db(None)
        if self.welcome is not None and self.tabs.indexOf(self.welcome)<0:
            self.welcome=WelcomePanel(self.lang,self.new_database,self.open_dialog,self.report_bug)
            self.tabs.insertTab(0,self.welcome,'Welcome' if self.lang=='en' else 'خوش‌آمدید')
        self.tabs.setCurrentWidget(self.welcome)
        self.refresh_explorer()
        self.build_commands()
        self.setWindowTitle(self.text('app_name')+'  |  v'+APP_VERSION)
    def new_table(self):
        if not self.require_db():return
        dlg=TableDesigner(self.db,self.lang,self.refresh_all,self)
        dlg.exec()
    def check_integrity(self):
        if not self.require_db():return
        try:issues=self.db.check_integrity()
        except Exception as exc:error(self,self.lang,exc);return
        if not issues:
            QMessageBox.information(self,'Referential Integrity','All foreign-key constraints are valid. No orphan references were found.')
        else:
            details='\n'.join(f"{r['table']} rowid={r['rowid']} → {r['parent']}" for r in issues[:50])
            QMessageBox.warning(self,'Referential Integrity',f'{len(issues)} invalid reference(s) found:\n'+details)
    def design_selected_table(self):
        table=self.selected_table()
        if table:self.design_table(table)
        else:QMessageBox.information(self,'Design Table','Select a table in Object Explorer or double-click one in the diagram.')
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
            self.statusBar().showMessage('Draw Link: click the parent PK field and then the child FK field. Press Esc to cancel.',12000)

    def diagram_relationship_selected(self,link):
        self.delete_link_button.setEnabled(bool(link))
        if link:
            text=(f"{link['kind']}  |  {link['parent']} → {link['child']}  |  "
                  f"{link.get('fk','')}")
            self.statusBar().showMessage('Selected relationship: '+text)
            self.propetext.setPlainText('RELATIONSHIP SELECTED\n'+'─'*35+'\n'
                +text+'\n\nRight-click the line or press Delete to remove this FK. '
                'Columns, records and tables will be kept.\n\n'
                +'WARNING: removing the FK removes its referential-integrity enforcement.')

    def delete_diagram_relationship(self,link):
        if not self.require_db():return
        semantic=bool(link.get('semantic'))
        if semantic:
            detail=(f"Delete BOTH foreign key constraints of the N:M relationship via {link.get('bridge')}?\n\n"
                    'The junction table, its columns, and all existing records will be kept.')
        else:
            detail=(f"Delete the relationship {link.get('parent')} → {link.get('child')} "
                    f"({link.get('fk')})?\n\n"
                    'The foreign key rule will be removed, but all tables, columns and rows will be preserved.')
        detail+='\n\nFuture orphan references will no longer be blocked by the removed FK.'
        response=QMessageBox.question(self,'Delete Relationship',detail,
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
        self.tabs.setCurrentWidget(self.diagram_page)
        self.statusBar().showMessage(result,12000)
        QMessageBox.information(self,'Relationship removed',result)

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
            QMessageBox.warning(self,'Field Mapping',
                'Start the link from the PRIMARY KEY field of the parent table, '                'or drag the child foreign-key field onto a parent PRIMARY KEY.')
            return
        dlg=RelationshipWizard(self.db,self.lang,self.refresh_all,self,
                               source_table=source_table,target_table=target_table,
                               source_field=source_field,target_field=target_field)
        created=bool(dlg.exec())
        self.link_mode_button.setChecked(False)
        if hasattr(self,'draw_link_button'):self.draw_link_button.setChecked(False)
        if created:
            self.tabs.setCurrentWidget(self.diagram_page)

    def reopen_diagram_tables(self):
        if not self.require_db():return
        hidden=sorted(self.diagram.hidden_tables & set(self.db.tables()))
        if not hidden:
            QMessageBox.information(self,'Reopen Tables','No tables are hidden in the diagram.')
            return
        menu=QMenu(self)
        for name in hidden:
            menu.addAction(name,lambda checked=False,n=name:self.diagram.show_table(n))
        menu.addSeparator()
        menu.addAction('Show All Tables',self.diagram.show_all_tables)
        menu.exec(self.restore_diagram_button.mapToGlobal(
            self.restore_diagram_button.rect().bottomLeft()))

    def close_data_page(self,table):
        page=self.data_tabs.get(table)
        if page is not None:
            index=self.tabs.indexOf(page)
            if index>=0:self.close_data_tab(index)

    def close_data_tab(self,index):
        page=self.tabs.widget(index)
        for table,tab in list(self.data_tabs.items()):
            if tab is page:
                self.data_tabs.pop(table,None)
                self.tabs.removeTab(index)
                tab.deleteLater()
                return
        # The SQL Editor and Database Diagram cannot accidentally be closed.

    def new_relation(self):
        self.new_relation_between(None,None)
    def new_relation_between(self,source=None,target=None):
        if hasattr(self,'link_mode_button'):self.link_mode_button.setChecked(False)
        if not self.require_db():return
        if not self.db.tables():
            QMessageBox.information(self,self.text('new_relation'),'Create at least one table first.')
            return
        if len(self.db.tables())<2 and not (source and target and source==target):
            QMessageBox.information(self,self.text('new_relation'),
                'Create two tables to link them, or right-click the existing table for a self-referencing relationship.')
            return
        dlg=RelationshipWizard(self.db,self.lang,self.refresh_all,self,
                               source_table=source,target_table=target)
        if dlg.exec():
            self.tabs.setCurrentWidget(self.diagram_page)
            if hasattr(self,'link_mode_button'):self.link_mode_button.setChecked(False)
    def create_demo(self):
        if not self.require_db():return
        if QMessageBox.question(self,self.text('demo'),self.text('confirm_demo')) != QMessageBox.StandardButton.Yes:return
        try:self.db.demo()
        except Exception as exc:error(self,self.lang,exc);return
        self.refresh_all()
        self.tabs.setCurrentWidget(self.diagram_page)
        info(self,self.lang,self.text('sample_ok'))
    def refresh_all(self):
        if not self.db:return
        self.refresh_explorer()
        self.diagram.set_db(self.db)
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
        self.statusBar().showMessage(f'{self.db.path.name}  |  {len(self.db.tables())} tables')
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
    def tree_current(self,current,previous):
        table=self.selected_table()
        if not self.db or not table:return
        cols=self.db.columns(table)
        fks=self.db.foreign_keys(table)
        lines=[f'TABLE  {table}','─'*33,'', 'COLUMNS']
        for c in cols:
            label=('PK  ' if c['pk'] else '    ')+c['name']+'  :  '+self.db.logical_type(table,c['name'])
            if is_identity(self.db,table,c['name']):
                identity=self.db.identity_settings(table)
                if identity:label+=f'   [IDENTITY({identity["seed"]},{identity["increment"]}): DB generated]'
            if c['notnull']:label+='   NOT NULL'
            lines.append(label)
        lines+=['','FOREIGN KEYS']
        if not fks:lines.append('(none)')
        for fk in fks:lines.append(f"{fk['from']}  →  {fk['table']}.{fk['to']}")
        lines+=['',self.text('guide_hint'),'',self.text('table_note')]
        self.propetext.setPlainText('\n'.join(lines))
    def explorer_menu(self,pos):
        if not self.db:return
        clicked=self.explorer.itemAt(pos)
        if clicked:self.explorer.setCurrentItem(clicked)
        menu=QMenu(self)
        table=self.selected_table()
        if table:
            menu.addAction(self.text('open_data'),lambda:self.show_data(table))
            menu.addAction('Design Table…',lambda:self.design_table(table))
            menu.addAction(self.text('add_record'),lambda:self.insert_row(table))
            menu.addAction('Edit Rows (Grid)',lambda:self.edit_rows(table))
            menu.addSeparator()
        menu.addAction(self.text('new_table'),self.new_table)
        menu.addAction(self.text('new_relation'),self.new_relation)
        menu.addAction(self.text('generate_scripts'),self.generate_scripts)
        menu.addSeparator()
        menu.addAction(self.text('refresh'),self.refresh_all)
        menu.exec(self.explorer.viewport().mapToGlobal(pos))
    def tree_double(self,item,column):
        table=self.selected_table()
        if table:self.show_data(table)
    def show_data(self,table):
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
            refresh=QPushButton(self.text('refresh'))
            refresh.setObjectName('refreshDataButton')
            refresh.clicked.connect(lambda:self.update_data_tab(table))
            top.addWidget(add)
            grid_edit=QPushButton('▦  Edit Rows')
            grid_edit.setObjectName('editRowsButton')
            grid_edit.clicked.connect(lambda:self.edit_rows(table))
            top.addWidget(grid_edit)
            top.addWidget(refresh)
            closeview=QPushButton('×  Close View')
            closeview.setObjectName('closeDataViewButton')
            closeview.setToolTip('Closes this view only; table and records stay in the database.')
            closeview.clicked.connect(lambda:self.close_data_page(table))
            top.addWidget(closeview)
            layout.addLayout(top)
            grid=QTableWidget()
            grid.setObjectName('dataGrid')
            grid.setAlternatingRowColors(True)
            grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            grid.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            grid.verticalHeader().setVisible(False)
            layout.addWidget(grid)
            self.data_tabs[table]=page
            self.tabs.addTab(page,self.text('data_title',table=table))
        self.update_data_tab(table)
        self.tabs.setCurrentWidget(self.data_tabs[table])
    def update_data_tab(self,table):
        if not self.db or table not in self.data_tabs:return
        page=self.data_tabs[table]
        grid=page.findChild(QTableWidget,'dataGrid')
        names,rows=get_rows(self.db,table)
        grid.setUpdatesEnabled(False)
        grid.clear()
        grid.setRowCount(len(rows))
        grid.setColumnCount(len(names))
        grid.setHorizontalHeaderLabels(names)
        for r,values in enumerate(rows):
            for c,value in enumerate(values):
                cell=QTableWidgetItem('NULL' if value is None else str(value))
                if value is None:cell.setForeground(QColor(palette(self.theme)['muted']))
                grid.setItem(r,c,cell)
        grid.resizeColumnsToContents()
        grid.setUpdatesEnabled(True)
    def insert_selected(self):
        if not self.require_db():return
        name=self.selected_table()
        if not name:
            QMessageBox.information(self,self.text('add_record'),self.text('table_note'))
            return
        self.insert_row(name)
    def edit_rows(self,table):
        if not self.require_db():return
        GridRowEditor(self.db,table,self.lang,self.refresh_all,self).exec()
    def insert_row(self,table):
        dlg=DataEntryDialog(self.db,table,self.lang,self.refresh_all,self)
        dlg.exec()
    def execute_sql(self):
        if not self.require_db():return
        statement=self.editor.textCursor().selectedText().replace('\u2029','\n') or self.editor.toPlainText()
        try:
            headings,rows,msg=self.db.execute(statement)
        except Exception as exc:
            self.output_tabs.setCurrentWidget(self.messages)
            self.messages.setPlainText(str(exc))
            error(self,self.lang,exc)
            return
        self.results.clear()
        self.results.setColumnCount(len(headings))
        self.results.setHorizontalHeaderLabels(headings)
        self.results.setRowCount(len(rows))
        for r,rec in enumerate(rows):
            for c,cell in enumerate(rec):
                self.results.setItem(r,c,QTableWidgetItem('NULL' if cell is None else str(cell)))
        self.results.resizeColumnsToContents()
        self.messages.setPlainText(msg)
        self.output_tabs.setCurrentWidget(self.results if headings else self.messages)
        self.refresh_all()
    def generate_scripts(self):
        if not self.require_db():return
        if not self.db.tables():
            QMessageBox.information(self,self.text('generate_scripts'),'Create at least one table first.')
            return
        ScriptExportWizard(self.db,self.lang,self).exec()
    def export_diagram(self):
        if not self.require_db():return
        path,_=QFileDialog.getSaveFileName(self,self.text('export_erd'),'Database_Diagram.png','PNG Image (*.png)')
        if path:
            try:
                if not path.lower().endswith('.png'):path+='.png'
                if not self.diagram.export_png(path):raise RuntimeError('Could not save PNG file.')
                info(self,self.lang,path)
            except Exception as exc:error(self,self.lang,exc)
    def report_bug(self):
        subject=f'Bug report | SQL Server Simulator v{APP_VERSION} | Ali Sayyadi'
        body=('Hello,\n\nBug description:\n\nSteps to reproduce:\n1. \n2. \n\nExpected result:\nActual result:\n\n'
              f'Application version: {APP_VERSION}\nWindows version:\n\n')
        webbrowser.open('https://mail.google.com/mail/?'+urlencode({'view':'cm','fs':'1','to':EMAIL,'su':subject,'body':body}))
    def report_mailto(self):
        subject=f'SQL Server Simulator {APP_VERSION} - Bug report'
        webbrowser.open('mailto:'+EMAIL+'?'+urlencode({'subject':subject}))
    def about(self):
        QMessageBox.about(self,self.text('about'),self.text('about_text'))
    def closeEvent(self,event):
        self.prefs.setValue('window/geometry',self.saveGeometry())
        self.prefs.sync()
        if self.db:self.db.close()
        super().closeEvent(event)

def run():
    app=QApplication(sys.argv)
    app.setOrganizationName('Ali Sayyadi')
    app.setApplicationName('SQL Server Simulator')
    app.setApplicationVersion(APP_VERSION)
    window=MainWindow()
    window.show()
    QTimer.singleShot(150,window.language_prompt_first_run)
    return app.exec()

if __name__=='__main__':sys.exit(run())
