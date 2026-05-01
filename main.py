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

AI_DEPTH = 4               # Python Numba 深度4 ~3s
BLOCK   = 40
MARGIN  = 40
LINES   = 15
W, H    = BLOCK * (LINES - 1) + MARGIN * 2, BLOCK * (LINES - 1) + MARGIN * 2
CONSOLE_W = 280            # 控制台面板宽度

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

def _check_draw(board):
    for row in board:
        if C_NONE in row:
            return False
    return True

def _draw_console(screen, font, score_log, board, ai, rules_font):
    """右侧独立控制台面板：棋局评估分 + 使用规则"""
    px = W                            # 面板左边界（棋盘右侧）
    # 背景
    screen.fill((30, 30, 45), (px, 0, CONSOLE_W, H))
    # 标题栏
    pygame.draw.rect(screen, (50, 50, 70), (px, 0, CONSOLE_W, 28))
    t = font.render('评估控制台', True, (255, 255, 150))
    screen.blit(t, (px + 5, 4))
    # 当前分数
    ev = ai.evaluate(board)
    c = (0, 255, 0) if ev.score >= 0 else (255, 150, 150)
    cur = font.render(f'当前: {ev.score:+d}', True, c)
    screen.blit(cur, (px + 5, 33))
    # 历史分数
    y = 53
    for step, sc in score_log[-17:]:
        c = (150, 255, 150) if sc >= 0 else (255, 150, 150)
        s = font.render(f'第{step:02d}手: {sc:+d}', True, c)
        screen.blit(s, (px + 5, y))
        y += 16
    # 底部规则说明
    rules = [
        '────── 规则 ──────',
        '分数 = 白方视角评估',
        '绿色 = 白方优势',
        '红色 = 黑方优势',
        '分数越大威胁越强',
        '按 C 关闭控制台',
    ]
    ry = H - len(rules) * 15 - 8
    for i, r in enumerate(rules):
        screen.blit(rules_font.render(r, True, (180, 180, 200)),
                    (px + 5, ry + i * 15))

# ==================== 主循环 ====================

def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption('五子棋')
    F  = _get_font(40)
    Fh = _get_font(18)
    Fc = _get_font(15)  # 控制台小字体
    Fr = _get_font(13)  # 规则说明字体

    ai = ChessAI()
    board = [[C_NONE] * LINES for _ in range(LINES)]

    human = C_BLACK
    ai_side = C_WHITE
    turn = C_BLACK
    over = False
    is_draw = False
    last = None
    hist = []
    show_console = False
    prev_console = False
    score_log = []  # [(step#, score), ...] 白方视角累计分

    while True:
        # 控制台切换时调整窗口宽度
        if show_console != prev_console:
            prev_console = show_console
            tw = W + CONSOLE_W if show_console else W
            screen = pygame.display.set_mode((tw, H))
            pygame.display.set_caption('五子棋')
        _draw_board(screen)
        _draw_pieces(screen, board, last)

        if not over:
            if not hist:
                s = f'左键落子 | 右键撤回 | A切换先后（你{"黑先" if human == C_BLACK else "白后"}）'
            else:
                s = '左键落子 | 右键撤回 | B AI辅助一步棋 | C控制台'
            screen.blit(Fh.render(s, True, (0, 0, 180)), (MARGIN, 5))

        if show_console:
            _draw_console(screen, Fc, score_log, board, ai, Fr)

        if over:
            if is_draw:
                t = F.render('平局（点任意处重置）', True, (255, 0, 0))
            else:
                t = F.render(f'{"黑子" if turn == C_BLACK else "白子"} 胜（点任意处重置）',
                             True, (255, 0, 0))
            screen.blit(t, (W // 2 - t.get_width() // 2, H // 2 - 20))

        pygame.display.flip()

        if over:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    board = [[C_NONE] * LINES for _ in range(LINES)]
                    turn = human; over = False; is_draw = False; last = None
                    hist.clear(); score_log.clear()
            continue

        if turn == ai_side:
            pygame.display.set_caption('五子棋（AI 思考中...）')
            pygame.event.pump()
            x, y = ai.get_action(board, depth=AI_DEPTH, ai_color=ai_side)
            pygame.event.clear()
            if board[x][y] == C_NONE:
                board[x][y] = ai_side; last = (x, y); hist.append((x, y))
                score_log.append((len(hist), ai.evaluate(board).score))
                over = _check_win(board, x, y, ai_side)
                if not over:
                    if _check_draw(board):
                        over = True; is_draw = True
                    else:
                        turn = human
            else:
                print(f'AI 非法落子 ({x},{y})'); turn = human
            pygame.display.set_caption('五子棋')

        assist = False
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_a and not hist and not over:
                if human == C_BLACK:
                    human, ai_side = C_WHITE, C_BLACK; turn = ai_side
                else:
                    human, ai_side = C_BLACK, C_WHITE; turn = C_BLACK
            if e.type == pygame.KEYDOWN and e.key == pygame.K_b and turn == human and not over:
                assist = True  # 标记 B 键，在主循环处理（避免重复触发）
            if e.type == pygame.KEYDOWN and e.key == pygame.K_c:
                show_console = not show_console
            if not assist and e.type == pygame.MOUSEBUTTONDOWN and turn == human and not over:
                if e.button == 1:
                    mx, my = e.pos
                    r = round((my - MARGIN) / BLOCK)
                    c = round((mx - MARGIN) / BLOCK)
                    if 0 <= r < LINES and 0 <= c < LINES and board[r][c] == C_NONE:
                        board[r][c] = human; last = (r, c); hist.append((r, c))
                        score_log.append((len(hist), ai.evaluate(board).score))
                        if _check_win(board, r, c, human):
                            over = True
                        elif _check_draw(board):
                            over = True; is_draw = True
                        else:
                            turn = ai_side
                elif e.button == 3 and len(hist) >= 2:
                    a = hist.pop(); board[a[0]][a[1]] = C_NONE
                    p = hist.pop(); board[p[0]][p[1]] = C_NONE
                    last = hist[-1] if hist else None
                    turn = human
                    if score_log: score_log.pop()
                    if score_log: score_log.pop()

        if assist:
            pygame.display.set_caption('五子棋（AI 辅助思考中...）')
            pygame.event.pump()
            x, y = ai.get_action(board, depth=AI_DEPTH, ai_color=human)
            pygame.event.clear()
            if board[x][y] == C_NONE:
                board[x][y] = human; last = (x, y); hist.append((x, y))
                score_log.append((len(hist), ai.evaluate(board).score))
                if _check_win(board, x, y, human):
                    over = True
                elif _check_draw(board):
                    over = True; is_draw = True
                else:
                    turn = ai_side
            pygame.display.set_caption('五子棋')

if __name__ == '__main__':
    main()
