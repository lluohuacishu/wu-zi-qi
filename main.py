# -*- coding: utf-8 -*-
import pygame
import sys
import os
from chess_ai import ChessAI, C_NONE, C_BLACK, C_WHITE

# ==================== 字体 ====================

def _get_font(size):
    base = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    bundled = os.path.join(base, 'simhei.ttf')
    if os.path.exists(bundled):
        return pygame.font.Font(bundled, size)
    for name in ('simhei', 'microsoft yahei', 'simsun', 'kaiti', 'fangsong'):
        if pygame.font.match_font(name):
            return pygame.font.SysFont(name, size)
    return pygame.font.Font(None, size)

# ==================== 配置 ====================

AI_DEPTH = 4               # 4层 ~3s, 5层 ~15s, 6层 ~42s（有 VCF 算杀兜底）
BLOCK   = 40
MARGIN  = 40
LINES   = 15
W, H    = BLOCK * (LINES - 1) + MARGIN * 2, BLOCK * (LINES - 1) + MARGIN * 2

C_BG    = (220, 180, 100)
C_LINE  = (0, 0, 0)
C_RED   = (255, 0, 0)

# ==================== 绘制 ====================

def _draw_board(screen):
    screen.fill(C_BG)
    for i in range(LINES):
        y = MARGIN + i * BLOCK
        pygame.draw.line(screen, C_LINE, (MARGIN, y), (W - MARGIN, y), 2)
        x = MARGIN + i * BLOCK
        pygame.draw.line(screen, C_LINE, (x, MARGIN), (x, H - MARGIN), 2)
    for px, py in ((3, 3), (11, 3), (3, 11), (11, 11), (7, 7)):
        pygame.draw.circle(screen, C_LINE,
                           (MARGIN + px * BLOCK, MARGIN + py * BLOCK), 5)

def _draw_pieces(screen, board, last):
    for i in range(LINES):
        for j in range(LINES):
            if board[i][j] == C_NONE:
                continue
            pos = (MARGIN + j * BLOCK, MARGIN + i * BLOCK)
            c = (0, 0, 0) if board[i][j] == C_BLACK else (255, 255, 255)
            pygame.draw.circle(screen, c, pos, BLOCK // 2 - 4)
            if last == (i, j):
                pygame.draw.circle(screen, C_RED, pos, 4)

def _check_win(board, x, y, color):
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        cnt = 1
        nx, ny = x + dx, y + dy
        while 0 <= nx < LINES and 0 <= ny < LINES and board[nx][ny] == color:
            cnt += 1; nx += dx; ny += dy
        nx, ny = x - dx, y - dy
        while 0 <= nx < LINES and 0 <= ny < LINES and board[nx][ny] == color:
            cnt += 1; nx -= dx; ny -= dy
        if cnt >= 5:
            return True
    return False

# ==================== 主循环 ====================

def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption('五子棋')
    F = _get_font(40)
    Fh = _get_font(18)

    ai = ChessAI()
    board = [[C_NONE] * LINES for _ in range(LINES)]

    human = C_BLACK
    ai_side = C_WHITE
    turn = C_BLACK
    over = False
    last = None
    hist = []

    while True:
        _draw_board(screen)
        _draw_pieces(screen, board, last)

        if not hist and not over:
            s = f'左键落子 | 右键撤回 | A 切换先后（你{"黑先" if human == C_BLACK else "白后"}）'
            screen.blit(Fh.render(s, True, (0, 0, 180)), (MARGIN, 5))

        if over:
            t = F.render(f'{"黑子" if turn == C_BLACK else "白子"} 胜（点任意处重置）',
                         True, (255, 0, 0))
            screen.blit(t, (W // 2 - t.get_width() // 2, H // 2 - 20))

        pygame.display.flip()

        if over:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    board = [[C_NONE] * LINES for _ in range(LINES)]
                    turn = human; over = False; last = None; hist.clear()
            continue

        if turn == ai_side:
            pygame.display.set_caption('五子棋（AI 思考中...）')
            pygame.event.pump()
            x, y = ai.get_action(board, depth=AI_DEPTH, ai_color=ai_side)
            if board[x][y] == C_NONE:
                board[x][y] = ai_side; last = (x, y); hist.append((x, y))
                over = _check_win(board, x, y, ai_side)
                if not over:
                    turn = human
            else:
                print(f'AI 非法落子 ({x},{y})'); turn = human
            pygame.display.set_caption('五子棋')

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_a and not hist and not over:
                if human == C_BLACK:
                    human, ai_side = C_WHITE, C_BLACK; turn = ai_side
                else:
                    human, ai_side = C_BLACK, C_WHITE; turn = C_BLACK
            if e.type == pygame.MOUSEBUTTONDOWN and turn == human and not over:
                if e.button == 1:
                    mx, my = e.pos
                    r = round((my - MARGIN) / BLOCK)
                    c = round((mx - MARGIN) / BLOCK)
                    if 0 <= r < LINES and 0 <= c < LINES and board[r][c] == C_NONE:
                        board[r][c] = human; last = (r, c); hist.append((r, c))
                        if _check_win(board, r, c, human):
                            over = True
                        else:
                            turn = ai_side
                elif e.button == 3 and len(hist) >= 2:
                    a = hist.pop(); board[a[0]][a[1]] = C_NONE
                    p = hist.pop(); board[p[0]][p[1]] = C_NONE
                    last = hist[-1] if hist else None
                    turn = human

if __name__ == '__main__':
    main()
