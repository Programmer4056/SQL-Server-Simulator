"""Reusable, native Qt designer widgets for the SQL teaching simulator."""
from __future__ import annotations
import re
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QRect, QSize, QRegularExpression, QPointF, QRectF, QStringListModel, QEvent
from PySide6.QtGui import (QColor, QFont, QPainter, QPen, QBrush, QTextFormat,
                           QSyntaxHighlighter, QTextCharFormat, QPainterPath, QPainterPathStroker, QTextCursor)
from PySide6.QtWidgets import (QWidget, QPlainTextEdit, QTextEdit, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsPathItem, QGraphicsSimpleTextItem, QGraphicsItem,
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QScrollArea, QSizePolicy, QCompleter, QLayout)
from core import LabDatabase
from layout_engine import auto_layout
from i18n import tr
from version_info import APP_AUTHOR, QA_LEAD_FA, QA_LEAD_EN
from locale_support import ui
from style import palette

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor=editor
    def sizeHint(self):
        return QSize(self.editor.line_width(), 0)
    def paintEvent(self, event):
        self.editor.paint_lines(event)

class SQLHighlighter(QSyntaxHighlighter):
    KW = re.compile(r'\b(SELECT|FROM|WHERE|CREATE|OR|ALTER|VIEW|PROCEDURE|PROC|FUNCTION|RETURNS|RETURN|EXEC|EXECUTE|BEGIN|END|GO|DECLARE|NOCOUNT|TABLE|DATABASE|PRIMARY|KEY|FOREIGN|REFERENCES|INSERT|INTO|VALUES|UPDATE|SET|DELETE|JOIN|INNER|LEFT|RIGHT|FULL|ON|AS|AND|OR|NOT|NULL|UNIQUE|ORDER|BY|GROUP|HAVING|LIMIT|ASC|DESC|DISTINCT|DROP|ALTER|ADD|INDEX|DEFAULT|AUTOINCREMENT|INTEGER|INT|TEXT|VARCHAR|DECIMAL|NUMERIC|REAL|DATE|DATETIME|CHECK|CASCADE|RESTRICT|BETWEEN|LIKE|IN|IS|COUNT|SUM|AVG|MIN|MAX)\b',re.I)
    STRING = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"")
    COMMENT = re.compile(r'--[^\n]*')
    NUMBER = re.compile(r'\b\d+(?:\.\d+)?\b')
    def __init__(self, document, theme='dark'):
        super().__init__(document)
        self.theme=theme
    def set_theme(self,theme):
        self.theme=theme
        self.rehighlight()
    def highlightBlock(self, text):
        p=palette(self.theme)
        for matcher, fg, bold in ((self.NUMBER,p['accent'],False),(self.KW,p['kw'],True),(self.STRING,p['string'],False),(self.COMMENT,p['comment'],False)):
            fmt=QTextCharFormat()
            fmt.setForeground(QColor(fg))
            if bold: fmt.setFontWeight(QFont.Weight.Bold)
            for match in matcher.finditer(text):
                self.setFormat(match.start(), match.end()-match.start(), fmt)

class SQLEditor(QPlainTextEdit):
    """SQL editor with schema-aware suggestions and accessible text zoom.

    Common SQL keywords, real table/view names, and matching table columns
    are offered as suggestions; accepting a suggestion never executes SQL.
    """
    MIN_FONT=8
    MAX_FONT=30
    DEFAULT_FONT=11
    KEYWORDS=(
        'SELECT','FROM','WHERE','JOIN','LEFT JOIN','INNER JOIN','RIGHT JOIN',
        'ON','AS','GROUP BY','ORDER BY','HAVING','DISTINCT','COUNT','SUM','AVG',
        'CREATE TABLE','CREATE VIEW','CREATE PROCEDURE','CREATE FUNCTION',
        'CREATE DATABASE','USE','GO','INSERT INTO','VALUES','UPDATE','SET',
        'DELETE FROM','ALTER TABLE','DROP TABLE','DROP VIEW','DROP PROCEDURE',
        'DROP FUNCTION','EXEC','EXECUTE','PRIMARY KEY','FOREIGN KEY',
        'REFERENCES','NOT NULL','IDENTITY','NVARCHAR','INT','DECIMAL',
        'BEGIN','END','RETURN','AND','OR','IS NULL','ORDER BY','ASC','DESC',
    )

    def __init__(self,theme='dark', parent=None):
        super().__init__(parent)
        self.theme=theme
        self.db=None
        self._font_point_size=self.DEFAULT_FONT
        self.on_zoom_changed=None
        self.setFont(QFont('Consolas' if sys.platform=='win32' else
                           ('Menlo' if sys.platform=='darwin' else 'DejaVu Sans Mono'),
                           self.DEFAULT_FONT))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.gutter=LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_width)
        self.updateRequest.connect(self.update_gutter)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.highlighter=SQLHighlighter(self.document(),theme)
        self._all_candidates=sorted(self.KEYWORDS,key=str.casefold)
        self._completion_model=QStringListModel(self)
        self.completer=QCompleter(self._completion_model,self)
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        self.completer.setMaxVisibleItems(10)
        self.completer.activated[str].connect(self.insert_completion)
        self.update_line_width()
        self.highlight_current_line()
        self.setPlaceholderText('SELECT * FROM "Student";')

    def set_database(self, db):
        self.db=db
        self.refresh_completion_source()

    def refresh_completion_source(self):
        """Discover table names and column names in the active database."""
        names=set(self.KEYWORDS)
        if self.db is not None:
            try:
                for table in self.db.tables():
                    names.add(table)
                    for column in self.db.columns(table):
                        names.add(column['name'])
                for row in self.db.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='view' AND name NOT LIKE 'sqlite_%'"
                ):
                    names.add(row[0])
            except Exception:
                # Metadata may disappear after a schema change; typing must
                # remain possible and refresh on the next schema update.
                pass
        self._all_candidates=sorted(names,key=str.casefold)
        self._completion_model.setStringList(self._all_candidates)

    def _completion_candidates(self, prefix):
        """Return columns after TableName. or general names otherwise."""
        text=self.textCursor().block().text()
        pos=self.textCursor().positionInBlock()
        before=text[:pos]
        dot=re.search(r'([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)?$',before)
        if dot and self.db is not None:
            table=dot.group(1)
            try:
                if table.casefold() in {name.casefold() for name in self.db.tables()}:
                    actual=next(name for name in self.db.tables() if name.casefold()==table.casefold())
                    return sorted({col['name'] for col in self.db.columns(actual)},key=str.casefold)
            except Exception:
                pass
        return self._all_candidates

    def _word_prefix(self):
        text=self.textCursor().block().text()
        before=text[:self.textCursor().positionInBlock()]
        match=re.search(r'([A-Za-z_][\w]*|[\w]*)$',before)
        return match.group(0) if match else ''

    def request_completion(self, force=False):
        prefix=self._word_prefix()
        if not force and len(prefix)<2:
            self.completer.popup().hide()
            return
        matches=self._completion_candidates(prefix)
        if not matches:
            self.completer.popup().hide()
            return
        self._completion_model.setStringList(matches)
        self.completer.setCompletionPrefix(prefix)
        if self.completer.completionCount()==0:
            self.completer.popup().hide()
            return
        popup=self.completer.popup()
        rect=self.cursorRect()
        rect.setWidth(max(240,popup.sizeHintForColumn(0)+popup.verticalScrollBar().sizeHint().width()+20))
        self.completer.complete(rect)

    def insert_completion(self, selected):
        if not selected:return
        cursor=self.textCursor()
        prefix=self._word_prefix()
        if prefix:
            cursor.movePosition(QTextCursor.MoveOperation.Left,
                                QTextCursor.MoveMode.KeepAnchor,len(prefix))
        cursor.insertText(selected)
        self.setTextCursor(cursor)
        self.completer.popup().hide()

    def keyPressEvent(self,event):
        key=event.key()
        ctrl=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if ctrl and key==Qt.Key.Key_Space:
            self.refresh_completion_source()
            self.request_completion(force=True)
            event.accept()
            return
        popup=self.completer.popup()
        if popup.isVisible():
            if key in (Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Tab):
                item=popup.currentIndex().data()
                if item:self.insert_completion(str(item))
                else:popup.hide()
                event.accept()
                return
            if key==Qt.Key.Key_Escape:
                popup.hide()
                event.accept()
                return
        super().keyPressEvent(event)
        if len(event.text())==1 and (event.text().isalnum() or event.text() in ('_','.')) and not ctrl:
            self.request_completion(force=event.text()=='.')
        elif key in (Qt.Key.Key_Space,Qt.Key.Key_Backspace):
            popup.hide()

    @property
    def font_point_size(self):
        return self._font_point_size

    def set_zoom(self, size):
        size=max(self.MIN_FONT,min(self.MAX_FONT,int(size)))
        if size==self._font_point_size:return
        self._font_point_size=size
        font=self.font()
        font.setPointSize(size)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ')*4)
        self.update_line_width()
        self.gutter.update()
        if self.on_zoom_changed:self.on_zoom_changed(size)

    def zoom_in_text(self):self.set_zoom(self._font_point_size+1)
    def zoom_out_text(self):self.set_zoom(self._font_point_size-1)
    def zoom_reset_text(self):self.set_zoom(self.DEFAULT_FONT)

    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle=event.angleDelta().y()
            if angle:
                self.set_zoom(self._font_point_size+(1 if angle>0 else -1))
            event.accept()
            return
        super().wheelEvent(event)

    def set_theme(self,theme):
        self.theme=theme
        self.highlighter.set_theme(theme)
        self.highlight_current_line()
        self.gutter.update()
    def line_width(self):
        digits=len(str(max(1,self.blockCount())))
        return 14+self.fontMetrics().horizontalAdvance('9')*digits
    def update_line_width(self,*args):
        self.setViewportMargins(self.line_width(),0,0,0)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        r=self.contentsRect()
        self.gutter.setGeometry(QRect(r.left(),r.top(),self.line_width(),r.height()))
    def update_gutter(self,rect,dy):
        if dy:self.gutter.scroll(0,dy)
        else:self.gutter.update(0,rect.y(),self.gutter.width(),rect.height())
        if rect.contains(self.viewport().rect()):self.update_line_width()
    def paint_lines(self,event):
        p=palette(self.theme)
        painter=QPainter(self.gutter)
        painter.fillRect(event.rect(),QColor(p['panel']))
        block=self.firstVisibleBlock()
        number=block.blockNumber()
        top=round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom=top+round(self.blockBoundingRect(block).height())
        while block.isValid() and top<=event.rect().bottom():
            if block.isVisible() and bottom>=event.rect().top():
                painter.setPen(QColor(p['muted']))
                painter.drawText(0,top,self.gutter.width()-7,self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight,str(number+1))
            block=block.next()
            top=bottom
            bottom=top+round(self.blockBoundingRect(block).height())
            number+=1
    def highlight_current_line(self):
        if self.isReadOnly():return
        extra=QTextEdit.ExtraSelection()
        p=palette(self.theme)
        extra.format.setBackground(QColor(p['secondary']))
        extra.format.setProperty(QTextFormat.Property.FullWidthSelection,True)
        extra.cursor=self.textCursor()
        extra.cursor.clearSelection()
        self.setExtraSelections([extra])

class TableNode(QGraphicsRectItem):
    WIDTH = 254
    def __init__(self, db: LabDatabase, name: str, colors, on_move):
        self.db=db
        self.name=name
        self.colors=colors
        self.on_move=on_move
        cols=db.columns(name)
        height=51+min(len(cols),18)*25+14
        super().__init__(0,0,self.WIDTH,height)
        self.setBrush(QBrush(QColor(colors['surface'])))
        self.setPen(QPen(QColor(colors['line']),1.5))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,True)
        self.setZValue(10)
        self._column_tips=[]
        self._close_tip=None
        self.setToolTip(name)
        header=QGraphicsRectItem(0,0,self.WIDTH,45,self)
        header.setBrush(QBrush(QColor(colors['secondary'])))
        header.setPen(QPen(QColor(colors['line']),0.6))
        ht=QGraphicsSimpleTextItem('▦  '+name,self)
        ht.setBrush(QBrush(QColor(colors['accent'])))
        ht.setFont(QFont('Segoe UI' if sys.platform=='win32' else ('Arial' if sys.platform=='darwin' else 'DejaVu Sans'),10,QFont.Weight.Bold))
        ht.setPos(12,12)
        closemark=QGraphicsSimpleTextItem('×',self)
        closemark.setBrush(QBrush(QColor(colors['muted'])))
        closemark.setFont(QFont('Segoe UI' if sys.platform=='win32' else ('Arial' if sys.platform=='darwin' else 'DejaVu Sans'),14,QFont.Weight.Bold))
        closemark.setPos(self.WIDTH-28,7)
        self._close_tip=closemark
        fkcols={fk['from'].lower() for fk in db.foreign_keys(name)}
        for i,c in enumerate(cols[:18]):
            tag=('PK' if c['pk'] else '')
            tag+=(' / FK' if c['name'].lower() in fkcols else '')
            tag+=(' / AI' if is_ai(db, name,c['name']) else '')
            col_text=QGraphicsSimpleTextItem(f"{'◆' if c['pk'] else '◇'}  {c['name']}      {db.logical_type(name,c['name'])}" ,self)
            col_text.setFont(QFont('Segoe UI' if sys.platform=='win32' else ('Arial' if sys.platform=='darwin' else 'DejaVu Sans'),9))
            col_text.setBrush(QBrush(QColor(colors['text'])))
            col_text.setPos(12,53+25*i)
            self._column_tips.append((col_text,c['name']))
            if tag:
                marker=QGraphicsSimpleTextItem(tag,self)
                marker.setBrush(QBrush(QColor(colors['accent'])))
                marker.setFont(QFont('Segoe UI' if sys.platform=='win32' else ('Arial' if sys.platform=='darwin' else 'DejaVu Sans'),7,QFont.Weight.Bold))
                marker.setPos(170,53+25*i)
        if len(cols)>18:
            rest=QGraphicsSimpleTextItem(f'+ {len(cols)-18} more...',self)
            rest.setBrush(QBrush(QColor(colors['muted'])))
            rest.setPos(12,height-18)
    def set_language(self,lang):
        self.setToolTip(self.name+'  |  '+ui('Drag a column onto another column to connect fields. Drag header to move. Click × to hide.',lang))
        if self._close_tip:
            self._close_tip.setToolTip(ui('Close table in diagram (no database changes)',lang))
        for item,column in self._column_tips:
            item.setToolTip(f'{self.name}.{column} ({self.db.logical_type(self.name,column)})  |  '+ui('Drag to another field',lang))

    def column_at(self, scene_point):
        local=self.mapFromScene(scene_point)
        row=int((local.y()-50)//25)
        columns=self.db.columns(self.name)
        if 0<=row<min(18,len(columns)) and 50<=local.y()<50+25*min(18,len(columns)):
            return columns[row]['name']
        return None
    def column_y(self,name):
        columns=self.db.columns(self.name)
        for i,c in enumerate(columns[:18]):
            if c['name'].casefold()==(name or '').casefold():return 64+25*i
        return self.rect().height()/2
    def close_hit(self,scene_point):
        point=self.mapFromScene(scene_point)
        return 0<=point.y()<=43 and self.WIDTH-37<=point.x()<=self.WIDTH

    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            self.on_move()
        return super().itemChange(change,value)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        try: self.db.save_position(self.name, int(self.pos().x()),int(self.pos().y()))
        except Exception: pass

def is_ai(db,table,column):
    from model_ext import is_identity
    return is_identity(db,table,column)

class ClickableRelationshipPath(QGraphicsPathItem):
    """Generous mouse hit area without an artificially thick visible line."""
    def boundingRect(self):
        return self.shape().boundingRect()
    def shape(self):
        stroker=QPainterPathStroker()
        stroker.setWidth(16.0)
        return stroker.createStroke(self.path())

class Edge:
    """Physical FK connection or a dashed conceptual N:M annotation."""
    def __init__(self,scene,parent,child,kind,fk,colors,semantic=False,parent_field=None,child_field=None, link=None):
        self.link=dict(link or {})
        self.colors=colors
        self.selected=False
        self.parent,self.child=parent,child
        self.kind,self.fk=kind,fk
        self.parent_field=parent_field
        self.child_field=child_field
        self.semantic=semantic
        self.path=ClickableRelationshipPath()
        color=QColor(colors['muted'] if semantic else colors['accent'])
        pen=QPen(color,1.8 if semantic else 2.2)
        if semantic:pen.setStyle(Qt.PenStyle.DashLine)
        self.path.setPen(pen)
        self.path.setZValue(0)
        scene.addItem(self.path)
        self.markers=QGraphicsPathItem()
        self.markers.setPen(QPen(color,1.7))
        self.markers.setZValue(1)
        scene.addItem(self.markers)
        prefix='N:M' if semantic else ('SELF  1:N' if kind=='SELF' else kind)
        self.label=QGraphicsSimpleTextItem(prefix+'  •  '+fk)
        self.label.setFont(QFont('Segoe UI' if sys.platform=='win32' else ('Arial' if sys.platform=='darwin' else 'DejaVu Sans'),8,QFont.Weight.Bold))
        self.label.setBrush(QBrush(color))
        self.label.setZValue(2)
        scene.addItem(self.label)
        self.one=QGraphicsSimpleTextItem('N' if semantic else '1')
        self.many=QGraphicsSimpleTextItem('M' if semantic else ('1' if kind=='1:1' else 'N'))
        for item in (self.one,self.many):
            item.setFont(QFont('Segoe UI' if sys.platform=='win32' else ('Arial' if sys.platform=='darwin' else 'DejaVu Sans'),9,QFont.Weight.Bold))
            item.setBrush(QBrush(color))
            item.setZValue(3)
            scene.addItem(item)
        self.parts=(self.path,self.markers,self.label,self.one,self.many)
        self.set_selected(False)
        tip=f'{kind}: {parent.name}.{parent_field or "PK"} → {child.name}.{child_field or fk}'
        if semantic: tip=f'N:M via {self.link.get("bridge", "junction")} (two real foreign keys)'
        self._description=tip
        self.set_language('en')
        self.update()

    def set_language(self,lang):
        for item in self.parts:
            item.setToolTip(self._description+'\n'+ui('Click to select; right-click to remove relationship.',lang))

    def set_selected(self,active):
        self.selected=bool(active)
        color=QColor('#f7b44c' if active else (self.colors['muted'] if self.semantic else self.colors['accent']))
        line=QPen(color,3.5 if active else (1.8 if self.semantic else 2.2))
        if self.semantic:line.setStyle(Qt.PenStyle.DashLine)
        self.path.setPen(line)
        self.markers.setPen(QPen(color,2.4 if active else 1.7))
        for label in (self.label,self.one,self.many):label.setBrush(QBrush(color))

    def update(self):
        if not self.parent.scene() or not self.child.scene():return
        a=self.parent.sceneBoundingRect();b=self.child.sceneBoundingRect()
        path=QPainterPath()
        marks=QPainterPath()
        def card(x,y,side,many):
            # Cardinality bars/crow's-foot forks, drawn outside the table border.
            xx=x+side*9
            if many:
                marks.moveTo(x,y);marks.lineTo(xx+side*9,y-9)
                marks.moveTo(x,y);marks.lineTo(xx+side*9,y+9)
                marks.moveTo(x,y);marks.lineTo(xx+side*9,y)
            else:
                marks.moveTo(xx,y-10);marks.lineTo(xx,y+10)
        if self.parent is self.child:
            ax=a.right()-35; ay=a.top()+32
            bx=a.right()-105; by=a.top()+9
            path.moveTo(ax,ay)
            path.cubicTo(a.right()+105,a.top()-108,a.left()+65,a.top()-115,bx,by)
            self.label.setPos(a.right()+4,a.top()-74)
            self.one.setPos(ax+5,ay+8)
            self.many.setPos(bx-24,by-16)
            card(ax,ay,1,False);card(bx,by,-1,True)
        else:
            rtl=a.center().x()>b.center().x()
            ax=a.left() if rtl else a.right()
            bx=b.right() if rtl else b.left()
            ay=a.top()+self.parent.column_y(self.parent_field)
            by=b.top()+self.child.column_y(self.child_field)
            midway=(ax+bx)/2
            path.moveTo(ax,ay)
            path.cubicTo(midway,ay,midway,by,bx,by)
            self.label.setPos(midway-self.label.boundingRect().width()/2,(ay+by)/2-(38 if self.semantic else 22))
            self.one.setPos(ax-18 if rtl else ax+4,ay-22)
            self.many.setPos(bx+3 if rtl else bx-18,by-22)
            card(ax,ay,-1 if rtl else 1,self.semantic)
            card(bx,by,1 if rtl else -1,self.semantic or self.kind!='1:1')
        self.path.setPath(path)
        self.markers.setPath(marks)


class Diagram(QGraphicsView):
    """Mouse-driven diagram: double-click to Design, drag a link, right-click for actions."""
    def __init__(self,theme='dark',parent=None):
        super().__init__(parent)
        self.theme=theme
        self.language='en'
        self.db=None
        self.on_design=None
        self.on_new_table=None
        self.on_connect=None
        self.on_field_connect=None
        self.on_delete_relationship=None
        self.on_select_relationship=None
        self.on_manual_cancel=None
        self.on_manual_activate=None
        self.on_link_progress=None
        self.hidden_tables=set()
        self.selected_edge=None
        self.manual_click_mode=False
        self.click_anchor=None
        self.connect_mode=False
        self.link_source=None
        self.link_source_field=None
        self.rubber=None
        self.gscene=QGraphicsScene(self)
        self.setScene(self.gscene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._panning=False
        self._last_pan=None
        self.on_zoom_changed=None
        # The auto-fit scale may be far below 20% for large diagrams.
        # Do not disable zoom-in at that scale: users must always be able to
        # return from an overview to readable fields.
        self._zoom_min=0.001
        self._zoom_max=8.0
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.edges=[];self.nodes={}
        self.set_language('en')
    def set_language(self,lang):
        self.language = lang if lang in ('en','fa') else 'en'
        self.setToolTip(ui('Drag a field onto another field, or choose Draw Link to click the two fields. Click any existing line to select or delete it.',self.language))
        for node in self.nodes.values():
            node.set_language(self.language)
        for edge in self.edges:
            edge.set_language(self.language)

    def set_actions(self,on_design=None,on_new_table=None,on_connect=None,on_field_connect=None,
                    on_delete_relationship=None,on_select_relationship=None):
        self.on_design=on_design;self.on_new_table=on_new_table;self.on_connect=on_connect
        self.on_field_connect=on_field_connect
        self.on_delete_relationship=on_delete_relationship
        self.on_select_relationship=on_select_relationship
    def edge_at(self,pos):
        # Ignore the temporary link preview, which tracks the mouse and would
        # otherwise intercept the second click of a two-click relationship.
        for clicked in self.items(pos):
            if clicked is self.rubber:
                continue
            parent=clicked
            while parent is not None:
                if isinstance(parent,TableNode):
                    return None  # table fields take priority over edges
                parent=parent.parentItem()
            edge=next((e for e in self.edges if clicked in e.parts),None)
            if edge:
                return edge
        return None
    def select_edge(self,edge):
        if edge is not None and edge not in self.edges:edge=None
        for candidate in self.edges:candidate.set_selected(candidate is edge)
        self.selected_edge=edge
        if self.on_select_relationship:
            self.on_select_relationship(edge.link if edge else None)
    def delete_selected_edge(self):
        if self.selected_edge and self.on_delete_relationship:
            self.on_delete_relationship(dict(self.selected_edge.link))
    def start_manual_drawing(self,active=True):
        self.manual_click_mode=bool(active)
        self.click_anchor=None
        if self.rubber:
            self.gscene.removeItem(self.rubber);self.rubber=None
        if active:self.start_connect(False)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor)
        if active and self.on_manual_activate:self.on_manual_activate()
        if self.on_link_progress:
            message=('Step 1/2: click the first field (parent PK or child FK).' if active else
                     'Tip: select Draw Link, then click two fields to create a relationship.')
            self.on_link_progress(ui(message,self.language))
    def _start_preview(self,node,field):
        self.link_source=node
        self.link_source_field=field
        self.rubber=QGraphicsPathItem()
        self.rubber.setPen(QPen(QColor(palette(self.theme)['accent']),2,Qt.PenStyle.DashLine))
        self.rubber.setZValue(5)
        self.gscene.addItem(self.rubber)
    def hide_table(self,name):
        """Hide from this diagram only; never DROP the actual database table."""
        self.hidden_tables.add(name)
        self.rebuild()
    def show_table(self,name):
        self.hidden_tables.discard(name)
        self.rebuild()
    def show_all_tables(self):
        self.hidden_tables.clear()
        self.rebuild()
    def start_connect(self,active=True):
        self.connect_mode=bool(active)
        self.link_source=None
        self.link_source_field=None
        if self.rubber:
            self.gscene.removeItem(self.rubber);self.rubber=None
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if (self.connect_mode or self.manual_click_mode) else Qt.CursorShape.ArrowCursor)
    def node_at(self,pos):
        # QGraphicsView.itemAt() returns the topmost paint item. During
        # connection drawing this may be the moving preview line, not the
        # underlying destination column, so search all stacked scene items.
        for top in self.items(pos):
            if top is self.rubber:
                continue
            item=top
            while item is not None and not isinstance(item,TableNode):
                item=item.parentItem()
            if item is not None:
                return item
        return None
    def contextMenuEvent(self,event):
        if not self.db:return super().contextMenuEvent(event)
        edge=self.edge_at(event.pos())
        if edge:
            self.select_edge(edge)
            menu=QMenu(self)
            menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.language=='fa' else Qt.LayoutDirection.LeftToRight)
            details=edge.link
            menu.addAction(ui('Relationship: ',self.language)+details.get('kind','FK')).setEnabled(False)
            if self.on_delete_relationship:
                name=ui('Delete N:M relationship (both foreign keys)…' if details.get('semantic') else 'Delete Relationship…',self.language)
                menu.addAction(name,lambda d=dict(details):self.on_delete_relationship(d))
            menu.exec(event.globalPos());event.accept();return
        node=self.node_at(event.pos())
        menu=QMenu(self)
        menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.language=='fa' else Qt.LayoutDirection.LeftToRight)
        if node:
            menu.addAction(ui('×  Close table in diagram (hide only)',self.language),lambda n=node.name:self.hide_table(n))
            owner=self.window()
            if callable(getattr(owner,'drop_column_ui',None)):
                menu.addAction(ui('Drop Column…',self.language),lambda n=node.name:owner.drop_column_ui(n))
            if callable(getattr(owner,'drop_table_ui',None)):
                menu.addAction(ui('Drop Table…',self.language),lambda n=node.name:owner.drop_table_ui(n))
            if self.on_design:menu.addAction(ui('Design Table  ✎',self.language),lambda n=node.name:self.on_design(n))
            if self.on_connect:
                menu.addAction(ui('New Relationship from {table}…',self.language).format(table=node.name),lambda n=node.name:self.on_connect(n,None))
                menu.addAction(ui('Self-referencing relationship…',self.language),lambda n=node.name:self.on_connect(n,n))
            menu.addSeparator()
        hidden=sorted(self.hidden_tables & set(self.db.tables()))
        if hidden:
            restore=menu.addMenu(ui('Reopen hidden table…',self.language))
            for name in hidden:
                restore.addAction(name,lambda n=name:self.show_table(n))
            menu.addAction(ui('Show all hidden tables',self.language),self.show_all_tables)
            menu.addSeparator()
        if self.on_new_table:menu.addAction(ui('New Table…',self.language),self.on_new_table)
        if self.on_connect:menu.addAction(ui('Relationship Wizard…',self.language),lambda:self.on_connect(None,None))
        menu.addAction(ui('Draw Link (click parent PK, then child FK)',self.language),lambda:self.start_manual_drawing(True))
        if self.connect_mode:menu.addAction(ui('Cancel link mode',self.language),lambda:self.start_connect(False))
        menu.exec(event.globalPos())
        event.accept()
    def mouseDoubleClickEvent(self,event):
        if self.edge_at(event.pos()):
            self.select_edge(self.edge_at(event.pos()));event.accept();return
        node=self.node_at(event.pos())
        if node and self.on_design:
            # A second click may have begun a field drag; clear that temporary line.
            self.start_connect(False)
            self.on_design(node.name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.MiddleButton:
            self._panning=True
            self._last_pan=event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            edge=self.edge_at(event.pos())
            if edge:
                self.setFocus()
                self.select_edge(edge);event.accept();return
            if self.selected_edge:self.select_edge(None)
            if self.manual_click_mode:
                node=self.node_at(event.pos())
                field=node.column_at(self.mapToScene(event.pos())) if node else None
                if node and field:
                    if self.click_anchor is None:
                        self.click_anchor=(node.name,field)
                        self._start_preview(node,field)
                        if self.on_link_progress:
                            self.on_link_progress(ui('Step 2/2: selected {field}. Click the target field (another table or the same table for a self-reference).',self.language).format(field=f'{node.name}.{field}'))
                    else:
                        src,src_field=self.click_anchor
                        self.click_anchor=None
                        if self.rubber:self.gscene.removeItem(self.rubber);self.rubber=None
                        self.link_source=None;self.link_source_field=None
                        if (src,src_field)!=(node.name,field) and self.on_field_connect:
                            self.on_field_connect(src,src_field,node.name,field)
                            self.start_manual_drawing(False)
                            if self.on_manual_cancel:self.on_manual_cancel()
                    event.accept();return
                event.accept();return
            node=self.node_at(event.pos())
            if node:
                point=self.mapToScene(event.pos())
                if node.close_hit(point):
                    self.hide_table(node.name)
                    event.accept();return
                field=node.column_at(point)
                # Row drag is always available. Header dragging still moves tables.
                if field and self.on_field_connect:
                    self._start_preview(node,field)
                    event.accept();return
                if self.connect_mode:
                    self._start_preview(node,None)
                    event.accept();return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._panning and self._last_pan is not None:
            now=event.position().toPoint()
            delta=now-self._last_pan
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y())
            self._last_pan=now
            event.accept();return
        if self.link_source and self.rubber:
            source=self.link_source
            x=source.sceneBoundingRect().center().x()
            y=(source.sceneBoundingRect().top()+source.column_y(self.link_source_field)
               if self.link_source_field else source.sceneBoundingRect().center().y())
            start=QPointF(x,y)
            end=self.mapToScene(event.pos())
            path=QPainterPath(start);path.lineTo(end)
            self.rubber.setPath(path)
            event.accept();return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.MiddleButton and self._panning:
            self._panning=False;self._last_pan=None
            self.viewport().setCursor(Qt.CursorShape.CrossCursor if (self.manual_click_mode or self.connect_mode) else Qt.CursorShape.ArrowCursor)
            event.accept();return
        if self.manual_click_mode:
            event.accept();return
        if self.link_source and event.button()==Qt.MouseButton.LeftButton:
            source=self.link_source
            source_field=self.link_source_field
            target=self.node_at(event.pos())
            target_field=target.column_at(self.mapToScene(event.pos())) if target else None
            self.link_source=None
            self.link_source_field=None
            if self.rubber:
                self.gscene.removeItem(self.rubber);self.rubber=None
            if source_field and target and target_field and self.on_field_connect:
                if (source.name,source_field)!=(target.name,target_field):
                    self.start_connect(False)
                    self.on_field_connect(source.name,source_field,target.name,target_field)
            elif not source_field and target and self.on_connect:
                self.start_connect(False)
                self.on_connect(source.name,target.name)
            event.accept();return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace) and self.selected_edge:
            self.delete_selected_edge();event.accept();return
        if event.key()==Qt.Key.Key_Escape:
            self.start_manual_drawing(False);self.start_connect(False)
            if self.on_manual_cancel:self.on_manual_cancel()
            self.select_edge(None);event.accept();return
        super().keyPressEvent(event)
    def set_db(self,db):
        if db is None or self.db is None or getattr(db,'path',None)!=getattr(self.db,'path',None):
            self.hidden_tables.clear()
        self.db=db;self.rebuild()
    def set_theme(self,theme):
        self.theme=theme;self.rebuild()
    def update_edges(self):
        for e in self.edges:e.update()
        if self.db and self.nodes:
            current=self.gscene.itemsBoundingRect()
            if not self.gscene.sceneRect().adjusted(1800,1800,-1800,-1800).contains(current):
                self.expand_canvas()
    def rebuild(self):
        self.start_connect(False)
        self.manual_click_mode=False
        if self.on_manual_cancel:self.on_manual_cancel()
        self.click_anchor=None
        self.link_source=None
        self.link_source_field=None
        self.rubber=None
        self.selected_edge=None
        self.gscene.clear()
        self.nodes={};self.edges=[]
        if self.db is None:return
        names=[n for n in self.db.tables() if n not in self.hidden_tables]
        old=self.db.positions();colors=palette(self.theme)
        for ix,name in enumerate(names):
            node=TableNode(self.db,name,colors,self.update_edges)
            node.set_language(self.language)
            self.gscene.addItem(node)
            x,y=old.get(name,((ix%3)*340,(ix//3)*305))
            node.setPos(x,y);self.nodes[name]=node
        for link in self.db.links():
            if link['parent'] in self.nodes and link['child'] in self.nodes:
                edge=Edge(self.gscene,self.nodes[link['parent']],self.nodes[link['child']],
                          link['kind'],link['fk'],colors,link.get('semantic',False),
                          link.get('parent_field'),link.get('child_field'),link=link)
                edge.set_language(self.language)
                self.edges.append(edge)
        self.expand_canvas()
        self.zoom_actual()
        # Avoid auto-shrinking all columns into tiny targets. Keep 100% scale
        # for accessible field-to-field dragging; user can explicitly Fit.
        if names:self.centerOn(self.nodes[names[0]])
    def expand_canvas(self):
        """Keep a generous navigable canvas around all nodes, including negative coords."""
        bounds=self.gscene.itemsBoundingRect()
        if bounds.isNull() or bounds.isEmpty():
            bounds=QRectF(-500,-500,1000,1000)
        # Substantial margins permit drag and pan far beyond the last table.
        self.gscene.setSceneRect(bounds.adjusted(-3500,-3500,3500,3500))

    def auto_layout(self):
        if not self.db:return {}
        positions=auto_layout(list(self.nodes),self.db.links())
        for name,(x,y) in positions.items():
            node=self.nodes.get(name)
            if node is not None:
                node.setPos(x,y)
                self.db.save_position(name,x,y)
        self.update_edges()
        self.expand_canvas()
        if self.nodes:self.fit_diagram()
        return positions

    def zoom_level(self):
        """Current view scale (1.0 = 100%, independent of scene dimensions)."""
        return self.transform().m11()

    def _emit_zoom(self):
        if self.on_zoom_changed:
            self.on_zoom_changed(self.zoom_level())

    def zoom_by(self, factor, *, anchor=None):
        """Incremental zoom, including after a very small Auto Layout fit.

        A fitted overview may be smaller than the normal zoom-out floor.
        Zooming *in* from that state must remain possible. Buttons zoom
        around the viewport center while Ctrl+wheel zooms at the pointer.
        """
        current=self.zoom_level()
        if current<=0 or factor<=0:
            return False
        if factor>1:
            if current>=self._zoom_max:
                return False
            target=min(current*factor,self._zoom_max)
        elif factor<1:
            if current<=self._zoom_min:
                return False
            target=max(current*factor,self._zoom_min)
        else:
            return False
        original=self.transformationAnchor()
        if anchor is not None:
            self.setTransformationAnchor(anchor)
        try:
            self.scale(target/current,target/current)
        finally:
            if anchor is not None:
                self.setTransformationAnchor(original)
        self._emit_zoom()
        return True

    def zoom_in(self):
        return self.zoom_by(1.25,anchor=QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def zoom_out(self):
        return self.zoom_by(1/1.25,anchor=QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def fit_diagram(self):
        if self.db and self.nodes:
            # Fit the actual tables, not the oversized scrollable workspace.
            bounds=self.gscene.itemsBoundingRect().adjusted(-110,-120,110,120)
            if not bounds.isEmpty():
                self.fitInView(bounds,Qt.AspectRatioMode.KeepAspectRatio)
                self._emit_zoom()

    def zoom_actual(self):
        self.resetTransform()
        self._emit_zoom()

    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps=event.angleDelta().y()/120
            if steps:
                # Keep existing zoom-under-mouse behavior for Ctrl+wheel.
                self.zoom_by(1.15**steps)
            event.accept()
        else:
            super().wheelEvent(event)
    def drawBackground(self,painter,rect):
        p=palette(self.theme)
        painter.fillRect(rect,QColor(p['bg']))
        painter.setPen(QPen(QColor(p['line']),0.4))
        grid=25
        startx=int(rect.left()//grid)*grid;starty=int(rect.top()//grid)*grid
        x=startx
        while x<rect.right():
            painter.drawLine(x,int(rect.top()),x,int(rect.bottom()));x+=grid
        y=starty
        while y<rect.bottom():
            painter.drawLine(int(rect.left()),y,int(rect.right()),y);y+=grid
    def export_png(self,path):
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QRectF
        bounds=self.gscene.itemsBoundingRect().adjusted(-35,-35,35,35)
        w=max(800,int(bounds.width()*2));h=max(500,int(bounds.height()*2))
        image=QImage(w,h,QImage.Format.Format_ARGB32)
        image.fill(QColor(palette(self.theme)['bg']))
        painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        self.gscene.render(painter,QRectF(0,0,w,h),bounds)
        painter.end()
        return image.save(path,'PNG')

class WelcomePanel(QWidget):
    """Welcome with room for every line and proper scrolling at small sizes."""
    def __init__(self, lang, new_callback, open_callback, report_callback=None, parent=None):
        super().__init__(parent)
        self.lang=lang
        is_fa=lang=='fa'
        direction=Qt.LayoutDirection.RightToLeft if is_fa else Qt.LayoutDirection.LeftToRight
        scroll=QScrollArea(self)
        scroll.setObjectName('welcomeScroll')
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer=QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(scroll)
        container=QWidget()
        container.setObjectName('welcomeContainer')
        scroll.setWidget(container)
        container.setMinimumWidth(0)
        surface=QVBoxLayout(container)
        surface.setContentsMargins(18,22,18,22)
        surface.setSpacing(8)
        # SetMinimumSize on the scroll content inherits an oversized minimum
        # width from wrapped child labels on some Windows DPI/font setups.
        # Keep the content width flexible and enforce only vertical scrolling.
        surface.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        surface.addStretch(1)
        card=QFrame()
        card.setObjectName('welcomeCard')
        self._welcome_card=card
        card.setMinimumWidth(0)
        card.setMaximumWidth(448)
        card.setMinimumHeight(392)
        # Let Qt calculate the actual height of every wrapped label.
        # Never cap the card height: credits and a long Persian title must not be clipped.
        card.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)
        card_layout=QVBoxLayout(card)
        card_layout.setContentsMargins(19,16,19,16)
        card_layout.setSpacing(7)
        # Do not let Qt change the frame's minimumWidth to the unwrapped
        # sizeHint (708 px on Qt 6.12 / Windows in the reported regression).
        # A layout-imposed minimum can silently defeat setFixedWidth(448).
        card_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        eyebrow=QLabel('شبیه‌ساز SQL Server | محیط طراحی پایگاه داده' if is_fa else 'SQL SERVER SIMULATOR  |  DATABASE DESIGN STUDIO')
        eyebrow.setProperty('role','eyebrow')
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eyebrow.setWordWrap(True)
        eyebrow.setMinimumHeight(22)
        eyebrow.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        card_layout.addWidget(eyebrow)
        title_text=tr('welcome_title',lang)
        title=QLabel(title_text)
        title.setObjectName('welcomeTitle')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        title.setLayoutDirection(direction)
        # Allow wrapping on narrower windows. A fixed one-line title forced the
        # scroll area's minimum width beyond the viewport on some DPI settings.
        title.setMinimumHeight(46)
        title.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        card_layout.addWidget(title)
        desc=QLabel(tr('welcome_desc',lang))
        desc.setObjectName('welcomeDescription')
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setLayoutDirection(direction)
        desc.setMinimumHeight(62)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        card_layout.addWidget(desc)
        separator=QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName('welcomeDivider')
        card_layout.addWidget(separator)
        buttons=QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        create=QPushButton(tr('new_project',lang))
        create.setMinimumHeight(36)
        create.setProperty('role','primary')
        create.clicked.connect(new_callback)
        buttons.addWidget(create)
        openb=QPushButton(tr('open_project',lang))
        openb.setMinimumHeight(36)
        openb.clicked.connect(open_callback)
        buttons.addWidget(openb)
        buttons.addStretch(1)
        card_layout.addLayout(buttons)
        # Compact display captions; full roles remain in About and translations.
        credits=((f'طراحی و توسعه: علی صیادی', f'آزمون و ارزیابی: {QA_LEAD_FA}')
                 if is_fa else (f'Developed by {APP_AUTHOR}', f'Testing & QA: {QA_LEAD_EN}'))
        for credit in credits:
            author=QLabel(credit)
            author.setObjectName('welcomeAuthor')
            author.setAlignment(Qt.AlignmentFlag.AlignCenter)
            author.setLayoutDirection(direction)
            author.setWordWrap(True)
            author.setMinimumHeight(28)
            author.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
            card_layout.addWidget(author)
        notice=QLabel(tr('v_notice',lang))
        notice.setObjectName('welcomeNotice')
        notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notice.setLayoutDirection(direction)
        notice.setWordWrap(True)
        notice.setMinimumHeight(25)
        card_layout.addWidget(notice)
        if report_callback:
            bug=QPushButton('گزارش خطا از طریق Gmail' if is_fa else 'Report a bug via Gmail')
            bug.setObjectName('welcomeBugButton')
            bug.setFlat(True)
            bug.setMinimumHeight(28)
            bug.clicked.connect(report_callback)
            card_layout.addWidget(bug,alignment=Qt.AlignmentFlag.AlignCenter)
        surface.addWidget(card,alignment=Qt.AlignmentFlag.AlignHCenter)
        surface.addStretch(1)
        # Track the actual scroll viewport, not the outer WelcomePanel size;
        # Qt can resize the viewport after QWidget.resizeEvent has completed.
        self._welcome_container=container
        self._welcome_scroll=scroll
        self._fitting_welcome=False
        scroll.viewport().installEventFilter(self)
        self._fit_card_to_viewport()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_card_to_viewport()

    def eventFilter(self, watched, event):
        # A scrollbar appearing/disappearing changes the effective viewport
        # width. Refit after that change rather than guessing from self.width().
        if (hasattr(self,'_welcome_scroll')
                and watched is self._welcome_scroll.viewport()
                and event.type()==QEvent.Type.Resize):
            self._fit_card_to_viewport()
        return super().eventFilter(watched,event)

    def _fit_card_to_viewport(self):
        if (not hasattr(self,'_welcome_card')
                or getattr(self,'_fitting_welcome',False)):
            return
        self._fitting_welcome=True
        try:
            card=self._welcome_card
            viewport=self._welcome_scroll.viewport()
            # Reserve margins inside the scroll content. No horizontal bar:
            # text must wrap and the card must fit the visible viewport.
            width=min(448,max(220,viewport.width()-36))
            if card.minimumWidth()!=width or card.maximumWidth()!=width:
                card.setFixedWidth(width)
            layout=card.layout()
            layout.invalidate()
            layout.activate()
            required=max(layout.minimumSize().height(),layout.sizeHint().height())
            if layout.hasHeightForWidth():
                required=max(required,layout.heightForWidth(width))
            height=max(392,required)
            if card.minimumHeight()!=height or card.maximumHeight()!=height:
                card.setFixedHeight(height)
            # Vertical minimum only. Qt no longer propagates a 708 px
            # *horizontal* minimum into the scroll area's widget.
            minimum_content_height=height+44  # 22 px margins on both sides
            if self._welcome_container.minimumHeight()!=minimum_content_height:
                self._welcome_container.setMinimumHeight(minimum_content_height)
        finally:
            self._fitting_welcome=False
