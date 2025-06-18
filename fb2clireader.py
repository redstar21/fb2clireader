import os
import sys
import json
import textwrap
import curses
import zipfile
from lxml import etree

# Путь к скрытому файлу состояния в домашней директории
STATE_FILE = os.path.join(os.path.expanduser("~"), ".fb2_reader_state.json")


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def extract_text_from_fb2(path):
    if path.endswith(".zip"):
        with zipfile.ZipFile(path, 'r') as zip_ref:
            fb2_names = [name for name in zip_ref.namelist() if name.endswith(".fb2")]
            if not fb2_names:
                return []
            with zip_ref.open(fb2_names[0]) as fb2_file:
                parser = etree.XMLParser(recover=True)
                tree = etree.parse(fb2_file, parser)
    else:
        parser = etree.XMLParser(recover=True)
        tree = etree.parse(path, parser)

    ns = {'fb2': 'http://www.gribuser.ru/xml/fictionbook/2.0'}
    paragraphs = tree.xpath('.//fb2:body//fb2:section//fb2:p', namespaces=ns)

    result = []
    for p in paragraphs:
        text = etree.tostring(p, encoding="unicode", method="text").strip()
        if text:
            result.append(text)
    return result


def wrap_lines(paragraphs, column_width, indent=2):
    wrapped = []
    for para in paragraphs:
        if para.isupper() and len(para) < 80:
            wrapped.extend(textwrap.wrap(para, column_width))
        else:
            wrapped.extend(textwrap.wrap(para, width=column_width,
                                         initial_indent=' ' * indent,
                                         subsequent_indent=''))
    return wrapped


def paginate_double_column(lines, lines_per_column):
    pages = []
    total_lines_per_page = lines_per_column * 2
    for i in range(0, len(lines), total_lines_per_page):
        page = lines[i:i + total_lines_per_page]
        pages.append(page)
    return pages


def reader(stdscr, paragraphs, current_page, book_id):
    curses.curs_set(0)
    stdscr.nodelay(False)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(2, curses.COLOR_WHITE, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)

    attr_normal = curses.color_pair(2)
    attr_bold = curses.color_pair(3) | curses.A_BOLD

    while True:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        if max_y < 5 or max_x < 40:
            stdscr.addstr(0, 0, "Слишком маленькое окно.", attr_normal)
            stdscr.refresh()
            stdscr.getch()
            continue

        top_padding = 1
        bottom_padding = 1
        left_padding = 2
        column_spacing = 4
        column_width = (max_x - left_padding - column_spacing) // 2
        lines_per_column = max_y - top_padding - bottom_padding

        wrapped_lines = wrap_lines(paragraphs, column_width)
        pages = paginate_double_column(wrapped_lines, lines_per_column)
        total_pages = len(pages)

        if current_page >= total_pages:
            current_page = total_pages - 1

        page = pages[current_page]
        left_column = page[:lines_per_column]
        right_column = page[lines_per_column:lines_per_column * 2]

        for i, line in enumerate(left_column):
            attr = attr_bold if line.isupper() and len(line) < 80 else attr_normal
            stdscr.addstr(i + top_padding, left_padding, line[:column_width], attr)

        for i, line in enumerate(right_column):
            attr = attr_bold if line.isupper() and len(line) < 80 else attr_normal
            stdscr.addstr(i + top_padding, left_padding + column_width + column_spacing, line[:column_width], attr)

        page_str = f"стр. {current_page + 1} / {total_pages}"
        stdscr.addstr(max_y - 1, max_x - len(page_str) - 5, page_str, attr_normal)

        stdscr.refresh()

        try:
            key = stdscr.get_wch()
        except curses.error:
            continue

        if key == curses.KEY_RIGHT and current_page < total_pages - 1:
            current_page += 1
        elif key == curses.KEY_LEFT and current_page > 0:
            current_page -= 1
        elif key in ('q', 'й'):
            state = load_state()
            state[book_id] = current_page
            save_state(state)
            break


def main():
    if len(sys.argv) < 2:
        print("Использование: python fb2_reader_curses.py путь_к_книге.fb2[.zip]")
        return

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print("Файл не найден:", file_path)
        return

    book_id = os.path.basename(file_path)
    state = load_state()
    current_page = state.get(book_id, 0)

    print("Загрузка файла...")
    paragraphs = extract_text_from_fb2(file_path)
    if not paragraphs:
        print("Не удалось извлечь текст из файла.")
        return

    curses.wrapper(lambda stdscr: reader(stdscr, paragraphs, current_page, book_id))


if __name__ == "__main__":
    main()

