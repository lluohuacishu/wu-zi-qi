# -*- coding: utf-8 -*-
# Python ctypes 桥接层 —— 调用 C++ DLL (chessai.dll)
import ctypes
import os
import sys

C_NONE, C_BLACK, C_WHITE = 0, 1, 2

# —— 加载 DLL（兼容 PyInstaller onefile 打包）——
_base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
_dll_path = os.path.join(_base, 'chessai.dll')
_dll = ctypes.CDLL(_dll_path)

# —— 类型定义 ——
Board15 = (ctypes.c_int * 15) * 15

class EvalResult(ctypes.Structure):
    _fields_ = [
        ('score',       ctypes.c_int),
        ('result',      ctypes.c_int),
        ('stat_win',    ctypes.c_int),
        ('stat_lose',   ctypes.c_int),
        ('stat_flex4',  ctypes.c_int),
        ('stat_block4', ctypes.c_int),
        ('stat_flex3',  ctypes.c_int),
    ]

# —— 函数签名 ——
_dll.ai_init.argtypes = []
_dll.ai_init.restype  = None

_dll.ai_destroy.argtypes = []
_dll.ai_destroy.restype  = None

_dll.ai_get_action.argtypes = [Board15, ctypes.c_int, ctypes.c_int,
                                ctypes.POINTER(ctypes.c_int),
                                ctypes.POINTER(ctypes.c_int),
                                ctypes.POINTER(ctypes.c_int)]
_dll.ai_get_action.restype = None

_dll.ai_evaluate.argtypes = [Board15]
_dll.ai_evaluate.restype = EvalResult


def _py_to_c(board):
    """Python 15x15 list → ctypes Board15"""
    c = Board15()
    for i in range(15):
        for j in range(15):
            c[i][j] = board[i][j]
    return c

# —— 对外接口（与 Python 版 ChessAI 接口一致） ——
_dll.ai_init()

class ChessAI:
    def __init__(self):
        pass  # DLL 内部维护单例

    def get_action(self, board, depth=4, ai_color=C_WHITE):
        c_board = _py_to_c(board)
        r = ctypes.c_int(); c = ctypes.c_int(); s = ctypes.c_int()
        _dll.ai_get_action(c_board, depth, ai_color, ctypes.byref(r), ctypes.byref(c), ctypes.byref(s))
        return (r.value, c.value)

    def evaluate(self, board):
        c_board = _py_to_c(board)
        ev = _dll.ai_evaluate(c_board)
        return ev.score, ev.result, ev.stat_win, ev.stat_lose
