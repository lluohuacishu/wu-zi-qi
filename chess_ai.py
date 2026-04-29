# -*- coding: utf-8 -*-
# 五子棋 AI —— 严格参照 Gobang-ai-master C++ 源码逐行翻译
import math
import numpy as np
from numba import njit

# —— Numba JIT evaluate：把扫棋盘的四重循环编译为机器码 ——
WEIGHT = np.array([0, 1000000, -10000000, 50000, -100000, 400, -100000,
                   400, -8000, 20, -50, 20, -50, 1, -3, 1, -3], dtype=np.int32)

@njit
def _evaluate_numba(A, tt):
    """JIT 编译的 evaluate 核心：A(17×17 padded int8), tt(4×4×4×4×4×4 6D int32 查表)"""
    stat = np.zeros(17, dtype=np.int32)
    # 横向
    for i in range(1, 16):
        for j in range(12):
            t = tt[A[i, j], A[i, j + 1], A[i, j + 2],
                  A[i, j + 3], A[i, j + 4], A[i, j + 5]]
            stat[t] += 1
    # 竖向
    for j in range(1, 16):
        for i in range(12):
            t = tt[A[i, j], A[i + 1, j], A[i + 2, j],
                  A[i + 3, j], A[i + 4, j], A[i + 5, j]]
            stat[t] += 1
    # 左上→右下
    for i in range(12):
        for j in range(12):
            t = tt[A[i, j], A[i + 1, j + 1], A[i + 2, j + 2],
                  A[i + 3, j + 3], A[i + 4, j + 4], A[i + 5, j + 5]]
            stat[t] += 1
    # 右上→左下
    for i in range(12):
        for j in range(5, 17):
            t = tt[A[i, j], A[i + 1, j - 1], A[i + 2, j - 2],
                  A[i + 3, j - 3], A[i + 4, j - 4], A[i + 5, j - 5]]
            stat[t] += 1
    # 计算 score + 5 种关键 STAT
    score = np.int64(0)
    for i in range(1, 17):
        score += np.int64(stat[i]) * np.int64(WEIGHT[i])
    return (score, stat[WIN], stat[LOSE], stat[FLEX4],
            stat[BLOCK4], stat[FLEX3])

C_NONE = 0
C_BLACK = 1
C_WHITE = 2

RIGHT = 0
UP = 1
UPRIGHT = 2
UPLEFT = 3

# 棋型代号（与 C++ #define 一一对应）
OTHER = 0
WIN = 1       # 白连5
LOSE = 2      # 黑连5
FLEX4 = 3     # 白活4
flex4 = 4     # 黑活4
BLOCK4 = 5    # 白冲4
block4 = 6    # 黑冲4
FLEX3 = 7     # 白活3
flex3 = 8     # 黑活3
BLOCK3 = 9    # 白眠3
block3 = 10   # 黑眠3
FLEX2 = 11
flex2 = 12
BLOCK2 = 13
block2 = 14
FLEX1 = 15
flex1 = 16

R_BLACK = 0
R_WHITE = 1
R_DRAW = 2


class Evaluation:
    """对应 C++ struct EVALUATION"""
    def __init__(self):
        self.score = 0
        self.result = R_DRAW
        self.STAT = [0] * 17  # C++ int STAT[8]，Python 直接给 17 保安全


class Decision:
    """对应 C++ struct DECISION"""
    def __init__(self):
        self.pos = (0, 0)
        self.eval_score = 0


class ChessAI:
    def __init__(self):
        self.tuple6type = {}
        self._init_tuple6type()
        self.nodeNum = 0
        self.decision = Decision()
        # 把 dict 转为 numpy 6D 数组供 Numba 查表
        self._tt_np = np.zeros((4, 4, 4, 4, 4, 4), dtype=np.int32)
        for k, v in self.tuple6type.items():
            self._tt_np[k[0], k[1], k[2], k[3], k[4], k[5]] = v

    # ==================== 基础工具 ====================

    def _check_bound(self, x, y):
        return 0 <= x < 15 and 0 <= y < 15

    def _get_xy(self, row, col, dr, rel):
        if dr == RIGHT:
            return (row, col + rel)
        if dr == UP:
            return (row - rel, col)
        if dr == UPRIGHT:
            return (row - rel, col + rel)
        if dr == UPLEFT:
            return (row - rel, col - rel)
        return (row, col)

    def _copy_board(self, src):
        return [row[:] for row in src]

    def _reverse_board(self, src):
        """对应 C++ reverseBoard：黑白互换"""
        dst = [[C_NONE] * 15 for _ in range(15)]
        for i in range(15):
            for j in range(15):
                if src[i][j] == C_BLACK:
                    dst[i][j] = C_WHITE
                elif src[i][j] == C_WHITE:
                    dst[i][j] = C_BLACK
        return dst

    # ==================== init_tuple6type（与 C++ 完全一致）====================

    def _init_tuple6type(self):
        # 白连5
        self.tuple6type[(2, 2, 2, 2, 2, 2)] = WIN
        self.tuple6type[(2, 2, 2, 2, 2, 0)] = WIN
        self.tuple6type[(0, 2, 2, 2, 2, 2)] = WIN
        self.tuple6type[(2, 2, 2, 2, 2, 1)] = WIN
        self.tuple6type[(1, 2, 2, 2, 2, 2)] = WIN
        self.tuple6type[(3, 2, 2, 2, 2, 2)] = WIN
        self.tuple6type[(2, 2, 2, 2, 2, 3)] = WIN
        # 黑连5
        self.tuple6type[(1, 1, 1, 1, 1, 1)] = LOSE
        self.tuple6type[(1, 1, 1, 1, 1, 0)] = LOSE
        self.tuple6type[(0, 1, 1, 1, 1, 1)] = LOSE
        self.tuple6type[(1, 1, 1, 1, 1, 2)] = LOSE
        self.tuple6type[(2, 1, 1, 1, 1, 1)] = LOSE
        self.tuple6type[(3, 1, 1, 1, 1, 1)] = LOSE
        self.tuple6type[(1, 1, 1, 1, 1, 3)] = LOSE
        # 白活4 / 黑活4
        self.tuple6type[(0, 2, 2, 2, 2, 0)] = FLEX4
        self.tuple6type[(0, 1, 1, 1, 1, 0)] = flex4
        # 白活3
        for t in [(0, 2, 2, 2, 0, 0), (0, 0, 2, 2, 2, 0),
                  (0, 2, 0, 2, 2, 0), (0, 2, 2, 0, 2, 0)]:
            self.tuple6type[t] = FLEX3
        # 黑活3
        for t in [(0, 1, 1, 1, 0, 0), (0, 0, 1, 1, 1, 0),
                  (0, 1, 0, 1, 1, 0), (0, 1, 1, 0, 1, 0)]:
            self.tuple6type[t] = flex3
        # 白活2
        for t in [(0, 2, 2, 0, 0, 0), (0, 2, 0, 2, 0, 0), (0, 2, 0, 0, 2, 0),
                  (0, 0, 2, 2, 0, 0), (0, 0, 2, 0, 2, 0), (0, 0, 0, 2, 2, 0)]:
            self.tuple6type[t] = FLEX2
        # 黑活2
        for t in [(0, 1, 1, 0, 0, 0), (0, 1, 0, 1, 0, 0), (0, 1, 0, 0, 1, 0),
                  (0, 0, 1, 1, 0, 0), (0, 0, 1, 0, 1, 0), (0, 0, 0, 1, 1, 0)]:
            self.tuple6type[t] = flex2
        # 白活1
        for t in [(0, 2, 0, 0, 0, 0), (0, 0, 2, 0, 0, 0),
                  (0, 0, 0, 2, 0, 0), (0, 0, 0, 0, 2, 0)]:
            self.tuple6type[t] = FLEX1
        # 黑活1
        for t in [(0, 1, 0, 0, 0, 0), (0, 0, 1, 0, 0, 0),
                  (0, 0, 0, 1, 0, 0), (0, 0, 0, 0, 1, 0)]:
            self.tuple6type[t] = flex1

        # ---------- 暴力枚举（与 C++ 完全一致，==0 检查防止覆盖）----------
        for p1 in range(4):
            for p2 in range(3):
                for p3 in range(3):
                    for p4 in range(3):
                        for p5 in range(3):
                            for p6 in range(4):
                                t = (p1, p2, p3, p4, p5, p6)
                                if t in self.tuple6type:
                                    continue

                                # 统计黑白个数（与 C++ 逐个 if 赋值完全等价）
                                x = (1 if p1 == 1 else (1 if p1 == 2 else 0))
                                y = (1 if p1 == 2 else 0)
                                ix = 0
                                iy = 0
                                for p in (p2, p3, p4, p5):
                                    if p == 1: x += 1; ix += 1
                                    elif p == 2: y += 1; iy += 1
                                if p6 == 1: ix += 1
                                elif p6 == 2: iy += 1

                                if p1 == 3 or p6 == 3:
                                    if p1 == 3 and p6 != 3:  # 左边界
                                        if ix == 0 and iy == 4 and t not in self.tuple6type:
                                            self.tuple6type[t] = BLOCK4
                                        elif ix == 4 and iy == 0 and t not in self.tuple6type:
                                            self.tuple6type[t] = block4
                                        elif ix == 0 and iy == 3 and t not in self.tuple6type:
                                            self.tuple6type[t] = BLOCK3
                                        elif ix == 3 and iy == 0 and t not in self.tuple6type:
                                            self.tuple6type[t] = block3
                                        elif ix == 0 and iy == 2 and t not in self.tuple6type:
                                            self.tuple6type[t] = BLOCK2
                                        elif ix == 2 and iy == 0 and t not in self.tuple6type:
                                            self.tuple6type[t] = block2
                                    elif p6 == 3 and p1 != 3:  # 右边界
                                        if x == 0 and y == 4 and t not in self.tuple6type:
                                            self.tuple6type[t] = BLOCK4
                                        elif x == 4 and y == 0 and t not in self.tuple6type:
                                            self.tuple6type[t] = block4
                                        elif x == 3 and y == 0 and t not in self.tuple6type:
                                            self.tuple6type[t] = BLOCK3
                                        elif x == 0 and y == 3 and t not in self.tuple6type:
                                            self.tuple6type[t] = block3
                                        elif x == 2 and y == 0 and t not in self.tuple6type:
                                            self.tuple6type[t] = BLOCK2
                                        elif x == 0 and y == 2 and t not in self.tuple6type:
                                            self.tuple6type[t] = block2
                                else:  # 无边界
                                    if (x == 0 and y == 4 or ix == 0 and iy == 4) and t not in self.tuple6type:
                                        self.tuple6type[t] = BLOCK4
                                    elif (x == 4 and y == 0 or ix == 4 and iy == 0) and t not in self.tuple6type:
                                        self.tuple6type[t] = block4
                                    elif (x == 0 and y == 3 or ix == 0 and iy == 3) and t not in self.tuple6type:
                                        self.tuple6type[t] = BLOCK3
                                    elif (x == 3 and y == 0 or ix == 3 and iy == 0) and t not in self.tuple6type:
                                        self.tuple6type[t] = block3
                                    elif (x == 0 and y == 2 or ix == 0 and iy == 2) and t not in self.tuple6type:
                                        self.tuple6type[t] = BLOCK2
                                    elif (x == 2 and y == 0 or ix == 2 and iy == 0) and t not in self.tuple6type:
                                        self.tuple6type[t] = block2

    # ==================== evaluate（C++: chessAi::evaluate）====================

    def evaluate(self, board):
        """Numba JIT 加速版，结果与 C++ evaluate 完全一致"""
        A = np.full((17, 17), 3, dtype=np.int32)
        A[1:16, 1:16] = np.array(board, dtype=np.int32)  # numpy 切片一次完成

        score, w, l, f4, b4, f3 = _evaluate_numba(A, self._tt_np)

        eval_res = Evaluation()
        eval_res.score = int(score)
        eval_res.STAT[WIN] = int(w);   eval_res.STAT[LOSE] = int(l)
        eval_res.STAT[FLEX4] = int(f4); eval_res.STAT[BLOCK4] = int(b4)
        eval_res.STAT[FLEX3] = int(f3)
        if w > 0:   eval_res.result = R_WHITE
        elif l > 0: eval_res.result = R_BLACK
        return eval_res

    # ==================== 贪心部分 ====================

    def _tuple_score_greedy(self, black, white, c_me):
        if c_me == C_BLACK and black == 5: return 9999999
        if c_me == C_WHITE and white == 5: return 9999999
        if black == 0 and white == 0: return 7
        if black >= 1 and white >= 1: return 0
        if c_me == C_BLACK:
            if black == 1 and white == 0: return 35
            if black == 2 and white == 0: return 800
            if black == 3 and white == 0: return 15000
            if black == 4 and white == 0: return 800000
            if black == 0 and white == 1: return 15
            if black == 0 and white == 2: return 400
            if black == 0 and white == 3: return 1800
            return 100000
        else:
            if black == 1 and white == 0: return 15
            if black == 2 and white == 0: return 400
            if black == 3 and white == 0: return 1800
            if black == 4 and white == 0: return 100000
            if black == 0 and white == 1: return 35
            if black == 0 and white == 2: return 800
            if black == 0 and white == 3: return 15000
            return 800000

    def _calc_one_pos_greedy(self, board, row, col, c_me):
        """C++: calcOnePosGreedy。不模拟落子，与 C++ 一致"""
        s = 0
        for dr in range(4):
            for j in range(5):
                sx, sy = self._get_xy(row, col, RIGHT + dr, j - 4)
                ex, ey = self._get_xy(sx, sy, RIGHT + dr, 4)
                if not (self._check_bound(sx, sy) and self._check_bound(ex, ey)):
                    continue
                bc = wc = 0
                for k in range(5):
                    tx, ty = self._get_xy(sx, sy, RIGHT + dr, k)
                    if board[tx][ty] == C_BLACK: bc += 1
                    if board[tx][ty] == C_WHITE: wc += 1
                s += self._tuple_score_greedy(bc, wc, c_me)
        return s

    # ==================== seekPoints（C++: chessAi::seekPoints）====================

    def seek_points(self, board, c_me=C_WHITE):
        # 标记候选区域（±3 邻域）
        B = [[False] * 15 for _ in range(15)]
        for i in range(15):
            for j in range(15):
                if board[i][j] != C_NONE:
                    for k in range(-3, 4):
                        if 0 <= i + k < 15:
                            B[i + k][j] = True
                            if 0 <= j + k < 15: B[i + k][j + k] = True
                            if 0 <= j - k < 15: B[i + k][j - k] = True
                        if 0 <= j + k < 15: B[i][j + k] = True

        worth = [[-math.inf] * 15 for _ in range(15)]
        for i in range(15):
            for j in range(15):
                if board[i][j] == C_NONE and B[i][j]:
                    worth[i][j] = self._calc_one_pos_greedy(board, i, j, c_me)

        # 手动取 Top 20
        best = []
        for _ in range(20):
            w = -math.inf
            bx = by = -1
            for i in range(15):
                for j in range(15):
                    if worth[i][j] > w:
                        w = worth[i][j]; bx, by = i, j
            if bx != -1:
                board[bx][by] = c_me
                sc = self.evaluate(board).score
                board[bx][by] = C_NONE
                best.append(((bx, by), sc))
                worth[bx][by] = -math.inf
            else:
                break
        return best

    # ==================== analyse（C++: chessAi::analyse）====================

    def analyse(self, board, depth, alpha, beta, max_depth=None):
        if max_depth is None:
            max_depth = depth
        EVAL = self.evaluate(board)
        if depth == 0 or EVAL.result != R_DRAW:
            self.nodeNum += 1
            if depth == 0:
                # 叶节点：始终从 AI 视角扩展。偶数深度的叶是 Max，
                # 奇数深度的叶是 Min，用 max_depth 奇偶判断
                is_max_leaf = max_depth % 2 == 0
                pts = self.seek_points(board, C_WHITE if is_max_leaf else C_BLACK)
                return pts[0][1] if pts else EVAL.score
            return EVAL.score

        # 用 max_depth 奇偶对齐，确保根节点始终是 Max（AI 回合）
        is_max = depth % 2 == max_depth % 2

        if is_max:  # Max —— 白方
            pts = self.seek_points(board, C_WHITE)
            if depth == max_depth and pts:
                self.decision.pos = pts[0][0]
            for i in range(min(10, len(pts))):
                x, y = pts[i][0]
                brd = self._copy_board(board)
                brd[x][y] = C_WHITE
                a = self.analyse(brd, depth - 1, alpha, beta, max_depth)
                if a > alpha:
                    alpha = a
                    if depth == max_depth:
                        self.decision.pos = (x, y)
                        self.decision.eval_score = a
                if beta <= alpha:
                    break
            return alpha
        else:  # Min —— 黑方
            rbrd = self._reverse_board(board)
            pts = self.seek_points(rbrd, C_WHITE)
            for i in range(min(10, len(pts))):
                x, y = pts[i][0]
                brd = self._copy_board(board)
                brd[x][y] = C_BLACK
                a = self.analyse(brd, depth - 1, alpha, beta, max_depth)
                if a < beta:
                    beta = a
                if beta <= alpha:
                    break
            return beta

    # ==================== seek_kill_points（C++: chessAi::seek_kill_points）====================

    def _seek_kill_points(self, board):
        ret = []
        base_eval = self.evaluate(board)
        pts = self.seek_points(board)
        for i in range(min(20, len(pts))):
            x, y = pts[i][0]
            tmp = self._copy_board(board)
            tmp[x][y] = C_WHITE
            ev = self.evaluate(tmp)
            if (ev.STAT[WIN] > 0 or
                ev.STAT[FLEX4] > base_eval.STAT[FLEX4] or
                ev.STAT[BLOCK4] > base_eval.STAT[BLOCK4] or
                ev.STAT[FLEX3] > base_eval.STAT[FLEX3]):
                ret.append((x, y))
        return ret

    # ==================== analyse_kill（C++: chessAi::analyse_kill）====================

    def analyse_kill(self, board, depth):
        EVAL = self.evaluate(board)
        if depth == 0 or EVAL.result != R_DRAW:
            if depth == 0:
                pts = self.seek_points(board)
                tmp = self._copy_board(board)
                tmp[pts[0][0][0]][pts[0][0][1]] = C_WHITE
                return self.evaluate(tmp).result == R_WHITE
            return EVAL.result == R_WHITE

        if depth % 2 == 0:  # Max
            if depth >= 14:
                pts = self.seek_points(board)
                for i in range(min(10, len(pts))):
                    x, y = pts[i][0]
                    brd = self._copy_board(board)
                    brd[x][y] = C_WHITE
                    if self.analyse_kill(brd, depth - 1):
                        if depth == 16:
                            self.decision.pos = (x, y)
                            self.decision.eval_score = 999999999
                        return True
                return False
            else:
                kpts = self._seek_kill_points(board)
                if not kpts:
                    return False
                for x, y in kpts:
                    brd = self._copy_board(board)
                    brd[x][y] = C_WHITE
                    if self.analyse_kill(brd, depth - 1):
                        return True
                return False
        else:  # Min
            rbrd = self._reverse_board(board)
            pts = self.seek_points(rbrd, C_WHITE)
            if not pts:
                return False
            x, y = pts[0][0]
            brd = self._copy_board(board)
            brd[x][y] = C_BLACK
            return self.analyse_kill(brd, depth - 1)

    # ==================== get_action（入口）====================

    def get_action(self, board, depth=6, ai_color=C_WHITE):
        self.nodeNum = 0
        # 如果 AI 执黑，翻转棋盘——始终从白方视角搜索
        b = self._reverse_board(board) if ai_color == C_BLACK else board

        empty = sum(row.count(C_NONE) for row in b)
        if empty == 225:
            return (7, 7)

        if self.analyse_kill(b, 16):
            return self.decision.pos

        self.analyse(b, depth, -math.inf, math.inf)
        return self.decision.pos
