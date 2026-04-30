#ifndef CHESSAI_DLL_H
#define CHESSAI_DLL_H
// 纯 C 接口 —— 剥离 Qt，供 Python ctypes 调用

#define C_NONE  0
#define C_BLACK 1
#define C_WHITE 2

#define RIGHT  0
#define UP     1
#define UPRIGHT 2
#define UPLEFT  3

// —— 棋型代号 ——
#define OTHER  0
#define WIN    1
#define LOSE   2
#define FLEX4  3
#define flex4  4
#define BLOCK4 5
#define block4 6
#define FLEX3  7
#define flex3  8
#define BLOCK3 9
#define block3 10
#define FLEX2  11
#define flex2  12
#define BLOCK2 13
#define block2 14
#define FLEX1  15
#define flex1  16

enum GameResult { R_BLACK = 0, R_WHITE = 1, R_DRAW = 2 };

struct Pos { int x, y; };

struct EvalResult {
    int score;
    int result;
    int stat_win;    // STAT[WIN]
    int stat_lose;   // STAT[LOSE]
    int stat_flex4;  // STAT[FLEX4]
    int stat_block4; // STAT[BLOCK4]
    int stat_flex3;  // STAT[FLEX3]
};

#ifdef __cplusplus
extern "C" {
#endif

__declspec(dllexport) void ai_init(void);
__declspec(dllexport) void ai_destroy(void);
__declspec(dllexport) void ai_get_action(int board[15][15], int depth,
                                          int ai_color,
                                          int* out_row, int* out_col,
                                          int* out_score);
__declspec(dllexport) EvalResult ai_evaluate(int board[15][15]);

#ifdef __cplusplus
}
#endif

#endif
