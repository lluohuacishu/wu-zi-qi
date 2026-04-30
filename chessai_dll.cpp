// chessai_dll.cpp —— 剥离 Qt 的五子棋 AI DLL
// 原始: Gobang-ai-master/chessai.cpp (Qt 项目)
// 改动: QPoint→Pos, QList→固定数组, qDebug→空
#include "chessai_dll.h"
#include <cstring>
#include <climits>
#include <cstdio>

// ==================== chessAi 类（与原版逻辑完全一致） ====================
class chessAi {
public:
    int  nodeNum;
    Pos  decision;
    int  tuple6type[4][4][4][4][4][4];
    struct LocalPoints { Pos pos[20]; int score[20]; } points;

    chessAi() { init_tuple6type(); nodeNum = 0; decision = {0,0}; }

    bool checkBound(int x, int y);
    Pos  getXY(int row, int col, int dir, int rel);
    int  calcOnePosGreedy(int board[15][15], int row, int col, int C_ME);
    int  tupleScoreGreedy(int black, int white, int C_ME);
    void init_tuple6type();
    void copyBoard(int A[15][15], int B[15][15]);
    void reverseBoard(int A[15][15], int B[15][15]);
    EvalResult evaluate(int board[15][15]);

    void seekPoints(int board[15][15], Pos out[], int scores[]);
    int  analyse(int board[15][15], int depth, int alpha, int beta, int max_depth=0);
    bool analyse_kill(int board[15][15], int depth);
    int  seek_kill_points(int board[15][15], Pos out[]);
};

// -------------------- 基础工具 --------------------
bool chessAi::checkBound(int x, int y) {
    return x >= 0 && x < 15 && y >= 0 && y < 15;
}
Pos chessAi::getXY(int row, int col, int dir, int rel) {
    Pos p = {row, col};
    if      (dir == RIGHT)   p.y += rel;
    else if (dir == UP)      p.x -= rel;
    else if (dir == UPRIGHT) { p.x -= rel; p.y += rel; }
    else if (dir == UPLEFT)  { p.x -= rel; p.y -= rel; }
    return p;
}
void chessAi::copyBoard(int (*A)[15], int (*B)[15]) {
    for (int i = 0; i < 15; ++i)
        for (int j = 0; j < 15; ++j)
            B[i][j] = A[i][j];
}
void chessAi::reverseBoard(int (*A)[15], int (*B)[15]) {
    for (int i = 0; i < 15; ++i)
        for (int j = 0; j < 15; ++j) {
            if      (A[i][j] == C_BLACK) B[i][j] = C_WHITE;
            else if (A[i][j] == C_WHITE) B[i][j] = C_BLACK;
            else                         B[i][j] = C_NONE;
        }
}

// -------------------- 贪心评分 --------------------
int chessAi::tupleScoreGreedy(int black, int white, int C_ME) {
    if (C_ME == C_BLACK && black == 5) return 9999999;
    if (C_ME == C_WHITE && white == 5) return 9999999;
    if (black == 0 && white == 0) return 7;
    if (black >= 1 && white >= 1) return 0;
    if (C_ME == C_BLACK) {
        if (black == 1 && white == 0) return 35;
        if (black == 2 && white == 0) return 800;
        if (black == 3 && white == 0) return 15000;
        if (black == 4 && white == 0) return 800000;
        if (black == 0 && white == 1) return 15;
        if (black == 0 && white == 2) return 400;
        if (black == 0 && white == 3) return 1800;
        return 100000;
    } else {
        if (black == 1 && white == 0) return 15;
        if (black == 2 && white == 0) return 400;
        if (black == 3 && white == 0) return 1800;
        if (black == 4 && white == 0) return 100000;
        if (black == 0 && white == 1) return 35;
        if (black == 0 && white == 2) return 800;
        if (black == 0 && white == 3) return 15000;
        return 800000;
    }
}
int chessAi::calcOnePosGreedy(int board[15][15], int row, int col, int C_ME) {
    int sum = 0;
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 5; ++j) {
            Pos s = getXY(row, col, RIGHT + i, j - 4);
            Pos e = getXY(s.x, s.y, RIGHT + i, 4);
            if (!checkBound(s.x, s.y) || !checkBound(e.x, e.y)) continue;
            int bc = 0, wc = 0;
            for (int k = 0; k < 5; ++k) {
                Pos t = getXY(s.x, s.y, RIGHT + i, k);
                if      (board[t.x][t.y] == C_BLACK) bc++;
                else if (board[t.x][t.y] == C_WHITE) wc++;
            }
            sum += tupleScoreGreedy(bc, wc, C_ME);
        }
    }
    return sum;
}

// -------------------- init_tuple6type（原封不动）--------------------
void chessAi::init_tuple6type() {
    memset(tuple6type, 0, sizeof(tuple6type));
    tuple6type[2][2][2][2][2][2] = WIN;   tuple6type[2][2][2][2][2][0] = WIN;
    tuple6type[0][2][2][2][2][2] = WIN;   tuple6type[2][2][2][2][2][1] = WIN;
    tuple6type[1][2][2][2][2][2] = WIN;   tuple6type[3][2][2][2][2][2] = WIN;
    tuple6type[2][2][2][2][2][3] = WIN;
    tuple6type[1][1][1][1][1][1] = LOSE;  tuple6type[1][1][1][1][1][0] = LOSE;
    tuple6type[0][1][1][1][1][1] = LOSE;  tuple6type[1][1][1][1][1][2] = LOSE;
    tuple6type[2][1][1][1][1][1] = LOSE;  tuple6type[3][1][1][1][1][1] = LOSE;
    tuple6type[1][1][1][1][1][3] = LOSE;
    tuple6type[0][2][2][2][2][0] = FLEX4; tuple6type[0][1][1][1][1][0] = flex4;
    tuple6type[0][2][2][2][0][0] = FLEX3; tuple6type[0][0][2][2][2][0] = FLEX3;
    tuple6type[0][2][0][2][2][0] = FLEX3; tuple6type[0][2][2][0][2][0] = FLEX3;
    tuple6type[0][1][1][1][0][0] = flex3; tuple6type[0][0][1][1][1][0] = flex3;
    tuple6type[0][1][0][1][1][0] = flex3; tuple6type[0][1][1][0][1][0] = flex3;
    tuple6type[0][2][2][0][0][0] = FLEX2; tuple6type[0][2][0][2][0][0] = FLEX2;
    tuple6type[0][2][0][0][2][0] = FLEX2; tuple6type[0][0][2][2][0][0] = FLEX2;
    tuple6type[0][0][2][0][2][0] = FLEX2; tuple6type[0][0][0][2][2][0] = FLEX2;
    tuple6type[0][1][1][0][0][0] = flex2; tuple6type[0][1][0][1][0][0] = flex2;
    tuple6type[0][1][0][0][1][0] = flex2; tuple6type[0][0][1][1][0][0] = flex2;
    tuple6type[0][0][1][0][1][0] = flex2; tuple6type[0][0][0][1][1][0] = flex2;
    tuple6type[0][2][0][0][0][0] = FLEX1; tuple6type[0][0][2][0][0][0] = FLEX1;
    tuple6type[0][0][0][2][0][0] = FLEX1; tuple6type[0][0][0][0][2][0] = FLEX1;
    tuple6type[0][1][0][0][0][0] = flex1; tuple6type[0][0][1][0][0][0] = flex1;
    tuple6type[0][0][0][1][0][0] = flex1; tuple6type[0][0][0][0][1][0] = flex1;
    // —— 修复：含间隔的4子模式 → 眠三，防止暴力枚举误判为冲四 ——
    // 白4子有间隔
    tuple6type[2][0][2][2][2][0] = BLOCK3; tuple6type[2][2][0][2][2][0] = BLOCK3;
    tuple6type[2][2][2][0][2][0] = BLOCK3;
    tuple6type[0][2][0][2][2][2] = BLOCK3; tuple6type[0][2][2][0][2][2] = BLOCK3;
    tuple6type[0][2][2][2][0][2] = BLOCK3;
    // 黑4子有间隔
    tuple6type[1][0][1][1][1][0] = block3; tuple6type[1][1][0][1][1][0] = block3;
    tuple6type[1][1][1][0][1][0] = block3;
    tuple6type[0][1][0][1][1][1] = block3; tuple6type[0][1][1][0][1][1] = block3;
    tuple6type[0][1][1][1][0][1] = block3;
    // —— 暴力枚举 ——
    for (int p1 = 0; p1 < 4; ++p1)
    for (int p2 = 0; p2 < 3; ++p2)
    for (int p3 = 0; p3 < 3; ++p3)
    for (int p4 = 0; p4 < 3; ++p4)
    for (int p5 = 0; p5 < 3; ++p5)
    for (int p6 = 0; p6 < 4; ++p6) {
        int x = 0, y = 0, ix = 0, iy = 0;
        if (p1 == 1) x++; else if (p1 == 2) y++;
        if (p2 == 1) { x++; ix++; } else if (p2 == 2) { y++; iy++; }
        if (p3 == 1) { x++; ix++; } else if (p3 == 2) { y++; iy++; }
        if (p4 == 1) { x++; ix++; } else if (p4 == 2) { y++; iy++; }
        if (p5 == 1) { x++; ix++; } else if (p5 == 2) { y++; iy++; }
        if (p6 == 1) ix++; else if (p6 == 2) iy++;
        if (p1 == 3 || p6 == 3) {
            if (p1 == 3 && p6 != 3) {
                if      (ix == 0 && iy == 4 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK4;
                else if (ix == 4 && iy == 0 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block4;
                else if (ix == 0 && iy == 3 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK3;
                else if (ix == 3 && iy == 0 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block3;
                else if (ix == 0 && iy == 2 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK2;
                else if (ix == 2 && iy == 0 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block2;
            } else if (p6 == 3 && p1 != 3) {
                if      (x == 0 && y == 4 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK4;
                else if (x == 4 && y == 0 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block4;
                else if (x == 3 && y == 0 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK3;
                else if (x == 0 && y == 3 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block3;
                else if (x == 2 && y == 0 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK2;
                else if (x == 0 && y == 2 && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block2;
            }
        } else {
            if      ((x == 0 && y == 4 || ix == 0 && iy == 4) && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK4;
            else if ((x == 4 && y == 0 || ix == 4 && iy == 0) && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block4;
            else if ((x == 0 && y == 3 || ix == 0 && iy == 3) && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK3;
            else if ((x == 3 && y == 0 || ix == 3 && iy == 0) && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block3;
            else if ((x == 0 && y == 2 || ix == 0 && iy == 2) && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = BLOCK2;
            else if ((x == 2 && y == 0 || ix == 2 && iy == 0) && tuple6type[p1][p2][p3][p4][p5][p6] == 0) tuple6type[p1][p2][p3][p4][p5][p6] = block2;
        }
    }
}

// -------------------- evaluate（原封不动）--------------------
EvalResult chessAi::evaluate(int board[15][15]) {
    int weight[17] = {0,1000000,-10000000,50000,-100000,400,-100000,400,-8000,20,-50,20,-50,1,-3,1,-3};
    int A[17][17];
    for (int i = 0; i < 17; ++i) A[i][0] = A[i][16] = A[0][i] = A[16][i] = 3;
    for (int i = 0; i < 15; ++i)
        for (int j = 0; j < 15; ++j)
            A[i+1][j+1] = board[i][j];

    int stat[4][17] = {{0}};
    for (int i = 1; i <= 15; ++i)
        for (int j = 0; j < 12; ++j)
            stat[0][tuple6type[A[i][j]][A[i][j+1]][A[i][j+2]][A[i][j+3]][A[i][j+4]][A[i][j+5]]]++;
    for (int j = 1; j <= 15; ++j)
        for (int i = 0; i < 12; ++i)
            stat[1][tuple6type[A[i][j]][A[i+1][j]][A[i+2][j]][A[i+3][j]][A[i+4][j]][A[i+5][j]]]++;
    for (int i = 0; i < 12; ++i)
        for (int j = 0; j < 12; ++j)
            stat[2][tuple6type[A[i][j]][A[i+1][j+1]][A[i+2][j+2]][A[i+3][j+3]][A[i+4][j+4]][A[i+5][j+5]]]++;
    for (int i = 0; i < 12; ++i)
        for (int j = 5; j < 17; ++j)
            stat[3][tuple6type[A[i][j]][A[i+1][j-1]][A[i+2][j-2]][A[i+3][j-3]][A[i+4][j-4]][A[i+5][j-5]]]++;

    EvalResult r = {0};
    for (int i = 1; i < 17; ++i) {
        int cnt = stat[0][i] + stat[1][i] + stat[2][i] + stat[3][i];
        r.score += cnt * weight[i];
        if      (i == WIN)    r.stat_win    = cnt;
        else if (i == LOSE)   r.stat_lose   = cnt;
        else if (i == FLEX4)  r.stat_flex4  = cnt;
        else if (i == BLOCK4) r.stat_block4 = cnt;
        else if (i == FLEX3)  r.stat_flex3  = cnt;
    }
    r.result = R_DRAW;
    if (r.stat_win  > 0) r.result = R_WHITE;
    else if (r.stat_lose > 0) r.result = R_BLACK;
    return r;
}

// -------------------- seekPoints（原封不动，加哨兵）--------------------
void chessAi::seekPoints(int board[15][15], Pos out[], int scores[]) {
    for (int k = 0; k < 20; ++k) { out[k] = {-1, -1}; scores[k] = 0; }
    bool B[15][15] = {{false}};
    for (int i = 0; i < 15; ++i)
        for (int j = 0; j < 15; ++j)
            if (board[i][j] != C_NONE)
                for (int k = -3; k <= 3; ++k) {
                    if (i+k >= 0 && i+k < 15) {
                        B[i+k][j] = true;
                        if (j+k >= 0 && j+k < 15) B[i+k][j+k] = true;
                        if (j-k >= 0 && j-k < 15) B[i+k][j-k] = true;
                    }
                    if (j+k >= 0 && j+k < 15) B[i][j+k] = true;
                }

    int worth[15][15];
    for (int i = 0; i < 15; ++i)
        for (int j = 0; j < 15; ++j)
            worth[i][j] = -INT_MAX;
    for (int i = 0; i < 15; ++i)
        for (int j = 0; j < 15; ++j)
            if (board[i][j] == C_NONE && B[i][j])
                worth[i][j] = calcOnePosGreedy(board, i, j, C_WHITE);

    for (int k = 0; k < 20; ++k) {
        int w = -INT_MAX, bx = -1, by = -1;
        for (int i = 0; i < 15; ++i)
            for (int j = 0; j < 15; ++j)
                if (worth[i][j] > w) { w = worth[i][j]; bx = i; by = j; }
        if (bx == -1) break;
        board[bx][by] = C_WHITE;
        scores[k] = evaluate(board).score;
        board[bx][by] = C_NONE;
        out[k] = {bx, by};
        worth[bx][by] = -INT_MAX;
    }
}

// -------------------- seek_kill_points（QList→数组+计数）--------------------
int chessAi::seek_kill_points(int board[15][15], Pos out[]) {
    Pos pts[20]; int sc[20]; int cnt = 0;
    seekPoints(board, pts, sc);

    int tmp[15][15];
    copyBoard(board, tmp);
    EvalResult base_eval = evaluate(board);

    for (int i = 0; i < 20; ++i) {
        if (pts[i].x < 0) break;
        tmp[pts[i].x][pts[i].y] = C_WHITE;
        EvalResult ev = evaluate(tmp);
        tmp[pts[i].x][pts[i].y] = C_NONE;
        if (ev.stat_win   > 0 ||
            ev.stat_flex4  > base_eval.stat_flex4 ||
            ev.stat_block4 > base_eval.stat_block4 ||
            ev.stat_flex3  > base_eval.stat_flex3)
            out[cnt++] = pts[i];
    }
    return cnt;
}

// -------------------- analyse（原封不动，depth%2==0 判定 Max/Min）--------------------
int chessAi::analyse(int (*board)[15], int depth, int alpha, int beta,
                     int max_depth) {
    EvalResult EVAL = evaluate(board);
    if (depth == 0 || EVAL.result != R_DRAW) {
        nodeNum++;
        if (depth == 0) {
            Pos pts[20]; int sc[20]; seekPoints(board, pts, sc);
            return sc[0];
        }
        return EVAL.score;
    }
    if (depth % 2 == 0) {  // Max —— 白方
        Pos pts[20]; int sc[20];
        seekPoints(board, pts, sc);
        if (depth == max_depth && pts[0].x >= 0)
            decision = pts[0];
        for (int i = 0; i < 10; ++i) {
            if (pts[i].x < 0) break;
            int brd[15][15];
            copyBoard(board, brd);
            brd[pts[i].x][pts[i].y] = C_WHITE;
            int a = analyse(brd, depth - 1, alpha, beta, max_depth);
            if (a > alpha) {
                alpha = a;
                if (depth == max_depth)
                    decision = pts[i];
            }
            if (beta <= alpha) break;
        }
        return alpha;
    } else {  // Min —— 黑方
        int rBoard[15][15];
        reverseBoard(board, rBoard);
        Pos pts[20]; int sc[20];
        seekPoints(rBoard, pts, sc);
        for (int i = 0; i < 10; ++i) {
            if (pts[i].x < 0) break;
            int brd[15][15];
            copyBoard(board, brd);
            brd[pts[i].x][pts[i].y] = C_BLACK;
            int a = analyse(brd, depth - 1, alpha, beta, max_depth);
            if (a < beta) beta = a;
            if (beta <= alpha) break;
        }
        return beta;
    }
}

// -------------------- analyse_kill（原封不动）--------------------
bool chessAi::analyse_kill(int (*board)[15], int depth) {
    EvalResult EVAL = evaluate(board);
    if (depth == 0 || EVAL.result != R_DRAW) {
        if (depth == 0) {
            Pos pts[20]; int sc[20];
            seekPoints(board, pts, sc);
            int brd[15][15];
            copyBoard(board, brd);
            brd[pts[0].x][pts[0].y] = C_WHITE;
            return evaluate(brd).result == R_WHITE;
        }
        return EVAL.result == R_WHITE;
    }
    if (depth % 2 == 0) {
        if (depth == 16 || depth == 14) {
            Pos pts[20]; int sc[20];
            seekPoints(board, pts, sc);
            for (int i = 0; i < 10; ++i) {
                if (pts[i].x < 0) break;
                int brd[15][15];
                copyBoard(board, brd);
                brd[pts[i].x][pts[i].y] = C_WHITE;
                if (analyse_kill(brd, depth - 1)) {
                    if (depth == 16)
                        decision = pts[i];
                    return true;
                }
            }
            return false;
        } else {
            Pos kpts[20];
            int kcnt = seek_kill_points(board, kpts);
            if (kcnt == 0) return false;
            for (int i = 0; i < kcnt; ++i) {
                int brd[15][15];
                copyBoard(board, brd);
                brd[kpts[i].x][kpts[i].y] = C_WHITE;
                if (analyse_kill(brd, depth - 1))
                    return true;
            }
            return false;
        }
    } else {
        int rBoard[15][15];
        reverseBoard(board, rBoard);
        Pos pts[20]; int sc[20];
        seekPoints(rBoard, pts, sc);
        if (pts[0].x < 0) return false;
        int brd[15][15];
        copyBoard(board, brd);
        brd[pts[0].x][pts[0].y] = C_BLACK;
        return analyse_kill(brd, depth - 1);
    }
}

// ==================== extern "C" 导出 ====================
static chessAi* g_ai = nullptr;

void ai_init(void) {
    if (!g_ai) g_ai = new chessAi();
}
void ai_destroy(void) {
    delete g_ai; g_ai = nullptr;
}

void ai_get_action(int board[15][15], int depth, int ai_color,
                   int* out_row, int* out_col, int* out_score) {
    if (!g_ai) ai_init();
    g_ai->nodeNum = 0;

    // 如果 AI 执黑，翻转为白方视角
    int b[15][15];
    if (ai_color == C_BLACK) g_ai->reverseBoard(board, b);
    else                     g_ai->copyBoard(board, b);

    // 空棋盘走中心
    int empty = 0;
    for (int i = 0; i < 15; ++i)
        for (int j = 0; j < 15; ++j)
            if (b[i][j] == C_NONE) empty++;
    if (empty == 225) { *out_row = 7; *out_col = 7; *out_score = 0; return; }

    // VCF 杀棋
    if (g_ai->analyse_kill(b, 16)) {
        *out_row = g_ai->decision.x;
        *out_col = g_ai->decision.y;
        *out_score = 99999999;
        return;
    }

    // 普通搜索
    int max_d = (depth % 2 == 0) ? depth : depth - 1;  // 强制偶数深度
    g_ai->analyse(b, max_d, -INT_MAX, INT_MAX, max_d);
    *out_row  = g_ai->decision.x;
    *out_col  = g_ai->decision.y;
    *out_score = 0;
}

EvalResult ai_evaluate(int board[15][15]) {
    if (!g_ai) ai_init();
    return g_ai->evaluate(board);
}
