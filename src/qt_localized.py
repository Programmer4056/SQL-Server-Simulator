"""Qt dialogs with Persian action buttons and localized common messages."""
from PySide6.QtWidgets import QMessageBox as _QMessageBox
from PySide6.QtCore import Qt
from locale_support import ui, runtime_message

def _language(parent):
    node=parent
    for _ in range(12):
        if node is None:break
        lang=getattr(node,'lang',None)
        if lang in ('fa','en'):return lang
        node=node.parent() if hasattr(node,'parent') else None
    return 'en'

class LocalizedMessageBox(_QMessageBox):
    @classmethod
    def _show(cls,kind,parent,title,message,buttons=None,default=None):
        lang=_language(parent)
        box=cls(parent)
        box.setIcon(kind)
        box.setWindowTitle(ui(title,lang))
        visible=runtime_message(str(message),lang)
        box.setText(visible)
        if lang=='fa' and visible != str(message):box.setDetailedText(str(message))
        if buttons is not None:box.setStandardButtons(buttons)
        else:box.setStandardButtons(cls.StandardButton.Ok)
        if default is not None:box.setDefaultButton(default)
        if lang=='fa':
            for std,label in ((cls.StandardButton.Ok,'باشه'),(cls.StandardButton.Yes,'بله'),
                              (cls.StandardButton.No,'خیر'),(cls.StandardButton.Cancel,'انصراف')):
                button=box.button(std)
                if button:button.setText(label)
            box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        return cls.StandardButton(box.exec())

    @classmethod
    def question(cls,parent,title,text,buttons=None,defaultButton=None):
        if buttons is None:buttons=cls.StandardButton.Yes|cls.StandardButton.No
        return cls._show(cls.Icon.Question,parent,title,text,buttons,defaultButton)

    @classmethod
    def warning(cls,parent,title,text,buttons=None,defaultButton=None):
        return cls._show(cls.Icon.Warning,parent,title,text,buttons,defaultButton)

    @classmethod
    def information(cls,parent,title,text,buttons=None,defaultButton=None):
        return cls._show(cls.Icon.Information,parent,title,text,buttons,defaultButton)

    @classmethod
    def critical(cls,parent,title,text,buttons=None,defaultButton=None):
        return cls._show(cls.Icon.Critical,parent,title,text,buttons,defaultButton)
