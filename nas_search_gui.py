"""NAS_search_GUI: Программа для поиска фильмов по индексу."""
# [x] Написать класс инициализации индекса (nas.txt)
# [x] Добавить пункт - "открыть файл индекса nas.txt"
# [x] Таймер при создании индекса
# [x] Параметр запуска для создания индекса
# [ ] Файл настроек или настройки в реестре?
# [ ] Добавить поиск дублей в базе

import ctypes
import os, sys, re
import threading
from glob import glob, iglob
from datetime import datetime, timedelta
import time
import subprocess

import argparse_ru
import argparse

import wx
import wx.adv
from pymediainfo import MediaInfo
import winutils

ctypes.windll.shcore.SetProcessDpiAwareness(2)

VER = '0.1.13'


def convert_bytes(num):
    """
    Converts bytes to MB.... GB... etc
    """
    for x in ['bytes', 'K', 'M', 'G', 'T']:
        if num < 1024.0:
            return f'{num:3.1f}{x}'
        num /= 1024.0


def check_mark(check: bool):
    if check:
        return "\u2714"
    else:
        return "\u274C"


def get_resource_path(relative_path):
    '''
    Определение пути для запуска из автономного exe файла.
    Pyinstaller cоздает временную папку, путь в _MEIPASS.
    '''
    try:
        base_path = sys._MEIPASS  # type: ignore
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def file_to_list(file: str):
    """
    Reads text file and returns list of strings
    """
    if os.path.isfile(file):
        with open(file, 'r', encoding='utf-8') as f:
            list = [x.strip() for x in f if not x.strip() == '']
        return list
    else:
        return []


def nas_scan(path, file_name='nas.txt', save_file=True):

    paths = glob(os.path.join(path, '\\**\\*.mp4'), recursive=True)
    if save_file:
        with open(file_name, 'w', encoding="utf-8") as file:
            for item in paths:
                file.write(item + "\n")


def nas_scan1(path, file_name, save_file=True):
    global stop_flag, result
    paths = []
    for i in iglob(os.path.join(path, '\\**\\*.mp4'), recursive=True):
        if stop_flag:
            result = False
            return
        paths.append(i)
    if save_file:
        with open(file_name, 'w', encoding="utf-8") as file:
            date = datetime.now().strftime('%d.%m.%Y')
            file.write(date + "\n")
            for item in paths:
                file.write(item + "\n")


class Mp4Info:

    def __init__(self, file) -> None:
        self.media_info = MediaInfo.parse(file)
        self.width = 0
        self.height = 0
        self.tags = False
        for track in self.media_info.tracks:  # type: ignore
            if track.track_type == "Video":
                self.width, self.height = track.width, track.height
        self.data = self.media_info.tracks[0].to_data()  # type: ignore
        self.filesize = self.data['file_size']
        if "title" in self.data and 'description' in self.data and 'longdescription' in self.data and self.data['cover'] == "Yes":
            self.tags = True


class NasIndex:

    def __init__(self, index_path):
        self.paths = []
        self.file_names = []
        if os.path.isfile(index_path):
            self.paths, self.file_names = self.load_nas_file(index_path)
            self.ready = True
        else:
            self.ready = False

    def is_ready(self):
        return self.ready

    def load_nas_file(self, nas_location):
        paths = file_to_list(nas_location)
        self.date = paths.pop(0)
        if paths:
            file_names = [os.path.splitext(os.path.basename(x))[0] for x in paths]
            return paths, file_names
        else:
            return [], []


class FileLocation(wx.Dialog):

    def __init__(self, parent, title, srs, dest):
        super().__init__(parent, title=title)
        self.SetClientSize(self.FromDIP(wx.Size((400, 100))))
        self.CentreOnParent()

        self.panel = wx.Panel(self)
        self.box1v = wx.BoxSizer(wx.VERTICAL)
        self.box1g = wx.BoxSizer(wx.HORIZONTAL)
        self.box2g = wx.BoxSizer(wx.HORIZONTAL)

        self.label1 = wx.StaticText(self.panel, label="Сетевой диск NAS:")
        self.t_nas_location = wx.TextCtrl(self.panel, value=srs)
        self.b_open_folder = wx.Button(self.panel, wx.ID_ANY, label="Открыть", size=self.FromDIP((60, 25)))
        self.Bind(wx.EVT_BUTTON, self.onOpenFolder, id=self.b_open_folder.GetId())
        self.box1g.Add(self.label1, flag=wx.ALIGN_CENTRE_VERTICAL | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.box1g.Add(self.t_nas_location, proportion=1, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.box1g.Add(self.b_open_folder, flag=wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)

        self.btn_ok = wx.Button(self.panel, wx.ID_OK, label="Начать", size=self.FromDIP((100, 25)))
        self.btn_cancel = wx.Button(self.panel, wx.ID_CANCEL, label="Отмена", size=self.FromDIP((100, 25)))
        self.box2g.Add(self.btn_ok, flag=wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.box2g.Add(self.btn_cancel, flag=wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)

        self.box1v.Add(self.box1g, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.box1v.Add(self.box2g, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.panel.SetSizer(self.box1v)

    def onOpenFolder(self, event):
        with wx.DirDialog(None, "Выбор NAS...", "", wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as d_dialog:
            if d_dialog.ShowModal() == wx.ID_CANCEL:
                return
            d_path = d_dialog.GetPath()
        self.t_nas_location.Value = d_path


class IndexingPanel(wx.Dialog):

    def __init__(self, parent, title, srs, dest):
        super().__init__(parent, title=title)

        self.panel = wx.Panel(self)
        self.box1v = wx.BoxSizer(wx.VERTICAL)

        self.label1 = wx.StaticText(self.panel, label="Выполняется сканирование...")
        self.progress = wx.Gauge(self.panel, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.btn_cancel = wx.Button(self.panel, wx.ID_OK, label="Отмена", size=self.FromDIP((100, 25)))

        self.box1v.Add(self.label1, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.box1v.Add(self.progress, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.box1v.Add(self.btn_cancel, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.Bind(wx.EVT_BUTTON, self.onCancel, id=self.btn_cancel.GetId())
        self.panel.SetSizer(self.box1v)

        self.progress.Pulse()
        self.SetClientSize(self.FromDIP(wx.Size((300, 80))))
        self.CentreOnParent()
        self.Show()

        global stop_flag, result
        stop_flag = False
        result = True
        self.scan(srs, dest, self.label1)
        self.Hide()
        if result:
            wx.MessageDialog(self, 'Создание индекса завершено!', 'Создание индекса', wx.OK | wx.ICON_INFORMATION).ShowModal()
        else:
            wx.MessageDialog(self, 'Создание индекса отменено!', 'Создание индекса', wx.OK | wx.ICON_WARNING).ShowModal()
        self.Destroy()

    @staticmethod
    def scan(srs, dest, label):
        index_thr = threading.Thread(target=nas_scan1, args=(srs, dest))
        index_thr.daemon = True
        sw = wx.StopWatch()
        index_thr.start()
        while index_thr.is_alive():
            time.sleep(0.1)
            timer = datetime.fromtimestamp(sw.Time() / 1000.0).strftime("%M:%S")
            label.Label = f"Выполняется сканирование... {timer}"
            wx.GetApp().Yield()
            continue

    def onCancel(self, event):
        global stop_flag
        stop_flag = True


class NotFoundPanel(wx.Dialog):

    def __init__(self, parent, title, not_found: list):
        super().__init__(parent, title=title)

        self.panel = wx.Panel(self)
        self.box1v = wx.BoxSizer(wx.VERTICAL)
        self.label1 = wx.StaticText(self.panel, label="Следующие фильмы не найдены!")
        self.list_notfound = wx.TextCtrl(self.panel, value="\n".join(not_found), style=wx.TE_READONLY | wx.ALIGN_TOP | wx.TE_MULTILINE)
        self.btn = wx.Button(self.panel, wx.ID_OK, label="OK", size=self.FromDIP((100, 25)))

        self.box1v.Add(self.label1, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box1v.Add(self.list_notfound, proportion=1, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box1v.Add(self.btn, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.panel.SetSizer(self.box1v)


class PopMenu(wx.Menu):

    def __init__(self, parent):
        super(PopMenu, self).__init__()

        self.parent = parent

        self.m_openfile = wx.MenuItem(self, wx.ID_ANY, 'Проиграть файл')
        self.Bind(wx.EVT_MENU, parent.Parent.Parent.onPlayFile, id=self.m_openfile.GetId())
        self.m_opendir = wx.MenuItem(self, wx.ID_ANY, 'Открыть расположение')
        self.Bind(wx.EVT_MENU, parent.Parent.Parent.onOpenDir, id=self.m_opendir.GetId())
        self.m_del = wx.MenuItem(self, wx.ID_ANY, 'Удалить из списка')
        self.Bind(wx.EVT_MENU, parent.Parent.Parent.onDelItem, id=self.m_del.GetId())

        self.m_checkall = wx.MenuItem(self, wx.ID_ANY, 'Выбрать все')
        self.Bind(wx.EVT_MENU, parent.Parent.Parent.onCheckAllItems, id=self.m_checkall.GetId())
        self.m_uncheckall = wx.MenuItem(self, wx.ID_ANY, 'Снять все отметки')
        self.Bind(wx.EVT_MENU, parent.Parent.Parent.onUnCheckAllItems, id=self.m_uncheckall.GetId())
        self.m_delall = wx.MenuItem(self, wx.ID_ANY, 'Удалить все')
        self.Bind(wx.EVT_MENU, parent.Parent.Parent.onDelAllItems, id=self.m_delall.GetId())

        self.Append(self.m_openfile)
        self.Append(self.m_opendir)
        self.Append(self.m_del)
        self.AppendSeparator()
        self.Append(self.m_checkall)
        self.Append(self.m_uncheckall)
        self.AppendSeparator()
        self.Append(self.m_delall)


class MyFrame(wx.Frame):

    def __init__(self, parent, title):
        super().__init__(parent, title=title, style=(wx.DEFAULT_FRAME_STYLE | wx.WANTS_CHARS))

        # ========== Меню ==========
        menubar = wx.MenuBar()

        # меню "Файл"
        fileMenu = wx.Menu()
        item_open = wx.MenuItem(fileMenu, wx.ID_OPEN, "Открыть файл\tCtrl+O")
        item_exit = wx.MenuItem(fileMenu, wx.ID_EXIT, "Выход\tCtrl+Q")
        fileMenu.Append(item_open)
        fileMenu.AppendSeparator()
        fileMenu.Append(item_exit)
        menubar.Append(fileMenu, "Файл")

        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.onQuit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.onOpenFile, id=wx.ID_OPEN)

        # менею "Индекс"
        indexMenu = wx.Menu()
        item_open_index = wx.MenuItem(indexMenu, wx.ID_ANY, "Открыть файл индекса")
        item_create_index = wx.MenuItem(indexMenu, wx.ID_ANY, "Создать файл индекса")
        indexMenu.Append(item_open_index)
        indexMenu.Append(item_create_index)
        menubar.Append(indexMenu, "Индекс")
        self.Bind(wx.EVT_MENU, self.OnOpenIndex, id=item_open_index.GetId())
        self.Bind(wx.EVT_MENU, self.OnIndex, id=item_create_index.GetId())

        # меню "Справка"
        infoMenu = wx.Menu()
        item_about = wx.MenuItem(fileMenu, wx.ID_ANY, "О программе")
        infoMenu.Append(item_about)
        menubar.Append(infoMenu, "Справка")
        self.Bind(wx.EVT_MENU, self.onAboutBox, id=item_about.GetId())

        # ========== Основные элементы ==========
        self.panel = wx.Panel(self)
        self.gr = wx.GridBagSizer(3, 4)

        self.t_search = wx.TextCtrl(self.panel, size=self.FromDIP((850, 25)), style=wx.TE_PROCESS_ENTER)
        self.gr.Add(self.t_search, pos=(0, 0), span=(1, 3), flag=wx.EXPAND | wx.TOP | wx.LEFT, border=10)
        self.Bind(wx.EVT_TEXT_ENTER, self.onEnter)

        self.t_search.Bind(wx.EVT_KEY_DOWN, self.onKeyboardHandle)

        self.b_search = wx.Button(self.panel, wx.ID_ANY, size=self.FromDIP((100, 25)), label='Поиск')
        self.gr.Add(self.b_search, pos=(0, 3), flag=wx.ALIGN_LEFT | wx.TOP | wx.LEFT | wx.RIGHT, border=10)
        self.Bind(wx.EVT_BUTTON, self.onEnter, id=self.b_search.GetId())

        self.mainlist = wx.ListCtrl(self.panel, style=wx.LC_REPORT)
        self.gr.Add(self.mainlist, pos=(1, 0), span=(1, 4), flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.gr.AddGrowableCol(1)
        self.gr.AddGrowableRow(1)
        self.panel.SetSizer(self.gr)

        # Список
        self.mainlist.InsertColumn(0, 'Запрос', width=self.FromDIP(160))
        self.mainlist.InsertColumn(1, 'Путь к файлу', width=self.FromDIP(556))
        self.mainlist.InsertColumn(2, 'Размер', width=self.FromDIP(100))
        self.mainlist.InsertColumn(3, 'Разрешение', width=self.FromDIP(90))
        self.mainlist.InsertColumn(4, 'Теги', width=self.FromDIP(45))
        self.mainlist.EnableCheckBoxes()

        # Контекстное меню
        self.ctx_item = PopMenu(self.mainlist)
        self.mainlist.Bind(wx.EVT_RIGHT_DOWN, self.onRightDown)
        self.mainlist.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.onRightDownItem)
        self.mainlist.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onPlayFile)
        self.mainlist.Bind(wx.EVT_KEY_DOWN, self.onKeyboardHandle)
        self.mainlist.Bind(wx.EVT_LIST_ITEM_CHECKED, self.CountChecked)
        self.mainlist.Bind(wx.EVT_LIST_ITEM_UNCHECKED, self.CountChecked)

        # Текст - информация о статусе индекса
        self.l_nasinfo = wx.StaticText(self.panel, label=40 * '_')
        self.gr.Add(self.l_nasinfo, pos=(2, 0), flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)

        # Счетчик отметок
        self.l_counter = wx.StaticText(self.panel, label='Выбрано 0')
        self.gr.Add(self.l_counter, pos=(2, 1), flag=wx.ALIGN_RIGHT | wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)

        # Чекбокс
        self.save_option = wx.CheckBox(self.panel, label='Создавать симлинки')
        self.save_option.SetValue(True)
        self.gr.Add(self.save_option, pos=(2, 2), flag=wx.EXPAND | wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT, border=10)

        # Кнопка
        self.b_save = wx.Button(self.panel, wx.ID_ANY, size=self.FromDIP((100, 25)), label='Скопировать')
        self.gr.Add(self.b_save, pos=(2, 3), flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.Bind(wx.EVT_BUTTON, self.onSave, id=self.b_save.GetId())

    def post_init(self, nas_location):
        
        def check_nas_date(date_txt):
            '''Проверка, что nas.txt создан не более 1 дня назад'''
            date_obj = datetime.strptime(date_txt, '%d.%m.%Y')
            now = datetime.now()
            delta = now - date_obj
            if delta > timedelta(days=1):
                return '(!)' 
            else:
                return ''
        
        self.nas = NasIndex(nas_location)
        if self.nas.is_ready():
            self.l_nasinfo.Label = f"{os.path.basename(nas_location)}: (дата {self.nas.date}{check_nas_date(self.nas.date)}, файлов {len(self.nas.paths)})"
        else:
            self.l_nasinfo.Label = "Индекс не загружен"

    def onEnter(self, event):
        if not self.t_search.Value.strip():
            self.t_search.Value = ""
            self.t_search.SetFocus()
            return
        films = [self.t_search.Value.strip()]
        films = self.filter_symbols(films)
        films_not_found = []
        global stop_flag
        stop_flag = False
        open_thr = threading.Thread(target=self.open_files_thread, args=(films, self.nas, films_not_found, self.mainlist))
        open_thr.start()
        self.reset_colour(self.mainlist)
        self.disable_elements()
        while open_thr.is_alive():
            time.sleep(0.1)
            wx.GetApp().Yield()
            continue
        self.enable_elements()
        self.mark_doubles(self.mainlist)
        self.t_search.Value = ""
        self.t_search.SetFocus()

    def disable_elements(self):
        self.b_search.Disable()
        self.mainlist.Disable()
        self.b_save.Disable()
        self.save_option.Disable()

    def enable_elements(self):
        self.b_search.Enable()
        self.mainlist.Enable()
        self.b_save.Enable()
        self.save_option.Enable()

    def onRightDown(self, event):
        self.x = event.GetX()
        self.y = event.GetY()
        event.Skip()

    def onRightDownItem(self, event):
        self.PopupMenu(self.ctx_item, (self.x, self.y))

    @staticmethod
    def filter_symbols(title_list):
        filtered_list = []
        for title in title_list:
            trtable = title.maketrans('', '', '\/:*?"<>«»')
            filtered_list.append(title.translate(trtable))
        return filtered_list

    def onOpenFile(self, event):
        with wx.FileDialog(self,
                           "Открыть файл...",
                           os.getcwd(),
                           "",
                           "Текстовые файлы (*.txt)|*.txt|Все файлы (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            path_name = fileDialog.GetPath()
        films = file_to_list(path_name)
        films = self.filter_symbols(films)
        films_not_found = []
        global stop_flag
        stop_flag = False
        open_thr = threading.Thread(target=self.open_files_thread, args=(films, self.nas, films_not_found, self.mainlist))
        open_thr.start()
        self.reset_colour(self.mainlist)
        self.disable_elements()
        while open_thr.is_alive():
            time.sleep(0.1)
            wx.GetApp().Yield()
            continue
        self.enable_elements()
        self.mark_doubles(self.mainlist)
        if films_not_found:
            self.notfoundpanel = NotFoundPanel(self, "Внимание!", films_not_found)
            self.notfoundpanel.SetClientSize(self.FromDIP(wx.Size((300, 200))))
            self.notfoundpanel.CentreOnParent()
            self.notfoundpanel.ShowModal()

    @staticmethod
    def mark_doubles(list: wx.ListCtrl):

        # Сравниваем имена без расширений, потом пробуем убрать год в скобках и опять сравниваем имена
        def check(name1, name2):
            name1 = os.path.splitext(name1)[0]
            name2 = os.path.splitext(name2)[0]
            if name1 == name2:
                return True
            try:
                name1 = re.findall(r'(.+)\s\(\d{4}\)', name1)[0]
            except:
                pass
            try:
                name2 = re.findall(r'(.+)\s\(\d{4}\)', name2)[0]
            except:
                pass
            if name1 == name2:
                return True
            else:
                return False

        for i in range(list.GetItemCount()):
            if list.GetItemBackgroundColour(i) == wx.RED:
                continue
            list.SetItemBackgroundColour(i, wx.WHITE)
        for i in range(list.GetItemCount()):
            file_name_1 = os.path.basename(list.GetItemText(i, 1))
            for j in range(i + 1, list.GetItemCount()):
                file_name_2 = os.path.basename(list.GetItemText(j, 1))
                if check(file_name_1, file_name_2):
                    if list.GetItemBackgroundColour(i) != wx.RED:
                        list.SetItemBackgroundColour(i, wx.YELLOW)
                    if list.GetItemBackgroundColour(j) != wx.RED:
                        list.SetItemBackgroundColour(j, wx.YELLOW)

    @staticmethod
    def reset_colour(list: wx.ListCtrl):
        for i in range(list.GetItemCount()):
            list.SetItemBackgroundColour(i, (-1, -1, -1, 255))

    @staticmethod
    def open_files_thread(films, nas_obj, films_not_found, list: wx.ListCtrl):

        def find_whole_word(w):
            return re.compile(r'\b({0})\b'.format(w), flags=re.IGNORECASE).search

        paths = nas_obj.paths
        file_names = nas_obj.file_names
        for film in films:
            flag = False  # фильм найден
            for j, file_name in enumerate(file_names):
                global stop_flag
                if stop_flag:
                    return
                if find_whole_word(film)(file_name) != None:
                    try:
                        film_tag = Mp4Info(paths[j])
                        size = convert_bytes(film_tag.filesize)
                        dimm = f"{film_tag.width}\u00D7{film_tag.height}"
                        tags_ok = check_mark(film_tag.tags)
                        list.Append((film, paths[j], size, dimm, tags_ok))
                    except:
                        list.Append((film, paths[j], "-", "-", "-"))
                        list.SetItemBackgroundColour(list.GetItemCount() - 1, wx.RED)
                    flag = True
            if not flag:
                films_not_found.append(film)

    # создание симлинков
    def _onSimlink(self):
        if self.mainlist.GetItemCount() == 0:
            return
        with wx.DirDialog(None, "Выбор папки...", "", wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as d_dialog:
            if d_dialog.ShowModal() == wx.ID_CANCEL:
                return
            d_path = d_dialog.GetPath()
        for i in range(self.mainlist.GetItemCount()):
            if self.mainlist.IsItemChecked(i):
                src = self.mainlist.GetItemText(i, 1)
                if not os.path.isfile(src):
                    continue
                dst = os.path.join(d_path, os.path.basename(src))
                try:
                    os.symlink(src, dst)
                except FileExistsError:
                    try:
                        os.remove(dst)
                        os.symlink(src, dst)
                    except OSError:
                        wx.MessageDialog(
                            self,
                            'Не удалось создать символьную ссылку! Необходимо включить режим разработчика или запустить программу с правами администратора.',
                            'Ошибка', wx.OK | wx.ICON_ERROR).ShowModal()
                        return
                except OSError:
                    wx.MessageDialog(
                        self,
                        'Не удалось создать символьную ссылку! Необходимо включить режим разработчика или запустить программу с правами администратора.',
                        'Ошибка', wx.OK | wx.ICON_ERROR).ShowModal()
                    return
        subprocess.Popen(f'explorer "{d_path}"', shell=True)

    def _onCopy(self):
        if self.mainlist.GetItemCount() == 0:
            return
        with wx.DirDialog(None, "Выбор папки...", "", wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as d_dialog:
            if d_dialog.ShowModal() == wx.ID_CANCEL:
                return
            d_path = d_dialog.GetPath()
        for i in range(self.mainlist.GetItemCount()):
            if self.mainlist.IsItemChecked(i):
                src = self.mainlist.GetItemText(i, 1)
                if not os.path.isfile(src):
                    continue
                dst = d_path
                try:
                    winutils.copy(src=src, dst=dst)
                except Exception:
                    wx.MessageDialog(self, 'Копирование прервано!', 'Ошибка', wx.OK | wx.ICON_ERROR).ShowModal()
                    return
        subprocess.Popen(f'explorer "{d_path}"', shell=True)

    def onSave(self, event):

        def is_checked():
            for i in range(self.mainlist.GetItemCount()):
                if self.mainlist.IsItemChecked(i):
                    return True
            return False

        if is_checked():
            if self.save_option.GetValue():
                self._onSimlink()
            else:
                self._onCopy()

    def onPlayFile(self, event):
        path = self.mainlist.GetItemText(self.mainlist.FocusedItem, 1)
        if os.path.isfile(path):
            subprocess.Popen(f'"{path}"', shell=True)

    def onOpenDir(self, event):
        path = self.mainlist.GetItemText(self.mainlist.FocusedItem, 1)
        if os.path.isfile(path):
            subprocess.Popen(f'explorer /select,"{path}"', shell=True)
        else:
            subprocess.Popen(f'explorer "{os.path.dirname(path)}"', shell=True)

    def onDelItem(self, event):
        for i in range(self.mainlist.SelectedItemCount):
            selected = self.mainlist.GetFirstSelected()
            self.mainlist.DeleteItem(selected)
        self.mainlist.Select(self.mainlist.FocusedItem)
        self.CountChecked(self)
        self.mark_doubles(self.mainlist)

    def onDelAllItems(self, event):
        self.mainlist.DeleteAllItems()
        self.CountChecked(self)

    def onCheckAllItems(self, event):
        for i in range(self.mainlist.GetItemCount()):
            self.mainlist.CheckItem(i, check=True)

    def onUnCheckAllItems(self, event):
        for i in range(self.mainlist.GetItemCount()):
            self.mainlist.CheckItem(i, check=False)

    def onKeyboardHandle(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_DELETE:
            self.onDelItem(self)
        if key == wx.WXK_ESCAPE:
            global stop_flag
            stop_flag = True
        event.Skip()

    def onQuit(self, event):
        self.Close()

    def onAboutBox(self, event):
        description = """Программа для поиска фильмов по индексу."""
        licence = """MIT"""
        info = wx.adv.AboutDialogInfo()
        info.SetName('NAS Search GUI')
        info.SetVersion(VER)
        info.SetDescription(description)
        info.SetCopyright('(C) 2022 Alexander Vanyunin, Andrey Abramov, Ivan Kashtanov')
        info.SetLicence(licence)
        info.SetIcon(wx.Icon(get_resource_path("favicon.png"), wx.BITMAP_TYPE_PNG))
        wx.adv.AboutBox(info)

    def OnIndex(self, event):
        self.src = "z:\\"
        self.file_loc = FileLocation(self, 'Создание индекса', self.src, "nas.txt")
        if self.file_loc.ShowModal() == wx.ID_OK:
            self.index = IndexingPanel(self, 'Создание индекса', self.file_loc.t_nas_location.Value, "nas.txt")
            self.post_init("nas.txt")

    def OnOpenIndex(self, event):
        with wx.FileDialog(self,
                           "Открыть файл...",
                           os.getcwd(),
                           "",
                           "Текстовые файлы (*.txt)|*.txt|Все файлы (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            path_name = fileDialog.GetPath()
        self.l_nasinfo.Disable()
        self.post_init(path_name)
        self.l_nasinfo.Enable()

    def CountChecked(self, event):
        checked = 0
        for i in range(self.mainlist.GetItemCount()):
            if self.mainlist.IsItemChecked(i):
                checked += 1
        self.l_counter.Label = 'Выбрано: ' + str(checked)


def run_gui():
    app = wx.App()
    top = MyFrame(None, title=f"NAS Search GUI (ver {VER})")
    top.SetIcon(wx.Icon(get_resource_path("favicon.ico")))
    top.SetClientSize(top.FromDIP(wx.Size(980, 500)))
    top.SetMinSize(top.FromDIP(wx.Size(1000, 560)))
    top.Centre()
    top.Show()
    top.post_init('nas.txt')
    app.MainLoop()


def main():
    parser = argparse.ArgumentParser(
        prog='Nas Search GUI',
        description='Утилита для быстрого поиска файлов на NAS.',
    )
    parser.add_argument("-i",
                        "--index",
                        nargs=2,
                        help="создает файл индекса. Первый параметр - путь до NAS (z:\), второй - имя файла индекса (nas.txt)")
    args = parser.parse_args()
    if args.index:
        path, file = args.index[0], args.index[1]
        print(path, file)
        global stop_flag, result
        stop_flag = False
        result = True
        nas_scan1(path, file)
        if result:
            print(f'Создан файл индекса: {file}')
        else:
            print('Создание индекса приостановлено.')
    else:
        run_gui()


if __name__ == '__main__':
    main()