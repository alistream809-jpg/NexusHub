"""Minimal stand-in for PySide6 so GUI modules can be import- and construct-tested without Qt."""
import sys, types

class Chain:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return Chain()
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return Chain()
    def __iter__(self): return iter(())
    def __bool__(self): return True
    def __int__(self): return 0
    def __index__(self): return 0
    def __float__(self): return 0.0
    def __sub__(self, o): return 0
    def __rsub__(self, o): return 0
    def __add__(self, o): return 0
    def __ge__(self, o): return True
    def __le__(self, o): return True
    def __lt__(self, o): return False
    def __gt__(self, o): return False

class Meta(type):
    def __getattr__(cls, n):
        if n.startswith("__"): raise AttributeError(n)
        c = Meta(n, (Base,), {}); setattr(cls, n, c); return c

class Base(metaclass=Meta):
    def __init__(self, *a, **k): pass
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return Chain()
    def addItems(self, items): self._items = list(items)
    def addItem(self, text, data=None): self.__dict__.setdefault("_items", []).append(text)
    def currentText(self): return (self.__dict__.get("_items") or [""])[0]
    def text(self): return ""
    def isChecked(self): return False

class Sig(Chain):
    def __get__(self, obj, owner=None): return self

def module(name):
    m = types.ModuleType(name)
    def __getattr__(attr):
        if attr.startswith("__"): raise AttributeError(attr)
        if attr == "Signal": return Sig
        cls = Meta(attr, (Base,), {}); setattr(m, attr, cls); return cls
    m.__getattr__ = __getattr__
    return m

def install():
    for name in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"):
        sys.modules[name] = module(name)
