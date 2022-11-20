import ctypes
import os, sys
import threading
from glob import glob, iglob
from datetime import datetime
import time

import wx
import wx.adv
from pymediainfo import MediaInfo

ctypes.windll.shcore.SetProcessDpiAwareness(2)

VER = '0.1.1'


def convert_bytes(num):
    """
    Converts bytes to MB.... GB... etc
    """
    for x in ['bytes', 'K', 'M', 'G', 'T']:
        if num < 1024.0:
            return f'{num:3.1f}{x}'
        num /= 1024.0


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
            list = [x.strip() for x in f]
        return list
    else:
        raise FileNotFoundError(f'Файл {file} не найден.')


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
        if "title" in self.data and 'recorded_date' in self.data and 'description' in self.data and 'longdescription' in self.data and self.data[
                'cover'] == "Yes":
            self.tags = True


def check_mark(check: bool):
    if check:
        return "\u2714"
    else:
        return "\u274C"


class FileLocation(wx.Dialog):

    def __init__(self, parent, title, srs, dest):
        super().__init__(parent, title=title)
        self.SetClientSize(self.FromDIP(wx.Size((400, 80))))
        self.CentreOnParent()
        
        self.panel = wx.Panel(self)
        self.box1v = wx.BoxSizer(wx.VERTICAL)
        self.box1g = wx.BoxSizer(wx.HORIZONTAL)
        self.box2g = wx.BoxSizer(wx.HORIZONTAL)

        self.label1 = wx.StaticText(self.panel, label="Сетевой диск NAS:")
        self.t_nas_location = wx.TextCtrl(self.panel, value=srs)
        self.b_open_folder = wx.Button(self.panel, wx.ID_ANY, label="Открыть", size=self.FromDIP((60, 25)))
        self.Bind(wx.EVT_BUTTON, self.onOpenFolder, id=self.b_open_folder.GetId())
        self.box1g.Add(self.label1, flag= wx.ALIGN_CENTRE_VERTICAL | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.box1g.Add(self.t_nas_location,
                       proportion=1,
                       flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT,
                       border=5)
        self.box1g.Add(self.b_open_folder, flag= wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)

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
        pass

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
        self.scan(srs, dest)
        self.Hide()
        if result:
            wx.MessageDialog(self, 'Создание индекса завершено!', 'Создание индекса',
                             wx.OK | wx.ICON_INFORMATION).ShowModal()
        else:
            wx.MessageDialog(self, 'Создание индекса отменено!', 'Создание индекса',
                             wx.OK | wx.ICON_WARNING).ShowModal()
        self.Destroy()

    @staticmethod
    def scan(srs, dest):
        index_thr = threading.Thread(target=nas_scan1, args=(srs, dest))
        index_thr.daemon = True
        index_thr.start()
        while index_thr.is_alive():
            time.sleep(0.1)
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
        self.list_notfound = wx.TextCtrl(self.panel,
                                         value="\n".join(not_found),
                                         style=wx.TE_READONLY | wx.ALIGN_TOP | wx.TE_MULTILINE)
        self.btn = wx.Button(self.panel, wx.ID_OK, label="OK", size=self.FromDIP((100, 25)))

        self.box1v.Add(self.label1, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
        self.box1v.Add(self.list_notfound,
                       proportion=1,
                       flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT,
                       border=5)
        self.box1v.Add(self.btn, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=5)
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
        self.m_delall = wx.MenuItem(self, wx.ID_ANY, 'Удалить все')
        self.Bind(wx.EVT_MENU, parent.Parent.Parent.onDelAllItems, id=self.m_delall.GetId())

        self.Append(self.m_openfile)
        self.Append(self.m_opendir)
        self.Append(self.m_del)
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
        # item_save = wx.MenuItem(fileMenu, wx.ID_SAVE, "Сохранить файл\tCtrl+S")
        item_exit = wx.MenuItem(fileMenu, wx.ID_EXIT, "Выход\tCtrl+Q")
        fileMenu.Append(item_open)
        # fileMenu.Append(item_save)
        fileMenu.AppendSeparator()
        fileMenu.Append(item_exit)
        menubar.Append(fileMenu, "Файл")

        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.onQuit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.onOpenFile, id=wx.ID_OPEN)
        # self.Bind(wx.EVT_MENU, self.onSaveFile, id=wx.ID_SAVE)

        # менею "Индекс"
        indexMenu = wx.Menu()
        item_create_index = wx.MenuItem(indexMenu, wx.ID_ANY, "Создать файл индекса")
        indexMenu.Append(item_create_index)
        menubar.Append(indexMenu, "Индекс")
        self.Bind(wx.EVT_MENU, self.OnIndex, id=item_create_index.GetId())

        # меню "Справка"
        infoMenu = wx.Menu()
        item_about = wx.MenuItem(fileMenu, wx.ID_ANY, "О программе")
        infoMenu.Append(item_about)
        menubar.Append(infoMenu, "Справка")
        self.Bind(wx.EVT_MENU, self.onAboutBox, id=item_about.GetId())

        # ========== Основные элементы ==========
        self.panel = wx.Panel(self)
        self.gr = wx.GridBagSizer(2, 2)

        self.mainlist = wx.ListCtrl(self.panel, style=wx.LC_REPORT)
        self.gr.Add(self.mainlist,
                    pos=(0, 0),
                    span=(1, 2),
                    flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT,
                    border=10)
        self.gr.AddGrowableCol(0)
        self.gr.AddGrowableRow(0)
        self.panel.SetSizer(self.gr)

        # Список
        self.mainlist.InsertColumn(0, 'Фильм', width=self.FromDIP(160))
        self.mainlist.InsertColumn(1, 'Путь к файлу', width=self.FromDIP(556))
        self.mainlist.InsertColumn(2, 'Размер', width=self.FromDIP(100))
        self.mainlist.InsertColumn(3, 'Разрешение', width=self.FromDIP(90))
        self.mainlist.InsertColumn(4, 'Теги', width=self.FromDIP(45))
        self.mainlist.EnableCheckBoxes()

        self.ctx_item = PopMenu(self.mainlist)
        self.mainlist.Bind(wx.EVT_RIGHT_DOWN, self.onRightDown)
        self.mainlist.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.onRightDownItem)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onPlayFile, id=self.mainlist.GetId())
        self.mainlist.Bind(wx.EVT_KEY_DOWN, self.onKeyboardHandle)

        # Кнопка
        self.b_save = wx.Button(self.panel, wx.ID_ANY, size=self.FromDIP((100, 25)), label='Сохранить')
        self.gr.Add(self.b_save, pos=(1, 1), flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.Bind(wx.EVT_BUTTON, self.onSave, id=self.b_save.GetId())

    def onRightDown(self, event):
        self.x = event.GetX()
        self.y = event.GetY()
        event.Skip()

    def onRightDownItem(self, event):
        self.PopupMenu(self.ctx_item, (self.x, self.y))

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
        # films = file_to_list('1.txt')
        paths = file_to_list('nas.txt')
        file_names = [os.path.splitext(os.path.basename(x))[0] for x in paths]
        films_not_found = []
        for film in films:
            flag = False
            for j, file_name in enumerate(file_names):
                if file_name.lower().find(film.lower()) != -1:
                    film_tag = Mp4Info(paths[j])
                    size = convert_bytes(film_tag.filesize)
                    dimm = f"{film_tag.width}\u00D7{film_tag.height}"
                    tags_ok = check_mark(film_tag.tags)
                    self.mainlist.Append((film, paths[j], size, dimm, tags_ok))
                    flag = True
            if not flag:
                films_not_found.append(film)
        if films_not_found:
            self.notfoundpanel = NotFoundPanel(self, "Внимание!", films_not_found)
            self.notfoundpanel.SetClientSize(self.FromDIP(wx.Size((300, 200))))
            self.notfoundpanel.CentreOnParent()
            self.notfoundpanel.ShowModal()

    def onSave(self, event):
        if self.mainlist.GetItemCount() == 0:
            return
        with wx.DirDialog(None, "Выбор папки...", "", wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as d_dialog:
            if d_dialog.ShowModal() == wx.ID_CANCEL:
                return
            d_path = d_dialog.GetPath()
        for i in range(self.mainlist.GetItemCount()):
            if self.mainlist.IsItemChecked(i):
                src = self.mainlist.GetItemText(i, 1)
                dst = os.path.join(d_path, os.path.basename(src))
                try:
                    os.symlink(src, dst)
                except FileExistsError:
                    os.remove(dst)
                    os.symlink(src, dst)
        os.system(f'explorer "{d_path}"')

    def onPlayFile(self, event):
        path = self.mainlist.GetItemText(self.mainlist.FocusedItem, 1)
        os.system(f'"{path}"')

    def onOpenDir(self, event):
        path = os.path.dirname(self.mainlist.GetItemText(self.mainlist.FocusedItem, 1))
        os.system(f'explorer "{path}"')

    def onDelItem(self, event):
        for i in range(self.mainlist.SelectedItemCount):
            selected = self.mainlist.GetFirstSelected()
            self.mainlist.DeleteItem(selected)
        self.mainlist.Select(self.mainlist.FocusedItem)

    def onDelAllItems(self, event):
        self.mainlist.DeleteAllItems()

    def onKeyboardHandle(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_DELETE:
            self.onDelItem(self)
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
        info.SetCopyright('(C) 2022 Alexander Vanyunin, Anrey Abramov, Ivan Kashtanov')
        info.SetLicence(licence)
        info.SetIcon(wx.Icon(get_resource_path("favicon.png"), wx.BITMAP_TYPE_PNG))
        wx.adv.AboutBox(info)

    def OnIndex(self, event):
        # self.src = r'C:\Users\ALeX\Documents\Python'
        self.src = "h:\\"
        self.file_loc = FileLocation(self, 'Создание индекса', self.src, "nas.txt")
        # self.file_loc.SetClientSize(self.file_loc.FromDIP(wx.Size((300, 80))))
        # self.file_loc.CentreOnParent()
        if self.file_loc.ShowModal() == wx.ID_OK:
            self.index = IndexingPanel(self, 'Создание индекса', self.file_loc.t_nas_location.Value, "nas.txt")


def main():
    app = wx.App()
    top = MyFrame(None, title=f"NAS Search GUI ({VER})")
    top.SetIcon(wx.Icon(get_resource_path("favicon.ico")))
    top.SetClientSize(top.FromDIP(wx.Size(980, 500)))
    top.SetMinSize(top.FromDIP(wx.Size(1000, 560)))
    top.Centre()
    top.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()