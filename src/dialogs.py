"""Mouse-driven database, table, relation and data-entry flows."""
from __future__ import annotations
from pathlib import Path
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWizard,QWizardPage,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,
    QLabel,QLineEdit,QPushButton,QToolButton,QComboBox,QCheckBox,QTableWidget,QTableWidgetItem,
    QHeaderView,QDialogButtonBox,QFileDialog,QMessageBox,QGroupBox,QWidget,QScrollArea,
    QSpinBox,QTextEdit,QListWidget,QListWidgetItem,QAbstractItemView)
from core import LabDatabase, LabError, Column, identifier, q
from model_ext import insert_data,is_identity
from sqlserver_export import export_script, TARGET_VERSIONS
from i18n import tr

TYPES=['INT','BIGINT','SMALLINT','TINYINT','BIT','NVARCHAR(50)','NVARCHAR(100)',
       'NVARCHAR(255)','NVARCHAR(MAX)','NCHAR(10)','VARCHAR(50)','VARCHAR(255)',
       'CHAR(10)','DECIMAL(18,2)','NUMERIC(18,2)','FLOAT','REAL',
       'DATE','DATETIME2','DATETIME','TIME','MONEY','UNIQUEIDENTIFIER',
       'VARBINARY(MAX)','TEXT','INTEGER']

class TypeSettings(QDialog):
    """Explicit SQL Server type/length chooser, no arbitrary SQL typing needed."""
    def __init__(self,initial='NVARCHAR(100)',parent=None):
        super().__init__(parent)
        self.setWindowTitle('SQL Server data type')
        self.resize(410,210)
        form=QFormLayout(self)
        self.base=QComboBox()
        bases=['INT','INTEGER','TEXT','BIGINT','SMALLINT','TINYINT','BIT','NVARCHAR','NCHAR','VARCHAR','CHAR',
               'DECIMAL','NUMERIC','FLOAT','REAL','DATE','DATETIME2','DATETIME','TIME',
               'MONEY','UNIQUEIDENTIFIER','VARBINARY']
        self.base.addItems(bases)
        self.length=QSpinBox();self.length.setRange(1,4000);self.length.setValue(100)
        self.maxlen=QCheckBox('MAX (NVARCHAR / VARCHAR / VARBINARY only)')
        self.precision=QSpinBox();self.precision.setRange(1,38);self.precision.setValue(18)
        self.scale=QSpinBox();self.scale.setRange(0,38);self.scale.setValue(2)
        form.addRow('Data type:',self.base)
        form.addRow('Length:',self.length)
        form.addRow('',self.maxlen)
        form.addRow('Precision:',self.precision)
        form.addRow('Scale:',self.scale)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        import re
        mt=re.fullmatch(r'(\w+)(?:\((MAX|\d+)(?:,\s*(\d+))?\))?',initial.upper())
        if mt:
            self.base.setCurrentText(mt.group(1))
            if mt.group(2)=='MAX':self.maxlen.setChecked(True)
            elif mt.group(2):self.length.setValue(min(4000,int(mt.group(2))));self.precision.setValue(min(38,int(mt.group(2))))
            if mt.group(3):self.scale.setValue(int(mt.group(3)))
        self.base.currentTextChanged.connect(self.sync)
        self.maxlen.toggled.connect(self.sync)
        self.sync()
    def sync(self,*args):
        name=self.base.currentText()
        strtype=name in ('NVARCHAR','VARCHAR','NCHAR','CHAR','VARBINARY')
        dec=name in ('DECIMAL','NUMERIC')
        self.length.setEnabled(strtype and not self.maxlen.isChecked())
        self.maxlen.setEnabled(name in ('NVARCHAR','VARCHAR','VARBINARY'))
        if not self.maxlen.isEnabled():self.maxlen.setChecked(False)
        self.precision.setEnabled(dec);self.scale.setEnabled(dec)
    def type_name(self):
        name=self.base.currentText()
        if name in ('NVARCHAR','VARCHAR','NCHAR','CHAR','VARBINARY'):
            if self.maxlen.isChecked():return f'{name}(MAX)'
            return f'{name}({self.length.value()})'
        if name in ('DECIMAL','NUMERIC'):
            return f'{name}({self.precision.value()},{self.scale.value()})'
        return name
    def accept(self):
        if self.base.currentText() in ('DECIMAL','NUMERIC') and self.scale.value()>self.precision.value():
            QMessageBox.warning(self,'Invalid precision','Scale cannot exceed precision.')
            return
        super().accept()

class IdentitySettings(QDialog):
    def __init__(self,seed=1,increment=1,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Identity Specification  /  SQL Server')
        self.setMinimumWidth(420)
        form=QFormLayout(self)
        self.seed=QLineEdit(str(int(seed)))
        self.increment=QLineEdit(str(int(increment)))
        form.addRow('(Is Identity):',QLabel('Yes  •  Database generated'))
        form.addRow('Identity Seed:',self.seed)
        form.addRow('Identity Increment:',self.increment)
        hint=QLabel('For Seed = 100 and Increment = 5, inserted keys are 100, 105, 110, ...')
        hint.setWordWrap(True);form.addRow(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject)
        form.addRow(buttons)
    def accept(self):
        try:
            seed=int(self.seed.text().strip())
            increment=int(self.increment.text().strip())
            if increment==0 or abs(seed)>10**12 or abs(increment)>10**9:
                raise ValueError('Seed must be within +/- 1 trillion; increment must be nonzero and within +/- 1 billion.')
        except ValueError as exc:
            QMessageBox.warning(self,'Invalid identity specification',str(exc))
            return
        super().accept()


def error(parent,lang,exc):
    QMessageBox.critical(parent,tr('err',lang),str(exc))

def info(parent,lang,message):
    QMessageBox.information(parent,tr('success',lang),message)

def apply_locale(dialog,lang):
    dialog.setLayoutDirection(Qt.LayoutDirection.RightToLeft if lang=='fa' else Qt.LayoutDirection.LeftToRight)

class NewDatabaseWizard(QWizard):
    def __init__(self,lang,root,parent=None):
        super().__init__(parent)
        self.lang=lang
        self.created_path=None
        self.setWindowTitle(tr('db_wiz_title',lang))
        self.setMinimumSize(630,395)
        apply_locale(self,lang)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        first=QWizardPage()
        first.setTitle(tr('wizard_welcome',lang))
        first.setSubTitle(tr('db_intro',lang))
        a=QVBoxLayout(first)
        intro=QLabel(tr('db_intro_detail',lang))
        intro.setWordWrap(True)
        a.addWidget(intro)
        a.addStretch()
        a.addWidget(QLabel('●  Primary keys     ●  Foreign keys     ●  Entity relationships'))
        self.addPage(first)
        second=QWizardPage()
        second.setTitle(tr('wizard_location',lang))
        second.setSubTitle(tr('db_review',lang))
        b=QFormLayout(second)
        self.name=QLineEdit('PracticeDB')
        self.name.textChanged.connect(lambda _:second.completeChanged.emit())
        b.addRow(tr('db_name',lang),self.name)
        dirrow=QWidget()
        lr=QHBoxLayout(dirrow)
        lr.setContentsMargins(0,0,0,0)
        self.folder=QLineEdit(str(root))
        self.folder.textChanged.connect(lambda _:second.completeChanged.emit())
        browse=QPushButton(tr('browse',lang))
        browse.clicked.connect(self.choose_dir)
        lr.addWidget(self.folder,1)
        lr.addWidget(browse)
        b.addRow(tr('location',lang),dirrow)
        self.addPage(second)
    def choose_dir(self):
        chosen=QFileDialog.getExistingDirectory(self,tr('location',self.lang),self.folder.text())
        if chosen: self.folder.setText(chosen)
    def accept(self):
        try:
            name=identifier(self.name.text())
            folder=Path(self.folder.text()).expanduser()
            if not folder.exists() or not folder.is_dir(): raise LabError('Choose an existing folder.')
            target=(folder / (name+'.db')).resolve()
            if target.exists(): raise LabError('This database already exists. Choose a different name or use Open Database.')
            db=LabDatabase(target)
            db.close()
            self.created_path=target
        except Exception as exc:
            error(self,self.lang,exc)
            return
        super().accept()

class TableDesigner(QDialog):
    def __init__(self,db,lang,on_saved,parent=None,table=None):
        super().__init__(parent)
        self.db,self.lang,self.on_saved=db,lang,on_saved
        self.existing_table=table
        self.setWindowTitle(('Design Table: '+table) if table else tr('tbl_title',lang))
        self.resize(960,630)
        apply_locale(self,lang)
        main=QVBoxLayout(self)
        header=QLabel(tr('tbl_title',lang))
        header.setProperty('role','heading')
        main.addWidget(header)
        form=QFormLayout()
        self.table_name=QLineEdit()
        self.table_name.setPlaceholderText('Student')
        if table:
            self.table_name.setText(table)
            self.table_name.setReadOnly(True)
        form.addRow(tr('table_name',lang)+':',self.table_name)
        main.addLayout(form)
        self.identity_values={}
        self.grid=QTableWidget(0,5)
        self.grid.setHorizontalHeaderLabels([tr('column_name',lang),tr('data_type',lang),
                                             tr('primary_key',lang),tr('not_null',lang),tr('auto_increment',lang)])
        self.grid.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.grid.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        for x in (2,3,4): self.grid.horizontalHeader().setSectionResizeMode(x,QHeaderView.ResizeMode.ResizeToContents)
        self.grid.setAlternatingRowColors(True)
        self.grid.verticalHeader().setVisible(False)
        self.grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        main.addWidget(self.grid)
        tools=QHBoxLayout()
        plus=QPushButton('＋  '+tr('add_column',lang))
        plus.clicked.connect(lambda: self.add_column())
        tools.addWidget(plus)
        minus=QPushButton('−  '+tr('remove_column',lang))
        minus.clicked.connect(self.remove_column)
        tools.addWidget(minus)
        tools.addStretch()
        main.addLayout(tools)
        tip=QLabel(tr('auto_hint',lang))
        tip.setWordWrap(True)
        tip.setProperty('role','muted')
        main.addWidget(tip)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Save Changes' if table else tr('save_table',lang))
        buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty('role','primary')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('cancel',lang))
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        main.addWidget(buttons)
        if table:
            for col in db.design_columns(table):
                self.add_column(col.name,col.type,col.primary,col.required,col.auto,
                                original=col.name,seed=col.seed,increment=col.increment)
        else:
            self.add_column('ID','INT',True,True,True)
            self.add_column('Name','NVARCHAR(100)',False,True,False)
        self.grid.setToolTip('Double-click a name to rename. Existing data are migrated safely when possible.')
    def add_column(self,name='',datatype='NVARCHAR(100)',pk=False,notnull=False,identity=False,
                   original=None,seed=1,increment=1):
        r=self.grid.rowCount()
        self.grid.insertRow(r)
        self.grid.setRowHeight(r,40)
        cell_name=QTableWidgetItem(name)
        cell_name.setData(Qt.ItemDataRole.UserRole,original)
        self.grid.setItem(r,0,cell_name)
        typ=QComboBox()
        typ.setEditable(False)  # Truly selectable SQL Server-style types.
        typ.addItems(TYPES)
        if datatype not in TYPES:typ.addItem(datatype)
        typ.setCurrentText(datatype)
        box_type=QWidget();type_layout=QHBoxLayout(box_type);type_layout.setContentsMargins(1,1,1,1)
        type_layout.addWidget(typ,1)
        details=QPushButton('…');details.setToolTip('Set SQL data type and length / precision')
        details.setFixedWidth(34)
        details.clicked.connect(lambda _=False,combo=typ:self.type_settings(combo))
        type_layout.addWidget(details)
        self.grid.setCellWidget(r,1,box_type)
        for col,initial in ((2,pk),(3,notnull),(4,identity)):
            chk=QCheckBox();chk.setChecked(initial)
            wrapper=QWidget();layout=QHBoxLayout(wrapper)
            layout.setContentsMargins(0,0,0,0)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(chk)
            if col==4:
                self.identity_values[chk]=(seed,increment)
                options=QPushButton('⚙')
                options.setToolTip('Identity Specification: Seed / Increment')
                options.clicked.connect(lambda _=False,cb=chk:self.open_identity(cb))
                layout.addWidget(options)
                chk.stateChanged.connect(lambda state,identity_checkbox=chk:self.identity_changed(identity_checkbox,state))
            self.grid.setCellWidget(r,col,wrapper)
    def type_combo(self,row):
        container=self.grid.cellWidget(row,1)
        return container.findChild(QComboBox) if container else None
    def type_settings(self,combo):
        dialog=TypeSettings(combo.currentText(),self)
        if dialog.exec():
            text=dialog.type_name()
            if combo.findText(text)<0:combo.addItem(text)
            combo.setCurrentText(text)
    def check(self,r,c):
        cell=self.grid.cellWidget(r,c)
        return cell.findChild(QCheckBox) if cell else None
    def open_identity(self,checkbox):
        if not checkbox.isChecked():checkbox.setChecked(True)
        seed,step=self.identity_values.get(checkbox,(1,1))
        editor=IdentitySettings(seed,step,self)
        if editor.exec():self.identity_values[checkbox]=(int(editor.seed.text()),int(editor.increment.text()))
    def identity_changed(self,checkbox,state):
        if not state:return
        r=next((i for i in range(self.grid.rowCount()) if self.check(i,4) is checkbox),-1)
        if r<0:return
        pk=self.check(r,2);nn=self.check(r,3)
        if pk:pk.setChecked(True)
        if nn:nn.setChecked(True)
        typ=self.type_combo(r)
        if typ and typ.currentText() not in ('INT','INTEGER','BIGINT','SMALLINT','TINYINT'):
            typ.setCurrentText('INT')
        for i in range(self.grid.rowCount()):
            if i!=r:
                other=self.check(i,4)
                if other:other.setChecked(False)
    def remove_column(self):
        rows=sorted({i.row() for i in self.grid.selectedIndexes()},reverse=True)
        if self.existing_table and any(self.grid.item(r,0) and self.grid.item(r,0).data(Qt.ItemDataRole.UserRole) for r in rows):
            if QMessageBox.question(self,'Remove existing columns',
                'Removing an existing column permanently deletes its values when you save. Continue?') != QMessageBox.StandardButton.Yes:
                return
        for r in rows:self.grid.removeRow(r)
    def save(self):
        try:
            cols=[]
            for r in range(self.grid.rowCount()):
                item=self.grid.item(r,0)
                name=item.text().strip() if item else ''
                data=self.type_combo(r).currentText().strip()
                isid=self.check(r,4).isChecked()
                seed,step=self.identity_values.get(self.check(r,4),(1,1))
                cols.append(Column(name,data,self.check(r,2).isChecked(),
                                   self.check(r,3).isChecked(),isid,seed,step))
            if self.existing_table:
                original_map={}
                for r,c in enumerate(cols):
                    original_map[c.name]=self.grid.item(r,0).data(Qt.ItemDataRole.UserRole)
                self.db.edit_table(self.existing_table,cols,original_map)
            else:
                self.db.create_table(self.table_name.text().strip(),cols)
        except Exception as exc:
            error(self,self.lang,exc)
            return
        self.on_saved()
        self.accept()

class RelationshipWizard(QWizard):
    """No-SQL relationship wizard, including precise field-to-field mapping."""
    CREATE_NEW = '<Create new foreign-key field>'

    def __init__(self, db, lang, on_saved, parent=None, source_table=None,
                 target_table=None, initial_kind=None, source_field=None, target_field=None):
        super().__init__(parent)
        self.db, self.lang, self.on_saved = db, lang, on_saved
        self.preselected_source_field = source_field
        self.preselected_target_field = target_field
        self.setWindowTitle('Create Relationship  |  Field Mapping')
        self.resize(760, 560)
        apply_locale(self, lang)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        p1 = QWizardPage()
        p1.setTitle('Choose relationship cardinality')
        info_layout = QVBoxLayout(p1)
        self.kind = QComboBox()
        for label, value in [
            ('One-to-many  (1:N)', '1:N'),
            ('One-to-one  (1:1 / shared primary key)', '1:1'),
            ('Many-to-many  (N:M / junction table)', 'N:M'),
            ('Self-referencing  (1:N / hierarchy)', 'SELF')
        ]:
            self.kind.addItem(label, value)
        info_layout.addWidget(self.kind)
        self.intro = QLabel()
        self.intro.setWordWrap(True)
        self.intro.setMinimumHeight(100)
        info_layout.addWidget(self.intro)
        info_layout.addStretch()
        self.addPage(p1)
        p2 = QWizardPage()
        p2.setTitle('Map fields and enforce foreign keys')
        p2.setSubTitle('The referenced side must be a PRIMARY KEY. The child holds the FOREIGN KEY.')
        form = QFormLayout(p2)
        names = db.tables()
        self.parent_combo = QComboBox()
        self.parent_combo.addItems(names)
        self.child_combo = QComboBox()
        self.child_combo.addItems(names)
        if len(names) > 1:
            self.child_combo.setCurrentIndex(1)
        if source_table in names:
            self.parent_combo.setCurrentText(source_table)
        if target_table in names:
            self.child_combo.setCurrentText(target_table)
        self.parent_field = QComboBox()
        self.child_field = QComboBox()
        self.fk = QLineEdit()
        self.fk.setPlaceholderText('DepartmentID')
        self.required = QCheckBox('Required: FK cannot be NULL')
        self.required.setChecked(False)
        self.bridge = QLineEdit('Enrollment')
        self.strategy = QComboBox()
        self.strategy.addItem('Composite primary key (two foreign keys)', 'composite')
        self.strategy.addItem('Surrogate IDENTITY key + unique FK pair', 'surrogate')
        self.mapping_hint = QLabel('')
        self.mapping_hint.setWordWrap(True)
        self.mapping_hint.setProperty('role', 'muted')
        self.form_rows = []
        def row(label, widget):
            lbl = QLabel(label)
            form.addRow(lbl, widget)
            self.form_rows.append((lbl, widget))
        row('Referenced / parent table (1):', self.parent_combo)
        row('Referenced PRIMARY KEY:', self.parent_field)
        row('Referencing / child table (N):', self.child_combo)
        row('Child FOREIGN KEY:', self.child_field)
        row('Name of NEW child FK:', self.fk)
        row('', self.required)
        row('Junction table:', self.bridge)
        row('Junction primary key strategy:', self.strategy)
        row('', self.mapping_hint)
        self.addPage(p2)
        self._suggested_fk = ''
        self.parent_combo.currentTextChanged.connect(self.populate_fields)
        self.child_combo.currentTextChanged.connect(self.populate_fields)
        self.parent_field.currentTextChanged.connect(self.sync_fields)
        self.child_field.currentIndexChanged.connect(self.sync_fields)
        self.kind.currentIndexChanged.connect(self.kind_changed)
        self.currentIdChanged.connect(lambda _: self.sync_fields())
        if source_table and target_table and source_table == target_table:
            initial_kind = 'SELF'
        elif source_field and target_field and source_table != target_table:
            child_key_names = {c['name'].casefold() for c in db.columns(target_table) if c['pk']}
            initial_kind = '1:1' if target_field.casefold() in child_key_names else '1:N'
        if initial_kind:
            at = self.kind.findData(initial_kind)
            if at >= 0:
                self.kind.setCurrentIndex(at)
        self.populate_fields()
        self.setButtonText(QWizard.WizardButton.FinishButton, 'Create Relationship')

    def populate_fields(self, *args):
        parent = self.parent_combo.currentText()
        child = self.child_combo.currentText()
        previous_parent = self.parent_field.currentText()
        previous_child = self.child_field.currentText()
        self.parent_field.blockSignals(True)
        self.child_field.blockSignals(True)
        self.parent_field.clear()
        self.child_field.clear()
        if parent:
            for col in self.db.columns(parent):
                if col['pk']:
                    self.parent_field.addItem(col['name'])
        if child:
            for col in self.db.columns(child):
                self.child_field.addItem(col['name'])
            self.child_field.addItem(self.CREATE_NEW)
        selected_parent = self.preselected_source_field or previous_parent
        selected_child = self.preselected_target_field or previous_child
        if self.parent_field.findText(selected_parent) >= 0:
            self.parent_field.setCurrentText(selected_parent)
        if self.child_field.findText(selected_child) >= 0:
            self.child_field.setCurrentText(selected_child)
        elif self.child_field.count():
            self.child_field.setCurrentText(self.CREATE_NEW)
        self.parent_field.blockSignals(False)
        self.child_field.blockSignals(False)
        self.preselected_source_field = None
        self.preselected_target_field = None
        if parent and self.parent_field.currentText():
            field = self.parent_field.currentText()
            proposal = parent+'ID' if field.casefold() == 'id' else field
            if child and proposal.casefold() in {c['name'].casefold() for c in self.db.columns(child)}:
                proposal = parent+'_'+field
            if not self.fk.text().strip() or self.fk.text() == self._suggested_fk:
                self.fk.setText(proposal)
            self._suggested_fk = proposal
        self.sync_fields()

    def kind_changed(self, *args):
        if self.kind.currentData() == 'SELF':
            self.child_combo.setCurrentText(self.parent_combo.currentText())
        self.sync_fields()

    def default_fk(self, *args):
        self.populate_fields()

    def sync_fields(self, *args):
        kind = self.kind.currentData()
        descriptions = {
            '1:N': 'Parent PK → Child FK. A child may reference an existing parent only; an optional FK may be NULL.',
            '1:1': 'Shared primary key: Child PK is also FK to Parent PK. Child Identity must be OFF.',
            'N:M': 'Choose the PK on both endpoint tables. A real junction table with two FKs will be created.',
            'SELF': 'One table references its own PK through a different FK field (e.g. ManagerID). Roots may have NULL FK.'
        }
        self.intro.setText(descriptions.get(kind, ''))
        if kind == 'SELF' and self.parent_combo.currentText() and self.child_combo.currentText() != self.parent_combo.currentText():
            self.child_combo.blockSignals(True)
            self.child_combo.setCurrentText(self.parent_combo.currentText())
            self.child_combo.blockSignals(False)
            self.populate_fields()
            return
        # When choosing 1:1 or N:M, child PK is the only meaningful target.
        if kind in ('1:1', 'N:M'):
            child = self.child_combo.currentText()
            if child:
                try:
                    pk = self.db.primary_key(child)['name']
                    if self.child_field.currentText() != pk:
                        self.child_field.blockSignals(True)
                        self.child_field.setCurrentText(pk)
                        self.child_field.blockSignals(False)
                except LabError:
                    pass
        new_fk = self.child_field.currentText() == self.CREATE_NEW
        for index, (label, control) in enumerate(self.form_rows):
            show = True
            if index == 4: show = new_fk and kind in ('1:N','SELF')
            if index == 5: show = kind == '1:N'
            if index in (6,7): show = kind == 'N:M'
            label.setVisible(show)
            control.setVisible(show)
        field = self.child_field.currentText()
        parent = self.parent_combo.currentText()
        child = self.child_combo.currentText()
        if kind == 'N:M':
            self.mapping_hint.setText('The endpoints remain separate. A new junction table and both enforced FKs are generated.')
        elif kind == 'SELF':
            self.mapping_hint.setText(f'{child}.{field if not new_fk else self.fk.text()} → {parent}.{self.parent_field.currentText()}')
        else:
            self.mapping_hint.setText(f'{parent}.{self.parent_field.currentText()} (PK) → {child}.{field if not new_fk else self.fk.text()} (FK)')

    def accept(self):
        try:
            kind = self.kind.currentData()
            parent, child = self.parent_combo.currentText(), self.child_combo.currentText()
            parent_field = self.parent_field.currentText()
            child_field = self.child_field.currentText()
            if child_field == self.CREATE_NEW:
                child_field = self.fk.text().strip()
            if not parent or not child or not parent_field or not child_field:
                raise LabError('Select the parent and child tables and fields.')
            if kind != 'SELF' and parent == child:
                raise LabError('For a relationship within one table, select Self-referencing.')
            if kind == 'SELF' and parent != child:
                raise LabError('Self-reference requires the same table on both sides.')
            result = self.db.connect_fields(parent,parent_field,child,child_field,
                                            kind=kind,required=self.required.isChecked(),
                                            bridge=self.bridge.text().strip() if kind == 'N:M' else None,
                                            strategy=self.strategy.currentData())
        except Exception as exc:
            error(self,self.lang,exc)
            return
        self.on_saved()
        info(self,self.lang,result)
        super().accept()

class ScriptExportWizard(QWizard):
    """Generate Scripts dialog with object selection and target version."""
    def __init__(self,db,lang,parent=None):
        super().__init__(parent)
        self.db=db;self.lang=lang
        self.setWindowTitle('Generate Scripts Wizard  /  SQL Server')
        self.resize(690,550)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        page1=QWizardPage();page1.setTitle('Choose objects to script')
        layout=QVBoxLayout(page1)
        layout.addWidget(QLabel('Select the tables to include in the SQL script.'))
        self.tablelist=QListWidget()
        for name in db.tables():
            item=QListWidgetItem(name)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.tablelist.addItem(item)
        layout.addWidget(self.tablelist)
        self.addPage(page1)
        page2=QWizardPage();page2.setTitle('Script options and target version')
        form=QFormLayout(page2)
        self.mode=QComboBox()
        for label,val in [('Schema and Data','both'),('Schema only','schema'),('Data only','data')]:
            self.mode.addItem(label,val)
        self.version=QComboBox()
        for v in TARGET_VERSIONS:self.version.addItem('SQL Server '+v,v)
        self.version.setCurrentIndex(self.version.findData('2022'))
        self.dbname=QLineEdit(db.path.stem)
        self.path=QLineEdit(str(db.path.with_name(db.path.stem+'_SQLServer.sql')))
        browse=QPushButton('Browse…')
        browse.clicked.connect(self.choose_path)
        targetrow=QWidget();r=QHBoxLayout(targetrow);r.setContentsMargins(0,0,0,0)
        r.addWidget(self.path,1);r.addWidget(browse)
        form.addRow('Types of data to script:',self.mode)
        form.addRow('Script for server version:',self.version)
        form.addRow('Target database name:',self.dbname)
        form.addRow('Save as script file:',targetrow)
        warning=QLabel('Creates a T-SQL (.sql) script, NOT a native .bak file.\n'
                       'Only selected tables/PK/FK/data are included.\n'
                       'Test scripts on a non-production SQL Server.')
        warning.setWordWrap(True)
        form.addRow(warning)
        self.addPage(page2)
        self.setButtonText(QWizard.WizardButton.FinishButton,'Generate Script')
    def choose_path(self):
        path,_=QFileDialog.getSaveFileName(self,'Save T-SQL script',self.path.text(),'SQL Scripts (*.sql)')
        if path:self.path.setText(path)
    def accept(self):
        try:
            names=[self.tablelist.item(i).text() for i in range(self.tablelist.count())
                   if self.tablelist.item(i).checkState()==Qt.CheckState.Checked]
            target=self.path.text().strip()
            if not names:raise LabError('Select at least one table.')
            if Path(target).exists():
                if QMessageBox.question(self,'Overwrite existing file?',target)!=QMessageBox.StandardButton.Yes:return
            export_script(self.db,target,names,self.mode.currentData(),self.version.currentData(),
                          self.dbname.text().strip() or None)
        except Exception as exc:
            error(self,self.lang,exc)
            return
        info(self,self.lang,f'SQL Server script exported to: \n{target}')
        super().accept()

class DataEntryDialog(QDialog):
    def __init__(self,db,table,lang,on_insert,parent=None):
        super().__init__(parent)
        self.db,self.table,self.lang,self.on_insert=db,table,lang,on_insert
        self.setWindowTitle(tr('record_title',lang,table=table))
        self.resize(570,510)
        apply_locale(self,lang)
        main=QVBoxLayout(self)
        tip=QLabel(tr('empty_as_null',lang))
        tip.setWordWrap(True)
        tip.setProperty('role','muted')
        main.addWidget(tip)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        holder=QWidget()
        form=QFormLayout(holder)
        self.fields=[]
        references={r['from']:r for r in db.foreign_keys(table)}
        for c in db.columns(table):
            name=c['name']
            lbl=name+('  [PK]' if c['pk'] else '')+('  [FK]' if name in references else '')
            if is_identity(db,table,name):
                field=QLabel('🔒  '+tr('db_generated',lang))
                field.setProperty('role','muted')
                form.addRow(lbl,field)
                continue
            if name in references:
                reference=references[name]
                field=QComboBox()
                field.addItem('(NULL / empty)', None)
                try:
                    rows=db.connection.execute('SELECT DISTINCT '+q(reference['to'])+' FROM '+q(reference['table'])+' LIMIT 500').fetchall()
                    for record in rows:field.addItem(str(record[0]),record[0])
                except sqlite3.Error:
                    pass
                if c['notnull'] and field.count()>1:field.setCurrentIndex(1)
            else:
                field=QLineEdit()
                field.setPlaceholderText(db.logical_type(table,name)+'  •  '+('required' if c['notnull'] or c['pk'] else 'optional'))
            nullable=not bool(c['notnull'] or c['pk'])
            nullcheck=QCheckBox('NULL') if nullable and name not in references else None
            if nullcheck:
                nullcheck.setChecked(True)
                field.setEnabled(False)
                nullcheck.toggled.connect(lambda checked,widget=field:widget.setEnabled(not checked))
                holderrow=QWidget();hl=QHBoxLayout(holderrow);hl.setContentsMargins(0,0,0,0)
                hl.addWidget(field,1);hl.addWidget(nullcheck)
                form.addRow(lbl,holderrow)
            else:
                form.addRow(lbl,field)
            self.fields.append((c,field,nullcheck))
        scroll.setWidget(holder)
        main.addWidget(scroll)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('insert',lang))
        buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty('role','primary')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('cancel',lang))
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        main.addWidget(buttons)
    def save(self):
        try:
            values={}
            for c,widget,nullcheck in self.fields:
                if nullcheck is not None and nullcheck.isChecked():
                    value=None
                elif isinstance(widget,QComboBox):value=widget.currentData()
                else:
                    raw=widget.text()  # Preserve empty string instead of silently inserting NULL.
                    value=raw
                    typ=self.db.logical_type(self.table,c['name']).upper()
                    if typ in ('INT','INTEGER','BIGINT','SMALLINT','TINYINT','BIT','BOOLEAN'):
                        if not raw.strip():raise LabError(f'{c["name"]} needs an integer value, or select NULL.')
                        value=int(raw.strip())
                        if typ in ('BIT','BOOLEAN') and value not in (0,1):raise LabError('BIT must be 0 or 1.')
                    elif typ.startswith(('DECIMAL','NUMERIC')) or typ in ('REAL','FLOAT','DOUBLE','MONEY','SMALLMONEY'):
                        if not raw.strip():raise LabError(f'{c["name"]} needs a numeric value, or select NULL.')
                        value=float(raw.strip())
                values[c['name']]=value
            ident, row=insert_data(self.db,self.table,values)
        except Exception as exc:
            error(self,self.lang,exc)
            return
        self.on_insert()
        info(self,self.lang,tr('saved_id',self.lang,id=ident))
        self.accept()

class GridRowEditor(QDialog):
    """SSMS-inspired Edit Rows view: existing rows read-only, a new input row below."""
    def __init__(self,db,table,lang,on_insert,parent=None):
        super().__init__(parent)
        self.db,self.table,self.lang,self.on_insert=db,table,lang,on_insert
        self.setWindowTitle(f'Edit Rows  |  {table}')
        self.resize(1030,650)
        layout=QVBoxLayout(self)
        heading=QLabel(f'Edit Rows  /  {table}')
        heading.setProperty('role','heading');layout.addWidget(heading)
        note=QLabel('Existing rows are read-only. Enter values on the last row (marked NEW). '
                    'NULL = database NULL; empty text = empty string; identity is database-generated. '
                    'Use Insert Row to save the new row.')
        note.setWordWrap(True);layout.addWidget(note)
        self.grid=QTableWidget()
        self.grid.setAlternatingRowColors(True)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self.grid,1)
        controls=QHBoxLayout()
        self.result=QLabel('Ready. Add one row at a time.')
        self.result.setProperty('role','muted');controls.addWidget(self.result,1)
        save=QPushButton('＋  Insert New Row');save.setProperty('role','primary')
        save.clicked.connect(self.insert_new);controls.addWidget(save)
        close=QPushButton('Close');close.clicked.connect(self.accept);controls.addWidget(close)
        layout.addLayout(controls)
        self.populate()
    def populate(self):
        self.cols=self.db.columns(self.table)
        rows=self.db.connection.execute(f'SELECT * FROM {q(self.table)} LIMIT 200').fetchall()
        self.grid.clear()
        self.grid.setRowCount(len(rows)+1)
        self.grid.setColumnCount(len(self.cols))
        self.grid.setHorizontalHeaderLabels([c['name']+'  ('+self.db.logical_type(self.table,c['name'])+')' for c in self.cols])
        self.grid.setVerticalHeaderLabels([str(i+1) for i in range(len(rows))]+['NEW  *'])
        for r,row in enumerate(rows):
            for j,v in enumerate(row):
                item=QTableWidgetItem('NULL' if v is None else str(v))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
                self.grid.setItem(r,j,item)
        self.newrow=len(rows)
        self.fk_widgets={}
        refs={r['from']:r for r in self.db.foreign_keys(self.table)}
        for col,c in enumerate(self.cols):
            name=c['name']
            if is_identity(self.db,self.table,name):
                item=QTableWidgetItem('(DB GENERATED)')
                item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
                self.grid.setItem(self.newrow,col,item)
            elif name in refs:
                ref=refs[name]
                combo=QComboBox()
                if not c['notnull']:combo.addItem('NULL',None)
                records=self.db.connection.execute(f'SELECT DISTINCT {q(ref["to"])} FROM {q(ref["table"])} LIMIT 500').fetchall()
                for rec in records:combo.addItem(str(rec[0]),rec[0])
                self.grid.setCellWidget(self.newrow,col,combo)
                self.fk_widgets[name]=combo
            else:
                default='NULL' if not c['pk'] and not c['notnull'] else ''
                item=QTableWidgetItem(default)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsEditable)
                self.grid.setItem(self.newrow,col,item)
        self.grid.resizeColumnsToContents()
    def insert_new(self):
        try:
            values={}
            for col,c in enumerate(self.cols):
                name=c['name']
                if is_identity(self.db,self.table,name):continue
                if name in self.fk_widgets:
                    value=self.fk_widgets[name].currentData()
                else:
                    item=self.grid.item(self.newrow,col)
                    raw=item.text() if item else ''
                    typ=self.db.logical_type(self.table,name).upper()
                    if raw.strip().upper()=='NULL':
                        value=None
                    elif typ in ('INT','INTEGER','BIGINT','SMALLINT','TINYINT','BIT','BOOLEAN'):
                        value=int(raw.strip())
                        if typ in ('BIT','BOOLEAN') and value not in (0,1):raise LabError('BIT must be 0 or 1.')
                    elif typ.startswith(('DECIMAL','NUMERIC')) or typ in ('FLOAT','REAL','MONEY','SMALLMONEY'):
                        value=float(raw.strip())
                    else:
                        value=raw
                values[name]=value
            rowid,row=insert_data(self.db,self.table,values)
        except Exception as exc:
            error(self,self.lang,exc)
            return
        self.on_insert()
        self.populate()
        self.result.setText(f'Row saved successfully. Generated row ID: {rowid}')

class LanguageChoice(QDialog):
    def __init__(self,default='en',parent=None):
        super().__init__(parent)
        self.setWindowTitle('Choose your language / انتخاب زبان')
        self.setMinimumSize(400,200)
        layout=QVBoxLayout(self)
        text=QLabel('Choose application language\nزبان نرم‌افزار را انتخاب کنید')
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setProperty('role','heading')
        layout.addWidget(text)
        self.choice=QComboBox()
        self.choice.addItem('English', 'en')
        self.choice.addItem('فارسی', 'fa')
        self.choice.setCurrentIndex(0 if default=='en' else 1)
        layout.addWidget(self.choice)
        ok=QPushButton('Continue  /  ادامه')
        ok.setProperty('role','primary')
        ok.clicked.connect(self.accept)
        layout.addWidget(ok)
        self.language=default
    def accept(self):
        self.language=self.choice.currentData()
        super().accept()
