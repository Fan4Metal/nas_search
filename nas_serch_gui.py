import ctypes
import os, sys
import threading
import time
import winreg

import wx
import wx.adv
from pymediainfo import MediaInfo

ctypes.windll.shcore.SetProcessDpiAwareness(2)


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

        popmenu = wx.MenuItem(self, wx.ID_ANY, 'Удалить ')
        self.Append(popmenu)
        self.AppendSeparator()
        popmenu2 = wx.MenuItem(self, wx.ID_ANY, 'Удалить все')
        self.Append(popmenu2)


class MyFrame(wx.Frame):

    def __init__(self, parent, title):
        super().__init__(parent, title=title, style=(wx.DEFAULT_FRAME_STYLE | wx.WANTS_CHARS))

        # ========== Меню ==========
        menubar = wx.MenuBar()

        # меню "Файл"
        fileMenu = wx.Menu()
        item_open = wx.MenuItem(fileMenu, wx.ID_OPEN, "Открыть файл\tCtrl+O")
        item_save = wx.MenuItem(fileMenu, wx.ID_SAVE, "Сохранить файл\tCtrl+S")
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
        self.mainlist.InsertColumn(1, 'Путь к файлу', width=self.FromDIP(570))
        self.mainlist.InsertColumn(2, 'Размер', width=self.FromDIP(100))
        self.mainlist.InsertColumn(3, 'Разрешение', width=self.FromDIP(90))
        self.mainlist.InsertColumn(4, 'Теги', width=self.FromDIP(45))
        self.mainlist.EnableCheckBoxes()

        self.ctx_item = PopMenu(self.mainlist)
        self.mainlist.Bind(wx.EVT_RIGHT_DOWN, self.onRightDown)
        self.mainlist.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.onRightDownItem)

        # self.mainlist.Append(("Матрица", "111111111111111111111111111111111111", "1", "1920x1080"))

        # Кнопка
        self.b_save = wx.Button(self.panel, wx.ID_ANY, size=self.FromDIP((100, 25)), label='Сохранить')
        self.gr.Add(self.b_save, pos=(1, 1), flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.Bind(wx.EVT_BUTTON, self.onSave, id=self.b_save.GetId())

    def onRightDown(self, event):
        # self.PopupMenu(self.ctx, event.GetPosition())
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

    def onQuit(self, event):
        self.Close()


def main():
    app = wx.App()
    top = MyFrame(None, title="NAS Search GUI (alpha version)")
    # top.SetIcon(wx.Icon(get_resource_path("favicon.ico")))
    top.SetClientSize(top.FromDIP(wx.Size(980, 500)))
    top.SetMinSize(top.FromDIP(wx.Size(1000, 560)))
    top.Centre()
    top.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()