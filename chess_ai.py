# -*- coding: utf-8 -*-
import math
import time
import numpy as np
from numba import njit

# ── JIT 编译 evaluate 核心 ──
WEIGHT = np.array([0, 1000000, -10000000, 50000, -100000, 400, -100000,
                   400, -8000, 20, -100, 50, -250, 1, -3, 1, -3], dtype=np.int32)
THINK_TIME_LIMIT = 5.0
KILL_DEFENSE_LIMIT = 8

@njit
def _evaluate_numba(A, tt):
    stat = np.zeros(17, dtype=np.int32)
    for i in range(1, 16):
        for j in range(12):
            stat[tt[A[i,j],A[i,j+1],A[i,j+2],A[i,j+3],A[i,j+4],A[i,j+5]]] += 1
    for j in range(1, 16):
        for i in range(12):
            stat[tt[A[i,j],A[i+1,j],A[i+2,j],A[i+3,j],A[i+4,j],A[i+5,j]]] += 1
    for i in range(12):
        for j in range(12):
            stat[tt[A[i,j],A[i+1,j+1],A[i+2,j+2],A[i+3,j+3],A[i+4,j+4],A[i+5,j+5]]] += 1
    for i in range(12):
        for j in range(5, 17):
            stat[tt[A[i,j],A[i+1,j-1],A[i+2,j-2],A[i+3,j-3],A[i+4,j-4],A[i+5,j-5]]] += 1
    score = np.int64(0)
    for i in range(1, 17):
        score += np.int64(stat[i]) * np.int64(WEIGHT[i])
    return (score, stat[WIN], stat[LOSE], stat[FLEX4], stat[BLOCK4], stat[FLEX3])

# ── JIT 编译禁手判断 ──
@njit
def _njit_line_count(board, x, y, dx, dy, color):
    cnt = 1
    nx, ny = x + dx, y + dy
    while 0 <= nx < 15 and 0 <= ny < 15 and board[nx, ny] == color:
        cnt += 1; nx += dx; ny += dy
    nx, ny = x - dx, y - dy
    while 0 <= nx < 15 and 0 <= ny < 15 and board[nx, ny] == color:
        cnt += 1; nx -= dx; ny -= dy
    return cnt

@njit
def _njit_has_overline(board, x, y, color):
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        if _njit_line_count(board, x, y, dx, dy, color) > 5: return True
    return False

@njit
def _njit_has_exact_five(board, x, y, color):
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        if _njit_line_count(board, x, y, dx, dy, color) == 5: return True
    return False

@njit
def _njit_count_open_four_lines(board, x, y, color):
    """统计落子后能造出几个活四方向"""
    ret = 0
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        has = False
        for step in range(-4, 5):
            tx, ty = x + step*dx, y + step*dy
            if not (0 <= tx < 15 and 0 <= ty < 15) or board[tx, ty] != 0: continue
            board[tx, ty] = color
            if _njit_line_count(board, tx, ty, dx, dy, color) == 5 and not _njit_has_overline(board, tx, ty, color):
                has = True
            board[tx, ty] = 0
            if has: break
        if has: ret += 1
    return ret

@njit
def _njit_has_open_four_in_dir(board, x1, y1, x2, y2, dx, dy, color):
    for start in range(-5, 1):
        a1 = a2 = False; ok = True
        for i in range(6):
            cx, cy = x2 + (start+i)*dx, y2 + (start+i)*dy
            if cx == x1 and cy == y1: a1 = True
            if cx == x2 and cy == y2: a2 = True
            v = board[cx, cy] if (0 <= cx < 15 and 0 <= cy < 15) else -1
            if i == 0 or i == 5:
                if v != 0: ok = False; break
            else:
                if v != color: ok = False; break
        if a1 and a2 and ok: return True
    return False

@njit
def _njit_count_open_three_lines(board, x, y, color):
    """统计落子后能造出几个活三方向"""
    ret = 0
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        has = False
        for step in range(-4, 5):
            tx, ty = x + step*dx, y + step*dy
            if not (0 <= tx < 15 and 0 <= ty < 15) or board[tx, ty] != 0: continue
            board[tx, ty] = color
            if not _njit_has_overline(board, tx, ty, color) and _njit_has_open_four_in_dir(board, x, y, tx, ty, dx, dy, color):
                has = True
            board[tx, ty] = 0
            if has: break
        if has: ret += 1
    return ret

@njit
def _njit_forbidden_reason(board, x, y, color):
    if _njit_has_exact_five(board, x, y, color): return 0
    if _njit_has_overline(board, x, y, color): return 1
    if _njit_count_open_four_lines(board, x, y, color) >= 2: return 2
    if _njit_count_open_three_lines(board, x, y, color) >= 2: return 3
    return 0

# ── 常量 ──
C_NONE, C_BLACK, C_WHITE = 0, 1, 2
RIGHT, UP, UPRIGHT, UPLEFT = 0, 1, 2, 3

OTHER, WIN, LOSE, FLEX4, flex4 = 0, 1, 2, 3, 4
BLOCK4, block4, FLEX3, flex3 = 5, 6, 7, 8
BLOCK3, block3, FLEX2, flex2 = 9, 10, 11, 12
BLOCK2, block2, FLEX1, flex1 = 13, 14, 15, 16
R_BLACK, R_WHITE, R_DRAW = 0, 1, 2

class Evaluation:
    def __init__(self):
        self.score, self.result, self.STAT = 0, R_DRAW, [0] * 17

class Decision:
    def __init__(self):
        self.pos, self.eval_score = None, 0

# ═══════════════ ChessAI 类 ═══════════════
class ChessAI:
    def __init__(self):
        self.tuple6type = {}
        self._init_tuple6type()
        self.nodeNum = 0
        self.decision = Decision()
        self.deadline = None
        self.timeout = False
        self.kill_root_depth = 0
        self._tt_np = np.zeros((4, 4, 4, 4, 4, 4), dtype=np.int32)
        for k, v in self.tuple6type.items():
            self._tt_np[k[0], k[1], k[2], k[3], k[4], k[5]] = v

    # ── 基础工具 ──
    def _check_bound(self, x, y): return 0 <= x < 15 and 0 <= y < 15

    def _get_xy(self, row, col, dr, rel):
        if dr == RIGHT:   return (row, col + rel)
        if dr == UP:      return (row - rel, col)
        if dr == UPRIGHT: return (row - rel, col + rel)
        if dr == UPLEFT:  return (row - rel, col - rel)
        return (row, col)

    def _copy_board(self, src): return [row[:] for row in src]

    def _reverse_board(self, src):
        dst = [[C_NONE] * 15 for _ in range(15)]
        for i in range(15):
            for j in range(15):
                if   src[i][j] == C_BLACK: dst[i][j] = C_WHITE
                elif src[i][j] == C_WHITE: dst[i][j] = C_BLACK
        return dst

    def _reverse_color(self, color):
        if color == C_BLACK: return C_WHITE
        if color == C_WHITE: return C_BLACK
        return None

    def _time_is_up(self):
        if self.deadline is not None and time.perf_counter() >= self.deadline:
            self.timeout = True
            return True
        return False

    # ── 胜负 & 禁手检测 ──
    def check_win(self, board, x, y, color, forbidden_rule=False):
        b = np.array(board, dtype=np.int32)
        if forbidden_rule and color == C_BLACK:
            return _njit_has_exact_five(b, x, y, color)
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            if _njit_line_count(b, x, y, dx, dy, color) >= 5: return True
        return False

    def get_forbidden_reason(self, board, x, y, color=C_BLACK):
        if not self._check_bound(x, y) or board[x][y] != C_NONE: return None
        b = np.array(board, dtype=np.int32)
        b[x, y] = color
        r = _njit_forbidden_reason(b, x, y, color)
        if r == 1: return '长连禁手'
        if r == 2: return '四四禁手'
        if r == 3: return '三三禁手'
        return None

    def is_forbidden_move(self, board, x, y, color=C_BLACK):
        return self.get_forbidden_reason(board, x, y, color) is not None

    # ── 棋型初始化 ──
    def _init_tuple6type(self):
        self.tuple6type[(2,2,2,2,2,2)] = WIN; self.tuple6type[(2,2,2,2,2,0)] = WIN
        self.tuple6type[(0,2,2,2,2,2)] = WIN; self.tuple6type[(2,2,2,2,2,1)] = WIN
        self.tuple6type[(1,2,2,2,2,2)] = WIN; self.tuple6type[(3,2,2,2,2,2)] = WIN
        self.tuple6type[(2,2,2,2,2,3)] = WIN
        self.tuple6type[(1,1,1,1,1,1)] = LOSE; self.tuple6type[(1,1,1,1,1,0)] = LOSE
        self.tuple6type[(0,1,1,1,1,1)] = LOSE; self.tuple6type[(1,1,1,1,1,2)] = LOSE
        self.tuple6type[(2,1,1,1,1,1)] = LOSE; self.tuple6type[(3,1,1,1,1,1)] = LOSE
        self.tuple6type[(1,1,1,1,1,3)] = LOSE
        self.tuple6type[(0,2,2,2,2,0)] = FLEX4; self.tuple6type[(0,1,1,1,1,0)] = flex4
        for t in [(0,2,2,2,0,0),(0,0,2,2,2,0),(0,2,0,2,2,0),(0,2,2,0,2,0)]: self.tuple6type[t] = FLEX3
        for t in [(0,1,1,1,0,0),(0,0,1,1,1,0),(0,1,0,1,1,0),(0,1,1,0,1,0)]: self.tuple6type[t] = flex3
        for t in [(0,2,2,0,0,0),(0,2,0,2,0,0),(0,2,0,0,2,0),(0,0,2,2,0,0),(0,0,2,0,2,0),(0,0,0,2,2,0)]: self.tuple6type[t] = FLEX2
        for t in [(0,1,1,0,0,0),(0,1,0,1,0,0),(0,1,0,0,1,0),(0,0,1,1,0,0),(0,0,1,0,1,0),(0,0,0,1,1,0)]: self.tuple6type[t] = flex2
        for t in [(0,2,0,0,0,0),(0,0,2,0,0,0),(0,0,0,2,0,0),(0,0,0,0,2,0)]: self.tuple6type[t] = FLEX1
        for t in [(0,1,0,0,0,0),(0,0,1,0,0,0),(0,0,0,1,0,0),(0,0,0,0,1,0)]: self.tuple6type[t] = flex1
        for p1 in range(4):
            for p2 in range(3):
                for p3 in range(3):
                    for p4 in range(3):
                        for p5 in range(3):
                            for p6 in range(4):
                                t = (p1,p2,p3,p4,p5,p6)
                                if t in self.tuple6type: continue
                                x = (1 if p1==1 else(1 if p1==2 else 0))
                                y = (1 if p1==2 else 0)
                                ix = iy = 0
                                for p in (p2,p3,p4,p5):
                                    if p==1: x+=1; ix+=1
                                    elif p==2: y+=1; iy+=1
                                if p6==1: ix+=1
                                elif p6==2: iy+=1
                                if p1==3 or p6==3:
                                    if p1==3 and p6!=3:
                                        if ix==0 and iy==4 and t not in self.tuple6type: self.tuple6type[t]=BLOCK4
                                        elif ix==4 and iy==0 and t not in self.tuple6type: self.tuple6type[t]=block4
                                        elif ix==0 and iy==3 and t not in self.tuple6type: self.tuple6type[t]=BLOCK3
                                        elif ix==3 and iy==0 and t not in self.tuple6type: self.tuple6type[t]=block3
                                        elif ix==0 and iy==2 and t not in self.tuple6type: self.tuple6type[t]=BLOCK2
                                        elif ix==2 and iy==0 and t not in self.tuple6type: self.tuple6type[t]=block2
                                    elif p6==3 and p1!=3:
                                        if x==0 and y==4 and t not in self.tuple6type: self.tuple6type[t]=BLOCK4
                                        elif x==4 and y==0 and t not in self.tuple6type: self.tuple6type[t]=block4
                                        elif x==3 and y==0 and t not in self.tuple6type: self.tuple6type[t]=BLOCK3
                                        elif x==0 and y==3 and t not in self.tuple6type: self.tuple6type[t]=block3
                                        elif x==2 and y==0 and t not in self.tuple6type: self.tuple6type[t]=BLOCK2
                                        elif x==0 and y==2 and t not in self.tuple6type: self.tuple6type[t]=block2
                                else:
                                    if (x==0 and y==4 or ix==0 and iy==4) and t not in self.tuple6type: self.tuple6type[t]=BLOCK4
                                    elif (x==4 and y==0 or ix==4 and iy==0) and t not in self.tuple6type: self.tuple6type[t]=block4
                                    elif (x==0 and y==3 or ix==0 and iy==3) and t not in self.tuple6type: self.tuple6type[t]=BLOCK3
                                    elif (x==3 and y==0 or ix==3 and iy==0) and t not in self.tuple6type: self.tuple6type[t]=block3
                                    elif (x==0 and y==2 or ix==0 and iy==2) and t not in self.tuple6type: self.tuple6type[t]=BLOCK2
                                    elif (x==2 and y==0 or ix==2 and iy==0) and t not in self.tuple6type: self.tuple6type[t]=block2

    # ── 局面评估 ──
    def evaluate(self, board):
        A = np.full((17, 17), 3, dtype=np.int32)
        A[1:16, 1:16] = np.array(board, dtype=np.int32)
        score, w, l, f4, b4, f3 = _evaluate_numba(A, self._tt_np)
        ev = Evaluation()
        ev.score = int(score)
        ev.STAT[WIN]=int(w); ev.STAT[LOSE]=int(l)
        ev.STAT[FLEX4]=int(f4); ev.STAT[BLOCK4]=int(b4); ev.STAT[FLEX3]=int(f3)
        if w>0: ev.result=R_WHITE
        elif l>0: ev.result=R_BLACK
        return ev

    # ── 贪心评分 ──
    def _tuple_score_greedy(self, black, white, c_me):
        if c_me==C_BLACK and black==5: return 9999999
        if c_me==C_WHITE and white==5: return 9999999
        if black==0 and white==0: return 7
        if black>=1 and white>=1: return 0
        if c_me==C_BLACK:
            if black==1 and white==0: return 35
            if black==2 and white==0: return 800
            if black==3 and white==0: return 15000
            if black==4 and white==0: return 800000
            if black==0 and white==1: return 15
            if black==0 and white==2: return 400
            if black==0 and white==3: return 1800
            return 100000
        else:
            if black==1 and white==0: return 15
            if black==2 and white==0: return 800  # 优先防守对方活2
            if black==3 and white==0: return 1800
            if black==4 and white==0: return 100000
            if black==0 and white==1: return 35
            if black==0 and white==2: return 400  # 降低自己建活3的优先级
            if black==0 and white==3: return 15000
            return 800000
    def _calc_one_pos_greedy(self, board, row, col, c_me):
        s = 0
        for dr in range(4):
            for j in range(5):
                sx, sy = self._get_xy(row, col, RIGHT+dr, j-4)
                ex, ey = self._get_xy(sx, sy, RIGHT+dr, 4)
                if not(self._check_bound(sx,sy) and self._check_bound(ex,ey)): continue
                bc = wc = 0
                for k in range(5):
                    tx, ty = self._get_xy(sx, sy, RIGHT+dr, k)
                    if board[tx][ty]==C_BLACK: bc+=1
                    if board[tx][ty]==C_WHITE: wc+=1
                s += self._tuple_score_greedy(bc, wc, c_me)
        return s

    # ── 候选点生成 ──
    def seek_points(self, board, c_me=C_WHITE, forbidden_color=None):
        B = [[False]*15 for _ in range(15)]
        for i in range(15):
            for j in range(15):
                if board[i][j]!=C_NONE:
                    for k in range(-3,4):
                        if 0<=i+k<15:
                            B[i+k][j]=True
                            if 0<=j+k<15: B[i+k][j+k]=True
                            if 0<=j-k<15: B[i+k][j-k]=True
                        if 0<=j+k<15: B[i][j+k]=True
        worth = [[-math.inf]*15 for _ in range(15)]
        board_np = np.array(board, dtype=np.int32) if forbidden_color is not None and c_me == forbidden_color else None
        for i in range(15):
            for j in range(15):
                if board[i][j]==C_NONE and B[i][j]:
                    if board_np is not None:
                        board_np[i,j] = c_me
                        if _njit_forbidden_reason(board_np, i, j, c_me) > 0:
                            board_np[i,j] = C_NONE; continue
                        board_np[i,j] = C_NONE
                    worth[i][j] = self._calc_one_pos_greedy(board,i,j,c_me)
        best = []
        for _ in range(20):
            w = -math.inf; bx = by = -1
            for i in range(15):
                for j in range(15):
                    if worth[i][j]>w: w=worth[i][j]; bx,by=i,j
            if bx!=-1:
                board[bx][by]=c_me
                sc = self.evaluate(board).score
                board[bx][by]=C_NONE
                best.append(((bx,by), sc))
                worth[bx][by] = -math.inf
            else: break
        return best

    # ── Minimax + Alpha-Beta 搜索 ──
    def analyse(self, board, depth, alpha, beta, max_depth=None, forbidden_color=None):
        if max_depth is None: max_depth = depth
        EVAL = self.evaluate(board)
        if self._time_is_up():
            return EVAL.score
        if depth==0 or EVAL.result!=R_DRAW:
            self.nodeNum += 1
            if depth==0:
                is_max_leaf = max_depth%2==0
                pts = self.seek_points(board, C_WHITE if is_max_leaf else C_BLACK, forbidden_color)
                return pts[0][1] if pts else EVAL.score
            return EVAL.score
        is_max = depth%2 == max_depth%2
        if is_max:
            pts = self.seek_points(board, C_WHITE, forbidden_color)
            if not pts: return EVAL.score
            if depth==max_depth and pts: self.decision.pos = pts[0][0]
            for i in range(min(10,len(pts))):
                if self._time_is_up(): break
                x, y = pts[i][0]
                brd = self._copy_board(board)
                brd[x][y] = C_WHITE
                a = self.analyse(brd, depth-1, alpha, beta, max_depth, forbidden_color)
                if a>alpha:
                    alpha = a
                    if depth==max_depth:
                        self.decision.pos = (x,y); self.decision.eval_score = a
                if beta<=alpha: break
            return alpha
        else:
            rbrd = self._reverse_board(board)
            pts = self.seek_points(rbrd, C_WHITE, self._reverse_color(forbidden_color))
            if not pts: return EVAL.score
            for i in range(min(10,len(pts))):
                if self._time_is_up(): break
                x, y = pts[i][0]
                brd = self._copy_board(board)
                brd[x][y] = C_BLACK
                a = self.analyse(brd, depth-1, alpha, beta, max_depth, forbidden_color)
                if a<beta: beta = a
                if beta<=alpha: break
            return beta

    # ── VCF 杀棋点 ──
    def _seek_kill_points(self, board, forbidden_color=None):
        ret = []
        base_eval = self.evaluate(board)
        pts = self.seek_points(board, C_WHITE, forbidden_color)
        for i in range(min(20,len(pts))):
            x, y = pts[i][0]
            tmp = self._copy_board(board)
            tmp[x][y] = C_WHITE
            ev = self.evaluate(tmp)
            if (ev.STAT[WIN]>0 or ev.STAT[FLEX4]>base_eval.STAT[FLEX4] or
                ev.STAT[BLOCK4]>base_eval.STAT[BLOCK4] or ev.STAT[FLEX3]>base_eval.STAT[FLEX3]):
                ret.append((x,y))
        return ret

    # ── VCF 算杀 ──
    def analyse_kill(self, board, depth, forbidden_color=None):
        if self._time_is_up():
            return False
        EVAL = self.evaluate(board)
        if depth==0 or EVAL.result!=R_DRAW:
            if depth==0:
                pts = self.seek_points(board, C_WHITE, forbidden_color)
                if not pts: return False
                tmp = self._copy_board(board)
                tmp[pts[0][0][0]][pts[0][0][1]] = C_WHITE
                return self.evaluate(tmp).result==R_WHITE
            return EVAL.result==R_WHITE
        if depth%2==0:
            if depth>=14:
                pts = self.seek_points(board, C_WHITE, forbidden_color)
                for i in range(min(10,len(pts))):
                    if self._time_is_up(): return False
                    x,y = pts[i][0]
                    brd = self._copy_board(board)
                    brd[x][y] = C_WHITE
                    if self.analyse_kill(brd, depth-1, forbidden_color):
                        if depth==self.kill_root_depth:
                            self.decision.pos = (x,y); self.decision.eval_score=999999999
                        return True
                return False
            else:
                kpts = self._seek_kill_points(board, forbidden_color)
                if not kpts: return False
                for x,y in kpts:
                    if self._time_is_up(): return False
                    brd = self._copy_board(board)
                    brd[x][y] = C_WHITE
                    if self.analyse_kill(brd, depth-1, forbidden_color):
                        if depth==self.kill_root_depth:
                            self.decision.pos = (x,y); self.decision.eval_score=999999999
                        return True
                return False
        else:
            rbrd = self._reverse_board(board)
            pts = self.seek_points(rbrd, C_WHITE, self._reverse_color(forbidden_color))
            if not pts: return False
            # 防守方只要有一种应手能解杀，就不能算作进攻方必杀。
            for pos, _ in pts[:KILL_DEFENSE_LIMIT]:
                if self._time_is_up(): return False
                x, y = pos
                brd = self._copy_board(board)
                brd[x][y] = C_BLACK
                if not self.analyse_kill(brd, depth-1, forbidden_color):
                    return False
            return True

    # ── 合法性兜底检查 ──
    def _action_is_legal(self, board, pos, color, forbidden_rule=False):
        if pos is None: return False
        x, y = pos
        if not self._check_bound(x, y) or board[x][y] != C_NONE: return False
        return not (forbidden_rule and color == C_BLACK and self.is_forbidden_move(board, x, y, C_BLACK))

    def _find_immediate_win(self, board, color, forbidden_rule=False):
        for i in range(15):
            for j in range(15):
                if not self._action_is_legal(board, (i, j), color, forbidden_rule):
                    continue
                board[i][j] = color
                win = self.check_win(board, i, j, color, forbidden_rule)
                board[i][j] = C_NONE
                if win:
                    return (i, j)
        return None

    def _kill_depth_for_search(self, depth):
        if depth <= 2:
            return 0
        if depth == 3:
            return 10
        return 16

    # ── 决策入口 ──
    def get_action(self, board, depth=6, ai_color=C_WHITE, forbidden_rule=False, time_limit=THINK_TIME_LIMIT):
        self.nodeNum = 0; self.decision = Decision()
        self.deadline = time.perf_counter() + time_limit if time_limit is not None else None
        self.timeout = False
        b = self._reverse_board(board) if ai_color==C_BLACK else board
        forbidden_color = None
        if forbidden_rule:
            forbidden_color = C_WHITE if ai_color==C_BLACK else C_BLACK

        if sum(row.count(C_NONE) for row in b)==225: return (7,7)
        win_pos = self._find_immediate_win(board, ai_color, forbidden_rule)
        if win_pos is not None:
            return win_pos
        block_pos = self._find_immediate_win(board, self._reverse_color(ai_color), forbidden_rule)
        if self._action_is_legal(board, block_pos, ai_color, forbidden_rule):
            return block_pos

        kill_depth = self._kill_depth_for_search(depth)
        self.kill_root_depth = kill_depth
        if kill_depth and self.analyse_kill(b, kill_depth, forbidden_color):
            if self._action_is_legal(board, self.decision.pos, ai_color, forbidden_rule):
                return self.decision.pos
        if not self.timeout:
            self.analyse(b, depth, -math.inf, math.inf, forbidden_color=forbidden_color)
        if self._action_is_legal(board, self.decision.pos, ai_color, forbidden_rule):
            return self.decision.pos
        # 禁手导致首选不可下，逐候选找合法点
        pts = self.seek_points(b, C_WHITE, forbidden_color)
        for pos, _ in pts:
            if self._action_is_legal(board, pos, ai_color, forbidden_rule): return pos
        for i in range(15):
            for j in range(15):
                if self._action_is_legal(board, (i,j), ai_color, forbidden_rule): return (i,j)
        return None
