# -*- coding: utf-8 -*-
import json, queue, secrets, socket, sys, threading, time

import pygame
from chess_ai import ChessAI, C_NONE, C_BLACK, C_WHITE

# ── 系统字体加载 ──
def _get_font(size):
    font_names = (
        'simhei', 'microsoft yahei', 'microsoft yahei ui', 'simsun',
        'nsimsun', 'kaiti', 'fangsong', 'pingfang sc',
        'hiragino sans gb', 'noto sans cjk sc', 'source han sans sc',
        'wenquanyi micro hei', 'arial unicode ms',
    )
    for name in font_names:
        if pygame.font.match_font(name):
            try:
                return pygame.font.SysFont(name, size)
            except pygame.error:
                continue
    return pygame.font.Font(None, size)

# ── 全局配置 ──
AI_DEPTH  = 5
LAN_PORT  = 50007
LAN_DISCOVERY_PORT = LAN_PORT + 1
LAN_PROTOCOL_VERSION = 1
LAN_MAX_MESSAGE_BYTES = 4096
LAN_ROOM_CODE_DIGITS = 6
LAN_DISCOVERY_TIMEOUT = 1.2
LAN_FRAME_RATE = 60
LAN_TURN_SECONDS = 35
LAN_TURN_MS = LAN_TURN_SECONDS * 1000
LAN_PING_INTERVAL_MS = 2000
LAN_PING_STALE_MS = 8000
BLOCK     = 40
MARGIN    = 40
TOP_MARGIN = 72
LINES     = 15
BOARD_SIZE = BLOCK * (LINES - 1)
W, H      = BOARD_SIZE + MARGIN * 2, BOARD_SIZE + TOP_MARGIN + MARGIN
CONSOLE_W = 280

C_BG   = (220, 180, 100)
C_LINE = (0, 0, 0)
C_RED  = (255, 0, 0)

# ── 棋盘绘制 ──
def _draw_board(screen):
    screen.fill(C_BG)
    for i in range(LINES):
        y = TOP_MARGIN + i * BLOCK
        pygame.draw.line(screen, C_LINE, (MARGIN, y), (W - MARGIN, y), 2)
        x = MARGIN + i * BLOCK
        pygame.draw.line(screen, C_LINE, (x, TOP_MARGIN), (x, H - MARGIN), 2)
    for px, py in ((3, 3), (11, 3), (3, 11), (11, 11), (7, 7)):
        pygame.draw.circle(screen, C_LINE,
                           (MARGIN + px * BLOCK, TOP_MARGIN + py * BLOCK), 5)

def _grid_pos(r, c):
    return MARGIN + c * BLOCK, TOP_MARGIN + r * BLOCK

# ── 棋子绘制 ──
def _draw_pieces(screen, board, last):
    for i in range(LINES):
        for j in range(LINES):
            if board[i][j] == C_NONE: continue
            pos = _grid_pos(i, j)
            c = (0, 0, 0) if board[i][j] == C_BLACK else (255, 255, 255)
            pygame.draw.circle(screen, c, pos, BLOCK // 2 - 4)
            if last == (i, j):
                pygame.draw.circle(screen, C_RED, pos, 4)

def _draw_win_line(screen, win_line):
    if not win_line:
        return
    (r1, c1), (r2, c2) = win_line
    start = _grid_pos(r1, c1)
    end = _grid_pos(r2, c2)
    pygame.draw.line(screen, (255, 235, 80), start, end, 8)
    pygame.draw.line(screen, (220, 0, 0), start, end, 4)

def _draw_ai_hint(screen, hint):
    if not hint:
        return
    r, c = hint
    if not (0 <= r < LINES and 0 <= c < LINES):
        return
    pos = _grid_pos(r, c)
    pygame.draw.circle(screen, (0, 100, 255), pos, BLOCK // 2 - 2, 3)
    pygame.draw.circle(screen, (255, 255, 255), pos, 8, 2)
    pygame.draw.line(screen, (0, 100, 255), (pos[0] - 8, pos[1]), (pos[0] + 8, pos[1]), 2)
    pygame.draw.line(screen, (0, 100, 255), (pos[0], pos[1] - 8), (pos[0], pos[1] + 8), 2)

def _draw_lan_latency(screen, font, lan_mode, lan_authenticated, latency_ms):
    if not (lan_mode and lan_authenticated):
        return
    if latency_ms is None:
        label = '延迟: --ms'
        color = (90, 90, 90)
    else:
        label = f'延迟: {latency_ms}ms'
        if latency_ms < 80:
            color = (0, 120, 40)
        elif latency_ms < 180:
            color = (170, 105, 0)
        else:
            color = (180, 0, 0)
    surf = font.render(label, True, color)
    pad_x = 6
    rect = pygame.Rect(
        W - surf.get_width() - pad_x * 2 - 8,
        46,
        surf.get_width() + pad_x * 2,
        surf.get_height() + 4,
    )
    pygame.draw.rect(screen, (245, 225, 160), rect)
    pygame.draw.rect(screen, (90, 65, 20), rect, 1)
    screen.blit(surf, (rect.x + pad_x, rect.y + 2))

def _check_draw(board):
    for row in board:
        if C_NONE in row: return False
    return True

def _difficulty_name(depth):
    return {2: "新手", 3: "精通", 4: "大师", 5: "宗师"}.get(depth, str(depth))

def _opponent(color):
    return C_WHITE if color == C_BLACK else C_BLACK

def _line_count(board, r, c, dr, dc, color):
    total = 1
    nr, nc = r + dr, c + dc
    while 0 <= nr < LINES and 0 <= nc < LINES and board[nr][nc] == color:
        total += 1
        nr += dr
        nc += dc
    nr, nc = r - dr, c - dc
    while 0 <= nr < LINES and 0 <= nc < LINES and board[nr][nc] == color:
        total += 1
        nr -= dr
        nc -= dc
    return total

def _check_win_fast(board, r, c, color, forbidden_rule=False):
    for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
        count = _line_count(board, r, c, dr, dc, color)
        if forbidden_rule and color == C_BLACK:
            if count == 5:
                return True
        elif count >= 5:
            return True
    return False

def _find_win_line(board, r, c, color, forbidden_rule=False):
    for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
        count = _line_count(board, r, c, dr, dc, color)
        if forbidden_rule and color == C_BLACK:
            if count != 5:
                continue
        elif count < 5:
            continue

        sr, sc = r, c
        while 0 <= sr - dr < LINES and 0 <= sc - dc < LINES and board[sr - dr][sc - dc] == color:
            sr -= dr
            sc -= dc
        er, ec = r, c
        while 0 <= er + dr < LINES and 0 <= ec + dc < LINES and board[er + dr][ec + dc] == color:
            er += dr
            ec += dc
        return (sr, sc), (er, ec)
    return None

def _has_overline_fast(board, r, c, color):
    for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
        if _line_count(board, r, c, dr, dc, color) > 5:
            return True
    return False

def _has_exact_five_fast(board, r, c, color):
    for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
        if _line_count(board, r, c, dr, dc, color) == 5:
            return True
    return False

def _count_open_four_lines_fast(board, r, c, color):
    total = 0
    for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
        has = False
        for step in range(-4, 5):
            nr, nc = r + step * dr, c + step * dc
            if not (0 <= nr < LINES and 0 <= nc < LINES) or board[nr][nc] != C_NONE:
                continue
            board[nr][nc] = color
            has = _line_count(board, nr, nc, dr, dc, color) == 5 and not _has_overline_fast(board, nr, nc, color)
            board[nr][nc] = C_NONE
            if has:
                break
        if has:
            total += 1
    return total

def _has_open_four_in_dir_fast(board, r1, c1, r2, c2, dr, dc, color):
    for start in range(-5, 1):
        has_first = False
        has_second = False
        ok = True
        for i in range(6):
            nr, nc = r2 + (start + i) * dr, c2 + (start + i) * dc
            if nr == r1 and nc == c1:
                has_first = True
            if nr == r2 and nc == c2:
                has_second = True
            value = board[nr][nc] if 0 <= nr < LINES and 0 <= nc < LINES else -1
            if i == 0 or i == 5:
                if value != C_NONE:
                    ok = False
                    break
            elif value != color:
                ok = False
                break
        if has_first and has_second and ok:
            return True
    return False

def _count_open_three_lines_fast(board, r, c, color):
    total = 0
    for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
        has = False
        for step in range(-4, 5):
            nr, nc = r + step * dr, c + step * dc
            if not (0 <= nr < LINES and 0 <= nc < LINES) or board[nr][nc] != C_NONE:
                continue
            board[nr][nc] = color
            has = (
                not _has_overline_fast(board, nr, nc, color)
                and _has_open_four_in_dir_fast(board, r, c, nr, nc, dr, dc, color)
            )
            board[nr][nc] = C_NONE
            if has:
                break
        if has:
            total += 1
    return total

def _get_forbidden_reason_fast(board, r, c, color):
    if color != C_BLACK or not (0 <= r < LINES and 0 <= c < LINES) or board[r][c] != C_NONE:
        return None
    board[r][c] = color
    try:
        if _has_exact_five_fast(board, r, c, color):
            return None
        if _has_overline_fast(board, r, c, color):
            return '长连禁手'
        if _count_open_four_lines_fast(board, r, c, color) >= 2:
            return '四四禁手'
        if _count_open_three_lines_fast(board, r, c, color) >= 2:
            return '三三禁手'
        return None
    finally:
        board[r][c] = C_NONE

def _is_protocol_supported(msg):
    return type(msg.get('protocol')) is int and msg.get('protocol') == LAN_PROTOCOL_VERSION

def _require_json_int(value):
    if type(value) is not int:
        raise ValueError('expected json integer')
    return value

def _require_json_bool(value):
    if type(value) is not bool:
        raise ValueError('expected json boolean')
    return value

# ── 通知提示（底部临时消息） ──
def _set_notice(msg):
    return msg, pygame.time.get_ticks() + 1800

def _get_lan_ip():
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return '127.0.0.1'
    finally:
        if sock:
            sock.close()

def _parse_join_target(text):
    target = text.strip()
    if not target:
        return None, LAN_PORT, ''
    room_code = ''
    if '#' in target:
        target, room_code = target.rsplit('#', 1)
        target = target.strip()
        room_code = room_code.strip()
    elif target.isdigit():
        return '', LAN_PORT, target
    if ':' not in target:
        return target, LAN_PORT, room_code

    host, port_text = target.rsplit(':', 1)
    host = host.strip()
    try:
        port = int(port_text)
    except ValueError:
        return None, LAN_PORT, room_code
    if not host or not (1 <= port <= 65535):
        return None, LAN_PORT, room_code
    return host, port, room_code

class LanConnection:
    def __init__(self, is_host, host='', port=LAN_PORT, room_code=''):
        self.is_host = is_host
        self.host = host
        self.port = port
        self.room_code = room_code
        self.sock = None
        self.server = None
        self.connected = False
        self.closed = False
        self.inbox = queue.Queue()
        self._send_lock = threading.Lock()
        target = self._run_host if is_host else self._run_client
        threading.Thread(target=target, daemon=True).start()

    def _configure_socket(self, sock):
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

    def _run_host(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('', self.port))
            server.listen(1)
            server.settimeout(0.5)
            self.server = server
            self.inbox.put({'_event': 'listening'})

            while not self.closed:
                try:
                    conn, addr = server.accept()
                    break
                except socket.timeout:
                    continue
            else:
                return

            self.sock = conn
            self._configure_socket(conn)
            self.sock.settimeout(0.5)
            self.connected = True
            self.inbox.put({'_event': 'connected', 'address': addr[0]})
            self._recv_loop()
        except OSError as exc:
            if not self.closed:
                self.inbox.put({'_event': 'error', 'message': str(exc)})
        finally:
            self._close_sockets()

    def _run_client(self):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._configure_socket(conn)
            conn.settimeout(5)
            conn.connect((self.host, self.port))
            conn.settimeout(0.5)
            self.sock = conn
            self.connected = True
            self.inbox.put({'_event': 'connected', 'address': self.host})
            self.send({'type': 'hello', 'code': self.room_code})
            self._recv_loop()
        except OSError as exc:
            if not self.closed:
                self.inbox.put({'_event': 'error', 'message': str(exc)})
        finally:
            self._close_sockets()

    def _recv_loop(self):
        buf = b''
        protocol_failed = False
        while not self.closed:
            try:
                sock = self.sock
                if not sock:
                    break
                data = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break

            buf += data
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                if len(line) > LAN_MAX_MESSAGE_BYTES:
                    self._queue_protocol_error('联机消息过长')
                    protocol_failed = True
                    break
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line.decode('utf-8'))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._queue_protocol_error('收到无法解析的联机消息')
                    protocol_failed = True
                    break
                if not isinstance(payload, dict) or not isinstance(payload.get('type'), str):
                    self._queue_protocol_error('收到异常联机消息')
                    protocol_failed = True
                    break
                self.inbox.put({'_event': 'message', 'payload': payload})
            if protocol_failed:
                break
            if len(buf) > LAN_MAX_MESSAGE_BYTES:
                self._queue_protocol_error('联机消息过长')
                protocol_failed = True
                break

        if not self.closed:
            self.connected = False
            if not protocol_failed:
                self.inbox.put({'_event': 'closed'})

    def send(self, msg):
        try:
            payload = dict(msg)
            payload.setdefault('protocol', LAN_PROTOCOL_VERSION)
            raw = (json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
            if len(raw) > LAN_MAX_MESSAGE_BYTES:
                self._queue_protocol_error('要发送的联机消息过长')
                return False
            with self._send_lock:
                sock = self.sock
                if not sock or not self.connected:
                    return False
                sock.sendall(raw)
            return True
        except (OSError, AttributeError, TypeError, ValueError) as exc:
            self.inbox.put({'_event': 'error', 'message': str(exc)})
            self.close()
            return False

    def _queue_protocol_error(self, message):
        if not self.closed:
            self.connected = False
            self.inbox.put({'_event': 'protocol_error', 'message': message})

    def poll(self):
        messages = []
        while True:
            try:
                messages.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        return messages

    def close(self):
        self.closed = True
        self.connected = False
        self._close_sockets()

    def _close_sockets(self):
        for s in (self.sock, self.server):
            if not s:
                continue
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass
        self.sock = None
        self.server = None

class LanDiscoveryResponder:
    def __init__(self, room_code, tcp_port=LAN_PORT):
        self.room_code = room_code
        self.tcp_port = tcp_port
        self.closed = False
        self.sock = None
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', LAN_DISCOVERY_PORT))
            sock.settimeout(0.25)
            self.sock = sock
            while not self.closed:
                try:
                    data, addr = sock.recvfrom(LAN_MAX_MESSAGE_BYTES)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if len(data) > LAN_MAX_MESSAGE_BYTES:
                    continue
                try:
                    msg = json.loads(data.decode('utf-8'))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get('type') != 'discover' or not _is_protocol_supported(msg):
                    continue
                if str(msg.get('code', '')) != self.room_code:
                    continue
                reply = {
                    'type': 'discover_reply',
                    'protocol': LAN_PROTOCOL_VERSION,
                    'code': self.room_code,
                    'port': self.tcp_port,
                }
                raw = json.dumps(reply, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                try:
                    sock.sendto(raw, addr)
                except OSError:
                    pass
        except OSError:
            pass
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
            self.sock = None

    def close(self):
        self.closed = True
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

def _discover_lan_host(room_code, timeout=LAN_DISCOVERY_TIMEOUT):
    payload = {
        'type': 'discover',
        'protocol': LAN_PROTOCOL_VERSION,
        'code': room_code,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    targets = (
        ('255.255.255.255', LAN_DISCOVERY_PORT),
        ('<broadcast>', LAN_DISCOVERY_PORT),
        ('127.0.0.1', LAN_DISCOVERY_PORT),
    )
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.12)
        deadline = time.monotonic() + timeout
        next_send = 0.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_send:
                for target in targets:
                    try:
                        sock.sendto(raw, target)
                    except OSError:
                        pass
                next_send = now + 0.25
            try:
                data, addr = sock.recvfrom(LAN_MAX_MESSAGE_BYTES)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get('type') != 'discover_reply' or not _is_protocol_supported(msg):
                continue
            if str(msg.get('code', '')) != room_code:
                continue
            try:
                port = _require_json_int(msg.get('port'))
            except ValueError:
                continue
            if 1 <= port <= 65535:
                return addr[0], port
    finally:
        if sock:
            sock.close()
    return None

def _draw_join_dialog(screen, font, text):
    rect = pygame.Rect(W // 2 - 180, H // 2 - 70, 360, 140)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 2)
    title = font.render('输入房间号 后按 Enter', True, (0, 0, 0))
    screen.blit(title, (rect.centerx - title.get_width() // 2, rect.y + 18))

    input_rect = pygame.Rect(rect.x + 32, rect.y + 58, rect.w - 64, 34)
    pygame.draw.rect(screen, (255, 255, 255), input_rect)
    pygame.draw.rect(screen, (60, 60, 60), input_rect, 1)
    shown = text if text else '例如 123456'
    color = (0, 0, 0) if text else (130, 130, 130)
    screen.blit(font.render(shown, True, color), (input_rect.x + 8, input_rect.y + 6))

    tip = font.render('自动搜索主机，也可写成 IP#房间号', True, (80, 80, 80))
    screen.blit(tip, (rect.centerx - tip.get_width() // 2, rect.y + 104))

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
    clock = pygame.time.Clock()
    F  = _get_font(40)
    Fh = _get_font(18)
    Fc = _get_font(15)
    Fr = _get_font(13)

    ai = ChessAI()
    board = [[C_NONE] * LINES for _ in range(LINES)]

    human, ai_side, turn = C_BLACK, C_WHITE, C_BLACK
    over, is_draw, last, win_line = False, False, None, None
    hist, score_log = [], []
    show_console, prev_console = False, False
    forbidden_rule = False
    pvp_mode = False
    ai_depth = AI_DEPTH
    show_diff_menu = False
    ai_hint = None
    notice, notice_until = '', 0
    btn_rects = []
    lan = None
    lan_mode = False
    lan_authenticated = False
    lan_room_code = ''
    lan_host_side = C_BLACK
    lan_game_id = 0
    lan_restart_local = False
    lan_restart_remote = False
    lan_undo_local = False
    lan_undo_remote = False
    lan_undo_move_no = None
    local_side, remote_side = None, None
    join_input, join_ip = False, ''
    lan_ip = _get_lan_ip()
    lan_discovery = None
    lan_turn_started_at = None
    lan_ping_seq = 0
    lan_pending_pings = {}
    lan_last_ping_at = 0
    lan_latency_ms = None
    lan_latency_updated_at = None
    forbidden_warm_started = False

    def quit_game():
        if lan_discovery:
            lan_discovery.close()
        if lan:
            if lan.connected:
                lan.send({'type': 'bye'})
            lan.close()
        pygame.quit()
        sys.exit()

    def reset_board(reset_sides=False):
        nonlocal board, human, ai_side, turn, over, is_draw, last, win_line, notice, show_diff_menu
        nonlocal ai_hint, lan_turn_started_at
        nonlocal lan_restart_local, lan_restart_remote, lan_undo_local, lan_undo_remote, lan_undo_move_no
        board = [[C_NONE] * LINES for _ in range(LINES)]
        if reset_sides:
            human, ai_side = C_BLACK, C_WHITE
        turn = C_BLACK
        over, is_draw, last, win_line = False, False, None, None
        ai_hint = None
        lan_turn_started_at = None
        notice = ''
        show_diff_menu = False
        lan_restart_local = False
        lan_restart_remote = False
        lan_undo_local = False
        lan_undo_remote = False
        lan_undo_move_no = None
        hist.clear()
        score_log.clear()

    def side_name(side):
        return '黑' if side == C_BLACK else '白'

    def set_lan_sides(host_side, is_host):
        nonlocal local_side, remote_side, human, ai_side
        if host_side not in (C_BLACK, C_WHITE):
            host_side = C_BLACK
        client_side = _opponent(host_side)
        if is_host:
            local_side, remote_side = host_side, client_side
        else:
            local_side, remote_side = client_side, host_side
        human, ai_side = local_side, remote_side

    def start_forbidden_warm_up():
        nonlocal forbidden_warm_started
        if forbidden_warm_started:
            return
        forbidden_warm_started = True
        threading.Thread(target=warm_up_forbidden_check, daemon=True).start()

    def warm_up_forbidden_check():
        try:
            warm_board = [[C_NONE] * LINES for _ in range(LINES)]
            ai.get_forbidden_reason(warm_board, LINES // 2, LINES // 2, C_BLACK)
        except Exception:
            pass

    def clear_lan_undo():
        nonlocal lan_undo_local, lan_undo_remote, lan_undo_move_no
        lan_undo_local = False
        lan_undo_remote = False
        lan_undo_move_no = None

    def clear_input_events_keep_quit():
        close_types = [pygame.QUIT]
        window_close = getattr(pygame, 'WINDOWCLOSE', None)
        if window_close is not None:
            close_types.append(window_close)
        close_events = [event for event in pygame.event.get() if event.type in close_types]
        for event in close_events:
            pygame.event.post(event)

    def clear_lan_latency():
        nonlocal lan_ping_seq, lan_pending_pings, lan_last_ping_at
        nonlocal lan_latency_ms, lan_latency_updated_at
        lan_ping_seq = 0
        lan_pending_pings = {}
        lan_last_ping_at = 0
        lan_latency_ms = None
        lan_latency_updated_at = None

    def update_lan_latency_probe():
        nonlocal lan_ping_seq, lan_last_ping_at, lan_latency_ms
        if not (lan_mode and lan_authenticated and lan and lan.connected):
            return
        now = pygame.time.get_ticks()
        if lan_latency_updated_at is not None and now - lan_latency_updated_at > LAN_PING_STALE_MS:
            lan_latency_ms = None
        for seq, sent_at in list(lan_pending_pings.items()):
            if now - sent_at > LAN_PING_STALE_MS:
                lan_pending_pings.pop(seq, None)
        if now - lan_last_ping_at < LAN_PING_INTERVAL_MS:
            return
        lan_ping_seq += 1
        lan_last_ping_at = now
        lan_pending_pings[lan_ping_seq] = now
        if not lan.send({'type': 'ping', 'seq': lan_ping_seq}):
            lan_pending_pings.pop(lan_ping_seq, None)

    def reset_lan_turn_timer():
        nonlocal lan_turn_started_at
        if lan_mode and lan_authenticated and not over:
            lan_turn_started_at = pygame.time.get_ticks()
        else:
            lan_turn_started_at = None

    def stop_lan_turn_timer():
        nonlocal lan_turn_started_at
        lan_turn_started_at = None

    def lan_time_left_seconds():
        if not (lan_mode and lan_authenticated and not over and lan_turn_started_at is not None):
            return None
        elapsed = pygame.time.get_ticks() - lan_turn_started_at
        return max(0, (LAN_TURN_MS - elapsed + 999) // 1000)

    def lan_timer_label():
        left = lan_time_left_seconds()
        return '' if left is None else f' | 限时:{left:02d}秒'

    def place_piece(r, c, color, record_score=True, lan_rules_only=False):
        nonlocal over, is_draw, last, win_line, turn, ai_hint
        if not (0 <= r < LINES and 0 <= c < LINES):
            return False, '请点击棋盘交叉点'
        if board[r][c] != C_NONE:
            return False, '这里已经有棋子'
        if color != turn:
            return False, '现在不是这一方回合'

        reason = None
        if forbidden_rule and color == C_BLACK:
            if lan_rules_only:
                reason = _get_forbidden_reason_fast(board, r, c, color)
            else:
                reason = ai.get_forbidden_reason(board, r, c, color)
        if reason:
            return False, f'{reason}: 黑棋不能下这里'

        board[r][c] = color
        last = (r, c)
        ai_hint = None
        hist.append((r, c))
        if lan_rules_only:
            clear_lan_undo()
        if record_score:
            score_log.append((len(hist), ai.evaluate(board).score))
        if lan_rules_only:
            over = _check_win_fast(board, r, c, color, forbidden_rule)
        else:
            over = ai.check_win(board, r, c, color, forbidden_rule)
        if over:
            win_line = _find_win_line(board, r, c, color, forbidden_rule)
            turn = color
            stop_lan_turn_timer()
            return True, ''
        if _check_draw(board):
            over = is_draw = True
            turn = color
            win_line = None
            stop_lan_turn_timer()
            return True, ''

        turn = _opponent(color)
        if lan_mode and lan_authenticated:
            reset_lan_turn_timer()
        return True, ''

    def start_lan_host():
        nonlocal lan, lan_mode, lan_authenticated, lan_room_code, pvp_mode
        nonlocal human, ai_side, turn, show_console, lan_game_id, notice, notice_until, lan_discovery
        if hist:
            notice, notice_until = _set_notice('开局后不能创建联机房间')
            return
        if lan:
            lan.close()
        if lan_discovery:
            lan_discovery.close()
        reset_board()
        clear_lan_latency()
        lan_game_id = 0
        show_console = False
        lan_room_code = f'{secrets.randbelow(10 ** LAN_ROOM_CODE_DIGITS):0{LAN_ROOM_CODE_DIGITS}d}'
        lan_authenticated = False
        lan = LanConnection(True, port=LAN_PORT)
        lan_discovery = LanDiscoveryResponder(lan_room_code, LAN_PORT)
        lan_mode = True
        pvp_mode = False
        set_lan_sides(lan_host_side, is_host=True)
        turn = C_BLACK
        notice, notice_until = _set_notice(
            f'房间号: {lan_room_code}，等待加入，你执{side_name(local_side)}'
        )

    def join_lan_host(target):
        nonlocal lan, lan_mode, lan_authenticated, lan_room_code, pvp_mode
        nonlocal human, ai_side, turn, show_console, lan_game_id, notice, notice_until
        host, port, room_code = _parse_join_target(target)
        if len(room_code) != LAN_ROOM_CODE_DIGITS or not room_code.isdigit():
            notice, notice_until = _set_notice(f'请输入 {LAN_ROOM_CODE_DIGITS} 位房间号')
            return False
        if not host:
            notice, notice_until = _set_notice(f'正在搜索房间 {room_code}...')
            pygame.display.flip()
            found = _discover_lan_host(room_code)
            if not found:
                notice, notice_until = _set_notice('未找到房间，可改用 主机IP#房间号')
                return False
            host, port = found
        if not host:
            notice, notice_until = _set_notice('请输入有效的主机 IP 或房间号')
            return False
        if hist:
            notice, notice_until = _set_notice('开局后不能加入联机房间')
            return False
        if lan:
            lan.close()
        reset_board()
        clear_lan_latency()
        lan_game_id = 0
        show_console = False
        lan_room_code = room_code
        lan_authenticated = False
        lan = LanConnection(False, host=host, port=port, room_code=room_code)
        lan_mode = True
        pvp_mode = False
        set_lan_sides(C_BLACK, is_host=False)
        turn = C_BLACK
        notice, notice_until = _set_notice(f'正在连接 {host}:{port}')
        return True

    def leave_lan_to_local(message, notify_remote=False):
        nonlocal lan, lan_mode, lan_authenticated, lan_room_code, pvp_mode, local_side, remote_side
        nonlocal lan_restart_local, lan_restart_remote, lan_undo_local, lan_undo_remote, lan_undo_move_no
        nonlocal notice, notice_until, lan_discovery, lan_turn_started_at, ai_hint
        if lan:
            if notify_remote and lan.connected:
                lan.send({'type': 'bye'})
            lan.close()
        if lan_discovery:
            lan_discovery.close()
            lan_discovery = None
        lan = None
        lan_mode = False
        lan_authenticated = False
        lan_room_code = ''
        lan_restart_local = False
        lan_restart_remote = False
        lan_undo_local = False
        lan_undo_remote = False
        lan_undo_move_no = None
        pvp_mode = True
        local_side, remote_side = None, None
        lan_turn_started_at = None
        ai_hint = None
        clear_lan_latency()
        notice, notice_until = _set_notice(message)

    def reopen_lan_host(message):
        nonlocal lan, lan_authenticated, lan_restart_local, lan_restart_remote
        nonlocal lan_undo_local, lan_undo_remote, lan_undo_move_no, notice, notice_until, lan_discovery
        nonlocal lan_turn_started_at
        if lan:
            lan.close()
        if lan_discovery:
            lan_discovery.close()
        lan_authenticated = False
        lan_restart_local = False
        lan_restart_remote = False
        lan_undo_local = False
        lan_undo_remote = False
        lan_undo_move_no = None
        lan_turn_started_at = None
        clear_lan_latency()
        lan = LanConnection(True, port=LAN_PORT)
        lan_discovery = LanDiscoveryResponder(lan_room_code, LAN_PORT)
        set_lan_sides(lan_host_side, is_host=True)
        notice, notice_until = _set_notice(message)

    def should_reopen_waiting_host():
        return bool(lan and lan.is_host and lan_mode and not lan_authenticated)

    def apply_lan_restart(next_host_side, swapped=False):
        nonlocal lan_host_side, lan_game_id, turn, notice, notice_until, lan_turn_started_at
        if next_host_side not in (C_BLACK, C_WHITE):
            next_host_side = lan_host_side
        lan_host_side = next_host_side
        set_lan_sides(lan_host_side, is_host=bool(lan and lan.is_host))
        reset_board()
        lan_game_id += 1
        turn = C_BLACK
        lan_turn_started_at = pygame.time.get_ticks()
        if swapped:
            notice, notice_until = _set_notice(f'已重开，双方黑白互换，你执{side_name(local_side)}')
        else:
            notice, notice_until = _set_notice(f'已重开，你执{side_name(local_side)}')

    def commit_lan_restart(send_remote=False):
        nonlocal notice, notice_until
        old_game_id = lan_game_id
        swapped = bool(over)
        next_host_side = _opponent(lan_host_side) if swapped else lan_host_side
        if send_remote and lan and lan.connected:
            ok = lan.send({
                'type': 'restart_commit',
                'game_id': old_game_id,
                'host_side': next_host_side,
                'swapped': swapped,
            })
            if not ok:
                notice, notice_until = _set_notice('重开确认发送失败')
                return
        apply_lan_restart(next_host_side, swapped)

    def request_lan_restart():
        nonlocal lan_restart_local, notice, notice_until
        if not lan_mode or not lan_authenticated or not lan or not lan.connected:
            notice, notice_until = _set_notice('联机尚未就绪')
            return
        if lan_restart_local:
            notice, notice_until = _set_notice('已请求重开，等待对方按 R')
            return
        lan_restart_local = True
        if not lan.send({'type': 'restart_request', 'game_id': lan_game_id}):
            lan_restart_local = False
            notice, notice_until = _set_notice('重开请求发送失败')
            return
        if lan_restart_remote:
            commit_lan_restart(send_remote=True)
        else:
            notice, notice_until = _set_notice('已请求重开，等待对方按 R')

    def apply_lan_undo(move_no):
        nonlocal turn, over, is_draw, last, win_line, ai_hint, notice, notice_until
        if move_no != len(hist) or not hist:
            notice, notice_until = _set_notice('悔棋手数不匹配，请双方重开')
            clear_lan_undo()
            return False
        r, c = hist.pop()
        removed_color = board[r][c]
        board[r][c] = C_NONE
        if score_log:
            score_log.pop()
        last = hist[-1] if hist else None
        turn = removed_color if removed_color in (C_BLACK, C_WHITE) else C_BLACK
        over = False
        is_draw = False
        win_line = None
        ai_hint = None
        reset_lan_turn_timer()
        clear_lan_undo()
        notice, notice_until = _set_notice(f'已悔棋，轮到{side_name(turn)}方')
        return True

    def commit_lan_undo(send_remote=False):
        nonlocal notice, notice_until
        move_no = len(hist)
        if move_no <= 0:
            notice, notice_until = _set_notice('当前没有可悔棋的落子')
            clear_lan_undo()
            return
        if send_remote and lan and lan.connected:
            ok = lan.send({
                'type': 'undo_commit',
                'game_id': lan_game_id,
                'move_no': move_no,
            })
            if not ok:
                notice, notice_until = _set_notice('悔棋确认发送失败')
                return
        apply_lan_undo(move_no)

    def request_lan_undo():
        nonlocal lan_undo_local, lan_undo_remote, lan_undo_move_no, notice, notice_until
        if not lan_mode or not lan_authenticated or not lan or not lan.connected:
            notice, notice_until = _set_notice('联机尚未就绪')
            return
        move_no = len(hist)
        if move_no <= 0:
            notice, notice_until = _set_notice('当前没有可悔棋的落子')
            return
        if lan_undo_local:
            notice, notice_until = _set_notice('已请求悔棋，等待对方右键同意')
            return
        if lan_undo_move_no is not None and lan_undo_move_no != move_no:
            clear_lan_undo()
        lan_undo_local = True
        lan_undo_move_no = move_no
        if not lan.send({'type': 'undo_request', 'game_id': lan_game_id, 'move_no': move_no}):
            clear_lan_undo()
            notice, notice_until = _set_notice('悔棋请求发送失败')
            return
        if lan_undo_remote:
            commit_lan_undo(send_remote=True)
        else:
            notice, notice_until = _set_notice('已请求悔棋，等待对方右键同意')

    def finish_lan_timeout(loser, send_remote=False):
        nonlocal over, is_draw, turn, win_line, ai_hint, notice, notice_until
        if loser not in (C_BLACK, C_WHITE):
            return
        winner = _opponent(loser)
        over = True
        is_draw = False
        turn = winner
        win_line = None
        ai_hint = None
        stop_lan_turn_timer()
        clear_lan_undo()
        if loser == local_side:
            notice, notice_until = _set_notice(f'你超时，{side_name(winner)}方胜')
        else:
            notice, notice_until = _set_notice(f'对方超时，{side_name(winner)}方胜')
        if send_remote and lan and lan.connected:
            ok = lan.send({
                'type': 'timeout',
                'game_id': lan_game_id,
                'move_no': len(hist),
                'loser': loser,
            })
            if not ok:
                leave_lan_to_local('超时结果发送失败，已切换为本地双人')

    def check_lan_turn_timeout():
        if not (lan_mode and lan_authenticated and lan and lan.connected and not over):
            return
        if turn != local_side:
            return
        if lan_turn_started_at is None:
            reset_lan_turn_timer()
            return
        if pygame.time.get_ticks() - lan_turn_started_at >= LAN_TURN_MS:
            finish_lan_timeout(local_side, send_remote=True)

    def lan_status_text():
        if not lan_mode:
            return ''
        if lan and lan.connected and lan_authenticated:
            if lan_undo_remote:
                return '对方请求悔棋，右键同意'
            if lan_undo_local:
                return '已请求悔棋，等待对方右键'
            if lan_restart_remote:
                return '对方请求重开，按 R 同意'
            if lan_restart_local:
                return '已请求重开，等待对方按 R'
            who = '你' if turn == local_side else '对方'
            return f'已连接 | 你执{side_name(local_side)} | 当前回合: {who}{lan_timer_label()}'
        if lan and lan.is_host:
            if lan.connected:
                return f'等待验证 | 主机执{side_name(lan_host_side)}'
            return f'等待加入 | 房间号:{lan_room_code} | 手动IP:{lan_ip}'
        if lan and lan.connected:
            return '已连接主机，等待开局同步'
        return '正在连接主机...'

    def toggle_lan_host_side():
        nonlocal lan_host_side, turn, notice, notice_until
        if hist or not lan_mode or lan_authenticated or not lan or not lan.is_host:
            return
        lan_host_side = _opponent(lan_host_side)
        set_lan_sides(lan_host_side, is_host=True)
        turn = C_BLACK
        notice, notice_until = _set_notice(f'主机已切换为执{side_name(lan_host_side)}')

    def handle_lan_messages():
        nonlocal local_side, remote_side, forbidden_rule, human, ai_side, turn, lan_mode, pvp_mode, lan_host_side
        nonlocal lan_authenticated, lan_restart_remote, lan_undo_remote, lan_undo_move_no
        nonlocal notice, notice_until, lan_discovery, lan_latency_ms, lan_latency_updated_at
        if not lan:
            return
        current_lan = lan
        for item in current_lan.poll():
            if not lan or lan is not current_lan:
                break
            if not isinstance(item, dict):
                continue
            event = item.get('_event')
            if event == 'listening':
                notice, notice_until = _set_notice(
                    f'房间号: {lan_room_code}，等待加入，主机执{side_name(lan_host_side)}'
                )
                continue
            if event == 'connected':
                if lan.is_host:
                    if lan_discovery:
                        lan_discovery.close()
                        lan_discovery = None
                    notice, notice_until = _set_notice('对方已连接，等待房间码验证')
                else:
                    notice, notice_until = _set_notice('已连接主机，等待开局同步')
                continue
            if event == 'closed':
                if should_reopen_waiting_host():
                    reopen_lan_host('连接已断开，继续等待加入')
                else:
                    leave_lan_to_local('联机已断开，已切换为本地双人')
                continue
            if event == 'protocol_error':
                if should_reopen_waiting_host():
                    reopen_lan_host(f'握手失败: {item.get("message", "未知错误")}，继续等待')
                else:
                    leave_lan_to_local(f'联机协议错误: {item.get("message", "未知错误")}')
                continue
            if event == 'error':
                if should_reopen_waiting_host():
                    reopen_lan_host(f'连接错误: {item.get("message", "未知错误")}，继续等待')
                else:
                    leave_lan_to_local(f'联机错误: {item.get("message", "未知错误")}')
                continue

            if event != 'message':
                continue

            msg = item.get('payload')
            if not isinstance(msg, dict):
                leave_lan_to_local('收到异常联机消息')
                continue
            if not _is_protocol_supported(msg):
                if should_reopen_waiting_host():
                    lan.send({'type': 'reject', 'reason': '版本不一致，请使用新版程序'})
                    reopen_lan_host('对方版本不一致，继续等待加入')
                else:
                    leave_lan_to_local('联机协议版本不匹配')
                continue
            kind = msg.get('type')
            if kind == 'bye':
                leave_lan_to_local('对方已退出联机，已切换为本地双人')
                continue
            if kind == 'hello':
                if lan.is_host:
                    code = str(msg.get('code', ''))
                    if code != lan_room_code:
                        lan.send({'type': 'reject', 'reason': '房间码错误'})
                        reopen_lan_host('房间码错误，继续等待加入')
                    else:
                        lan_authenticated = True
                        set_lan_sides(lan_host_side, is_host=True)
                        turn = C_BLACK
                        reset_lan_turn_timer()
                        lan_mode, pvp_mode = True, False
                        ok = lan.send({
                            'type': 'start',
                            'forbidden_rule': forbidden_rule,
                            'host_side': lan_host_side,
                        })
                        if ok:
                            notice, notice_until = _set_notice(f'验证通过，你执{side_name(local_side)}')
                        else:
                            leave_lan_to_local('开局同步发送失败，已切换为本地双人')
                continue
            if kind == 'reject':
                reason = str(msg.get('reason', '加入被拒绝'))[:40]
                leave_lan_to_local(f'加入失败: {reason}')
                continue
            if kind == 'start':
                if lan.is_host or lan_authenticated:
                    continue
                try:
                    host_side = _require_json_int(msg.get('host_side'))
                    remote_forbidden_rule = _require_json_bool(msg.get('forbidden_rule'))
                except (TypeError, ValueError):
                    leave_lan_to_local('收到异常开局数据')
                    continue
                if host_side not in (C_BLACK, C_WHITE):
                    leave_lan_to_local('收到异常开局数据')
                    continue
                forbidden_rule = remote_forbidden_rule
                reset_board()
                lan_authenticated = True
                lan_host_side = host_side
                set_lan_sides(host_side, is_host=False)
                turn = C_BLACK
                reset_lan_turn_timer()
                lan_mode, pvp_mode = True, False
                notice, notice_until = _set_notice(f'开局同步完成，你执{side_name(local_side)}')
                continue
            if not lan_authenticated:
                continue
            if kind == 'ping':
                try:
                    seq = _require_json_int(msg.get('seq'))
                except (TypeError, ValueError):
                    continue
                lan.send({'type': 'pong', 'seq': seq})
                continue
            if kind == 'pong':
                try:
                    seq = _require_json_int(msg.get('seq'))
                except (TypeError, ValueError):
                    continue
                sent_at = lan_pending_pings.pop(seq, None)
                if sent_at is not None:
                    now = pygame.time.get_ticks()
                    lan_latency_ms = max(0, now - sent_at)
                    lan_latency_updated_at = now
                continue
            if kind == 'restart_request':
                try:
                    game_id = _require_json_int(msg.get('game_id'))
                except (TypeError, ValueError):
                    notice, notice_until = _set_notice('收到异常重开请求')
                    continue
                if game_id != lan_game_id:
                    continue
                lan_restart_remote = True
                if lan_restart_local:
                    commit_lan_restart(send_remote=True)
                else:
                    notice, notice_until = _set_notice('对方请求重开，按 R 同意')
                continue
            if kind == 'restart_commit':
                try:
                    game_id = _require_json_int(msg.get('game_id'))
                    host_side = _require_json_int(msg.get('host_side'))
                except (TypeError, ValueError):
                    notice, notice_until = _set_notice('收到异常重开确认')
                    continue
                if game_id != lan_game_id:
                    continue
                if not lan_restart_local:
                    notice, notice_until = _set_notice('收到未请求的重开确认，已忽略')
                    continue
                if not lan_restart_remote:
                    notice, notice_until = _set_notice('收到未配对的重开确认，已忽略')
                    continue
                if host_side not in (C_BLACK, C_WHITE):
                    notice, notice_until = _set_notice('收到异常重开确认')
                    continue
                expected_swapped = bool(over)
                expected_host_side = _opponent(lan_host_side) if expected_swapped else lan_host_side
                if host_side != expected_host_side:
                    notice, notice_until = _set_notice('收到不匹配的重开确认，已忽略')
                    continue
                apply_lan_restart(expected_host_side, expected_swapped)
                continue
            if kind == 'undo_request':
                try:
                    game_id = _require_json_int(msg.get('game_id'))
                    move_no = _require_json_int(msg.get('move_no'))
                except (TypeError, ValueError):
                    notice, notice_until = _set_notice('收到异常悔棋请求')
                    continue
                if game_id != lan_game_id:
                    continue
                if move_no != len(hist) or not hist:
                    notice, notice_until = _set_notice('收到过期悔棋请求，已忽略')
                    clear_lan_undo()
                    continue
                if lan_undo_move_no is not None and lan_undo_move_no != move_no:
                    notice, notice_until = _set_notice('收到不匹配的悔棋请求，已忽略')
                    continue
                lan_undo_remote = True
                lan_undo_move_no = move_no
                if lan_undo_local:
                    commit_lan_undo(send_remote=True)
                else:
                    notice, notice_until = _set_notice('对方请求悔棋，右键同意')
                continue
            if kind == 'undo_commit':
                try:
                    game_id = _require_json_int(msg.get('game_id'))
                    move_no = _require_json_int(msg.get('move_no'))
                except (TypeError, ValueError):
                    notice, notice_until = _set_notice('收到异常悔棋确认')
                    continue
                if game_id != lan_game_id:
                    continue
                if not lan_undo_local or lan_undo_move_no != move_no:
                    notice, notice_until = _set_notice('收到未请求的悔棋确认，已忽略')
                    continue
                apply_lan_undo(move_no)
                continue
            if kind == 'timeout':
                if over:
                    continue
                try:
                    game_id = _require_json_int(msg.get('game_id'))
                    move_no = _require_json_int(msg.get('move_no'))
                    loser = _require_json_int(msg.get('loser'))
                except (TypeError, ValueError):
                    notice, notice_until = _set_notice('收到异常超时数据')
                    continue
                if game_id != lan_game_id:
                    continue
                if move_no != len(hist):
                    notice, notice_until = _set_notice('收到超时数据但棋局不同步')
                    continue
                if loser != remote_side or turn != remote_side:
                    notice, notice_until = _set_notice('收到异常超时数据')
                    continue
                finish_lan_timeout(remote_side, send_remote=False)
                continue
            if kind == 'move':
                if over:
                    continue
                try:
                    r = _require_json_int(msg.get('row'))
                    c = _require_json_int(msg.get('col'))
                    color = _require_json_int(msg.get('color'))
                    game_id = _require_json_int(msg.get('game_id'))
                    move_no = _require_json_int(msg.get('move_no'))
                except (KeyError, TypeError, ValueError):
                    notice, notice_until = _set_notice('收到异常落子数据')
                    continue
                if game_id != lan_game_id:
                    continue
                if color != remote_side:
                    notice, notice_until = _set_notice('收到异常棋子颜色')
                    continue
                if move_no != len(hist) + 1:
                    notice, notice_until = _set_notice('棋局不同步，请双方重开')
                    continue
                ok, reason = place_piece(r, c, color, record_score=False, lan_rules_only=True)
                if not ok:
                    notice, notice_until = _set_notice(reason)
                continue

    while True:
        clock.tick(LAN_FRAME_RATE)
        handle_lan_messages()
        update_lan_latency_probe()
        check_lan_turn_timeout()
        if lan_mode and show_console:
            show_console = False

        if show_console != prev_console:
            prev_console = show_console
            tw = W + CONSOLE_W if show_console else W
            screen = pygame.display.set_mode((tw, H))
        _draw_board(screen)
        _draw_pieces(screen, board, last)
        _draw_win_line(screen, win_line)
        _draw_ai_hint(screen, ai_hint)
        _draw_lan_latency(screen, Fh, lan_mode, lan_authenticated, lan_latency_ms)

        # ── 提示栏 (采用双行显示以节省空间) ──
        if not over:
            mode_str = "局域网" if lan_mode else ("双人" if pvp_mode else "人机")
            diff_str = _difficulty_name(ai_depth)
            if lan_mode:
                if not lan_authenticated:
                    if lan and lan.is_host:
                        s1 = f'A换色 | D禁手:{"开" if forbidden_rule else "关"} | Esc退出 | 模式: {mode_str}'
                    else:
                        s1 = f'等待开局同步 | Esc退出 | 模式: {mode_str}'
                elif not hist:
                    s1 = f'左键落子 | R重开 | Esc退出 | 模式: {mode_str} | 禁手:{"开" if forbidden_rule else "关"}'
                else:
                    s1 = f'末子: {side_name(_opponent(turn))} | 右键悔棋 | R重开 | Esc退出'
                s2 = lan_status_text()
            else:
                if not hist:
                    if pvp_mode:
                        s1 = f'左键落子 | E模式:{mode_str} | D禁手:{"开" if forbidden_rule else "关"} | N主机 | J加入'
                        s2 = '当前为本地双人，黑方先行 | C控制台'
                    else:
                        s1 = f'左键落子 | E模式:{mode_str} | A先后:{"黑先" if human == C_BLACK else "白后"} | D禁手:{"开" if forbidden_rule else "关"}'
                        s2 = f'F难度:{diff_str} | N创建局域网主机 | J加入主机 | C控制台'
                else:
                    s1 = f'末子: {"黑" if turn == C_WHITE else "白"} | 右键悔棋 | C控制台 | 模式: {mode_str}'
                    if pvp_mode:
                        s2 = f'禁手:{"开" if forbidden_rule else "关"} | 当前回合: {"黑" if turn == C_BLACK else "白"}'
                    else:
                        s2 = f'禁手:{"开" if forbidden_rule else "关"} | B AI提示 | F难度:{diff_str}'
            screen.blit(Fh.render(s1, True, (0, 0, 180)), (10, 2))
            screen.blit(Fh.render(s2, True, (0, 0, 180)), (10, 22))

        if notice:
            if pygame.time.get_ticks() < notice_until:
                screen.blit(Fh.render(notice, True, (180, 0, 0)), (MARGIN, H - 28))
            else:
                notice = ''

        if show_console and not lan_mode:
            _draw_console(screen, Fc, score_log, board, ai, Fr, forbidden_rule)

        if over:
            if lan_mode:
                if is_draw: t = F.render('平局（R重开 / 右键悔棋）', True, (255, 0, 0))
                else: t = F.render(f'{side_name(turn)}子胜（R重开 / 右键悔棋）', True, (255, 0, 0))
            else:
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

        if join_input:
            _draw_join_dialog(screen, Fh, join_ip)

        pygame.display.flip()

        # ── 游戏结束处理 ──
        if over:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    quit_game()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_c and not lan_mode:
                        show_console = not show_console
                    if e.key == pygame.K_r and lan_mode:
                        request_lan_restart()
                    if e.key == pygame.K_ESCAPE and lan_mode:
                        leave_lan_to_local('已退出联机，切换为本地双人', notify_remote=True)
                if e.type == pygame.MOUSEBUTTONDOWN:
                    if lan_mode:
                        if e.button == 3:
                            request_lan_undo()
                        else:
                            notice, notice_until = _set_notice('联机结束后按 R 重开，右键请求悔棋')
                    else:
                        reset_board(reset_sides=True)
            continue

        # ── AI 自动回合 ──
        if not lan_mode and not pvp_mode and turn == ai_side:
            pygame.display.set_caption('五子棋（AI 思考中...）')
            pygame.event.pump()
            action = ai.get_action(board, depth=ai_depth, ai_color=ai_side, forbidden_rule=forbidden_rule)
            clear_input_events_keep_quit()
            if action is None:
                over = is_draw = True
            else:
                x, y = action
                ok, _ = place_piece(x, y, ai_side)
                if not ok:
                    turn = human
            pygame.display.set_caption('五子棋')

        # ── 玩家输入事件 ──
        assist = False
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                quit_game()

            if join_input:
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN:
                        if join_lan_host(join_ip):
                            join_input = False
                            pygame.key.stop_text_input()
                    elif e.key == pygame.K_ESCAPE:
                        join_input = False
                        pygame.key.stop_text_input()
                    elif e.key == pygame.K_BACKSPACE:
                        join_ip = join_ip[:-1]
                    elif e.unicode and len(join_ip) < 64 and e.unicode in '0123456789.:#':
                        join_ip += e.unicode
                continue

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_n and not hist and not over and not lan_mode:
                    start_lan_host()
                if e.key == pygame.K_j and not hist and not over and not lan_mode:
                    join_input = True
                    join_ip = ''
                    show_diff_menu = False
                    pygame.key.start_text_input()
                if e.key == pygame.K_ESCAPE and lan_mode:
                    leave_lan_to_local('已退出联机，切换为本地双人', notify_remote=True)
                if e.key == pygame.K_r and lan_mode:
                    request_lan_restart()
                if e.key == pygame.K_a and lan_mode:
                    toggle_lan_host_side()
                if e.key == pygame.K_d and not hist and not over and lan_mode and lan and lan.is_host and not lan_authenticated:
                    forbidden_rule = not forbidden_rule
                    notice, notice_until = _set_notice(f'联机禁手规则已{"开启" if forbidden_rule else "关闭"}')
                if e.key == pygame.K_f and not pvp_mode and not lan_mode:
                    show_diff_menu = not show_diff_menu
                if e.key == pygame.K_e and not hist and not over and not lan_mode:
                    pvp_mode = not pvp_mode
                    ai_hint = None
                    notice, notice_until = _set_notice(f'已切换为 {"双人对战" if pvp_mode else "人机对战"}')
                if e.key == pygame.K_a and not pvp_mode and not hist and not over and not lan_mode:
                    if human == C_BLACK: human, ai_side = C_WHITE, C_BLACK
                    else:                human, ai_side = C_BLACK, C_WHITE
                    turn = C_BLACK
                    ai_hint = None
                if e.key == pygame.K_d and not hist and not over and not lan_mode:
                    forbidden_rule = not forbidden_rule
                    ai_hint = None
                    if forbidden_rule:
                        start_forbidden_warm_up()
                    notice, notice_until = _set_notice(f'本局禁手规则已{"开启" if forbidden_rule else "关闭"}')
                if e.key == pygame.K_b and not pvp_mode and not lan_mode and turn == human and not over:
                    assist = True
                if e.key == pygame.K_c and not lan_mode:
                    show_console = not show_console
            if e.type == pygame.MOUSEBUTTONDOWN and not over and not assist:
                if show_diff_menu:
                    if e.button == 1:
                        mx, my = e.pos
                        for brect, val in btn_rects:
                            if brect.collidepoint(mx, my):
                                ai_depth = val
                                ai_hint = None
                                notice, notice_until = _set_notice(f'AI 难度已设为 {_difficulty_name(val)}')
                                show_diff_menu = False
                                break
                        else:
                            if not pygame.Rect(W // 2 - 100, H // 2 - 145, 200, 290).collidepoint(mx, my):
                                show_diff_menu = False
                    continue
                
                if lan_mode:
                    if e.button == 1:
                        if not lan or not lan.connected:
                            notice, notice_until = _set_notice('等待对方连接')
                        elif not lan_authenticated:
                            notice, notice_until = _set_notice('等待联机同步')
                        elif turn != local_side:
                            notice, notice_until = _set_notice('还没轮到你')
                        else:
                            mx, my = e.pos
                            r = round((my - TOP_MARGIN) / BLOCK)
                            c = round((mx - MARGIN) / BLOCK)
                            if 0 <= r < LINES and 0 <= c < LINES:
                                ok, reason = place_piece(r, c, local_side, record_score=False, lan_rules_only=True)
                                if ok:
                                    sent = lan.send({
                                        'type': 'move',
                                        'game_id': lan_game_id,
                                        'row': r,
                                        'col': c,
                                        'color': local_side,
                                        'move_no': len(hist),
                                    })
                                    if not sent:
                                        leave_lan_to_local('落子发送失败，已切换为本地双人')
                                else:
                                    notice, notice_until = _set_notice(reason)
                    elif e.button == 3:
                        request_lan_undo()
                    continue

                if pvp_mode:
                    if e.button == 1:
                        mx, my = e.pos
                        r = round((my - TOP_MARGIN) / BLOCK)
                        c = round((mx - MARGIN) / BLOCK)
                        if 0 <= r < LINES and 0 <= c < LINES:
                            ok, reason = place_piece(r, c, turn)
                            if not ok:
                                notice, notice_until = _set_notice(reason)
                    elif e.button == 3 and len(hist) >= 1:
                        a = hist.pop(); board[a[0]][a[1]] = C_NONE
                        last = hist[-1] if hist else None
                        turn = _opponent(turn)
                        ai_hint = None
                        notice = ''
                        if score_log: score_log.pop()
                else:
                    if turn == human:
                        if e.button == 1:
                            mx, my = e.pos
                            r = round((my - TOP_MARGIN) / BLOCK)
                            c = round((mx - MARGIN) / BLOCK)
                            if 0 <= r < LINES and 0 <= c < LINES:
                                ok, reason = place_piece(r, c, human)
                                if not ok:
                                    notice, notice_until = _set_notice(reason)
                        elif e.button == 3 and len(hist) >= 2:
                            a = hist.pop(); board[a[0]][a[1]] = C_NONE
                            p = hist.pop(); board[p[0]][p[1]] = C_NONE
                            last = hist[-1] if hist else None
                            turn = human
                            ai_hint = None
                            notice = ''
                            if score_log: score_log.pop()
                            if score_log: score_log.pop()

        # ── B 键 AI 提示 ──
        if assist:
            pygame.display.set_caption('五子棋（AI 提示思考中...）')
            pygame.event.pump()
            action = ai.get_action(board, depth=ai_depth, ai_color=human, forbidden_rule=forbidden_rule)
            clear_input_events_keep_quit()
            if action is None:
                ai_hint = None
                notice, notice_until = _set_notice('没有可下的合法点')
            else:
                ai_hint = action
                notice, notice_until = _set_notice('AI 建议点已标出')
            pygame.display.set_caption('五子棋')

if __name__ == '__main__':
    main()
