# -*- coding: utf-8 -*-
import math
import numpy as np
from numba import njit

# ── JIT 编译 evaluate 核心 ──
WEIGHT = np.array([0, 1000000, -10000000, 50000, -100000, 400, -100000,
                   400, -8000, 20, -50, 20, -50, 1, -3, 1, -3], dtype=np.int32)

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

# ── 常量 ──
C_NONE, C_BLACK, C_WHITE = 0, 1, 2
RIGHT, UP, UPRIGHT, UPLEFT = 0, 1, 2, 3

# 棋型代号
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
        self.pos, self.eval_score = (0, 0), 0

# ═══════════════ ChessAI 类 ═══════════════
class ChessAI:
    def __init__(self):
        self.tuple6type = {}
        self._init_tuple6type()
        self.nodeNum = 0
        self.decision = Decision()
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
            if black==2 and white==0: return 400
            if black==3 and white==0: return 1800
            if black==4 and white==0: return 100000
            if black==0 and white==1: return 35
            if black==0 and white==2: return 800
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
    def seek_points(self, board, c_me=C_WHITE):
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
        for i in range(15):
            for j in range(15):
                if board[i][j]==C_NONE and B[i][j]:
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
    def analyse(self, board, depth, alpha, beta, max_depth=None):
        if max_depth is None: max_depth = depth
        EVAL = self.evaluate(board)
        if depth==0 or EVAL.result!=R_DRAW:
            self.nodeNum += 1
            if depth==0:
                is_max_leaf = max_depth%2==0
                pts = self.seek_points(board, C_WHITE if is_max_leaf else C_BLACK)
                return pts[0][1] if pts else EVAL.score
            return EVAL.score
        is_max = depth%2 == max_depth%2
        if is_max:
            pts = self.seek_points(board, C_WHITE)
            if depth==max_depth and pts: self.decision.pos = pts[0][0]
            for i in range(min(10,len(pts))):
                x, y = pts[i][0]
                brd = self._copy_board(board)
                brd[x][y] = C_WHITE
                a = self.analyse(brd, depth-1, alpha, beta, max_depth)
                if a>alpha:
                    alpha = a
                    if depth==max_depth:
                        self.decision.pos = (x,y); self.decision.eval_score = a
                if beta<=alpha: break
            return alpha
        else:
            rbrd = self._reverse_board(board)
            pts = self.seek_points(rbrd, C_WHITE)
            for i in range(min(10,len(pts))):
                x, y = pts[i][0]
                brd = self._copy_board(board)
                brd[x][y] = C_BLACK
                a = self.analyse(brd, depth-1, alpha, beta, max_depth)
                if a<beta: beta = a
                if beta<=alpha: break
            return beta

    # ── VCF 杀棋点 ──
    def _seek_kill_points(self, board):
        ret = []
        base_eval = self.evaluate(board)
        pts = self.seek_points(board)
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
    def analyse_kill(self, board, depth):
        EVAL = self.evaluate(board)
        if depth==0 or EVAL.result!=R_DRAW:
            if depth==0:
                pts = self.seek_points(board)
                tmp = self._copy_board(board)
                tmp[pts[0][0][0]][pts[0][0][1]] = C_WHITE
                return self.evaluate(tmp).result==R_WHITE
            return EVAL.result==R_WHITE
        if depth%2==0:
            if depth>=14:
                pts = self.seek_points(board)
                for i in range(min(10,len(pts))):
                    x,y = pts[i][0]
                    brd = self._copy_board(board)
                    brd[x][y] = C_WHITE
                    if self.analyse_kill(brd, depth-1):
                        if depth==16:
                            self.decision.pos = (x,y); self.decision.eval_score=999999999
                        return True
                return False
            else:
                kpts = self._seek_kill_points(board)
                if not kpts: return False
                for x,y in kpts:
                    brd = self._copy_board(board)
                    brd[x][y] = C_WHITE
                    if self.analyse_kill(brd, depth-1): return True
                return False
        else:
            rbrd = self._reverse_board(board)
            pts = self.seek_points(rbrd, C_WHITE)
            if not pts: return False
            x,y = pts[0][0]
            brd = self._copy_board(board)
            brd[x][y] = C_BLACK
            return self.analyse_kill(brd, depth-1)

    # ── 决策入口 ──
    def get_action(self, board, depth=6, ai_color=C_WHITE):
        self.nodeNum = 0
        b = self._reverse_board(board) if ai_color==C_BLACK else board
        if sum(row.count(C_NONE) for row in b)==225: return (7,7)
        if self.analyse_kill(b, 16): return self.decision.pos
        self.analyse(b, depth, -math.inf, math.inf)
        return self.decision.pos
