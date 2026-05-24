# -*- coding: utf-8 -*-
import pygame, sys, os
from chess_ai import ChessAI, C_NONE, C_BLACK, C_WHITE

# ── 跨平台字体加载 ──
def _get_font(size):
    base = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    bundled = os.path.join(base, 'simhei.ttf')
    if os.path.exists(bundled):
        return pygame.font.Font(bundled, size)
    for name in ('simhei', 'microsoft yahei', 'simsun', 'kaiti', 'fangsong'):
        if pygame.font.match_font(name):
            return pygame.font.SysFont(name, size)
    return pygame.font.Font(None, size)

# ── 全局配置 ──
AI_DEPTH  = 5
BLOCK     = 40
MARGIN    = 40
LINES     = 15
W, H      = BLOCK * (LINES - 1) + MARGIN * 2, BLOCK * (LINES - 1) + MARGIN * 2
CONSOLE_W = 280

C_BG   = (220, 180, 100)
C_LINE = (0, 0, 0)
C_RED  = (255, 0, 0)

# ── 棋盘绘制 ──
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

# ── 棋子绘制 ──
def _draw_pieces(screen, board, last):
    for i in range(LINES):
        for j in range(LINES):
            if board[i][j] == C_NONE: continue
            pos = (MARGIN + j * BLOCK, MARGIN + i * BLOCK)
            c = (0, 0, 0) if board[i][j] == C_BLACK else (255, 255, 255)
            pygame.draw.circle(screen, c, pos, BLOCK // 2 - 4)
            if last == (i, j):
                pygame.draw.circle(screen, C_RED, pos, 4)

def _check_draw(board):
    for row in board:
        if C_NONE in row: return False
    return True

def _difficulty_name(depth):
    return {2: "新手", 3: "精通", 4: "大师", 5: "宗师"}.get(depth, str(depth))

# ── 通知提示（底部临时消息） ──
def _set_notice(msg):
    return msg, pygame.time.get_ticks() + 1800

# ── 右侧控制台面板 ──
def _draw_console(screen, font, score_log, board, ai, rf, forbidden_rule):
    px = W
    screen.fill((30, 30, 45), (px, 0, CONSOLE_W, H))
    pygame.draw.rect(screen, (50, 50, 70), (px, 0, CONSOLE_W, 28))
    screen.blit(font.render('评估控制台', True, (255, 255, 150)), (px + 5, 4))

    ev = ai.evaluate(board)
    c = (0, 255, 0) if ev.score >= 0 else (255, 150, 150)
    screen.blit(font.render(f'当前: {ev.score:+d}', True, c), (px + 5, 33))
    screen.blit(font.render(f'禁手: {"开" if forbidden_rule else "关"}', True, (230, 230, 230)), (px + 5, 51))

    y = 71
    for step, sc in score_log[-16:]:
        c = (150, 255, 150) if sc >= 0 else (255, 150, 150)
        screen.blit(font.render(f'第{step:02d}手: {sc:+d}', True, c), (px + 5, y))
        y += 16

    rules = ['────── 规则 ──────', '分数 = 白方视角评估',
             '绿色 = 白方优势  红色 = 黑方优势',
             '禁手开时: 黑棋禁长连/三三/四四',
             '开局前按 D 切换禁手', '按 C 关闭控制台']
    ry = H - len(rules) * 15 - 8
    for i, r in enumerate(rules):
        screen.blit(rf.render(r, True, (180, 180, 200)), (px + 5, ry + i * 15))

# ═══════════════ 主循环 ═══════════════
def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption('五子棋')
    F  = _get_font(40)
    Fh = _get_font(18)
    Fc = _get_font(15)
    Fr = _get_font(13)

    ai = ChessAI()
    board = [[C_NONE] * LINES for _ in range(LINES)]

    human, ai_side, turn = C_BLACK, C_WHITE, C_BLACK
    over, is_draw, last = False, False, None
    hist, score_log = [], []
    show_console, prev_console = False, False
    forbidden_rule = False
    pvp_mode = False
    ai_depth = AI_DEPTH
    show_diff_menu = False
    notice, notice_until = '', 0
    btn_rects = []

    while True:
        if show_console != prev_console:
            prev_console = show_console
            tw = W + CONSOLE_W if show_console else W
            screen = pygame.display.set_mode((tw, H))
        _draw_board(screen)
        _draw_pieces(screen, board, last)

        # ── 提示栏 (采用双行显示以节省空间) ──
        if not over:
            mode_str = "双人" if pvp_mode else "人机"
            diff_str = _difficulty_name(ai_depth)
            if not hist:
                s1 = f'落子:左键 | E模式: {mode_str} | D禁手:{"开" if forbidden_rule else "关"} | F难度:{diff_str}'
                if not pvp_mode:
                    s2 = f'A切换先后（你要{"黑先" if human == C_BLACK else "白后"}）'
                else:
                    s2 = '当前为双人对战，黑方先行'
            else:
                s1 = f'末子: {"黑" if turn == C_WHITE else "白"} | 右键悔棋 | C控制台 | 模式: {mode_str}'
                if pvp_mode:
                    s2 = f'禁手:{"开" if forbidden_rule else "关"} | 当前回合: {"黑" if turn == C_BLACK else "白"}'
                else:
                    s2 = f'禁手:{"开" if forbidden_rule else "关"} | B AI辅助 | F难度:{diff_str}'
            screen.blit(Fh.render(s1, True, (0, 0, 180)), (10, 2))
            screen.blit(Fh.render(s2, True, (0, 0, 180)), (10, 22))

        if notice:
            if pygame.time.get_ticks() < notice_until:
                screen.blit(Fh.render(notice, True, (180, 0, 0)), (MARGIN, H - 28))
            else:
                notice = ''

        if show_console:
            _draw_console(screen, Fc, score_log, board, ai, Fr, forbidden_rule)

        if over:
            if is_draw: t = F.render('平局（点任意处重置）', True, (255, 0, 0))
            else: t = F.render(f'{"黑子"if turn==C_BLACK else"白子"} 胜（点任意处重置）', True, (255, 0, 0))
            screen.blit(t, (W // 2 - t.get_width() // 2, H // 2 - 20))

        # ── 绘制难度选择弹窗 ──
        if show_diff_menu:
            menu_rect = pygame.Rect(W // 2 - 100, H // 2 - 145, 200, 290)
            pygame.draw.rect(screen, (240, 240, 240), menu_rect)
            pygame.draw.rect(screen, (0, 0, 0), menu_rect, 2)
            
            title_surf = Fh.render('选择 AI 难度', True, (0, 0, 0))
            screen.blit(title_surf, (W // 2 - title_surf.get_width() // 2, H // 2 - 125))
            
            btn_rects = []
            options = [("新手 (层数 2)", 2), ("精通 (层数 3)", 3), ("大师 (层数 4)", 4), ("宗师 (层数 5)", 5)]
            mx, my = pygame.mouse.get_pos()
            for idx, (label, val) in enumerate(options):
                by = H // 2 - 75 + idx * 50
                brect = pygame.Rect(W // 2 - 80, by, 160, 40)
                btn_rects.append((brect, val))
                
                color = (200, 240, 200) if brect.collidepoint(mx, my) else (220, 220, 220)
                if ai_depth == val:
                    color = (180, 220, 180)
                    pygame.draw.rect(screen, (0, 0, 255), brect, 2)
                pygame.draw.rect(screen, color, brect)
                pygame.draw.rect(screen, (0, 0, 0), brect, 1)
                
                if ai_depth == val:
                    pygame.draw.rect(screen, (255, 0, 0), brect, 2)
                
                tsurf = Fh.render(label, True, (0, 0, 0))
                screen.blit(tsurf, (W // 2 - tsurf.get_width() // 2, by + 10))

        pygame.display.flip()

        # ── 游戏结束处理 ──
        if over:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: pygame.quit(); sys.exit()
                if e.type == pygame.MOUSEBUTTONDOWN:
                    board = [[C_NONE]*LINES for _ in range(LINES)]
                    human, ai_side, turn = C_BLACK, C_WHITE, C_BLACK
                    over = is_draw = False; last = None
                    notice = ''
                    hist.clear(); score_log.clear()
            continue

        # ── AI 自动回合 ──
        if not pvp_mode and turn == ai_side:
            pygame.display.set_caption('五子棋（AI 思考中...）')
            pygame.event.pump()
            action = ai.get_action(board, depth=ai_depth, ai_color=ai_side, forbidden_rule=forbidden_rule)
            pygame.event.clear()
            if action is None:
                over = is_draw = True
            else:
                x, y = action
                if board[x][y] == C_NONE:
                    board[x][y] = ai_side; last = (x, y); hist.append((x, y))
                    score_log.append((len(hist), ai.evaluate(board).score))
                    over = ai.check_win(board, x, y, ai_side, forbidden_rule)
                    if not over:
                        if _check_draw(board): over = is_draw = True
                        else: turn = human
                else:
                    turn = human
            pygame.display.set_caption('五子棋')

        # ── 玩家输入事件 ──
        assist = False
        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_f and not pvp_mode:
                    show_diff_menu = not show_diff_menu
                if e.key == pygame.K_e and not hist and not over:
                    pvp_mode = not pvp_mode
                    notice, notice_until = _set_notice(f'已切换为 {"双人对战" if pvp_mode else "人机对战"}')
                if e.key == pygame.K_a and not pvp_mode and not hist and not over:
                    if human == C_BLACK: human, ai_side = C_WHITE, C_BLACK
                    else:                human, ai_side = C_BLACK, C_WHITE
                    turn = C_BLACK
                if e.key == pygame.K_d and not hist and not over:
                    forbidden_rule = not forbidden_rule
                    notice, notice_until = _set_notice(f'本局禁手规则已{"开启" if forbidden_rule else "关闭"}')
                if e.key == pygame.K_b and not pvp_mode and turn == human and not over:
                    assist = True
                if e.key == pygame.K_c:
                    show_console = not show_console
            if e.type == pygame.MOUSEBUTTONDOWN and not over and not assist:
                if show_diff_menu:
                    if e.button == 1:
                        mx, my = e.pos
                        for brect, val in btn_rects:
                            if brect.collidepoint(mx, my):
                                ai_depth = val
                                notice, notice_until = _set_notice(f'AI 难度已设为 {_difficulty_name(val)}')
                                show_diff_menu = False
                                break
                        else:
                            if not pygame.Rect(W // 2 - 100, H // 2 - 145, 200, 290).collidepoint(mx, my):
                                show_diff_menu = False
                    continue
                
                if pvp_mode:
                    if e.button == 1:
                        mx, my = e.pos
                        r = round((my - MARGIN) / BLOCK)
                        c = round((mx - MARGIN) / BLOCK)
                        if 0 <= r < LINES and 0 <= c < LINES and board[r][c] == C_NONE:
                            reason = ai.get_forbidden_reason(board, r, c, turn) if forbidden_rule and turn == C_BLACK else None
                            if reason:
                                notice, notice_until = _set_notice(f'{reason}: 黑棋不能下这里')
                            else:
                                board[r][c] = turn; last = (r, c); hist.append((r, c))
                                score_log.append((len(hist), ai.evaluate(board).score))
                                over = ai.check_win(board, r, c, turn, forbidden_rule)
                                if not over:
                                    if _check_draw(board): over = is_draw = True
                                    else: turn = C_WHITE if turn == C_BLACK else C_BLACK
                    elif e.button == 3 and len(hist) >= 1:
                        a = hist.pop(); board[a[0]][a[1]] = C_NONE
                        last = hist[-1] if hist else None
                        turn = C_WHITE if turn == C_BLACK else C_BLACK
                        notice = ''
                        if score_log: score_log.pop()
                else:
                    if turn == human:
                        if e.button == 1:
                            mx, my = e.pos
                            r = round((my - MARGIN) / BLOCK)
                            c = round((mx - MARGIN) / BLOCK)
                            if 0 <= r < LINES and 0 <= c < LINES and board[r][c] == C_NONE:
                                reason = ai.get_forbidden_reason(board, r, c, human) if forbidden_rule and human == C_BLACK else None
                                if reason:
                                    notice, notice_until = _set_notice(f'{reason}: 黑棋不能下这里')
                                else:
                                    board[r][c] = human; last = (r, c); hist.append((r, c))
                                    score_log.append((len(hist), ai.evaluate(board).score))
                                    over = ai.check_win(board, r, c, human, forbidden_rule)
                                    if not over:
                                        if _check_draw(board): over = is_draw = True
                                        else: turn = ai_side
                        elif e.button == 3 and len(hist) >= 2:
                            a = hist.pop(); board[a[0]][a[1]] = C_NONE
                            p = hist.pop(); board[p[0]][p[1]] = C_NONE
                            last = hist[-1] if hist else None
                            turn = human
                            notice = ''
                            if score_log: score_log.pop()
                            if score_log: score_log.pop()

        # ── B 键 AI 辅助 ──
        if assist:
            pygame.display.set_caption('五子棋（AI 辅助思考中...）')
            pygame.event.pump()
            action = ai.get_action(board, depth=ai_depth, ai_color=human, forbidden_rule=forbidden_rule)
            pygame.event.clear()
            if action is None:
                notice, notice_until = _set_notice('没有可下的合法点')
            else:
                x, y = action
                if board[x][y] == C_NONE:
                    board[x][y] = human; last = (x, y); hist.append((x, y))
                    score_log.append((len(hist), ai.evaluate(board).score))
                    over = ai.check_win(board, x, y, human, forbidden_rule)
                    if not over:
                        if _check_draw(board): over = is_draw = True
                        else: turn = ai_side
            pygame.display.set_caption('五子棋')

if __name__ == '__main__':
    main()
